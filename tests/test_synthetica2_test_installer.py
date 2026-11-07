"""Host checks for experimental installer packaging and fail-closed preflight.

Real MagiskBoot repacking is tested separately with ARM/QEMU and synthetic images.
These tests never access an actual device or block partition.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer'
SPEC = importlib.util.spec_from_file_location('s2test_package', ROOT / 'build-kit/scripts/package_synthetica2_test.py')
pkg = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pkg)


class InstallerShellTests(unittest.TestCase):
    def test_scripts_parse_in_both_shells(self):
        for script in ('anykernel.sh', 'prepare-boot.sh'):
            for cmd in (['sh', '-n'], ['busybox', 'ash', '-n']):
                with self.subTest(script=script, command=cmd):
                    subprocess.run([*cmd, str(SCRIPTS / script)], check=True)

    def invoke_installer(self, values):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            bindir = home / 'bin'
            bindir.mkdir()
            fake = bindir / 'getprop'
            fake.write_text('#!/bin/sh\ncase "$1" in\n' + ''.join(
                f'  {key}) printf "%s\\n" "{value}";;\n' for key, value in values.items()
            ) + 'esac\n')
            fake.chmod(0o755)
            env = os.environ | {'AKHOME': str(home), 'OUTFD': '1', 'PATH': str(bindir) + ':' + os.environ['PATH']}
            return subprocess.run(['busybox', 'ash', str(SCRIPTS / 'anykernel.sh')],
                                  env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_installer_aborts_before_accessing_block_for_ab_slot(self):
        p = self.invoke_installer({'ro.boot.slot_suffix': '_a', 'ro.boot.flash.locked': '0'})
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('A/B slot detected', p.stdout)
        self.assertNotIn('Writing boot partition', p.stdout)

    def test_installer_aborts_if_locked_or_unknown(self):
        for props, message in (({'ro.boot.flash.locked': '1'}, 'Bootloader reports locked'),
                               ({'ro.boot.vbmeta.device_state': 'locked', 'ro.boot.verifiedbootstate': 'orange'}, 'Bootloader reports locked'),
                               ({}, 'Cannot confirm unlocked bootloader')):
            with self.subTest(properties=props):
                p = self.invoke_installer(props)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(message, p.stdout)
                self.assertNotIn('Writing boot partition', p.stdout)

    def test_unlocked_but_missing_expected_block_fails(self):
        p = self.invoke_installer({'ro.boot.verifiedbootstate': 'orange'})
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Expected boot block device does not exist', p.stdout)
        self.assertNotIn('Writing boot partition', p.stdout)

    def test_writer_is_explicitly_limited_to_boot(self):
        text = (SCRIPTS / 'anykernel.sh').read_text()
        self.assertIn('BLOCK=/dev/block/bootdevice/by-name/boot', text)
        self.assertIn('of="$BLOCK"', text)
        self.assertIn('conv=fsync', text)
        self.assertIn('cmp -s -n "$partsize" "$candidate" "$BLOCK"', text)
        self.assertIn('do.modules=0', text)
        self.assertIn('do.systemless=0', text)
        self.assertNotIn('/data/adb/ksud', text)
        self.assertNotIn('PATCHVBMETAFLAG=true', text)
        prep = (SCRIPTS / 'prepare-boot.sh').read_text()
        self.assertIn('PATCHVBMETAFLAG=false', prep)
        self.assertNotIn('/dev/block', prep)


class PackageTests(unittest.TestCase):
    def setUp(self):
        value = os.environ.get('S2_EVIDENCE')
        if not value:
            self.skipTest('set S2_EVIDENCE to run compile-evidence packaging tests')
        self.evidence = Path(value)
        if not self.evidence.is_file():
            self.fail('S2_EVIDENCE does not exist')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_package_is_reproducible_and_has_the_expected_payload(self):
        a, b = self.work / 'a.zip', self.work / 'b.zip'
        pkg.package(self.evidence, a)
        pkg.package(self.evidence, b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with zipfile.ZipFile(a) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()), set(pkg.BASE_FILES) | {
                'Image.gz', 'anykernel.sh', 'tools/prepare-boot.sh', 'README-FLASH.txt', 'BUILD-INFO.json'})
            self.assertEqual(pkg.sha(z.read('Image.gz')), pkg.IMAGE_SHA256)
            meta = json.loads(z.read('BUILD-INFO.json'))
            self.assertEqual(meta['kind'], 'EXPERIMENTAL_RECOVERY_INSTALLER_NOT_DEVICE_TESTED')
            self.assertFalse(meta['auto_backup'])
            self.assertIn('NOT VERIFIED', meta['rom_module_abi_and_signatures'])
            self.assertNotIn('ksud', z.namelist())
            self.assertIn(b'BUKAN RILIS STABIL', z.read('README-FLASH.txt'))
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            pkg.package(self.evidence, a)

    def test_damaged_evidence_is_rejected_without_creating_output(self):
        data = bytearray(self.evidence.read_bytes())
        data[len(data)//2] ^= 1
        bad = self.work / 'bad.zip'
        bad.write_bytes(data)
        target = self.work / 'installer.zip'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            pkg.package(bad, target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
