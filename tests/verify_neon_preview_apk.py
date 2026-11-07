#!/usr/bin/env python3
"""Fail closed if the visual demo accidentally includes any KSU payload."""
from __future__ import annotations

from pathlib import Path
import sys
import zipfile


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
        for marker in (b'neon-ambient', b'NEON // MANAGER 3.0', 'PRATINJAU SAJA'.encode()):
            if marker not in dex:
                raise ValueError(f'Preview marker missing: {marker!r}')
        for forbidden in (b'/data/adb/ksud', b'/system/bin/su', b'Java_com_rifsxd_ksunext_Natives'):
            if forbidden in dex:
                raise ValueError(f'Preview contains a root-control marker: {forbidden!r}')
        print('ZIP integrity, demo UI markers and no KSU/ksud/adbroot payload: OK')
        print('This is not the Manager and does not grant or administer root.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} PREVIEW_APK')
    verify(Path(sys.argv[1]))
