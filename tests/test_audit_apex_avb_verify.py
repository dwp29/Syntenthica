"""Safety/identity unit tests for the data-only APEX AVB host verifier."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_apex_avb_verify as avb


class AvbProbeUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='avb-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unpinned_source_never_runs(self):
        source = self.root / 'wrong.py'
        source.write_bytes(b'not the pinned public AOSP source')
        with mock.patch.object(avb.shutil, 'copyfile') as copier:
            with self.assertRaises(avb.AvbProbeError):
                avb.prepare(self.root, source)
            copier.assert_not_called()

    def test_symlink_and_oversized_inputs_are_refused(self):
        target = self.root / 'target'
        target.write_bytes(b'fixture')
        link = self.root / 'link'
        link.symlink_to(target)
        with mock.patch.object(avb.shutil, 'which', return_value='/usr/bin/unshare'):
            with self.assertRaises(avb.AvbProbeError):
                avb.verify_isolated(self.root, link)
            with mock.patch.object(avb, 'MAX_INPUT', 1), self.assertRaises(avb.AvbProbeError):
                avb.verify_isolated(self.root, target)

    def test_result_requires_isolation_and_never_claims_trust(self):
        (self.root / 'input-avb').mkdir()
        source = self.root / 'fixture.img'
        source.write_bytes(b'only a synthetic input')
        def output(result):
            return SimpleNamespace(returncode=0, communicate=lambda timeout: (json.dumps(result).encode(), b''))
        valid = {'payload_signature_and_hashtree_verified_with_embedded_key': True,
                 'verification_exit_code': 0, 'root_read_only': True, 'no_new_privs': True,
                 'capabilities_dropped': True, 'signer_identity_or_trust_verified': False}
        with mock.patch.object(avb.shutil, 'which', return_value='/usr/bin/unshare'), \
                mock.patch.object(avb.subprocess, 'Popen', return_value=output(valid)):
            result = avb.verify_isolated(self.root, source)
        self.assertTrue(result['payload_signature_and_hashtree_verified_with_embedded_key'])
        self.assertFalse(result['signer_identity_or_trust_verified'])
        self.assertFalse((self.root / 'input-avb/payload.img').exists())
        for change in ({'root_read_only': False}, {'signer_identity_or_trust_verified': True},
                       {'verification_exit_code': 1}, {'no_new_privs': False}):
            candidate = {**valid, **change}
            with self.subTest(change=change), \
                    mock.patch.object(avb.shutil, 'which', return_value='/usr/bin/unshare'), \
                    mock.patch.object(avb.subprocess, 'Popen', return_value=output(candidate)), \
                    self.assertRaises(avb.AvbProbeError):
                avb.verify_isolated(self.root, source)
            self.assertFalse((self.root / 'input-avb/payload.img').exists())

    def test_existing_sandbox_input_is_not_overwritten(self):
        (self.root / 'input-avb').mkdir()
        destination = self.root / 'input-avb/payload.img'
        destination.write_bytes(b'leave intact')
        source = self.root / 'source.img'
        source.write_bytes(b'new')
        with mock.patch.object(avb.shutil, 'which', return_value='/usr/bin/unshare'):
            with self.assertRaises(avb.AvbProbeError):
                avb.verify_isolated(self.root, source)
        self.assertEqual(destination.read_bytes(), b'leave intact')


if __name__ == '__main__':
    unittest.main()
