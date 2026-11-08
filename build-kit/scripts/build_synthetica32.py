#!/usr/bin/env python3
"""Build Synthetica 3.2 from the pinned 2.0 baseline, not an installer.

The 2.0 builder runs in a disposable tree with its existing security and input
checks. Only LOCALVERSION and the IKCONFIG metadata fix are permitted. Every
exported symbol/owner/type/CRC is checked against archived build evidence.
Successful checks do not establish compatibility with an Android ROM or device.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SYMVERS_SHA256 = '07bb866c067a4c2c0567f5eb17f51137ca7da948dd82799077d93deb82278972'
RELEASE = '4.14.357-openela-synthetica-3.2'
LOCALVERSION = '"-synthetica-3.2"'
BASELINE_RECORDS = 12236
BASELINE_BUILTIN_RECORDS = 12227
IMAGE_NAME = 'DO-NOT-FLASH-Synthetica-3.2-Image.gz'


def load_baseline_builder():
    spec = importlib.util.spec_from_file_location('synthetica32_private_baseline', HERE / 'build_synthetica3.py')
    if spec is None or spec.loader is None:
        raise ValueError('cannot load baseline build guard')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXPECTED_RELEASE = RELEASE
    return module


base = load_baseline_builder()
_original_check_config = base.check_config
_original_verify_image = base.verify_image


def check_config(baseline: str, generated: str) -> dict[str, dict[str, str]]:
    # First parse the actual bytes so duplicates cannot be hidden by replacement.
    actual = base.read_config(generated)
    if actual.get('LOCALVERSION') != LOCALVERSION:
        raise ValueError('3.2 LOCALVERSION missing or incorrect')
    before = 'CONFIG_LOCALVERSION=' + LOCALVERSION
    after = 'CONFIG_LOCALVERSION="-Synthetica-3.0"'
    if generated.count(before) != 1:
        raise ValueError('3.2 LOCALVERSION is not uniquely represented')
    # Reuse the proven 2.0 equality, required security and no-bypass guards.
    _original_check_config(baseline, generated.replace(before, after, 1))
    for feature in ('LRU_GEN', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP'):
        if actual.get(feature, 'n') != 'n':
            raise ValueError(f'experimental feature enabled: {feature}')
    return {'LOCALVERSION': {'2.0': '"-Synthetica-2.0"', '3.2': LOCALVERSION}}


def verify_image(raw: bytes, config: bytes, manager: dict[str, object]) -> None:
    try:
        _original_verify_image(raw, config, manager)
    except ValueError as exc:
        if str(exc) == 'image release is not Synthetica 3.0':
            raise ValueError('image release is not Synthetica 3.2') from exc
        raise


# Modify only the imported private module. The 2.0/3.0 build recipes remain intact.
base.check_config = check_config
base.verify_image = verify_image


def parse_symvers(text: str) -> dict[str, tuple[str, str, str]]:
    """Parse all records, rejecting malformed, duplicate and zero-CRC exports."""
    exports: dict[str, tuple[str, str, str]] = {}
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split()
        if len(fields) != 4 or not re.fullmatch(r'0x[0-9a-fA-F]{8}', fields[0]):
            raise ValueError(f'malformed Module.symvers record at line {number}')
        crc, name, owner, kind = fields
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError(f'invalid exported symbol at line {number}')
        if not re.fullmatch(r'EXPORT_(?:UNUSED_)?SYMBOL(?:_GPL(?:_FUTURE)?)?', kind):
            raise ValueError(f'invalid export type at line {number}')
        if int(crc, 16) == 0:
            raise ValueError(f'zero export CRC for {name}')
        if name in exports:
            raise ValueError(f'duplicate exported symbol: {name}')
        exports[name] = (crc.lower(), owner, kind)
    if not exports:
        raise ValueError('empty Module.symvers')
    return exports


def compare_symvers(reference: Path, generated: Path) -> dict[str, object]:
    if reference.is_symlink() or not reference.is_file() or base.digest(reference) != BASE_SYMVERS_SHA256:
        raise ValueError('archived 2.0-based Module.symvers hash mismatch')
    if generated.is_symlink() or not generated.is_file():
        raise ValueError('missing or unsafe generated Module.symvers')
    old = parse_symvers(reference.read_text(encoding='utf-8'))
    new = parse_symvers(generated.read_text(encoding='utf-8'))
    builtin_count = sum(owner == 'vmlinux' for _crc, owner, _kind in old.values())
    if (len(old), builtin_count) != (BASELINE_RECORDS, BASELINE_BUILTIN_RECORDS):
        raise ValueError('unexpected number of archived exported symbols')
    if old.get('module_layout') != ('0x08efcbb0', 'vmlinux', 'EXPORT_SYMBOL'):
        raise ValueError('unexpected baseline module_layout export')
    missing = sorted(old.keys() - new.keys())
    added = sorted(new.keys() - old.keys())
    different = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])
    if missing or added or different:
        raise ValueError('export ABI differs from archived baseline: '
                         f'missing={len(missing)} added={len(added)} changed={len(different)}; '
                         f'examples={(missing + added + different)[:12]}')
    canonical = ''.join(f'{name}\t{crc}\t{owner}\t{kind}\n'
                        for name, (crc, owner, kind) in sorted(new.items())).encode()
    return {
        'reference_sha256': BASE_SYMVERS_SHA256,
        'generated_sha256': base.digest(generated),
        'exported_records_compared': len(old),
        'builtin_records_compared': builtin_count,
        'module_records_compared': len(old) - builtin_count,
        'missing_added_or_changed': 0,
        'canonical_records_sha256': hashlib.sha256(canonical).hexdigest(),
        'module_layout_crc': old['module_layout'][0],
        'scope': 'All exported symbol names, owners, export types and CRCs; not ROM module trust, vermagic, imports or runtime loading.',
    }


def toolchain_info(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise ValueError('toolchain directory not found')
    clang, lld = directory / 'clang', directory / 'ld.lld'
    clang_version = subprocess.run([str(clang), '--version'], check=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True).stdout.splitlines()[0]
    lld_version = subprocess.run([str(lld), '--version'], check=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True).stdout.splitlines()[0]
    if not re.search(r'\bclang version 18\.', clang_version, re.I) or not re.search(r'\bLLD 18\.', lld_version, re.I):
        raise ValueError('toolchain must be Clang and LLD major 18')
    return {'clang_version': clang_version, 'clang_binary_sha256': base.digest(clang),
            'lld_version': lld_version, 'lld_binary_sha256': base.digest(lld)}


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    base.prepare(source, destination, baseline)
    builder = destination / 'ci/rollercoaster/build-rollercoaster.sh'
    driver = destination / 'scripts/build_chronicle_base.py'
    builder_text = builder.read_text(encoding='utf-8')
    driver_text = driver.read_text(encoding='utf-8')
    if builder_text.count('# 3.0 must keep the whole 2.0 config') != 1 or \
       driver_text.count('Image compiled; 3.0 verification still required') != 1:
        raise ValueError('unexpected inherited guard layout')
    builder.write_text(builder_text.replace('# 3.0 must keep the whole 2.0 config',
                                            '# 3.2 must keep the whole 2.0 config'), encoding='utf-8')
    driver.write_text(driver_text.replace('Image compiled; 3.0 verification still required',
                                          'Image compiled; 3.2 verification still required'), encoding='utf-8')


def finish(kit: Path, out: Path, baseline: Path, reference_image: Path,
           reference_symvers: Path, toolchain: Path, result: Path) -> None:
    if result.exists() or result.is_symlink():
        raise ValueError('refusing to overwrite an existing result directory')
    # Check all records and the actual compiler before emitting any deliverable.
    abi = compare_symvers(reference_symvers, out / 'Module.symvers')
    compiler = toolchain_info(toolchain)
    base.finish(kit, out, baseline, reference_image, result)
    old_name = 'DO-NOT-FLASH-Synthetica-3.0-Image.gz'
    (result / old_name).rename(result / IMAGE_NAME)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    status['output_sha256'][IMAGE_NAME] = status['output_sha256'].pop(old_name)
    status.update({
        'status': 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED',
        'device_target': 'miatoll family, subject to ROM/device-specific validation',
        'prior_test': 'No physical boot of this 3.2 image has been performed.',
        'compiled_toolchain': compiler,
        'export_abi_against_2_0_based_baseline': abi,
        'module_public_cert_sha256': base.digest(result / 'kernel-module-public-cert.x509'),
        'kernel_manager_identity': {'package': 'net.ember.labs',
                                    'cert_sha256': 'fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140',
                                    'scope': 'Identity strings linked; Android recognition and root are not runtime-tested.'},
        'no_experimental_3_1_mglru_or_uclamp_patches': True,
        'installer_or_boot_image_created': False,
        'checks_not_proofs': [
            'Matching every exported symbol name, owner, type and CRC is not proof of compatibility with ROM modules.',
            'The kernel release/vermagic changed and the fresh module certificate is not the ROM module signer.',
            'The six same-build modules are signature and CRC checked, but their runtime loading is not tested.',
            'Pinned KernelSU Manager identity is present; Manager operation and root are not tested.',
            'AVB trust, boot header, ramdisk, DTB/DTBO and the target ROM are not verified.',
            'No physical Android 17 boot, hardware or stability test was performed.',
        ],
    })
    status_path.write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    (result / 'README-DO-NOT-FLASH.txt').write_text(
        'DO NOT FLASH. Synthetica 3.2 is compiled but has not booted on a physical device.\n'
        'This is not an installer or a complete boot image. ROM/AVB/module integration is not verified.\n'
        'The 2.0 generated config is preserved except LOCALVERSION; IKCONFIG metadata is corrected.\n'
        'All exported symbol names, owners, types and CRCs match the archived 2.0-based build.\n'
        'Six selected same-build modules are signed; ROM module signatures/trust remain unknown.\n'
        'No bypass for module signatures, MODVERSIONS, SELinux, or dm-verity is included.\n', encoding='utf-8')
    files = sorted(p for p in result.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (result / 'SHA256SUMS.txt').write_text(''.join(
        f'{base.digest(path)}  {path.relative_to(result).as_posix()}\n' for path in files), encoding='utf-8')
    print(json.dumps(status, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('source', 'destination', 'baseline'):
        prep.add_argument('--' + name, required=True, type=Path)
    cfg = sub.add_parser('check-config')
    for name in ('baseline', 'generated'):
        cfg.add_argument('--' + name, required=True, type=Path)
    fix = sub.add_parser('fix-ikconfig')
    fix.add_argument('--tree', required=True, type=Path)
    done = sub.add_parser('finish')
    for name in ('kit', 'out', 'baseline', 'reference-image', 'reference-symvers', 'toolchain', 'result'):
        done.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.baseline)
    elif args.command == 'check-config':
        print(json.dumps(check_config(base.verified_baseline(args.baseline),
                                      args.generated.read_text(encoding='utf-8')), indent=2))
    elif args.command == 'fix-ikconfig':
        base.fix_ikconfig(args.tree)
    else:
        finish(args.kit, args.out, args.baseline, args.reference_image,
               args.reference_symvers, args.toolchain, args.result)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError, KeyError, IndexError) as exc:
        print(f'Synthetica 3.2 build refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
