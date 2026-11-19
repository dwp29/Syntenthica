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
    """Every allowed change must be traceable to the kit's own profile file."""

    def setUp(self):
        self.m = load()

    def test_stability_variant_changes_no_config_symbol(self):
        self.assertEqual(dict(self.m.ALLOWED_BY_VARIANT['fresh-milk']), {})

    def test_gaming_profile_uses_the_kit_profile(self):
        self.assertEqual(self.m.VARIANTS['cheese-burger']['profile'], 'critical')
        self.assertEqual(self.m.VARIANTS['fresh-milk']['profile'], 'synthetica')

    def test_gaming_delta_is_derived_from_the_profile_not_typed(self):
        """The allowed set must come from critical.config, not a hand list."""
        from pathlib import Path as _P
        profiles = ROOT / 'build-kit/ci/rollercoaster/profiles'
        reference = self.m.read_config_symbols(
            (ROOT / 'artifacts/generated.config.txt').read_text(encoding='utf-8'))
        expected = set(self.m.read_profile_delta('critical', reference)) | set(self.m.DERIVED_OK)

        def parse(text):
            return self.m.read_config_symbols(text)

        critical = parse((profiles / 'critical.config').read_text(encoding='utf-8'))
        real = {k for k, v in critical.items() if reference.get(k, 'n') != v}
        self.assertEqual({k for k in self.m.ALLOWED_BY_VARIANT['cheese-burger']
                          if k not in self.m.DERIVED_OK}, {k for k in expected
                                                           if k not in self.m.DERIVED_OK})
        self.assertTrue(real, 'critical.config must differ from the reference somewhere')

    def test_forbidden_symbols_never_appear_in_the_allowed_set(self):
        allowed = set(self.m.ALLOWED_BY_VARIANT['cheese-burger'])
        for key in self.m.MUST_STAY_OFF:
            self.assertNotIn(key, allowed, key)

    def test_required_features_are_not_permissively_allowed(self):
        # A symbol that must stay on cannot also be "free to change".
        allowed = set(self.m.ALLOWED_BY_VARIANT['cheese-burger'])
        mutated = {'UCLAMP_TASK', 'SCHED_WALT', 'KSU', 'KSU_SUSFS', 'NOMOUNT'}
        self.assertFalse(allowed & mutated, sorted(allowed & mutated))


class KitProfileGuard(unittest.TestCase):
    """The disposable kit must accept exactly the variant's own profile."""

    def setUp(self):
        self.m = load()

    def test_stability_kit_is_left_untouched(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'ci/rollercoaster/build-rollercoaster.sh'
            script.parent.mkdir(parents=True)
            guard = '[ "$PROFILE" = synthetica ] || { echo "wrong profile"; exit 1; }'
            script.write_text(guard + '\n', encoding='utf-8')
            self.m._allow_profile_in_kit(Path(tmp), 'synthetica')
            self.assertEqual(script.read_text(encoding='utf-8').strip(), guard)

    def test_gaming_kit_accepts_both_own_profiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'ci/rollercoaster/build-rollercoaster.sh'
            script.parent.mkdir(parents=True)
            script.write_text(
                '[ "$PROFILE" = synthetica ] || { echo "wrong profile"; exit 1; }\n',
                encoding='utf-8')
            self.m._allow_profile_in_kit(Path(tmp), 'critical')
            text = script.read_text(encoding='utf-8')
            self.assertIn('synthetica|critical', text)
            self.assertNotIn('[ "$PROFILE" = synthetica ]', text)


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
