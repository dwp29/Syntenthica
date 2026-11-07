#!/usr/bin/env python3
"""Static UAPI and payload checks for the 3.0 unsigned Manager APK.

No Android install, signing identity or live root behavior is inferred here.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

from verify_synthetica21_apk import REFERENCE, SYMBOL, get_symbol_code, normalized_native

REQUIRED_DEX = (b'neon-ambient', b'neon-pulse', b'neon_accent', b'neon_motion', b'NEON // MANAGER 3.0')


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as candidate, zipfile.ZipFile(REFERENCE) as previous:
        bad = candidate.testzip()
        if bad:
            raise ValueError(f'APK ZIP CRC mismatch: {bad}')
        libname = 'lib/arm64-v8a/libkernelsu.so'
        daemon_name = 'lib/arm64-v8a/libksud.so'
        native = candidate.read(libname)
        if get_symbol_code(native, SYMBOL) != bytes.fromhex('80008052c0035fd6'):
            raise ValueError('Manager JNI accessor does not return UAPI 4')
        if normalized_native(native) != normalized_native(previous.read(libname)):
            raise ValueError('Manager JNI differs from 2.0 except ELF build ID')
        daemon = candidate.read(daemon_name)
        if daemon != previous.read(daemon_name):
            raise ValueError('Manager daemon differs from 2.0')
        other_arch = [name for name in candidate.namelist()
                      if name.startswith('lib/') and name.endswith('.so') and not name.startswith('lib/arm64-v8a/')]
        if other_arch:
            raise ValueError(f'Unexpected native ABI: {other_arch}')
        dex = b''.join(candidate.read(name) for name in candidate.namelist() if name.endswith('.dex'))
        missing = [marker.decode() for marker in REQUIRED_DEX if marker not in dex]
        if missing:
            raise ValueError(f'Neon UI bytecode markers missing: {missing}')
        print('APK ZIP CRC: OK')
        print('JNI: UAPI 4, matches 2.0 except ELF build ID')
        print('arm64 ksud:', hashlib.sha256(daemon).hexdigest(), '(matches 2.0)')
        print('Neon UI and preferences markers present; no non-arm64 native libraries')
        print('Not a signature, Android runtime, update or root test')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
