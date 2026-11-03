import importlib.util
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import preflight_spatialflow as p

class SpatialFlowPreflightTests(unittest.TestCase):
    def item(self):
        return {'id': p.APP_ID, 'name': p.APP_NAME, 'size': p.APP_SIZE,
                'digest': 'sha256:' + p.APP_SHA256, 'state': 'uploaded'}
    def expected(self):
        return [(p.APP_ID, p.APP_NAME, p.APP_SIZE, p.APP_SHA256)]
    def test_exact_release_asset_is_accepted(self):
        asset = self.item()
        self.assertEqual(p.asset_snapshot({'draft': False, 'assets': [asset]}, self.expected(), draft=False),
                         tuple(self.expected()))
    def test_wrong_draft_state_is_rejected(self):
        with self.assertRaises(p.PreflightError):
            p.asset_snapshot({'draft': True, 'assets': [self.item()]}, self.expected(), draft=False)
    def test_wrong_size_digest_id_or_state_rejected(self):
        for key, value in (('size', 1), ('digest', 'sha256:' + '0' * 64), ('id', 1), ('state', 'new')):
            asset = self.item(); asset[key] = value
            with self.subTest(key=key), self.assertRaises(p.PreflightError):
                p.asset_snapshot({'draft': False, 'assets': [asset]}, self.expected(), draft=False)
    def test_missing_or_duplicated_asset_rejected(self):
        for assets in ([], [self.item(), self.item()]):
            with self.assertRaises(p.PreflightError):
                p.asset_snapshot({'draft': False, 'assets': assets}, self.expected(), draft=False)
    def test_pinned_part_sizes_sum_to_complete_zip(self):
        self.assertEqual(sum(size for _, size, _ in p.PARTS), p.SOURCE_SIZE)
        self.assertEqual(len({i for i, _, _ in p.PARTS}), 3)
    def test_known_public_testkey_blocks_apk_preflight(self):
        badging="package: name='com.codetrio.spatialflow' versionCode='10' versionName='1.8.2'\nsdkVersion:'25'\ntargetSdkVersion:'36'\nnative-code: 'arm64-v8a'\n"
        signature='Verified using v3 scheme test: true\nSigner #1 certificate SHA-256 digest: '+p.signer_output.AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256+'\n'
        with mock.patch.object(p,'digest_file',return_value=(p.APP_SIZE,p.APP_SHA256)), \
             mock.patch.object(p,'command',side_effect=[badging,'manifest',signature,'']), \
             self.assertRaisesRegex(p.PreflightError,'publicly known AOSP development testkey'):
            p.inspect_apk(Path('/unused.apk'),'aapt','apksigner','zipalign')
    def test_app_does_not_claim_a_signature_trust_anchor(self):
        self.assertEqual(len(p.APP_SHA256), 64)
        self.assertNotEqual(p.APP_SHA256, '0' * 64)

if __name__ == '__main__':
    unittest.main()
