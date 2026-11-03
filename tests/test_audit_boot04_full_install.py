"""Disposable-file controls for the full 04 updater probe; never opens a device."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'))
import audit_boot04_full_install as p


def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()


def fake_tree():
    return {'sha':p.TREE_COMMIT,'truncated':False,'tree':[
        {'type':'blob','path':'README.md','size':1,'sha':'a'*40},
        {'type':'blob','path':'proprietary/system/priv-app/MiuiCamera/MiuiCamera.apk.00',
         'size':3,'sha':'605d07cdc014be5befea4a4a44beadea9bb8adaa'},
        {'type':'blob','path':'proprietary/system/priv-app/MiuiCamera/MiuiCamera.apk.01',
         'size':4,'sha':'c0c55420cfc1183b2d2c48ea4f79d32c230684e0'},
        {'type':'blob','path':'proprietary/system/lib64/libexample.so','size':3,'sha':blob(b'abc')},
    ]}


class Full04Tests(unittest.TestCase):
    def test_camera_tree_combines_only_locked_two_parts(self):
        with mock.patch.multiple(p,TREE_BLOBS=4,TREE_TOTAL=11,CAMERA_BYTES=7,CAMERA_SHA='b'*64):
            rows=p.camera_targets(fake_tree())
            self.assertEqual(len(rows),2)
            self.assertEqual(sum(x['bytes'] for x in rows),10)
            camera=next(x for x in rows if x['path'].endswith('MiuiCamera.apk'))
            self.assertEqual((camera['bytes'],camera['sha256']),(7,'b'*64))
            for key,value in (('truncated',True),('sha','0'*40)):
                tree=fake_tree();tree[key]=value
                with self.assertRaises(p.FullEmulationError):p.camera_targets(tree)
            tree=fake_tree();tree['tree'][1]['sha']='d'*40
            with self.assertRaises(p.FullEmulationError):p.camera_targets(tree)

    def test_capacity_is_optimistic_and_includes_real_deficit(self):
        result=p.hypothetical_camera_capacity(36_904_960)
        self.assertEqual(result['single_tail_bytes'],30_408_704)
        self.assertEqual(result['minimum_deficit_before_overhead_or_reserve_bytes'],60_564_968)
        self.assertTrue(result['apk_exceeds_ceiling'])
        self.assertTrue(result['does_not_include_native_libraries'])
        self.assertFalse(p.hypothetical_camera_capacity(100,20,10)['apk_exceeds_ceiling'])
        with self.assertRaises(p.FullEmulationError):p.hypothetical_camera_capacity(-1)

    def test_fake_target_is_streamed_and_symlink_rejected_even_when_empty(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'target';path.write_bytes(b'')
            self.assertEqual(p.target_state(path,8)['bytes'],0)
            path.write_bytes(b'abc');self.assertEqual(p.target_state(path,8)['sha256'],sha(b'abc'))
            with self.assertRaises(p.FullEmulationError):p.target_state(path,2)
            link=root/'link';link.symlink_to(path)
            with self.assertRaises(p.FullEmulationError):p.target_state(link,8)

    def test_execution_requires_each_exact_length_and_hash(self):
        inputs={'super':b'super','boot':b'boot','dtbo':b'dtbo'}
        specs={k:(len(v),sha(v)) for k,v in inputs.items()}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(p,'PARTS',specs):
            base=Path(d)
            for k,v in inputs.items():(base/k).write_bytes(v)
            result=p.execution_summary(SimpleNamespace(returncode=0,stdout=p.emu.FINISHED_MESSAGE,stderr=''),base)
            self.assertTrue(result['all_outputs_match_locked_04'])
            (base/'boot').write_bytes(b'boox')
            result=p.execution_summary(SimpleNamespace(returncode=0,stdout=p.emu.FINISHED_MESSAGE,stderr=''),base)
            self.assertFalse(result['all_outputs_match_locked_04'])
            self.assertFalse(result['matches_locked_04_members']['boot'])

    def test_system_slice_is_bounded_and_hash_checked(self):
        image=b'prefixSYSTEMsuffix'
        with tempfile.TemporaryDirectory() as d, mock.patch.multiple(p,SYSTEM_START=6,SYSTEM_BYTES=6,SYSTEM_SHA=sha(b'SYSTEM')):
            root=Path(d);source=root/'super';source.write_bytes(image);target=root/'system'
            self.assertEqual(p.copy_system(source,target)['sha256'],sha(b'SYSTEM'))
            self.assertEqual(target.read_bytes(),b'SYSTEM')
            with self.assertRaises(p.FullEmulationError):p.copy_system(source,target)
            source.write_bytes(b'prefixFAIL!!suffix')
            with self.assertRaises(p.FullEmulationError):p.copy_system(source,root/'bad')

    def test_camera_paths_distinguish_same_different_missing_and_symlink(self):
        class Entry:
            def __init__(self,data,kind=1):self.data=data;self.info=SimpleNamespace(meta=SimpleNamespace(flags=1,type=kind,size=len(data)))
            def read_random(self,pos,n):return self.data[pos:pos+n]
        class FS:
            def open(self,path):
                if path.endswith('absent'):raise OSError('not found')
                return {'/same':Entry(b'abc'),'/different':Entry(b'xyz'),'/link':Entry(b'abc',2)}[path]
        targets=[{'path':'/same','bytes':3,'git_blob_sha1':blob(b'abc')},
                 {'path':'/different','bytes':3,'sha256':sha(b'abc')},
                 {'path':'/absent','bytes':3,'sha256':sha(b'abc')},
                 {'path':'/link','bytes':3,'sha256':sha(b'abc')}]
        tsk=SimpleNamespace(TSK_FS_META_FLAG_ALLOC=1,TSK_FS_META_TYPE_REG=1)
        with mock.patch.object(p.vintf,'pytsk3',tsk):r=p.compare_camera_paths(FS(),targets)
        self.assertEqual(r['counts']['same_bytes_by_pinned_digest'],1)
        self.assertEqual(r['counts']['different_existing_file'],1)
        self.assertEqual(r['counts']['not_seen_at_exact_path'],1)
        self.assertEqual(r['counts']['existing_nonregular_or_unallocated'],1)

    def test_full_sandbox_never_probes_image_when_fake_write_fails(self):
        spec={'super':(2,sha(b'aa')),'boot':(2,sha(b'bb')),'dtbo':(2,sha(b'cc'))}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(p,'PARTS',spec):
            root=Path(d);q=root/'qemu';q.write_bytes(b'fake qemu');archive=root/'archive';archive.write_bytes(b'fake')
            def failed(*args,**kwargs):return SimpleNamespace(returncode=1,stdout='error',stderr='')
            with mock.patch.object(p.emu,'_exec_isolated',side_effect=failed), mock.patch.object(p,'system_probe') as probe:
                result=p.run_sandbox(q,b'fake updater',archive,root,{})
                self.assertEqual(result['execution']['exit_code'],1)
                self.assertFalse(result['execution']['all_outputs_match_locked_04']);probe.assert_not_called()
            def success(sandbox,*args,**kwargs):
                base=sandbox/'dev/block/bootdevice/by-name'
                for k,v in {'super':b'aa','boot':b'bb','dtbo':b'cc'}.items():(base/k).write_bytes(v)
                return SimpleNamespace(returncode=0,stdout=p.emu.FINISHED_MESSAGE,stderr='')
            with mock.patch.object(p.emu,'_exec_isolated',side_effect=success) as execute, \
                 mock.patch.object(p,'system_probe',return_value={'synthetic':True}) as probe:
                result=p.run_sandbox(q,b'fake updater',archive,root,{})
                self.assertTrue(result['execution']['all_outputs_match_locked_04']);probe.assert_called_once()
                self.assertGreater(execute.call_args.kwargs['file_size_limit'],8*1024**3)


if __name__=='__main__':unittest.main()
