import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'synthetica-project/music-router'
A='{http://schemas.android.com/apk/res/android}'

class RouterSourceTests(unittest.TestCase):
    def test_manifest_is_narrow_nonprivileged_and_matches_preference(self):
        root=ET.parse(SRC/'AndroidManifest.xml').getroot()
        self.assertEqual(root.get('package'),'org.syntenthica.musicrouter')
        self.assertEqual(root.findall('uses-permission'),[])
        self.assertEqual(root.findall('uses-permission-sdk-23'),[])
        self.assertEqual([(x.tag,x.get(A+'name')) for x in root.find('queries')],
                         [('package','com.codetrio.spatialflow')])
        app=root.find('application');self.assertEqual(app.get(A+'allowBackup'),'false')
        self.assertEqual([x.tag for x in app],['activity'])
        activity=app.find('activity');self.assertEqual(activity.get(A+'name'),'.MusicPlayerRouter')
        self.assertEqual(activity.get(A+'exported'),'true')
        filters=activity.findall('intent-filter');self.assertEqual(len(filters),1)
        self.assertEqual([(x.tag,x.get(A+'name')) for x in filters[0]],
                         [('action','android.intent.action.MUSIC_PLAYER'),('category','android.intent.category.DEFAULT')])
        pref=ET.parse(SRC/'preferred-spatialflow-router.xml').getroot()
        self.assertEqual(pref.tag,'preferred-activities');self.assertEqual(len(pref),1)
        self.assertEqual(pref[0].attrib,{'name':'org.syntenthica.musicrouter/.MusicPlayerRouter'})
        self.assertEqual([(x.tag,x.get('name')) for x in pref[0][0]],
                         [('action','android.intent.action.MUSIC_PLAYER'),('cat','android.intent.category.DEFAULT')])

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK unavailable locally')
    def test_actual_java_with_android_stubs(self):
        """Exercise actual router code on synthetic stubs, never Android/device data."""
        stubs={
          'android/os/Bundle.java':'package android.os; public class Bundle {}',
          'android/content/ActivityNotFoundException.java':'package android.content; public class ActivityNotFoundException extends RuntimeException {}',
          'android/content/Intent.java':'''package android.content;
public class Intent { public static final String ACTION_MAIN="android.intent.action.MAIN", CATEGORY_DEFAULT="android.intent.category.DEFAULT";
 public String action,cat,pkg,cls; public Intent(String a){action=a;} public String getAction(){return action;}
 public Intent addCategory(String c){cat=c;return this;} public Intent setClassName(String p,String c){pkg=p;cls=c;return this;} }''',
          'android/app/Activity.java':'''package android.app; import android.content.*; import android.os.Bundle;
public class Activity { public Intent incoming,started; public boolean finished; public int fail;
 protected void onCreate(Bundle b){} public Intent getIntent(){return incoming;}
 public void startActivity(Intent i){if(fail==1)throw new ActivityNotFoundException(); if(fail==2)throw new SecurityException(); started=i;}
 public void finish(){finished=true;} }''',
          'android/widget/Toast.java':'''package android.widget; import android.app.Activity;
public class Toast { public static final int LENGTH_SHORT=0; public static int shown=0;
 public static Toast makeText(Activity a,String s,int n){return new Toast();} public void show(){shown++;} }''',
          'org/syntenthica/musicrouter/RouterHarness.java':'''package org.syntenthica.musicrouter;
import android.content.Intent; import android.widget.Toast;
public class RouterHarness { static void require(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  MusicPlayerRouter r=new MusicPlayerRouter(); r.incoming=new Intent("android.intent.action.MUSIC_PLAYER"); r.onCreate(null);
  require(r.finished&&r.started!=null); require(r.started.action.equals(Intent.ACTION_MAIN));
  require(r.started.cat.equals(Intent.CATEGORY_DEFAULT)); require(r.started.pkg.equals("com.codetrio.spatialflow"));
  require(r.started.cls.equals("com.codetrio.spatialflow.MainActivity"));
  MusicPlayerRouter nullIntent=new MusicPlayerRouter(); nullIntent.onCreate(null); require(nullIntent.finished&&nullIntent.started==null);
  MusicPlayerRouter wrong=new MusicPlayerRouter(); wrong.incoming=new Intent("android.intent.action.VIEW"); wrong.onCreate(null);
  require(wrong.finished&&wrong.started==null);
  for(int n=1;n<=2;n++){MusicPlayerRouter bad=new MusicPlayerRouter();bad.incoming=new Intent("android.intent.action.MUSIC_PLAYER");
    bad.fail=n;bad.onCreate(null);require(bad.finished&&bad.started==null);}
  require(Toast.shown==2); System.out.println("router synthetic host logic OK");
 } }''',
        }
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=[]
            for path,content in stubs.items():
                out=root/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(content);paths.append(str(out))
            paths.append(str(SRC/'src/org/syntenthica/musicrouter/MusicPlayerRouter.java'))
            subprocess.run(['javac','--release','8','-d',str(root/'classes'),*paths],check=True,capture_output=True,timeout=60)
            result=subprocess.run(['java','-cp',str(root/'classes'),'org.syntenthica.musicrouter.RouterHarness'],
                                  check=True,capture_output=True,text=True,timeout=30)
            self.assertIn('synthetic host logic OK',result.stdout)

if __name__=='__main__':unittest.main()
