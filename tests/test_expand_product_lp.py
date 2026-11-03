import hashlib
import struct
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
sys.path.insert(0, str(ROOT / 'tests'))
import expand_product_lp as ex
import test_hyperos4_lp_metadata as fixture


def synthetic(*, group_limit=1_048_576, product_sector=80, system_sector=128, image_bytes=1_048_576):
    lp = ex.lp
    geo = fixture.geometry(max_size=4096, slots=1, block_size=4096)
    name = fixture.name
    partitions = (name('product') + struct.pack('<IIII', 0, 0, 1, 0)
                  + name('system') + struct.pack('<IIII', 0, 1, 1, 0))
    extents = (struct.pack('<QIQI', 16, 0, product_sector, 0)
               + struct.pack('<QIQI', 16, 0, system_sector, 0))
    group = name('main') + struct.pack('<IQ', 0, group_limit)
    device = struct.pack('<QIIQ', 48, 4096, 0, image_bytes) + name('super') + struct.pack('<I', 0)
    tables = partitions + extents + group + device
    header = bytearray(128)
    struct.pack_into('<IHHI', header, 0, lp.HEADER_MAGIC, 10, 0, 128)
    struct.pack_into('<I', header, 44, len(tables)); header[48:80] = hashlib.sha256(tables).digest()
    cursor = 0
    for off, count, size in ((80,2,52),(92,2,24),(104,1,48),(116,1,64)):
        struct.pack_into('<III', header, off, cursor, count, size); cursor += count * size
    header[12:44] = hashlib.sha256(header).digest()
    result = bytearray(24 * 1024)
    for off in (4096, 8192): result[off:off+len(geo)] = geo
    blob = bytes(header) + tables
    for off in (12288, 16384): result[off:off+len(blob)] = blob
    return bytes(result)

class ExpandProductTests(unittest.TestCase):
    def test_adds_only_product_extent_and_preserves_backup_and_other_partitions(self):
        old = synthetic()
        new, plan = ex.build(old, 1_048_576, 64*1024)
        parsed = ex.lp.inspect_raw_super(new, 1_048_576)
        self.assertTrue(parsed['metadata_slots'][0]['copies_match'])
        parts = {x['name']: x for x in parsed['metadata_slots'][0]['primary']['partitions']}
        self.assertEqual(parts['product']['extent_count'], 2)
        self.assertEqual(parts['product']['bytes'], 8192+64*1024)
        self.assertEqual(parts['system']['bytes'], 8192)
        self.assertEqual(parts['system']['first_extent']['target_sector'], 128)
        self.assertEqual(plan['product_new_extent']['source_offset'], 8192)
        self.assertEqual(new[plan['metadata_reserved_end']:], old[plan['metadata_reserved_end']:])
    def test_rejects_corrupt_or_different_metadata_copies(self):
        old = bytearray(synthetic()); old[16384+128] ^= 1
        with self.assertRaises(ex.LPExpandError): ex.build(bytes(old), 1_048_576, 64*1024)
    def test_rejects_wrong_locked_metadata(self):
        with self.assertRaises(ex.LPExpandError): ex.build(synthetic(), 1_048_576, 64*1024, expected_metadata_sha='0'*64)
    def test_rejects_overlapping_partition_extents(self):
        with self.assertRaises(ex.LPExpandError): ex.build(synthetic(system_sector=88), 1_048_576, 64*1024)
    def test_rejects_growth_over_group_limit(self):
        with self.assertRaises(ex.LPExpandError): ex.build(synthetic(group_limit=32*1024), 1_048_576, 64*1024)
    def test_rejects_insufficient_trailing_space(self):
        with self.assertRaises(ex.LPExpandError): ex.build(synthetic(image_bytes=96*1024), 96*1024, 64*1024)
    def test_rejects_nonzero_padding_that_would_be_overwritten(self):
        old = bytearray(synthetic()); parsed=ex.lp.inspect_raw_super(bytes(old), 1_048_576)
        p=parsed['metadata_slots'][0]['primary']; off=12288
        size=struct.unpack_from('<I',old,off+44)[0] + struct.unpack_from('<I',old,off+8)[0]
        old[off+size]=1
        with self.assertRaises(ex.LPExpandError): ex.build(bytes(old), 1_048_576, 64*1024)

if __name__ == '__main__': unittest.main()
