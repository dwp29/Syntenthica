import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import scan_apk_packages as s

class PackageNameTests(unittest.TestCase):
    def test_valid_aapt_package(self):
        self.assertEqual(s.parse_package("package: name='com.example.music' versionCode='1'\n"), 'com.example.music')
    def test_missing_and_malformed_package_rejected(self):
        for text in ('', "package: name='../malicious' ", "package: name='com' ", "package: name='com..bad' "):
            with self.subTest(text=text), self.assertRaises(s.PackageScanError): s.parse_package(text)

if __name__ == '__main__': unittest.main()
