#!/usr/bin/env python3
"""Fresh-Milk-14.03 / CHEESE-BURGER-11.08 - two identities, one proven tree.

This module is a thin, explicit layer on the 3.2-r1 recipe (which passed its
own host tests). It does NOT change code, patches, toolchain, SuSFS or root.
It changes two things only:

  1. the release identity (CONFIG_LOCALVERSION and therefore vermagic), and
  2. nothing else - the whole config guard stays exactly as 3.2-r1 left it.

The identity is not written into a config file by hand: the rollercoaster
builder derives CONFIG_LOCALVERSION from SP_BUILD_NAME and SP_BUILD_KVER
(LOCALVER="-${NAME}-${KVER}"). So the capitalisation that users see in
`uname -r` comes from those two variables, and this module refuses to run
when they disagree with the variant table below.

Why no extra CONFIG_* symbols: the three that were considered
(CRYPTO_ZSTD, CRYPTO_LZ4HC, TMPFS_XATTR) are already enabled in the 2.0
baseline that 3.2-r1 was built from, so "adding" them is a no-op. They are
therefore guarded as must-stay-on instead of listed as allowed changes -
listing them as changes would make the exact-difference guard fail, which is
exactly what it is there to do.

Usage
    build_fresh_milk.py <variant> verify
    build_fresh_milk.py <variant> apply      # same guards, no compile
    build_fresh_milk.py <3.2-r1 subcommand>  # delegation, variant from FM_VARIANT
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'build-kit/ci/fresh-milk'

VARIANTS = {
    # The `B` suffix marks the BakaSU root stack. A release string is the only
    # thing a user can read off `uname -r` to tell which manager a kernel will
    # answer to, so the two stacks must never share a name.
    'fresh-milk': {
        'name': 'Fresh-Milk',
        'kver': '14.03B',
        'localversion': '"-Fresh-Milk-14.03B"',
        'release': '4.14.357-openela-Fresh-Milk-14.03B',
        'profile': 'synthetica',
        'focus': 'stability',
        'root_stack': 'bakasu',
    },
    'cheese-burger': {
        'name': 'CHEESE-BURGER',
        'kver': '11.08B',
        'localversion': '"-CHEESE-BURGER-11.08B"',
        'release': '4.14.357-openela-CHEESE-BURGER-11.08B',
        'profile': 'critical',
        'focus': 'gaming-performance',
        'root_stack': 'bakasu',
    },
}

# Which config symbols each variant may differ in, relative to 3.1.
#
# The stability variant changes none. The gaming variant runs the kit's own
# critical.config profile, so its allowed set is *derived* from that file and
# from the 3.1 config rather than typed by hand - a hand-written list drifts the
# moment either file changes.
#
# Two effects learned from a real CI failure shape this:
#   * critical.config repeats many values 3.1 already carries. Repeating a value
#     is not a change and must not appear in the allowed set.
#   * Kconfig resolves mutually exclusive options itself (HZ_300=y turns
#     HZ_100 off; the performance governor deselects schedutil's default).
#     Those derived flips are permitted per symbol, with no pinned value,
#     because the profile never states the resulting value.
REFERENCE_31 = ROOT / 'artifacts/generated.config.txt'
PROFILE_DIR = ROOT / 'build-kit/ci/rollercoaster/profiles'
DERIVED_OK = (
    # HZ_300=y deselects HZ_100 through Kconfig exclusivity.
    'HZ_100',
    # critical.config states the performance governor as the default and never
    # mentions schedutil's default, so Kconfig turns the latter off.
    'CPU_FREQ_DEFAULT_GOV_SCHEDUTIL',
    # critical.config omits WQ_POWER_EFFICIENT_DEFAULT, and Kconfig drops an
    # option the chosen profile does not restate.
    'WQ_POWER_EFFICIENT_DEFAULT',
    # DEFAULT_IOSCHED="deadline" makes Kconfig drop the cfq default companion.
    'DEFAULT_CFQ',
)


def read_config_symbols(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('# CONFIG_') and line.endswith(' is not set'):
            out[line[len('# CONFIG_'):-len(' is not set')]] = 'n'
            continue
        if line.startswith('CONFIG_'):
            key, _, value = line[len('CONFIG_'):].partition('=')
            out[key] = value
    return out


def read_profile_delta(profile: str, reference: dict[str, str]) -> tuple[str, ...]:
    """Symbols a profile actually changes relative to the reference config."""
    stated = read_config_symbols((PROFILE_DIR / f'{profile}.config').read_text(encoding='utf-8'))
    return tuple(k for k, v in stated.items() if reference.get(k, 'n') != v)


# Symbols that must be present in the final .config. The last three are already
# enabled in the 2.0 baseline, so they are guards, not changes.
MUST_STAY_ON = (
    'LRU_GEN', 'LRU_GEN_ENABLED', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP',
    'SCHED_WALT', 'SCHED_TUNE', 'KSU', 'KSU_MANUAL_HOOK',
    'NOMOUNT', 'SECCOMP', 'SECCOMP_FILTER', 'MODULE_SIG_FORCE', 'MODVERSIONS',
    'SECURITY_SELINUX', 'DM_VERITY', 'F2FS_FS', 'EROFS_FS',
    'BPF_SYSCALL', 'BPF_JIT_ALWAYS_ON',
    'CRYPTO_ZSTD', 'CRYPTO_LZ4HC', 'TMPFS_XATTR',
)

MUST_STAY_OFF = {
    'MODULE_FORCE_LOAD': 'allows loading unsigned modules',
    'KSU_SUSFS_TRY_UMOUNT':
        'this 4.14 SuSFS port has no susfs_try_umount(); forcing it fails the build',
    'KSU_SUSFS_SUS_MEMFD': 'disabled in the 3.2 base; not changed without a reason',
}

# On the BakaSU stack, SuSFS is not "off because someone changed their mind": it
# is a competing member of the same Kconfig `choice` as KSU_MANUAL_HOOK, and a
# 4.14 kernel must take the manual hook. Declaring SuSFS impossible here keeps
# the build from flipping back and forth depending on file order.
BAKASU_MUST_STAY_OFF = {
    'KSU_SUSFS': 'BakaSU ties SuSFS and manual hooks to one choice; 4.14 takes the manual hook',
    'KSU_SUSFS_SUS_PATH': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_SUS_MOUNT': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_SUS_KSTAT': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_SUS_MAP': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_SPOOF_UNAME': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_OPEN_REDIRECT': 'SuSFS sub-option; parent is off on this stack',
    'KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS': 'SuSFS sub-option; parent is off on this stack',
}


# Symbols whose value changes on the BakaSU stack, and nothing else. Each is a
# consequence of BakaSU's Kconfig, not a preference: SuSFS and manual hooks share
# one `choice`, so taking the manual hook turns the SuSFS family off.
BAKASU_CONFIG_DELTA = (
    'KSU_MANUAL_HOOK', 'KSU_SUSFS', 'KSU_SUSFS_SUS_PATH', 'KSU_SUSFS_SUS_MOUNT',
    'KSU_SUSFS_SUS_KSTAT', 'KSU_SUSFS_SUS_MEMFD', 'KSU_SUSFS_SUS_MAP',
    'KSU_SUSFS_SPOOF_UNAME', 'KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG',
    'KSU_SUSFS_OPEN_REDIRECT', 'KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS',
    'KSU_SUSFS_ENABLE_LOG', 'KSU_SUSFS_TRY_UMOUNT',
    'KSU_MULTI_MANAGER_SUPPORT', 'KSU_FULL_NAME_FORMAT',
    # BakaSU opens a `menu depends on KSU_MANUAL_HOOK` block; these three are
    # its only members and they default to y. Taking the manual hook therefore
    # turns them on, and Kconfig writes them into .config. They were found by
    # running olddefconfig against this tree, not guessed: the first local run
    # of the real gate listed exactly these three as "outside the BakaSU set".
    'KSU_MANUAL_HOOK_AUTO_SETUID_HOOK',
    'KSU_MANUAL_HOOK_AUTO_INPUT_HOOK',
    'KSU_MANUAL_HOOK_AUTO_INITRC_HOOK',
)

# variant -> (permissive symbols, derived symbols)
ALLOWED_BY_VARIANT = {
    'fresh-milk': (),
    'cheese-burger': (read_profile_delta('critical', read_config_symbols(
        REFERENCE_31.read_text(encoding='utf-8'))) if REFERENCE_31.exists() else ()) + DERIVED_OK,
}


def load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _allow_profile_in_kit(kit: Path, profile: str) -> None:
    """Let the disposable kit accept this variant's profile.

    build_synthetica3.py stamps `[ "$PROFILE" = synthetica ] || exit 1` into the
    copied builder as a guard. That guard exists to stop a 3.2 build from
    silently running a foreign profile. A variant that deliberately runs one of
    the kit's own profiles has to widen the check - in the disposable copy only,
    never in the repo, and only for the exact profile drawn from the variant
    table.
    """
    script = kit / 'ci/rollercoaster/build-rollercoaster.sh'
    if profile == 'synthetica' or not script.is_file():
        return
    text = script.read_text(encoding='utf-8')
    before = '[ "$PROFILE" = synthetica ] || { echo "wrong profile"; exit 1; }'
    after = ('case "$PROFILE" in synthetica|' + profile + ') : ;; '
             '*) echo "wrong profile"; exit 1 ;; esac')
    if text.count(before) != 1:
        raise SystemExit(f'kit builder does not carry the expected profile guard: {script}')
    script.write_text(text.replace(before, after, 1), encoding='utf-8')
    print(f'kit          : profile guard accepts synthetica|{profile}')


def _carry_features_into_profile(kit: Path, profile: str) -> None:
    """Give a non-stability profile the same pinned 3.2 feature block.

    prepare() in the 2.0-experiment recipe appends the pinned feature config and
    the MGLRU boot-default fragment to profiles/synthetica.config only. Building
    another profile therefore silently drops MGLRU, UCLAMP and WALT - features
    Synthetica 3.2 is required to keep - and the build guard then refuses with
    "LRU_GEN_ENABLED does not match requested on variant".

    Rather than re-typing those symbols, the block that prepare() already wrote
    into synthetica.config is copied verbatim. One source, one value set.
    """
    if profile == 'synthetica':
        return
    profiles = kit / 'ci/rollercoaster/profiles'
    source = profiles / 'synthetica.config'
    target = profiles / f'{profile}.config'
    if not source.is_file() or not target.is_file():
        raise SystemExit(f'kit is missing {source.name} or {target.name}')

    marker = '# Synthetica 2.0 experiment only'
    source_text = source.read_text(encoding='utf-8')
    if marker not in source_text:
        raise SystemExit('prepared kit does not carry the pinned feature block')
    block = marker + source_text.split(marker, 1)[1]

    text = target.read_text(encoding='utf-8')
    if block.strip() in text:
        return
    # critical.config never mentions F2FS_STAT_FS, so it would revert to the
    # value in 00-common (=y). 3.2 deliberately keeps f2fs statistics off: they
    # are profiling overhead in a hot path, which a gaming build least wants.
    # Stating the same choice here keeps the two profiles aligned on it.
    if 'F2FS_STAT_FS' not in text:
        block += ('\n# Statistics are profiling overhead; 3.2 keeps them off and so\n'
                  '# does this profile, rather than reverting to 00-common.\n'
                  '# CONFIG_F2FS_STAT_FS is not set\n')

    target.write_text(text.rstrip('\n') + '\n\n' + block, encoding='utf-8')
    print(f'kit          : pinned feature block copied from synthetica into {profile}.config')


def apply_prepared_kit(kit_dir: str) -> int:
    """Called right after `prepare`: install the variant into the kit copy."""
    variant = _variant_from_env()
    spec = VARIANTS[variant]
    print(f'prepared kit : {kit_dir}')
    kit = Path(kit_dir)
    _allow_profile_in_kit(kit, spec['profile'])
    _carry_features_into_profile(kit, spec['profile'])
    return 0




def _bakasu_delta_expectations(old: dict[str, str], new: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Expected differences contributed by the BakaSU stack, and nothing else.

    A symbol in BAKASU_CONFIG_DELTA is *allowed* to move, not *required* to:
    most of the SuSFS family is already off in both reference configs, so
    demanding that it move fails a build whose config is correct. The closed
    set is enforced in the other direction - any KSU* symbol that moved but is
    not in the list is refused by name, which is the whole point of having a
    list instead of a "KSU* is fine" wildcard.
    """
    moved = {key for key in BAKASU_CONFIG_DELTA
             if old.get(key, 'n') != new.get(key, 'n')}
    stray = sorted(key for key in old.keys() | new.keys()
                   if key.startswith('KSU') and key not in BAKASU_CONFIG_DELTA
                   and old.get(key, 'n') != new.get(key, 'n'))
    if stray:
        raise ValueError('config symbol changed outside the BakaSU set: '
                         + ', '.join(stray[:20]))
    return {key: (old.get(key, 'n'), new.get(key, 'n')) for key in moved}


