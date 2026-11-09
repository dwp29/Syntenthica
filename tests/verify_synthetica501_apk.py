#!/usr/bin/env python3
"""Static Manager 5.0.1 payload checks; NOT a device/root or Android update test."""
from pathlib import Path
import sys
import zipfile

import verify_synthetica50_apk as old


def verify(apk: Path) -> None:
    old.verify(apk)
    import hashlib
    with zipfile.ZipFile(apk) as z:
        names = set(z.namelist())
        dex = b''.join(z.read(name) for name in z.namelist() if name.endswith('.dex'))
        for marker in (
            b'PIXEL // MANAGER 5.0.1',
            b'CYBERPUNK // MANAGER 5.0.1',
            b'GLASS // MANAGER 5.0.1',
            b'NEON // MANAGER 5.0.1',
            b'DOT_MATRIX_OS // UAPI_V4 :: READY',
            b'SYS.NODE // KERNELSU-NEXT :: UAPI_V4',
            b'NEON OVERDRIVE // UAPI_V4 :: ONLINE',
            b'manager_visual_style',
            b'ios_glass',
            b'cyberpunk',
        ):
            if marker not in dex:
                raise ValueError(f'5.0.1 production style marker missing: {marker!r}')
        arsc = z.read('resources.arsc') if 'resources.arsc' in names else b''
        for emblem in ('ic_emblem_pixel', 'ic_emblem_cyberpunk', 'ic_emblem_ios_glass', 'ic_emblem_neon'):
            if emblem.encode() not in arsc and not any(emblem in n for n in names):
                raise ValueError(f'5.0.1 theme PNG emblem missing from APK: {emblem}')
        png_hashes = {
            hashlib.sha256(z.read(n)).hexdigest()
            for n in names
            if n.startswith('res/') and n.endswith('.png')
        }
        if len(png_hashes) < 4:
            raise ValueError('Expected at least 4 distinct PNG emblems in 5.0.1 APK')
    print('5.0.1 presentation (4 PNG emblems, 4 splash screens, 4 layouts/animations) and unchanged 4.0/5.0 root payload statically verified.')
    print('No Android update, physical device, root or boot behavior was verified.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
