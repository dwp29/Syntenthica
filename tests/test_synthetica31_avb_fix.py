"""Exercise AVB repair on disposable synthetic files; no device needed."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build-kit/scripts'))
import audit_boot_avb_hash as avb
import audit_synthetica3_boot as boot

@unittest.skipUnless(os.environ.get('S31_FIX_AVB') and os.environ.get('S31_AVBTOOL') and shutil.which('busybox'), 'compiled helper and avbtool required')
class FixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name);self.img=self.dir/'boot.img'
        self.img.write_bytes(b'ANDROID!'+b'A'*4088)
        subprocess.run([sys.executable,os.environ['S31_AVBTOOL'],'add_hash_footer','--image',str(self.img),
                        '--partition_size','1048576','--partition_name','boot'],check=True,capture_output=True)
        self.assertTrue(avb.inspect(self.img)['embedded_boot_hash']['digest_matches'])
        with self.img.open('rb') as f: self.foot=boot.footer(f,self.img.stat().st_size)
        self.vb=self.foot['vbmeta_offset']
        with self.img.open('rb') as f:
            f.seek(self.vb); h=avb.HEADER.unpack(f.read(256))
            self.desc=self.vb+256+h[3]+h[14]
            f.seek(self.desc); d=avb.HASH_DESC.unpack(f.read(avb.HASH_DESC.size))
        self.dlen=self.desc+avb.HASH_DESC.size+d[4]+d[5]
    def run_fix(self, file=None, busybox=None):
        prefix=os.environ.get('S31_FIX_PREFIX','').split()
        return subprocess.run(prefix+[os.environ['S31_FIX_AVB'],str(file or self.img),busybox or shutil.which('busybox')],capture_output=True)
    def test_repairs_stale_descriptor_digest_and_length(self):
        data=bytearray(self.img.read_bytes()); data[self.desc+16:self.desc+24]=struct.pack('>Q',800000);data[self.dlen:self.dlen+32]=b'X'*32
        self.img.write_bytes(data)
        p=self.run_fix();self.assertEqual(p.returncode,0,p.stderr)
        result=avb.inspect(self.img);self.assertTrue(result['embedded_boot_hash']['digest_matches'])
        self.assertEqual(result['embedded_boot_hash']['image_bytes'],self.foot['original_image_size'])
        after=bytearray(self.img.read_bytes());after[self.desc+16:self.desc+24]=data[self.desc+16:self.desc+24];after[self.dlen:self.dlen+32]=data[self.dlen:self.dlen+32]
        self.assertEqual(data,after)
        subprocess.run([sys.executable,os.environ['S31_AVBTOOL'],'verify_image','--image',str(self.img)],check=True,capture_output=True)
    def test_refuses_signed_or_malformed_without_writing(self):
        original=self.img.read_bytes()
        for off,val in ((self.vb+28,b'\0\0\0\1'),(self.vb,b'BAD!'),(self.desc+24,b'md5xxx')):
            with self.subTest(off=off):
                data=bytearray(original);data[off:off+len(val)]=val;self.img.write_bytes(data)
                self.assertNotEqual(self.run_fix().returncode,0);self.assertEqual(self.img.read_bytes(),data)
    def test_missing_hash_tool_and_symlink_refused(self):
        before=self.img.read_bytes();self.assertNotEqual(self.run_fix(busybox='/not/a/program').returncode,0);self.assertEqual(self.img.read_bytes(),before)
        link=self.dir/'link';link.symlink_to(self.img)
        self.assertNotEqual(self.run_fix(file=link).returncode,0);self.assertEqual(self.img.read_bytes(),before)
