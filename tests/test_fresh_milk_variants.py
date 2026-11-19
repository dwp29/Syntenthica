"""Host-side checks for the Fresh-Milk / CHEESE-BURGER variants.

These never compile anything. They pin the decisions that a build must not be
allowed to drift from: the release identity and where it comes from, the exact
set of config changes (none), the symbols that must stay on or off, and the
installer text.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build-kit/scripts/build_fresh_milk.py'
ASSETS = ROOT / 'build-kit/ci/fresh-milk'
INSTALLER = ROOT / 'build-kit/ci/rollercoaster/anykernel/anykernel.sh'
WORKFLOW = ROOT / '.github/workflows/fresh-milk-kernel.yml'


def load(name: str = 'fresh_milk_variants'):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VariantIdentity(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_release_names_fit_utsname(self):
        for name, spec in self.m.VARIANTS.items():
            self.assertLessEqual(len(spec['release']), 64, name)

    def test_capitalisation_is_preserved(self):
        # Users and the manager see this string; it is matched literally.
        self.assertEqual(self.m.VARIANTS['fresh-milk']['release'],
                         '4.14.357-openela-Fresh-Milk-14.03')
        self.assertEqual(self.m.VARIANTS['cheese-burger']['release'],
                         '4.14.357-openela-CHEESE-BURGER-11.08')

    def test_localversion_matches_release(self):
        for name, spec in self.m.VARIANTS.items():
            self.assertEqual(spec['localversion'], f'"{spec["release"].split("openela")[1]}"',
                             name)

    def test_two_distinct_releases(self):
        releases = {s['release'] for s in self.m.VARIANTS.values()}
        self.assertEqual(len(releases), len(self.m.VARIANTS))

    def test_identity_has_matching_builder_parts(self):
        # The rollercoaster builder derives CONFIG_LOCALVERSION from these two
        # variables, so they must agree with the release string exactly.
        for name, spec in self.m.VARIANTS.items():
            self.assertEqual(spec['release'],
                             f'4.14.357-openela-{spec["name"]}-{spec["kver"]}', name)


class ConfigScope(unittest.TestCase):
    """The only thing allowed to change is the identity."""

    def setUp(self):
        self.m = load()

    def test_no_config_symbol_is_changed(self):
        self.assertEqual(dict(self.m.ALLOWED), {})

    def test_baseline_already_has_the_considered_symbols(self):
        # CRYPTO_ZSTD, CRYPTO_LZ4HC and TMPFS_XATTR are already y in the 2.0
        # baseline, so they are guards, not changes. Pin that reasoning.
        baseline = (ROOT / 'artifacts/generated.config.txt').read_text(encoding='utf-8')
        for symbol in ('CRYPTO_ZSTD', 'CRYPTO_LZ4HC', 'TMPFS_XATTR'):
            self.assertIn(f'CONFIG_{symbol}=y', baseline, symbol)
            self.assertIn(symbol, self.m.MUST_STAY_ON)

    def test_must_stay_off_has_reasons(self):
        for key, reason in self.m.MUST_STAY_OFF.items():
            self.assertTrue(reason.strip(), key)

    def test_try_umount_stays_off_with_reason(self):
        self.assertIn('KSU_SUSFS_TRY_UMOUNT', self.m.MUST_STAY_OFF)
        self.assertIn('susfs_try_umount', self.m.MUST_STAY_OFF['KSU_SUSFS_TRY_UMOUNT'])

    def test_required_features_cover_the_32_baseline(self):
        for feature in ('KSU', 'KSU_SUSFS', 'NOMOUNT', 'LRU_GEN', 'SCHED_TUNE',
                        'SCHED_WALT', 'UCLAMP_TASK', 'MODULE_SIG_FORCE'):
            self.assertIn(feature, self.m.MUST_STAY_ON)


class BuildEnvironment(unittest.TestCase):
    """Wrong environment must fail before a compile starts, not after."""

    def setUp(self):
        self.m = load()

    def test_mismatched_builder_name_is_refused(self):
        import os
        saved = os.environ.get('SP_BUILD_NAME')
        os.environ['SP_BUILD_NAME'] = 'fresh-milk'          # lowercase is wrong
        try:
            with self.assertRaises(SystemExit):
                self.m.apply_variant('fresh-milk')
        finally:
            if saved is None:
                os.environ.pop('SP_BUILD_NAME', None)
            else:
                os.environ['SP_BUILD_NAME'] = saved

    def test_matching_environment_is_accepted(self):
        import os
        saved = os.environ.get('SP_BUILD_NAME')
        os.environ['SP_BUILD_NAME'] = 'CHEESE-BURGER'
        try:
            self.m.apply_variant('cheese-burger')
        finally:
            if saved is None:
                os.environ.pop('SP_BUILD_NAME', None)
            else:
                os.environ['SP_BUILD_NAME'] = saved


class Delegation(unittest.TestCase):
    """build-rollercoaster.sh calls $S2X_HELPER; that must reach the recipe."""

    def test_helper_accepts_recipe_subcommands(self):
        env = {'PATH': '/usr/bin:/bin', 'FM_VARIANT': 'fresh-milk'}
        out = subprocess.run([sys.executable, str(SCRIPT), 'check-config',
                              '--baseline', '/dev/null', '--generated', '/dev/null'],
                             capture_output=True, text=True, env=env, timeout=120)
        combined = out.stdout + out.stderr
        self.assertNotIn('invalid choice', combined)
        self.assertNotIn('unrecognized arguments', combined)
        self.assertIn('config paths are required', combined)

    def test_helper_requires_a_known_variant(self):
        env = {'PATH': '/usr/bin:/bin', 'FM_VARIANT': 'not-a-variant'}
        out = subprocess.run([sys.executable, str(SCRIPT), 'check-config'],
                             capture_output=True, text=True, env=env, timeout=120)
        self.assertIn('FM_VARIANT', out.stdout + out.stderr)


class InstallerText(unittest.TestCase):
    def setUp(self):
        self.text = INSTALLER.read_text(encoding='utf-8')

    def test_installer_is_english(self):
        for word in ('Menginstal', 'Kernel terpasang', 'selesai', 'doa'):
            self.assertNotIn(word, self.text)

    def test_installer_shows_the_release(self):
        # The packager rewrites SP_RELEASE from the build's CONFIG_LOCALVERSION.
        self.assertIn('SP_RELEASE', self.text)
        self.assertIn('4.14.357-openela-', self.text)

    def test_installer_keeps_ksud_installation(self):
        # Root userspace must still be installed; dropping this silently would
        # leave users with a kernel and no root.
        self.assertIn('/data/adb/ksud', self.text)
        self.assertIn('ksud', self.text)

    def test_progress_is_plain_percentages(self):
        # Percentages are arguments to sp_bar, which renders "[####....] 35%".
        self.assertIn('ui_print "  [${_bar}] ${_pct}%  $2"', self.text)
        for step in ('sp_bar 10', 'sp_bar 35', 'sp_bar 75', 'sp_bar 100'):
            self.assertIn(step, self.text)

    def test_no_auto_reboot(self):
        self.assertNotIn('reboot recovery', self.text)
        self.assertIn('auto_reboot=no', self.text)

    def test_installer_is_syntactically_valid_shell(self):
        out = subprocess.run(['sh', '-n', str(INSTALLER)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)


class Workflow(unittest.TestCase):
    def setUp(self):
        import yaml
        self.doc = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))

    def test_matrix_carries_the_builder_identity(self):
        include = self.doc['jobs']['variant']['strategy']['matrix']['include']
        self.assertEqual([i['name'] for i in include], ['Fresh-Milk', 'CHEESE-BURGER'])
        self.assertEqual([i['kver'] for i in include], ['14.03', '11.08'])

    def test_profile_exists_in_the_kit(self):
        include = self.doc['jobs']['variant']['strategy']['matrix']['include']
        profiles = (ROOT / 'build-kit/ci/rollercoaster/profiles')
        for item in include:
            self.assertTrue((profiles / 'synthetica.config').exists(), item['variant'])


if __name__ == '__main__':
    unittest.main()
