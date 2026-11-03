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
    def test_mixed_known_and_unknown_signers_are_ambiguous_but_stamp_is_not(self):
        known='V3.0 Signer: certificate SHA-256 digest: '+'a'*64+'\n'
        unknown='Future signer #2 certificate SHA-256 digest: '+'b'*64+'\n'
        stamp='Source Stamp Signer: certificate SHA-256 digest: '+'c'*64+'\n'
        self.assertEqual(p.parse_certificates(known+unknown),['a'*64])
        self.assertEqual(p.unparsed_signer_certificate_lines(known+unknown),[unknown.strip()])
        self.assertEqual(p.unparsed_signer_certificate_lines(known+stamp),[])
        self.assertLessEqual(len(p.unparsed_signer_certificate_lines(unknown*100)),8)
    def test_multiple_distinct_certificates_remain_visible(self):
        line=lambda x:'V3.0 Signer: certificate SHA-256 digest: '+x*64+'\n'
        self.assertEqual(p.parse_certificates(line('a')+line('b')+line('a')),['a'*64,'b'*64])
    def test_scheme_versions_and_duplicate_rejection(self):
        text='Verified using v3 scheme (APK Signature Scheme v3): true\nVerified using v3.1 scheme (APK Signature Scheme v3.1): false\n'
        self.assertEqual(p.parse_schemes(text),{'3':True,'3.1':False})
        with self.assertRaises(p.SignerOutputError):p.parse_schemes(text+text)
    def test_public_aosp_testkey_is_flagged_without_assuming_other_trust(self):
        self.assertTrue(p.matches_aosp_public_testkey(p.AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256.upper()))
        self.assertFalse(p.matches_aosp_public_testkey('b'*64))
        self.assertIsNone(p.matches_aosp_public_testkey(None))
        with self.assertRaises(p.SignerOutputError):p.matches_aosp_public_testkey('invalid')
    def test_output_cap(self):
        with self.assertRaises(p.SignerOutputError):p.parse_certificates('a'*(p.MAX_OUTPUT+1))
if __name__=='__main__':unittest.main()
