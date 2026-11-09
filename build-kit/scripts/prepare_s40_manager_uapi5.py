#!/usr/bin/env python3
"""Prepare a disposable, UNSIGNED UAPI-5 Manager prototype; never a release.

This layers the existing 5.0.1 UI on pinned upstream JNI/UAPI and a pinned
published arm64 ksud. It deliberately does not alter the 5.0.1 release or
relax the kernel's signature checks. There is no device/runtime proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_501_themes as base501
import build_manager_source as manager_base
import build_synthetica40 as kernel_build

PINS = json.loads((ROOT / 'build-kit/ci/manager-uapi5-dev/inputs.json').read_text())
OUTPUT_NAME = 'Manager-UAPI5-UNSIGNED-DO-NOT-INSTALL.apk'


def verify_source(name: str, source: Path) -> None:
    if not source.is_dir():
        raise ValueError(f'{name} source is not a directory')
    for relative, expected in PINS[name]['sentinels'].items():
        file = source / relative
        if not file.is_file() or file.is_symlink() or kernel_build.sha256(file) != expected:
            raise ValueError(f'{name} source sentinel mismatch: {relative}')


def verify_archive(name: str, archive: Path) -> None:
    if archive.is_symlink() or not archive.is_file() or kernel_build.sha256(archive) != PINS[name]['archive_sha256']:
        raise ValueError(f'{name} archive SHA-256 mismatch')


def verify_daemon(path: Path) -> None:
    pin = PINS['ksud_arm64']
    if path.is_symlink() or not path.is_file() or path.stat().st_size != pin['bytes']:
        raise ValueError('Unexpected or symlinked ksud asset')
    if kernel_build.sha256(path) != pin['sha256']:
        raise ValueError('ksud SHA-256 mismatch')
    with path.open('rb') as f:
        header = f.read(20)
    if (len(header) != 20 or header[:6] != b'\x7fELF\x02\x01' or
            struct.unpack_from('<H', header, 16)[0] not in (2, 3) or
            struct.unpack_from('<H', header, 18)[0] != 183):
        raise ValueError('ksud is not an arm64 ELF executable')


def verify_uapi_delta(old: Path, new: Path) -> None:
    def hashes(source: Path) -> dict[str, str]:
        directory = source / 'uapi'
        if not directory.is_dir():
            raise ValueError('UAPI directory missing')
        files = sorted(p for p in directory.rglob('*') if p.is_file())
        if any(p.is_symlink() for p in files):
            raise ValueError('Unexpected symlink in UAPI files')
        return {p.relative_to(directory).as_posix(): kernel_build.sha256(p) for p in files}

    before, after = hashes(old), hashes(new)
    if before.keys() != after.keys():
        raise ValueError('UAPI header set changed unexpectedly')
    if {name for name in before if before[name] != after[name]} != {'feature.h', 'supercall.h'}:
        raise ValueError('Unexpected UAPI header differences')
    old_native = (old / 'manager/app/src/main/cpp/ksu.cc').read_text()
    new_native = (new / 'manager/app/src/main/cpp/ksu.cc').read_text()
    if ('KERNEL_SU_UAPI_VERSION = 4;' not in (old / 'uapi/supercall.h').read_text() or
            'KERNEL_SU_UAPI_VERSION = 5;' not in (new / 'uapi/supercall.h').read_text() or
            'KSU_FEATURE_FLAG_SUPPORTED' in old_native or
            new_native.count('KSU_FEATURE_FLAG_SUPPORTED') != 2):
        raise ValueError('Unexpected UAPI or native feature-flag semantics')


def prepare(old: Path, new: Path, daemon: Path, work: Path) -> Path:
    verify_source('old_manager', old)
    verify_source('new_backend', new)
    verify_uapi_delta(old, new)
    verify_daemon(daemon)
    kernel_build.check_work_directory(work, [old, new])
    work.mkdir(parents=True)
    source = work / 'source'
    shutil.copytree(old, source, symlinks=True)
    # Reuse the entire 5.0.1 layering: themes, preferences, Device Check,
    # Control/Boost, identity and baseline daemon checks remain unchanged.
    base501.prepare_tree(source)

    main = source / 'manager/app/src/main'
    native_uapi = main / 'cpp/uapi'
    if not native_uapi.is_symlink() or native_uapi.resolve() != (source / 'uapi').resolve():
        raise ValueError('Expected the Manager JNI UAPI link to the source root')
    for name in ('supercall.h', 'feature.h'):
        shutil.copyfile(new / 'uapi' / name, source / 'uapi' / name)
    shutil.copyfile(new / 'manager/app/src/main/cpp/ksu.cc', main / 'cpp/ksu.cc')
    target = main / 'jniLibs/arm64-v8a/libksud.so'
    shutil.copyfile(daemon, target)
    target.chmod(0o755)

    # Keep the existing strict UAPI equality check: never make an old kernel
    # appear compatible by only changing the displayed version.
    natives = (main / 'java/com/rifsxd/ksunext/Natives.kt').read_text()
    if 'kernelUAPIVersion == managerUAPIVersion' not in natives:
        raise ValueError('Manager lost its strict UAPI equality gate')
    patch = base501.base50.previous.previous.patch_file
    prototype = PINS['prototype']
    patch(source / 'manager/build.gradle.kts', [
        ('val managerVersionCode by extra(60001)',
         f"val managerVersionCode by extra({prototype['version_code']})", 'dev version code', 1),
        ('val managerVersionName by extra("5.0.1")',
         f"val managerVersionName by extra(\"{prototype['version_name']}\")", 'dev version name', 1),
    ])
    patch(source / 'manager/app/build.gradle.kts', [
        ('output.outputFileName = "Synthetica-5.0.1-MultiTheme-$name.apk"',
         'output.outputFileName = "Manager-UAPI5-UNSIGNED-DO-NOT-INSTALL-$name.apk"',
         'dev output label', 1),
        # AGP otherwise strips the already-built daemon and changes its pinned
        # byte identity. Preserve the exact upstream asset inside the APK.
        ('        jniLibs {\n            useLegacyPackaging = true\n',
         '        jniLibs {\n            useLegacyPackaging = true\n'
         '            keepDebugSymbols += "**/libksud.so"\n', 'preserve published ksud', 1),
    ])
    for locale, value in (
        ('values', 'UAPI 5 DEV: not a tested or installable release'),
        ('values-in-rID', 'UAPI 5 DEV: bukan release teruji atau untuk dipasang'),
    ):
        base501.base50.replace_string(main / 'res' / locale / 'strings_synthetica.xml', 'ios_about_sub', value)
    manifest = {
        'kind': 'UNSIGNED_MANAGER_UAPI5_SOURCE_PROTOTYPE_NOT_FOR_INSTALL',
        'old_manager_commit': PINS['old_manager']['commit'],
        'new_backend_commit': PINS['new_backend']['commit'],
        'ksud_sha256': PINS['ksud_arm64']['sha256'],
        'ksud_origin': PINS['ksud_arm64']['origin'],
        **prototype,
        'kernel_apk_v3_blocker_resolved': False,
        'android_or_root_tested': False,
    }
    (work / 'PROTOTYPE.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    verify = sub.add_parser('verify-archives')
    verify.add_argument('--old', required=True, type=Path)
    verify.add_argument('--new', required=True, type=Path)
    prep = sub.add_parser('prepare')
    for name in ('old', 'new', 'daemon', 'work'):
        prep.add_argument('--' + name, required=True, type=Path)
    prep.add_argument('--build-unsigned', action='store_true',
                      help='build only inside work/result; do not sign, install or publish')
    args = parser.parse_args()
    if args.command == 'verify-archives':
        verify_archive('old_manager', args.old)
        verify_archive('new_backend', args.new)
        print('Both source archive SHA-256 values verified.')
        return 0
    source = prepare(args.old, args.new, args.daemon, args.work)
    print(f'Development-only source prepared in {source}; no runtime compatibility claim.')
    if args.build_unsigned:
        manager_base.OUT_UNSIGNED = args.work / 'result' / OUTPUT_NAME
        manager_base.zipalign_apk(manager_base.build_gradle(source))
        print('UNSIGNED AND UNTESTED: DO NOT INSTALL OR DISTRIBUTE AS A RELEASE.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
