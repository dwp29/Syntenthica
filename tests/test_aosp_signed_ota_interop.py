"""Two-pass AOSP SignApk experiment using synthetic ZIPs and throwaway keys only."""
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
sys.path.insert(0, str(ROOT / 'tests'))
import audit_recovery_signature as recovery
import audit_signed_ota as gate
import build_ota_metadata_candidate as ota
from test_audit_recovery_signature import make_cert
from test_audit_signed_ota import checked, make_reference, rewrite_zip, sha

JAR = os.environ.get('AOSP_SIGNAPK_JAR')
LIB = os.environ.get('AOSP_SIGNAPK_LIB')


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=90)


@unittest.skipUnless(recovery.cms and JAR and LIB and shutil.which('java') and shutil.which('openssl'),
                     'Pinned AOSP SignApk, Java, OpenSSL, asn1crypto and protobuf required')
class SignedOtaSignApkInterop(unittest.TestCase):
    def test_signapk_reorders_then_two_pass_synthetic_control(self):
        jar, lib = Path(JAR), Path(LIB)
        self.assertTrue(jar.is_file())
        self.assertTrue((lib / 'libconscrypt_openjdk_jni.so').is_file())
        with tempfile.TemporaryDirectory(prefix='synthetic-aosp-ota-gate-') as temp:
            root = Path(temp)
            key, cert, pin = make_cert(root, 'throwaway')
            pk8 = root / 'throwaway.pk8'
            run(['openssl', 'pkcs8', '-topk8', '-inform', 'PEM', '-outform', 'DER',
                 '-in', str(key), '-out', str(pk8), '-nocrypt'], root)
            os.chmod(pk8, 0o600)
            reference = make_reference(root, cert)
            reference_hash = sha(reference)
            first, intermediate, final = root / 'first.zip', root / 'intermediate.zip', root / 'final.zip'

            def sign(src, dst):
                run(['java', '-Xmx1g', f'-Djava.library.path={lib}', '-jar', str(jar), '-w',
                     str(cert), str(pk8), str(src), str(dst)], root)

            sign(reference, first)
            self.assertEqual(sha(reference), reference_hash)
            self.assertTrue(recovery.audit(first, cert, sha(first), pin)['signature_matches_reference_public_key'])
            with self.assertRaisesRegex(gate.SignedOtaError, 'offset/size'):
                checked(reference, first, cert, pin)

            # In this small control only, derive new fixed-width property values
            # from the first SignApk layout, then re-sign. The final gate below
            # independently checks that this second layout really stayed put.
            with zipfile.ZipFile(first) as z:
                text, pb = z.read(ota.METADATA), z.read(ota.METADATA_PB)
                props, order = ota.property_values(text, pb)
                positions = {
                    'metadata': (gate._stored_data_offset(z, z.getinfo(ota.METADATA)), len(text)),
                    'metadata.pb': (gate._stored_data_offset(z, z.getinfo(ota.METADATA_PB)), len(pb)),
                }
                replacements = {}
                for name, old in props.items():
                    value = ','.join(f'{short}:{positions[short][0]}:{positions[short][1]}' for short in order[name])
                    self.assertLessEqual(len(value), len(old))
                    replacements[name] = value.ljust(len(old))
                final_text, final_pb = ota.rewrite_legacy(text, replacements), ota.rewrite_proto(pb, replacements)
                self.assertEqual((len(final_text), len(final_pb)), (len(text), len(pb)))
            rewrite_zip(first, intermediate, {ota.METADATA: final_text, ota.METADATA_PB: final_pb})
            sign(intermediate, final)
            result = checked(reference, final, cert, pin)
            self.assertTrue(result['signature']['signature_matches_reference_public_key'])
            self.assertTrue(result['ota_metadata']['legacy_and_protobuf_values_equal'])
            self.assertTrue(result['embedded_otacert_public_key_matches_explicit_pin'])
            self.assertEqual(len(result['ota_metadata']['property_files']), 2)
            self.assertEqual(reference_hash, sha(reference))
            self.assertIn('not_flash_approval', result['status'])


if __name__ == '__main__':
    unittest.main()
