import hashlib
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'));sys.path.insert(0,str(ROOT/'tests'))
import prepare_spatialflow_music_intent as patch
import prepare_spatialflow_preference as preference
from test_prepare_spatialflow_music_intent import fixture

def patched():
    src=fixture();return patch.patch_manifest(src,expected_sha256=hashlib.sha256(src).hexdigest())[0]
def prepare(data):return preference.prepare(data,expected_sha256=hashlib.sha256(data).hexdigest())

class PreferredPrototypeTests(unittest.TestCase):
    def test_exact_prototype_for_patched_route(self):
        out,report=prepare(patched());root=ET.fromstring(out)
        self.assertEqual(root.tag,'preferred-activities');self.assertEqual(len(root),1)
        self.assertEqual(root[0].attrib,{'name':preference.COMPONENT})
        self.assertEqual([(x.tag,x.get('name')) for x in root[0][0]],
                         [('action',patch.ACTION),('cat',patch.CATEGORY)])
        self.assertEqual(report['status'],'SOURCE_PROTOTYPE_HOLD_NOT_IN_ROM_NOT_A_DEVICE_TEST')
    def test_unpatched_release_source_rejected(self):
        with self.assertRaises(preference.PreferenceError):prepare(fixture())
    def test_default_cli_identity_rejects_unpinned_data(self):
        with self.assertRaises(preference.PreferenceError):preference.prepare(patched())
    def test_unexported_and_constrained_filters_rejected(self):
        data=patched()
        for mutated in (data.replace(b'android:name=".MainActivity" android:exported="true"',b'android:name=".MainActivity" android:exported="false"'),
                        data.replace(patch.OLD_FILTER.encode(),patch.OLD_FILTER.replace('</intent-filter>','<data android:scheme="file" /></intent-filter>').encode())):
            with self.subTest(mutated=mutated),self.assertRaises(preference.PreferenceError):prepare(mutated)
if __name__=='__main__':unittest.main()
