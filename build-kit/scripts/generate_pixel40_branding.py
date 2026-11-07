#!/usr/bin/env python3
"""Generate the original, deliberately pixelated 4.0 emblem with the stdlib.

No vendor marks or proprietary fonts are used. Files are checked in so Android
builds do not need Pillow or a network connection to regenerate artwork.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'ci/ksun-pixel40/branding'
DENSITIES = {'mdpi': (48, 108), 'hdpi': (72, 162), 'xhdpi': (96, 216),
             'xxhdpi': (144, 324), 'xxxhdpi': (192, 432)}
# Original 9 x 11 stepped S. Four corner pixels form a status/signal motif.
S = (
    '001111100',
    '011000110',
    '110000000',
    '110000000',
    '011111000',
    '001111100',
    '000001110',
    '000000110',
    '000000110',
    '110001100',
    '011111000',
)


def png(path: Path, width: int, pixel) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack('>I', len(data)) + kind + data +
                struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
    rows = bytearray()
    for y in range(width):
        rows.append(0)
        for x in range(width):
            rows.extend(pixel(x, y, width))
    content = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, width, 8, 6, 0, 0, 0)) +
               chunk(b'IDAT', zlib.compress(bytes(rows), 9)) + chunk(b'IEND', b''))
    path.write_bytes(content)


def render(x: int, y: int, n: int, *, foreground: bool = False, mono: bool = False) -> tuple[int, int, int, int]:
    # A 21x21 grid leaves adaptive-icon safe-zone padding around the symbol.
    gx, gy = x * 21 // n, y * 21 // n
    on_s = 6 <= gx < 15 and 5 <= gy < 16 and S[gy - 5][gx - 6] == '1'
    signal = (gx, gy) in {(15, 4), (16, 4), (16, 5), (16, 6)}
    if on_s or signal:
        return (245, 244, 237, 255) if on_s or mono else (238, 72, 66, 255)
    if foreground or mono:
        return (0, 0, 0, 0)
    return (19, 19, 18, 255)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    png(OUT / 'ic_synthetica_emblem.png', 256, render)
    png(OUT / 'icon-512.png', 512, render)
    for density, (launcher, adaptive) in DENSITIES.items():
        png(OUT / f'ic_launcher-{density}.png', launcher, render)
        png(OUT / f'ic_foreground-{density}.png', adaptive, lambda x, y, n: render(x, y, n, foreground=True))
        png(OUT / f'ic_background-{density}.png', adaptive, lambda _x, _y, _n: (19, 19, 18, 255))
        png(OUT / f'ic_mono-{density}.png', adaptive, lambda x, y, n: render(x, y, n, mono=True))


if __name__ == '__main__':
    main()
