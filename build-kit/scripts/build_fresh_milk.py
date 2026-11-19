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
    'fresh-milk': {
        'name': 'Fresh-Milk',
        'kver': '14.03',
        'localversion': '"-Fresh-Milk-14.03"',
        'release': '4.14.357-openela-Fresh-Milk-14.03',
        'profile': 'synthetica',
        'focus': 'stability',
    },
    'cheese-burger': {
        'name': 'CHEESE-BURGER',
        'kver': '11.08',
        'localversion': '"-CHEESE-BURGER-11.08"',
        'release': '4.14.357-openela-CHEESE-BURGER-11.08',
        'profile': 'synthetica',
        'focus': 'gaming-performance',
    },
}

# No config symbol may differ from the 2.0 baseline except the identity.
ALLOWED = {}

# Symbols that must be present in the final .config. The last three were
# verified to be already enabled in the 2.0 baseline, so they are guards,
# not changes.
MUST_STAY_ON = (
    'LRU_GEN', 'LRU_GEN_ENABLED', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP',
    'SCHED_WALT', 'SCHED_TUNE', 'KSU', 'KSU_MANUAL_HOOK', 'KSU_SUSFS',
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


def load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    module = load('build-kit/scripts/build_synthetica32_r1.py',
                  f'synthetica32_r1_for_{variant.replace("-", "_")}')

    module.RELEASE = spec['release']
    module.LOCALVERSION = spec['localversion']

    # The 2.0 experiment instance held by the rc recipe compares
    # CONFIG_LOCALVERSION against its own expected value, so reshape that.
    root = module.old.base
    rc = root.rc
    s2x = rc.s2x
    allowed = dict(s2x.ALLOWED_CHANGES)
    allowed['LOCALVERSION'] = ('"-Synthetica-2.0"', spec['localversion'])
    s2x.ALLOWED_CHANGES = allowed
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

        allowed_keys = set(ALLOWED) | {'LOCALVERSION'}
        unexpected = sorted(k for k in changes if k not in allowed_keys)
        if unexpected:
            raise ValueError('config changed beyond the variant identity: '
                             + ', '.join(unexpected[:20]))

        if current.get('LOCALVERSION') != spec['localversion']:
            raise ValueError('LOCALVERSION is not this variant: '
                             f"{current.get('LOCALVERSION')} != {spec['localversion']}")
        for key, (_before, after) in ALLOWED.items():
            if current.get(key, 'n') != after:
                raise ValueError(f'{key} was not reached: '
                                 f"{current.get(key, 'n')} != {after}")

        missing = [f for f in MUST_STAY_ON if current.get(f) != 'y']
        if missing:
            raise ValueError('required feature missing: ' + ', '.join(missing))
        for key, reason in MUST_STAY_OFF.items():
            if current.get(key) == 'y':
                raise ValueError(f'{key} must stay off: {reason}')

        return changes

    module.compare_31_config = compare_31_config

    print(f'variant      : {variant} ({spec["focus"]})')
    print(f'builder name : {spec["name"]} / {spec["kver"]}')
    print(f'release      : {spec["release"]}  ({len(spec["release"])} chars)')
    print(f'profile      : {spec["profile"]}')
    print(f'must stay on : {len(MUST_STAY_ON)} symbols')
    print(f'must stay off: {", ".join(sorted(MUST_STAY_OFF))}')
    print('changed      : CONFIG_LOCALVERSION only; no code, patch, toolchain,'
          ' SuSFS or root change')
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

    if explicit:
        if pending == ['verify'] or pending[:1] == ['apply']:
            return 0
        raise SystemExit('unknown variant command: ' + ' '.join(pending))

    saved = sys.argv
    try:
        sys.argv = [str(ROOT / 'build-kit/scripts/build_synthetica32_r1.py')] + pending
        return module.main()
    finally:
        sys.argv = saved


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
