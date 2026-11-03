import base64
import hashlib
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'synthetica-project'))
import audit_gms_erofs as g

def raw():
    data=b'fake binary manifest';return {'tool_exit_code':0,'root_read_only':True,'no_new_privs':True,'capabilities_dropped':True,
      'tmpfs_bytes_limit':805306368,'tmpfs_inode_limit':12000,'paths_checked':3,'input_sha256':'c'*64,
      'tool_log_bytes':0,'tool_log_sha256':hashlib.sha256(b'').hexdigest(),'symlinks_not_followed':[],
      'apks':[{'path':'/priv-app/Gms/base.apk','bytes':500,'sha256':'a'*64,'manifest_bytes':len(data),
               'manifest_sha256':hashlib.sha256(data).hexdigest(),'manifest_zip_crc_checked':True,
               'manifest_base64':base64.b64encode(data).decode()}]}

class ErofsDecodeTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.scratch=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_valid_metadata_checks_and_redacts_manifest(self):
        with mock.patch.object(g,'_reader_package',return_value='com.google.android.gms'):
            r=g.decode_apks(raw(),'aapt','aapt2',self.scratch)
        self.assertTrue(r['gms_package_found']);self.assertEqual(r['apk_count'],1)
        self.assertNotIn('manifest_base64',r['apks'][0]);self.assertNotIn('manifest_base64',str(r))
        self.assertTrue(r['isolation']['capabilities_dropped'])
    def test_isolation_and_tool_failures_closed(self):
        for field,value in [('tool_exit_code',1),('root_read_only',False),('capabilities_dropped',False),('no_new_privs',False)]:
            record=raw();record[field]=value
            with self.subTest(field=field),self.assertRaises(g.GmsErofsError):g.decode_apks(record,'a','b',self.scratch)
    def test_corrupt_metadata_rejected_before_invoking_reader(self):
        for field,value in [('manifest_sha256','b'*64),('manifest_base64','!!!'),('manifest_zip_crc_checked',False),
                            ('path','relative.apk'),('bytes',0)]:
            record=raw();record['apks'][0][field]=value
            with self.subTest(field=field),mock.patch.object(g,'_reader_package') as reader:
                with self.assertRaises(g.GmsErofsError):g.decode_apks(record,'a','b',self.scratch)
                reader.assert_not_called()
    def test_duplicate_paths_are_rejected(self):
        record=raw();record['apks'].append(dict(record['apks'][0]))
        with mock.patch.object(g,'_reader_package',return_value='com.google.android.gms'),self.assertRaises(g.GmsErofsError):
            g.decode_apks(record,'a','b',self.scratch)
    def test_manifest_only_readers_must_agree_and_clean_up(self):
        with mock.patch.object(g.pre,'command',side_effect=['first','second']),mock.patch.object(g.scan,'parse_xmltree_package',side_effect=['one.pkg','different.pkg']):
            with self.assertRaises(g.GmsErofsError):g._reader_package(b'manifest','a','b',self.scratch)
        self.assertEqual(list(self.scratch.iterdir()),[])
if __name__=='__main__':unittest.main()
