import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import scan_apk_packages as s

class PackageNameTests(unittest.TestCase):
    def test_valid_aapt_package(self):
        self.assertEqual(s.parse_package("package: name='com.example.music' versionCode='1'\n"), 'com.example.music')
    def test_missing_and_malformed_package_rejected(self):
        for text in ('', "package: name='../malicious' ", "package: name='com' ", "package: name='com..bad' ",
                     "package: name='a.b' \npackage: name='c.d' "):
            with self.subTest(text=text), self.assertRaises(s.PackageScanError): s.parse_package(text)
    def test_xmltree_root_package(self):
        text='''N: android=http://schemas.android.com/apk/res/android
  E: manifest (line=19)
    A: android:versionCode(0x0101021b)=(type 0x10)0x25
    A: package="com.android.shell" (Raw: "com.android.shell")
    E: application (line=400)
      A: package="com.example.child"
'''
        self.assertEqual(s.parse_xmltree_package(text),'com.android.shell')
    def test_xmltree_ambiguous_or_not_root_rejected(self):
        for text in ('', '  E: application (line=1)\n    A: package="com.example.fake"\n',
                     '  E: manifest (line=1)\n    E: application (line=2)\n      A: package="com.example.child"\n',
                     '  E: manifest (line=1)\n    A: package="com.one"\n    A: package="com.two"\n',
                     '  E: manifest (line=1)\n    A: package="com.one" (Raw: "com.two")\n',
                     '  E: manifest (line=1)\n    A: android:package="com.example.fake"\n'):
            with self.subTest(text=text), self.assertRaises(s.PackageScanError): s.parse_xmltree_package(text)

class PackageReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='.work-pkg-reader-',dir=ROOT)
        self.root=Path(self.tmp.name);self.apk=self.root/'sample.apk'
        with zipfile.ZipFile(self.apk,'w') as z: z.writestr('AndroidManifest.xml',b'binary xml synthetic')
    def tearDown(self): self.tmp.cleanup()
    def process(self,code,out='',err=''):
        return subprocess.CompletedProcess([],code,out.encode(),err.encode())
    def xml(self,pkg): return f'  E: manifest (line=1)\n    A: package="{pkg}" (Raw: "{pkg}")\n    E: application (line=2)\n'
    def test_normal_badging(self):
        with patch.object(s,'_run_tool',return_value=self.process(0,"package: name='com.example.app' ")):
            self.assertEqual(s.package_from_apk(self.apk,'aapt','aapt2'),('com.example.app','aapt_badging'))
    def test_failed_badging_requires_both_tree_readers(self):
        responses=[self.process(1,"package: name='com.android.shell' ",'unresolved label'),
                   self.process(0,self.xml('com.android.shell')), self.process(0,self.xml('com.android.shell'))]
        with patch.object(s,'_run_tool',side_effect=responses) as tool:
            self.assertEqual(s.package_from_apk(self.apk,'aapt','aapt2'),('com.android.shell','aapt_and_aapt2_xmltree'))
            self.assertEqual(tool.call_count,3)
    def test_tree_reader_disagreement_fails_closed(self):
        responses=[self.process(1),self.process(0,self.xml('com.one')),self.process(0,self.xml('com.two'))]
        with patch.object(s,'_run_tool',side_effect=responses),self.assertRaises(s.PackageScanError):
            s.package_from_apk(self.apk,'aapt','aapt2')
    def test_partial_badging_disagreement_fails_closed(self):
        responses=[self.process(1,"package: name='com.other.app' "),self.process(0,self.xml('com.one')),self.process(0,self.xml('com.one'))]
        with patch.object(s,'_run_tool',side_effect=responses),self.assertRaises(s.PackageScanError):
            s.package_from_apk(self.apk,'aapt','aapt2')
    def test_failed_tree_reader_fails_closed(self):
        responses=[self.process(1),self.process(0,self.xml('com.one')),self.process(1)]
        with patch.object(s,'_run_tool',side_effect=responses),self.assertRaises(s.PackageScanError):
            s.package_from_apk(self.apk,'aapt','aapt2')
    def test_duplicate_manifest_rejected_before_tools(self):
        with zipfile.ZipFile(self.apk,'a') as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning);z.writestr('AndroidManifest.xml',b'other')
        with patch.object(s,'_run_tool') as tool,self.assertRaises(s.PackageScanError):
            s.package_from_apk(self.apk,'aapt','aapt2')
        tool.assert_not_called()
    def test_badging_success_but_invalid_output_fails_closed(self):
        with patch.object(s,'_run_tool',return_value=self.process(0,'no package')) as tool,self.assertRaises(s.PackageScanError):
            s.package_from_apk(self.apk,'aapt','aapt2')
        self.assertEqual(tool.call_count,1)
    def test_tool_timeout_fails_closed(self):
        with patch.object(s.subprocess,'run',side_effect=subprocess.TimeoutExpired('aapt',60)), self.assertRaises(s.PackageScanError):
            s._run_tool(['aapt'])

