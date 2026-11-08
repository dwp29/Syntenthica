#!/usr/bin/env python3
"""Verify the separate theme preview remains non-root and contains 5.0 styles."""
from pathlib import Path
import sys
import zipfile

import verify_pixel40_preview_apk as old


def verify(apk: Path) -> None:
    old.verify(apk)
    with zipfile.ZipFile(apk) as z:
        dex = b''.join(z.read(name) for name in z.namelist() if name.endswith('.dex'))
        for marker in (b'manager_visual_style', b'cyberpunk', b'ios_glass', b' // MANAGER 5.0'):
            if marker not in dex:
                raise ValueError(f'5.0 style marker missing: {marker!r}')
    print('5.0 theme preview markers present; this APK is not the Manager.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} PREVIEW_APK')
    verify(Path(sys.argv[1]))
