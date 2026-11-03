import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import feature_ext4 as f

@unittest.skipUnless(f.guard.pytsk3 is not None and Path('/usr/sbin/mke2fs').exists(), 'requires pytsk3 and e2fsprogs')
class FeatureExt4Tests(unittest.TestCase):
    def setUp(self):
        # A relative temp directory under the repository has a debugfs-safe path.
        self.temp = tempfile.TemporaryDirectory(prefix='.work-ext4-test-', dir=str(ROOT))
        self.base = Path(self.temp.name)
        self.image = self.base / 'before.img'
        with self.image.open('wb') as out: out.truncate(64 * 1024 * 1024)
        subprocess.run(['/usr/sbin/mke2fs', '-q', '-t', 'ext4', '-F', str(self.image)], check=True)
        self.label = self.base / 'label'; self.label.write_bytes(f.LABEL)
        self.old = self.base / 'old'; self.old.write_bytes(b'untouched existing file')
        commands = self.base / 'setup'
        commands.write_text('mkdir /app\n' + f'ea_set -f {self.label} /app security.selinux\n' +
                            f'write {self.old} /app/existing.apk\n')
        subprocess.run([f.DEBUGFS, '-w', '-f', str(commands), str(self.image)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        self.apk = self.base / 'candidate.apk'; self.apk.write_bytes(b'a synthetic APK, not executable')
        self.sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        self.after = self.base / 'after.img'
        self.work = self.base / 'scratch'; self.work.mkdir()
    def tearDown(self): self.temp.cleanup()
    def test_addition_only_and_source_not_changed(self):
        r = f.edit(self.image, self.after, self.apk, self.work, self.sha)
        self.assertEqual(r['status'], 'only_nonprivileged_spatialflow_paths_added')
        self.assertEqual(r['e2fsck_read_only_exit'], 0)
        self.assertEqual(r['apk_sha256'], self.sha)
        self.assertTrue(r['source_image_and_apk_unchanged'])
    def test_safe_growth_preserves_all_existing_paths_and_checks_fs(self):
        r = f.edit(self.image, self.after, self.apk, self.work, self.sha, grow_by=16 * 1024 * 1024)
        self.assertEqual(r['after_bytes'], r['before_bytes'] + 16 * 1024 * 1024)
        self.assertEqual(r['growth_bytes'], 16 * 1024 * 1024)
        self.assertTrue(r['source_image_and_apk_unchanged'])
    def test_growth_bounds_and_alignment_are_enforced(self):
        for size in (-4096, 1, f.MAX_GROWTH + 4096):
            with self.subTest(size=size), self.assertRaises(f.FeatureImageError):
                f.edit(self.image, self.after, self.apk, self.work, self.sha, grow_by=size)
        self.assertFalse(self.after.exists())
    def test_invalid_app_hash_rejected_before_output(self):
        with self.assertRaises(f.FeatureImageError): f.edit(self.image, self.after, self.apk, self.work, '0' * 64)
        self.assertFalse(self.after.exists())
    def test_existing_destination_is_never_overwritten(self):
        self.after.write_bytes(b'untouched')
        with self.assertRaises(f.FeatureImageError): f.edit(self.image, self.after, self.apk, self.work, self.sha)
        self.assertEqual(self.after.read_bytes(), b'untouched')
    def test_changed_old_file_is_detected(self):
        f.edit(self.image, self.after, self.apk, self.work, self.sha)
        cmd = self.base / 'tamper'; cmd.write_text('rm /app/existing.apk\n')
        subprocess.run([f.DEBUGFS, '-w', '-f', str(cmd), str(self.after)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        with self.assertRaises(f.FeatureImageError): f.compare(self.image, self.after, self.apk.stat().st_size, self.sha)
    def test_unexpected_new_file_is_detected(self):
        f.edit(self.image, self.after, self.apk, self.work, self.sha)
        cmd = self.base / 'extra'; cmd.write_text(f'write {self.old} /app/surprise\n')
        subprocess.run([f.DEBUGFS, '-w', '-f', str(cmd), str(self.after)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        with self.assertRaises(f.FeatureImageError): f.compare(self.image, self.after, self.apk.stat().st_size, self.sha)
    def test_bad_label_is_detected(self):
        f.edit(self.image, self.after, self.apk, self.work, self.sha)
        cmd = self.base / 'badlabel'; cmd.write_text(f'ea_rm {f.APK_PATH} security.selinux\n')
        subprocess.run([f.DEBUGFS, '-w', '-f', str(cmd), str(self.after)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        with self.assertRaises(f.FeatureImageError): f.compare(self.image, self.after, self.apk.stat().st_size, self.sha)

if __name__ == '__main__': unittest.main()
