import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import synthetica2_delta as delta  # noqa: E402
spec = importlib.util.spec_from_file_location('integrated_experiment', ROOT / 'synthetica-project/restore_synthetica2_integrated_experiment.py')
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)


class IntegratedExperimentTests(unittest.TestCase):
    def setUp(self):
        self.old = b'abcdefghijklmnop'; self.new = b'abcdWXYZijkl1234'
        self.windows = [(4, 8), (12, 16)]
        patch = io.BytesIO()
        self.patch_report = delta.build_diff(io.BytesIO(self.old), io.BytesIO(self.new), patch, 16, self.windows, block=4, chunk=8)
        self.patch = patch.getvalue()
        self.boot = b'HOST-ONLY-BOOT'; self.dtbo = b'ORIGINAL-DTBO'
        self.dtbo_spec = (len(self.dtbo), hashlib.sha256(self.dtbo).hexdigest())
        self.manifest = {'patch': self.patch_report}
        self.report = {'status': 'HOST_ONLY_DO_NOT_FLASH', 'device_tested': False}
        self.base = io.BytesIO()
        with zipfile.ZipFile(self.base, 'w') as z:
            z.writestr('super.img', self.old); z.writestr('dtbo.img', self.dtbo)
        self.source = self.source_zip(self.patch)

    def source_zip(self, patch, installer=delta.INSTALLER):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            z.writestr('delta/super.patch', patch)
            for name in delta.DOCS:
                data = {delta.DOCS[1]: installer, delta.DOCS[2]: delta.UPDATER}.get(name, ('doc:' + name).encode())
                z.writestr('files/' + name, data)
        return stream

    def create_candidate(self, source=None, dtbo_spec=None):
        result = io.BytesIO(); self.base.seek(0); (source or self.source).seek(0)
        with zipfile.ZipFile(self.base) as b, zipfile.ZipFile(source or self.source) as d, zipfile.ZipFile(result, 'w') as out:
            exp.write_archive(b, d, out, self.manifest, self.boot, self.report,
                              windows=self.windows, dtbo_spec=dtbo_spec or self.dtbo_spec)
        result.seek(0)
        return result

    def test_streams_and_verifies_integrated_members_and_inert_installer(self):
        result = self.create_candidate(); self.source.seek(0)
        with zipfile.ZipFile(result) as z, zipfile.ZipFile(self.source) as d:
            exp.verify_archive(z, d, self.manifest, self.boot, self.report, dtbo_spec=self.dtbo_spec)
            self.assertEqual(z.read(delta.SUPER_NAME), self.new)
            self.assertEqual(z.read(delta.BOOT_NAME), self.boot)
            self.assertEqual(z.read(delta.DTBO_NAME), self.dtbo)
            self.assertEqual(z.read(delta.DOCS[1]), delta.INSTALLER)
            self.assertEqual(z.read(delta.DOCS[2]), delta.UPDATER)
            self.assertEqual(z.read(delta.DOCS[0]), exp.README)
            self.assertIn(b'DO NOT FLASH', z.comment)

    def test_bad_patch_dtbo_or_active_installer_is_rejected(self):
        with self.assertRaises(delta.DeltaError): self.create_candidate(self.source_zip(self.patch[:-1] + b'!'))
        with self.assertRaises(ValueError): self.create_candidate(dtbo_spec=(len(self.dtbo), '0'*64))
        with self.assertRaises(ValueError): self.create_candidate(self.source_zip(self.patch, b'flash everything'))

    def test_readback_detects_tampered_member_with_valid_zip_crc(self):
        result = self.create_candidate(); result.seek(0); modified = io.BytesIO()
        with zipfile.ZipFile(result) as old, zipfile.ZipFile(modified, 'w') as new:
            for entry in old.infolist():
                data = old.read(entry)
                if entry.filename == delta.BOOT_NAME: data = b'BAD' + data[3:]
                new.writestr(entry.filename, data)
        modified.seek(0); self.source.seek(0)
        with zipfile.ZipFile(modified) as z, zipfile.ZipFile(self.source) as d, self.assertRaises(ValueError):
            exp.verify_archive(z, d, self.manifest, self.boot, self.report, dtbo_spec=self.dtbo_spec)

    def test_readback_rejects_extra_members(self):
        result = self.create_candidate()
        with zipfile.ZipFile(result, 'a') as z: z.writestr('unexpected', b'x')
        result.seek(0); self.source.seek(0)
        with zipfile.ZipFile(result) as z, zipfile.ZipFile(self.source) as d, self.assertRaises(ValueError):
            exp.verify_archive(z, d, self.manifest, self.boot, self.report, dtbo_spec=self.dtbo_spec)

    def test_complete_restore_readback_and_failure_cleanup_with_synthetic_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); private = root / '.work-private'; private.mkdir()
            original = private / 'original.zip'; original.write_bytes(self.base.getvalue())
            source = private / 'base-delta.zip'; source.write_bytes(self.source.getvalue())
            boot_path = private / 'boot.img'; boot_path.write_bytes(self.boot)
            output = private / 'DO-NOT-FLASH-out.zip'
            source_spec = delta.sha_file(source)
            new_boot_spec = (len(self.boot), hashlib.sha256(self.boot).hexdigest())
            with mock.patch.object(exp, 'ROOT', root), mock.patch.object(exp, 'BASE_DELTA', source_spec), \
                    mock.patch.object(exp, 'NEW_BOOT', new_boot_spec), mock.patch.object(exp, 'DTBO', self.dtbo_spec), \
                    mock.patch.object(exp, 'verify_boot', return_value=self.report), \
                    mock.patch.object(delta, 'WINDOWS', self.windows), mock.patch.object(delta, 'open_manifest', return_value=self.manifest), \
                    mock.patch.object(delta, 'checked_original'):
                report = exp.restore(original, source, boot_path, output)
                self.assertFalse(report['flashable'])
                self.assertTrue(report['archive_members_readback_verified'])
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                with zipfile.ZipFile(output) as z:
                    self.assertEqual(z.read(delta.SUPER_NAME), self.new)
                    self.assertEqual(z.read(delta.BOOT_NAME), self.boot)
                with self.assertRaises(ValueError): exp.restore(original, source, boot_path, output)
                failed = private / 'DO-NOT-FLASH-failed.zip'
                with mock.patch.object(exp, 'verify_archive', side_effect=ValueError('failed readback')):
                    with self.assertRaises(ValueError): exp.restore(original, source, boot_path, failed)
                self.assertFalse(failed.exists())
                self.assertFalse(failed.with_name(failed.name + '.INCOMPLETE').exists())
                raced = private / 'DO-NOT-FLASH-raced.zip'
                real_link = exp.os.link
                def collide(src, dst, **kwargs):
                    Path(dst).write_bytes(b'existing')
                    return real_link(src, dst, **kwargs)
                with mock.patch.object(exp.os, 'link', side_effect=collide):
                    with self.assertRaises(FileExistsError): exp.restore(original, source, boot_path, raced)
                self.assertEqual(raced.read_bytes(), b'existing')
                self.assertFalse(raced.with_name(raced.name + '.INCOMPLETE').exists())

    def test_real_boot_verifier_rejects_any_other_input(self):
        with self.assertRaises(ValueError): exp.verify_boot(b'not the pinned boot')

    def test_refuses_output_outside_private_scratch_or_existing(self):
        with self.assertRaises(ValueError):
            exp.restore(Path('missing'), Path('missing'), Path('missing'), Path('/tmp/DO-NOT-FLASH-out.zip'))
        with self.assertRaises(ValueError):
            exp.restore(Path('missing'), Path('missing'), Path('missing'), ROOT)


if __name__ == '__main__': unittest.main()
