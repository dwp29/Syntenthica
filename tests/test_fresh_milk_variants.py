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
import tempfile
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
                         '4.14.357-openela-Fresh-Milk-14.03B')
        self.assertEqual(self.m.VARIANTS['cheese-burger']['release'],
                         '4.14.357-openela-CHEESE-BURGER-11.08B')

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


class BakasuDelta(unittest.TestCase):
    """The BakaSU config delta is a closed set, not a blanket KSU_* pass.

    Two failures are being pinned here, both of which cost a CI run:

      1. listing the whole SuSFS family as an *expected change* failed every
         build, because those symbols are already off in the 2.0 baseline and
         therefore never appear in the diff;
      2. accepting "any KSU_* that moved" is not a guard at all - it would
         stamp a config nobody reviewed. A symbol outside the list must fail.
    """

    BASE = [
        'CONFIG_KSU=y', 'CONFIG_KSU_MANUAL_HOOK=y', 'CONFIG_SECCOMP=y',
        'CONFIG_SECCOMP_FILTER=y', 'CONFIG_SCHED_WALT=y', 'CONFIG_SCHED_TUNE=y',
        'CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y', 'CONFIG_CGROUP_SCHED=y',
        'CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y', 'CONFIG_LRU_GEN=y',
        '# CONFIG_LRU_GEN_ENABLED is not set',
        '# CONFIG_KSU_SUSFS is not set', '# CONFIG_KSU_SUSFS_SUS_PATH is not set',
        'CONFIG_KSU_MULTI_MANAGER_SUPPORT=y', 'CONFIG_KSU_FULL_NAME_FORMAT=y',
        'CONFIG_LOCALVERSION="-Synthetica-2.0"',
    ]
    GENERATED = [
        'CONFIG_KSU=y', 'CONFIG_KSU_MANUAL_HOOK=y', 'CONFIG_SECCOMP=y',
        'CONFIG_SECCOMP_FILTER=y', 'CONFIG_SCHED_WALT=y', 'CONFIG_SCHED_TUNE=y',
        'CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y', 'CONFIG_CGROUP_SCHED=y',
        'CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y', 'CONFIG_LRU_GEN=y',
        'CONFIG_LRU_GEN_ENABLED=y',
        '# CONFIG_KSU_SUSFS is not set', '# CONFIG_KSU_SUSFS_SUS_PATH is not set',
        '# CONFIG_KSU_MULTI_MANAGER_SUPPORT is not set',
        '# CONFIG_KSU_FULL_NAME_FORMAT is not set',
        'CONFIG_LOCALVERSION="-Fresh-Milk-14.03B"',
    ]

    TESTED = [
        'CONFIG_KSU=y', '# CONFIG_KSU_MANUAL_HOOK is not set', 'CONFIG_KSU_SUSFS=y',
        'CONFIG_KSU_SUSFS_SUS_PATH=y', 'CONFIG_KSU_MULTI_MANAGER_SUPPORT=y',
        'CONFIG_KSU_FULL_NAME_FORMAT=y', 'CONFIG_SECCOMP=y', 'CONFIG_SECCOMP_FILTER=y',
        'CONFIG_SCHED_WALT=y', 'CONFIG_SCHED_TUNE=y', 'CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y',
        'CONFIG_CGROUP_SCHED=y', 'CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y',
        'CONFIG_LRU_GEN=y', 'CONFIG_LRU_GEN_ENABLED=y', 'CONFIG_THERMAL=y',
        'CONFIG_MODULE_SIG_FORCE=y', 'CONFIG_MODVERSIONS=y', 'CONFIG_UCLAMP_TASK=y',
        'CONFIG_UCLAMP_TASK_GROUP=y', 'CONFIG_LOCALVERSION="-Synthetica-2.0-exp"',
    ]

    def install(self):
        m = load()
        module = type('Module', (), {})()
        v3 = type('V3', (), {'REQUIRED_Y': (), 'FORBIDDEN_Y': (),
                             'read_config': staticmethod(m.read_config_symbols)})()
        s2x = type('S2X', (), {})()
        s2x.v3 = v3
        s2x.ALLOWED_CHANGES = {
            'LOCALVERSION': ('"-Synthetica-2.0"', '"-Fresh-Milk-14.03B"')}
        s2x.MGLRU_FRAGMENTS = {'on': ('a', 'b'), 'off': ('c', 'd')}
        rc = type('RC', (), {})()
        rc.s2x = s2x
        base = type('Base', (), {})()
        base.rc = rc
        module.old = type('Old', (), {'base': base})()
        m._install_config_check(module, 'fresh-milk', set())
        return m, s2x

    def write(self, lines):
        return '\n'.join(lines) + '\n'

    def test_susfs_symbols_that_did_not_move_do_not_fail_the_build(self):
        m, s2x = self.install()
        changed = s2x.check_config(self.write(self.BASE), self.write(self.GENERATED))
        for key in ('KSU_SUSFS', 'KSU_SUSFS_SUS_PATH'):
            self.assertNotIn(key, changed, 'unchanged symbol must not be required to move')
        self.assertIn('KSU_MULTI_MANAGER_SUPPORT', changed)

    def test_a_ksu_symbol_outside_the_list_is_refused(self):
        m, s2x = self.install()
        stray = self.GENERATED + ['CONFIG_KSU_NOT_REVIEWED=y']
        with self.assertRaises(ValueError) as ctx:
            s2x.check_config(self.write(self.BASE), self.write(stray))
        self.assertIn('outside the BakaSU set', str(ctx.exception))
        self.assertIn('KSU_NOT_REVIEWED', str(ctx.exception))

    def install_tested(self):
        """The other gate: the build against the saved 2.0-experiment config."""
        m = load()
        module = type('Module', (), {})()
        v3 = type('V3', (), {'digest': lambda _self, _p: 'x',
                             'read_config': staticmethod(m.read_config_symbols)})()
        s2x = type('S2X', (), {})()
        s2x.v3 = v3
        rc = type('RC', (), {})()
        rc.s2x = s2x
        rc.TESTED_CONFIG_SHA256 = 'x'
        module.old = type('Old', (), {'base': type('Base', (), {'rc': rc})()})()
        m._install_tested_compare(module, 'fresh-milk', set())
        return rc

    def test_tested_gate_accepts_the_bakasu_hook_swap(self):
        # This exact difference - KSU_MANUAL_HOOK n->y with the identity flags
        # off - failed run 44692397153 after the 2.0-baseline gate was fixed.
        rc = self.install_tested()
        now = [line for line in self.TESTED]
        now = [('CONFIG_KSU_MANUAL_HOOK=y' if line == '# CONFIG_KSU_MANUAL_HOOK is not set'
                else '# CONFIG_KSU_SUSFS is not set' if line == 'CONFIG_KSU_SUSFS=y'
                else '# CONFIG_KSU_SUSFS_SUS_PATH is not set' if line == 'CONFIG_KSU_SUSFS_SUS_PATH=y'
                else '# CONFIG_KSU_MULTI_MANAGER_SUPPORT is not set'
                if line == 'CONFIG_KSU_MULTI_MANAGER_SUPPORT=y'
                else '# CONFIG_KSU_FULL_NAME_FORMAT is not set'
                if line == 'CONFIG_KSU_FULL_NAME_FORMAT=y'
                else 'CONFIG_LOCALVERSION="-Fresh-Milk-14.03B"'
                if line.startswith('CONFIG_LOCALVERSION') else line) for line in now]

        class Stub:
            def __init__(self, text):
                self.text = text

            def read_text(self, encoding=None):
                return self.text

        changed = rc.compare_tested_config(Stub('\n'.join(self.TESTED) + '\n'),
                                           '\n'.join(now) + '\n')
        self.assertEqual(changed['KSU_MANUAL_HOOK'], {'tested_2.0_exp': 'n', 'now': 'y'})
        self.assertEqual(changed['KSU_SUSFS'], {'tested_2.0_exp': 'y', 'now': 'n'})

    def test_tested_gate_refuses_a_symbol_outside_the_list(self):
        rc = self.install_tested()

        class Stub:
            def __init__(self, text):
                self.text = text

            def read_text(self, encoding=None):
                return self.text

        now = self.TESTED + ['CONFIG_KSU_RANDOM_FLAG=y']
        with self.assertRaises(ValueError) as ctx:
            rc.compare_tested_config(Stub('\n'.join(self.TESTED) + '\n'),
                                     '\n'.join(now) + '\n')
        self.assertIn('outside the BakaSU set', str(ctx.exception))

    def test_the_delta_is_closed_and_names_no_susfs_requirement(self):
        m = load()
        self.assertIsInstance(m.BAKASU_CONFIG_DELTA, tuple)
        for key in m.BAKASU_CONFIG_DELTA:
            self.assertTrue(key.startswith('KSU'), key)
            # SuSFS can never be a required feature on the manual-hook stack;
            # only the hook itself and the identity flags may be pinned on.
            if key.startswith('KSU_SUSFS'):
                self.assertNotIn(key, m.MUST_STAY_ON, key)

    def test_every_susfs_symbol_is_declared_impossible(self):
        m = load()
        declared = {k for k in m.BAKASU_MUST_STAY_OFF if k.startswith('KSU_SUSFS')}
        for key in declared:
            self.assertIn(key, m.BAKASU_CONFIG_DELTA, key)