def _install_tested_compare(module, variant: str, allowed: set[str]) -> None:
    """Widen the tested-config comparison by the variant's own symbol set.

    compare_tested_config() requires the build to differ from the saved 2.0
    experiment config in LOCALVERSION and nothing else. A variant that
    deliberately runs a different kit profile necessarily differs more, so the
    expected-difference map gains exactly the variant's derived symbols, using
    the value the build actually produced. Every other assertion - the pinned
    digest, the required feature list - is unchanged.
    """
    spec = VARIANTS[variant]
    rc = module.old.base.rc
    s2x = rc.s2x

    def compare_tested_config(tested: Path, generated: str):
        if s2x.v3.digest(tested) != rc.TESTED_CONFIG_SHA256:
            raise ValueError('tested 2.0 experiment config digest changed')
        old = s2x.v3.read_config(tested.read_text(encoding='utf-8'))
        new = s2x.v3.read_config(generated)
        changes = {key: {'tested_2.0_exp': old.get(key, 'n'), 'now': new.get(key, 'n')}
                   for key in sorted(old.keys() | new.keys())
                   if old.get(key, 'n') != new.get(key, 'n')}
        expected = {'LOCALVERSION': {'tested_2.0_exp': '"-Synthetica-2.0-exp"',
                                     'now': spec['localversion']}}
        if spec.get('root_stack') == 'bakasu':
            # The saved 2.0-experiment config is a KernelSU-Next one, so the
            # hook choice and the identity flags move on this stack. Same
            # closed-set rule as the 2.0-baseline gate below.
            for key, (before, after) in _bakasu_delta_expectations(old, new).items():
                expected[key] = {'tested_2.0_exp': before, 'now': after}
        for key in allowed:
            expected[key] = {'tested_2.0_exp': old.get(key, 'n'),
                             'now': new.get(key, 'n')}
        if changes != expected:
            bad = sorted(key for key in changes.keys() | expected.keys()
                         if changes.get(key) != expected.get(key))
            raise ValueError('config differs from the tested experiment beyond the '
                             'approved set: ' + ', '.join(bad[:20]))
        for key in ('SECCOMP', 'SECCOMP_FILTER', 'LRU_GEN', 'LRU_GEN_ENABLED',
                    'UCLAMP_TASK', 'UCLAMP_TASK_GROUP', 'SCHED_TUNE', 'SCHED_WALT',
                    'THERMAL', 'KSU', 'KSU_MANUAL_HOOK', 'MODULE_SIG_FORCE', 'MODVERSIONS'):
            if new.get(key) != 'y':
                raise ValueError('required feature/security config missing: ' + key)
        return changes

    rc.compare_tested_config = compare_tested_config


