import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthetica-project'))
import prepare_axsandbox_vault_quarantine as p


def fixture():
    text='package sample\nclass Example {\n    val untouched = "outside { }"\n'
    for signature in p.REPLACEMENTS:
        text+=signature+'\n        val tricky = "quoted } and ${value}"\n        // } is not the end\n        /* nested { /* } */ } */\n        if (true) { val x = \'{\' }\n    }\n'
    return (text+'    fun unrelated() { println("unchanged") }\n}\n').encode()

def patch(data):return p.prepare(data,expected_sha256=hashlib.sha256(data).hexdigest())

class QuarantineTests(unittest.TestCase):
    def test_quarantine_disables_operations_and_preserves_unrelated_source(self):
        source=fixture();output,report=patch(source)
        self.assertIn(b'val untouched = "outside { }"',output)
        self.assertIn(b'fun unrelated() { println("unchanged") }',output)
        self.assertEqual(report['replaced_method_count'],7);self.assertFalse(report['vault_is_functional'])
        self.assertEqual(report['status'],'SOURCE_QUARANTINE_ONLY_NOT_BUILT_NOT_INSTALLED_HOLD')
        self.assertIn(b'Vault import is disabled in quarantine',output)
        self.assertIn(b'Vault restore is disabled in quarantine',output)
        self.assertNotIn(b'cleanupOriginal(',output);self.assertNotIn(b'dbHelper.deleteFile(entry.id)',output)
    def test_default_identity_rejects_nonpinned_source(self):
        with self.assertRaises(p.QuarantineError):p.prepare(fixture())
    def test_missing_or_duplicate_signatures_fail_closed(self):
        source=fixture();first=next(iter(p.REPLACEMENTS)).encode()
        for data in (source.replace(first,b'    fun renamed() {',1), source+first+b' }\n'):
            with self.subTest(data=data),self.assertRaises(p.QuarantineError):patch(data)
    def test_invalid_or_unclosed_kotlin_fails(self):
        data=fixture().replace(b'val tricky = "quoted } and ${value}"',b'val tricky = "unterminated',1)
        with self.assertRaises(p.QuarantineError):patch(data)
        with self.assertRaises(p.QuarantineError):patch(b'\xff')
    def test_brace_scanner_handles_triple_strings_and_nested_comments(self):
        text='{ val a = """fake } {"""; /* { /* } */ } */ if (true) { x() } } trailing'
        self.assertEqual(text[p._method_end(text,0):], ' trailing')
    def test_source_with_surviving_known_destructive_path_fails(self):
        source=fixture()+b'\nmetadataFile.delete()\n'
        with self.assertRaises(p.QuarantineError):patch(source)
if __name__=='__main__':unittest.main()
