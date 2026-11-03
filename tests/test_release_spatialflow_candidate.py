import sys
import hashlib
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import release_spatialflow_candidate as r

class ReleaseTests(unittest.TestCase):
    def test_report_must_prove_preservation_and_hold(self):
        for report in ({}, {'schema': 'synthetica-spatialflow-rom-candidate-v1'},
                       {'status': 'HOST_VERIFIED_DEVICE_UNTESTED_HOLD_DO_NOT_FLASH'}):
            with self.assertRaises(r.ReleaseError): r.checked_report(report, Path('unused'))
    def test_release_never_uses_an_arbitrary_tag(self):
        for tag in ('v1', 'synthetica-feature-spatialflow-04-run-x-1', 'other', ''):
            with self.assertRaises(r.ReleaseError): r.create_draft(tag, '0' * 40)
    def test_release_requires_a_real_commit_digest_shape(self):
        with self.assertRaises(r.ReleaseError): r.create_draft('synthetica-feature-spatialflow-04-run-1-1', 'unknown')

    def test_new_draft_is_pinned_to_exact_build_commit(self):
        tag='synthetica-feature-spatialflow-04-run-1-1';commit='1'*40
        def post(args,**kwargs):
            payload=json.loads(kwargs['input'])
            self.assertEqual(payload['target_commitish'],commit)
            self.assertTrue(payload['draft'])
            return subprocess.CompletedProcess(args,0,json.dumps({'id':321,'tag_name':tag,
                'draft':True,'target_commitish':commit,'assets':[]}).encode(),b'')
        with patch.object(r.subprocess,'run',side_effect=post):
            self.assertEqual(r.create_draft(tag,commit),321)
    def test_draft_checks_exact_revision_and_unpublished_status(self):
        tag='synthetica-feature-spatialflow-04-run-1-1';commit='1'*40
        good={'id':321,'tag_name':tag,'draft':True,'target_commitish':commit,'assets':[]}
        with patch.object(r,'api',return_value=good):self.assertEqual(r.draft(321,tag,commit),good)
        for change in ({'target_commitish':r.BRANCH},{'target_commitish':'2'*40},{'draft':False}):
            with self.subTest(change=change),patch.object(r,'api',return_value={**good,**change}),self.assertRaises(r.ReleaseError):
                r.draft(321,tag,commit)
    def test_each_split_upload_is_bound_to_exact_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'rom.zip';source.write_bytes(b'abcdefghij')
            work=root/'transfer';work.mkdir();seen=[];commit='1'*40
            def fake_upload(number,tag,build_commit,path,sha):
                self.assertEqual(build_commit,commit)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha)
                seen.append(path.read_bytes())
            with patch.object(r,'PART_BYTES',4),patch.object(r,'upload',side_effect=fake_upload):
                rows=r.split_and_upload(321,'tag',commit,source,work,10,hashlib.sha256(b'abcdefghij').hexdigest())
            self.assertEqual(seen,[b'abcd',b'efgh',b'ij'])
            self.assertEqual([x['bytes'] for x in rows],[4,4,2]);self.assertEqual(list(work.iterdir()),[])
    def test_redownload_checks_part_hashes_and_commit_on_both_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);data={'rom.zip.001':b'one','rom.zip.002':b'two'};commit='1'*40
            rows=[{'number':n,'name':name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
                  for n,(name,blob) in enumerate(data.items(),1)]
            release={'assets':[{'id':n,'name':row['name'],'size':row['bytes'],'digest':'sha256:'+row['sha256']}
                               for n,row in enumerate(rows,1)]}
            def download(args):
                name=args[args.index('--pattern')+1];(work/name).write_bytes(data[name])
            with patch.object(r,'draft',return_value=release) as draft,patch.object(r.pre,'command',side_effect=download):
                r.redownload(321,'tag',commit,rows,work,hashlib.sha256(b'onetwo').hexdigest())
            self.assertEqual(draft.call_count,2)
            self.assertTrue(all(c.args==(321,'tag',commit) for c in draft.call_args_list))
            self.assertEqual(list(work.iterdir()),[])

    def valid_report(self):
        return {'schema':'synthetica-spatialflow-rom-candidate-v1',
            'status':'HOST_VERIFIED_DEVICE_UNTESTED_HOLD_DO_NOT_FLASH',
            'source':{'sha256':r.pre.SOURCE_SHA256},'apk':{'sha256':r.pre.APP_SHA256},
            'filesystem_audit':{'status':'only_nonprivileged_spatialflow_paths_added','e2fsck_read_only_exit':0},
            'super_comparison':{'all_bytes_outside_metadata_and_product_extents_identical':True,
                                'all_nonproduct_logical_partitions_identical':True},
            'isolated_lpdump':{'status':'ISOLATED_THIRD_PARTY_LPDUMP_AGREES'},
            'package_collision_scan':{'collision_found_in_scanned_roots':False,'apk_manifest_zip_crc_checked':True,
                'apks_checked':50,'independent_xmltree_fallback_count':1,
                'independent_xmltree_fallback_paths':['system:/system/priv-app/Shell/Shell.apk'],
                'tool_sha256':{'aapt_sha256':'a'*64,'aapt2_sha256':'b'*64}},
            'ota_metadata':{'legacy_and_protobuf_values_equal':True},
            'output':{'name':r.builder.OUTPUT_NAME,'bytes':123,'sha256':'f'*64,'signed_by_this_recipe':False}}
    def test_report_requires_manifest_checks_and_distinct_bounded_readers(self):
        output=Path(r.builder.OUTPUT_NAME)
        with patch.object(r.pre,'digest_file',return_value=(123,'f'*64)):
            self.assertEqual(r.checked_report(self.valid_report(),output),(123,'f'*64))
            mutations=[('apk_manifest_zip_crc_checked',False),('apks_checked',0),
                       ('independent_xmltree_fallback_count',2),('independent_xmltree_fallback_paths',None),
                       ('tool_sha256',{'aapt_sha256':'a'*64,'aapt2_sha256':'a'*64})]
            for key,value in mutations:
                with self.subTest(key=key):
                    report=self.valid_report();report['package_collision_scan'][key]=value
                    with self.assertRaises(r.ReleaseError):r.checked_report(report,output)

if __name__ == '__main__': unittest.main()
