#!/usr/bin/env python3
"""Safety checks for the separately signed simulated UI fixture, NOT a Manager."""
from pathlib import Path
import sys
import zipfile


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or z.testzip() is not None:
            raise ValueError('Duplicate or corrupted fixture ZIP entry')
        for name in names:
            low = name.lower()
            if any(bad in low for bad in ('libksud.so', 'libkernelsu.so', 'libadbroot.so',
                                          'update-binary', 'updater-script', 'synthetica-boost40.sh',
                                          'synthetica-control40.sh')):
                raise ValueError(f'Fixture contains privileged payload: {name}')
        dex = b''.join(z.read(name) for name in names if name.endswith('.dex'))
        for marker in (b'SIMULATED UI', b'UI fixture: privileged backend disabled',
                       b'manager_visual_style', b'ios_glass', b'cyberpunk',
                       b'com/rifsxd/ksunext/ui/screen/HomeKt',
                       b'com/rifsxd/ksunext/ui/screen/CustomizationKt'):
            if marker not in dex:
                raise ValueError(f'Fixture isolation/real-screen marker missing: {marker!r}')
    print('Simulated UI fixture: actual screen classes, stub marker and no known privileged payload.')
    print('Check the fixture package and lack of network permissions separately with aapt.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'usage: {sys.argv[0]} FIXTURE_APK')
    verify(Path(sys.argv[1]))
