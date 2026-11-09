"""Offline installer integration with the SHA-pinned public ROM boot image.

ARM tools execute through QEMU on a regular file in a temporary directory.
The harness redirects paths and denies writing to real block devices. This does
not run recovery, verify the bootloader's AVB chain, or boot the result.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_synthetica3_boot as boot
import audit_boot_avb_hash as avb

spec = importlib.util.spec_from_file_location('installer_fixture', ROOT / 'tests/test_synthetica3_installer20_qemu.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

PUBLIC_BOOT_SHA = 'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f'
IMAGE_SHA = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
fixture.IMAGE_SHA = IMAGE_SHA

@unittest.skipUnless(os.environ.get('S31_INFINITY_OFFLINE') == '1', 'public ROM and QEMU test opt-in')
class PublicROMInstallerTest(unittest.TestCase):
    setUp = fixture.OriginalAnyKernelTests.setUp
    run_entry = fixture.OriginalAnyKernelTests.run_entry

    def test_actual_installer_on_pinned_public_boot_regular_file(self):
        source = Path(os.environ['S31_PUBLIC_BOOT'])
        self.assertEqual(source.stat().st_size, 134217728)
        self.assertEqual(fixture.sha(source.read_bytes()), PUBLIC_BOOT_SHA)
        before = boot.inspect_boot(source)
        shutil.copyfile(source, self.boot)
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout[-8000:])
        self.assertIn('Done. No automatic reboot.', p.stdout)
        after = boot.inspect_boot(self.boot)
        comparison = boot.compare_boot(before, after, IMAGE_SHA)
        result = {'scope': 'Emulated installer on public ROM regular file, no recovery or physical boot; external AVB not verified.',
                  'installer_completed': True, 'boot_comparison': comparison}
        try:
            result['output_embedded_avb'] = avb.inspect(self.boot)
        except (ValueError, OSError) as e:
            result['output_embedded_avb'] = {'read_error': str(e)}
        print('INFINITY_OFFLINE_RESULT=' + json.dumps(result, sort_keys=True))
        self.assertTrue(comparison['candidate_kernel_equals_bundle_image'])
        self.assertTrue(all(comparison['stable_header_fields_match'].values()))
        self.assertTrue(all(comparison['non_kernel_sections_match'].values()))
        self.assertTrue(comparison['candidate_legacy_boot_id_matches'])

if __name__ == '__main__':
    unittest.main()
