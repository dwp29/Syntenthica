import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import build_spatialflow_candidate as b

class SpatialFlowBuildTests(unittest.TestCase):
    def test_free_space_preserves_reserved_blocks_and_safety_margin(self):
        data = {'free_blocks': 20_000, 'reserved_blocks': 1000, 'free_inodes': 10, 'block_size': 4096}
        b.validate_space(data, 1_000_000)
        for item in ({**data, 'free_inodes': 1}, {**data, 'free_blocks': 1500}):
            with self.assertRaises(b.FeatureBuildError): b.validate_space(item, 1_000_000)
    def test_packaging_preserves_other_members_and_super_outside_product(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, output, replacement = root/'old.zip', root/'new.zip', root/'product.img'
            original = b'a' * 4096 + b'b' * 4096 + b'c' * 4096
            new_part = b'Z' * 4096
            replacement.write_bytes(new_part)
            with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('metadata', b'first')
                z.writestr('super.img', original)
                z.writestr('boot.img', b'boot was not changed')
            with zipfile.ZipFile(source) as z:
                before = {i.filename:i for i in z.infolist()}
            old_sha = hashlib.sha256(original).hexdigest()
            new_part_sha = hashlib.sha256(new_part).hexdigest()
            extent = {'start': 4096, 'end': 8192, 'bytes': 4096}
            windows = {'system': {'start': 0, 'end': 4096, 'bytes': 4096, 'sha256': hashlib.sha256(b'a'*4096).hexdigest()},
                       'product': {**extent, 'sha256': hashlib.sha256(b'b'*4096).hexdigest()},
                       'vendor': {'start': 8192, 'end': 12288, 'bytes': 4096, 'sha256': hashlib.sha256(b'c'*4096).hexdigest()}}
            with patch.object(b.pre, 'SUPER_SHA256', old_sha), patch.object(b.vintf, 'SUPER_BYTES', len(original)):
                result = b.package(source, output, before, replacement, extent, new_part_sha)
                with zipfile.ZipFile(output) as z:
                    after = {i.filename:i for i in z.infolist()}
                    self.assertEqual(z.read('super.img'), b'a'*4096 + new_part + b'c'*4096)
                    self.assertEqual(z.read('boot.img'), b'boot was not changed')
                self.assertEqual(b.compare_compressed_others(source, output, before, after), 2)
                report = b.compare_supers(source, output, windows, new_part_sha, result['sha256'])
                self.assertTrue(report['all_bytes_outside_product_identical'])
                self.assertEqual(len(report['partitions']), 3)
    def test_packaging_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'exists'; p.write_bytes(b'keep')
            with self.assertRaises(b.FeatureBuildError):
                b.package(Path(d)/'source', p, {}, Path(d)/'replacement', {}, '0'*64)
            self.assertEqual(p.read_bytes(), b'keep')

if __name__ == '__main__': unittest.main()
