#!/usr/bin/env python3
"""Build 3.2-r1 from 3.1, keeping its features and adding bounded MGLRU guards.

The prior 3.2 baseline experiment is NOT the basis of this build. The release
suffix distinguishes their incompatible module ABI. Full config and exported
symbol checks are tied to exact 3.1 evidence. No device/ROM boot is implied.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '4.14.357-openela-synthetica-3.2-r1'
LOCALVERSION = '"-synthetica-3.2-r1"'
BASE31_LOCALVERSION = '"-synthetica-3.1"'
BASE31_CONFIG_SHA256 = '4b53a2cb030e9aa55ff798a3ee5c773c0eb50e56cd36430d2874adcb56fa236d'
BASE31_SYMVERS_SHA256 = '1ce7153529b53f3f4bf361ea2e061ec575e712cd47cc5a0f10a854cf91d19ac3'
BASE31_IMAGE_SHA256 = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
BASE31_CERT_SHA256 = '6d8ab0c34f5052d098c801841d34976a75ef9c3fed53e3630376dc2b0f93b72e'
PATCH = ROOT / 'build-kit/ci/synthetica32-r1/0001-mglru-safety-guards.patch'
PATCH_SHA256 = '59450715255a96893963d1470cffb6a4b9250b807a63e30e532be13707e4a0a0'
SOURCE_BEFORE = 'bc5ba78d4050b4e52bd1b721ba05d6b1c76a9856cfdb21ddc5194d5ce7b9abe6'
SOURCE_AFTER = 'ccba650e0c2c7b4fbd2fbc1bbf9af35e9429eb3d7e92d3afdb74e1dfe36400b8'
STATUS_KIND = 'SYNTHETICA_3_2_R1_FROM_3_1_COMPILED_NOT_DEVICE_VALIDATED'


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('cannot load pinned 3.1 build guards')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load(ROOT / 'build-kit/scripts/build_synthetica31.py', 'synthetica31_for_32_r1')
# Configure only the private imported guard chain, leaving 3.1 sources intact.
old.base.EXPECTED_RELEASE = RELEASE
old.base.EXPECTED_LOCALVERSION = LOCALVERSION
old.base.STATUS_KIND = STATUS_KIND
old.base.rc.EXPECTED_RELEASE = RELEASE
old.base.rc.EXPECTED_LOCALVERSION = LOCALVERSION
old.base.rc.s2x.EXPECTED_RELEASE = RELEASE
old.base.rc.s2x.ALLOWED_CHANGES = dict(old.base.rc.s2x.ALLOWED_CHANGES)
old.base.rc.s2x.ALLOWED_CHANGES['LOCALVERSION'] = ('"-Synthetica-2.0"', LOCALVERSION)
base = old.base
v3 = base.rc.s2x.v3
modules = base.rc.s2x.modules
abi_helper = load(ROOT / 'build-kit/scripts/build_synthetica32.py', 'synthetica32_abi_for_r1')


def check_inputs() -> None:
    base.check_inputs()
    if PATCH.is_symlink() or not PATCH.is_file() or v3.digest(PATCH) != PATCH_SHA256:
        raise ValueError('3.2-r1 MGLRU guard patch digest changed')


def compare_31_config(baseline31: Path, generated: str) -> dict[str, dict[str, str]]:
    if baseline31.is_symlink() or not baseline31.is_file() or v3.digest(baseline31) != BASE31_CONFIG_SHA256:
        raise ValueError('3.1 config is missing, unsafe or does not match the pin')
    previous = v3.read_config(baseline31.read_text(encoding='utf-8'))
    current = v3.read_config(generated)
    changes = {key: {'3.1': previous.get(key, 'n'), '3.2-r1': current.get(key, 'n')}
               for key in sorted(previous.keys() | current.keys())
               if previous.get(key, 'n') != current.get(key, 'n')}
    expected = {'LOCALVERSION': {'3.1': BASE31_LOCALVERSION, '3.2-r1': LOCALVERSION}}
    if changes != expected:
        bad = sorted(key for key in changes.keys() | expected.keys() if changes.get(key) != expected.get(key))
        raise ValueError('3.2-r1 differs from 3.1 config beyond LOCALVERSION: ' + ', '.join(bad[:20]))
    for feature in ('LRU_GEN', 'LRU_GEN_ENABLED', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP', 'SCHED_WALT',
                    'SCHED_TUNE', 'KSU', 'KSU_MANUAL_HOOK', 'KSU_SUSFS', 'NOMOUNT', 'SECCOMP',
                    'SECCOMP_FILTER', 'MODULE_SIG_FORCE', 'MODVERSIONS', 'SECURITY_SELINUX', 'DM_VERITY'):
        if current.get(feature) != 'y':
            raise ValueError('3.1 feature/security config missing: ' + feature)
    if current.get('MODULE_FORCE_LOAD', 'n') != 'n':
        raise ValueError('module force-load must remain disabled')
    return changes


def compare_31_exports(reference: Path, generated: Path) -> dict[str, object]:
    if reference.is_symlink() or not reference.is_file() or v3.digest(reference) != BASE31_SYMVERS_SHA256:
        raise ValueError('3.1 Module.symvers does not match the pinned build')
    if generated.is_symlink() or not generated.is_file():
        raise ValueError('generated Module.symvers missing or unsafe')
    old_exports = abi_helper.parse_symvers(reference.read_text(encoding='utf-8'))
    new_exports = abi_helper.parse_symvers(generated.read_text(encoding='utf-8'))
    old_builtin = sum(owner == 'vmlinux' for _crc, owner, _kind in old_exports.values())
    if len(old_exports) != 12236 or old_builtin != 12227 or \
       old_exports.get('module_layout') != ('0xed5659d1', 'vmlinux', 'EXPORT_SYMBOL'):
        raise ValueError('unexpected 3.1 export reference')
    missing, added = sorted(old_exports.keys() - new_exports.keys()), sorted(new_exports.keys() - old_exports.keys())
    changed = sorted(n for n in old_exports.keys() & new_exports.keys() if old_exports[n] != new_exports[n])
    if missing or added or changed:
        raise ValueError(f'3.2-r1 export ABI differs from 3.1: missing={len(missing)} '
                         f'added={len(added)} changed={len(changed)}; examples={(missing+added+changed)[:12]}')
    return {'reference_symvers_sha256': BASE31_SYMVERS_SHA256,
            'generated_symvers_sha256': v3.digest(generated),
            'exported_records_compared': len(old_exports), 'builtin_records_compared': old_builtin,
            'module_records_compared': len(old_exports)-old_builtin, 'missing_added_or_changed': 0,
            'module_layout_crc': '0xed5659d1',
            'scope': 'All export names, owners, types and CRCs match 3.1; ROM modules and runtime trust not established.'}


def check_config(baseline20: Path, generated: Path, tested20: Path, baseline31: Path, mglru: str) -> dict[str, object]:
    check_inputs()
    inherited = base.rc.check_config(baseline20, generated, tested20, mglru)
    return {'retained_3_1_guards': inherited,
            'changes_from_exact_3_1': compare_31_config(baseline31, generated.read_text(encoding='utf-8'))}


def prepare(source: Path, destination: Path, baseline20: Path) -> None:
    check_inputs()
    base.prepare(source, destination, baseline20)
    driver = destination / 'scripts/build_chronicle_base.py'
    text = driver.read_text(encoding='utf-8')
    before = '3.0 root-path candidate compiled; verification and device tests still required'
    if text.count(before) != 1:
        raise ValueError('unexpected inherited 3.1 driver layout')
    driver.write_text(text.replace(before, '3.2-r1 compiled; verification and device tests still required', 1), encoding='utf-8')


def verify_vmscan(tree: Path, patched: bool) -> None:
    path = tree / 'mm/vmscan.c'
    if path.is_symlink() or not path.is_file() or v3.digest(path) != (SOURCE_AFTER if patched else SOURCE_BEFORE):
        raise ValueError('unexpected pinned 3.1 MGLRU source or safety patch')


def prepare_tree(tree: Path) -> None:
    check_inputs()
    tree = base.rc.s2x.ensure_disposable(tree)
    base.prepare_tree(tree)  # 3.1 MGLRU/UCLAMP, seccomp and Manager fd patches
    verify_vmscan(tree, patched=False)
    subprocess.run(['git', 'apply', '--check', str(PATCH)], cwd=tree, check=True)
    subprocess.run(['git', 'apply', str(PATCH)], cwd=tree, check=True)
    verify_vmscan(tree, patched=True)
    print('Applied 3.2-r1 MGLRU input and cleanup guards; 3.1 features retained.', flush=True)


def finish(kit: Path, out: Path, baseline20: Path, tested20: Path, baseline31: Path,
           symvers31: Path, result: Path, toolchain: Path, neutron: Path) -> None:
    check_inputs()
    if result.exists() or result.is_symlink():
        raise ValueError('refusing to overwrite an existing result')
    out = base.rc.s2x.ensure_disposable(out)
    verify_vmscan(out.parent, patched=True)
    config = (out / '.config').read_bytes()
    changes = compare_31_config(baseline31, config.decode('utf-8'))
    abi = compare_31_exports(symvers31, out / 'Module.symvers')
    base.finish(kit, out, baseline20, tested20, result, toolchain, neutron)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    if status.get('image_sha256') == BASE31_IMAGE_SHA256:
        raise ValueError('3.2-r1 image must not be the archived 3.1 image')
    if status.get('module_public_cert_sha256') == BASE31_CERT_SHA256:
        raise ValueError('unexpected previous module certificate reuse')
    # Preserve the six already validated modules alongside this exact build.
    with gzip.open(result / 'Image.gz.DO-NOT-FLASH', 'rb') as f:
        raw = f.read(v3.MAX_RAW_IMAGE + 1)
    if len(raw) > v3.MAX_RAW_IMAGE:
        raise ValueError('uncompressed image exceeds limit')
    cert = (result / 'module-signing-public-cert.x509').read_bytes()
    stage = out / 'synthetica2-experimental-modules/lib/modules' / RELEASE / 'kernel'
    checked = modules.collect(stage, config=v3.read_config(config.decode('utf-8')), release=RELEASE,
                              certificate_der=cert, raw_kernel=raw,
                              symvers_text=(out / 'Module.symvers').read_text(encoding='utf-8'))
    (result / 'signed-modules').mkdir()
    for name, (data, details) in checked.items():
        if details != status['same_build_modules_static_checks'][name]:
            raise ValueError('same-build module verification changed: ' + name)
        (result / 'signed-modules' / (name + '.ko')).write_bytes(data)
    # Inherited status mentions old builds; do not pass unrelated historical
    # user reports or the rc1 labels off as evidence for this candidate.
    for key in ('camera_0_6x', 'previous_2_0_experiment_user_report'):
        status.pop(key, None)
    tested_delta = status.get('config_comparison', {}).get('changes_from_user_tested_experiment', {})
    if 'LOCALVERSION' in tested_delta:
        values = tested_delta['LOCALVERSION']
        if '3.0_rc1' in values:
            values['3.2-r1'] = values.pop('3.0_rc1')
    status.update({
        'kind': STATUS_KIND,
        'candidate': '3.2-r1 derived from 3.1; physical boot and ROM compatibility NOT VERIFIED',
        'baseline_3_1_image_sha256': BASE31_IMAGE_SHA256,
        'baseline_3_1_config_sha256': BASE31_CONFIG_SHA256,
        'baseline_3_1_module_public_cert_sha256': BASE31_CERT_SHA256,
        'changes_from_exact_3_1_config': changes,
        'export_abi_against_3_1': abi,
        'mglru_guard_patch_sha256': PATCH_SHA256,
        'mglru_guard_source_before_sha256': SOURCE_BEFORE,
        'mglru_guard_source_after_sha256': SOURCE_AFTER,
        'mglru_guard_scope': ['Reject negative spread values; valid 0..MAX_NR_GENS-1 unchanged.',
                              'Free and clear the MGLRU walker allocation if kswapd fails to start.'],
        'mglru_guard_limitations': 'Static/host-tested defensive edge cases; neither is a proven cause of any Android 17 boot failure.',
        'physical_boot_test_this_image': 'NOT RUN',
        'rom_module_abi_and_runtime_keyring': 'NOT VERIFIED',
        'avb_ramdisk_dtb_dtbo_recovery': 'NOT VERIFIED',
        'previous_3_2_baseline_experiment': 'Superseded; different source, features and module ABI. Do not mix modules.',
        'module_cert_note': 'Fresh build certificate; whether ROM module signers are trusted is unknown.',
    })
    status_path.write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    (result / 'README-DO-NOT-FLASH.txt').write_text(
        'DO NOT FLASH. 3.2-r1 is built from 3.1 with MGLRU/UCLAMP and root-path patches retained.\n'
        'The kernel includes two narrow MGLRU defensive checks, not a proven Android 17 boot fix.\n'
        'ROM modules, signature trust, AVB, physical boot, root and hardware remain unverified.\n'
        'This evidence is NOT a recovery installer or a complete boot image.\n', encoding='utf-8')
    paths = sorted(p for p in result.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (result / 'SHA256SUMS.txt').write_text(''.join(f'{v3.digest(p)}  {p.relative_to(result).as_posix()}\n'
                                                  for p in paths), encoding='utf-8')
    print(json.dumps(status, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('source', 'destination', 'baseline'):
        prep.add_argument('--'+name, required=True, type=Path)
    tree = sub.add_parser('prepare-tree')
    tree.add_argument('--tree', required=True, type=Path)
    cfg = sub.add_parser('check-config')
    for name in ('baseline', 'generated'):
        cfg.add_argument('--'+name, required=True, type=Path)
    cfg.add_argument('--mglru', default='on')
    cfg.add_argument('--tested-config', type=Path, default=Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None)
    cfg.add_argument('--baseline31', type=Path, default=Path(os.environ['S31_EXACT_CONFIG']) if os.environ.get('S31_EXACT_CONFIG') else None)
    done = sub.add_parser('finish')
    for name in ('kit', 'out', 'baseline', 'tested-config', 'baseline31', 'symvers31', 'result', 'toolchain-bin', 'neutron-archive'):
        done.add_argument('--'+name, required=True, type=Path)
    args = p.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.baseline)
    elif args.command == 'prepare-tree':
        prepare_tree(args.tree)
    elif args.command == 'check-config':
        if args.tested_config is None or args.baseline31 is None:
            raise ValueError('exact 3.1 and tested 2.0 experiment config paths are required')
        print(json.dumps(check_config(args.baseline, args.generated, args.tested_config, args.baseline31, args.mglru), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.tested_config, args.baseline31, args.symvers31,
               args.result, args.toolchain_bin, args.neutron_archive)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError, KeyError) as exc:
        print(f'Synthetica 3.2-r1 build refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
