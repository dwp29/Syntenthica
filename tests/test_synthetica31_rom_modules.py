"""Host-only 3.1 ROM-module audit tests. Never accesses a phone or flashes."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_synthetica31_rom_modules as audit
import audit_synthetica3_vendor as vendor


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


class SyntheticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'evidence.zip'
        self.modules = self.root / 'modules'
        self.modules.mkdir()
        self.cert = b'public-certificate-for-host-test-only'
        self.release = '4.14.357-openela-synthetica-3.1'
        self.config = b'CONFIG_MODVERSIONS=y\nCONFIG_MODULE_SIG_FORCE=y\n'
        self.files = {
            'Image.gz.DO-NOT-FLASH': gzip.compress(b'Linux version ' + self.release.encode() + b' test\0' + self.cert),
            'generated.config.txt': self.config,
            'module-signing-public-cert.x509': self.cert,
            'Module.symvers': b'0x00000001 module_layout vmlinux EXPORT_SYMBOL\n',
            'System.map': b'00000000 T module_layout\n',
        }
        self.pins = {
            'release': self.release, 'source': 'fixture-only', 'baseline_3_0_config_sha256': 'a' * 64,
            'module_layout_crc': '0x00000001',
        }
        self.status = {
            'kind': 'SYNTHETICA_3_1_REBUILT_KERNEL_NOT_DEVICE_VALIDATED',
            'release': self.release, 'base_source': self.pins['source'],
            'baseline_3_0_config_sha256': self.pins['baseline_3_0_config_sha256'],
            'installer_created': False, 'private_key_exported': False,
            'module_layout_crc': '0x00000001', 'mglru': {'variant': 'on'},
        }
        self.sync_hashes()

    def sync_hashes(self):
        for key, name in audit.FIELDS.items():
            self.status[key] = digest(self.files[name])
            if key in ('image_sha256', 'config_sha256', 'module_public_cert_sha256'):
                self.pins[key] = self.status[key]

    def write_archive(self, extras: tuple[tuple[str, bytes], ...] = ()):
        self.files['STATUS.json'] = json.dumps(self.status).encode()
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(buffer, 'w') as z:
                for name, data in self.files.items():
                    z.writestr(name, data)
                for name, data in extras:
                    z.writestr(name, data)
        data = buffer.getvalue()
        self.archive.write_bytes(data)
        self.pins['transfer_sha256'] = digest(data)
        self.pins['transfer_git_blob'] = blob_id(data)

    def load(self):
        with mock.patch.object(audit.build, 'verify_embedded_config') as embedded:
            target = audit.load_candidate(self.archive, self.pins)
            embedded.assert_called_once()
            return target

    def test_valid_archive_checks_image_and_build_evidence(self):
        self.write_archive()
        target = self.load()
        self.assertEqual(target['release'], self.release)
        self.assertEqual(target['symvers']['module_layout'], 1)
        self.assertEqual(target['cert'], self.cert)
        self.assertEqual(target['module_srcversions'], {})
        self.assertEqual(target['export_providers']['module_layout'][0]['kind'], 'vmlinux')

    def test_archive_tampering_and_extra_or_duplicate_members_refused(self):
        self.write_archive()
        self.archive.write_bytes(self.archive.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            self.load()
        self.write_archive(extras=(('../escape', b'bad'),))
        with self.assertRaisesRegex(ValueError, 'unexpected or duplicate'):
            self.load()
        self.write_archive(extras=(('System.map', b'duplicate'),))
        with self.assertRaisesRegex(ValueError, 'unexpected or duplicate'):
            self.load()

    def test_evidence_file_hash_status_config_and_crc_are_checked(self):
        self.write_archive()
        self.files['System.map'] += b'1 T unexpected\n'
        self.write_archive()  # archive pin changed, but STATUS still binds old System.map
        with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
            self.load()
        self.files['System.map'] = b'00000000 T module_layout\n'
        self.status['private_key_exported'] = True
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'compile status'):
            self.load()
        self.status['private_key_exported'] = False
        self.files['generated.config.txt'] = b'CONFIG_MODVERSIONS=y\n# CONFIG_MODULE_SIG_FORCE is not set\n'
        self.sync_hashes()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'module-verification config'):
            self.load()
        self.files['generated.config.txt'] = self.config
        self.sync_hashes()
        self.pins['module_layout_crc'] = self.status['module_layout_crc'] = '0x00000002'
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'module_layout CRC'):
            self.load()

    def test_wrong_certificate_and_oversized_or_symlink_archive_refused(self):
        self.files['Image.gz.DO-NOT-FLASH'] = gzip.compress(b'Linux version ' + self.release.encode() + b' test\0')
        self.sync_hashes()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'embedded module certificate'):
            self.load()
        link = self.root / 'evidence-link.zip'
        link.symlink_to(self.archive)
        with self.assertRaises(OSError):
            audit.read_evidence(link, self.pins)
        huge = self.root / 'huge.zip'
        with huge.open('wb') as f:
            f.truncate(audit.MAX_ARCHIVE + 1)
        with self.assertRaisesRegex(ValueError, 'bounded regular'):
            audit.read_evidence(huge, self.pins)

    def test_unparseable_module_and_private_report_are_not_compatibility_claims(self):
        self.write_archive()
        target = self.load()
        (self.modules / 'broken.ko').write_bytes(b'not an ELF module')
        report = audit.audit_modules(self.modules, target)
        self.assertEqual(report['summary']['module_files_unparsed'], 1)
        self.assertEqual(report['summary']['module_layout_matches'], 0)
        self.assertFalse(report['candidate_installer_contains_modules'])
        self.assertIn('not an exhaustive runtime keyring', report['scope'])
        self.assertIn('not a complete loadability or boot verdict', report['evidence_note'])
        path = self.root / 'private-report.json'
        vendor.write_private(path, report, [self.modules, self.archive])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            vendor.write_private(path, report, [self.modules, self.archive])
        with self.assertRaisesRegex(ValueError, 'outside'):
            vendor.write_private(self.modules / 'report.json', report, [self.modules, self.archive])

    def test_existing_old_build_fixture_can_verify_with_its_own_certificate(self):
        # Positive signature path only: this is a checked-in 3.0 fixture and
        # its own synthetic target, NOT a 3.1 ROM compatibility claim.
        bundle = ROOT / 'artifacts/synthetica-3.0'
        module = self.modules / 'tcp_bic.ko'
        shutil.copyfile(bundle / 'signed-modules/tcp_bic.ko', module)
        before = digest(module.read_bytes())
        target = vendor.load_bundle(bundle)
        target.update(mode='on', certificate_sha256=digest(target['cert']))
        report = audit.audit_modules(self.modules, target)
        self.assertEqual(report['summary']['module_files_parsed'], 1)
        self.assertEqual(report['summary']['verified_with_exported_build_certificate'], 1)
        self.assertEqual(report['summary']['module_layout_matches'], 1)
        self.assertEqual(digest(module.read_bytes()), before)


@unittest.skipUnless(os.environ.get('S31_EVIDENCE'), 'pinned public 3.1 CI evidence ZIP not provided')
class RealEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence = Path(os.environ['S31_EVIDENCE'])
        self.modules = self.root / 'modules'
        self.modules.mkdir()

    def test_real_build_against_unrelated_older_fixture_is_not_a_rom_result(self):
        target = audit.load_candidate(self.evidence)
        self.assertEqual(target['release'], '4.14.357-openela-synthetica-3.1')
        self.assertEqual(target['symvers']['module_layout'], 0xed5659d1)
        self.assertEqual(target['certificate_sha256'], audit.evidence_pins()['module_public_cert_sha256'])
        path = self.modules / 'tcp_bic.ko'
        shutil.copyfile(ROOT / 'artifacts/synthetica-3.0/signed-modules/tcp_bic.ko', path)
        before = digest(path.read_bytes())
        report = audit.audit_modules(self.modules, target)
        self.assertEqual(report['summary']['module_files_parsed'], 1)
        self.assertEqual(report['summary']['module_layout_matches'], 0)
        self.assertEqual(report['summary']['vermagic_matches'], 0)
        self.assertEqual(report['summary']['verified_with_exported_build_certificate'], 0)
        self.assertIn('No device', report['scope'])
        self.assertEqual(before, digest(path.read_bytes()))

    @unittest.skipUnless(os.environ.get('S30_EVIDENCE'), 'pinned public 3.0 CI evidence ZIP not provided')
    def test_pinned_30_and_31_symbol_evidence_is_identical_but_certificates_differ(self):
        # Compare only the exact public build outputs. This is not a ROM audit
        # or a device test, and matching symbol files are not a boot verdict.
        raw30 = vendor.read_regular(Path(os.environ['S30_EVIDENCE']), audit.MAX_ARCHIVE)
        self.assertEqual(digest(raw30), '77f7a76159c5f450704adc75d9dc7daa02a7c6e18f33edf4216025314e38e5c9')
        self.assertEqual(blob_id(raw30), '8541d4a26081b94215d4d493332cc27711f2fd15')
        with zipfile.ZipFile(io.BytesIO(raw30)) as z:
            self.assertEqual(set(z.namelist()), {
                'synthetica-3.0.zip', 'STATUS.json', 'generated.config.txt',
                'module-signing-public-cert.x509', 'Module.symvers', 'System.map',
            })
            self.assertEqual(len(z.infolist()), 6)
            self.assertIsNone(z.testzip())
            files30 = {name: z.read(name) for name in z.namelist()}
        status30 = json.loads(files30['STATUS.json'])
        self.assertEqual(status30['kind'], 'SYNTHETICA_3_0_COMPILED_ONLY_DO_NOT_FLASH')
        self.assertEqual(status30['release'], '4.14.357-openela-synthetica-3.0')
        self.assertEqual(status30['base_source'], audit.evidence_pins()['source'])
        for key, name in (
            ('config_sha256', 'generated.config.txt'),
            ('module_public_cert_sha256', 'module-signing-public-cert.x509'),
            ('module_symvers_sha256', 'Module.symvers'),
            ('system_map_sha256', 'System.map'),
        ):
            self.assertEqual(digest(files30[name]), status30[key])
        with zipfile.ZipFile(io.BytesIO(files30['synthetica-3.0.zip'])) as z:
            image30 = z.read('Image.gz')
        self.assertEqual(digest(image30), status30['image_sha256'])

        # load_candidate also verifies the pinned 3.1 archive, image, embedded
        # config and build certificate. The 3.0 identity is cross-bound in 3.1.
        audit.load_candidate(self.evidence)
        files31 = audit.read_evidence(self.evidence, audit.evidence_pins())
        status31 = json.loads(files31['STATUS.json'])
        self.assertEqual(status31['baseline_3_0_image_sha256'], digest(image30))
        self.assertEqual(status31['baseline_3_0_config_sha256'], digest(files30['generated.config.txt']))
        self.assertEqual(status31['baseline_3_0_module_cert_sha256'], digest(files30['module-signing-public-cert.x509']))
        self.assertNotEqual(digest(image30), digest(files31['Image.gz.DO-NOT-FLASH']))
        self.assertNotEqual(files30['module-signing-public-cert.x509'], files31['module-signing-public-cert.x509'])
        for name in ('Module.symvers', 'System.map'):
            self.assertEqual(files30[name], files31[name])
        self.assertEqual(len(files30['Module.symvers'].splitlines()), 12236)
        self.assertEqual(files30['generated.config.txt'].count(b'CONFIG_LOCALVERSION="-synthetica-3.0"'), 1)
        self.assertEqual(files30['generated.config.txt'].replace(
            b'CONFIG_LOCALVERSION="-synthetica-3.0"', b'CONFIG_LOCALVERSION="-synthetica-3.1"', 1
        ), files31['generated.config.txt'])
        for key in ('clang_sha256', 'lld_sha256', 'neutron_archive_sha256'):
            self.assertEqual(status30['compiler'][key], status31['compiler'][key])

    def test_cli_writes_private_report_and_refuses_overwrite(self):
        shutil.copyfile(ROOT / 'artifacts/synthetica-3.0/signed-modules/tcp_bic.ko', self.modules / 'tcp_bic.ko')
        result = self.root / 'report.json'
        cmd = [sys.executable, str(ROOT / 'build-kit/scripts/audit_synthetica31_rom_modules.py'),
               '--modules', str(self.modules), '--evidence', str(self.evidence), '--report', str(result)]
        first = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(result.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(first.stdout)['summary']['module_files_parsed'], 1)
        self.assertEqual(list(self.root.glob('.synthetica31-module-audit-*')), [])
        second = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('already exists', second.stderr)


if __name__ == '__main__':
    unittest.main()
