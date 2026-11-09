"""ARM user-mode installer test against public ROM; all paths are redirected."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build-kit/scripts'))
import audit_boot_avb_hash as avb
import audit_synthetica3_boot as boot
spec=importlib.util.spec_from_file_location('rom_fixture',ROOT/'tests/test_synthetica31_infinity_installer_offline.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

@unittest.skipUnless(os.environ.get('S31_INFINITY_OFFLINE')=='1','public ROM and ARM QEMU opt-in')
class RepairedInfinityTest(fixture.PublicROMInstallerTest):
    def setUp(self):
        super().setUp()
        with zipfile.ZipFile(os.environ['S3_INSTALLER20_ZIP']) as z:
            arm=self.arm/'fix-avb';arm.write_bytes(z.read('tools/fix-avb'));arm.chmod(0o755)
        wrapper=self.tools/'fix-avb'
        wrapper.write_text('#!/bin/sh\nexec qemu-arm-static "'+str(arm)+'" "$@"\n');wrapper.chmod(0o755)

    def test_actual_installer_on_pinned_public_boot_regular_file(self):
        source=Path(os.environ['S31_PUBLIC_BOOT'])
        self.assertEqual(fixture.fixture.sha(source.read_bytes()),fixture.PUBLIC_BOOT_SHA)
        before=boot.inspect_boot(source);shutil.copyfile(source,self.boot)
        p=self.run_entry();self.assertEqual(p.returncode,0,p.stdout[-6000:])
        self.assertIn('repairing unsigned embedded AVB hash',p.stdout)
        self.assertIn('Done. No automatic reboot.',p.stdout)
        after=boot.inspect_boot(self.boot);comparison=boot.compare_boot(before,after,fixture.IMAGE_SHA)
        self.assertTrue(comparison['candidate_kernel_equals_bundle_image'])
        self.assertTrue(comparison['candidate_legacy_boot_id_matches'])
        self.assertTrue(all(comparison['stable_header_fields_match'].values()))
        self.assertTrue(all(v for k,v in comparison['non_kernel_sections_match'].items() if k!='ramdisk'))
        report=avb.inspect(self.boot)
        self.assertTrue(report['vbmeta_algorithm_none'])
        self.assertTrue(report['embedded_boot_hash']['digest_matches'])
        self.assertEqual(report['embedded_boot_hash']['image_bytes'],after['avb']['original_image_size'])
        print('PATCHED_INFINITY_AVB_OK=1 physical_boot=NOT_TESTED external_avb=NOT_VERIFIED')