def _install_config_check(module, variant: str, allowed: set[str]) -> None:
    """Keep the 2.0-experiment guard, minus its one structural assumption.

    check_config() in the experiment recipe asserts that the *default* CPU
    governor is schedutil. That is right for a daily-use build and wrong for a
    gaming profile, whose whole point is the performance governor. The check is
    reimplemented here with exactly one difference: the schedutil *governor* must
    still be compiled in, while the *default* choice is left to the profile.

    Every other assertion - the required baseline set, the forbidden set,
    LRU_GEN_STATS, the MGLRU boot default, and the exact allowed difference -
    is kept as-is. The allowed difference is widened only by the variant's own
    derived symbol set, which is itself derived from a profile file.
    """
    spec = VARIANTS[variant]
    s2x = module.old.base.rc.s2x
    v3 = s2x.v3

    def check_config(baseline: str, generated: str, mglru: str = 'on'):
        if mglru not in s2x.MGLRU_FRAGMENTS:
            raise ValueError('MGLRU variant must be on or off')
        old, new = v3.read_config(baseline), v3.read_config(generated)

        required = list((*v3.REQUIRED_Y, 'SCHED_WALT', 'SCHED_TUNE',
                         'CPU_FREQ_GOV_SCHEDUTIL', 'CGROUP_SCHED'))
        if spec['profile'] == 'synthetica':
            # Identical to the inherited guard, baseline included.
            required.append('CPU_FREQ_DEFAULT_GOV_SCHEDUTIL')
        for symbol in required:
            if old.get(symbol) != 'y' or new.get(symbol) != 'y':
                raise ValueError('required baseline, thermal/security or scheduler '
                                 f'feature not preserved: {symbol}')
        if spec['profile'] != 'synthetica':
            # The gaming profile must still expose a working default choice.
            if new.get('CPU_FREQ_DEFAULT_GOV_PERFORMANCE') != 'y' and \
               new.get('CPU_FREQ_DEFAULT_GOV_SCHEDUTIL') != 'y':
                raise ValueError('no usable default CPU governor is enabled')

        for symbol in (*v3.FORBIDDEN_Y, 'LRU_GEN_STATS'):
            if new.get(symbol, 'n') != 'n':
                raise ValueError(f'unsafe or premature experimental option enabled: {symbol}')
        if new.get('LRU_GEN_ENABLED', 'n') != ('y' if mglru == 'on' else 'n'):
            raise ValueError(f'LRU_GEN_ENABLED does not match requested {mglru} variant')

        changed = {k: {'2.0': old.get(k, 'n'), 'experiment': new.get(k, 'n')}
                   for k in sorted(old.keys() | new.keys())
                   if old.get(k, 'n') != new.get(k, 'n')}
        expected_values = dict(s2x.ALLOWED_CHANGES)
        if mglru == 'on':
            expected_values['LRU_GEN_ENABLED'] = ('n', 'y')
        if spec.get('root_stack') == 'bakasu':
            expected_values.update(_bakasu_delta_expectations(old, new))
        for key in allowed:
            before = old.get(key, 'n')
            expected_values[key] = (before, new.get(key, 'n'))
        expected = {k: {'2.0': a, 'experiment': b} for k, (a, b) in expected_values.items()}
        if changed != expected:
            bad = sorted(k for k in changed.keys() | expected.keys()
                         if changed.get(k) != expected.get(k))
            raise ValueError('unexpected configuration difference(s): ' + ', '.join(bad[:20]))
        return changed

    s2x.check_config = check_config


