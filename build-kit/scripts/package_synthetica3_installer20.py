#!/usr/bin/env python3
"""Repackage the exact 3.0 kernel with the exact 2.0 release installer.

Only the Image.gz and display identity are changed; no guard is invented and
no installer script is executed.  The original 2.0 installer can write ksud
under /data before attempting boot.  Its absence of several 3.0 guards is an
intentional consequence of matching 2.0, not a compatibility or safety claim.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE20_SHA = 'b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
SOURCE30_SHA = '16b32f57381005c08cbee0ec684397dc91acc77f5b2ccbb4ef7f4b99a9a791e6'
IMAGE30_SHA = '92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb'
KSUD_SHA = '52ba3da465459bfbac98dd25c53f8d31f93ee5a8ee89d84f67a28fe0d18cdef2'
UNAME = '4.14.357-openela-synthetica-3.0'
VERSION = '3.0 (installer 2.0 TEST)'
BINARY = 'META-INF/com/google/android/update-binary'
UPDATER = 'META-INF/com/google/android/updater-script'
SOURCE20_MEMBERS = frozenset((
    'BUILD-INFO.txt', 'Image.gz', 'LICENSE', BINARY, UPDATER, 'README-FLASH.txt',
    'anykernel.sh', 'ksud', 'tools/ak3-core.sh', 'tools/busybox', 'tools/fec',
    'tools/httools_static', 'tools/lptools_static', 'tools/magiskboot',
    'tools/magiskpolicy', 'tools/snapshotupdater_static',
))
SOURCE30_MEMBERS = frozenset((
    'BUILD-INFO.json', 'Image.gz', 'LICENSE', BINARY, UPDATER, 'README-FLASH.txt',
    'anykernel.sh', 'banner', 'tools/busybox', 'tools/magiskboot', 'tools/prepare-boot.sh',
))

README = f'''SY N T H E T I C A  3.0 — INSTALLER 2.0, KANDIDAT UJI

Paket ini memakai Image.gz 3.0 yang sudah dikompilasi sebelumnya dan installer
AnyKernel rilis 2.0. Kernel TIDAK dikompilasi ulang atau diubah. Semua skrip
installer 2.0 dipertahankan; hanya label versi dan uname yang diperbarui.
Tidak ada uji recovery atau boot fisik untuk paket ini. Tidak ada jaminan boot,
root, AVB, modul, kamera, atau kompatibilitas untuk ROM/perangkat tertentu.

PENTING SEBELUM MENCOBA
- Pastikan bootloader terbuka dan perangkat, ROM dan recovery memang cocok.
- Simpan backup boot yang TEPAT untuk kondisi perangkat sekarang di tempat
  terpisah, dan pastikan cara restore melalui recovery. Paket TIDAK membuat
  backup otomatis. Jika gagal saat penulisan, jangan reboot sebelum restore.
- Installer 2.0 ini TIDAK memiliki pemeriksaan slot/unlock, hash DTB, ramdisk,
  dan readback pascatulis setara installer 3.0 asli. IS_SLOT_DEVICE=0 bukan
  bukti bahwa perangkat tidak memiliki slot. Jangan flash jika ragu slotnya.
- Sebelum boot ditulis, installer dapat me-mount /data read-write dan
  MENGGANTI /data/adb/ksud dengan daemon yang dibawa 2.0. Aksi itu mungkin
  terjadi meskipun flash boot kemudian gagal. Jika data terkunci, ksud dilewati.
- Tidak ada DTB/DTBO atau modul di paket. AnyKernel dapat mem-patch DTB/AVB
  dalam kondisi tertentu (misalnya Magisk); tidak ada jaminan signature AVB
  valid. Jangan mengubah vbmeta atau wipe data untuk memaksa boot.
- Installer tidak reboot otomatis. Log dicoba di penyimpanan bila tersedia.

ZIP basis 2.0 SHA-256: {SOURCE20_SHA}
ZIP kernel asli 3.0 SHA-256: {SOURCE30_SHA}
Image.gz 3.0 SHA-256: {IMAGE30_SHA}
ksud dari 2.0 SHA-256: {KSUD_SHA}
uname kernel: {UNAME}
'''.encode('utf-8')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_archive(path: Path, expected_sha: str, expected_size: int,
                 expected_members: frozenset[str]) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'input must be a regular file: {path}')
    if path.stat().st_size != expected_size:
        raise ValueError(f'input size mismatch: {path}')
    raw = path.read_bytes()
    if len(raw) != expected_size or sha(raw) != expected_sha:
        raise ValueError(f'input SHA-256 mismatch: {path}')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or frozenset(names) != expected_members:
            raise ValueError(f'unexpected or duplicate ZIP entries: {path}')
        if any(z.getinfo(name).file_size > 20_000_000 for name in names) or z.testzip():
            raise ValueError(f'oversized or corrupt ZIP entry: {path}')
        return {name: z.read(name) for name in names}


def change_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise ValueError(f'expected one installer identity line: {old!r}')
    return data.replace(old, new, 1)


def assemble(source20: Path, source30: Path) -> dict[str, bytes]:
    two = read_archive(source20, SOURCE20_SHA, 21_567_245, SOURCE20_MEMBERS)
    three = read_archive(source30, SOURCE30_SHA, 15_719_303, SOURCE30_MEMBERS)
    info = json.loads(three['BUILD-INFO.json'])
    if sha(three['Image.gz']) != IMAGE30_SHA or info.get('image_sha256') != IMAGE30_SHA:
        raise ValueError('3.0 kernel identity mismatch')
    if info.get('release') != UNAME or sha(two['ksud']) != KSUD_SHA:
        raise ValueError('3.0 release or 2.0 ksud identity mismatch')
    entry = change_once(two['anykernel.sh'], b'SP_VERSION="2.0"',
                        f'SP_VERSION="{VERSION}"'.encode())
    entry = change_once(entry, b'SP_UNAME="4.14.357-openela-Synthetica-2.0"',
                        f'SP_UNAME="{UNAME}"'.encode())
    two['Image.gz'] = three['Image.gz']
    two['anykernel.sh'] = entry
    two['README-FLASH.txt'] = README
    metadata = {
        'kind': 'SYNTHETICA_3_0_2_0_INSTALLER_TEST_NOT_DEVICE_VALIDATED',
        'release': UNAME,
        'kernel_rebuilt_for_this_package': False,
        'kernel_image_sha256': IMAGE30_SHA,
        'source_2_0_zip_sha256': SOURCE20_SHA,
        'source_3_0_zip_sha256': SOURCE30_SHA,
        'ksud_from_2_0_sha256': KSUD_SHA,
        'installer_changes': ['SP_VERSION label', 'SP_UNAME label'],
        'physical_recovery_or_boot_test_of_this_package': 'NOT RUN',
        'rom_module_abi_and_signatures': 'NOT VERIFIED',
        'avb_signature_after_repack': 'NOT VERIFIED',
        'boot_backup_automatic': False,
        'installer_side_effects': '2.0 backend may mount filesystems; ksud may be copied into /data/adb before boot write',
        'dtb_policy': '2.0 AnyKernel behavior; no 3.0 fixed DTB hash guard',
    }
    two['BUILD-INFO.txt'] = (json.dumps(metadata, indent=2, ensure_ascii=False) + '\n').encode()
    return two


def package(source20: Path, source30: Path, output: Path) -> dict[str, object]:
    files = assemble(source20, source30)
    if output.exists() or output.is_symlink():
        raise ValueError(f'refusing to overwrite output: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            created = True
            for name, data in sorted(files.items()):
                entry = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
                entry.create_system = 3
                executable = name in (BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                entry.external_attr = (0o100755 if executable else 0o100644) << 16
                z.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or set(names) != set(files) or z.testzip():
                raise ValueError('output ZIP failed entry or CRC verification')
            for name in names:
                executable = name in (BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                if z.read(name) != files[name] or z.getinfo(name).external_attr >> 16 != (0o100755 if executable else 0o100644):
                    raise ValueError(f'output verification failed: {name}')
        return {'path': str(output), 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes()),
                'image_sha256': IMAGE30_SHA, 'physical_boot_test': False}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source20', type=Path, default=ROOT / 'release/Synthetica-2.0.zip')
    parser.add_argument('--source30', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.source20, args.source30, args.output), indent=2))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f'Packaging failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
