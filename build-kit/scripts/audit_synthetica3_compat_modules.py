#!/usr/bin/env python3
"""Compare privately extracted ROM modules with the exact 3.0 kernel build.

This is a read-only, offline static comparison; it does not load modules, prove
that a ROM is installed, determine the runtime keyring, or predict boot success.
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

import audit_synthetica2_rom_modules as old
import audit_synthetica3_vendor as vendor
import build_synthetica3 as build
import package_synthetica3_compat as pkg
import verify_synthetica3_modules as modules


FIELDS = {
    'config_sha256': 'generated.config.txt',
    'module_symvers_sha256': 'Module.symvers',
    'system_map_sha256': 'System.map',
    'module_public_cert_sha256': 'module-signing-public-cert.x509',
}


def load_candidate(original_zip: Path, evidence: Path) -> dict:
    """Bind every evidence file to STATUS.json, itself pinned by the 3.0 ZIP."""
    if evidence.is_symlink() or not evidence.is_dir():
        raise ValueError('evidence must be an existing non-symlink directory')
    files = pkg.original_files(original_zip)
    metadata = json.loads(files['BUILD-INFO.json'])
    status_raw = vendor.read_regular(evidence / 'STATUS.json', 200_000)
    if hashlib.sha256(status_raw).hexdigest() != metadata.get('compile_status_sha256'):
        raise ValueError('build status does not match the pinned 3.0 ZIP')
    status = json.loads(status_raw)
    if (status.get('kind') != 'SYNTHETICA_3_0_COMPILED_ONLY_DO_NOT_FLASH'
            or status.get('release') != metadata.get('release')
            or status.get('image_sha256') != metadata.get('image_sha256')
            or status.get('installer_created') is not False
            or status.get('private_key_exported') is not False
            or status.get('mglru', {}).get('variant') != 'on'):
        raise ValueError('unexpected 3.0 build evidence')
    data: dict[str, bytes] = {}
    for field, name in FIELDS.items():
        content = vendor.read_regular(evidence / name, old.MAX_TEXT)
        if hashlib.sha256(content).hexdigest() != status.get(field):
            raise ValueError(f'evidence hash mismatch: {name}')
        data[name] = content
    if (status['config_sha256'] != metadata.get('config_sha256')
            or status['module_public_cert_sha256'] != metadata.get('module_public_cert_sha256')):
        raise ValueError('configuration or certificate does not match the 3.0 ZIP')
    cert, config = data['module-signing-public-cert.x509'], data['generated.config.txt']
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(files['Image.gz'])) as f:
            image = f.read(build.MAX_RAW_IMAGE + 1)
    except (EOFError, OSError) as exc:
        raise ValueError('invalid compressed kernel') from exc
    if (len(image) > build.MAX_RAW_IMAGE or not cert or image.count(cert) != 1
            or ('Linux version ' + status['release'] + ' ').encode() not in image):
        raise ValueError('kernel banner or embedded certificate is not verified')
    build.verify_embedded_config(image, config)
    symvers_text = data['Module.symvers'].decode('ascii')
    symvers = modules.symvers_records(symvers_text)
    if status.get('module_layout_crc') != f"0x{symvers['module_layout']:08x}":
        raise ValueError('module_layout CRC does not match build status')
    map_types: dict[str, set[str]] = {}
    for line in data['System.map'].decode('ascii').splitlines():
        row = line.split()
        if len(row) != 3 or not re.fullmatch(r'[0-9a-fA-F]+', row[0]) or len(row[1]) != 1:
            raise ValueError('invalid System.map entry')
        map_types.setdefault(row[2], set()).add(row[1])
    builtins = {row[1] for line in symvers_text.splitlines() if len(row := line.split()) >= 3
                and row[2] == 'vmlinux'}
    return {
        'release': status['release'], 'mode': status['mglru']['variant'], 'cert': cert,
        'symvers': symvers, 'map_names': set(map_types), 'map_types': map_types, 'builtins': builtins,
        # The flashable 3.0 ZIP contains no .ko; do not mark compile-time
        # provider names as modules bundled with this installer.
        'module_srcversions': {}, 'export_providers': vendor.export_provider_index(symvers_text, set()),
        'image_sha256': status['image_sha256'], 'certificate_sha256': status['module_public_cert_sha256'],
    }


def audit_modules(directory: Path, target: dict) -> dict:
    report = old.audit(directory, target)
    report['scope'] = ('Static comparison only; supplied modules may not be loaded or from the installed ROM. '
                       'The build certificate is not an exhaustive runtime keyring audit; no device test was performed.')
    report['candidate_installer_contains_modules'] = False
    report['evidence_note'] = ('All evidence hashes were bound to the published 3.0 ZIP; '
                               'version/signature matches still do not prove successful loading or boot.')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', required=True, type=Path, help='private extracted ROM .ko directory')
    parser.add_argument('--original', required=True, type=Path, help='pinned published 3.0 ZIP')
    parser.add_argument('--evidence', required=True, type=Path, help='3.0 compile evidence directory')
    parser.add_argument('--report', required=True, type=Path, help='new absolute report outside repository and inputs')
    args = parser.parse_args()
    try:
        protected = [args.modules, args.evidence]
        destination = vendor.validate_output(args.report, protected)
        target = load_candidate(args.original, args.evidence)
        # Keep OpenSSL verifier's temporary module payloads private and outside
        # the repository/ROM inputs; do not change or load any supplied module.
        with tempfile.TemporaryDirectory(prefix='.synthetica3-module-audit-', dir=destination.parent) as scratch:
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
        print('3.0 module audit did not complete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
