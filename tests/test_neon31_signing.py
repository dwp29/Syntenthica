"""Non-secret checks for the 3.1 original-key local signing gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_signer31', ROOT / 'build-kit/scripts/sign_manager_31_locally.py')
assert spec and spec.loader
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)


class Signing31Tests(unittest.TestCase):
    def test_only_original_certificate_and_version_are_accepted(self):
        signer.require_expected_cert(signer.EXPECTED_CERT)
        with self.assertRaises(ValueError):
            signer.require_expected_cert('0' * 64)
        good = "package: name='net.ember.labs' versionCode='41000' versionName='3.1.0'\n"
        with mock.patch.object(signer, 'command_output', return_value=good):
            signer.validate_package(Path('/aapt'), Path('/unsigned.apk'))
        for bad in ("package: name='net.ember.labs.neon31preview' versionCode='41000' versionName='3.1.0'",
                    "package: name='net.ember.labs' versionCode='40000' versionName='3.0.0'"):
            with self.subTest(bad=bad), mock.patch.object(signer, 'command_output', return_value=bad), self.assertRaises(ValueError):
                signer.validate_package(Path('/aapt'), Path('/unsigned.apk'))

    def test_signature_schemes_must_be_verified(self):
        good = ('Verified using v2 scheme (APK Signature Scheme v2): true\n'
                'Verified using v3 scheme (APK Signature Scheme v3): true\n')
        signer.validate_schemes(good)
        for text in ('', good.replace('v3 scheme (APK Signature Scheme v3): true', 'v3 scheme (APK Signature Scheme v3): false')):
            with self.assertRaises(ValueError):
                signer.validate_schemes(text)

    def test_compare_all_non_signature_payloads_and_reject_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b, dup = root / 'a.apk', root / 'b.apk', root / 'dup.apk'
            with zipfile.ZipFile(a, 'w') as z:
                z.writestr('classes.dex', b'payload')
                z.writestr('META-INF/com/google/android/update-binary', b'script')
            with zipfile.ZipFile(b, 'w') as z:
                z.writestr('classes.dex', b'payload')
                z.writestr('META-INF/com/google/android/update-binary', b'script')
                z.writestr('META-INF/CERT.SF', b'signature')
                z.writestr('META-INF/CERT.RSA', b'signature')
            self.assertEqual(signer.payload_digests(a), signer.payload_digests(b))
            with zipfile.ZipFile(dup, 'w') as z:
                z.writestr('classes.dex', b'first')
                with self.assertWarns(UserWarning):
                    z.writestr('classes.dex', b'second')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                signer.payload_digests(dup)

    def test_no_password_flags_and_output_is_exclusive(self):
        source = (ROOT / 'build-kit/scripts/sign_manager_31_locally.py').read_text()
        for dangerous in ('--ks-pass', '--key-pass', 'KEYSTORE_PASSWORD'):
            self.assertNotIn(dangerous, source)
        for guard in ('sys.stdin.isatty()', 'os.O_EXCL', '--expected-sha256', 'ROOT in keystore.parents',
                      "'-P', '16'", 'payload_digests(signed) != original_payload'):
            self.assertIn(guard, source)


if __name__ == '__main__':
    unittest.main()
