#!/usr/bin/env python3
"""Build an isolated, demo-signed Neon UI preview. It is NOT a root Manager.

This project contains no Manager backend or KSU native payload and uses a different
application ID so it can coexist with an installed Synthetica Manager.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'build-kit/ci/neon-preview'
THEME = ROOT / 'build-kit/ci/ksun-neon/theme'
ICON = ROOT / 'build-kit/ci/branding-neon/ic_synthetica_emblem.png'
WRAPPER = {
    'gradlew': '6656e30acffccafed9e50c8fd44f54d167d4c06a7864fc8b8b4c69c4ebbddc00',
    'gradle/wrapper/gradle-wrapper.jar': '423cb469ccc0ecc31f0e4e1c309976198ccb734cdcbb7029d4bda0f18f57e8d9',
    'gradle/wrapper/gradle-wrapper.properties': '297d70e976c3434033149e1a72983da5db39a70c114a9b60d58357ef7a320041',
}


def prepare(target: Path, source: Path) -> None:
    if target.exists():
        raise ValueError('preview target must not already exist')
    if 'KERNEL_SU_UAPI_VERSION = 4;' not in (source / 'uapi/supercall.h').read_text():
        raise ValueError('wrapper source must be the pinned UAPI-4 tree')
    shutil.copytree(PROJECT, target)
    for name, expected in WRAPPER.items():
        original = source / 'manager' / name
        if hashlib.sha256(original.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Pinned Gradle wrapper mismatch: {name}')
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    os.chmod(target / 'gradlew', 0o755)
    theme = target / 'app/src/main/java/com/rifsxd/ksunext/ui/theme'
    theme.mkdir(parents=True)
    for name in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt'):
        shutil.copy2(THEME / name, theme / name)
    drawable = target / 'app/src/main/res/drawable-nodpi'
    drawable.mkdir(parents=True)
    shutil.copy2(ICON, drawable / 'ic_synthetica_emblem.png')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='pinned KernelSU-Next tree for the Gradle wrapper')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetica-neon-preview-') as temp:
        target = Path(temp) / 'project'
        prepare(target, args.source)
        if args.verify_only:
            print('Preview project and pinned wrapper prepared; no APK built')
            return
        subprocess.run([str(target / 'gradlew'), ':app:assembleDebug', '--no-daemon', '--stacktrace'], cwd=target, check=True)
        apks = list((target / 'app/build/outputs/apk/debug').glob('*.apk'))
        if len(apks) != 1:
            raise RuntimeError('Expected exactly one debug-signed preview APK')
        output = Path(os.environ['NEON_PREVIEW_OUTPUT'])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise RuntimeError('Refusing to overwrite existing preview output')
        shutil.copy2(apks[0], output)
        print('Preview only (not Manager):', output, hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
