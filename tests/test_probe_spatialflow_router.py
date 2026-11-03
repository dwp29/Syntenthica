import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'synthetica-project'))
import probe_spatialflow_router as p

SOURCE=ROOT/'synthetica-project/music-router'

def xml(package,activity,action,categories,exported='true',extra=''):
    cats=''.join('          E: category (line=7)\n            A: android:name(0x01010003)="'+x+'"\n' for x in categories)
    return f'''N: android=http://schemas.android.com/apk/res/android
  E: manifest (line=1)
    A: package="{package}"
{extra}    E: application (line=2)
      E: activity (line=3)
        A: android:name(0x01010003)="{activity}"
        A: android:exported(0x01010010)={exported}
        E: intent-filter (line=4)
          E: action (line=5)
            A: android:name(0x01010003)="{action}"
'''+cats

def two(s):return (s,s.replace('A: android:','A: http://schemas.android.com/apk/res/android:'))

class RouterProbeTests(unittest.TestCase):
    def test_source_prototype_and_reject_added_permission(self):
        m=(SOURCE/'AndroidManifest.xml').read_bytes();pref=(SOURCE/'preferred-spatialflow-router.xml').read_bytes()
        self.assertEqual(p.source_prototype(m,pref)['component'],p.ROUTER_ACTIVITY)
        for bad_m,bad_p in ((m.replace(b'<queries>',b'<uses-permission android:name="android.permission.INTERNET"/><queries>'),pref),
                            (m,pref.replace(b'android.intent.action.MUSIC_PLAYER',b'android.intent.action.VIEW'))):
            with self.assertRaises(p.RouterError):p.source_prototype(bad_m,bad_p)
    def test_two_readers_match_route_and_upstream_main(self):
        router=xml(p.ROUTER_PACKAGE,'.MusicPlayerRouter',p.MUSIC,[p.DEFAULT])
        upstream=xml(p.pre.APP_PACKAGE,'.MainActivity',p.MAIN,[p.DEFAULT,'android.intent.category.BROWSABLE'])
        self.assertTrue(p.compare_activities(*two(router),p.ROUTER_PACKAGE,p.ROUTER_ACTIVITY,p.MUSIC,router=True)['exported'])
        self.assertEqual(p.compare_activities(*two(upstream),p.pre.APP_PACKAGE,p.UPSTREAM_ACTIVITY,p.MAIN,router=False)['component'],p.UPSTREAM_ACTIVITY)
    def test_reject_unexported_extra_permission_missing_default_and_reader_disagreement(self):
        base=xml(p.ROUTER_PACKAGE,'.MusicPlayerRouter',p.MUSIC,[p.DEFAULT])
        cases=[xml(p.ROUTER_PACKAGE,'.MusicPlayerRouter',p.MUSIC,[p.DEFAULT],exported='false'),
               xml(p.ROUTER_PACKAGE,'.MusicPlayerRouter',p.MUSIC,[]),
               xml(p.ROUTER_PACKAGE,'.MusicPlayerRouter',p.MUSIC,[p.DEFAULT],extra='    E: uses-permission (line=1)\n')]
        for bad in cases:
            with self.subTest(bad=bad),self.assertRaises(p.RouterError):
                p.compare_activities(*two(bad),p.ROUTER_PACKAGE,p.ROUTER_ACTIVITY,p.MUSIC,router=True)
        with self.assertRaises(p.RouterError):
            p.compare_activities(base,base.replace('exported(0x01010010)=true','exported(0x01010010)=false'),p.ROUTER_PACKAGE,p.ROUTER_ACTIVITY,p.MUSIC,router=True)

if __name__=='__main__':unittest.main()
