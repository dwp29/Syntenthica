#!/usr/bin/env python3
"""Verify static identity and packaged 4.0 assets; does not test live root."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

from verify_synthetica21_apk import REFERENCE, SYMBOL, get_symbol_code, normalized_native

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'build-kit/ci/ksun-pixel40'
FONT_HASHES = {
    'c845473330b94c2079ce9af01c51ac8ba2d99c24f4d14c039843bbb8e642ebd8',
    '768476aa712d4f5c3e18d3bce80f980a8bd3f72b7094d22ec5e768df3acfed61',
}
REQUIRED_DEX = (
    b'pixel-pulse', b'neon_motion', b'neon_theme', b'PIXEL // MANAGER 4.0',
    b'neon31-preflight', b'sha256sum -c -', b'/proc/loadavg',
    b'synthetica-control40.sh', b'synthetica-boost40.sh', b'susfs features',
    b'https://github.com/LSPosed/LSPosed/releases', b'https://modules.lsposed.org/',
)


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as candidate, zipfile.ZipFile(REFERENCE) as previous:
        bad = candidate.testzip()
        if bad:
            raise ValueError(f'APK ZIP CRC mismatch: {bad}')
        libname = 'lib/arm64-v8a/libkernelsu.so'
        native = candidate.read(libname)
        if get_symbol_code(native, SYMBOL) != bytes.fromhex('80008052c0035fd6'):
            raise ValueError('Manager JNI accessor does not return UAPI 4')
        if normalized_native(native) != normalized_native(previous.read(libname)):
            raise ValueError('Manager JNI differs from 2.0 except ELF build ID')
        adbroot = 'lib/arm64-v8a/libadbroot.so'
        if normalized_native(candidate.read(adbroot)) != normalized_native(previous.read(adbroot)):
            raise ValueError('ADB root native code differs from 2.0 except ELF build ID')
        daemon = candidate.read('lib/arm64-v8a/libksud.so')
        if daemon != previous.read('lib/arm64-v8a/libksud.so'):
            raise ValueError('Manager daemon differs from 2.0')
        for name in ('assets/main.jar', 'META-INF/com/google/android/update-binary',
                     'META-INF/com/google/android/updater-script'):
            if candidate.read(name) != previous.read(name):
                raise ValueError(f'Existing root-facing asset differs: {name}')
        for name in ('synthetica-control40.sh', 'synthetica-boost40.sh'):
            if candidate.read(f'assets/{name}') != (ASSETS / 'assets' / name).read_bytes():
                raise ValueError(f'Unexpected helper content: {name}')
        other_arch = [name for name in candidate.namelist()
                      if name.startswith('lib/') and name.endswith('.so') and not name.startswith('lib/arm64-v8a/')]
        if other_arch:
            raise ValueError(f'Unexpected native ABI: {other_arch}')
        fonts = {hashlib.sha256(candidate.read(name)).hexdigest() for name in candidate.namelist()
                 if name.startswith('res/') and name.endswith('.ttf')}
        if not FONT_HASHES <= fonts:
            raise ValueError('Pinned Silkscreen fonts are missing')
        if candidate.read('assets/licenses/Silkscreen-OFL.txt') != (ASSETS / 'assets/licenses/Silkscreen-OFL.txt').read_bytes():
            raise ValueError('Silkscreen OFL license missing or changed')
        dex = b''.join(candidate.read(name) for name in candidate.namelist() if name.endswith('.dex'))
        missing = [marker.decode() for marker in REQUIRED_DEX if marker not in dex]
        if missing:
            raise ValueError(f'4.0 feature bytecode markers missing: {missing}')
        print('APK ZIP CRC: OK')
        print('JNI: UAPI 4; JNI and adbroot match 2.0 except ELF build ID')
        print('arm64 ksud:', hashlib.sha256(daemon).hexdigest(), '(matches 2.0)')
        print('Existing root-facing assets unchanged; explicitly opted-in helper assets verified')
        print('Licensed Silkscreen fonts, 3.1 preflight and 4.0 feature markers present')
        print('Not a signature, Android runtime, device upgrade or root test')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
