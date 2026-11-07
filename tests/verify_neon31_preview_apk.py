#!/usr/bin/env python3
"""Reject a 3.1 preview that accidentally contains any KSU root payload."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

FONT_SHA256 = '2ce01d946e1e1ffc8d7eecfffbda8623bedd63eaf811a20488c4b69af45babb0'


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f'ZIP integrity failed: {bad}')
        names = z.namelist()
        for suffix in ('libkernelsu.so', 'libksud.so', 'libadbroot.so'):
            if any(name.endswith(suffix) for name in names):
                raise ValueError(f'Preview contains a root Manager payload: {suffix}')
        dex = b''.join(z.read(name) for name in names if name.endswith('.dex'))
        for marker in (b'neon_theme', b'neon_glow', b'PREVIEW ONLY', b'/sys/devices/system/cpu/cpu'):
            if marker not in dex:
                raise ValueError(f'Preview marker missing: {marker!r}')
        for forbidden in (b'/data/adb/ksud', b'/system/bin/su', b'Java_com_rifsxd_ksunext_Natives'):
            if forbidden in dex:
                raise ValueError(f'Preview contains a root-control marker: {forbidden!r}')
        if not any(hashlib.sha256(z.read(name)).hexdigest() == FONT_SHA256
                   for name in names if name.startswith('res/') and name.endswith('.ttf')):
            raise ValueError('Pinned offline font is missing')
        if 'assets/licenses/Oxanium-OFL.txt' not in names:
            raise ValueError('Font license is missing')
        print('ZIP integrity, Device Check/theme markers, licensed font and no KSU native payload: OK')
        print('This separate preview cannot grant or administer root.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} PREVIEW_APK')
    verify(Path(sys.argv[1]))
