import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'))
import audit_gmssystem_apex as g

@unittest.skipUnless(g.vintf.pytsk3 is not None and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(),'requires pytsk3 and e2fsprogs')
class GmsApexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='.work-gms-apex-',dir=ROOT);self.root=Path(self.tmp.name)
        self.image=self.root/'payload.img'
        with self.image.open('wb') as f:f.truncate(24*1024*1024)
        subprocess.run(['/usr/sbin/mke2fs','-q','-t','ext4','-F',str(self.image)],check=True)
        self.apk=self.root/'gms.apk'
        with zipfile.ZipFile(self.apk,'w') as z:
            z.writestr('AndroidManifest.xml',b'fake manifest');z.writestr('package.txt','com.google.android.gms')
        cmds=self.root/'debugfs.txt';cmds.write_text(f'mkdir /priv-app\nmkdir /priv-app/Gms\nwrite {self.apk} /priv-app/Gms/base.apk\nsymlink /priv-app/GmsAlias.apk /data/app/Gms.apk\n')
        subprocess.run(['/usr/sbin/debugfs','-w','-f',str(cmds),str(self.image)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        self.aapt=self.root/'aapt';self.aapt2=self.root/'aapt2'
        self.aapt.write_text('#!'+sys.executable+'''\nimport sys,zipfile
pkg=zipfile.ZipFile(sys.argv[-1]).read('package.txt').decode()
print("package: name='"+pkg+"' versionCode='1'")
''');self.aapt.chmod(0o755)
        self.aapt2.write_text('#!'+sys.executable+'\n# second reader\nprint("unused")\n');self.aapt2.chmod(0o755)
        self.scratch=self.root/'scratch';self.scratch.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def test_read_ext4_payload_and_find_gms_without_modifying_image(self):
        before=hashlib.sha256(self.image.read_bytes()).hexdigest()
        rows=g.inspect_ext4(self.image,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertTrue(rows['gms_package_found']);self.assertEqual(rows['apk_count'],1)
        self.assertEqual(rows['apks'][0]['path'],'/priv-app/Gms/base.apk')
        self.assertEqual(rows['apks'][0]['sha256'],hashlib.sha256(self.apk.read_bytes()).hexdigest())
        self.assertEqual(len(rows['symlinks_not_followed']),1)
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(),before)
        self.assertEqual(list(self.scratch.iterdir()),[])
    def test_apex_zip_and_payload_are_read_without_modification(self):
        package=self.root/'input.apex'
        with zipfile.ZipFile(package,'w') as z:
            z.writestr('apex_manifest.pb',b'test');z.write(self.image,'apex_payload.img')
        before=hashlib.sha256(package.read_bytes()).hexdigest()
        result=g.inspect_apex(package,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertEqual(result['status'],'READ_ONLY_APEX_CONTENTS_INSPECTED_HOLD')
        self.assertTrue(result['payload']['contents']['gms_package_found'])
        self.assertTrue(result['payload']['zip_crc_checked_at_eof'])
        self.assertFalse(result['apex_signature_verified']);self.assertFalse(result['runtime_activation_tested'])
        self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(),before)
    def test_unsupported_payload_is_inconclusive(self):
        package=self.root/'unknown.apex'
        with zipfile.ZipFile(package,'w') as z:z.writestr('apex_payload.img',b'unknown payload'*200)
        result=g.inspect_apex(package,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertEqual(result['status'],'INCOMPLETE_UNSUPPORTED_APEX_FILESYSTEM_HOLD')
        self.assertNotIn('contents',result['payload'])
    def test_duplicate_member_fails_closed(self):
        package=self.root/'duplicate.apex'
        with zipfile.ZipFile(package,'w') as z:
            z.writestr('apex_payload.img',b'1');z.writestr('apex_payload.img',b'2')
        with self.assertRaises(g.GmsApexError):g.inspect_apex(package,str(self.aapt),str(self.aapt2),self.scratch)
if __name__=='__main__':unittest.main()
