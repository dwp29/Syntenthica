import sys
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
