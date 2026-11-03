import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'))
import inventory_baseline_packages as inv

class BaselineInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.work=Path(self.tmp.name)
        self.source_data=b'synthetic source'; self.source_sha=hashlib.sha256(self.source_data).hexdigest()
    def tearDown(self): self.tmp.cleanup()
    def download(self,work):
        path=work/'candidate.zip';path.write_bytes(self.source_data);return path
    def extract(self,source,work,lock):
        result={}
        for name in ('system','system_ext','product'):
            p=work/(name+'.img');data=name.encode();p.write_bytes(data)
            result[name]={'path':p,'window':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}
        return result
    def test_static_inventory_checks_each_input_before_and_after(self):
        def inspect(images,aapt,scratch,forbidden,**kwargs):
            self.assertEqual(set(images),{'system','system_ext','product'})
            self.assertIn('com.android.vending',kwargs['watch_packages'])
            return {'watched_package_paths':{'com.android.vending':[]}}
        with patch.object(inv.pre,'download_candidate',side_effect=self.download), \
             patch.object(inv.pre,'extract_extents',side_effect=self.extract), \
             patch.object(inv.pre,'SOURCE_SIZE',len(self.source_data)), \
             patch.object(inv.pre,'SOURCE_SHA256',self.source_sha), \
             patch.object(inv.scan,'scan',side_effect=inspect):
            report=inv.run(self.work,'aapt','aapt2')
        self.assertTrue(report['all_extracted_input_extents_unchanged'])
        self.assertEqual(report['status'],'READ_ONLY_INVENTORY_NOT_A_DEVICE_TEST_HOLD')
    def test_partition_mutation_fails_closed(self):
        def mutate(images,*args,**kwargs):
            images['system'].write_bytes(b'tampered');return {}
        with patch.object(inv.pre,'download_candidate',side_effect=self.download), \
             patch.object(inv.pre,'extract_extents',side_effect=self.extract), \
             patch.object(inv.scan,'scan',side_effect=mutate), \
             self.assertRaises(inv.InventoryError):
            inv.run(self.work,'aapt','aapt2')
    def test_nonempty_work_rejected_before_download(self):
        (self.work/'keep').write_text('untouched')
        with patch.object(inv.pre,'download_candidate') as call, self.assertRaises(inv.InventoryError):
            inv.run(self.work,'aapt','aapt2')
        call.assert_not_called()

if __name__=='__main__':unittest.main()
