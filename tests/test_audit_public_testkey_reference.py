import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import audit_public_testkey_reference as p

class PublicTestkeyTests(unittest.TestCase):
    def setUp(self):
        self.pem=b'synthetic public certificate';self.der=b'synthetic DER certificate';self.der_sha=hashlib.sha256(self.der).hexdigest()
        self.rows={
            'schema':'synthetica-leica-miatoll-prebuilt-probe-v1','status':'READ_ONLY_PREBUILT_INSPECTED_HOLD',
            'source_commit':'2582e3859181d32372a669f0cdaad151095b8a53',
            'inspection':{'apk':{'sha256':p.LEICA_APK_SHA},'apk_signature':{'certificate_sha256':self.der_sha,
                'signature_verified_on_host':True,'verifier_exit_code':0,'signer_authority_or_platform_trust_verified':False,
                'unparsed_certificate_digest_lines':[]}}}
        self.check={'id':p.LEICA_CHECK,'head_sha':p.LEICA_HEAD,'name':'Synthetica Leica miatoll source probe',
                    'status':'completed','conclusion':'success','output':{'summary':json.dumps(self.rows)}}
        self.patches=[mock.patch.object(p,'PEM_BYTES',len(self.pem)),mock.patch.object(p,'PEM_SHA',hashlib.sha256(self.pem).hexdigest()),
            mock.patch.object(p,'AOSP_BLOB',hashlib.sha1(f'blob {len(self.pem)}\0'.encode()+self.pem).hexdigest()),
            mock.patch.object(p,'DER_SHA',self.der_sha),mock.patch.object(p.signer,'matches_aosp_public_testkey',return_value=True)]
        for x in self.patches:x.start();self.addCleanup(x.stop)
    def test_same_public_certificate_rejected_for_production_not_crypto(self):
        proc=SimpleNamespace(returncode=0,stdout=self.der,stderr=b'')
        with mock.patch.object(p.subprocess,'run',return_value=proc) as invoke:r=p.inspect(self.pem,self.check)
        self.assertTrue(r['leica_matches_public_aosp_testkey']);self.assertEqual(r['production_key_gate'],'REJECT_PUBLIC_TESTKEY')
        self.assertFalse(r['signature_proves_publisher_identity']);self.assertFalse(r['device_platform_key_checked'])
        self.assertFalse(r['private_key_requested_or_used']);self.assertEqual(invoke.call_args.kwargs['input'],self.pem)
    def test_mismatched_reference_or_check_fails_closed(self):
        with mock.patch.object(p.subprocess,'run') as run:
            with self.assertRaises(p.PublicCertificateError):p.inspect(self.pem+b'x',self.check)
            with self.assertRaises(p.PublicCertificateError):p.inspect(self.pem,{**self.check,'id':1})
            run.assert_not_called()
        self.rows['inspection']['apk_signature']['unparsed_certificate_digest_lines']=['unknown']
        self.check['output']['summary']=json.dumps(self.rows)
        with self.assertRaises(p.PublicCertificateError):p.inspect(self.pem,self.check)
    def test_nonmatching_fingerprint_is_not_approved(self):
        self.rows['inspection']['apk_signature']['certificate_sha256']='b'*64;self.check['output']['summary']=json.dumps(self.rows)
        with mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=self.der,stderr=b'')):
            r=p.inspect(self.pem,self.check)
        self.assertFalse(r['leica_matches_public_aosp_testkey']);self.assertEqual(r['production_key_gate'],'NOT_ASSESSED')
    def test_inventory_checks_every_public_certificate_and_rejects_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'example.x509.pem').write_bytes(self.pem)
            with mock.patch.object(p.signer,'AOSP_PUBLIC_DEVELOPMENT_CERTIFICATES',{self.der_sha:'example'}), \
                 mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=self.der,stderr=b'')):
                r=p.inspect_inventory(root);self.assertEqual(r['public_certificates_verified'],1)
                self.assertFalse(r['nonmatching_certificate_proves_trust'])
                (root/'extra').write_bytes(b'bad')
                with self.assertRaises(p.PublicCertificateError):p.inspect_inventory(root)
    def test_invalid_der_or_openssl_failure_is_not_a_match(self):
        for proc in (SimpleNamespace(returncode=1,stdout=b'',stderr=b'bad'),SimpleNamespace(returncode=0,stdout=b'other',stderr=b'')):
            with mock.patch.object(p.subprocess,'run',return_value=proc),self.assertRaises(p.PublicCertificateError):p.inspect(self.pem,self.check)
if __name__=='__main__':unittest.main()
