import sys
import unittest
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

if __name__ == '__main__': unittest.main()