@unittest.skipUnless(s.vintf.pytsk3 is not None and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(), 'requires pytsk3/e2fsprogs')
class PackageScanIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.work-pkgscan-', dir=str(ROOT))
        self.root = Path(self.temp.name)
        self.images = {}
        for name in ('system','system_ext','product'):
            img = self.root/(name+'.img')
            with img.open('wb') as f: f.truncate(32*1024*1024)
            subprocess.run(['/usr/sbin/mke2fs','-q','-t','ext4','-F',str(img)], check=True)
            self.images[name]=img
        self.aapt = self.root/'fake-aapt'
        self.aapt.write_text('#!'+sys.executable+"\nprint(\"package: name='com.example.original' versionCode='1'\")\n")
        self.aapt.chmod(0o755)
        self.aapt2=self.root/'aapt2'
        self.aapt2.write_text('#!'+sys.executable+'\n# distinct second test reader\nprint("unused")\n')
        self.aapt2.chmod(0o755)
        self.payload = self.root/'app.apk'
        with zipfile.ZipFile(self.payload,'w') as z: z.writestr('AndroidManifest.xml',b'synthetic')
        self.commands = self.root/'cmd'
        self.commands.write_text('mkdir /app\nmkdir /app/original\n'+f'write {self.payload} /app/original/original.apk\n')
        subprocess.run(['/usr/sbin/debugfs','-w','-f',str(self.commands),str(self.images['product'])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        self.scratch=self.root/'scratch';self.scratch.mkdir()
    def tearDown(self): self.temp.cleanup()
    def test_walks_real_ext4_and_confirms_no_collision(self):
        hashes={n:hashlib.sha256(p.read_bytes()).digest() for n,p in self.images.items()}
        r=s.scan(self.images,str(self.aapt),self.scratch,'com.example.target')
        self.assertEqual(r['apks_checked'],1)
        self.assertTrue(r['apk_manifest_zip_crc_checked'])
        self.assertEqual(r['independent_xmltree_fallback_count'],0)
        self.assertFalse(r['collision_found_in_scanned_roots'])
        self.assertEqual(hashes,{n:hashlib.sha256(p.read_bytes()).digest() for n,p in self.images.items()})
    def test_existing_target_package_fails_closed(self):
        with self.assertRaises(s.PackageScanError):
            s.scan(self.images,str(self.aapt),self.scratch,'com.example.original')
    def test_same_executable_cannot_be_claimed_as_independent(self):
        with self.assertRaisesRegex(s.PackageScanError,'not distinct'):
            s.scan(self.images,str(self.aapt),self.scratch,'com.example.target',aapt2=str(self.aapt))
    def test_unparseable_existing_apk_fails_closed(self):
        self.aapt.write_text('#!'+sys.executable+'\nprint("no recognizable package")\n');self.aapt.chmod(0o755)
        with self.assertRaises(s.PackageScanError):
            s.scan(self.images,str(self.aapt),self.scratch,'com.example.target')
    def test_fallback_collision_is_not_ignored(self):
        self.aapt.write_text('#!'+sys.executable+'''\nimport sys
if sys.argv[2]=='badging':
 print("package: name='com.example.original' ");sys.exit(1)
print('  E: manifest (line=1)\\n    A: package="com.example.original" (Raw: "com.example.original")')
''');self.aapt.chmod(0o755)
        aapt2=self.root/'fake-aapt2'
        aapt2.write_text('#!'+sys.executable+'''\nprint('  E: manifest (line=1)\\n    A: package="com.example.original" (Raw: "com.example.original")')
''');aapt2.chmod(0o755)
        with self.assertRaisesRegex(s.PackageScanError,'already exists'):
            s.scan(self.images,str(self.aapt),self.scratch,'com.example.original',aapt2=str(aapt2))
        result=s.scan(self.images,str(self.aapt),self.scratch,'com.example.target',aapt2=str(aapt2))
        self.assertEqual(result['independent_xmltree_fallback_count'],1)
        self.assertEqual(result['independent_xmltree_fallback_paths'],['product:/app/original/original.apk'])

if __name__ == '__main__': unittest.main()
