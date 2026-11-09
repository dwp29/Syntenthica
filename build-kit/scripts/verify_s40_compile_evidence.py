#!/usr/bin/env python3
"""Independently audit the pinned 6.18 compile evidence, NEVER flash or load it.

Checks the exported sample modules cryptographically with the ephemeral public
certificate embedded in this particular Image. This does not establish device
boot, ROM trust, runtime root, or compatibility of the other 197 modules.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import verify_synthetica3_modules as module_verify

PIN_FILE = ROOT / 'build-kit/ci/s40-evidence/compile-42545930921.json'
PINS = json.loads(PIN_FILE.read_text())
BOARDS = ('curtana', 'joyeuse')
PANELS = ('huaxing', 'tianma')
DTBS = tuple(f'dtbs/sm7125-xiaomi-{board}-{panel}.dtb.DO-NOT-FLASH'
             for board in BOARDS for panel in PANELS)
SAMPLES = ('tcp_bic', 'tcp_htcp', 'tcp_westwood')
EXPECTED_FILES = frozenset({
    'EVIDENCE.json', 'INPUTS.json', 'Image.gz.DO-NOT-FLASH', 'Module.symvers.txt',
    'README-JANGAN-FLASH.txt', 'SHA256SUMS.txt', 'System.map.txt', 'generated.config.txt',
    'kernel-module-public-cert.x509', 'nm-arm64.DO-NOT-RUN', *DTBS,
    *(f'sample-signed-modules/{name}.ko.DO-NOT-LOAD' for name in SAMPLES),
})
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_ENTRY = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_IMAGE = 128 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_archive(path: Path, expected_hash: str) -> dict[str, bytes]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Evidence archive missing, symlinked, or oversized')
    raw = path.read_bytes()
    if sha(raw) != expected_hash:
        raise ValueError('Evidence archive SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        if set(names) != EXPECTED_FILES:
            raise ValueError('Missing or unexpected evidence ZIP entries')
        if sum(item.file_size for item in infos) > MAX_TOTAL:
            raise ValueError('Evidence ZIP is oversized')
        for item in infos:
            relative = PurePosixPath(item.filename)
            if (relative.is_absolute() or '..' in relative.parts or item.is_dir() or
                    stat.S_ISLNK(item.external_attr >> 16) or item.file_size > MAX_ENTRY):
                raise ValueError(f'Unsafe evidence ZIP entry: {item.filename}')
        return {item.filename: archive.read(item) for item in infos}


def check_manifest(files: dict[str, bytes]) -> None:
    try:
        rows = files['SHA256SUMS.txt'].decode('ascii').splitlines()
    except UnicodeDecodeError as error:
        raise ValueError('SHA256SUMS is not ASCII') from error
    expected: dict[str, str] = {}
    for row in rows:
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', row)
        if not match or match.group(2) in expected:
            raise ValueError('Malformed or duplicate SHA256SUMS entry')
        expected[match.group(2)] = match.group(1)
    if set(expected) != set(files) - {'SHA256SUMS.txt'}:
        raise ValueError('SHA256SUMS does not cover exactly the evidence files')
    for name, digest in expected.items():
        if sha(files[name]) != digest:
            raise ValueError(f'SHA256SUMS mismatch: {name}')


def check_config(text: str, release: str) -> None:
    config = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            config[key] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            config[line[2:-11]] = 'n'
    for key in ('CONFIG_KSU', 'CONFIG_NOMOUNT', 'CONFIG_KPROBES', 'CONFIG_FTRACE',
                'CONFIG_FTRACE_SYSCALLS', 'CONFIG_TRACEPOINTS', 'CONFIG_MODULES',
                'CONFIG_MODULE_SIG', 'CONFIG_MODULE_SIG_FORCE', 'CONFIG_MODULE_SIG_ALL',
                'CONFIG_MODULE_SIG_SHA512', 'CONFIG_MODVERSIONS', 'CONFIG_BASIC_MODVERSIONS',
                'CONFIG_SECURITY_SELINUX', 'CONFIG_SECCOMP_FILTER', 'CONFIG_STACKPROTECTOR_STRONG',
                'CONFIG_LRU_GEN_ENABLED'):
        if config.get(key) != 'y':
            raise ValueError(f'Required configuration missing: {key}')
    suffix = release.removeprefix('6.18.58')
    if config.get('CONFIG_LOCALVERSION') != f'"{suffix}"' or config.get('CONFIG_LOCALVERSION_AUTO', 'n') != 'n':
        raise ValueError('Unexpected local kernel version')


def check_dtb(data: bytes, board: str, panel: str) -> None:
    if len(data) < 40:
        raise ValueError('DTB header truncated')
    magic, total, off_struct, off_strings, off_reserve, version, last_version, _, len_strings, len_struct = \
        struct.unpack_from('>10I', data)
    if (magic != 0xD00DFEED or total != len(data) or version < 17 or last_version > version or
            off_reserve < 40 or off_reserve >= total or off_struct < 40 or off_strings < 40 or
            off_struct + len_struct > total or off_strings + len_strings > total or
            f'xiaomi,{board}'.encode() not in data or b'qcom,sm7125' not in data or panel.encode() not in data):
        raise ValueError(f'Invalid {board}/{panel} DTB header or identifying strings')


def check_nm(data: bytes) -> None:
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('NoMount CLI is not little-endian ELF64')
    kind, machine = struct.unpack_from('<HH', data, 16)
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phentsize, phnum = struct.unpack_from('<HH', data, 54)
    if (kind != 2 or machine != 183 or phentsize != 56 or not 0 < phnum <= 128 or
            phoff < 64 or phoff + phentsize * phnum > len(data)):
        raise ValueError('NoMount CLI is not a bounded arm64 executable')
    if any(struct.unpack_from('<I', data, phoff + i * phentsize)[0] in (2, 3) for i in range(phnum)):
        raise ValueError('NoMount CLI unexpectedly has a dynamic segment/interpreter')


def check_metadata(meta: dict, inputs: dict, pin: dict) -> None:
    exact = {
        'kind': 'EXPERIMENTAL_6_18_COMPILE_EVIDENCE_NOT_A_RELEASE',
        'kernelrelease': pin['kernelrelease'],
        'kernel_source': pin['kernel_source'],
        'ksun_source': pin['ksun_source'],
        'nomount_source': pin['nomount_source'],
        'image_sha256_uncompressed': pin['image_sha256'],
        'image_bytes': pin['image_bytes'],
        'image_runtime_size_bytes': pin['image_runtime_size_bytes'],
        'all_module_count': pin['ci_installed_module_count'],
        'nomount_protocol': 22,
        'ksun_uapi': 5,
        'manager_existing_uapi': 4,
        'susfs_2_4_included': False,
        'flashable': False,
        'physical_boot_tested': False,
        'runtime_root_tested': False,
        'target_rom_module_trust_tested': False,
    }
    for key, value in exact.items():
        if meta.get(key) != value or type(meta.get(key)) is not type(value):
            raise ValueError(f'Evidence metadata mismatch: {key}')
    provenance = meta.get('provenance', {})
    if (provenance.get('GITHUB_REPOSITORY') != 'dwp29/Syntenthica' or
            provenance.get('GITHUB_SHA') != pin['workflow_commit'] or
            provenance.get('GITHUB_RUN_ID') != str(pin['workflow_run']) or
            provenance.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('Unexpected workflow provenance')
    for source, field in (('kernel', 'kernel_source'), ('ksun', 'ksun_source'), ('nomount', 'nomount_source')):
        if inputs[source]['commit'] != pin[field]:
            raise ValueError(f'Pinned {source} source differs')
    if (inputs['susfs_research_only']['included_in_kernel'] is not False or
            inputs['manager_identity']['certificate_sha256'] != pin['manager_certificate_sha256']):
        raise ValueError('Unexpected SUSFS or Manager identity claim')


def verify(path: Path, pin: dict = PINS) -> dict:
    files = read_archive(path, pin['archive_sha256'])
    check_manifest(files)
    meta = json.loads(files['EVIDENCE.json'])
    inputs = json.loads(files['INPUTS.json'])
    check_metadata(meta, inputs, pin)
    if sha(files['INPUTS.json']) != pin['inputs_sha256'] or sha(files['generated.config.txt']) != pin['config_sha256']:
        raise ValueError('Input/config hash mismatch')
    check_config(files['generated.config.txt'].decode('utf-8'), pin['kernelrelease'])
    image_gzip = files['Image.gz.DO-NOT-FLASH']
    if sha(image_gzip) != pin['image_gzip_sha256']:
        raise ValueError('Compressed Image SHA-256 mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(image_gzip)) as stream:
        image = stream.read(MAX_IMAGE + 1)
    if (len(image) > MAX_IMAGE or len(image) != pin['image_bytes'] or sha(image) != pin['image_sha256'] or
            len(image) < 64 or image[56:60] != b'ARM\x64' or
            struct.unpack_from('<Q', image, 16)[0] != pin['image_runtime_size_bytes'] or
            pin['image_runtime_size_bytes'] < len(image)):
        raise ValueError('Uncompressed arm64 Image integrity mismatch')
    cert = files['kernel-module-public-cert.x509']
    if sha(cert) != pin['module_signing_public_cert_sha256'] or image.count(cert) != 1:
        raise ValueError('Image does not contain exactly the pinned build certificate')
    if pin['manager_certificate_sha256'].encode() not in image:
        raise ValueError('Manager certificate digest missing from Image')
    system_map = files['System.map.txt'].decode('utf-8')
    for symbol in ('nomount_init', 'kernelsu_init'):
        if not re.search(r'^[0-9a-f]+ [A-Za-z] ' + symbol + r'$', system_map, re.M):
            raise ValueError(f'Missing init symbol: {symbol}')
    check_nm(files['nm-arm64.DO-NOT-RUN'])
    for board in BOARDS:
        for panel in PANELS:
            check_dtb(files[f'dtbs/sm7125-xiaomi-{board}-{panel}.dtb.DO-NOT-FLASH'], board, panel)
    symvers = module_verify.symvers_records(files['Module.symvers.txt'].decode('utf-8'))
    if f"0x{symvers['module_layout']:08x}" != pin['module_layout_crc']:
        raise ValueError('module_layout CRC mismatch')
    samples = []
    for name in SAMPLES:
        data = files[f'sample-signed-modules/{name}.ko.DO-NOT-LOAD']
        if sha(data) != pin['sample_modules'][name]:
            raise ValueError(f'{name} SHA-256 mismatch')
        samples.append(module_verify.verify_module(data, name=name, release=pin['kernelrelease'],
                       certificate_der=cert, raw_kernel=image, symvers=symvers))
    return {
        'kind': 'PINNED_COMPILE_EVIDENCE_AUDIT_NOT_A_RELEASE',
        'workflow_run': pin['workflow_run'],
        'workflow_commit': pin['workflow_commit'],
        'archive_sha256': pin['archive_sha256'],
        'kernelrelease': pin['kernelrelease'],
        'image_sha256_uncompressed': pin['image_sha256'],
        'exported_symbol_records': len(symvers),
        'module_layout_crc': pin['module_layout_crc'],
        'sample_modules_pkcs7_and_crc_verified': samples,
        'ci_installed_module_count_reported': pin['ci_installed_module_count'],
        'ci_other_modules_cryptographically_verified_by_this_audit': False,
        'susfs_2_4_included': False,
        'flashable': False,
        'physical_boot_tested': False,
        'runtime_root_tested': False,
        'rom_module_trust_tested': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, struct.error, zipfile.BadZipFile, EOFError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
