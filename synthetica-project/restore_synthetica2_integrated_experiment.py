#!/usr/bin/env python3
"""Restore a private, NON-FLASHABLE integrated Joyeuse research archive.

The pinned original ROM and the already-verified base delta are inputs, never
modified. A new host-only boot experiment replaces the old boot only in the
new archive; the previous super patch and aborting installer are preserved.
All reconstructed member bytes and CRCs are read back before publishing.
This does not create an AVB-signed ROM, validate device behavior, or permit
flashing. A real reconstruction still requires the user's private original.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import zipfile

import synthetica2_delta as delta

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("joyeuse_host_boot", ROOT / "synthetica-project/build_joyeuse_boot_host_experiment.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load host boot verification")
boot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boot)

BASE_DELTA = (15_910_995, "71a3b2c81539f83f2675c1d72acc292f61147e266abae7e8647ce4890c26d0c2")
NEW_BOOT = (16_728_064, "5f730a1bba4e08c7458a63d437338f2ed20472ae99e3a38b2ad06023ebf1effc")
DTBO = (25_165_824, delta.DTBO_SHA)
BOOT_REPORT = "audit/boot-host-experiment.json"
README = '''SYNTHETICA 2.0 / JOYEUSE -- KANDIDAT RISET HOST, JANGAN FLASH

Ini BUKAN ROM siap pakai dan BUKAN installer recovery. Installer sengaja
berhenti; jangan flash image secara manual. Boot memakai kernel empat built-in
hasil perbaikan IKCONFIG, bukan backport mi_memory beda SoC yang belum aman.
Ramdisk dan DTB dipertahankan; cmdline meminta SELinux enforcing, tetapi
runtime belum diverifikasi. Ramdisk asli masih memiliki KEEPVERITY=false dan
KEEPFORCEENCRYPT=false; konfigurasi AVB juga membutuhkan pemeriksaan lanjut.

Super memakai delta lama yang mempertahankan delapan penghapusan APK terbatas,
hosts adblock dan proposal fallback MTP; semua baru diuji di host. SpatialFlow
tidak ditambahkan. AVB, tanda tangan dan ABI modul, recovery, boot, dan fitur
perangkat belum terbukti. Arsip berisi firmware privat; jangan publikasikan.
'''.encode()


def verify_boot(image: bytes) -> dict:
    if (len(image), hashlib.sha256(image).hexdigest()) != NEW_BOOT:
        raise ValueError("experimental boot differs from pinned SHA and size")
    parts, fields = boot.parse(image)
    checks = {name: hashlib.sha256(data).hexdigest() for name, data in parts.items()}
    if (checks["kernel"] != boot.KERNEL_SPEC[1] or checks["ramdisk"] != boot.RAMDISK_SHA256
            or checks["dtb"] != boot.DTB_SHA256):
        raise ValueError("boot parts differ from pinned references")
    tokens = b"".join(fields).split()
    if [t for t in tokens if t.startswith(b"androidboot.selinux=")] != [boot.NEW_TOKEN]:
        raise ValueError("boot does not request SELinux enforcing exactly once")
    return {
        "status": "HOST_ONLY_DO_NOT_FLASH", "flashable": False, "device_tested": False,
        "boot_sha256": NEW_BOOT[1], "boot_bytes": NEW_BOOT[0],
        "kernel_sha256": checks["kernel"], "ramdisk_sha256": checks["ramdisk"], "dtb_sha256": checks["dtb"],
        "selinux_header_request": "enforcing", "selinux_runtime": "NOT_VERIFIED",
        "avb_signature": "NOT_VERIFIED", "module_abi_and_signatures": "NOT_VERIFIED",
        "ramdisk_security_note": "Original ramdisk unchanged; KEEPVERITY=false and KEEPFORCEENCRYPT=false require review.",
        "mi_memory_different_soc_donor_included": False, "spatialflow_added": False,
    }


def report_bytes(report: dict) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()


def write_archive(base, source_delta, result, manifest, new_boot: bytes, report: dict,
                  *, windows, dtbo_spec: tuple[int, str]) -> None:
    """Stream a candidate; callers separately validate inputs and readback."""
    result.comment = b'DO NOT FLASH: host-only research archive, not signed or device-tested.'
    with base.open('super.img') as src, source_delta.open('delta/super.patch') as patch, \
            result.open(delta.zip_info(delta.SUPER_NAME, manifest['patch']['super_bytes']), 'w', force_zip64=True) as dest:
        delta.apply_diff(src, patch, dest, manifest['patch'], windows)
    result.writestr(delta.zip_info(delta.BOOT_NAME, len(new_boot)), new_boot)
    with base.open('dtbo.img') as src, result.open(delta.zip_info(delta.DTBO_NAME, dtbo_spec[0]), 'w', force_zip64=True) as dest:
        if delta.copy_member(src, dest) != dtbo_spec:
            raise ValueError("original DTBO does not match its pinned reference")
    for name in delta.DOCS:
        data = README if name == delta.DOCS[0] else delta.read_member(source_delta, 'files/' + name, 2 * 1024 * 1024)
        if name == delta.DOCS[1] and data != delta.INSTALLER or name == delta.DOCS[2] and data != delta.UPDATER:
            raise ValueError("installer must remain inert")
        result.writestr(delta.zip_info(name, len(data)), data)
    data = report_bytes(report)
    result.writestr(delta.zip_info(BOOT_REPORT, len(data)), data)


def verify_archive(result, source_delta, manifest, new_boot: bytes, report: dict,
                   *, dtbo_spec: tuple[int, str]) -> None:
    """Independently read every output member to EOF, validating hashes and CRC."""
    expected = {delta.SUPER_NAME, delta.BOOT_NAME, delta.DTBO_NAME, BOOT_REPORT, *delta.DOCS}
    entries = result.infolist()
    if len(entries) != len(expected) or {i.filename for i in entries} != expected:
        raise ValueError("reconstructed archive member set differs")
    specs = {
        delta.SUPER_NAME: (manifest['patch']['super_bytes'], manifest['patch']['candidate_super_sha256']),
        delta.BOOT_NAME: (len(new_boot), hashlib.sha256(new_boot).hexdigest()),
        delta.DTBO_NAME: dtbo_spec,
    }
    for name, (size, expected_sha) in specs.items():
        if result.getinfo(name).file_size != size:
            raise ValueError("reconstructed member length differs: " + name)
        with result.open(name) as src:
            h = hashlib.sha256()
            total = 0
            while block := src.read(delta.CHUNK):
                total += len(block)
                h.update(block)
            if (total, h.hexdigest()) != (size, expected_sha):
                raise ValueError("reconstructed member hash differs: " + name)
    for name in delta.DOCS:
        expected_data = README if name == delta.DOCS[0] else delta.read_member(source_delta, 'files/' + name, 2 * 1024 * 1024)
        if delta.read_member(result, name, 2 * 1024 * 1024) != expected_data:
            raise ValueError("reconstructed document differs: " + name)
    if delta.read_member(result, BOOT_REPORT, 64 * 1024) != report_bytes(report):
        raise ValueError("boot provenance report differs")


def restore(original: Path, base_delta: Path, new_boot_path: Path, output: Path) -> dict:
    output = output.absolute()
    private_root = (ROOT / '.work-private').resolve()
    if (output.exists() or output.is_symlink() or output.suffix.lower() != '.zip'
            or 'DO-NOT-FLASH' not in output.name or not output.parent.is_dir()
            or not output.resolve().is_relative_to(private_root)):
        raise ValueError("output must be a new DO-NOT-FLASH ZIP in .work-private")
    temporary = output.with_name(output.name + '.INCOMPLETE')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("incomplete output already exists")
    delta.checked_original(original)
    if delta.sha_file(base_delta) != BASE_DELTA:
        raise ValueError("base delta differs from pinned SHA and size")
    new_boot = boot.read_locked(new_boot_path, *NEW_BOOT)
    report = verify_boot(new_boot)
    created = False
    try:
        with zipfile.ZipFile(original) as base, zipfile.ZipFile(base_delta) as source_delta:
            manifest = delta.open_manifest(source_delta)
            if source_delta.testzip() is not None:
                raise ValueError("base delta has a CRC error")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            created = True
            with os.fdopen(fd, 'w+b') as raw:
                with zipfile.ZipFile(raw, 'w', allowZip64=True) as result:
                    write_archive(base, source_delta, result, manifest, new_boot, report,
                                  windows=delta.WINDOWS, dtbo_spec=DTBO)
                raw.flush()
                os.fsync(raw.fileno())
            with zipfile.ZipFile(temporary) as result:
                verify_archive(result, source_delta, manifest, new_boot, report, dtbo_spec=DTBO)
        delta.checked_original(original)
        if delta.sha_file(base_delta) != BASE_DELTA:
            raise ValueError("base delta changed during reconstruction")
        size, digest = delta.sha_file(temporary)
        # A hard link is an atomic no-clobber publish on the same filesystem.
        # os.rename() would overwrite a file created while the 8 GiB stream ran.
        os.link(temporary, output, follow_symlinks=False)
        temporary.unlink()
        return {'status': 'INTEGRATED_HOST_ONLY_DO_NOT_FLASH', 'output': str(output),
                'bytes': size, 'sha256': digest, 'flashable': False, 'device_tested': False,
                'original_rom_unchanged': True, 'archive_members_readback_verified': True,
                'candidate_super_sha256': manifest['patch']['candidate_super_sha256'],
                'boot_sha256': NEW_BOOT[1], 'avb_or_signatures_verified': False}
    except BaseException:
        if created and temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()
        raise


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--base-delta', type=Path, required=True)
    p.add_argument('--boot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(restore(a.original, a.base_delta, a.boot, a.output), indent=2, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, delta.DeltaError) as exc:
        print('Integrated experiment withheld: ' + str(exc), file=sys.stderr)
        sys.exit(1)
