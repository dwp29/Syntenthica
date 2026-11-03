import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import probe_spatialflow_intent as p

XML='''N: android=http://schemas.android.com/apk/res/android
  E: manifest (line=2)
    A: package="com.codetrio.spatialflow" (Raw: "com.codetrio.spatialflow")
    E: application (line=20)
      E: activity (line=30)
        A: android:name(0x01010003)=".MainActivity" (Raw: ".MainActivity")
        A: android:exported(0x01010010)=(type 0x12)0xffffffff
        E: intent-filter (line=33)
          E: action (line=34)
            A: android:name(0x01010003)="android.intent.action.MAIN" (Raw: "android.intent.action.MAIN")
      E: activity (line=50)
        A: android:name(0x01010003)=".ui.ExternalPlayerActivity" (Raw: ".ui.ExternalPlayerActivity")
        A: android:exported(0x01010010)=(type 0x12)0xffffffff
        E: intent-filter (line=51)
          E: action (line=52)
            A: android:name(0x01010003)="android.intent.action.MUSIC_PLAYER" (Raw: "android.intent.action.MUSIC_PLAYER")
          E: category (line=53)
            A: android:name(0x01010003)="android.intent.category.DEFAULT" (Raw: "android.intent.category.DEFAULT")
'''
class IntentProbeTests(unittest.TestCase):
    def test_detects_exact_activity_exported_and_filter(self):
        rows=p.parse_tree(XML);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['component'],'com.codetrio.spatialflow.ui.ExternalPlayerActivity')
        self.assertTrue(rows[0]['exported']);self.assertEqual(rows[0]['categories'],['android.intent.category.DEFAULT'])
    def test_readers_must_agree(self):
        self.assertEqual(p.compare_readers(XML,XML),p.parse_tree(XML))
        with self.assertRaises(p.IntentProbeError):p.compare_readers(XML,XML.replace('.ui.ExternalPlayerActivity','.MainActivity2'))
    def test_wrong_root_and_duplicate_attribute_rejected(self):
        with self.assertRaises(Exception):p.parse_tree(XML.replace('com.codetrio.spatialflow','com.example.other'))
        with self.assertRaises(p.IntentProbeError):p.parse_tree(XML.replace('A: android:exported(0x01010010)=(type 0x12)0xffffffff', 'A: android:exported(0x01010010)=(type 0x12)0xffffffff\n        A: android:exported(0x01010010)=(type 0x12)0x0',1))
    def test_missing_action_is_distinct_from_bad_parser(self):
        self.assertEqual(p.parse_tree(XML.replace('android.intent.action.MUSIC_PLAYER','android.intent.action.VIEW')),[])
    def test_unexported_and_data_constraints(self):
        text=XML.replace('(type 0x12)0xffffffff','(type 0x12)0x0').replace('          E: category (line=53)',
              '          E: data (line=53)\n            A: android:mimeType(0x01010026)="audio/*"\n          E: category (line=53)')
        row=p.parse_tree(text)[0];self.assertFalse(row['exported']);self.assertEqual(row['data'],[{'android:mimeType':'audio/*'}])
if __name__=='__main__':unittest.main()
