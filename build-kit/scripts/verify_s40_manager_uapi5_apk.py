#!/usr/bin/env python3
"""Static sanity checks for an unsigned, DO-NOT-INSTALL UAPI-5 prototype APK."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import prepare_s40_manager_uapi5 as migration


def arm64_elf(data: bytes, allowed_types: tuple[int, ...]) -> bool:
    return (len(data) >= 20 and data[:6] == b'\x7fELF\x02\x01' and
            struct.unpack_from('<H', data, 16)[0] in allowed_types and
            struct.unpack_from('<H', data, 18)[0] == 183)


def verify(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError('APK must be a regular non-symlink file')
    with zipfile.ZipFile(path) as apk:
        entries = apk.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError('APK has duplicate entries')
        if apk.testzip() is not None:
            raise ValueError('APK ZIP CRC validation failed')
        libs = [name for name in entries if name.startswith('lib/') and name.endswith('.so')]
        if not libs or any(not name.startswith('lib/arm64-v8a/') for name in libs):
            raise ValueError('Unexpected or missing native ABI')
        if any(name.upper().startswith('META-INF/') and name.upper().endswith(('.RSA', '.DSA', '.EC', '.SF'))
               for name in entries):
            raise ValueError('Unexpected v1 APK signature')
        daemon_name = 'lib/arm64-v8a/libksud.so'
        jni_name = 'lib/arm64-v8a/libkernelsu.so'
        for name in (daemon_name, jni_name):
            if name not in entries:
                raise ValueError(f'Missing {name}')
        daemon_info = apk.getinfo(daemon_name)
        pin = migration.PINS['ksud_arm64']
        if daemon_info.file_size != pin['bytes']:
            raise ValueError(f"Unexpected packaged ksud size: {daemon_info.file_size} != {pin['bytes']}")
        daemon = apk.read(daemon_info)
        if hashlib.sha256(daemon).hexdigest() != pin['sha256'] or not arm64_elf(daemon, (2, 3)):
            raise ValueError('Packaged ksud identity or ARM64 ELF mismatch')
        jni_info = apk.getinfo(jni_name)
        if jni_info.file_size > 32 * 1024 * 1024:
            raise ValueError('Unexpected JNI library size')
        if not arm64_elf(apk.read(jni_info), (3,)):
            raise ValueError('Manager JNI is not an ARM64 shared object')
    # Signing-block presence is not sufficient for signature validation. This
    # deliberately only checks absence; CI additionally runs Android apksigner.
    raw = path.read_bytes()
    eocd = raw.rfind(b'PK\x05\x06')
    if eocd < 0 or eocd + 22 > len(raw):
        raise ValueError('APK EOCD missing')
    cd = struct.unpack_from('<I', raw, eocd + 16)[0]
    if cd >= 16 and raw[cd - 16:cd] == b'APK Sig Block 42':
        raise ValueError('Unexpected APK signing block in unsigned prototype')
    return {
        'kind': 'UNSIGNED_MANAGER_UAPI5_STATIC_CHECK_ONLY',
        'apk_sha256': hashlib.sha256(raw).hexdigest(),
        'ksud_sha256': pin['sha256'],
        'jni_abi': 'arm64-v8a',
        'signed': False,
        'runtime_tested': False,
        'installable_release': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.apk), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, struct.error, zipfile.BadZipFile) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
