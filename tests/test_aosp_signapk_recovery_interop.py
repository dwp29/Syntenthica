"""Interop against hash-pinned AOSP SignApk, with disposable synthetic keys only."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_recovery_signature as audit

JAR = os.environ.get('AOSP_SIGNAPK_JAR')
LIB = os.environ.get('AOSP_SIGNAPK_LIB')


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=90)


def sha(data):
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(audit.cms and JAR and LIB and shutil.which('java') and shutil.which('openssl'),
                     'Pinned AOSP SignApk, Java, OpenSSL and asn1crypto required')
class SignApkInterop(unittest.TestCase):
    def test_real_signapk_synthetic_package_and_tamper(self):
        jar, lib = Path(JAR), Path(LIB)
        self.assertTrue(jar.is_file())
        self.assertTrue((lib / 'libconscrypt_openjdk_jni.so').is_file())
        with tempfile.TemporaryDirectory(prefix='synthetic-aosp-signapk-') as temp:
            root = Path(temp)
            private, cert, pk8 = root / 'fixture.key', root / 'fixture.x509.pem', root / 'fixture.pk8'
            run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-sha256', '-nodes',
                 '-keyout', str(private), '-out', str(cert), '-subj', '/CN=ephemeral-fixture', '-days', '1'], root)
            os.chmod(private, 0o600)
            run(['openssl', 'pkcs8', '-topk8', '-inform', 'PEM', '-outform', 'DER',
                 '-in', str(private), '-out', str(pk8), '-nocrypt'], root)
            os.chmod(pk8, 0o600)
            original, signed = root / 'source.zip', root / 'signed.zip'
            with zipfile.ZipFile(original, 'w') as z:
                z.writestr('a.txt', 'synthetic data only')
                z.writestr('metadata', 'no ROM content')
            source_hash = sha(original.read_bytes())
            run(['java', '-Xmx1g', f'-Djava.library.path={lib}', '-jar', str(jar), '-w',
                 str(cert), str(pk8), str(original), str(signed)], root)
            self.assertEqual(source_hash, sha(original.read_bytes()))
            with zipfile.ZipFile(signed) as z:
                self.assertTrue(z.comment.startswith(b'signed by SignApk\0'))
                self.assertEqual(z.read('metadata'), b'no ROM content')
            _, spki, _, _ = audit._certificate(cert)
            key_pin = sha(spki)
            result = audit.audit(signed, cert, sha(signed.read_bytes()), key_pin)
            self.assertTrue(result['signature_matches_reference_public_key'])
            self.assertFalse(result['recovery_certificate_trust_or_settings_verified'])
            self.assertFalse(result['target_recovery_implementation_executed'])
            raw = bytearray(signed.read_bytes())
            raw[35] ^= 1
            signed.write_bytes(raw)
            with self.assertRaisesRegex(audit.RecoverySignatureError, 'does not match the specified public key'):
                audit.audit(signed, cert, sha(raw), key_pin)


if __name__ == '__main__':
    unittest.main()
