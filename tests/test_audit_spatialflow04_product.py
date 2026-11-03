import hashlib
import io
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import audit_spatialflow04_product as p

class Product04Tests(unittest.TestCase):
    def asset(self,aid,name,size,sha):return {'id':aid,'name':name,'size':size,'digest':'sha256:'+sha,'state':'uploaded'}
    def release(self):
        assets=[self.asset(a,p.OUTPUT_NAME+f'.{n:03d}',s,h) for n,(a,s,h) in enumerate(p.PARTS,1)]
        assets += [self.asset(*x) for x in p.AUX]
        return {'id':p.RELEASE_ID,'tag_name':p.TAG,'target_commitish':p.RECIPE_COMMIT,'draft':True,'prerelease':True,'assets':assets}
    def test_only_exact_draft_and_assets_accepted(self):
        r=self.release();self.assertEqual(len(p.release_snapshot(r)),5)
        for field,value in [('draft',False),('prerelease',False),('target_commitish','a'*40),('id',1)]:
            changed={**r,field:value}
            with self.subTest(field=field),self.assertRaises(p.ProductAuditError):p.release_snapshot(changed)
        r=self.release();r['assets'][0]['digest']='sha256:'+'0'*64
        with self.assertRaises((p.ProductAuditError,p.pre.PreflightError)):p.release_snapshot(r)
        r=self.release();r['assets'].append(dict(r['assets'][0]))
        with self.assertRaises(p.ProductAuditError):p.release_snapshot(r)
    def test_reconstruction_checks_each_part_and_combined_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);chunks=[b'ab',b'cd',b'ef'];parts=tuple((n,len(x),hashlib.sha256(x).hexdigest()) for n,x in enumerate(chunks,1))
            def fake_command(args):
                n=int(args[args.index('--pattern')+1][-3:]);(work/args[args.index('--pattern')+1]).write_bytes(chunks[n-1]);return ''
            with mock.patch.object(p,'PARTS',parts),mock.patch.object(p,'ZIP_BYTES',6),\
                 mock.patch.object(p,'ZIP_SHA',hashlib.sha256(b'abcdef').hexdigest()),\
                 mock.patch.object(p,'release_snapshot',return_value=('same',)),mock.patch.object(p.pre,'gh_json',return_value={}),\
                 mock.patch.object(p.pre,'command',side_effect=fake_command):
                out=p.download(work)
            self.assertEqual(out.read_bytes(),b'abcdef');self.assertEqual(len(list(work.iterdir())),1)
    def test_bad_part_deletes_partial_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);parts=((1,2,hashlib.sha256(b'ab').hexdigest()),)
            def bad(args):(work/args[args.index('--pattern')+1]).write_bytes(b'xx')
            with mock.patch.object(p,'PARTS',parts),mock.patch.object(p,'ZIP_BYTES',2),mock.patch.object(p,'ZIP_SHA',hashlib.sha256(b'ab').hexdigest()),\
                 mock.patch.object(p,'release_snapshot',return_value=('same',)),mock.patch.object(p.pre,'gh_json',return_value={}),\
                 mock.patch.object(p.pre,'command',side_effect=bad):
                with self.assertRaises(p.ProductAuditError):p.download(work)
            self.assertFalse((work/p.OUTPUT_NAME).exists())
    def test_two_extent_stream_hashes_whole_source_and_concatenated_product(self):
        data=b'0123456789abcdefghij';windows=((2,6),(12,15));expected=b'2345cde'
        stream=io.BytesIO(data);prefix=stream.read(5);out=io.BytesIO()
        result=p.copy_windows(stream,prefix,out,windows,total_size=len(data),total_sha=hashlib.sha256(data).hexdigest(),
                              product_size=len(expected),product_sha=hashlib.sha256(expected).hexdigest())
        self.assertEqual(out.getvalue(),expected);self.assertEqual(result['product_bytes'],7)
        for bad in (data[:-1],b'X'+data[1:]):
            s=io.BytesIO(bad);prefix=s.read(5)
            with self.assertRaises(p.ProductAuditError):p.copy_windows(s,prefix,io.BytesIO(),windows,total_size=len(data),
                total_sha=hashlib.sha256(data).hexdigest(),product_size=7,product_sha=hashlib.sha256(expected).hexdigest())
    def test_overlapping_unsorted_or_out_of_bounds_windows_rejected(self):
        data=b'0123456789';sha=hashlib.sha256(data).hexdigest()
        for windows in (((2,6),(4,8)),((5,8),(1,3)),((2,20),),((-1,2),)):
            with self.subTest(windows=windows),self.assertRaises(p.ProductAuditError):
                p.copy_windows(io.BytesIO(b''),data,io.BytesIO(),windows,total_size=10,total_sha=sha,product_size=sum(b-a for a,b in windows),product_sha=sha)
    def test_metadata_requires_both_pinned_copies(self):
        extent={'sectors':(p.PRODUCT_WINDOWS[0][1]-p.PRODUCT_WINDOWS[0][0])//512,'type':0,'target_sector':p.PRODUCT_WINDOWS[0][0]//512,'source_index':0}
        primary={'header_and_tables_sha256':p.LP_SHA,'block_devices':[{'name':'super','size_bytes_declared':p.vintf.SUPER_BYTES}],
                 'partitions':[{'name':'product','bytes':p.PRODUCT_BYTES,'extent_count':2,'first_extent':extent}]}
        row={'copies_match':True,'primary':primary};layout={'geometry_copies_match':True,'metadata_slots':[row,row]}
        with mock.patch.object(p.vintf.lp,'inspect_raw_super',return_value=layout):
            self.assertTrue(p.check_product_metadata(b'x',p.vintf.SUPER_BYTES)['geometry_and_slot_copies_match'])
        row2={'copies_match':False,'primary':primary};layout['metadata_slots']=[row,row2]
        with mock.patch.object(p.vintf.lp,'inspect_raw_super',return_value=layout),self.assertRaises(p.ProductAuditError):
            p.check_product_metadata(b'x',p.vintf.SUPER_BYTES)
    @unittest.skipIf(p.vintf.pytsk3 is None,'pytsk3 unavailable')
    def test_fixed_file_must_be_allocated_regular_and_match(self):
        data=b'payload';meta=SimpleNamespace(flags=p.vintf.pytsk3.TSK_FS_META_FLAG_ALLOC,type=p.vintf.pytsk3.TSK_FS_META_TYPE_REG,size=len(data))
        entry=SimpleNamespace(info=SimpleNamespace(meta=meta),read_random=lambda off,n:data[off:off+n]);fs=SimpleNamespace(open=lambda path:entry)
        row=p.inspect_file(fs,'/a.apk',len(data),hashlib.sha256(data).hexdigest());self.assertTrue(row['allocated_regular_file'])
        with self.assertRaises(p.ProductAuditError):p.inspect_file(fs,'/a.apk',len(data),'0'*64)
        meta.flags=0
        with self.assertRaises(p.ProductAuditError):p.inspect_file(fs,'/a.apk',len(data),hashlib.sha256(data).hexdigest())
if __name__=='__main__':unittest.main()