class HookResolutionOrder(unittest.TestCase):
    """The hook choice must be resolved before the builder reads the profiles.

    build-rollercoaster.sh concatenates profiles/*.config into the defconfig and
    immediately runs olddefconfig. Resolving the choice during prepare-tree -
    after the tree is unpacked - rewrites a file whose content was already
    consumed. Locally that produced CONFIG_KSU_SUSFS=y and no manual hook, while
    the log said "hook choice resolved": the build would have compiled SuSFS and
    then failed its own audit.
    """

    SCRIPT = ROOT / 'build-kit/scripts/build_synthetica32_r1.py'
    BUILDER = ROOT / 'build-kit/ci/rollercoaster/build-rollercoaster.sh'

    def test_resolution_happens_in_prepare_not_prepare_tree(self):
        text = self.SCRIPT.read_text(encoding='utf-8')
        prepare, _, rest = text.partition('def prepare_tree(')
        self.assertIn('resolve_hook_choice', prepare)
        self.assertNotIn('resolve_hook_choice', rest)

    def test_resolution_gates_on_stack_not_archive(self):
        # The CI "Prepare isolated kit" step sets only FM_VARIANT, never
        # BAKASU_ARCHIVE. Keying the resolution on the archive skips it there,
        # leaves the profiles raw, and the compile step then fails its config
        # gate on a config that never carried the manual hook. This was the
        # exact failure behind the KSU_MANUAL_HOOK compile-step rejection.
        text = self.SCRIPT.read_text(encoding='utf-8')
        prepare = text[:text.index('def prepare_tree(')]
        # The gate line itself must test SP_ROOT_STACK, and must not test the
        # archive environment variable (the comment prose is allowed to name it).
        gate = [line.strip() for line in prepare.splitlines()
                if line.strip().startswith('if ') and 'resolve_hook_choice' not in line]
        gate = [line for line in gate if 'bakasu' in line]
        self.assertTrue(gate, 'no bakasu gate line found in prepare')
        self.assertIn('SP_ROOT_STACK', gate[-1])
        self.assertNotIn('BAKASU_ARCHIVE', gate[-1])

    def test_builder_audits_susfs_off_for_bakasu(self):
        # If the builder refuses SuSFS=n on this stack, no BakaSU build can pass
        # its own config audit no matter what the profile says.
        text = self.BUILDER.read_text(encoding='utf-8')
        audit = text[text.index('# --- audit: gagal cepat'):
                     text.index('# khusus port: pastikan uname')]
        self.assertIn('BAKASU_ARCHIVE', audit)
        branch = audit[audit.index('if [ "${BAKASU_ARCHIVE:-}" != "" ]; then'):
                       audit.index('else')]
        self.assertIn('chk KSU_MANUAL_HOOK y', branch)
        self.assertIn('chk KSU_SUSFS n', branch)

    def test_builder_still_demands_susfs_for_kernelsu_next(self):
        text = self.BUILDER.read_text(encoding='utf-8')
        audit = text[text.index('# --- audit: gagal cepat'):
                     text.index('# khusus port: pastikan uname')]
        after_else = audit[audit.index('else'):]
        self.assertIn('chk KSU_SUSFS y', after_else)


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


