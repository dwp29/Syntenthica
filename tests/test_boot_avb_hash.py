"""Synthetic AVB descriptor checks; these never access an Android device."""
import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build-kit/scripts'))
import audit_boot_avb_hash as audit


def make_image(partition=b'boot', double=False, algorithm=b'sha256'):
    image=b'ANDROID!'+bytes(range(256))*16
    salt=b'unit-test-salt'
    digest=hashlib.sha256(salt+image).digest()
    v=partition+salt+digest
    n=((116+len(v)+7)//8)*8
    d=struct.pack('>QQQ32sIIII60s',2,n,len(image),algorithm,len(partition),len(salt),len(digest),0,b'')+v
    d+=bytes(16+n-len(d))
    if double: d+=d
    aux=d+bytes((-len(d))%64)
    header=audit.HEADER.pack(b'AVB0',1,0,0,len(aux),0, 0,0,0,0,0,0,0,0,0,len(d),0,0,0,b'',b'')
    vb=header+aux
    size=32768; foot=struct.pack('>4sIIQQQ28s',b'AVBf',1,0,len(image),len(image),len(vb),b'')
    return image+vb+bytes(size-len(image)-len(vb)-64)+foot

class AVBHashTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory(); self.addCleanup(self.d.cleanup)
        self.path=Path(self.d.name)/'boot.img'
    def run_image(self, data):
        self.path.write_bytes(data); return audit.inspect(self.path)
    def test_valid_hash_and_payload_tamper(self):
        raw=make_image(); r=self.run_image(raw)
        self.assertTrue(r['embedded_boot_hash']['digest_matches']); self.assertTrue(r['vbmeta_algorithm_none'])
        changed=bytearray(raw); changed[42]^=1
        self.assertFalse(self.run_image(changed)['embedded_boot_hash']['digest_matches'])
    def test_missing_or_multiple_boot_descriptors_rejected(self):
        for raw in (make_image(b'vendor'), make_image(double=True)):
            with self.assertRaises(ValueError): self.run_image(raw)
    def test_unsupported_algorithm_and_corrupt_bounds_rejected(self):
        with self.assertRaises(ValueError): self.run_image(make_image(algorithm=b'md5'))
        a=bytearray(make_image()); o=struct.unpack_from('>Q',a,len(a)-64+20)[0]
        struct.pack_into('>Q',a,o+104,0xffffffffffffffff) # descriptor size
        with self.assertRaises(ValueError): self.run_image(a)
    def test_missing_footer_rejected(self):
        a=bytearray(make_image());a[-64:-60]=b'NONE'
        with self.assertRaises(ValueError): self.run_image(a)
    def test_crosscheck_against_avbtool(self):
        tool=os.environ.get('S31_AVBTOOL')
        if not tool: self.skipTest('AVB tool not supplied')
        self.path.write_bytes(b'ANDROID!' + bytes(4096))
        subprocess.run([sys.executable,tool,'add_hash_footer','--image',str(self.path),
                        '--partition_size','1048576','--partition_name','boot'],check=True, capture_output=True)
        cmd=[sys.executable,tool,'verify_image','--image',str(self.path)]
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertTrue(audit.inspect(self.path)['embedded_boot_hash']['digest_matches'])
        data=bytearray(self.path.read_bytes()); data[16]^=1; self.path.write_bytes(data)
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertFalse(audit.inspect(self.path)['embedded_boot_hash']['digest_matches'])
    def test_real_image_if_supplied(self):
        name=os.environ.get('S31_PRIVATE_BOOT')
        if not name: self.skipTest('private boot not supplied')
        actual=audit.inspect(Path(name))
        self.assertTrue(actual['embedded_boot_hash']['digest_matches'])
        self.assertTrue(actual['vbmeta_algorithm_none'])

if __name__=='__main__':unittest.main()
