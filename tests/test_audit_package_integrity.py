import hashlib
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
import audit_package_integrity as audit
import audit_boot_first_installer as installer


class IntegrityTests(unittest.TestCase):
    def test_avb_footer_detection_and_bounds(self):
        self.assertEqual(audit.footer_observation(b'\0' * 64, 1024)['status'], 'canonical_avb_footer_not_seen')
        good = struct.pack('>4sIIQQQ28s', b'AVBf', 1, 0, 600, 700, 100, b'\0' * 28)
        result = audit.footer_observation(good, 1024)
        self.assertEqual(result['status'], 'footer_present')
        self.assertTrue(result['bounds_valid'])
        bad = struct.pack('>4sIIQQQ28s', b'AVBf', 1, 0, 600, 1000, 100, b'\0' * 28)
        self.assertEqual(audit.footer_observation(bad, 1024)['status'], 'footer_present_invalid_bounds')

    def test_member_hash_and_crc_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'test.zip'
            data = b'synthetic image only'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('boot.img', data)
            expected = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            with zipfile.ZipFile(p) as z:
                row = audit.stream_image(z, 'boot.img', expected)
                self.assertTrue(row['zip_crc_checked_at_eof'])
                with self.assertRaises(audit.IntegrityAuditError):
                    audit.stream_image(z, 'boot.img', {'bytes': len(data), 'sha256': '0' * 64})
                with self.assertRaises(audit.IntegrityAuditError):
                    audit.stream_image(z, 'boot.img', {'bytes': len(data) + 1, 'sha256': expected['sha256']})

    def test_synthetic_package_metadata_without_device_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'test.zip'
            images = {'boot.img': b'a' * 100, 'dtbo.img': b'b' * 80}
            members = {installer.SCRIPT: b'synthetic script', installer.BINARY: b'not a binary',
                       installer.METADATA: b'ota-property-files=metadata:0:10\n', installer.METADATA_PB: b'synthetic',
                       'super.img': b'not a real super', **images}
            with zipfile.ZipFile(p, 'w') as z:
                for name, data in members.items():
                    z.writestr(name, data)
            before = hashlib.sha256(p.read_bytes()).hexdigest()
            expected = {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                        for name, data in images.items()}
            result = audit.inspect(p, expected)
            self.assertEqual(result['whole_file_android_ota_signature_footer'], 'not_present_empty_zip_comment')
            self.assertEqual(result['vbmeta_image_entries'], [])
            self.assertEqual(result['ota_metadata_offsets'][0]['name'], 'metadata')
            self.assertFalse(result['ota_metadata_offsets'][0]['offset_matches'])
            self.assertEqual(before, hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertTrue(any('does not rule out' in x for x in result['limitations']))

    def test_duplicate_zip_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'duplicate.zip'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(p, 'w') as z:
                    for name in (installer.SCRIPT, installer.BINARY, installer.METADATA,
                                 installer.METADATA_PB, 'super.img', 'boot.img', 'dtbo.img', 'boot.img'):
                        z.writestr(name, b'x')
            with self.assertRaises(installer.AuditError):
                audit.inspect(p, {})


if __name__ == '__main__':
    unittest.main()
