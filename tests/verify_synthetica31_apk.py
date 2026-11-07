#!/usr/bin/env python3
"""Verify static identity/compatibility of a 3.1 Manager APK, not live root."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

from verify_synthetica21_apk import REFERENCE, SYMBOL, get_symbol_code, normalized_native

FONT_SHA256 = '2ce01d946e1e1ffc8d7eecfffbda8623bedd63eaf811a20488c4b69af45babb0'
LICENSE_SHA256 = 'fe17c0f2581d71b4e1ea7e636e7f4877c29223e11bb1dd1a871e8c3f2a86336b'
REQUIRED_DEX = (b'neon-pulse', b'neon_accent', b'neon_motion', b'neon_theme', b'neon_glow',
                b'NEON // MANAGER 3.1', b'/sys/devices/system/cpu/cpu', b'/proc/loadavg',
                b'/sys/class/kgsl/kgsl-3d0/gpuclk', b'neon31-preflight', b'SHA-256', b'sha256sum -c -')


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
        daemon_name = 'lib/arm64-v8a/libksud.so'
        daemon = candidate.read(daemon_name)
        if daemon != previous.read(daemon_name):
            raise ValueError('Manager daemon differs from 2.0')
        for name in ('assets/main.jar', 'META-INF/com/google/android/update-binary',
                     'META-INF/com/google/android/updater-script'):
            if candidate.read(name) != previous.read(name):
                raise ValueError(f'Root-facing packaged asset differs from 2.0: {name}')
        other_arch = [name for name in candidate.namelist()
                      if name.startswith('lib/') and name.endswith('.so') and not name.startswith('lib/arm64-v8a/')]
        if other_arch:
            raise ValueError(f'Unexpected native ABI: {other_arch}')
        fonts = [name for name in candidate.namelist() if name.startswith('res/') and name.endswith('.ttf')]
        if not any(hashlib.sha256(candidate.read(name)).hexdigest() == FONT_SHA256 for name in fonts):
            raise ValueError('Pinned Oxanium font is not packaged')
        if hashlib.sha256(candidate.read('assets/licenses/Oxanium-OFL.txt')).hexdigest() != LICENSE_SHA256:
            raise ValueError('Oxanium license is not packaged intact')
        dex = b''.join(candidate.read(name) for name in candidate.namelist() if name.endswith('.dex'))
        missing = [marker.decode() for marker in REQUIRED_DEX if marker not in dex]
        if missing:
            raise ValueError(f'3.1 UI/device bytecode markers missing: {missing}')
        print('APK ZIP CRC: OK')
        print('JNI: UAPI 4; JNI and adbroot match 2.0 except ELF build ID')
        print('arm64 ksud:', hashlib.sha256(daemon).hexdigest(), '(matches 2.0)')
        print('Root-facing packaged scripts and main.jar match 2.0')
        print('Licensed Oxanium font, diagnostics and ZIP preflight markers are present')
        print('Not a signature, Android runtime, update or root test')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
