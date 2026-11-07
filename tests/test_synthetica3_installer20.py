"""Reproducible packaging and device check for the 3.0/2.0 hybrid ZIP.

No test executes an installer against a device or partition. Set
S3_INSTALLER20_SOURCE30 to the pinned original ZIP to test real inputs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer20', ROOT / 'build-kit/scripts/package_synthetica3_installer20.py')
pack = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pack)
SOURCE20 = ROOT / 'release/Synthetica-2.0.zip'
SOURCE30 = Path(os.environ['S3_INSTALLER20_SOURCE30']) if os.environ.get('S3_INSTALLER20_SOURCE30') else None


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def original20() -> dict[str, bytes]:
    return pack.read_archive(SOURCE20, pack.SOURCE20_SHA, 21_567_245, pack.SOURCE20_MEMBERS)


class DeviceCheckTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('busybox'), 'BusyBox ash is required')
    def test_2_0_backend_checks_each_property_without_excluding_unified_miatoll(self):
        two = original20()
        backend = two[pack.BINARY].decode('utf-8')
        function = backend.split('do_devicecheck() {\n', 1)[1].split('\nint2ver() {', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'anykernel.sh').write_bytes(two['anykernel.sh'])
            runner = root / 'devicecheck.sh'
            runner.write_text('''#!/bin/sh
ui_print() { :; }
abort() { echo rejected; exit 7; }
file_getprop() { grep "^$2=" "$1" | tail -n1 | cut -d= -f2-; }
getprop() {
  case "$1" in
    ro.product.device) echo "${DEVICE-}";;
    ro.build.product) echo "${PRODUCT-}";;
    ro.product.vendor.device) echo "${VENDOR-}";;
    ro.vendor.product.device) echo "${VENDOR_PRODUCT-}";;
  esac
}
do_devicecheck() {
''' + function + '''
do_devicecheck
echo accepted
''')
            env = os.environ.copy()
            for key in ('DEVICE', 'PRODUCT', 'VENDOR', 'VENDOR_PRODUCT'):
                env.pop(key, None)
            for value in ('miatoll', 'curtana', 'excalibur', 'gram', 'joyeuse'):
                for key in ('DEVICE', 'PRODUCT', 'VENDOR', 'VENDOR_PRODUCT'):
                    with self.subTest(value=value, prop=key):
                        p = subprocess.run(['busybox', 'ash', str(runner)], cwd=root,
                                           env=env | {key: value}, text=True, capture_output=True)
                        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                        self.assertIn('accepted', p.stdout)
            for value in ('unknown', 'miatoll-other', ''):
                with self.subTest(rejected=value):
                    p = subprocess.run(['busybox', 'ash', str(runner)], cwd=root,
                                       env=env | {'DEVICE': value}, text=True, capture_output=True)
                    self.assertEqual(p.returncode, 7, p.stdout + p.stderr)
                    self.assertIn('rejected', p.stdout)


@unittest.skipUnless(SOURCE30 is not None, 'set S3_INSTALLER20_SOURCE30 to exact original 3.0 ZIP')
class HybridPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source20 = original20()
        assert SOURCE30 is not None
        self.source30 = pack.read_archive(SOURCE30, pack.SOURCE30_SHA, 15_719_303, pack.SOURCE30_MEMBERS)

    def test_only_kernel_identity_and_docs_change_from_2_0(self):
        files = pack.assemble(SOURCE20, SOURCE30)
        self.assertEqual(set(files), set(self.source20))
        self.assertEqual(files['Image.gz'], self.source30['Image.gz'])
        self.assertEqual(hash_bytes(files['Image.gz']), pack.IMAGE30_SHA)
        self.assertEqual(hash_bytes(files['ksud']), pack.KSUD_SHA)
        changed = {'Image.gz', 'anykernel.sh', 'BUILD-INFO.txt', 'README-FLASH.txt'}
        for name in set(files) - changed:
            with self.subTest(member=name):
                self.assertEqual(files[name], self.source20[name])
        expected_entry = self.source20['anykernel.sh'].replace(
            b'SP_VERSION="2.0"', f'SP_VERSION="{pack.VERSION}"'.encode(), 1).replace(
            b'SP_UNAME="4.14.357-openela-Synthetica-2.0"', f'SP_UNAME="{pack.UNAME}"'.encode(), 1)
        self.assertEqual(files['anykernel.sh'], expected_entry)
        self.assertNotIn(b'tools/prepare-boot.sh', files['anykernel.sh'])
        self.assertFalse(any(name.endswith('.ko') or name in ('dtb', 'dtb.img', 'dtbo', 'dtbo.img') for name in files))
        metadata = json.loads(files['BUILD-INFO.txt'])
        self.assertFalse(metadata['kernel_rebuilt_for_this_package'])
        self.assertEqual(metadata['physical_recovery_or_boot_test_of_this_package'], 'NOT RUN')
        self.assertEqual(metadata['kernel_image_sha256'], pack.IMAGE30_SHA)
        self.assertIn(b'/data/adb/ksud', files['README-FLASH.txt'])
        self.assertIn(b'TIDAK membuat', files['README-FLASH.txt'])

    def test_reproducible_zip_and_executable_modes(self):
        one, two = self.root / 'one.zip', self.root / 'two.zip'
        a = pack.package(SOURCE20, SOURCE30, one)
        b = pack.package(SOURCE20, SOURCE30, two)
        self.assertEqual(a['sha256'], b['sha256'])
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with zipfile.ZipFile(one) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(frozenset(z.namelist()), pack.SOURCE20_MEMBERS)
            for name in z.namelist():
                executable = name in (pack.BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                self.assertEqual(z.getinfo(name).external_attr >> 16,
                                 0o100755 if executable else 0o100644, name)

    def test_tampered_and_symlinked_inputs_are_rejected_without_output(self):
        original = SOURCE30.read_bytes()
        for name, data in (('truncated', original[:-1]),
                           ('changed', original[:100] + bytes([original[100] ^ 1]) + original[101:])):
            bad, output = self.root / name, self.root / (name + '.zip')
            bad.write_bytes(data)
            with self.assertRaises(ValueError):
                pack.package(SOURCE20, bad, output)
            self.assertFalse(output.exists())
        symlink = self.root / 'link.zip'
        symlink.symlink_to(SOURCE30.resolve())
        with self.assertRaises(ValueError):
            pack.package(SOURCE20, symlink, self.root / 'symlink-output.zip')
        self.assertFalse((self.root / 'symlink-output.zip').exists())

    def test_existing_output_is_not_overwritten(self):
        output = self.root / 'exists.zip'
        output.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            pack.package(SOURCE20, SOURCE30, output)
        self.assertEqual(output.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
