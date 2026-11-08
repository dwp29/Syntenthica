"""Offline 3.2-r1 evidence verification; never connects to a device."""
from __future__ import annotations

import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import verify_synthetica32_r1_evidence as verify


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'evidence.zip'
        self.cert = b'test certificate'
        self.manager = {'package': 'test.manager', 'cert_sha256': 'a'*64}
        self.raw = (b'Linux version '+verify.build.RELEASE.encode()+b' test\nKernelSU '+self.cert+b' '
                    +self.manager['package'].encode()+b' '+self.manager['cert_sha256'].encode())
        self.changes = {'LOCALVERSION': {'3.1': 'old', '3.2-r1': 'new'}}
        self.exports = {'exported_records_compared': 12236}
        self.files = {
            verify.IMAGE: gzip.compress(self.raw),
            verify.CERT: self.cert,
            'generated.config.txt': b'CONFIG_PLACEHOLDER=y\n',
            'Module.symvers': b'0xed5659d1\tmodule_layout\tvmlinux\tEXPORT_SYMBOL\n',
            'System.map': b'00000000 T placeholder\n',
            'manager-apk_sign.o': (b'fake object '+self.manager['package'].encode()+b'\0'
                                   +self.manager['cert_sha256'].encode()+b'\0'),
            'README-DO-NOT-FLASH.txt': b'Not flashable',
            'PROVENANCE.json': json.dumps({'commit': 'f'*40, 'run_id': '123'}).encode(),
        }
        self.files.update({path: name.encode() for name, path in verify.MODULE_PATHS.items()})
        self.status = {
            'kind': verify.build.STATUS_KIND, 'release': verify.build.RELEASE,
            'base_source': verify.build.v3.SOURCE, 'installer_created': False,
            'private_key_exported': False, 'module_layout_crc': '0xed5659d1',
            'physical_boot_test_this_image': 'NOT RUN',
            'mglru_guard_patch_sha256': verify.build.PATCH_SHA256,
            'mglru_guard_source_before_sha256': verify.build.SOURCE_BEFORE,
            'mglru_guard_source_after_sha256': verify.build.SOURCE_AFTER,
            'changes_from_exact_3_1_config': self.changes,
            'export_abi_against_3_1': self.exports,
            'manager': {'apk_sign_object_sha256': verify.sha(self.files['manager-apk_sign.o'])},
            'same_build_modules_static_checks': {
                name: {'name': name, 'sha256': verify.sha(self.files[member])}
                for name, member in verify.MODULE_PATHS.items()},
        }
        self.pins = {'commit': 'f'*40, 'build_run': 123}
        self.sync_status_hashes()

    def sync_status_hashes(self):
        for field, member in verify.STATUS_HASHES.items():
            self.status[field] = self.pins[field] = verify.sha(self.files[member])

    def archive(self, *, manifest=True, duplicate=None):
        self.files['STATUS.json'] = json.dumps(self.status).encode()
        if manifest:
            self.files['SHA256SUMS.txt'] = ''.join(
                f'{verify.sha(content)}  {name}\n' for name, content in sorted(self.files.items())
                if name != 'SHA256SUMS.txt').encode()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, content in self.files.items():
                    archive.writestr(name, content)
                if duplicate:
                    archive.writestr(duplicate, self.files[duplicate])
        raw = self.path.read_bytes()
        self.pins['transfer_sha256'], self.pins['transfer_git_blob'] = verify.sha(raw), verify.blob_sha(raw)

    def run_verify(self):
        def module(data, *, name, **kwargs):
            return {'name': name, 'sha256': verify.sha(data)}
        with mock.patch.object(verify.build, 'compare_31_config', return_value=self.changes), \
             mock.patch.object(verify.build, 'compare_31_exports', return_value=self.exports), \
             mock.patch.object(verify.build.v3, 'verify_embedded_config') as embedded, \
             mock.patch.object(verify.build.base.rc.s2x, 'verify_manager', return_value=self.manager), \
             mock.patch.object(verify.modules, 'verify_module', side_effect=module):
            result = verify.verify_evidence(self.path, Path('unused-config'), Path('unused-symvers'), self.pins)
            embedded.assert_called_once()
            return result

    def test_valid_archive_and_scope(self):
        self.archive()
        before = self.path.read_bytes()
        report = self.run_verify()
        self.assertEqual(report['exports_compared'], 12236)
        self.assertEqual(report['same_build_modules_verified_statically'], 6)
        self.assertIn('NOT VERIFIED', report['physical_boot_and_rom_module_trust'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_pin_and_duplicate_members_rejected(self):
        self.archive()
        self.pins['transfer_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'does not match the pinned'):
            self.run_verify()
        self.archive(duplicate=verify.IMAGE)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.run_verify()

    def test_manifest_and_unsafe_status_rejected(self):
        self.archive()
        self.files['System.map'] += b'changed'
        self.archive(manifest=False)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.run_verify()
        self.sync_status_hashes()
        self.status['private_key_exported'] = True
        self.archive()
        with self.assertRaisesRegex(ValueError, 'compile status'):
            self.run_verify()

    def test_certificate_image_and_module_changes_rejected_even_with_updated_manifest(self):
        self.files[verify.CERT] = b'not-in-kernel'
        self.sync_status_hashes()
        self.archive()
        with self.assertRaisesRegex(ValueError, 'embedded signing certificate'):
            self.run_verify()
        self.files[verify.CERT] = self.cert
        self.files[verify.IMAGE] = gzip.compress(self.raw.replace(verify.build.RELEASE.encode(), b'wrong-release'))
        self.sync_status_hashes()
        self.archive()
        with self.assertRaisesRegex(ValueError, 'kernel release mismatch'):
            self.run_verify()
        self.files[verify.IMAGE] = gzip.compress(self.raw)
        self.files[verify.MODULE_PATHS['tcp_bic']] += b'tampered'
        self.sync_status_hashes()
        self.archive()
        with self.assertRaisesRegex(ValueError, 'module check differs'):
            self.run_verify()

    def test_config_and_export_comparison_must_match_build_status(self):
        self.status['changes_from_exact_3_1_config'] = {}
        self.archive()
        with self.assertRaisesRegex(ValueError, 'config comparison'):
            self.run_verify()
        self.status['changes_from_exact_3_1_config'] = self.changes
        self.status['export_abi_against_3_1'] = {}
        self.archive()
        with self.assertRaisesRegex(ValueError, 'export comparison'):
            self.run_verify()


@unittest.skipUnless(all(os.environ.get(k) for k in ('S32R1_EVIDENCE', 'S31_EXACT_CONFIG', 'S31_EXACT_SYMVERS')),
                     'exact real build evidence and 3.1 references not provided')
class RealEvidenceTests(unittest.TestCase):
    def test_real_image_exports_and_signed_modules(self):
        result = verify.verify_evidence(Path(os.environ['S32R1_EVIDENCE']), Path(os.environ['S31_EXACT_CONFIG']),
                                        Path(os.environ['S31_EXACT_SYMVERS']))
        self.assertEqual(result['exports_compared'], 12236)
        self.assertEqual(result['same_build_modules_verified_statically'], 6)
        self.assertEqual(result['physical_boot_and_rom_module_trust'], 'NOT VERIFIED')


if __name__ == '__main__':
    unittest.main()
