"""Offline 3.0 module comparison; inputs are checked-in synthetic/old-build fixtures."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_synthetica3_compat_modules as audit
import audit_synthetica3_vendor as vendor


class CandidateModuleAuditTests(unittest.TestCase):
    def setUp(self):
        original = os.environ.get('S3_COMPAT_ORIGINAL')
        evidence = os.environ.get('S3_ROOT_EVIDENCE')
        if not original or not evidence:
            self.skipTest('S3_COMPAT_ORIGINAL and S3_ROOT_EVIDENCE required')
        self.original, self.evidence = Path(original), Path(evidence)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'modules'
        self.input.mkdir()

    def test_pinned_build_and_other_build_module_do_not_prove_rom_compatibility(self):
        target = audit.load_candidate(self.original, self.evidence)
        self.assertEqual(target['image_sha256'], audit.pkg.IMAGE_SHA256)
        self.assertEqual(target['symvers']['module_layout'], 0xed5659d1)
        self.assertTrue(target['release'].endswith('-synthetica-3.0'))
        source = ROOT / 'artifacts/synthetica-3.0/signed-modules/tcp_bic.ko'
        module = self.input / source.name
        shutil.copy2(source, module)
        before = hashlib.sha256(module.read_bytes()).hexdigest()
        result = audit.audit_modules(self.input, target)
        summary = result['summary']
        self.assertEqual((summary['module_files_found'], summary['module_files_parsed'],
                          summary['module_files_unparsed']), (1, 1, 0))
        self.assertEqual((summary['module_layout_matches'], summary['vermagic_matches'],
                          summary['verified_with_exported_build_certificate']), (0, 0, 0))
        self.assertFalse(result['candidate_installer_contains_modules'])
        self.assertIn('not an exhaustive runtime keyring', result['scope'])
        self.assertEqual(hashlib.sha256(module.read_bytes()).hexdigest(), before)
        report = self.root / 'private-report.json'
        vendor.write_private(report, result, [self.input, self.evidence])
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            vendor.write_private(report, result, [self.input, self.evidence])
        with self.assertRaisesRegex(ValueError, 'outside'):
            vendor.write_private(self.input / 'report.json', result, [self.input, self.evidence])

    def test_tampered_evidence_and_symlink_are_rejected(self):
        dest = self.root / 'evidence'
        shutil.copytree(self.evidence, dest)
        p = dest / 'Module.symvers'
        p.write_bytes(p.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
            audit.load_candidate(self.original, dest)
        p.write_bytes((self.evidence / 'Module.symvers').read_bytes())
        p = dest / 'STATUS.json'
        p.write_bytes(p.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'build status'):
            audit.load_candidate(self.original, dest)
        alias = self.root / 'evidence-link'
        alias.symlink_to(self.evidence, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            audit.load_candidate(self.original, alias)

    def test_bad_module_is_reported_as_unparsed_not_as_compatible(self):
        target = audit.load_candidate(self.original, self.evidence)
        (self.input / 'broken.ko').write_bytes(b'not a module')
        report = audit.audit_modules(self.input, target)
        self.assertEqual(report['summary']['module_files_unparsed'], 1)
        self.assertEqual(report['summary']['module_layout_matches'], 0)
        self.assertEqual(report['summary']['verified_with_exported_build_certificate'], 0)


if __name__ == '__main__':
    unittest.main()
