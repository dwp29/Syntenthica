"""Synthetic reconstruction of reported LP metadata, without image contents.

The known hash checks serialization against the already-inspected layout.
"""
import hashlib
import struct
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'synthetica-project'))
import expand_product_lp as expand


def metadata_prefix():
    lp = expand.lp
    def name(s): return s.encode('ascii').ljust(36, b'\0')
    rows = [('product',7600952,2048), ('system',3384512,7604224),
            ('system_ext',2748624,10989568), ('vendor',2910680,13740032)]
    partitions = b''.join(name(n) + struct.pack('<IIII',0,i,1,1) for i,(n,_,_) in enumerate(rows))
    extents = b''.join(struct.pack('<QIQI',sectors,0,start,0) for _,sectors,start in rows)
    groups = name('default') + struct.pack('<IQ',0,0) + name('qti_dynamic_partitions') + struct.pack('<IQ',0,8589934592)
    device = struct.pack('<QIIQ',2048,1048576,0,8589934592) + name('super') + struct.pack('<I',0)
    tables = partitions + extents + groups + device
    header = bytearray(128)
    struct.pack_into('<IHHI',header,0,lp.HEADER_MAGIC,10,0,128)
    struct.pack_into('<I',header,44,len(tables));header[48:80] = hashlib.sha256(tables).digest()
    cursor=0
    for offset,count,size in ((80,4,52),(92,4,24),(104,2,48),(116,1,64)):
        struct.pack_into('<III',header,offset,cursor,count,size);cursor += count*size
    header[12:44]=hashlib.sha256(header).digest()
    blob = bytes(header) + tables
    if hashlib.sha256(blob).hexdigest() != '2ef44fc572691c89a81a2065a6466b9602a57c10d8d99c258a9e0b15cdc58cf5':
        raise AssertionError('Synthetic metadata does not match reported source metadata hash')
    geo=bytearray(struct.pack('<II',lp.GEOMETRY_MAGIC,52)+b'\0'*32+struct.pack('<III',65536,2,4096))
    geo[8:40]=hashlib.sha256(geo).digest(); prefix=bytearray(4*1024*1024)
    for off in (4096,8192): prefix[off:off+52]=geo
    for off in (12288,77824,143360,208896): prefix[off:off+len(blob)] = blob
    return bytes(prefix)


class LockedLayoutTests(unittest.TestCase):
    def test_product_growth_into_trailing_gap_preserves_other_geometry(self):
        before=metadata_prefix()
        after,plan=expand.build(before,8589934592,32*1024*1024,
            expected_metadata_sha='2ef44fc572691c89a81a2065a6466b9602a57c10d8d99c258a9e0b15cdc58cf5')
        self.assertEqual(plan['product_new_extent']['start'],8525971456)
        self.assertEqual(plan['product_new_extent']['end'],8559525888)
        self.assertEqual(plan['product_bytes_after'],3925241856)
        self.assertEqual(plan['output_metadata_sha256'],'a648fde5f228e6dcd9bbaea50be9662612205a938b214b53f6cc9560c85b49e6')
        self.assertEqual(plan['metadata_slots'],2)
        self.assertEqual(before[plan['metadata_reserved_end']:],after[plan['metadata_reserved_end']:])
        result=expand.lp.inspect_raw_super(after,8589934592)
        self.assertTrue(all(s['copies_match'] for s in result['metadata_slots']))
        self.assertEqual(result['metadata_slots'][0]['primary']['partitions'][0]['extent_count'],2)

if __name__=='__main__': unittest.main()
