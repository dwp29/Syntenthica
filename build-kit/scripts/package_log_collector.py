#!/usr/bin/env python3
"""Build a small, standalone recovery/ADB diagnostics ZIP; no kernel payload."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build-kit/ci/log-collector'
VERSION = '1.0'
BINARY = 'META-INF/com/google/android/update-binary'
UPDATER = 'META-INF/com/google/android/updater-script'
EXPECTED_NAMES = frozenset((BINARY, UPDATER, 'collector.sh', 'README-ID.txt'))
MARKER = b'# Standalone recovery diagnostics; update-binary is a shell script.\n'


def payloads() -> dict[str, bytes]:
    script = (SOURCE / 'collector.sh').read_bytes()
    readme = (SOURCE / 'README-ID.txt').read_bytes()
    if not script.startswith(b'#!/sbin/sh\n') or not readme or b'logcat' not in script:
        raise ValueError('collector source or README is incomplete')
    return {BINARY: script, UPDATER: MARKER, 'collector.sh': script, 'README-ID.txt': readme}


def verify(path: Path, expected: dict[str, bytes] | None = None) -> dict[str, object]:
    expected = expected or payloads()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or frozenset(names) != EXPECTED_NAMES:
            raise ValueError('unexpected or duplicate collector ZIP entries')
        if archive.testzip() is not None:
            raise ValueError('collector ZIP CRC check failed')
        for name in names:
            entry = archive.getinfo(name)
            if archive.read(name) != expected[name]:
                raise ValueError('collector ZIP differs from checked-in source: ' + name)
            mode = entry.external_attr >> 16
            want = 0o100755 if name in (BINARY, 'collector.sh') else 0o100644
            if mode != want:
                raise ValueError('unexpected ZIP entry permissions: ' + name)
    return {
        'file': path.name,
        'bytes': path.stat().st_size,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'kind': 'recovery diagnostics, no kernel, unsigned, not device-tested',
    }


def package(output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite an existing output')
    files = payloads()
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            created = True
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (0o100755 if name in (BINARY, 'collector.sh') else 0o100644) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        return verify(output, files)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new ZIP path; must not already exist')
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print('Collector packaging refused: ' + str(exc), file=sys.stderr)
        sys.exit(1)
