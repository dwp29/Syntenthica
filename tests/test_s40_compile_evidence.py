"""Offline-only tests for non-flashable 6.18 compile evidence."""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import verify_s40_compile_evidence as evidence


class EvidencePrimitiveTests(unittest.TestCase):
    def test_archive_hash_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / 'evidence.zip'
            archive.write_bytes(b'not the pinned ZIP')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                evidence.read_archive(archive, '0' * 64)
            link = base / 'link.zip'
            link.symlink_to(archive)
            with self.assertRaisesRegex(ValueError, 'symlinked'):
                evidence.read_archive(link, hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_duplicate_zip_entries_fail_before_manifest_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'duplicate.zip'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('EVIDENCE.json', '{}')
                    z.writestr('EVIDENCE.json', '{}')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'Duplicate ZIP'):
                evidence.read_archive(archive, digest)

    def test_manifest_requires_exact_coverage_and_correct_hash(self):
        files = {'one': b'first', 'two': b'second'}
        sums = ''.join(f'{evidence.sha(data)}  {name}\n' for name, data in files.items()).encode()
        files['SHA256SUMS.txt'] = sums
        evidence.check_manifest(files)
        files['one'] = b'changed'
        with self.assertRaisesRegex(ValueError, 'SHA256SUMS mismatch'):
            evidence.check_manifest(files)
        files['one'] = b'first'
        files['SHA256SUMS.txt'] = sums + sums.splitlines(keepends=True)[0]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            evidence.check_manifest(files)

    def test_static_cli_requires_arm64_and_no_interpreter(self):
        elf = bytearray(120)
        elf[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', elf, 16, 2, 183)
        struct.pack_into('<Q', elf, 32, 64)
        struct.pack_into('<HH', elf, 54, 56, 1)
        struct.pack_into('<I', elf, 64, 1)
        evidence.check_nm(elf)
        struct.pack_into('<I', elf, 64, 3)
        with self.assertRaisesRegex(ValueError, 'dynamic segment/interpreter'):
            evidence.check_nm(elf)
        struct.pack_into('<I', elf, 64, 1)
        struct.pack_into('<H', elf, 18, 62)
        with self.assertRaisesRegex(ValueError, 'arm64'):
            evidence.check_nm(elf)

    def test_dtb_bounds_and_board_panel_identifiers(self):
        strings = b'xiaomi,joyeuse\0qcom,sm7125\0huaxing\0'
        total = 40 + len(strings)
        header = struct.pack('>10I', 0xD00DFEED, total, 40, 40, 40, 17, 16, 0, len(strings), 0)
        dtb = header + strings
        evidence.check_dtb(dtb, 'joyeuse', 'huaxing')
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            evidence.check_dtb(dtb, 'curtana', 'huaxing')
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            evidence.check_dtb(dtb[:-1], 'joyeuse', 'huaxing')


class RealEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = os.environ.get('S40_EVIDENCE_ZIP')
        if not archive:
            raise unittest.SkipTest('set S40_EVIDENCE_ZIP to the pinned compile-only ZIP')
        cls.archive = Path(archive)
        if not cls.archive.is_file():
            raise AssertionError('S40_EVIDENCE_ZIP is not a file')

    def repack_with_changes(self, changes: dict[str, bytes], path: Path) -> dict:
        with zipfile.ZipFile(self.archive) as z:
            files = {name: z.read(name) for name in z.namelist()}
        files.update(changes)
        files['SHA256SUMS.txt'] = ''.join(
            f'{evidence.sha(data)}  {name}\n' for name, data in sorted(files.items())
            if name != 'SHA256SUMS.txt').encode()
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            for name, data in files.items():
                z.writestr(name, data)
        pin = copy.deepcopy(evidence.PINS)
        pin['archive_sha256'] = evidence.sha(path.read_bytes())
        return pin

    def test_real_pinned_zip_and_three_sample_signatures(self):
        result = evidence.verify(self.archive)
        self.assertEqual(result['workflow_run'], 42545930921)
        self.assertEqual(result['exported_symbol_records'], 15001)
        self.assertEqual(result['module_layout_crc'], '0xdd02b758')
        self.assertEqual(len(result['sample_modules_pkcs7_and_crc_verified']), 3)
        self.assertTrue(all(x['signature_verified_with_embedded_certificate']
                            for x in result['sample_modules_pkcs7_and_crc_verified']))
        self.assertFalse(result['ci_other_modules_cryptographically_verified_by_this_audit'])
        self.assertFalse(result['physical_boot_tested'])
        self.assertFalse(result['flashable'])

    def test_changed_module_fails_signature_even_with_rewritten_hashes(self):
        name = 'sample-signed-modules/tcp_bic.ko.DO-NOT-LOAD'
        with zipfile.ZipFile(self.archive) as z:
            original = z.read(name)
        changed = original.replace(b'license=GPL', b'license=XPL', 1)
        self.assertNotEqual(changed, original)
        with tempfile.TemporaryDirectory() as temp:
            modified = Path(temp) / 'tampered.zip'
            pin = self.repack_with_changes({name: changed}, modified)
            pin['sample_modules']['tcp_bic'] = evidence.sha(changed)
            with self.assertRaisesRegex(ValueError, 'module signature'):
                evidence.verify(modified, pin)

    def test_missing_tracepoint_rejected_even_with_rewritten_hashes(self):
        name = 'generated.config.txt'
        with zipfile.ZipFile(self.archive) as z:
            original = z.read(name)
        changed = original.replace(b'CONFIG_TRACEPOINTS=y', b'# CONFIG_TRACEPOINTS is not set', 1)
        self.assertNotEqual(changed, original)
        with tempfile.TemporaryDirectory() as temp:
            modified = Path(temp) / 'bad-config.zip'
            pin = self.repack_with_changes({name: changed}, modified)
            pin['config_sha256'] = evidence.sha(changed)
            with self.assertRaisesRegex(ValueError, 'CONFIG_TRACEPOINTS'):
                evidence.verify(modified, pin)


if __name__ == '__main__':
    unittest.main()
