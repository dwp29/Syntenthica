#!/usr/bin/env python3
"""Static 5.0 Manager payload/identity regression checks (not a device test)."""
from pathlib import Path
import hashlib
import sys
import zipfile

import verify_synthetica40_apk as old

ROOT = Path(__file__).resolve().parents[1]
OXANIUM = '2ce01d946e1e1ffc8d7eecfffbda8623bedd63eaf811a20488c4b69af45babb0'
MARKERS = (b'manager_visual_style', b'cyberpunk', b'ios_glass', b' // MANAGER 5.0')


def verify(apk: Path) -> None:
    old.REQUIRED_DEX = tuple(m for m in old.REQUIRED_DEX if m != b'PIXEL // MANAGER 4.0') + MARKERS
    old.verify(apk)
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate APK ZIP entries')
        fonts = {hashlib.sha256(z.read(name)).hexdigest() for name in names
                 if name.startswith('res/') and name.endswith('.ttf')}
        if OXANIUM not in fonts:
            raise ValueError('Licensed Neon Oxanium font missing')
        license_path = 'assets/licenses/Oxanium-OFL.txt'
        if z.read(license_path) != (ROOT / 'build-kit/ci/ksun-neon31' / license_path).read_bytes():
            raise ValueError('Oxanium font license missing or changed')
    print('5.0 style preference and theme markers, Oxanium and original root-facing payload checked')
    print('No Android update, live root or device functionality was verified.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
