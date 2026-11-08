#!/usr/bin/env python3
"""Static Manager 5.0.1 payload checks; NOT a device/root or Android update test."""
from pathlib import Path
import sys
import zipfile

import verify_synthetica50_apk as old


def verify(apk: Path) -> None:
    old.verify(apk)
    with zipfile.ZipFile(apk) as z:
        dex = b''.join(z.read(name) for name in z.namelist() if name.endswith('.dex'))
        for marker in (b' // MANAGER 5.0.1', b'manager_visual_style', b'ios_glass', b'cyberpunk'):
            if marker not in dex:
                raise ValueError(f'5.0.1 production style marker missing: {marker!r}')
    print('5.0.1 presentation and unchanged 4.0/5.0 root payload statically verified.')
    print('No Android update, physical device, root or boot behavior was verified.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} APK')
    verify(Path(sys.argv[1]))
