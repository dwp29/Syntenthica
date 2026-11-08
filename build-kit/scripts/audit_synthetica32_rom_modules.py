#!/usr/bin/env python3
"""Compare privately extracted ROM modules with the exact 3.2 compile evidence.

Only read-only, bounded static analysis is performed. The ROM/device, runtime
keyrings, module load order, physical boot and AVB trust remain unverified.
The detailed report must be new and outside the repository and all inputs.
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

import audit_synthetica2_rom_modules as old
import audit_synthetica3_vendor as vendor
import build_synthetica32 as build
import verify_synthetica3_modules as modules

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / 'build-kit/ci/synthetica32-build-evidence.json'
BASE_CONFIG = ROOT / 'artifacts/generated.config.txt'
BASE_SYMVERS = ROOT / 'artifacts/synthetica-3.0/Module.symvers.txt'
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024
MEMBERS = {
    build.IMAGE_NAME, 'STATUS.json', 'generated.config.txt', 'kernel-module-public-cert.x509',
    'Module.symvers.txt', 'System.map.txt', 'README-DO-NOT-FLASH.txt', 'SHA256SUMS.txt',
    'PROVENANCE.json', *(f'signed-modules/{name}.ko' for name in modules.MODULE_CONFIG),
}
FIELDS = {
    'image_sha256': build.IMAGE_NAME,
    'config_sha256': 'generated.config.txt',
    'module_public_cert_sha256': 'kernel-module-public-cert.x509',
    'module_symvers_sha256': 'Module.symvers.txt',
    'system_map_sha256': 'System.map.txt',
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_pins() -> dict:
    pins = json.loads(vendor.read_regular(PINS, 20_000))
    if pins.get('kind') != 'SYNTHETICA_3_2_COMPILE_EVIDENCE_PUBLIC_ONLY':
        raise ValueError('unexpected 3.2 evidence pin kind')
    for key, length in (('transfer_git_blob', 40), ('original_ci_transfer_git_blob', 40),
                        ('commit', 40), ('transfer_sha256', 64), ('original_ci_transfer_sha256', 64),
                        *((field, 64) for field in FIELDS)):
        if not isinstance(pins.get(key), str) or not re.fullmatch('[0-9a-f]{%d}' % length, pins[key]):
            raise ValueError('invalid 3.2 evidence pin: ' + key)
    if (pins.get('release') != build.RELEASE or pins.get('module_layout_crc') != '0x08efcbb0'
            or not isinstance(pins.get('build_run'), int)):
        raise ValueError('unexpected 3.2 release, build run or module_layout pin')
    return pins


def read_evidence(path: Path, pins: dict) -> dict[str, bytes]:
    raw = vendor.read_regular(path, MAX_ARCHIVE)
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if sha(raw) != pins['transfer_sha256'] or blob != pins['transfer_git_blob']:
        raise ValueError('3.2 evidence archive hash does not match the pinned build')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != len(MEMBERS) or {e.filename for e in entries} != MEMBERS:
                raise ValueError('unexpected or duplicate 3.2 evidence members')
            if any(e.is_dir() or e.file_size > MAX_MEMBER for e in entries):
                raise ValueError('invalid or oversized 3.2 evidence member')
            if sum(e.file_size for e in entries) > 160 * 1024 * 1024:
                raise ValueError('3.2 evidence exceeds the bounded total')
            if archive.testzip():
                raise ValueError('3.2 evidence has a bad ZIP CRC')
            return {name: archive.read(name) for name in MEMBERS}
    except (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error) as exc:
        raise ValueError('invalid 3.2 evidence ZIP') from exc


def verify_manifest(data: dict[str, bytes]) -> None:
    """Require exactly one checksum for every other evidence member."""
    entries: dict[str, str] = {}
    for line in data['SHA256SUMS.txt'].decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match.group(2) in entries:
            raise ValueError('invalid or duplicate 3.2 manifest entry')
        checksum, name = match.groups()
        entries[name] = checksum
    if entries.keys() != MEMBERS - {'SHA256SUMS.txt'}:
        raise ValueError('3.2 manifest member set mismatch')
    for name, checksum in entries.items():
        if sha(data[name]) != checksum:
            raise ValueError('3.2 manifest digest mismatch: ' + name)


def load_candidate(path: Path, pins: dict | None = None) -> dict:
    """Verify exact CI evidence, module certificate, config, identity and ABI."""
    pins = evidence_pins() if pins is None else pins
    data = read_evidence(path, pins)
    verify_manifest(data)
    status = json.loads(data['STATUS.json'])
    if (status.get('status') != 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED'
            or status.get('uname_release') != pins['release']
            or status.get('source') != build.base.SOURCE
            or status.get('reference_2_0_generated_config_sha256') != build.base.V2_CONFIG_SHA256
            or status.get('installer_or_boot_image_created') is not False
            or status.get('private_signing_key_exported') is not False
            or status.get('no_experimental_3_1_mglru_or_uclamp_patches') is not True
            or status.get('module_layout_crc') != pins['module_layout_crc']):
        raise ValueError('unexpected 3.2 compile status')
    provenance = json.loads(data['PROVENANCE.json'])
    if (provenance.get('commit') != pins['commit']
            or str(provenance.get('run_id')) != str(pins['build_run'])):
        raise ValueError('3.2 provenance does not match the pinned build')
    for field, name in FIELDS.items():
        actual = sha(data[name])
        if actual != pins[field] or actual != status.get('output_sha256', {}).get(name):
            raise ValueError('3.2 evidence hash mismatch: ' + name)
    for name in modules.MODULE_CONFIG:
        member = f'signed-modules/{name}.ko'
        if sha(data[member]) != status.get('output_sha256', {}).get(member):
            raise ValueError('same-build module hash mismatch: ' + name)
    config = data['generated.config.txt']
    build.check_config(build.base.verified_baseline(BASE_CONFIG), config.decode('utf-8'))
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data[build.IMAGE_NAME])) as image:
            raw = image.read(build.base.MAX_RAW_IMAGE + 1)
    except (EOFError, OSError, zlib.error) as exc:
        raise ValueError('invalid compressed 3.2 image') from exc
    cert = data['kernel-module-public-cert.x509']
    if len(raw) > build.base.MAX_RAW_IMAGE or not cert or raw.count(cert) != 1:
        raise ValueError('3.2 image or embedded module certificate mismatch')
    manager_data = vendor.read_regular(ROOT / 'build-kit/artifacts/manager/MANAGER.json', 20_000)
    if sha(manager_data) != build.base.PINNED_INPUTS['artifacts/manager/MANAGER.json']:
        raise ValueError('pinned manager identity changed')
    build.verify_image(raw, config, json.loads(manager_data))
    symvers_text = data['Module.symvers.txt'].decode('ascii')
    # Compare the complete generated export set, not only module_layout.
    reference = vendor.read_regular(BASE_SYMVERS, MAX_MEMBER)
    if sha(reference) != build.BASE_SYMVERS_SHA256:
        raise ValueError('archived export baseline hash mismatch')
    if build.parse_symvers(reference.decode('ascii')) != build.parse_symvers(symvers_text):
        raise ValueError('3.2 export ABI differs from baseline')
    symvers = modules.symvers_records(symvers_text)
    if pins['module_layout_crc'] != f"0x{symvers['module_layout']:08x}":
        raise ValueError('3.2 module_layout CRC does not match evidence')
    for name in modules.MODULE_CONFIG:
        modules.verify_module(data[f'signed-modules/{name}.ko'], name=name, release=pins['release'],
                              certificate_der=cert, raw_kernel=raw, symvers=symvers)
    map_types: dict[str, set[str]] = {}
    for line in data['System.map.txt'].decode('ascii').splitlines():
        row = line.split()
        if len(row) != 3 or not re.fullmatch(r'[0-9a-fA-F]+', row[0]) or len(row[1]) != 1:
            raise ValueError('invalid 3.2 System.map entry')
        map_types.setdefault(row[2], set()).add(row[1])
    builtins = {row[1] for line in symvers_text.splitlines() if len(row := line.split()) >= 3
                and row[2] == 'vmlinux'}
    return {
        'release': pins['release'], 'mode': 'baseline-without-3.1-mglru', 'cert': cert, 'symvers': symvers,
        'map_names': set(map_types), 'map_types': map_types, 'builtins': builtins,
        # Six modules are compile evidence, not an installer or proof of ROM installation.
        'module_srcversions': {}, 'export_providers': vendor.export_provider_index(symvers_text, set()),
        'image_sha256': pins['image_sha256'], 'certificate_sha256': pins['module_public_cert_sha256'],
    }


def audit_modules(directory: Path, target: dict) -> dict:
    report = old.audit(directory, target)
    report['scope'] = (
        'Offline static comparison only. Supplied files may not be loaded or come from the installed ROM; '
        'the exported build certificate is not an exhaustive runtime keyring audit. '
        'No device, module load, root, flash or boot was tested.'
    )
    report['candidate_installer_contains_modules'] = False
    report['evidence_note'] = (
        'Target is the exact pinned 3.2 compile evidence. Signature, CRC or exact vermagic comparisons '
        'are not a complete loadability or boot verdict; this tool never authorizes flashing.'
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', required=True, type=Path, help='private directory of extracted ROM .ko files')
    parser.add_argument('--evidence', required=True, type=Path, help='exact pinned public 3.2 CI evidence ZIP')
    parser.add_argument('--report', required=True, type=Path, help='new absolute report outside repository and inputs')
    args = parser.parse_args()
    try:
        protected = [args.modules, args.evidence]
        destination = vendor.validate_output(args.report, protected)
        # Keep OpenSSL verification temporaries private and outside the ROM/repo.
        with tempfile.TemporaryDirectory(prefix='.synthetica32-module-audit-', dir=destination.parent) as scratch:
            saved = tempfile.tempdir
            try:
                tempfile.tempdir = scratch
                target = load_candidate(args.evidence)
                report = audit_modules(args.modules, target)
            finally:
                tempfile.tempdir = saved
        vendor.write_private(args.report, report, protected)
        print(json.dumps({'summary': report['summary'], 'scope': report['scope']}, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        print('3.2 module audit did not complete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
