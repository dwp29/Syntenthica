#!/usr/bin/env python3
"""Build a guarded Synthetica 3.0 root-path candidate; not device-validated.

The rc1 inputs and all of its config, Manager, compiler and module guards are
retained. A second, tightly scoped patch installs an ordinary CLOEXEC driver fd
only after the recognized Manager successfully execs its libksud.so helper.
The inherited seccomp filter and existing ioctl authorization are unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'build-kit/ci/synthetica3-root/0001-manager-fd-after-exec.patch'
PATCH_SHA256 = '88ca9b4439c5250cb23f1d83bb3e7709eaecca5a19f495733eef75889032f97d'
SOURCE_HASHES = {
    'fs/exec.c': ('7b4aa0bfc6500ff63ce38609dd116a9dfc5fad7e242a37308328252d78ebe1aa',
                  '01212931effe732e4a0530c1009ab41585eecc3933f01dd5d8a58f2ae068865a'),
    'KernelSU-Next/kernel/supercall/supercall.c':
        ('d7c271b34c496d1e760ea977bf2830b72881f19fe3748197d3a8634b2835cba6',
         'fe4d76bd6283ca28db0b4fb5a86c6afb320d870b3f5e832b26e0675b7f837016'),
}
EXPECTED_RELEASE = '4.14.357-openela-synthetica-3.0'
EXPECTED_LOCALVERSION = '"-synthetica-3.0"'
STATUS_KIND = 'SYNTHETICA_3_0_COMPILED_ONLY_DO_NOT_FLASH'


def load_rc():
    spec = importlib.util.spec_from_file_location('synthetica3_rc_for_root_candidate',
                                                  ROOT / 'build-kit/scripts/build_synthetica3_rc.py')
    if spec is None or spec.loader is None:
        raise ValueError('rc1 build guards could not be loaded')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Private imports only; neither the rc1 recipe nor its immutable pins change.
    module.EXPECTED_RELEASE = EXPECTED_RELEASE
    module.EXPECTED_LOCALVERSION = EXPECTED_LOCALVERSION
    module.s2x.EXPECTED_RELEASE = EXPECTED_RELEASE
    module.s2x.ALLOWED_CHANGES = dict(module.s2x.ALLOWED_CHANGES)
    module.s2x.ALLOWED_CHANGES['LOCALVERSION'] = ('"-Synthetica-2.0"', EXPECTED_LOCALVERSION)
    return module


rc = load_rc()


def check_inputs() -> None:
    rc.check_inputs()
    if rc.s2x.v3.digest(PATCH) != PATCH_SHA256:
        raise ValueError('Manager helper exec patch digest changed')


def verify_root_source(tree: Path, patched: bool) -> None:
    for name, hashes in SOURCE_HASHES.items():
        if rc.s2x.v3.digest(tree / name) != hashes[1 if patched else 0]:
            raise ValueError('unexpected Manager helper source: ' + name)


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    check_inputs()
    rc.prepare(source, destination, baseline)
    driver = destination / 'scripts/build_chronicle_base.py'
    text = rc.s2x.replace_once(driver.read_text(encoding='utf-8'),
        '3.0-rc1 compiled; verification and device tests still required',
        '3.0 root-path candidate compiled; verification and device tests still required')
    driver.write_text(text, encoding='utf-8')


def prepare_tree(tree: Path) -> None:
    check_inputs()
    tree = rc.s2x.ensure_disposable(tree)
    verify_root_source(tree, patched=False)
    rc.prepare_tree(tree)
    subprocess.run(['git', 'apply', '--check', str(PATCH)], cwd=tree, check=True)
    subprocess.run(['git', 'apply', str(PATCH)], cwd=tree, check=True)
    verify_root_source(tree, patched=True)
    print('Applied Manager-only post-exec driver-fd patch', flush=True)


def verify_exec_objects(out: Path) -> dict[str, object]:
    objdump = '/usr/bin/aarch64-linux-gnu-objdump'
    exec_obj = out / 'fs/exec.o'
    driver_obj = out / 'drivers/kernelsu/supercall/supercall.o'
    relocations = subprocess.run([objdump, '-r', str(exec_obj)], check=True, text=True,
                                 capture_output=True).stdout
    symbols = subprocess.run([objdump, '-t', str(driver_obj)], check=True, text=True,
                             capture_output=True).stdout
    if not re.search(r'\bksu_install_manager_exec_fd\b', relocations):
        raise ValueError('compiled exec object does not call the Manager helper hook')
    if not re.search(r'\bksu_install_manager_exec_fd\s*$', symbols, re.MULTILINE):
        raise ValueError('compiled KernelSU object is missing the Manager helper hook')
    return {'fs_exec_sha256': rc.s2x.v3.digest(exec_obj),
            'ksu_supercall_sha256': rc.s2x.v3.digest(driver_obj),
            'symbol': 'ksu_install_manager_exec_fd',
            'note': 'static compiled-object check, not Android/device execution'}


def finish(kit: Path, out: Path, baseline: Path, tested: Path, result: Path,
           toolchain_bin: Path, neutron_archive: Path) -> None:
    check_inputs()
    out = rc.s2x.ensure_disposable(out)
    verify_root_source(out.parent, patched=True)
    objects = verify_exec_objects(out)
    # rc1 finish verifies both rc1 source hashes, full config, embedded identity,
    # image, toolchain, signed same-build modules, and public certificate.
    rc.finish(kit, out, baseline, tested, result, toolchain_bin, neutron_archive)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    status.update({
        'kind': STATUS_KIND,
        'candidate': '3.0 Manager root-path candidate; NOT a device-validated stable release',
        'manager_exec_fd_patch_sha256': PATCH_SHA256,
        'manager_exec_fd_objects': objects,
        'manager_exec_fd_scope': (
            'After successful libksud.so exec by the recognized Manager UID, install an ordinary '
            'O_CLOEXEC driver fd. Existing ioctl authorization and inherited Manager seccomp '
            'remain unchanged; no su-session fd and no filter bypass.'),
        'manager_root_cause': 'HYPOTHESIS based on rc1 source and upstream helper; installed APK/ROM and on-device logs not verified',
        'root_after_patch': 'NOT DEVICE TESTED; other failure causes remain possible',
    })
    status_path.write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    (result / 'README-DO-NOT-FLASH.txt').write_text(
        '3.0 ROOT-PATH CANDIDATE COMPILE EVIDENCE ONLY; no installer is included here.\n'
        'The Manager helper fd change is a tested source-level hypothesis, not a proven device fix.\n'
        'Physical boot, Manager root, seccomp, AVB, ROM modules and camera remain unverified.\n',
        encoding='utf-8')
    print(json.dumps(status, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('source', 'destination', 'baseline'):
        prep.add_argument('--' + name, required=True, type=Path)
    tree = sub.add_parser('prepare-tree')
    tree.add_argument('--tree', required=True, type=Path)
    cfg = sub.add_parser('check-config')
    cfg.add_argument('--baseline', required=True, type=Path)
    cfg.add_argument('--generated', required=True, type=Path)
    cfg.add_argument('--mglru', default='on')
    cfg.add_argument('--tested-config', type=Path,
                     default=Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None)
    done = sub.add_parser('finish')
    for name in ('kit', 'out', 'baseline', 'tested-config', 'result', 'toolchain-bin', 'neutron-archive'):
        done.add_argument('--' + name, required=True, type=Path)
    args = p.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.baseline)
    elif args.command == 'prepare-tree':
        prepare_tree(args.tree)
    elif args.command == 'check-config':
        if args.tested_config is None:
            raise ValueError('tested experiment config is required')
        check_inputs()
        print(json.dumps(rc.check_config(args.baseline, args.generated, args.tested_config, args.mglru), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.tested_config, args.result,
               args.toolchain_bin, args.neutron_archive)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f'3.0 root candidate build refused: {exc}', file=sys.stderr)
        sys.exit(1)
