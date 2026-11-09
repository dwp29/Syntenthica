import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build-kit/scripts'))
import collect_synthetica31_module_pair as pair


class PairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.result = self.root / 'result'
        self.result.mkdir()
        (self.result / 'Image.gz.DO-NOT-FLASH').write_bytes(gzip.compress(
            b'Linux version ' + pair.RELEASE.encode() + b' test'))
        (self.result / 'generated.config.txt').write_text('CONFIG_MODVERSIONS=y\n')
        (self.result / 'module-signing-public-cert.x509').write_bytes(b'public cert')
        (self.result / 'Module.symvers').write_text('dummy')
        self.checks = {'gspca_main': (b'module', {'name': 'gspca_main'})}
        (self.result / 'STATUS.json').write_text(json.dumps(
            {'same_build_modules_static_checks': {'gspca_main': {'name': 'gspca_main'}}}))
        self.output = self.root / 'pair.zip'

    @mock.patch.object(pair.vm, 'collect')
    @mock.patch.object(pair.v3, 'verify_embedded_config')
    def test_packaging_only_checked_public_data_and_no_overwrite(self, embedded, collect):
        collect.return_value = self.checks
        pair.collect(self.root / 'out', self.result, self.output)
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('modules.DO-NOT-INSTALL/gspca_main.ko'), b'module')
            self.assertIn('JANGAN FLASH', z.read('BACA-DULU.txt').decode())
            self.assertFalse(any('private' in x.lower() or x.endswith('.pem') for x in z.namelist()))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            pair.collect(self.root / 'out', self.result, self.output)

    @mock.patch.object(pair.vm, 'collect')
    @mock.patch.object(pair.v3, 'verify_embedded_config')
    def test_rejects_mismatched_status(self, embedded, collect):
        collect.return_value = {'gspca_main': (b'module', {'name': 'wrong'})}
        with self.assertRaisesRegex(ValueError, 'prior build verification differs'):
            pair.collect(self.root / 'out', self.result, self.output)
        self.assertFalse(self.output.exists())

    @mock.patch.object(pair.vm, 'collect')
    def test_rejects_wrong_kernel_release_before_module_check(self, collect):
        (self.result / 'Image.gz.DO-NOT-FLASH').write_bytes(gzip.compress(b'Linux version wrong test'))
        with self.assertRaisesRegex(ValueError, 'kernel release mismatch'):
            pair.collect(self.root / 'out', self.result, self.output)
        collect.assert_not_called()

if __name__ == '__main__':
    unittest.main()
