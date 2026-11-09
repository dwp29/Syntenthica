"""QEMU tests for Synthetica 3.2 installer: cross-ROM synthetic, stock Infinity 4.1, and upgrade."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_boot_avb_hash as avb
import audit_synthetica3_boot as boot

ENABLED = os.environ.get('S32_FINAL_QEMU') == '1'
if ENABLED:
    os.environ['S31_QEMU'] = '1'
    os.environ['S31_ZIP'] = os.environ['S32_ZIP']
    os.environ['S31_IMAGE_SHA'] = os.environ['S32_IMAGE_SHA']

spec31 = importlib.util.spec_from_file_location('s31_qemu_for_32', ROOT / 'tests/test_synthetica31_package_qemu.py')
s31_qemu = importlib.util.module_from_spec(spec31)
assert spec31 and spec31.loader
spec31.loader.exec_module(s31_qemu)

PUBLIC_BOOT_SHA = 'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f'


def wrap_fix_avb(test_case):
    with zipfile.ZipFile(os.environ['S32_ZIP']) as z:
        arm = test_case.arm / 'fix-avb'
        arm.write_bytes(z.read('tools/fix-avb'))
        arm.chmod(0o755)
    wrapper = test_case.tools / 'fix-avb'
    wrapper.write_text(f'#!/bin/sh\nexec qemu-arm-static "{arm}" "$@"\n')
    wrapper.chmod(0o755)


@unittest.skipUnless(ENABLED, 'Synthetica 3.2 QEMU integration is opt-in')
class Synthetica32CrossRomSyntheticTests(s31_qemu.NewInstallerTests):
    def setUp(self):
        super().setUp()
        wrap_fix_avb(self)


@unittest.skipUnless(ENABLED and os.environ.get('S31_PUBLIC_BOOT'), 'public Infinity ROM boot required')
class Synthetica32InfinityAndUpgradeTests(unittest.TestCase):
    run_entry = s31_qemu.old.OriginalAnyKernelTests.run_entry

    def setUp(self):
        s31_qemu.old.OriginalAnyKernelTests.setUp(self)
        wrap_fix_avb(self)

    def test_fresh_infinity_and_direct_reflashing_upgrade(self):
        source = Path(os.environ['S31_PUBLIC_BOOT'])
        image_sha = os.environ['S32_IMAGE_SHA']
        self.assertEqual(s31_qemu.old.sha(source.read_bytes()), PUBLIC_BOOT_SHA)
        before = boot.inspect_boot(source)
        shutil.copyfile(source, self.boot)

        # Stage 1: fresh flash on stock Project Infinity X 4.1 GAPPS boot.img
        p1 = self.run_entry()
        self.assertEqual(p1.returncode, 0, p1.stdout[-6000:])
        self.assertIn('Infinity 4.1: repairing unsigned embedded AVB hash...', p1.stdout)
        self.assertIn('Done. No automatic reboot.', p1.stdout)
        after1 = boot.inspect_boot(self.boot)
        cmp1 = boot.compare_boot(before, after1, image_sha)
        self.assertTrue(cmp1['candidate_kernel_equals_bundle_image'])
        self.assertTrue(cmp1['candidate_legacy_boot_id_matches'])
        rep1 = avb.inspect(self.boot)
        self.assertTrue(rep1['vbmeta_algorithm_none'])
        self.assertTrue(rep1['embedded_boot_hash']['digest_matches'])
        self.assertEqual(rep1['embedded_boot_hash']['image_bytes'], after1['avb']['original_image_size'])

        # Stage 2: direct re-flash / upgrade over already-flashed Synthetica boot image
        p2 = self.run_entry()
        self.assertEqual(p2.returncode, 0, p2.stdout[-6000:])
        self.assertIn('Done. No automatic reboot.', p2.stdout)
        after2 = boot.inspect_boot(self.boot)
        cmp2 = boot.compare_boot(before, after2, image_sha)
        self.assertTrue(cmp2['candidate_kernel_equals_bundle_image'])
        self.assertTrue(cmp2['candidate_legacy_boot_id_matches'])
        rep2 = avb.inspect(self.boot)
        self.assertTrue(rep2['vbmeta_algorithm_none'])
        self.assertTrue(rep2['embedded_boot_hash']['digest_matches'])
        self.assertEqual(rep2['embedded_boot_hash']['image_bytes'], after2['avb']['original_image_size'])


if __name__ == '__main__':
    unittest.main()
