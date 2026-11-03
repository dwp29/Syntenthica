import hashlib
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'synthetica-project'))
import prepare_spatialflow_music_intent as p


def fixture():
    return ('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application>
        <activity android:name=".MainActivity" android:exported="true">
'''+p.MAIN_MARKER+'''            <intent-filter><action android:name="android.intent.action.MAIN" /></intent-filter>
        </activity>
        <activity android:name=".ui.ExternalPlayerActivity" android:exported="true">
            <intent-filter><action android:name="android.intent.action.VIEW" /><data android:mimeType="audio/*" /></intent-filter>
'''+p.OLD_FILTER+'''        </activity>
    </application>
</manifest>
''').encode()

def patch(data): return p.patch_manifest(data,expected_sha256=hashlib.sha256(data).hexdigest())

class MusicIntentPatchTests(unittest.TestCase):
    def test_moves_only_music_action_and_preserves_view(self):
        src=fixture(); result,report=patch(src)
        self.assertEqual(result.count(p.OLD_FILTER.encode()),1)
        self.assertLess(result.find(p.OLD_FILTER.encode()),result.find(p.MAIN_MARKER.encode()))
        self.assertIn(b'android.intent.action.VIEW',result)
        self.assertIn(b'android:mimeType="audio/*"',result)
        self.assertTrue(report['other_manifest_nodes_identical'])
        self.assertEqual(report['status'],'SOURCE_PATCH_ONLY_NOT_BUILT_NOT_SIGNED_NOT_INSTALLED')
    def test_unpinned_source_fails_closed(self):
        with self.assertRaises(p.PatchError): p.patch_manifest(fixture())
    def test_duplicate_music_filter_fails_closed(self):
        src=fixture().replace(p.OLD_FILTER.encode(),(p.OLD_FILTER*2).encode())
        with self.assertRaises(p.PatchError): patch(src)
    def test_unexported_main_activity_fails_closed(self):
        src=fixture().replace(b'android:name=".MainActivity" android:exported="true"',b'android:name=".MainActivity" android:exported="false"')
        with self.assertRaises(p.PatchError): patch(src)
    def test_unexpected_category_fails_closed(self):
        src=fixture().replace(b'android.intent.category.DEFAULT',b'android.intent.category.LAUNCHER')
        with self.assertRaises(p.PatchError): patch(src)
    def test_already_patched_or_missing_filter_fails_closed(self):
        src=fixture().replace(p.OLD_FILTER.encode(),b'')
        with self.assertRaises(p.PatchError): patch(src)

if __name__=='__main__': unittest.main()
