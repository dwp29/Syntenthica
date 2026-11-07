#!/usr/bin/env python3
"""Reject a 4.0 demo preview that contains a KSU payload or root helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

FONTS = {
    'c845473330b94c2079ce9af01c51ac8ba2d99c24f4d14c039843bbb8e642ebd8',
    '768476aa712d4f5c3e18d3bce80f980a8bd3f72b7094d22ec5e768df3acfed61',
}


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as z:
        if z.testzip():
            raise ValueError('Invalid preview ZIP')
        names = z.namelist()
        for suffix in ('libkernelsu.so', 'libksud.so', 'libadbroot.so', 'synthetica-control40.sh', 'synthetica-boost40.sh'):
            if any(name.endswith(suffix) for name in names):
                raise ValueError(f'Preview contains privileged payload: {suffix}')
        dex = b''.join(z.read(name) for name in names if name.endswith('.dex'))
        for marker in (b'PREVIEW ONLY', b'pixel-preview-tab', b'neon31-preflight', b'/proc/loadavg',
                       b'https://github.com/LSPosed/LSPosed/releases'):
            if marker not in dex:
                raise ValueError(f'Preview marker missing: {marker!r}')
        for forbidden in (b'/data/adb/ksud', b'/system/bin/su', b'Java_com_rifsxd_ksunext_Natives'):
            if forbidden in dex:
                raise ValueError(f'Preview contains a root-control marker: {forbidden!r}')
        fonts = {hashlib.sha256(z.read(name)).hexdigest() for name in names
                 if name.startswith('res/') and name.endswith('.ttf')}
        if not FONTS <= fonts or 'assets/licenses/Silkscreen-OFL.txt' not in names:
            raise ValueError('Licensed Pixel display font missing')
        print('Separate 4.0 preview: integrity, licensed font and isolation checks passed')
        print('No Manager backend, tuning helper or installer is present.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} PREVIEW_APK')
    verify(Path(sys.argv[1]))
