"""3.1 UI/2.0 AnyKernel integration on temporary synthetic files only.

Requires S31_QEMU=1, S31_ZIP and S31_IMAGE_SHA. Inherited harness rewrites
paths in scratch scripts, bounds dd to a regular fixture and mocks mounts.
No physical recovery, partition, root, module trust or device boot is tested.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get('S31_QEMU') == '1'
if ENABLED:
    os.environ['S3_INSTALLER20_QEMU'] = '1'
    os.environ['S3_INSTALLER20_ZIP'] = os.environ['S31_ZIP']
spec = importlib.util.spec_from_file_location('synthetica20_qemu_for_31',
                                              ROOT / 'tests/test_synthetica3_installer20_qemu.py')
old = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(old)
if ENABLED:
    old.IMAGE_SHA = os.environ['S31_IMAGE_SHA']


@unittest.skipUnless(ENABLED, 'ARM/QEMU synthetic 3.1 integration is opt-in')
class NewInstallerTests(old.OriginalAnyKernelTests):
    def test_real_2_0_anykernel_core_installs_on_synthetic_boot_and_copies_ksud(self):
        tree = old.fixture.fdt(b'31-synthetic-dtb-one\0')
        self.make_boot(tree)
        adb = self.fs / 'data/adb'
        adb.mkdir(parents=True)
        (adb / 'ksud').write_bytes(b'previous daemon')
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('[2/3] Installing ksud...', p.stdout)
        self.assertIn('ksud: OK', p.stdout)
        self.assertIn('[3/3] Preparing boot...', p.stdout)
        self.assertIn('[3/3] Writing boot...', p.stdout)
        self.assertIn('Done. No automatic reboot.', p.stdout)
        self.assertEqual(old.sha((adb / 'ksud').read_bytes()), old.KSUD_SHA)
        for value in ('0.20', '0.45', '0.75', '1.0'):
            self.assertIn('set_progress ' + value, p.stdout)
        self.verify_boot(tree)

    def test_locked_data_skips_ksud_but_installs_on_a_second_synthetic_dtb(self):
        tree = old.fixture.fdt(b'31-synthetic-dtb-two\0')
        self.make_boot(tree)
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('ksud skipped.', p.stdout)
        self.assertIn('WARNING:', p.stdout)
        self.assertFalse((self.fs / 'data/adb/ksud').exists())
        self.assertIn('Done. No automatic reboot.', p.stdout)
        self.verify_boot(tree)

    def test_invalid_boot_exposes_error_and_never_reports_success(self):
        tree = old.fixture.fdt(b'31-invalid-boot\0')
        self.make_boot(tree)
        data = bytearray(self.boot.read_bytes())
        data[:8] = b'BAD-BOOT'
        self.boot.write_bytes(data)
        before = old.sha(bytes(data))
        p = self.run_entry()
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Aborting', p.stdout)
        self.assertNotIn('Done. No automatic reboot.', p.stdout)
        self.assertNotIn('set_progress 1.0', p.stdout)
        self.assertEqual(old.sha(self.boot.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