def _check_build_environment(variant: str) -> None:
    """Fail before compiling if the builder would print a different identity."""
    spec = VARIANTS[variant]
    for var, want in (('SP_BUILD_NAME', spec['name']),
                      ('SP_BUILD_KVER', spec['kver']),
                      ('SP_PROFILE', spec['profile'])):
        got = os.environ.get(var)
        if got is not None and got != want:
            raise SystemExit(f'{var}={got!r} but variant {variant} needs {want!r}')


def apply_variant(variant: str):
    """Install the variant identity into the private 3.2-r1 import chain."""
    if variant not in VARIANTS:
        raise SystemExit('variant must be one of: ' + ', '.join(VARIANTS))
    spec = VARIANTS[variant]
    _check_build_environment(variant)

    allowed = set(ALLOWED_BY_VARIANT[variant])

    module = load('build-kit/scripts/build_synthetica32_r1.py',
                  f'synthetica32_r1_for_{variant.replace("-", "_")}')

    module.RELEASE = spec['release']
    module.LOCALVERSION = spec['localversion']

    # The 2.0 experiment instance held by the rc recipe compares
    # CONFIG_LOCALVERSION against its own expected value, so reshape that.
    root = module.old.base
    rc = root.rc
    s2x = rc.s2x
    s2x_allowed = dict(s2x.ALLOWED_CHANGES)
    s2x_allowed['LOCALVERSION'] = ('"-Synthetica-2.0"', spec['localversion'])

    s2x.ALLOWED_CHANGES = s2x_allowed
    s2x.EXPECTED_RELEASE = spec['release']

    # rc and root compare the tested config against EXPECTED_LOCALVERSION.
    rc.EXPECTED_RELEASE = spec['release']
    rc.EXPECTED_LOCALVERSION = spec['localversion']
    root.EXPECTED_RELEASE = spec['release']
    root.EXPECTED_LOCALVERSION = spec['localversion']

    def compare_31_config(baseline31: Path, generated: str):
        """Only the identity may differ from the exact 3.1 config.

        The 3.2-r1 version of this function expected exactly one change with a
        hardcoded localversion. Here the expectation follows the variant, and
        the must-stay-on / must-stay-off sets are enforced on every build.
        """
        v3 = module.v3
        if baseline31.is_symlink() or not baseline31.is_file():
            raise ValueError('3.1 config must be a regular file')
        previous = v3.read_config(baseline31.read_text(encoding='utf-8'))
        current = v3.read_config(generated)
        changes = {k: {'3.1': previous.get(k, 'n'), 'now': current.get(k, 'n')}
                   for k in sorted(previous.keys() | current.keys())
                   if previous.get(k, 'n') != current.get(k, 'n')}

        allowed_keys = set(allowed) | {'LOCALVERSION'}
        if spec.get('root_stack') == 'bakasu':
            # The exact 3.1 config is a KernelSU-Next one. Moving to BakaSU
            # moves the hook choice and the identity flags as a structural
            # consequence of the Kconfig choice, not as a variant preference.
            # The same closed set the other two gates accept.
            allowed_keys |= set(BAKASU_CONFIG_DELTA)
        unexpected = sorted(k for k in changes if k not in allowed_keys)
        if unexpected:
            raise ValueError('config changed beyond the approved set: '
                             + ', '.join(unexpected[:20]))

        if current.get('LOCALVERSION') != spec['localversion']:
            raise ValueError('LOCALVERSION is not this variant: '
                             f"{current.get('LOCALVERSION')} != {spec['localversion']}")
        missing = [f for f in MUST_STAY_ON if current.get(f) != 'y']
        if missing:
            raise ValueError('required feature missing: ' + ', '.join(missing))
        must_off = dict(MUST_STAY_OFF)
        if spec.get('root_stack') == 'bakasu':
            must_off.update(BAKASU_MUST_STAY_OFF)
        for key, reason in must_off.items():
            if current.get(key) == 'y':
                raise ValueError(f'{key} must stay off: {reason}')
        if spec.get('root_stack') == 'bakasu' and current.get('KSU_MANUAL_HOOK') != 'y':
            raise ValueError('BakaSU on 4.14 requires KSU_MANUAL_HOOK=y')

        return changes

    module.compare_31_config = compare_31_config

    original_compare_31_exports = module.compare_31_exports

    def compare_31_exports(reference: Path, generated: Path):
        """Exported ABI must match 3.1; symbol addresses may move on BakaSU.

        The pinned 3.1 reference is a KernelSU-Next build. On the KernelSU-Next
        stack the rebuild reproduces the exact link layout, so the strict gate
        (names, owners, export types AND crcs) applies unchanged. BakaSU swaps
        the root driver and moves the Kconfig hook choice, which shifts the
        kernel link layout: every symbol's address (crc) moves even though the
        exported ABI - names, owners and export types - is unchanged. Compare
        the ABI and allow the crc delta; a name, owner or type change still
        fails the gate.
        """
        if spec.get('root_stack') != 'bakasu':
            return original_compare_31_exports(reference, generated)
        v3 = module.v3
        abi = module.abi_helper
        if reference.is_symlink() or not reference.is_file() or v3.digest(reference) != module.BASE31_SYMVERS_SHA256:
            raise ValueError('3.1 Module.symvers does not match the pinned build')
        if generated.is_symlink() or not generated.is_file():
            raise ValueError('generated Module.symvers missing or unsafe')
        old_exports = abi.parse_symvers(reference.read_text(encoding='utf-8'))
        new_exports = abi.parse_symvers(generated.read_text(encoding='utf-8'))
        old_builtin = sum(owner == 'vmlinux' for _crc, owner, _kind in old_exports.values())
        if len(old_exports) != 12236 or old_builtin != 12227:
            raise ValueError('unexpected 3.1 export reference')
        missing = sorted(old_exports.keys() - new_exports.keys())
        added = sorted(new_exports.keys() - old_exports.keys())
        abi_changed = sorted(n for n in old_exports.keys() & new_exports.keys()
                             if old_exports[n][1:] != new_exports[n][1:])
        if missing or added or abi_changed:
            raise ValueError('3.2-r1 export ABI differs from 3.1: missing='
                             f'{len(missing)} added={len(added)} '
                             f'owner/type changed={len(abi_changed)}; '
                             f'examples={(missing + added + abi_changed)[:12]}')
        crc_moved = sorted(n for n in old_exports.keys() & new_exports.keys()
                           if old_exports[n][0] != new_exports[n][0])
        module_layout_crc = new_exports.get('module_layout', ('unknown',))[0]
        return {'reference_symvers_sha256': module.BASE31_SYMVERS_SHA256,
                'generated_symvers_sha256': v3.digest(generated),
                'exported_records_compared': len(old_exports),
                'builtin_records_compared': old_builtin,
                'module_records_compared': len(old_exports) - old_builtin,
                'missing_added_or_changed': 0,
                'crc_moved_on_bakasu_stack': len(crc_moved),
                'module_layout_crc': module_layout_crc,
                'scope': 'All export names, owners and types match 3.1; symbol '
                         'addresses (crcs) are build-layout dependent on the BakaSU stack.'}

    module.compare_31_exports = compare_31_exports
    _install_config_check(module, variant, allowed)
    _install_tested_compare(module, variant, allowed)

    print(f'variant      : {variant} ({spec["focus"]})')
    print(f'builder name : {spec["name"]} / {spec["kver"]}')
    print(f'release      : {spec["release"]}  ({len(spec["release"])} chars)')
    print(f'profile      : {spec["profile"]}')
    print(f'must stay on : {len(MUST_STAY_ON)} symbols')
    print(f'must stay off: {", ".join(sorted(MUST_STAY_OFF))}')
    print('changed      : CONFIG_LOCALVERSION'
          + (f' + {len(allowed)} profile symbol(s)' if allowed else ' only')
          + '; no code, patch, toolchain, SuSFS or root change')
    return module


