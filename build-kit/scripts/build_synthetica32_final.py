#!/usr/bin/env python3
"""Rebuild the device-verified 3.1 kernel as 3.2 with only LOCALVERSION changed.

Preserves 100% of the 3.0/3.1 source tree, patches (MGLRU, UCLAMP, KernelSU-Next
Rollercoaster 34000 manual hook, Manager seccomp & post-exec driver-fd),
Neutron Clang 18 toolchain, and .config symbols, changing only
CONFIG_LOCALVERSION from "-synthetica-3.1" to "-synthetica-3.2". Also verifies
that all 12,236 exported symbols and CRCs in Module.symvers match 3.1 and saves
the six signed same-build modules for future development.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '4.14.357-openela-synthetica-3.2'
LOCALVERSION = '"-synthetica-3.2"'
BASE31_LOCALVERSION = '"-synthetica-3.1"'
BASE31_CONFIG_SHA256 = '4b53a2cb030e9aa55ff798a3ee5c773c0eb50e56cd36430d2874adcb56fa236d'
BASE31_IMAGE_SHA256 = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
BASE31_MODULE_CERT_SHA256 = '6d8ab0c34f5052d098c801841d34976a75ef9c3fed53e3630376dc2b0f93b72e'
BASE31_SYMVERS_SHA256 = '1ce7153529b53f3f4bf361ea2e061ec575e712cd47cc5a0f10a854cf91d19ac3'
STATUS_KIND = 'SYNTHETICA_3_2_RELEASE_BUILD_FROM_PROVEN_3_1'


def load_s31():
    spec = importlib.util.spec_from_file_location('synthetica31_for_32',
                                                  ROOT / 'build-kit/scripts/build_synthetica31.py')
    if spec is None or spec.loader is None:
        raise ValueError('cannot load 3.1 build recipe')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RELEASE = RELEASE
    module.LOCALVERSION = LOCALVERSION
    module.STATUS_KIND = STATUS_KIND
    module.base.EXPECTED_RELEASE = RELEASE
    module.base.EXPECTED_LOCALVERSION = LOCALVERSION
    module.base.STATUS_KIND = STATUS_KIND
    module.base.rc.EXPECTED_RELEASE = RELEASE
    module.base.rc.EXPECTED_LOCALVERSION = LOCALVERSION
    module.base.rc.s2x.EXPECTED_RELEASE = RELEASE
    module.base.rc.s2x.ALLOWED_CHANGES = dict(module.base.rc.s2x.ALLOWED_CHANGES)
    module.base.rc.s2x.ALLOWED_CHANGES['LOCALVERSION'] = ('"-Synthetica-2.0"', LOCALVERSION)
    return module


s31 = load_s31()
v3 = s31.base.rc.s2x.v3
modules = s31.base.rc.s2x.modules


def compare_31_config(baseline31: Path, generated: str) -> dict[str, dict[str, str]]:
    if baseline31.is_symlink() or not baseline31.is_file():
        raise ValueError('3.1 build config must be a regular file')
    if v3.digest(baseline31) != BASE31_CONFIG_SHA256:
        raise ValueError('3.1 build config hash mismatch')
    old = v3.read_config(baseline31.read_text(encoding='utf-8'))
    new = v3.read_config(generated)
    changes = {key: {'3.1': old.get(key, 'n'), '3.2': new.get(key, 'n')}
               for key in sorted(old.keys() | new.keys())
               if old.get(key, 'n') != new.get(key, 'n')}
    expected = {'LOCALVERSION': {'3.1': BASE31_LOCALVERSION, '3.2': LOCALVERSION}}
    if changes != expected:
        bad = [key for key in sorted(changes.keys() | expected.keys())
               if changes.get(key) != expected.get(key)]
        raise ValueError('3.2 differs from exact 3.1 config beyond LOCALVERSION: ' + ', '.join(bad[:20]))
    return changes


def compare_31_symvers(symvers31: Path, generated: Path) -> dict[str, object]:
    if symvers31.is_symlink() or not symvers31.is_file() or v3.digest(symvers31) != BASE31_SYMVERS_SHA256:
        raise ValueError('3.1 Module.symvers hash mismatch')
    if generated.is_symlink() or not generated.is_file():
        raise ValueError('missing generated Module.symvers')
    old = modules.symvers_records(symvers31.read_text(encoding='utf-8'))
    new = modules.symvers_records(generated.read_text(encoding='utf-8'))
    if old != new or len(new) != 12236 or f"0x{new.get('module_layout', 0):08x}" != '0xed5659d1':
        raise ValueError('3.2 exported symbol CRCs differ from 3.1')
    return {'reference_3_1_symvers_sha256': BASE31_SYMVERS_SHA256,
            'generated_3_2_symvers_sha256': v3.digest(generated),
            'exported_symbol_count': len(new),
            'module_layout_crc': '0xed5659d1'}


def check_config(baseline20: Path, generated: Path, tested20: Path,
                 baseline30: Path, baseline31: Path, mglru: str) -> dict[str, object]:
    res = s31.check_config(baseline20, generated, tested20, baseline30, mglru)
    res['changes_from_exact_3_1'] = compare_31_config(baseline31, generated.read_text(encoding='utf-8'))
    return res


def prepare(source: Path, destination: Path, baseline20: Path) -> None:
    s31.prepare(source, destination, baseline20)


def finish(kit: Path, out: Path, baseline20: Path, tested20: Path, baseline30: Path,
           baseline31: Path, symvers31: Path, result: Path, toolchain: Path, archive: Path) -> None:
    cfg_text = (out / '.config').read_text(encoding='utf-8')
    changes31 = compare_31_config(baseline31, cfg_text)
    abi31 = compare_31_symvers(symvers31, out / 'Module.symvers')
    s31.finish(kit, out, baseline20, tested20, baseline30, result, toolchain, archive)
    with gzip.open(result / 'Image.gz.DO-NOT-FLASH', 'rb') as f:
        raw = f.read(v3.MAX_RAW_IMAGE + 1)
    if len(raw) > v3.MAX_RAW_IMAGE:
        raise ValueError('uncompressed image exceeds limit')
    cert = (result / 'module-signing-public-cert.x509').read_bytes()
    stage = out / 'synthetica2-experimental-modules/lib/modules' / RELEASE / 'kernel'
    checked = modules.collect(stage, config=v3.read_config(cfg_text), release=RELEASE,
                              certificate_der=cert, raw_kernel=raw,
                              symvers_text=(out / 'Module.symvers').read_text(encoding='utf-8'))
    mod_dir = result / 'signed-modules'
    mod_dir.mkdir()
    for name, (data, _details) in sorted(checked.items()):
        (mod_dir / f'{name}.ko').write_bytes(data)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    status.update({
        'kind': STATUS_KIND,
        'version': '3.2',
        'release': RELEASE,
        'proven_3_1_image_sha256': BASE31_IMAGE_SHA256,
        'proven_3_1_config_sha256': BASE31_CONFIG_SHA256,
        'proven_3_1_module_cert_sha256': BASE31_MODULE_CERT_SHA256,
        'changes_from_proven_3_1_config': changes31,
        'export_abi_against_proven_3_1': abi31,
        'proven_3_1_device_validation': 'User verified normal boot and Manager APK operation on Project Infinity X 4.1 (Android 17) and Lunaris 3.13 (Android 16) with unsigned embedded AVB repair.',
    })
    status_path.write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')


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
    cfg.add_argument('--baseline31', type=Path,
                     default=Path(os.environ['S32_BASELINE31_CONFIG']) if os.environ.get('S32_BASELINE31_CONFIG') else None)
    done = sub.add_parser('finish')
    for name in ('kit', 'out', 'baseline', 'tested-config', 'baseline30', 'baseline31', 'symvers31', 'result', 'toolchain-bin', 'neutron-archive'):
        done.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.baseline)
    elif args.command == 'prepare-tree':
        s31.base.prepare_tree(args.tree)
    elif args.command == 'check-config':
        if None in (args.tested_config, args.baseline30, args.baseline31):
            raise ValueError('tested-2.0, 3.0 and 3.1 config paths are required')
        print(json.dumps(check_config(args.baseline, args.generated, args.tested_config,
                                      args.baseline30, args.baseline31, args.mglru), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.tested_config, args.baseline30,
               args.baseline31, args.symvers31, args.result, args.toolchain_bin, args.neutron_archive)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'Synthetica 3.2 build refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
