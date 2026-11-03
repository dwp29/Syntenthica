import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import audit_gms_inner_signature as inner

class InnerSignatureTests(unittest.TestCase):
    def test_identity_is_bounded_and_rejects_traversal(self):
        inner._validate_identity('/app/control.apk',1,'a'*64)
        for path,size,sha in [('/a/../x.apk',1,'a'*64),('relative.apk',1,'a'*64),('/a//x.apk',1,'a'*64),
                              ('/a/a.apk',0,'a'*64),('/a/a.apk',inner.MAX_APK+1,'a'*64),('/a/a.apk',1,'G'*64)]:
            with self.subTest(path=path,size=size),self.assertRaises(inner.InnerError):inner._validate_identity(path,size,sha)
    def test_launcher_requires_unchanged_base_and_compiles(self):
        launcher=inner._launcher();compile(launcher,'launcher','exec')
        self.assertIn('os.closerange(3,exportfd)',launcher);self.assertIn('h.hexdigest() != exportsha',launcher)
        with self.assertRaises(inner.InnerError):inner._launcher('unexpected')
    def test_export_failure_removes_private_output_and_copied_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sandbox=root/'sandbox';(sandbox/'input').mkdir(parents=True)
            image=root/'input.img';image.write_bytes(b'payload');output=root/'target.apk'
            class Bad:
                returncode=1
                def __init__(self,*a,**kw):pass
                def communicate(self,timeout):return b'',b'failed'
            with patch.object(inner.shutil,'which',return_value='/usr/bin/unshare'),patch.object(inner.subprocess,'Popen',Bad):
                with self.assertRaises(inner.InnerError):inner.export_raw(sandbox,image,output,path='/app/a.apk',size=3,sha='a'*64,control=True)
            self.assertFalse(output.exists());self.assertFalse((sandbox/'input/payload.erofs').exists());self.assertEqual(image.read_bytes(),b'payload')
    def test_successful_export_checks_fd_content_and_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sandbox=root/'sandbox';(sandbox/'input').mkdir(parents=True)
            image=root/'input.img';image.write_bytes(b'payload');output=root/'target.apk';data=b'apk';sha=hashlib.sha256(data).hexdigest()
            class Good:
                returncode=0
                def __init__(self,*a,**kw):
                    os.write(kw['pass_fds'][0],data)
                def communicate(self,timeout):
                    return json.dumps({'tool_exit_code':0,'root_read_only':True,'no_new_privs':True,'capabilities_dropped':True,
                       'exported':{'bytes':3,'sha256':sha,'path':'/app/a.apk'}}).encode(),b''
            with patch.object(inner.shutil,'which',return_value='/usr/bin/unshare'),patch.object(inner.subprocess,'Popen',Good):
                r=inner.export_raw(sandbox,image,output,path='/app/a.apk',size=3,sha=sha,control=True)
            self.assertEqual(output.read_bytes(),data);self.assertEqual(r['input_sha256'],hashlib.sha256(b'payload').hexdigest())
            self.assertFalse((sandbox/'input/payload.erofs').exists())
    def test_bad_export_hash_and_symlink_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sandbox=root/'sandbox';(sandbox/'input').mkdir(parents=True)
            image=root/'i';image.write_bytes(b'image');output=root/'o';output.symlink_to(root/'missing')
            with patch.object(inner.shutil,'which',return_value='/usr/bin/unshare'):
                with self.assertRaises(inner.InnerError):inner.export_raw(sandbox,image,output,path='/a.apk',size=1,sha='a'*64)
            self.assertTrue(output.is_symlink());self.assertFalse((root/'missing').exists())
    def test_mutation_keeps_zip_directory_and_changes_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'in.apk';dst=Path(tmp)/'out.apk'
            with zipfile.ZipFile(src,'x') as z:z.writestr('a',b'abcdef')
            inner.mutate_one_zip_byte(src,dst)
            self.assertNotEqual(src.read_bytes(),dst.read_bytes())
            with zipfile.ZipFile(dst) as z:self.assertEqual(z.namelist(),['a'])
            with self.assertRaises(inner.InnerError):inner.mutate_one_zip_byte(src,dst)
    def test_verifier_requires_exit_one_signer_and_modern_scheme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);apk=root/'x.apk';apk.write_bytes(b'example');tool=root/'signer'
            tool.write_text('#!/bin/sh\nprintf "Verified using v3 scheme test: true\\nSigner #1 certificate SHA-256 digest: '+('a'*64)+'\\n"\nexit 0\n');tool.chmod(0o755)
            result=inner.verify_apk(apk,str(tool));self.assertTrue(result['signature_verified_on_host'])
            self.assertFalse(result['signer_identity_or_device_trust_verified'])
            tool.write_text('#!/bin/sh\nprintf "Verified using v3 scheme test: true\\nSigner #1 certificate SHA-256 digest: '+('a'*64)+'\\n"\nexit 1\n');tool.chmod(0o755)
            self.assertFalse(inner.verify_apk(apk,str(tool))['signature_verified_on_host'])
            tool.write_text('#!/bin/sh\nprintf "Verified using v3 scheme test: true\\nSigner #1 certificate SHA-256 digest: '+('a'*64)+'\\nFuture signer #2 certificate SHA-256 digest: '+('b'*64)+'\\n"\nexit 0\n');tool.chmod(0o755)
            self.assertFalse(inner.verify_apk(apk,str(tool))['signature_verified_on_host'])
            tool.write_text('#!/bin/sh\nprintf "Verified using v3 scheme test: true\\n"\nexit 0\n');tool.chmod(0o755)
            self.assertFalse(inner.verify_apk(apk,str(tool))['signature_verified_on_host'])
if __name__=='__main__':unittest.main()
