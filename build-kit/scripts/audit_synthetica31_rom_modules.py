#!/usr/bin/env python3
"""Offline comparison of supplied ROM modules with the pinned 3.1 build.

Inputs are read-only and a new private report is written outside the repo and
input directories. No device, root, flashing, module loading or modification of
ROM files is involved. Results are *not* a boot or compatibility verdict.
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

import audit_synthetica2_rom_modules as old
import audit_synthetica3_vendor as vendor
import build_synthetica3 as build
import verify_synthetica3_modules as modules

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / 'build-kit/ci/synthetica31-build-evidence.json'
MAX_ARCHIVE = 32 * 1024 * 1024
MEMBERS = {
    'Image.gz.DO-NOT-FLASH', 'STATUS.json', 'generated.config.txt',
    'module-signing-public-cert.x509', 'Module.symvers', 'System.map',
}
FIELDS = {
    'image_sha256': 'Image.gz.DO-NOT-FLASH',
    'config_sha256': 'generated.config.txt',
    'module_public_cert_sha256': 'module-signing-public-cert.x509',
    'module_symvers_sha256': 'Module.symvers',
    'system_map_sha256': 'System.map',
}


def evidence_pins() -> dict:
    pins = json.loads(vendor.read_regular(PINS, 20_000))
    if pins.get('kind') != 'SYNTHETICA_3_1_COMPILE_EVIDENCE_PUBLIC_ONLY':
        raise ValueError('unexpected 3.1 evidence pin kind')
    for key, length in (('transfer_git_blob', 40), ('transfer_sha256', 64),
                        ('image_sha256', 64), ('config_sha256', 64),
                        ('module_public_cert_sha256', 64), ('baseline_3_0_config_sha256', 64)):
        if not isinstance(pins.get(key), str) or not re.fullmatch('[0-9a-f]{%d}' % length, pins[key]):
            raise ValueError('invalid 3.1 evidence pin: ' + key)
    if (pins.get('release') != '4.14.357-openela-synthetica-3.1'
            or pins.get('module_layout_crc') != '0xed5659d1'):
        raise ValueError('unexpected 3.1 release or module_layout pin')
    return pins


def read_evidence(path: Path, pins: dict) -> dict[str, bytes]:
    """Read only the six members of the pinned, public CI evidence archive."""
    raw = vendor.read_regular(path, MAX_ARCHIVE)
    sha = hashlib.sha256(raw).hexdigest()
    git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if sha != pins['transfer_sha256'] or git_blob != pins['transfer_git_blob']:
        raise ValueError('3.1 CI evidence archive hash does not match the pinned build')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) != len(MEMBERS) or {x.filename for x in infos} != MEMBERS:
                raise ValueError('unexpected or duplicate 3.1 evidence members')
            if any(x.is_dir() or x.file_size > 32 * 1024 * 1024 for x in infos):
                raise ValueError('invalid or oversized 3.1 evidence member')
            if archive.testzip():
                raise ValueError('3.1 evidence has a bad ZIP CRC')
            return {name: archive.read(name) for name in MEMBERS}
    except (zipfile.BadZipFile, EOFError, RuntimeError) as exc:
        raise ValueError('invalid 3.1 evidence ZIP') from exc


def load_candidate(path: Path, pins: dict | None = None) -> dict:
    """Bind config, image, module certificate and symbol data to CI evidence."""
    pins = evidence_pins() if pins is None else pins
    data = read_evidence(path, pins)
    status = json.loads(data['STATUS.json'])
    if (status.get('kind') != 'SYNTHETICA_3_1_REBUILT_KERNEL_NOT_DEVICE_VALIDATED'
            or status.get('release') != pins['release']
            or status.get('base_source') != pins['source']
            or status.get('baseline_3_0_config_sha256') != pins['baseline_3_0_config_sha256']
            or status.get('installer_created') is not False
            or status.get('private_key_exported') is not False
            or status.get('module_layout_crc') != pins['module_layout_crc']
            or status.get('mglru', {}).get('variant') != 'on'):
        raise ValueError('unexpected 3.1 compile status')
    for field, name in FIELDS.items():
        actual = hashlib.sha256(data[name]).hexdigest()
        if actual != status.get(field) or (field in pins and actual != pins[field]):
            raise ValueError('3.1 evidence hash mismatch: ' + name)
    config = data['generated.config.txt']
    settings = build.read_config(config.decode('utf-8'))
    if settings.get('MODVERSIONS') != 'y' or settings.get('MODULE_SIG_FORCE') != 'y':
        raise ValueError('unexpected 3.1 module-verification config')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data['Image.gz.DO-NOT-FLASH'])) as image:
            raw = image.read(build.MAX_RAW_IMAGE + 1)
    except (EOFError, OSError) as exc:
        raise ValueError('invalid compressed 3.1 image') from exc
    cert = data['module-signing-public-cert.x509']
    if (len(raw) > build.MAX_RAW_IMAGE or not cert or raw.count(cert) != 1
            or ('Linux version ' + pins['release'] + ' ').encode('ascii') not in raw):
        raise ValueError('3.1 image release or embedded module certificate mismatch')
    build.verify_embedded_config(raw, config)
    symvers_text = data['Module.symvers'].decode('ascii')
    symvers = modules.symvers_records(symvers_text)
    if status['module_layout_crc'] != f"0x{symvers['module_layout']:08x}":
        raise ValueError('3.1 module_layout CRC does not match evidence')
    map_types: dict[str, set[str]] = {}
    for line in data['System.map'].decode('ascii').splitlines():
        row = line.split()
        if len(row) != 3 or not re.fullmatch(r'[0-9a-fA-F]+', row[0]) or len(row[1]) != 1:
            raise ValueError('invalid 3.1 System.map entry')
        map_types.setdefault(row[2], set()).add(row[1])
    builtins = {row[1] for line in symvers_text.splitlines() if len(row := line.split()) >= 3
                and row[2] == 'vmlinux'}
    return {
        'release': pins['release'], 'mode': 'on', 'cert': cert, 'symvers': symvers,
        'map_names': set(map_types), 'map_types': map_types, 'builtins': builtins,
        # The published 3.1 installer contains no .ko; compile-only samples are
        # not evidence that a dependency was bundled in the recovery ZIP.
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
        'Target is the pinned 3.1 CI build, not a verification of the ZIP installed on the affected device. '
        'Signature, CRC or exact vermagic comparison is not a complete loadability or boot verdict.'
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', required=True, type=Path, help='private directory of extracted ROM .ko files')
    parser.add_argument('--evidence', required=True, type=Path, help='exact pinned 3.1 public CI evidence ZIP')
    parser.add_argument('--report', required=True, type=Path, help='new absolute report path outside repository and inputs')
    args = parser.parse_args()
    try:
        protected = [args.modules, args.evidence]
        destination = vendor.validate_output(args.report, protected)
        target = load_candidate(args.evidence)
        # OpenSSL uses short-lived, private host files when checking signatures;
        # the supplied modules and evidence are never modified or executed.
        with tempfile.TemporaryDirectory(prefix='.synthetica31-module-audit-', dir=destination.parent) as scratch:
            old_tempdir = tempfile.tempdir
            try:
                tempfile.tempdir = scratch
                report = audit_modules(args.modules, target)
            finally:
                tempfile.tempdir = old_tempdir
        vendor.write_private(args.report, report, protected)
        print(json.dumps({'summary': report['summary'], 'scope': report['scope']}, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        print('3.1 module audit did not complete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
