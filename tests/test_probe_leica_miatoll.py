import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'synthetica-project'))
import probe_leica_miatoll as p

def git_id(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

class LeicaProbeTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_assemble_requires_both_exact_git_blobs_and_readback(self):
        a,b=b'first bytes',b'second bytes';pa=self.root/'00';pb=self.root/'01';pa.write_bytes(a);pb.write_bytes(b)
        out=self.root/'camera.apk';ident,parts=p.assemble([(pa,len(a),git_id(a)),(pb,len(b),git_id(b))],out)
        self.assertEqual(out.read_bytes(),a+b);self.assertEqual(ident,{'bytes':len(a+b),'sha256':hashlib.sha256(a+b).hexdigest()})
        self.assertEqual(parts[0]['sha256'],hashlib.sha256(a).hexdigest())
        with self.assertRaises(p.LeicaProbeError):p.assemble([(pa,len(a),git_id(b))],self.root/'bad.apk')
        with self.assertRaises(p.LeicaProbeError):p.assemble([(pa,len(a),git_id(a))],out)
    def test_symlink_or_mutated_blob_rejected(self):
        data=b'blob-data';path=self.root/'source';path.write_bytes(data);link=self.root/'link';link.symlink_to(path)
        with self.assertRaises((p.LeicaProbeError,p.guard.AuditError,OSError)):p.part_identity(link,len(data),git_id(data))
        path.write_bytes(b'blob-datA')
        with self.assertRaises(p.LeicaProbeError):p.part_identity(path,len(data),git_id(data))
    def test_download_checks_size_and_git_object_without_printing_remote_body(self):
        data=b'example';blob=git_id(data)
        def execute(*args,**kw):kw['stdout'].write(data);return SimpleNamespace(returncode=0)
        with mock.patch.object(p.subprocess,'run',side_effect=execute) as run:
            path=p.download_part(self.root,'00',len(data),blob)
        self.assertEqual(path.read_bytes(),data);self.assertEqual(run.call_args.kwargs['stderr'],p.subprocess.DEVNULL)
    def test_inspection_requires_two_manifest_readers_to_agree(self):
        apk=self.root/'sample.apk'
        with zipfile.ZipFile(apk,'w') as z:z.writestr('AndroidManifest.xml',b'fake');z.writestr('lib/arm64-v8a/liba.so',b'sample')
        identity={'bytes':apk.stat().st_size,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}
        xml=b'  E: manifest (line=1)\n    A: package="com.example.camera"\n    E: application (line=2)\n'
        badging=b"package: name='com.example.camera' versionCode='1' versionName='5'\nsdkVersion:'29'\ntargetSdkVersion:'36'\n"
        calls=[SimpleNamespace(returncode=0,stdout=xml),SimpleNamespace(returncode=0,stdout=xml),SimpleNamespace(returncode=0,stdout=badging)]
        with mock.patch.object(p.scan,'_tool_digest',side_effect=lambda x:'1'*64 if x=='aapt' else '2'*64), \
             mock.patch.object(p.scan,'package_from_apk',return_value=('com.example.camera','aapt_badging')), \
             mock.patch.object(p.scan,'_run_tool',side_effect=calls),mock.patch.object(p,'apk_signature',return_value={'signature_verified_on_host':False}):
            r=p.inspect(apk,identity,'aapt','aapt2','signer')
        self.assertEqual(r['package'],'com.example.camera');self.assertTrue(r['independent_xml_readers_agree'])
        self.assertEqual(r['native_abis_in_apk'],['arm64-v8a']);self.assertTrue(r['all_zip_member_crc_checked'])
        calls=[SimpleNamespace(returncode=0,stdout=xml),SimpleNamespace(returncode=0,stdout=xml.replace(b'com.example.camera',b'com.example.other'))]
        with mock.patch.object(p.scan,'_tool_digest',side_effect=lambda x:'1'*64 if x=='aapt' else '2'*64), \
             mock.patch.object(p.scan,'package_from_apk',return_value=('com.example.camera','aapt_badging')), \
             mock.patch.object(p.scan,'_run_tool',side_effect=calls),self.assertRaises(p.LeicaProbeError):
            p.inspect(apk,identity,'aapt','aapt2','signer')
    def test_new_v3_signer_format_is_recognized_without_claiming_trust(self):
        output=('V3.0 Signer: certificate SHA-256 digest: '+'a'*64+'\n').encode()
        with mock.patch.object(p.scan,'_tool_digest',return_value='a'*64), \
             mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr=b'')):
            r=p.apk_signature(self.root/'sample.apk','/bin/true')
        self.assertTrue(r['signature_verified_on_host']);self.assertEqual(r['certificate_sha256'],'a'*64)
        self.assertFalse(r['signer_authority_or_platform_trust_verified'])
    def test_unrecognized_signer_format_is_bounded_and_inconclusive(self):
        output=('Signer (minSdkVersion=28) #1 certificate SHA-256 digest: '+'f'*64+'\n').encode()
        with mock.patch.object(p.scan,'_tool_digest',return_value='a'*64), \
             mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr=b'')):
            r=p.apk_signature(self.root/'sample.apk','/bin/true')
        self.assertFalse(r['signature_verified_on_host'])
        self.assertEqual(len(r['unparsed_certificate_digest_lines']),1)
        self.assertIn('Signer (minSdkVersion=28)',r['unparsed_certificate_digest_lines'][0])
    def test_public_testkey_is_detected_but_host_crypto_result_preserved(self):
        cert=p.signer_output.AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256
        output=('V3.0 Signer: certificate SHA-256 digest: '+cert+'\n').encode()
        with mock.patch.object(p.scan,'_tool_digest',return_value='a'*64), \
             mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr=b'')):
            r=p.apk_signature(self.root/'sample.apk','/bin/true')
        self.assertTrue(r['signature_verified_on_host']);self.assertTrue(r['matches_aosp_public_development_testkey'])
        self.assertEqual(r['production_key_gate'],'REJECT_PUBLIC_TESTKEY');self.assertFalse(r['signer_authority_or_platform_trust_verified'])
    def test_known_plus_unknown_signer_is_not_claimed_verified(self):
        output=('V3.0 Signer: certificate SHA-256 digest: '+'a'*64+'\nFuture signer #2 certificate SHA-256 digest: '+'b'*64+'\n').encode()
        with mock.patch.object(p.scan,'_tool_digest',return_value='a'*64), \
             mock.patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr=b'')):
            r=p.apk_signature(self.root/'sample.apk','/bin/true')
        self.assertFalse(r['signature_verified_on_host']);self.assertIsNone(r['certificate_sha256'])
        self.assertEqual(len(r['unparsed_certificate_digest_lines']),1)
    def test_ambiguous_manifest_fails_before_host_tools(self):
        apk=self.root/'sample.apk'
        with zipfile.ZipFile(apk,'w') as z:z.writestr('other',b'nothing')
        identity={'bytes':apk.stat().st_size,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}
        with mock.patch.object(p.scan,'_tool_digest',side_effect=lambda x:'1'*64 if x=='aapt' else '2'*64), \
             mock.patch.object(p.scan,'package_from_apk') as tools,self.assertRaises(p.LeicaProbeError):
            p.inspect(apk,identity,'aapt','aapt2','signer')
        tools.assert_not_called()
if __name__=='__main__':unittest.main()
