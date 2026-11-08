#!/usr/bin/env python3
"""Verify pinned 3.2-r1 compile evidence offline; never flash or load modules.

This checks integrity, the complete 3.1 config/exports comparison, embedded
identity and same-build module signatures. It does NOT assess the installed
ROM, runtime keyrings, AVB, physical boot, root or device compatibility.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile
import zlib

import audit_synthetica3_vendor as files
import build_synthetica32_r1 as build

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / 'build-kit/ci/synthetica32-r1-build-evidence.json'
modules = build.modules
IMAGE = 'Image.gz.DO-NOT-FLASH'
CERT = 'module-signing-public-cert.x509'
MODULE_PATHS = {name: f'signed-modules/{name}.ko' for name in modules.MODULE_CONFIG}
MEMBERS = {IMAGE, CERT, 'generated.config.txt', 'Module.symvers', 'System.map',
           'manager-apk_sign.o', 'STATUS.json', 'README-DO-NOT-FLASH.txt',
           'PROVENANCE.json', 'SHA256SUMS.txt', *MODULE_PATHS.values()}
STATUS_HASHES = {'image_sha256': IMAGE, 'config_sha256': 'generated.config.txt',
                 'module_symvers_sha256': 'Module.symvers', 'system_map_sha256': 'System.map',
                 'module_public_cert_sha256': CERT}
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024
MAX_TOTAL = 160 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def pins_from_file(path: Path = PINS) -> dict:
    pins = json.loads(files.read_regular(path, 20_000))
    if pins.get('kind') != 'SYNTHETICA_3_2_R1_COMPILE_EVIDENCE_PUBLIC_ONLY':
        raise ValueError('unexpected evidence pin kind')
    for name, length in (('commit', 40), ('transfer_git_blob', 40),
                         ('transfer_sha256', 64), *((key, 64) for key in STATUS_HASHES)):
        if not isinstance(pins.get(name), str) or not re.fullmatch(f'[0-9a-f]{{{length}}}', pins[name]):
            raise ValueError('invalid evidence pin: ' + name)
    if (pins.get('release') != build.RELEASE or pins.get('module_layout_crc') != '0xed5659d1'
            or not isinstance(pins.get('build_run'), int)):
        raise ValueError('unexpected release, build run or module_layout pin')
    return pins


def read_evidence(path: Path, pins: dict) -> dict[str, bytes]:
    raw = files.read_regular(path, MAX_ARCHIVE)
    if sha(raw) != pins['transfer_sha256'] or blob_sha(raw) != pins['transfer_git_blob']:
        raise ValueError('3.2-r1 evidence archive does not match the pinned build')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != len(MEMBERS) or {e.filename for e in entries} != MEMBERS:
                raise ValueError('unexpected or duplicate 3.2-r1 evidence members')
            if any(e.is_dir() or e.file_size > MAX_MEMBER or (e.flag_bits & 1) for e in entries):
                raise ValueError('invalid, encrypted or oversized evidence member')
            if sum(e.file_size for e in entries) > MAX_TOTAL:
                raise ValueError('evidence exceeds the bounded total')
            if archive.testzip() is not None:
                raise ValueError('bad evidence ZIP CRC')
            return {name: archive.read(name) for name in MEMBERS}
    except (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error) as exc:
        raise ValueError('invalid evidence ZIP') from exc


def verify_manifest(data: dict[str, bytes]) -> None:
    entries: dict[str, str] = {}
    for line in data['SHA256SUMS.txt'].decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match.group(2) in entries:
            raise ValueError('invalid or duplicate evidence checksum')
        checksum, name = match.groups()
        entries[name] = checksum
    if entries.keys() != MEMBERS - {'SHA256SUMS.txt'}:
        raise ValueError('evidence checksum member set differs')
    for name, digest in entries.items():
        if sha(data[name]) != digest:
            raise ValueError('evidence checksum mismatch: ' + name)


def verify_evidence(path: Path, baseline31: Path, symvers31: Path, pins: dict | None = None) -> dict:
    pins = pins_from_file() if pins is None else pins
    data = read_evidence(path, pins)
    verify_manifest(data)
    status = json.loads(data['STATUS.json'])
    provenance = json.loads(data['PROVENANCE.json'])
    if (status.get('kind') != build.STATUS_KIND or status.get('release') != build.RELEASE
            or status.get('base_source') != build.v3.SOURCE
            or status.get('installer_created') is not False or status.get('private_key_exported') is not False
            or status.get('module_layout_crc') != '0xed5659d1'
            or status.get('physical_boot_test_this_image') != 'NOT RUN'
            or status.get('mglru_guard_patch_sha256') != build.PATCH_SHA256
            or status.get('mglru_guard_source_before_sha256') != build.SOURCE_BEFORE
            or status.get('mglru_guard_source_after_sha256') != build.SOURCE_AFTER):
        raise ValueError('unexpected 3.2-r1 compile status')
    if (provenance.get('commit') != pins['commit']
            or str(provenance.get('run_id')) != str(pins['build_run'])):
        raise ValueError('compile provenance does not match the pin')
    for field, member in STATUS_HASHES.items():
        actual = sha(data[member])
        if actual != pins[field] or actual != status.get(field):
            raise ValueError('compile evidence hash mismatch: ' + member)
    manager_hash = status.get('manager', {}).get('apk_sign_object_sha256')
    if sha(data['manager-apk_sign.o']) != manager_hash:
        raise ValueError('Manager object hash differs from compile status')
    config = data['generated.config.txt']
    config_changes = build.compare_31_config(baseline31, config.decode('utf-8'))
    if status.get('changes_from_exact_3_1_config') != config_changes:
        raise ValueError('3.1 config comparison differs from compile status')
    with tempfile.TemporaryDirectory(prefix='synthetica32-r1-evidence-') as d:
        generated = Path(d) / 'Module.symvers'
        generated.write_bytes(data['Module.symvers'])
        exports = build.compare_31_exports(symvers31, generated)
    if status.get('export_abi_against_3_1') != exports:
        raise ValueError('3.1 export comparison differs from compile status')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data[IMAGE])) as image:
            raw = image.read(build.v3.MAX_RAW_IMAGE + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError('invalid compressed kernel image') from exc
    cert = data[CERT]
    if len(raw) > build.v3.MAX_RAW_IMAGE or not cert or raw.count(cert) != 1:
        raise ValueError('image or embedded signing certificate mismatch')
    match = re.search(rb'Linux version ([^\s]+)', raw)
    if not match or match.group(1).decode('ascii', 'replace') != build.RELEASE:
        raise ValueError('image kernel release mismatch')
    build.v3.verify_embedded_config(raw, config)
    manager = build.base.rc.s2x.verify_manager()
    for value in (b'KernelSU', manager['package'].encode(), manager['cert_sha256'].encode()):
        if value not in raw:
            raise ValueError('Manager or KernelSU identity missing from image')
    for value in (manager['package'].encode(), manager['cert_sha256'].encode()):
        if value + b'\0' not in data['manager-apk_sign.o']:
            raise ValueError('Manager identity missing from audited object')
    versions = modules.symvers_records(data['Module.symvers'].decode('ascii'))
    if versions['module_layout'] != 0xed5659d1:
        raise ValueError('module_layout CRC differs')
    recorded_modules = status.get('same_build_modules_static_checks')
    if not isinstance(recorded_modules, dict) or set(recorded_modules) != set(MODULE_PATHS):
        raise ValueError('unexpected same-build module set')
    for name, member in MODULE_PATHS.items():
        checked = modules.verify_module(data[member], name=name, release=build.RELEASE,
                                        certificate_der=cert, raw_kernel=raw, symvers=versions)
        if checked != recorded_modules[name]:
            raise ValueError('same-build module check differs from status: ' + name)
    return {
        'release': build.RELEASE,
        'image_sha256': sha(data[IMAGE]),
        'config_changes_from_3_1': config_changes,
        'exports_compared': exports['exported_records_compared'],
        'same_build_modules_verified_statically': len(MODULE_PATHS),
        'physical_boot_and_rom_module_trust': 'NOT VERIFIED',
        'note': 'Compile evidence only; no installer, module loading or device operations performed.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--config31', required=True, type=Path)
    parser.add_argument('--symvers31', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_evidence(args.evidence, args.config31, args.symvers31), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        print('3.2-r1 evidence verification refused: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
