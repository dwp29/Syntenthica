"""Repack tests use synthetic inputs; optional private reference never leaves host."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build-kit/scripts'))
import build_synthetica31_control_boot as build
import audit_synthetica3_boot as audit
import audit_boot_avb_hash as avb
spec=importlib.util.spec_from_file_location('boot_fixture',ROOT/'tests/test_synthetica3_boot.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class RepackTests(unittest.TestCase):
    def setUp(self):
        self.avbtool=os.environ.get('S31_AVBTOOL')
        if not self.avbtool:self.skipTest('pinned avbtool not supplied')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name);self.old=self.d/'boot.img';self.output=self.d/'new.img'
        self.old.write_bytes(fixture.boot(kernel=b'old kernel',ramdisk=b'070701'+b'x'*100,tree=fixture.fdt()))
        subprocess.run([sys.executable,self.avbtool,'add_hash_footer','--image',str(self.old),
                        '--partition_size','1048576','--partition_name','boot'],check=True,capture_output=True)
        self.raw=self.old.read_bytes();self.k=b'new kernel fixture';self.sha=build.sha(self.raw)
    def construct(self,source=None,output=None):
        with patch.object(build,'REFERENCE',self.sha),patch.object(build,'SIZE',len(self.raw)),patch.object(build,'IMAGE',build.sha(self.k)),patch.object(build,'get_kernel',return_value=self.k):
            return build.construct(source or self.old,self.d/'ignored.zip',output or self.output)
    def test_repack_keeps_sections_and_repairs_unsigned_hash(self):
        result=self.construct(); self.assertEqual(self.old.read_bytes(),self.raw)
        before=audit.inspect_boot(self.old);after=audit.inspect_boot(self.output)
        cmp=audit.compare_boot(before,after,build.sha(self.k))
        self.assertTrue(all(cmp['stable_header_fields_match'].values()));self.assertTrue(all(cmp['non_kernel_sections_match'].values()))
        self.assertTrue(cmp['candidate_kernel_equals_bundle_image']);self.assertTrue(cmp['candidate_legacy_boot_id_matches'])
        self.assertTrue(avb.inspect(self.output)['embedded_boot_hash']['digest_matches'])
        self.assertEqual(build.sha(self.output.read_bytes()),result['candidate_sha256'])
        verifydir=self.d/'verify';verifydir.mkdir();shutil.copy(self.output,verifydir/'boot.img')
        subprocess.run([sys.executable,self.avbtool,'verify_image','--image',str(verifydir/'boot.img')],check=True,capture_output=True)
        other=self.d/'other.img';self.construct(output=other);self.assertEqual(self.output.read_bytes(),other.read_bytes())
    def test_modified_reference_rejected_no_output(self):
        bad=self.d/'bad.img'; raw=bytearray(self.raw);raw[4097]^=1;bad.write_bytes(raw)
        with self.assertRaises(ValueError): self.construct(source=bad)
        self.assertFalse(self.output.exists())
    def test_existing_output_refused(self):
        self.output.write_bytes(b'keep')
        with self.assertRaises(ValueError): self.construct()
        self.assertEqual(self.output.read_bytes(),b'keep')
    def test_signed_vbmeta_rejected(self):
        data=bytearray(self.raw);footer=avb.inspect(self.old)['footer'];offset=footer['vbmeta_offset']
        data[offset+28:offset+32]=(1).to_bytes(4,'big')
        bad=self.d/'signed.img';bad.write_bytes(data)
        with patch.object(build,'REFERENCE',build.sha(data)),patch.object(build,'SIZE',len(data)),patch.object(build,'IMAGE',build.sha(self.k)),patch.object(build,'get_kernel',return_value=self.k):
            with self.assertRaises(ValueError):build.construct(bad,self.d/'ignored.zip',self.output)
        self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()

class PrivatePackageTests(unittest.TestCase):
    def test_actual_private_package_if_present(self):
        import hashlib, json, zipfile
        paths=[os.environ.get(n) for n in ('S31_PRIVATE_BOOT','S31_PRIVATE_CANDIDATE','S31_PRIVATE_PACKAGE')]
        if not all(paths): self.skipTest('private package not provided')
        old,new,archive=map(Path,paths)
        sys.path.insert(0,str(ROOT/'build-kit/scripts'))
        import package_synthetica31_control_boot as pkg
        self.assertEqual(build.sha(old.read_bytes()),build.REFERENCE)
        self.assertEqual(build.sha(new.read_bytes()),pkg.CANDIDATE)
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip()); self.assertEqual(len(z.namelist()),len(set(z.namelist())))
            self.assertEqual(set(z.namelist()), {pkg.BINARY,'META-INF/com/google/android/updater-script','boot.img','tools/busybox','LICENSE','README-ID.txt','BUILD-INFO.json'})
            self.assertEqual(build.sha(z.read('boot.img')),pkg.CANDIDATE)
            entry=z.read(pkg.BINARY);self.assertEqual(entry.count(build.REFERENCE.encode()),2);self.assertEqual(entry.count(pkg.CANDIDATE.encode()),1)
            self.assertNotIn(b'@REFERENCE@',entry);self.assertNotIn(b'@CANDIDATE@',entry)
            self.assertFalse(json.loads(z.read('BUILD-INFO.json'))['auto_backup'])
            with tempfile.TemporaryDirectory() as tmp:
                binary=Path(tmp)/'update-binary';binary.write_bytes(entry)
                subprocess.run(['busybox','ash','-n',str(binary)],check=True)
