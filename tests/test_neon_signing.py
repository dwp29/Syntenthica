"""Non-secret unit tests for the opt-in local signing gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_signer', ROOT / 'build-kit/scripts/sign_neon_manager_locally.py')
assert spec and spec.loader
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)


class SigningGuardTests(unittest.TestCase):
    def test_only_original_certificate_is_accepted(self):
        colon = ':'.join(signer.EXPECTED_CERT[i:i + 2].upper() for i in range(0, 64, 2))
        self.assertEqual(signer.keytool_certificate('Certificate fingerprints:\n\t SHA256: ' + colon + '\n'), signer.EXPECTED_CERT)
        self.assertEqual(signer.apksigner_certificate('Signer #1 certificate SHA-256 digest: ' + signer.EXPECTED_CERT + '\n'), signer.EXPECTED_CERT)
        signer.require_expected_cert(signer.EXPECTED_CERT)
        with self.assertRaises(ValueError):
            signer.require_expected_cert('0' * 64)
        with self.assertRaises(ValueError):
            signer.keytool_certificate('no certificate')
        with self.assertRaises(ValueError):
            signer.apksigner_certificate('Signer #1 certificate SHA-256 digest: ' + signer.EXPECTED_CERT + '\n' +
                                         'Signer #2 certificate SHA-256 digest: ' + signer.EXPECTED_CERT + '\n')

    def test_metadata_gate_rejects_preview_and_old_version(self):
        with mock.patch.object(signer, 'command_output', return_value="package: name='net.ember.labs' versionCode='40000' versionName='3.0.0'\n"):
            signer.validate_package(Path('/aapt'), Path('/unsigned.apk'))
        for bad in ("package: name='net.ember.labs.neonpreview' versionCode='40000' versionName='3.0.0'",
                    "package: name='net.ember.labs' versionCode='30004' versionName='3.0.0'"):
            with self.subTest(bad=bad), mock.patch.object(signer, 'command_output', return_value=bad), self.assertRaises(ValueError):
                signer.validate_package(Path('/aapt'), Path('/unsigned.apk'))

    def test_no_password_flags_or_bundled_private_key(self):
        source = (ROOT / 'build-kit/scripts/sign_neon_manager_locally.py').read_text()
        for dangerous in ('--ks-pass', '--key-pass', 'KEYSTORE_PASSWORD'):
            self.assertNotIn(dangerous, source)
        self.assertIn('sys.stdin.isatty()', source)
        self.assertIn('os.O_EXCL', source)
        self.assertIn('--expected-sha256', source)


if __name__ == '__main__':
    unittest.main()
