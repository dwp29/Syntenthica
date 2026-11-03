import hashlib
import sys
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'synthetica-project'))
import check_spatialflow_source_build as p

EXPECTED={'component':'com.codetrio.spatialflow.MainActivity','kind':'activity','exported':True,
          'actions':['android.intent.action.MUSIC_PLAYER'],'categories':['android.intent.category.DEFAULT'],'data':[]}
BADGING="package: name='com.codetrio.spatialflow' versionCode='10' versionName='1.8.2'\n"

class SourceBuildTests(unittest.TestCase):
    def make_apk(self,path,abi='arm64-v8a'):
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('AndroidManifest.xml',b'binary manifest')
            z.writestr('lib/'+abi+'/libaudio.so',b'native')
    def inspect_with(self,root,routes=None,verify=1,abi='arm64-v8a'):
        apk=root/'app.apk';self.make_apk(apk,abi);manifest=root/'AndroidManifest.xml';manifest.write_bytes(b'source')
        def commands(args,**kw):return BADGING if 'badging' in args else 'XML'
        def tools(args):return SimpleNamespace(returncode=(verify if args[0]=='signer' else 0),stdout=b'DOES NOT VERIFY' if args[0]=='signer' and verify else b'',stderr=b'')
        with mock.patch.object(p.preference,'prepare',return_value=(b'preference',{'status':'PROTOTYPE'})), \
             mock.patch.object(p.scan,'_tool_digest',side_effect=lambda name:hashlib.sha256(name.encode()).hexdigest()), \
             mock.patch.object(p.pre,'command',side_effect=commands), \
             mock.patch.object(p.intent,'compare_readers',return_value=[EXPECTED] if routes is None else routes), \
             mock.patch.object(p.scan,'_run_tool',side_effect=tools):
            return p.inspect(apk,manifest,'aapt','aapt2','signer','zipalign')
    def test_valid_patched_unsigned_host_result(self):
        with tempfile.TemporaryDirectory() as d:r=self.inspect_with(Path(d))
        self.assertEqual(r['status'],'UNSIGNED_HOST_BUILD_ROUTE_VERIFIED_NOT_INSTALLED')
        self.assertTrue(r['manifest']['two_readers_agree']);self.assertEqual(r['apk']['apksigner_verify_exit'],1)
    def test_v1_signature_file_is_rejected_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'app.apk';self.make_apk(apk)
            with zipfile.ZipFile(apk,'a') as z:z.writestr('META-INF/CERT.RSA',b'signed')
            manifest=Path(d)/'source';manifest.write_bytes(b'source')
            with mock.patch.object(p.preference,'prepare',return_value=(b'preference',{})), \
                 mock.patch.object(p.scan,'_tool_digest',side_effect=lambda n:hashlib.sha256(n.encode()).hexdigest()), \
                 self.assertRaises(p.SourceBuildError):
                p.inspect(apk,manifest,'aapt','aapt2','signer','zipalign')
    def test_apk_signing_block_is_rejected_even_if_verifier_would_fail(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'app.apk';self.make_apk(apk)
            data=bytearray(apk.read_bytes());offset=struct.unpack_from('<I',data,len(data)-6)[0]
            data[offset:offset]=b'APK Sig Block 42'
            struct.pack_into('<I',data,len(data)-6,offset+16);apk.write_bytes(data)
            manifest=Path(d)/'source';manifest.write_bytes(b'source')
            with mock.patch.object(p.preference,'prepare',return_value=(b'preference',{})), \
                 mock.patch.object(p.scan,'_tool_digest',side_effect=lambda n:hashlib.sha256(n.encode()).hexdigest()), \
                 self.assertRaisesRegex(p.SourceBuildError,'signing block'):
                p.inspect(apk,manifest,'aapt','aapt2','signer','zipalign')
    def test_unexpected_signing_or_manifest_is_rejected(self):
        for kw in ({'verify':0},{'routes':[]},{'abi':'x86_64'}):
            with self.subTest(kw=kw), tempfile.TemporaryDirectory() as d, self.assertRaises(p.SourceBuildError):
                self.inspect_with(Path(d),**kw)

if __name__=='__main__':unittest.main()
