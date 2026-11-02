"""Synthetic VNDK APEX fixtures; no ROM code is executed or installed."""
import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_vndk_apex as audit
import audit_vendor_abi as abi


def field_string(number, text):
    data = text.encode()
    assert number < 16 and len(data) < 128
    return bytes([(number << 3) | 2, len(data)]) + data


MANIFEST = field_string(1, 'com.android.vndk.v30') + b'\x10\x01'


class ApexTests(unittest.TestCase):
    def test_reads_only_expected_manifest_fields(self):
        blob = MANIFEST + field_string(14, '30') + b'\x30\x01' + b'\xa0\x06\x03'
        parsed = audit.parse_apex_manifest(blob)
        self.assertEqual(parsed['name'], 'com.android.vndk.v30')
        self.assertEqual(parsed['version'], 1)
        self.assertEqual(parsed['vndk_version_field'], '30')
        self.assertTrue(parsed['no_code'])
        for bad in (b'', b'\x0a\x05abc', MANIFEST + field_string(1, 'duplicate'),
                    b'\x0a\xff\xff\xff\xff\xff\xff\xff\xff\xff\x02', b'\x00'):
            with self.subTest(bad=bad), self.assertRaises(audit.VndkApexError):
                audit.parse_apex_manifest(bad)

    def test_small_zip_member_rejects_duplicates_and_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'fake.apex'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('apex_manifest.pb', MANIFEST)
                z.writestr('apex_pubkey', b'key')
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(audit.small_member(z, 'apex_manifest.pb'), MANIFEST)
                with self.assertRaises(audit.VndkApexError):
                    audit.small_member(z, 'missing')
            with zipfile.ZipFile(archive, 'a') as z:
                with self.assertWarns(UserWarning):
                    z.writestr('apex_manifest.pb', b'other')
            with zipfile.ZipFile(archive) as z, self.assertRaises(audit.VndkApexError):
                audit.small_member(z, 'apex_manifest.pb')

    def test_avb_key_comparison_is_not_signature_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / 'fake.img'
            key = b'public-key'
            auth = b'A' * 64
            aux = b'prefix' + key + b'suffix'
            hdr = struct.pack(audit.HEADER_FORMAT, b'AVB0', 1, 0, len(auth), len(aux), 1,
                              0, 32, 32, 32, 6, len(key), 0, 0, 0, 0, 0, 0, 0, b'test')
            offset = 4096
            size = len(hdr) + len(auth) + len(aux)
            footer = struct.pack('>4sIIQQQ28s', b'AVBf', 1, 0, offset, offset, size, b'')
            image.write_bytes(b'0' * offset + hdr + auth + aux + footer)
            result = audit.avb_header_observation(image, key)
            self.assertTrue(result['public_key_matches_bundled_apex_pubkey'])
            self.assertFalse(result['signature_or_hashtree_verified'])
            self.assertEqual(result['signer_trusted'], 'not_assessed')
            self.assertFalse(audit.avb_header_observation(image, b'other')['public_key_matches_bundled_apex_pubkey'])
            image.write_bytes(b'invalid')
            self.assertEqual(audit.avb_header_observation(image, key)['status'], 'missing_or_invalid_footer')

    def test_vendor_name_matching_is_explicitly_limited(self):
        collector = abi.Collector()
        collector.references[(64, 'libone.so')] = 3
        collector.references[(32, 'libtwo.so')] = 2
        result = audit.summarize_vendor_references(collector, {(64, 'libone.so')}, True)
        self.assertEqual(result['candidate_vndk30_name_and_basic_elf_header_matches'], 1)
        self.assertEqual(result['dependency_edges_referencing_those_names'], 3)
        result = audit.summarize_vendor_references(collector, set(), False)
        self.assertNotIn('candidate_vndk30_name_and_basic_elf_header_matches', result)


def fake_elf(bits):
    head = bytearray(64)
    head[:7] = b'\x7fELF' + bytes([1 if bits == 32 else 2, 1, 1])
    struct.pack_into('<H', head, 16, 3)
    struct.pack_into('<H', head, 18, 40 if bits == 32 else 183)
    return bytes(head)


@unittest.skipUnless(audit.inventory.pytsk3 and Path('/usr/sbin/mke2fs').exists(), 'Synthetic ext4 tools are required')
class ApexExt4Tests(unittest.TestCase):
    def test_real_nested_ext4_and_zip_are_read_only(self):
        with tempfile.TemporaryDirectory(prefix='vndk-apex-fixture-') as temp:
            root = Path(temp)
            inner = root / 'inner'
            (inner / 'lib').mkdir(parents=True)
            (inner / 'lib64').mkdir()
            (inner / 'apex_manifest.pb').write_bytes(MANIFEST)
            (inner / 'lib/libx.so').write_bytes(fake_elf(32))
            (inner / 'lib64/libx.so').write_bytes(fake_elf(64))
            image = root / 'payload.img'
            with image.open('wb') as f:
                f.truncate(16 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(inner), str(image)],
                           check=True, capture_output=True)
            sys_ext = root / 'system-ext'
            (sys_ext / 'apex').mkdir(parents=True)
            package = sys_ext / 'apex/com.android.vndk.v30.apex'
            with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('apex_manifest.pb', MANIFEST)
                z.writestr('apex_pubkey', b'fake-public-key')
                z.write(image, 'apex_payload.img')
            extent = root / 'extent.img'
            with extent.open('wb') as f:
                f.truncate(16 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(sys_ext), str(extent)],
                           check=True, capture_output=True)
            before = hashlib.sha256(extent.read_bytes()).hexdigest()
            with mock.patch.object(audit, 'EXPECTED_BYTES', package.stat().st_size), \
                    mock.patch.object(audit, 'EXPECTED_SHA256', hashlib.sha256(package.read_bytes()).hexdigest()):
                report, providers = audit.inspect_system_ext(extent)
            self.assertEqual(report['outer_manifest']['name'], 'com.android.vndk.v30')
            self.assertEqual(report['payload']['filesystem'], 'ext4')
            self.assertTrue(report['payload']['inner_and_outer_manifest_bytes_identical'])
            self.assertEqual(providers, {(32, 'libx.so'), (64, 'libx.so')})
            self.assertEqual(before, hashlib.sha256(extent.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
