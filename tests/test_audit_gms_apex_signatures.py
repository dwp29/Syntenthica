import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import audit_gms_apex_signatures as s

class GmsSignatureTests(unittest.TestCase):
    def call(self,exitcode,output):
        proc=SimpleNamespace(returncode=exitcode,stdout=output.encode(),stderr=b'')
        with mock.patch.object(s.pre,'digest_file',return_value=(s.APEX_BYTES,s.APEX_SHA256)),\
             mock.patch.object(s.scan,'_tool_digest',return_value='a'*64),\
             mock.patch.object(s.subprocess,'run',return_value=proc) as invoke:
            result=s.outer_signature(Path('/fake.apex'),'/bin/true')
            self.assertNotIn('GH_TOKEN',invoke.call_args.kwargs['env'])
        return result
    def test_host_success_is_not_trust(self):
        cert='f'*64
        out='Verified using v3 scheme (APK Signature Scheme v3): true\nV3.0 Signer: certificate SHA-256 digest: '+cert+'\n'
        r=self.call(0,out)
        self.assertTrue(r['outer_signature_verified_by_host']);self.assertFalse(r['signer_identity_or_device_trust_verified'])
        self.assertEqual(r['certificate_sha256'],cert);self.assertEqual(r['schemes_reported'],{'3':True})
    def test_exit_failure_or_ambiguous_cert_does_not_pass(self):
        cert='a'*64;out='Signer #1 certificate SHA-256 digest: '+cert+'\n'
        self.assertFalse(self.call(1,out)['outer_signature_verified_by_host'])
        self.assertFalse(self.call(0,out+'Signer #2 certificate SHA-256 digest: '+'b'*64+'\n')['outer_signature_verified_by_host'])
        self.assertFalse(self.call(0,'')['outer_signature_verified_by_host'])
        self.assertFalse(self.call(0,out+'Future signer #2 certificate SHA-256 digest: '+'b'*64+'\n')['outer_signature_verified_by_host'])
    def test_unpinned_apex_rejected(self):
        with mock.patch.object(s.pre,'digest_file',return_value=(1,'0'*64)),self.assertRaises(s.GmsSignatureError):
            s.outer_signature(Path('/fake.apex'),'/bin/true')
    def test_sandbox_has_tmpfs_mountpoint_before_avb_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            def fake_avb(sandbox, avbtool):
                self.assertTrue((sandbox/'out').is_dir())
                self.assertFalse((sandbox/'out').is_symlink())
                return {'tool':'avb'}
            with mock.patch.object(s.check,'prepare_tool',return_value={'tool':'aosp'}), \
                 mock.patch.object(s.avb,'prepare',side_effect=fake_avb):
                sandbox,aosp,avb=s.prepare_sandbox(work,Path('/ota.zip'),Path('/avbtool'))
            self.assertEqual(sandbox,work/'sandbox')
            self.assertEqual(aosp,{'tool':'aosp'});self.assertEqual(avb,{'tool':'avb'})
    def test_nonempty_scratch_rejected_before_tool_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'existing').write_text('leave intact')
            with mock.patch.object(s.check,'prepare_tool') as prepare, self.assertRaises(s.GmsSignatureError):
                s.prepare_sandbox(work,Path('/ota.zip'),Path('/avbtool'))
            prepare.assert_not_called()
if __name__=='__main__':unittest.main()
