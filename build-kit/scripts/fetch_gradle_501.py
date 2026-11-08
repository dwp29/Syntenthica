#!/usr/bin/env python3
"""Fetch the official, SHA-256-pinned Gradle 9.2.0 ZIP in verified ranges.

Some CI proxies return 504 for the full 135 MB response but support byte ranges.
The archive is a temporary build tool, never a Manager artifact or signing key.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

from build_manager_501_themes import GRADLE_SHA256, ROOT

URL = 'https://downloads.gradle.org/distributions/gradle-9.2.0-bin.zip'
TOTAL = 135_534_361
PART = 2 * 1024 * 1024


def validate_response(headers: str, size: int, start: int, end: int, total: int = TOTAL) -> None:
    matches = re.findall(r'(?im)^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)\s*$', headers)
    if not matches or tuple(map(int, matches[-1])) != (start, end, total) or size != end - start + 1:
        raise ValueError(f'Gradle range {start}-{end} returned wrong offset, length or total')


def fetch(output: Path) -> None:
    output = output.resolve()
    if ROOT == output or ROOT in output.parents:
        raise ValueError('The 135 MB Gradle distribution must stay outside the repository')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gradle501-fetch-', dir=output.parent) as tmp:
        root = Path(tmp)
        partial, headers, chunk = root / 'complete.part', root / 'headers', root / 'chunk'
        digest = hashlib.sha256()
        with partial.open('xb') as assembled:
            for start in range(0, TOTAL, PART):
                end = min(TOTAL - 1, start + PART - 1)
                # Unique URL prevents a shared proxy cache confusing different ranges.
                request_url = f'{URL}?segment={start}-{end}'
                subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                                '--retry', '2', '--retry-all-errors', '--retry-delay', '2',
                                '--connect-timeout', '30', '--max-time', '120',
                                '--range', f'{start}-{end}', '--dump-header', str(headers),
                                '--output', str(chunk), request_url], check=True)
                validate_response(headers.read_text(errors='replace'), chunk.stat().st_size, start, end, TOTAL)
                with chunk.open('rb') as stream:
                    while data := stream.read(1024 * 1024):
                        assembled.write(data)
                        digest.update(data)
                if end == TOTAL - 1 or (start // PART) % 10 == 0:
                    print(f'Gradle distribution: {end + 1}/{TOTAL} bytes verified by range', flush=True)
        if partial.stat().st_size != TOTAL or digest.hexdigest() != GRADLE_SHA256:
            raise ValueError('Gradle distribution SHA-256 mismatch; refusing to use it')
        # Link is atomic and refuses to replace a file created by another process.
        os.link(partial, output)
        print(f'Pinned Gradle 9.2.0 SHA-256 verified: {GRADLE_SHA256}', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    fetch(args.out)


if __name__ == '__main__':
    main()