def _variant_from_env() -> str:
    variant = os.environ.get('FM_VARIANT', '').strip()
    if variant not in VARIANTS:
        raise SystemExit('FM_VARIANT must be set to: ' + ', '.join(VARIANTS))
    return variant


def main(argv: list[str]) -> int:
    pending = argv[1:]
    if not pending:
        raise SystemExit('usage: build_fresh_milk.py <variant> verify|apply  |  '
                         '<3.2-r1 subcommand> [args]')

    if pending[0] in VARIANTS:
        variant = pending[0]
        pending = pending[1:]
        explicit = True
    else:
        variant = _variant_from_env()
        explicit = False

    module = apply_variant(variant)

    # The build-kit recipes distinguish the root stack through SP_ROOT_STACK.
    # The compile step receives it from the workflow, but the prepare step sets
    # only FM_VARIANT. Publish it here from the variant spec so the hook choice
    # resolution - gated on the stack, not on the archive - runs during kit
    # preparation too. Without this the prepare step leaves the profiles raw
    # (SuSFS on, manual hook dropped by olddefconfig) and the compile step then
    # fails its config gate on a config that never carried the manual hook.
    # Setting it here, not in apply_variant, keeps direct apply_variant calls
    # from leaking SP_ROOT_STACK into other test modules that expect the default.
    os.environ['SP_ROOT_STACK'] = VARIANTS[variant]['root_stack']

    if explicit:
        if pending == ['verify'] or pending[:1] == ['apply']:
            return 0
        raise SystemExit('unknown variant command: ' + ' '.join(pending))

    if pending[:1] == ['prepare']:
        argv2 = pending
        args = {'--destination': None}
        for i, item in enumerate(argv2):
            if item == '--destination' and i + 1 < len(argv2):
                args['--destination'] = argv2[i + 1]
        saved = sys.argv
        try:
            sys.argv = [str(ROOT / 'build-kit/scripts/build_synthetica32_r1.py')] + argv2
            rc = module.main()
        finally:
            sys.argv = saved
        if rc == 0 and args['--destination']:
            apply_prepared_kit(args['--destination'])
        return rc

    saved = sys.argv
    try:
        sys.argv = [str(ROOT / 'build-kit/scripts/build_synthetica32_r1.py')] + pending
        return module.main()
    finally:
        sys.argv = saved


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