class FeatureBlock(unittest.TestCase):
    """A gaming profile must not lose the 3.2 features the kit pins."""

    def setUp(self):
        self.m = load()

    def test_feature_block_is_copied_verbatim(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp) / 'ci/rollercoaster/profiles'
            profiles.mkdir(parents=True)
            block = ('# Synthetica 2.0 experiment only\n'
                     'CONFIG_LRU_GEN=y\nCONFIG_LRU_GEN_ENABLED=y\n'
                     'CONFIG_UCLAMP_TASK=y\nCONFIG_SCHED_WALT=y\n')
            (profiles / 'synthetica.config').write_text('CONFIG_KSU=y\n\n' + block,
                                                        encoding='utf-8')
            (profiles / 'critical.config').write_text('CONFIG_HZ_300=y\n', encoding='utf-8')
            self.m._carry_features_into_profile(Path(tmp), 'critical')
            text = (profiles / 'critical.config').read_text(encoding='utf-8')
            self.assertIn('CONFIG_LRU_GEN_ENABLED=y', text)
            self.assertIn('CONFIG_UCLAMP_TASK=y', text)
            # The gaming values must survive the copy.
            self.assertIn('CONFIG_HZ_300=y', text)
            # f2fs statistics stay off instead of reverting to 00-common.
            self.assertIn('# CONFIG_F2FS_STAT_FS is not set', text)
            # Idempotent: a second call must not duplicate the block.
            self.m._carry_features_into_profile(Path(tmp), 'critical')
            self.assertEqual(text, (profiles / 'critical.config').read_text(encoding='utf-8'))

    def test_stability_profile_is_not_modified(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp) / 'ci/rollercoaster/profiles'
            profiles.mkdir(parents=True)
            (profiles / 'synthetica.config').write_text('CONFIG_A=y\n', encoding='utf-8')
            (profiles / 'critical.config').write_text('CONFIG_B=y\n', encoding='utf-8')
            self.m._carry_features_into_profile(Path(tmp), 'synthetica')
            self.assertEqual((profiles / 'critical.config').read_text(encoding='utf-8'),
                             'CONFIG_B=y\n')


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
        self.assertEqual([i['kver'] for i in include], ['14.03B', '11.08B'])

    def test_profile_exists_in_the_kit(self):
        include = self.doc['jobs']['variant']['strategy']['matrix']['include']
        profiles = (ROOT / 'build-kit/ci/rollercoaster/profiles')
        for item in include:
            self.assertTrue((profiles / 'synthetica.config').exists(), item['variant'])


