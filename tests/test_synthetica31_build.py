"""Host checks for the isolated 3.1 rebuild recipe; not a physical boot test."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_s31_test', ROOT / 'build-kit/scripts/build_synthetica31.py')
build = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(build)
BASE30 = Path(os.environ['S31_BASELINE_CONFIG']) if os.environ.get('S31_BASELINE_CONFIG') else None
TESTED20 = Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None


class BuildRecipeTests(unittest.TestCase):
    def test_version_is_31_in_each_private_guard_without_editing_original(self):
        self.assertEqual(build.RELEASE, '4.14.357-openela-synthetica-3.1')
        self.assertEqual(build.base.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.s2x.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.EXPECTED_LOCALVERSION, build.LOCALVERSION)
        self.assertEqual(build.base.rc.s2x.ALLOWED_CHANGES['LOCALVERSION'][1], build.LOCALVERSION)
        original_spec = importlib.util.spec_from_file_location('original_30', ROOT / 'build-kit/scripts/build_synthetica3_root.py')
        original = importlib.util.module_from_spec(original_spec)
        assert original_spec and original_spec.loader
        original_spec.loader.exec_module(original)
        self.assertEqual(original.EXPECTED_RELEASE, '4.14.357-openela-synthetica-3.0')
        self.assertEqual(original.rc.EXPECTED_LOCALVERSION, '"-synthetica-3.0"')

    def test_original_pins_and_disposable_prepare(self):
        build.base.check_inputs()
        with tempfile.TemporaryDirectory() as path:
            out = Path(path) / 'kit'
            build.prepare(ROOT / 'build-kit', out, ROOT / 'artifacts/generated.config.txt')
            builder = (out / 'ci/rollercoaster/build-rollercoaster.sh').read_text()
            self.assertIn('S2X_HELPER', builder)
            self.assertIn('check-config', builder)
            self.assertIn('Neutron', builder)
            self.assertFalse((out / 'ci/rollercoaster/patches/port-allow-foreign-vermagic.patch').exists())

    @unittest.skipUnless(BASE30 is not None and TESTED20 is not None, 'pinned 3.0 and experiment configs required')
    def test_only_localversion_may_change_from_the_exact_30_config(self):
        assert BASE30 is not None and TESTED20 is not None
        original = BASE30.read_text()
        self.assertIn('CONFIG_LOCALVERSION="-synthetica-3.0"', original)
        generated = original.replace('CONFIG_LOCALVERSION="-synthetica-3.0"',
                                     'CONFIG_LOCALVERSION="-synthetica-3.1"')
        self.assertNotEqual(original, generated)
        expected = {'LOCALVERSION': {'3.0': build.BASE30_LOCALVERSION, '3.1': build.LOCALVERSION}}
        self.assertEqual(build.compare_30_config(BASE30, generated), expected)
        with tempfile.TemporaryDirectory() as path:
            generated_path = Path(path) / 'config31'
            generated_path.write_text(generated)
            report = build.check_config(ROOT / 'artifacts/generated.config.txt', generated_path,
                                        TESTED20, BASE30, 'on')
            self.assertEqual(report['changes_from_original_3_0'], expected)
            generated_path.write_text(generated.replace('CONFIG_KSU=y', '# CONFIG_KSU is not set'))
            with self.assertRaises(ValueError):
                build.check_config(ROOT / 'artifacts/generated.config.txt', generated_path,
                                   TESTED20, BASE30, 'on')
            other = Path(path) / 'tampered30'
            other.write_text(original + '\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                build.compare_30_config(other, generated)

    def test_reference_config_hash_cannot_be_relaxed(self):
        with tempfile.TemporaryDirectory() as path:
            p = Path(path) / 'not-30-config'
            p.write_text('CONFIG_LOCALVERSION="-synthetica-3.0"\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                build.compare_30_config(p, 'CONFIG_LOCALVERSION="-synthetica-3.1"\n')


if __name__ == '__main__':
    unittest.main()
