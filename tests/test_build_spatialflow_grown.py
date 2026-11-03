import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'synthetica-project')); sys.path.insert(0, str(ROOT/'tests'))
import build_spatialflow_candidate as b
import expand_product_lp as lp
from test_expand_product_lp import synthetic

class GrownPackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.prefix = synthetic()
        full = bytearray(1_048_576)
        full[:len(self.prefix)] = self.prefix
        full[80*512:96*512] = b'P'*8192
        full[128*512:144*512] = b'S'*8192
        self.old = bytes(full)
        self.old_sha = hashlib.sha256(self.old).hexdigest()
        self.new_prefix, self.plan = lp.build(self.prefix, len(full), 64*1024)
        self.new_prefix = self.new_prefix[:self.plan['metadata_reserved_end']]
        self.product = b'R'*8192 + b'T'*(64*1024)
        self.product_sha = hashlib.sha256(self.product).hexdigest()
        self.prod = self.root/'product.img'; self.prod.write_bytes(self.product)
        self.source, self.output = self.root/'old.zip', self.root/'out.zip'
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('metadata', b'unchanged')
            z.writestr('super.img', self.old)
            z.writestr('boot.img', b'boot')
        with zipfile.ZipFile(self.source) as z: self.infos={i.filename:i for i in z.infolist()}
        self.windows={'product':{'start':80*512,'end':96*512,'bytes':8192,'sha256':hashlib.sha256(b'P'*8192).hexdigest()},
                      'system':{'start':128*512,'end':144*512,'bytes':8192,'sha256':hashlib.sha256(b'S'*8192).hexdigest()}}
    def tearDown(self): self.tmp.cleanup()
    def test_two_extent_growth_and_preservation(self):
        with patch.object(b.pre,'SUPER_SHA256',self.old_sha), patch.object(b.vintf,'SUPER_BYTES',len(self.old)):
            output = b.package_grown(self.source,self.output,self.infos,self.prod,self.plan,self.new_prefix,self.product_sha)
            with zipfile.ZipFile(self.output) as z:
                data=z.read('super.img'); after={i.filename:i for i in z.infolist()}
            self.assertEqual(data[80*512:96*512], b'R'*8192)
            tail=self.plan['product_new_extent']; self.assertEqual(data[tail['start']:tail['end']], b'T'*(64*1024))
            self.assertEqual(data[128*512:144*512], b'S'*8192)
            self.assertEqual(b.compare_compressed_others(self.source,self.output,self.infos,after),2)
            result,prefix=b.compare_grown_supers(self.source,self.output,self.windows,self.plan,self.new_prefix,self.product_sha,output['sha256'])
            self.assertTrue(result['all_bytes_outside_metadata_and_product_extents_identical'])
            self.assertTrue(result['all_nonproduct_logical_partitions_identical'])
            self.assertEqual(prefix,self.new_prefix)
    def test_outside_changed_byte_is_not_whitelisted(self):
        seg=b._segments(self.plan,self.new_prefix)
        a=b'A'*100; pos=128*512
        c=bytearray(a); c[10]=ord('B')
        self.assertFalse(b._outside_identical(a,bytes(c),pos,seg))
        self.assertTrue(b._outside_identical(a,a,pos,seg))
    def test_wrong_product_digest_rejected(self):
        with patch.object(b.pre,'SUPER_SHA256',self.old_sha), patch.object(b.vintf,'SUPER_BYTES',len(self.old)):
            with self.assertRaises(b.FeatureBuildError):
                b.package_grown(self.source,self.output,self.infos,self.prod,self.plan,self.new_prefix,'0'*64)

if __name__=='__main__': unittest.main()
