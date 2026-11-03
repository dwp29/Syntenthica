import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'synthetica-project'))
import probe_shell_apk as p

class ProbeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='.work-shell-test-', dir=ROOT)
        self.root = Path(self.tmp.name)
        self.apk = self.root/'input.apk'
        with zipfile.ZipFile(self.apk,'w') as z:
            z.writestr('AndroidManifest.xml', b'\x03\x00\x08\x00manifest')
            z.writestr('classes.dex', b'dex synthetic')
    def tearDown(self): self.tmp.cleanup()
    def test_archive_records_bounded_manifest_and_hash(self):
        info=p.inspect_archive(self.apk)
        self.assertEqual(info['entries'], 2)
        self.assertEqual(info['manifest_sha256'], hashlib.sha256(b'\x03\x00\x08\x00manifest').hexdigest())
    def test_missing_manifest_rejected(self):
        with zipfile.ZipFile(self.apk,'w') as z: z.writestr('other', b'data')
        with self.assertRaises(p.ProbeError): p.inspect_archive(self.apk)
    def test_control_characters_are_not_reported(self):
        self.assertEqual(p.excerpt(b'bad\x1b[31m\x00'), 'bad?[31m?')
    def test_tool_error_does_not_fail_open(self):
        result=p.tool_result([str(self.root/'missing')])
        self.assertIsNone(result['exit'])

@unittest.skipUnless(p.vintf.pytsk3 and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(), 'requires pytsk3/e2fsprogs')
class ProbeExt4Tests(ProbeArchiveTests):
    def test_extracts_and_readbacks_locked_path(self):
        img=self.root/'system.img'
        with img.open('wb') as f: f.truncate(24*1024*1024)
        subprocess.run(['/usr/sbin/mke2fs','-q','-t','ext4','-F',str(img)],check=True)
        commands=self.root/'commands'; commands.write_text('mkdir /system\nmkdir /system/priv-app\nmkdir /system/priv-app/Shell\n'+f'write {self.apk} {p.APK_PATH}\n')
        subprocess.run(['/usr/sbin/debugfs','-w','-f',str(commands),str(img)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        out=self.root/'output.apk'; size,sha=p.extract_apk(img,out)
        self.assertEqual(size,self.apk.stat().st_size)
        self.assertEqual(sha,hashlib.sha256(self.apk.read_bytes()).hexdigest())
        self.assertEqual(out.read_bytes(),self.apk.read_bytes())

if __name__ == '__main__': unittest.main()
