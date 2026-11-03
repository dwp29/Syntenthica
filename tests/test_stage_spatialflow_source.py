import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'));sys.path.insert(0,str(ROOT/'tests'))
import stage_spatialflow_source as p
from test_prepare_spatialflow_music_intent import fixture

WRAPPER=(b'#Fri Jan 30 23:15:34 IST 2026\n'
 b'distributionBase=GRADLE_USER_HOME\n'
 b'distributionPath=wrapper/dists\n'
 b'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip\n'
 b'networkTimeout=10000\nvalidateDistributionUrl=true\n'
 b'zipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n')

def sha(b):return hashlib.sha256(b).hexdigest()

class StageSpatialFlowTests(unittest.TestCase):
    def test_wrapper_pin_is_added_once_and_input_is_verified(self):
        self.assertEqual(sha(WRAPPER),p.WRAPPER_SHA)
        out=p.wrapper_with_checksum(WRAPPER)
        self.assertEqual(out.count(b'distributionSha256Sum='),1)
        self.assertIn(p.GRADLE_SHA.encode(),out)
        for invalid in (WRAPPER+b'changed',out):
            with self.assertRaises(p.StageError):p.wrapper_with_checksum(invalid)
    def test_clean_checkout_stages_only_the_two_expected_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);m=root/'app/src/main/AndroidManifest.xml';w=root/'gradle/wrapper/gradle-wrapper.properties';j=w.with_name('gradle-wrapper.jar')
            m.parent.mkdir(parents=True);w.parent.mkdir(parents=True)
            m.write_bytes(fixture());w.write_bytes(WRAPPER);j.write_bytes(b'jar')
            original_patch=p.patch.patch_manifest
            def patch_synthetic(data):return original_patch(data,expected_sha256=sha(data))
            with mock.patch.object(p,'git_checkout_identity'), \
                 mock.patch.object(p.patch,'SOURCE_SHA256',sha(fixture())), \
                 mock.patch.object(p,'WRAPPER_JAR_SHA',sha(b'jar')), \
                 mock.patch.object(p.patch,'patch_manifest',side_effect=patch_synthetic):
                result=p.stage(root)
            self.assertIn(b'distributionSha256Sum=',w.read_bytes())
            self.assertIn(p.patch.OLD_FILTER.encode(),m.read_bytes())
            self.assertLess(m.read_bytes().find(p.patch.OLD_FILTER.encode()),m.read_bytes().find(p.patch.MAIN_MARKER.encode()))
            self.assertEqual(result['status'],'STAGED_FOR_UNSIGNED_HOST_BUILD_NOT_INSTALLED')
            self.assertEqual(j.read_bytes(),b'jar')
    def test_symlink_or_unknown_file_never_changes_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);target=root/'target';target.write_bytes(b'hello');link=root/'link';link.symlink_to(target)
            with self.assertRaises(p.StageError):p.checked_regular(link,sha(b'hello'))
            with self.assertRaises(p.StageError):p.checked_regular(target,'0'*64)
            self.assertEqual(target.read_bytes(),b'hello')

if __name__=='__main__':unittest.main()
