"""Packaging checks for the 3.0-rc1 test ZIP; not physical recovery tests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s3rc_pkg', ROOT / 'build-kit/scripts/package_synthetica3_rc.py')
pkg = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pkg)


class TemplateGuardTests(unittest.TestCase):
    def test_exact_previously_exercised_templates_are_pinned(self):
        entry = (pkg.SCRIPTS / 'anykernel.sh').read_bytes()
        prep = (pkg.SCRIPTS / 'prepare-boot.sh').read_bytes()
        self.assertEqual(pkg.sha(entry), pkg.ENTRY_SHA256)
        self.assertEqual(pkg.sha(prep), pkg.PREPARE_SHA256)
        self.assertEqual(pkg.sha(pkg.BASE.read_bytes()), pkg.BASE_SHA256)
        self.assertEqual(entry.count(pkg.build.TESTED_IMAGE_SHA256.encode()), 1)
        self.assertEqual(entry.count(pkg.REFERENCE_DTB_SHA256.encode()), 1)
        for required in (b'BLOCK=/dev/block/bootdevice/by-name/boot', b'cmp -s "$original" "$BLOCK"',
                         b'conv=fsync', b'cmp -s -n "$partsize" "$candidate" "$BLOCK"',
                         b'do.modules=0', b'do.systemless=0'):
            self.assertIn(required, entry)
        self.assertNotIn(b'/data/adb/ksud', entry)
        self.assertIn(b'PATCHVBMETAFLAG=false', prep)
        self.assertNotIn(b'/dev/block', prep)

    def test_warning_never_claims_camera_root_or_seccomp_verified(self):
        text = pkg.readme('a' * 64, 'b' * 64)
        self.assertIn('BUKAN RILIS STABIL', text)
        self.assertIn('BELUM DIUJI', text)
        self.assertIn('TIDAK berisi perbaikan kamera', text)
        self.assertIn('tidak diubah', text)
        self.assertIn('tidak membuat backup otomatis', text)
        self.assertIn('Signature boot lama mungkin tidak lagi valid', text)


class CandidatePackageTests(unittest.TestCase):
    def setUp(self):
        result, config = os.environ.get('S3RC_EVIDENCE_DIR'), os.environ.get('S3RC_TESTED_CONFIG')
        if not result or not config:
            self.skipTest('S3RC_EVIDENCE_DIR and S3RC_TESTED_CONFIG required for real candidate packaging')
        self.result, self.config = Path(result), Path(config)
        if not self.result.is_dir() or not self.config.is_file():
            self.fail('candidate evidence or tested config is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_package_integrity_reproducibility_and_exact_payload(self):
        a, b = self.work / 'a.zip', self.work / 'b.zip'
        info = pkg.package(self.result, self.config, a)
        pkg.package(self.result, self.config, b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with zipfile.ZipFile(a) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()), set(pkg.BASE_FILES) | {
                'Image.gz', 'anykernel.sh', 'tools/prepare-boot.sh', 'README-FLASH.txt', 'BUILD-INFO.json'})
            image = z.read('Image.gz')
            entry = z.read('anykernel.sh')
            meta = json.loads(z.read('BUILD-INFO.json'))
            self.assertEqual(pkg.sha(image), info['image_sha256'])
            self.assertEqual(meta['image_sha256'], info['image_sha256'])
            self.assertEqual(entry.count(meta['image_sha256'].encode()), 1)
            self.assertEqual(entry.count(pkg.REFERENCE_DTB_SHA256.encode()), 1)
            self.assertNotIn(pkg.build.TESTED_IMAGE_SHA256.encode(), entry)
            self.assertIn(b'Synthetica 3.0-rc1 TEST', entry)
            for file in ('anykernel.sh', 'tools/prepare-boot.sh'):
                path = self.work / Path(file).name
                path.write_bytes(z.read(file))
                subprocess.run(['sh', '-n', str(path)], check=True)
                subprocess.run(['busybox', 'ash', '-n', str(path)], check=True)
            self.assertFalse(any(x.endswith(('.pem', '.key', '.ko')) for x in z.namelist()))

    def test_tampered_status_image_or_config_is_refused_without_output(self):
        copied = self.work / 'evidence'
        shutil.copytree(self.result, copied)
        out = self.work / 'should-not-exist.zip'
        status_path = copied / 'STATUS.json'
        status = status_path.read_bytes()
        changed = json.loads(status)
        changed['manager_seccomp_patch_sha256'] = '0' * 64
        status_path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            pkg.package(copied, self.config, out)
        self.assertFalse(out.exists())
        status_path.write_bytes(status)
        image_path = copied / 'Image.gz.DO-NOT-FLASH'
        with image_path.open('ab') as f:
            f.write(b'tampered')
        with self.assertRaises(ValueError):
            pkg.package(copied, self.config, out)
        self.assertFalse(out.exists())
        bad_config = self.work / 'bad.config'
        bad_config.write_bytes(self.config.read_bytes() + b'# tampered\n')
        with self.assertRaises(ValueError):
            pkg.package(self.result, bad_config, out)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