class Compare31ExportsGate(unittest.TestCase):
    """The export ABI gate: BakaSU lets symbol addresses move, not the ABI.

    The pinned 3.1 reference is a KernelSU-Next build. BakaSU changes the root
    driver and the Kconfig hook choice, which shifts the kernel link layout:
    every symbol's address (crc) moves even though the exported ABI - names,
    owners and export types - is unchanged. The gate must accept the crc delta
    but still refuse any name, owner or type change, and must leave the strict
    KernelSU-Next gate untouched.
    """

    REF_SYMS = 12236
    REF_BUILTIN = 12227

    def _symvers(self, crc_shift=0, owner_shift=False):
        lines = ['0xed5659d1 module_layout vmlinux EXPORT_SYMBOL']
        for i in range(self.REF_BUILTIN - 1):
            lines.append(f'0x{(i + 1 + crc_shift) & 0xFFFFFFFF:08x} vmsym{i} vmlinux EXPORT_SYMBOL')
        for i in range(self.REF_SYMS - self.REF_BUILTIN):
            owner = 'other_module' if (owner_shift and i == 0) else 'some_module'
            lines.append(f'0x{(100000 + i + 1 + crc_shift) & 0xFFFFFFFF:08x} modsym{i} {owner} EXPORT_SYMBOL_GPL')
        return '\n'.join(lines) + '\n'

    def _module(self, stack='bakasu'):
        import os
        self._env = {}
        for var, val in (('SP_BUILD_NAME', 'Fresh-Milk'), ('SP_BUILD_KVER', '14.03B'),
                         ('SP_PROFILE', 'synthetica')):
            self._env[var] = os.environ.get(var)
            os.environ[var] = val
        m = load()
        # The closure reads spec['root_stack'] when the gate runs, so keep the
        # override in place until tearDown restores it.
        self._saved_stack = m.VARIANTS['fresh-milk']['root_stack']
        m.VARIANTS['fresh-milk']['root_stack'] = stack
        module = m.apply_variant('fresh-milk')
        # Neutralise the pinned reference digest so arbitrary fixture bytes pass.
        module.BASE31_SYMVERS_SHA256 = 'deadbeef'
        module.v3.digest = lambda _p: 'deadbeef'
        return module

    def tearDown(self):
        import os
        for var, val in getattr(self, '_env', {}).items():
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val
        if hasattr(self, '_saved_stack'):
            load().VARIANTS['fresh-milk']['root_stack'] = self._saved_stack

    def test_bakasu_allows_the_crc_to_move(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / 'ref.symvers'
            gen = Path(tmp) / 'gen.symvers'
            ref.write_text(self._symvers(crc_shift=0), encoding='utf-8')
            gen.write_text(self._symvers(crc_shift=1), encoding='utf-8')
            result = module.compare_31_exports(ref, gen)
            self.assertEqual(result['missing_added_or_changed'], 0)
            self.assertGreater(result['crc_moved_on_bakasu_stack'], 0)

    def test_bakasu_refuses_an_abi_change(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / 'ref.symvers'
            gen = Path(tmp) / 'gen.symvers'
            ref.write_text(self._symvers(), encoding='utf-8')
            gen.write_text(self._symvers(owner_shift=True), encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                module.compare_31_exports(ref, gen)
            self.assertIn('owner/type changed', str(ctx.exception))

    def test_kernelsu_next_stack_stays_strict(self):
        module = self._module(stack='kernelsu-next')
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / 'ref.symvers'
            gen = Path(tmp) / 'gen.symvers'
            ref.write_text(self._symvers(crc_shift=0), encoding='utf-8')
            gen.write_text(self._symvers(crc_shift=1), encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                module.compare_31_exports(ref, gen)
            self.assertIn('changed=', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
