"""3.1 installer UI and package checks; never executes a real device installer."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_s31_test', ROOT / 'build-kit/scripts/package_synthetica31.py')
package = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(package)
SOURCE20 = ROOT / 'release/Synthetica-2.0.zip'
RESULT = Path(os.environ['S31_RESULT']) if os.environ.get('S31_RESULT') else None
TESTED20 = Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None
BASE30 = Path(os.environ['S31_BASELINE_CONFIG']) if os.environ.get('S31_BASELINE_CONFIG') else None


def original20() -> dict[str, bytes]:
    return package.legacy.read_archive(SOURCE20, package.legacy.SOURCE20_SHA, 21_567_245,
                                       package.legacy.SOURCE20_MEMBERS)


class InstallerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original20()
        cls.entry = package.ui_changes(cls.original['anykernel.sh'], package.ENTRY_UI)
        cls.backend = package.ui_changes(cls.original[package.legacy.BINARY], package.BACKEND_UI)

    def test_logo_progress_and_important_warnings(self):
        lines = package.BANNER.decode('ascii').splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line) <= 52 for line in lines))
        entry = self.entry.decode()
        backend = self.backend.decode()
        for marker in ('[2/3] Installing ksud', '[3/3] Preparing boot', '[3/3] Writing boot',
                       'WARNING: /data locked; ksud skipped.', 'Unlock /data and flash again for ksud.',
                       'WARNING: ksud failed', 'Done. No automatic reboot.', 'sp_progress 0.20', 'sp_progress 0.45',
                       'sp_progress 0.75', 'sp_progress 1.0'):
            self.assertIn(marker, entry)
        self.assertIn('[1/3] Checking device...', backend)
        self.assertIn('show_progress 1.0 0;', backend)
        self.assertIn('if [ -f banner ]; then', backend)
        self.assertNotIn('AnyKernel3 by osm0sis @ xda-developers', backend)
        self.assertNotIn('INSTALLATION LOG:', entry)
        self.assertIn('log_line "result=success"', entry)
        self.assertIn('abort " " "Unsupported device. Aborting...";', backend)

    def test_all_non_presentation_installer_lines_remain_exact(self):
        # The transformations are explicit, bounded to one instance each.
        # Reverse all entry changes to prove that root copy/dump/write logic
        # and every other byte match the boot-reported 2.0 entry.
        restored = self.entry.decode()
        for old, new in reversed(package.ENTRY_UI):
            self.assertTrue(new and restored.count(new) == 1, new)
            restored = restored.replace(new, old, 1)
        self.assertEqual(restored.encode(), self.original['anykernel.sh'])
        backend = self.backend.decode()
        for snippet in ('setup_env;', 'do_devicecheck;', 'do_versioncheck;', 'do_levelcheck;',
                        'do_vendorlevelcheck;', 'ash anykernel.sh;', 'do_modules;',
                        'debugging;', 'restore_env;', 'abort "Unzip failed. Aborting...";'):
            self.assertIn(snippet, backend)
        for file in ('tools/ak3-core.sh', 'ksud', 'tools/busybox', 'tools/magiskboot'):
            self.assertTrue(self.original[file])
        self.assertIn('dump_boot;\nui_print "[3/3] Writing boot...";', self.entry.decode())
        self.assertIn('write_boot;\nsp_progress 1.0;', self.entry.decode())

    @unittest.skipUnless(shutil.which('busybox'), 'BusyBox shell needed')
    def test_logo_passes_through_original_recovery_ui_protocol(self):
        backend = self.backend.decode('utf-8')
        functions = backend[backend.index('ui_print() {'):backend.index('show_progress() {')]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'banner').write_bytes(package.BANNER)
            script = root / 'banner.sh'
            script.write_text('OUTFD=1; BOOTMODE=true;\n' + functions + '\nui_printfile banner\n')
            p = subprocess.run(['busybox', 'ash', str(script)], cwd=root, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            for line in package.BANNER.decode().splitlines():
                self.assertIn('ui_print ' + line, p.stdout)

    @unittest.skipUnless(shutil.which('busybox'), 'BusyBox shell needed')
    def test_device_checks_and_failure_remain_visible(self):
        backend = self.backend.decode('utf-8')
        function = backend.split('do_devicecheck() {\n', 1)[1].split('\nint2ver() {', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'anykernel.sh').write_bytes(self.entry)
            script = root / 'devicecheck.sh'
            script.write_text('''#!/bin/sh
ui_print() { printf '%s\\n' "$@"; }
abort() { ui_print "$@"; exit 7; }
file_getprop() { grep "^$2=" "$1" | tail -n1 | cut -d= -f2-; }
getprop() { [ "$1" = ro.product.device ] && echo "${DEVICE-}"; return 0; }
do_devicecheck() {
''' + function + '''
do_devicecheck
''')
            for device in ('miatoll', 'curtana', 'excalibur', 'gram', 'joyeuse'):
                with self.subTest(device=device):
                    p = subprocess.run(['busybox', 'ash', str(script)], cwd=root,
                                       env=os.environ | {'DEVICE': device}, text=True, capture_output=True)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                    self.assertIn('[1/3] Checking device...', p.stdout)
                    self.assertIn('Device: ' + device, p.stdout)
            p = subprocess.run(['busybox', 'ash', str(script)], cwd=root,
                               env=os.environ | {'DEVICE': 'unknown'}, text=True, capture_output=True)
            self.assertEqual(p.returncode, 7, p.stdout + p.stderr)
            self.assertIn('Unsupported device. Aborting...', p.stdout)

    def test_ui_transform_rejects_changed_source(self):
        with self.assertRaisesRegex(ValueError, 'expected one'):
            package.ui_changes(self.original['anykernel.sh'] + b'\nSP_VERSION="2.0"\n', package.ENTRY_UI)
        with self.assertRaisesRegex(ValueError, 'expected one'):
            package.ui_changes(self.original[package.legacy.BINARY].replace(b'unzip -o "$ZIPFILE";', b''),
                               package.BACKEND_UI)


@unittest.skipUnless(RESULT is not None and TESTED20 is not None and BASE30 is not None,
                     'verified 3.1 build evidence and pinned configs required')
class ActualPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_package_has_new_kernel_and_actual_2_0_core_and_ksud(self):
        assert RESULT and TESTED20 and BASE30
        files = package.collect(RESULT, TESTED20, BASE30, SOURCE20)
        source = original20()
        metadata = json.loads(files['BUILD-INFO.txt'])
        self.assertEqual(metadata['kernel_release'], package.build.RELEASE)
        self.assertEqual(metadata['physical_boot_test_this_3_1_image'], 'NOT RUN')
        self.assertEqual(files['Image.gz'], (RESULT / 'Image.gz.DO-NOT-FLASH').read_bytes())
        self.assertNotEqual(package.sha(files['Image.gz']), package.build.BASE30_IMAGE_SHA256)
        self.assertEqual(files['tools/ak3-core.sh'], source['tools/ak3-core.sh'])
        self.assertEqual(files['ksud'], source['ksud'])
        self.assertEqual(files['tools/busybox'], source['tools/busybox'])
        self.assertEqual(files['tools/magiskboot'], source['tools/magiskboot'])
        self.assertFalse(any(name.endswith('.ko') or name in ('dtb','dtb.img','dtbo','dtbo.img') for name in files))
        self.assertIn(b'belum diuji secara', files['README-FLASH.txt'])

    def test_deterministic_zip_and_reject_overwrite(self):
        assert RESULT and TESTED20 and BASE30
        one, two = self.root / 'one.zip', self.root / 'two.zip'
        info = package.package(RESULT, TESTED20, BASE30, SOURCE20, one)
        again = package.package(RESULT, TESTED20, BASE30, SOURCE20, two)
        self.assertEqual(info['sha256'], again['sha256'])
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with zipfile.ZipFile(one) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()), package.legacy.SOURCE20_MEMBERS | {'banner'})
            self.assertEqual(z.read('banner'), package.BANNER)
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in z.infolist()))
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            package.package(RESULT, TESTED20, BASE30, SOURCE20, one)

    def test_corrupted_build_evidence_rejected(self):
        assert RESULT and TESTED20 and BASE30
        with mock.patch.object(package.build, 'BASE30_IMAGE_SHA256', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'evidence mismatch'):
                package.collect(RESULT, TESTED20, BASE30, SOURCE20)


if __name__ == '__main__':
    unittest.main()
