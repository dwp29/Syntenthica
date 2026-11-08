"""Read-only tests for the 3.2 ROM-module audit; no device/ROM is accessed."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import warnings
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build-kit/scripts'))
import audit_synthetica32_rom_modules as audit
import audit_synthetica3_vendor as vendor


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob_id(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root/'evidence.zip'
        self.moddir = self.root/'modules'
        self.moddir.mkdir()
        self.cert = b'public-certificate-for-host-test-only'
        self.config = (ROOT/'artifacts/generated.config.txt').read_bytes().replace(
            b'CONFIG_LOCALVERSION="-Synthetica-2.0"', b'CONFIG_LOCALVERSION="-synthetica-3.2"')
        mgr = json.loads((ROOT/'build-kit/artifacts/manager/MANAGER.json').read_text())
        raw = (b'Linux version ' + audit.build.RELEASE.encode() + b' synthetic\nKernelSU\0' +
               mgr['package'].encode() + b'\0' + mgr['cert_sha256'].encode() + b'\0' + self.cert +
               b'\0IKCFG_ST' + gzip.compress(self.config) + b'IKCFG_ED')
        self.files = {
            audit.build.IMAGE_NAME: gzip.compress(raw),
            'generated.config.txt': self.config,
            'kernel-module-public-cert.x509': self.cert,
            'Module.symvers.txt': (ROOT/'artifacts/synthetica-3.0/Module.symvers.txt').read_bytes(),
            'System.map.txt': b'00000000 T module_layout\n',
            'README-DO-NOT-FLASH.txt': b'synthetic only',
            'SHA256SUMS.txt': b'synthetic manifest',
            'PROVENANCE.json': json.dumps({'commit': 'a'*40, 'run_id': '123'}).encode(),
            **{f'signed-modules/{name}.ko': b'synthetic '+name.encode() for name in audit.modules.MODULE_CONFIG},
        }
        self.pins = {'release': audit.build.RELEASE, 'module_layout_crc': '0x08efcbb0',
                     'build_run': 123, 'commit': 'a'*40}
        self.status = {
            'status': 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED',
            'uname_release': audit.build.RELEASE, 'source': audit.build.base.SOURCE,
            'reference_2_0_generated_config_sha256': audit.build.base.V2_CONFIG_SHA256,
            'installer_or_boot_image_created': False, 'private_signing_key_exported': False,
            'no_experimental_3_1_mglru_or_uclamp_patches': True, 'module_layout_crc': '0x08efcbb0',
            'output_sha256': {},
        }
        self.sync_hashes()

    def sync_hashes(self):
        for field, name in audit.FIELDS.items():
            self.pins[field] = self.status['output_sha256'][name] = digest(self.files[name])
        for name in audit.modules.MODULE_CONFIG:
            member = f'signed-modules/{name}.ko'
            self.status['output_sha256'][member] = digest(self.files[member])

    def write_archive(self, extras=(), manifest=True):
        self.files['STATUS.json'] = json.dumps(self.status).encode()
        if manifest:
            self.files['SHA256SUMS.txt'] = ''.join(
                f'{digest(data)}  {name}\n' for name, data in sorted(self.files.items())
                if name != 'SHA256SUMS.txt').encode()
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name, data in self.files.items():
                    z.writestr(name, data)
                for name, data in extras:
                    z.writestr(name, data)
        data = buffer.getvalue()
        self.archive.write_bytes(data)
        self.pins['transfer_sha256'] = digest(data)
        self.pins['transfer_git_blob'] = blob_id(data)

    def load(self):
        # Actual ELF/PKCS7 verification uses the already tested shared verifier;
        # the synthetic .ko fixture is deliberately not claimed to be signed.
        with mock.patch.object(audit.modules, 'verify_module') as verifier:
            target = audit.load_candidate(self.archive, self.pins)
            self.assertEqual(verifier.call_count, 6)
            return target

    def test_evidence_checks_identity_full_abi_and_same_build_modules(self):
        self.write_archive()
        target = self.load()
        self.assertEqual(target['release'], audit.build.RELEASE)
        self.assertEqual(target['symvers']['module_layout'], 0x08efcbb0)
        self.assertEqual(len(target['symvers']), 12236)
        self.assertEqual(target['cert'], self.cert)
        self.assertEqual(target['module_srcversions'], {})
        self.assertEqual(target['export_providers']['module_layout'][0]['kind'], 'vmlinux')

    def test_archive_hash_entries_and_safe_regular_file(self):
        self.write_archive()
        self.archive.write_bytes(self.archive.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            self.load()
        self.write_archive(extras=(('../escape', b'bad'),))
        with self.assertRaisesRegex(ValueError, 'unexpected or duplicate'):
            self.load()
        self.write_archive(extras=(('System.map.txt', b'duplicate'),))
        with self.assertRaisesRegex(ValueError, 'unexpected or duplicate'):
            self.load()
        link = self.root/'link.zip'
        link.symlink_to(self.archive)
        with self.assertRaises(OSError):
            audit.read_evidence(link, self.pins)

    def test_manifest_covers_every_file_and_rejects_bad_hashes(self):
        self.write_archive()
        self.files['System.map.txt'] += b'0 T changed\n'
        self.write_archive(manifest=False)
        with self.assertRaisesRegex(ValueError, 'manifest digest mismatch'):
            self.load()
        self.write_archive()
        self.files['SHA256SUMS.txt'] += self.files['SHA256SUMS.txt'].splitlines()[0] + b'\n'
        self.write_archive(manifest=False)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.load()

    def test_every_output_hash_and_provenance_are_bound(self):
        self.write_archive()
        self.files['System.map.txt'] += b'0 T changed\n'
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
            self.load()
        self.sync_hashes()
        self.status['private_signing_key_exported'] = True
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'compile status'):
            self.load()
        self.status['private_signing_key_exported'] = False
        self.files['PROVENANCE.json'] = b'{"commit":"wrong","run_id":"123"}'
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.load()

    def test_all_export_crcs_checked_even_if_module_layout_is_unchanged(self):
        source = self.files['Module.symvers.txt']
        self.files['Module.symvers.txt'] = source.replace(b'0x1ec57692', b'0xffffffff', 1)
        self.assertNotEqual(self.files['Module.symvers.txt'], source)
        self.assertIn(b'0x08efcbb0\tmodule_layout', self.files['Module.symvers.txt'])
        self.sync_hashes()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'export ABI differs'):
            self.load()

    def test_bad_config_embedded_cert_and_module_hash_are_rejected(self):
        good = self.files['generated.config.txt']
        self.files['generated.config.txt'] = good.replace(b'CONFIG_MODULE_SIG_FORCE=y',
                                                           b'# CONFIG_MODULE_SIG_FORCE is not set')
        self.sync_hashes()
        self.write_archive()
        with self.assertRaises(ValueError):
            self.load()
        self.files['generated.config.txt'] = good
        self.files['kernel-module-public-cert.x509'] = b'other-cert'
        self.sync_hashes()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'embedded module certificate'):
            self.load()
        self.files['kernel-module-public-cert.x509'] = self.cert
        self.sync_hashes()
        self.files['signed-modules/tcp_bic.ko'] += b'tamper'
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'module hash'):
            self.load()

    def test_rom_input_not_modified_and_matching_crc_is_not_trust(self):
        self.write_archive()
        target = self.load()
        path = self.moddir/'tcp_bic.ko'
        shutil.copyfile(ROOT/'artifacts/synthetica-3.0/signed-modules/tcp_bic.ko', path)
        before = digest(path.read_bytes())
        report = audit.audit_modules(self.moddir, target)
        self.assertEqual(report['summary']['module_files_parsed'], 1)
        self.assertEqual(report['summary']['module_layout_matches'], 1)
        self.assertEqual(report['summary']['vermagic_matches'], 0)
        self.assertEqual(report['summary']['verified_with_exported_build_certificate'], 0)
        self.assertIn('not an exhaustive runtime keyring', report['scope'])
        self.assertIn('not a complete loadability or boot verdict', report['evidence_note'])
        self.assertEqual(digest(path.read_bytes()), before)
        out = self.root/'private-report.json'
        vendor.write_private(out, report, [self.moddir, self.archive])
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            vendor.write_private(out, report, [self.moddir, self.archive])
        with self.assertRaisesRegex(ValueError, 'outside'):
            vendor.write_private(self.moddir/'report.json', report, [self.moddir, self.archive])


@unittest.skipUnless(__import__('os').environ.get('S32_EVIDENCE'), 'real 3.2 CI evidence ZIP not provided')
class RealEvidenceTests(unittest.TestCase):
    def test_real_build_modules_verify_and_old_module_is_not_rom_proof(self):
        import os
        archive = Path(os.environ['S32_EVIDENCE'])
        target = audit.load_candidate(archive)
        self.assertEqual(target['release'], audit.build.RELEASE)
        self.assertEqual(target['symvers']['module_layout'], 0x08efcbb0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'tcp_bic.ko'
            shutil.copyfile(ROOT/'artifacts/synthetica-3.0/signed-modules/tcp_bic.ko', path)
            before = digest(path.read_bytes())
            report = audit.audit_modules(Path(d), target)
            self.assertEqual(report['summary']['module_files_parsed'], 1)
            self.assertEqual(report['summary']['module_layout_matches'], 1)
            self.assertEqual(report['summary']['vermagic_matches'], 0)
            self.assertEqual(report['summary']['verified_with_exported_build_certificate'], 0)
            self.assertEqual(digest(path.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
