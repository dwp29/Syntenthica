#!/usr/bin/env python3
"""Rebuild the 3.0 root-path kernel as 3.1 with only LOCALVERSION changed.

Builds in a disposable tree using the pinned 3.0 recipe and toolchain. The
result is a *new* kernel binary and module-signing certificate; a user-reported
boot of the earlier 3.0 package does not validate this 3.1 image on a device.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '4.14.357-openela-synthetica-3.1'
LOCALVERSION = '"-synthetica-3.1"'
BASE30_LOCALVERSION = '"-synthetica-3.0"'
BASE30_CONFIG_SHA256 = '253a89a338e8c5b71da71b698a0160d9fb361468cfac3a3bfc7fae2c52f4af2d'
BASE30_IMAGE_SHA256 = '92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb'
BASE30_MODULE_CERT_SHA256 = 'fccecddc68e8828ff42c59be08f3aca01baf1f07e9caf8369ce69e8fad4bd062'
STATUS_KIND = 'SYNTHETICA_3_1_REBUILT_KERNEL_NOT_DEVICE_VALIDATED'


def load_root():
    spec = importlib.util.spec_from_file_location('synthetica30_for_31',
                                                  ROOT / 'build-kit/scripts/build_synthetica3_root.py')
    if spec is None or spec.loader is None:
        raise ValueError('cannot load 3.0 build recipe')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Mutate only the private imported copy: the 3.0 build and its pins stay intact.
    module.EXPECTED_RELEASE = RELEASE
    module.EXPECTED_LOCALVERSION = LOCALVERSION
    module.STATUS_KIND = STATUS_KIND
    module.rc.EXPECTED_RELEASE = RELEASE
    module.rc.EXPECTED_LOCALVERSION = LOCALVERSION
    module.rc.s2x.EXPECTED_RELEASE = RELEASE
    module.rc.s2x.ALLOWED_CHANGES = dict(module.rc.s2x.ALLOWED_CHANGES)
    module.rc.s2x.ALLOWED_CHANGES['LOCALVERSION'] = ('"-Synthetica-2.0"', LOCALVERSION)
    return module


base = load_root()


def compare_30_config(baseline30: Path, generated: str) -> dict[str, dict[str, str]]:
    if baseline30.is_symlink() or not baseline30.is_file():
        raise ValueError('3.0 build config must be a regular file')
    if base.rc.s2x.v3.digest(baseline30) != BASE30_CONFIG_SHA256:
        raise ValueError('3.0 build config hash mismatch')
    parser = base.rc.s2x.v3.read_config
    old = parser(baseline30.read_text(encoding='utf-8'))
    new = parser(generated)
    changes = {key: {'3.0': old.get(key, 'n'), '3.1': new.get(key, 'n')}
               for key in sorted(old.keys() | new.keys())
               if old.get(key, 'n') != new.get(key, 'n')}
    expected = {'LOCALVERSION': {'3.0': BASE30_LOCALVERSION, '3.1': LOCALVERSION}}
    if changes != expected:
        bad = [key for key in sorted(changes.keys() | expected.keys())
               if changes.get(key) != expected.get(key)]
        raise ValueError('3.1 differs from the exact 3.0 config beyond LOCALVERSION: ' + ', '.join(bad[:20]))
    return changes


def check_config(baseline20: Path, generated: Path, tested20: Path,
                 baseline30: Path, mglru: str) -> dict[str, object]:
    base.check_inputs()
    original = base.rc.check_config(baseline20, generated, tested20, mglru)
    return {'inherited_3_0_checks': original,
            'changes_from_original_3_0': compare_30_config(baseline30, generated.read_text(encoding='utf-8'))}


def prepare(source: Path, destination: Path, baseline20: Path) -> None:
    base.prepare(source, destination, baseline20)


def finish(kit: Path, out: Path, baseline20: Path, tested20: Path, baseline30: Path,
           result: Path, toolchain: Path, archive: Path) -> None:
    # Check the exact 3.0 build config before writing any final output.
    changes = compare_30_config(baseline30, (out / '.config').read_text(encoding='utf-8'))
    base.finish(kit, out, baseline20, tested20, result, toolchain, archive)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    status.update({
        'kind': STATUS_KIND,
        'candidate': '3.1 recompiled kernel; physical boot and ROM compatibility NOT VERIFIED',
        'baseline_3_0_image_sha256': BASE30_IMAGE_SHA256,
        'baseline_3_0_config_sha256': BASE30_CONFIG_SHA256,
        'baseline_3_0_module_cert_sha256': BASE30_MODULE_CERT_SHA256,
        'changes_from_original_3_0_config': changes,
        'previous_3_0_2_0_installer_report': 'User reports a previously Error 1-affected user now boots; ROM, installed bytes and broad compatibility not independently verified.',
        'physical_boot_test_this_3_1_image': 'NOT RUN',
        'module_cert_note': 'New compilation creates a different auto-generated module signing certificate; ROM module trust must not be assumed.',
    })
    status_path.write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    (result / 'README-DO-NOT-FLASH.txt').write_text(
        'Synthetica 3.1 compile evidence only. The newly built kernel has not been physically boot tested.\n'
        'The prior 3.0+2.0-installer user report does not prove this image, AVB or ROM module trust.\n'
        'Only the public module-signing certificate is exported.\n', encoding='utf-8')
    print(json.dumps(status, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('source', 'destination', 'baseline'):
        prep.add_argument('--' + name, required=True, type=Path)
    tree = sub.add_parser('prepare-tree')
    tree.add_argument('--tree', required=True, type=Path)
    cfg = sub.add_parser('check-config')
    for name in ('baseline', 'generated'):
        cfg.add_argument('--' + name, required=True, type=Path)
    cfg.add_argument('--mglru', default='on')
    cfg.add_argument('--tested-config', type=Path,
                     default=Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None)
    cfg.add_argument('--baseline30', type=Path,
                     default=Path(os.environ['S31_BASELINE_CONFIG']) if os.environ.get('S31_BASELINE_CONFIG') else None)
    done = sub.add_parser('finish')
    for name in ('kit', 'out', 'baseline', 'tested-config', 'baseline30', 'result', 'toolchain-bin', 'neutron-archive'):
        done.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.baseline)
    elif args.command == 'prepare-tree':
        base.prepare_tree(args.tree)
    elif args.command == 'check-config':
        if args.tested_config is None or args.baseline30 is None:
            raise ValueError('both pinned tested-2.0 and exact 3.0 config files are required')
        print(json.dumps(check_config(args.baseline, args.generated, args.tested_config, args.baseline30, args.mglru), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.tested_config, args.baseline30,
               args.result, args.toolchain_bin, args.neutron_archive)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f'Synthetica 3.1 build refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
