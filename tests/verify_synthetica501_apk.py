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
        for marker in (b' // MANAGER 5.0.1', b'manager_visual_style', b'ios_glass', b'cyberpunk',
                       b'PixelMatrixSplash', b'CyberBrutalSplash', b'IosLiquidGlassSplash', b'NeonCyberSplash'):
            if marker not in dex:
                raise ValueError(f'5.0.1 production style marker missing: {marker!r}')
        emblem_hashes = set()
        for emblem in ('ic_emblem_pixel.png', 'ic_emblem_cyberpunk.png', 'ic_emblem_ios_glass.png', 'ic_emblem_neon.png'):
            matched = [n for n in names if n.endswith('/' + emblem)]
            if not matched:
                raise ValueError(f'5.0.1 theme PNG emblem missing from APK: {emblem}')
            emblem_hashes.add(hashlib.sha256(z.read(matched[0])).hexdigest())
        if len(emblem_hashes) != 4:
            raise ValueError('Expected 4 distinct PNG emblems in 5.0.1 APK')
    print('5.0.1 presentation (4 PNG emblems, 4 splash screens, 4 layouts/animations) and unchanged 4.0/5.0 root payload statically verified.')
    print('No Android update, physical device, root or boot behavior was verified.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
