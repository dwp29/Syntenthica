import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'))
import audit_additional_apks as a

class AdditionalPathTests(unittest.TestCase):
    def test_previously_scanned_prefix_is_boundary_aware(self):
        self.assertTrue(a.previously_scanned('system','/system/priv-app/X/base.apk'))
        self.assertFalse(a.previously_scanned('system','/system/priv-apps/X/base.apk'))
        self.assertFalse(a.previously_scanned('vendor','/app/Foo/base.apk'))
    def test_framework_exclusion_is_partition_specific(self):
        self.assertTrue(a.framework_path('system','/system/framework/framework-res.apk'))
        self.assertTrue(a.framework_path('product','/framework/miui.apk'))
        self.assertFalse(a.framework_path('system','/system/framework-extra/x.apk'))

@unittest.skipUnless(a.vintf.pytsk3 is not None and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(),'requires pytsk3 and e2fsprogs')
class AdditionalExt4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='.work-extra-apk-',dir=ROOT);self.root=Path(self.tmp.name)
        self.images={}
        for n in a.PARTITIONS:
            path=self.root/(n+'.img')
            with path.open('wb') as f:f.truncate(24*1024*1024)
            subprocess.run(['/usr/sbin/mke2fs','-q','-t','ext4','-F',str(path)],check=True)
            self.images[n]=path
        self.aapt=self.root/'aapt';self.aapt2=self.root/'aapt2'
        self.aapt.write_text('#!'+sys.executable+'''\nimport sys,zipfile
pkg=zipfile.ZipFile(sys.argv[-1]).read('package.txt').decode()
print("package: name='"+pkg+"' versionCode='1'")
''');self.aapt.chmod(0o755)
        self.aapt2.write_text('#!'+sys.executable+'\n# distinct test executable\nprint("unused")\n');self.aapt2.chmod(0o755)
        self.scratch=self.root/'scratch';self.scratch.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def apk(self,name,package):
        p=self.root/name
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('AndroidManifest.xml',b'fake manifest');z.writestr('package.txt',package)
        return p
    def add(self,partition,commands):
        path=self.root/'commands';path.write_text(commands)
        subprocess.run(['/usr/sbin/debugfs','-w','-f',str(path),str(self.images[partition])],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    def test_discovers_gms_only_outside_standard_roots_without_modifying_images(self):
        gms=self.apk('gms.apk','com.google.android.gms');std=self.apk('std.apk','com.example.standard')
        framework=self.apk('framework.apk','android')
        self.add('product',f'mkdir /app\nmkdir /app/Standard\nwrite {std} /app/Standard/base.apk\n'
                           +f'mkdir /data-app\nmkdir /data-app/GoogleServices\nwrite {gms} /data-app/GoogleServices/base.apk\n'
                           +f'mkdir /framework\nwrite {framework} /framework/framework-res.apk\n'
                           +'symlink /data-app/GmsAlias.apk /data/user/GmsCore.apk\n')
        hashes={n:hashlib.sha256(p.read_bytes()).digest() for n,p in self.images.items()}
        r=a.inspect(self.images,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertTrue(r['matching_gms_package_found']);self.assertFalse(r['potential_spatialflow_collision_outside_roots'])
        self.assertEqual(r['additional_apks_checked'],1);self.assertEqual(r['apks_in_previously_scanned_roots_skipped'],1)
        self.assertEqual(r['framework_apks_skipped'],1)
        self.assertEqual(r['matching_extra_apks'][0]['path'],'/data-app/GoogleServices/base.apk')
        self.assertEqual(r['matching_extra_apks'][0]['sha256'],hashlib.sha256(gms.read_bytes()).hexdigest())
        self.assertGreaterEqual(r['relevant_symlink_count'],1)
        self.assertEqual(hashes,{n:hashlib.sha256(p.read_bytes()).digest() for n,p in self.images.items()})
    def test_potential_spatialflow_collision_is_reported_not_hidden(self):
        app=self.apk('target.apk','com.codetrio.spatialflow')
        self.add('vendor',f'mkdir /app\nwrite {app} /app/candidate.apk\n')
        r=a.inspect(self.images,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertTrue(r['potential_spatialflow_collision_outside_roots'])
    def test_malformed_apk_outside_roots_fails_closed(self):
        bad=self.root/'bad.apk';bad.write_bytes(b'not a ZIP')
        self.add('product',f'mkdir /preload\nwrite {bad} /preload/bad.apk\n')
        with self.assertRaises(a.AdditionalAuditError):
            a.inspect(self.images,str(self.aapt),str(self.aapt2),self.scratch)
        self.assertEqual(list(self.scratch.iterdir()),[])

if __name__=='__main__':unittest.main()
