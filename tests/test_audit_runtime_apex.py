import hashlib
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
from test_audit_vendor_elf_metadata import fake_elf
import audit_runtime_apex as audit
import audit_vintf_candidate as inventory


class RuntimeApexTests(unittest.TestCase):
    def test_exact_payload_only_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apex = root / 'one.apex'
            with zipfile.ZipFile(apex, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('../not-extracted', b'never written')
                z.writestr('apex_payload.img', b'only payload')
            meta = audit.extract_payload(apex, root / 'payload')
            self.assertEqual((root / 'payload').read_bytes(), b'only payload')
            self.assertTrue(meta['zip_crc_checked_at_eof'])
            self.assertFalse((root.parent / 'not-extracted').exists())
            duplicate = root / 'duplicate.apex'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(duplicate, 'w') as z:
                    z.writestr('apex_payload.img', b'a')
                    z.writestr('apex_payload.img', b'b')
            with self.assertRaises(audit.ApexAuditError):
                audit.extract_payload(duplicate, root / 'not-created')
            self.assertFalse((root / 'not-created').exists())

    def test_payload_filesystem_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'img'
            p.write_bytes(b'\0' * 1024 + b'\xe2\xe1\xf5\xe0' + b'\0' * 60)
            self.assertEqual(audit.payload_format(p), 'erofs')
            p.write_bytes(b'\0' * 1080 + b'\x53\xef' + b'\0' * 6)
            self.assertEqual(audit.payload_format(p), 'ext4')
            p.write_bytes(b'not a filesystem')
            self.assertEqual(audit.payload_format(p), 'unknown')

    @unittest.skipUnless(inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs are required')
    def test_erofs_callback_must_use_exact_payload_and_may_report_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tree = root / 'tree'
            (tree / 'system/apex').mkdir(parents=True)
            erofs = b'\0' * 1024 + b'\xe2\xe1\xf5\xe0' + b'\0' * 60
            with zipfile.ZipFile(tree / 'system/apex/com.android.runtime.apex', 'w') as z:
                z.writestr('apex_payload.img', erofs)
            image = root / 'system.img'
            with image.open('wb') as f:
                f.truncate(16 * 1024**2)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(tree), str(image)], check=True)
            def incomplete(payload):
                return {'input_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
                        'tool_exit_code': 1, 'files': []}
            result = audit.inspect_system(image, erofs_inspector=incomplete)
            self.assertEqual(result['payload']['filesystem'], 'erofs')
            self.assertEqual(result['payload']['linker_headers'], 'not_inspected_tool_error')
            with self.assertRaises(audit.ApexAuditError):
                audit.inspect_system(image, erofs_inspector=lambda _: {'input_sha256': 'wrong', 'tool_exit_code': 0})

    @unittest.skipUnless(inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs are required')
    def test_runtime_apex_linkers_are_inspected_as_data_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload_tree = root / 'payload_tree'
            (payload_tree / 'bin').mkdir(parents=True)
            (payload_tree / 'bin/linker').write_bytes(fake_elf(32, 40, '/system/bin/linker'))
            (payload_tree / 'bin/linker64').write_bytes(fake_elf(64, 183, '/system/bin/linker64'))
            payload = root / 'payload.img'
            with payload.open('wb') as f:
                f.truncate(16 * 1024**2)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(payload_tree), str(payload)],
                           check=True)
            system_tree = root / 'system_tree'
            (system_tree / 'system/apex').mkdir(parents=True)
            package = system_tree / 'system/apex/com.android.runtime.apex'
            with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.write(payload, 'apex_payload.img')
            system = root / 'system.img'
            with system.open('wb') as f:
                f.truncate(16 * 1024**2)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(system_tree), str(system)],
                           check=True)
            before = hashlib.sha256(system.read_bytes()).hexdigest()
            result = audit.inspect_system(system)
            self.assertEqual(result['payload']['filesystem'], 'ext4')
            self.assertEqual(result['payload']['linker_headers'][0]['elf']['architecture'], 'ARM')
            self.assertEqual(result['payload']['linker_headers'][1]['elf']['architecture'], 'AArch64')
            self.assertFalse(result['apex_signature_verified'])
            self.assertEqual(before, hashlib.sha256(system.read_bytes()).hexdigest())
            self.assertFalse(any(p.name.startswith('runtime-apex-audit-') for p in root.iterdir()))


if __name__ == '__main__':
    unittest.main()
