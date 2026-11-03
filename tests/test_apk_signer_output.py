import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import apk_signer_output as p

class SignerOutputTests(unittest.TestCase):
    def test_known_android_sdk_signer_labels(self):
        cert='AB'*32
        for prefix in ('Signer #1','Signer #1:','V2 Signer:','V3 Signer:','V3.0 Signer:',
                       'V3.1 Signer: (minSdkVersion=33, maxSdkVersion=2147483647)',
                       'V3.0 Signer: (minSdkVersion=28 (dev release=true), maxSdkVersion=32)'):
            with self.subTest(prefix=prefix):
                self.assertEqual(p.parse_certificates(prefix+' certificate SHA-256 digest: '+cert+'\n'),[cert.lower()])
    def test_excludes_source_stamp_unknown_and_bad_values(self):
        digest='f'*64
        for line in ('Source Stamp Signer: certificate SHA-256 digest: '+digest,
                     'Signer (minSdkVersion=28) #1 certificate SHA-256 digest: '+digest,
                     'V3.2 Hybrid PQC Signer: certificate SHA-256 digest: '+digest,
                     'V3.0 Signer: certificate SHA-256 digest: '+digest+'x'):
            with self.subTest(line=line):self.assertEqual(p.parse_certificates(line),[])
    def test_multiple_distinct_certificates_remain_visible(self):
        line=lambda x:'V3.0 Signer: certificate SHA-256 digest: '+x*64+'\n'
        self.assertEqual(p.parse_certificates(line('a')+line('b')+line('a')),['a'*64,'b'*64])
    def test_scheme_versions_and_duplicate_rejection(self):
        text='Verified using v3 scheme (APK Signature Scheme v3): true\nVerified using v3.1 scheme (APK Signature Scheme v3.1): false\n'
        self.assertEqual(p.parse_schemes(text),{'3':True,'3.1':False})
        with self.assertRaises(p.SignerOutputError):p.parse_schemes(text+text)
    def test_output_cap(self):
        with self.assertRaises(p.SignerOutputError):p.parse_certificates('a'*(p.MAX_OUTPUT+1))
if __name__=='__main__':unittest.main()
