#!/usr/bin/env python3
"""Read-only AVB embedded boot hash check; not signature or chain verification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import audit_synthetica3_boot as common

MAX_META = 4 * 1024 * 1024
HEADER = struct.Struct('>4sIIQQI' + 'Q'*10 + 'QII48s80s')
HASH_DESC = struct.Struct('>QQQ32sIIII60s')


def inspect(path: Path) -> dict:
    with common.readonly_file(path) as (f, size):
        footer = common.footer(f, size)
        if not footer['footer_at_end']:
            raise ValueError('AVB footer missing')
        off, n = footer['vbmeta_offset'], footer['vbmeta_bytes']
        if not 256 <= n <= MAX_META:
            raise ValueError('invalid vbmeta size')
        vb = common.read_exact(f, off, n, size)
        h = HEADER.unpack_from(vb)
        if h[0] != b'AVB0':
            raise ValueError('missing vbmeta magic')
        auth, aux, algo = h[3:6]
        desc_off, desc_len = h[14:16]
        if 256 + auth + aux != n or desc_off > aux or desc_len > aux - desc_off:
            raise ValueError('invalid vbmeta block or descriptor bounds')
        descriptors = vb[256+auth+desc_off:256+auth+desc_off+desc_len]
        pos = 0; boot = []
        while pos < len(descriptors):
            if len(descriptors)-pos < 16:
                raise ValueError('short descriptor header')
            tag, following = struct.unpack_from('>QQ', descriptors, pos)
            if following % 8 or following > len(descriptors)-pos-16:
                raise ValueError('invalid descriptor length')
            data = descriptors[pos:pos+16+following]
            pos += len(data)
            if tag != 2:
                continue
            if len(data) < HASH_DESC.size:
                raise ValueError('short hash descriptor')
            _, _, image_size, algorithm, name_len, salt_len, digest_len, flags, _ = HASH_DESC.unpack_from(data)
            varlen = name_len + salt_len + digest_len
            if ((HASH_DESC.size - 16 + varlen + 7) // 8 * 8 != following or
                    HASH_DESC.size + varlen > len(data)):
                raise ValueError('invalid hash descriptor fields')
            try:
                name = data[HASH_DESC.size:HASH_DESC.size+name_len].decode('utf-8')
                algorithm = algorithm.rstrip(b'\0').decode('ascii')
            except UnicodeDecodeError as e:
                raise ValueError('invalid descriptor encoding') from e
            if name != 'boot':
                continue
            if algorithm not in ('sha256', 'sha512') or digest_len != hashlib.new(algorithm).digest_size:
                raise ValueError('unsupported boot hash')
            if not 0 < image_size <= footer['original_image_size']:
                raise ValueError('invalid boot hash image size')
            salt_off = HASH_DESC.size + name_len
            salt = data[salt_off:salt_off+salt_len]
            expected = data[salt_off+salt_len:salt_off+salt_len+digest_len]
            digest = hashlib.new(algorithm); digest.update(salt)
            common.hash_range(f, 0, image_size, size, digest)
            boot.append({'partition': name, 'algorithm': algorithm, 'flags': flags,
                         'image_bytes': image_size, 'digest_matches': digest.digest() == expected})
        if len(boot) != 1:
            raise ValueError('expected exactly one embedded boot hash descriptor')
        return {'file_bytes': size, 'footer': footer, 'vbmeta_algorithm_type': algo,
                'vbmeta_algorithm_none': algo == 0, 'embedded_boot_hash': boot[0],
                'scope': 'Data digest only. Does not verify VBMeta signature, external vbmeta, trust chain, bootloader state, or device boot.'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('image', type=Path)
    args = p.parse_args()
    try:
        result = inspect(args.image); print(json.dumps(result, indent=2))
        return 0 if result['embedded_boot_hash']['digest_matches'] else 1
    except (OSError, ValueError, struct.error) as exc:
        print('AVB audit refused: ' + str(exc), file=sys.stderr); return 2

if __name__ == '__main__':
    raise SystemExit(main())
