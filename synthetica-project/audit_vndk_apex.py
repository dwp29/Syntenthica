#!/usr/bin/env python3
"""Inspect the candidate's existing VNDK 30 APEX as bounded data only.

The package and payload are temporary copies from a hash-verified extent; no
candidate, device or signature is modified. AVB key/header observations are
structural only and do not verify signatures, trust, activation or ABI.
"""
from __future__ import annotations

import hashlib
import re
import stat
import struct
import tempfile
import zipfile
from pathlib import Path

import audit_runtime_apex as runtime
import audit_vendor_abi as abi
import audit_vendor_elf_metadata as elf
import audit_vintf_candidate as inventory

APEX_PATH = '/apex/com.android.vndk.v30.apex'
EXPECTED_SHA256 = 'bd9fd612ddf6e42431ee0ebd680bd306505bc5abc1cf5afef5b0ba09af0089b3'
EXPECTED_BYTES = 114769920
MAX_SMALL = 1024 * 1024
MAX_VBMETA = 16 * 1024 * 1024
HEADER_FORMAT = '!4s2L2QL2Q2Q2Q2Q2QQLL47sx80x'


class VndkApexError(RuntimeError):
    pass


def small_member(archive: zipfile.ZipFile, name: str) -> bytes:
    items = [i for i in archive.infolist() if i.filename == name]
    if len(items) != 1:
        raise VndkApexError('Missing or duplicate selected APEX member')
    item = items[0]
    if (item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1
            or not 0 < item.file_size <= MAX_SMALL):
        raise VndkApexError('Unsafe selected APEX member')
    data = archive.read(item)
    if len(data) != item.file_size:
        raise VndkApexError('Selected APEX member length mismatch')
    return data


def _varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise VndkApexError('Truncated protobuf varint')
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise VndkApexError('Protobuf varint overflow')
        value |= (byte & 127) << (7 * index)
        if byte < 128:
            return value, offset
    raise VndkApexError('Unterminated protobuf varint')


def parse_apex_manifest(data: bytes) -> dict:
    """Read selected ApexManifest proto3 fields; skip bounded unknown fields."""
    if not data or len(data) > MAX_SMALL:
        raise VndkApexError('Invalid APEX protobuf length')
    offset, fields, seen = 0, 0, {}
    while offset < len(data):
        fields += 1
        if fields > 10000:
            raise VndkApexError('APEX protobuf field limit exceeded')
        tag, offset = _varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise VndkApexError('Invalid APEX protobuf field number')
        if wire == 0:
            value, offset = _varint(data, offset)
        elif wire == 2:
            length, offset = _varint(data, offset)
            if length > MAX_SMALL or length > len(data) - offset:
                raise VndkApexError('Invalid APEX protobuf length-delimited field')
            value, offset = data[offset:offset + length], offset + length
        elif wire in (1, 5):
            length = 8 if wire == 1 else 4
            if length > len(data) - offset:
                raise VndkApexError('Truncated APEX protobuf fixed field')
            value, offset = data[offset:offset + length], offset + length
        else:
            raise VndkApexError('Unsupported APEX protobuf wire type')
        if number in (1, 2, 6, 14):
            expected_wire = {1: 2, 2: 0, 6: 0, 14: 2}[number]
            if number in seen or wire != expected_wire:
                raise VndkApexError('Duplicate or mistyped APEX protobuf field')
            seen[number] = value
    name = seen.get(1, b'')
    version_vndk = seen.get(14, b'')
    if not re.fullmatch(rb'[A-Za-z0-9_.-]{1,200}', name):
        raise VndkApexError('Unexpected APEX manifest name')
    if version_vndk and not re.fullmatch(rb'[A-Za-z0-9_.-]{1,64}', version_vndk):
        raise VndkApexError('Unexpected APEX VNDK version field')
    if seen.get(6, 0) not in (0, 1):
        raise VndkApexError('Unexpected APEX noCode field')
    return {'name': name.decode('ascii'), 'version': seen.get(2, 0),
            'vndk_version_field': version_vndk.decode('ascii'),
            'no_code': bool(seen.get(6, 0)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def avb_header_observation(payload: Path, bundled_key: bytes) -> dict:
    """Compare the bounded vbmeta key to the bundled key, NOT signature verification."""
    length = payload.stat().st_size
    if length < 64:
        return {'status': 'missing_or_invalid_footer'}
    with payload.open('rb') as stream:
        stream.seek(-64, 2)
        footer = stream.read(64)
        magic, major, minor, original, offset, size, _ = struct.unpack('>4sIIQQQ28s', footer)
        if (magic != b'AVBf' or original > length or size < 256 or size > MAX_VBMETA
                or offset > length - 64 or size > length - 64 - offset):
            return {'status': 'missing_or_invalid_footer'}
        stream.seek(offset)
        header = stream.read(256)
        if len(header) != 256 or struct.calcsize(HEADER_FORMAT) != 256:
            raise VndkApexError('Malformed vbmeta header')
        fields = struct.unpack(HEADER_FORMAT, header)
        if fields[0] != b'AVB0':
            raise VndkApexError('Invalid vbmeta header magic')
        auth_size, aux_size, algorithm = fields[3], fields[4], fields[5]
        key_offset, key_size = fields[10], fields[11]
        if (auth_size > size - 256 or aux_size > size - 256 - auth_size
                or key_offset > aux_size or key_size > aux_size - key_offset or key_size > MAX_SMALL):
            raise VndkApexError('Invalid vbmeta block bounds')
        stream.seek(offset + 256 + auth_size + key_offset)
        public_key = stream.read(key_size)
        if len(public_key) != key_size:
            raise VndkApexError('Short vbmeta public key read')
    return {'status': 'footer_and_header_read', 'footer_version': f'{major}.{minor}',
            'vbmeta_algorithm_type': algorithm, 'vbmeta_bytes': size,
            'vbmeta_public_key_bytes': len(public_key),
            'vbmeta_public_key_sha256': hashlib.sha256(public_key).hexdigest(),
            'public_key_matches_bundled_apex_pubkey': public_key == bundled_key,
            'signature_or_hashtree_verified': False, 'signer_trusted': 'not_assessed'}


def inspect_ext4_payload(payload: Path, outer_manifest: bytes) -> tuple[dict, set[tuple[int, str]]]:
    disk, fs = elf._open_ext4(payload)
    inner = fs.open(path='/apex_manifest.pb')
    if inner.info.meta is None or inner.info.meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG:
        raise VndkApexError('Inner APEX manifest is not a regular file')
    size = int(inner.info.meta.size)
    if not 0 < size <= MAX_SMALL:
        raise VndkApexError('Inner APEX manifest exceeds bounds')
    data = inner.read_random(0, size)
    if len(data) != size:
        raise VndkApexError('Short inner manifest read')
    providers = set()
    roots = []
    for bits, path in ((32, '/lib'), (64, '/lib64')):
        try:
            root = fs.open(path=path)
        except (OSError, RuntimeError):
            roots.append({'path': path, 'status': 'missing_or_unreadable'})
            continue
        if root.info.meta is None or root.info.meta.type != inventory.pytsk3.TSK_FS_META_TYPE_DIR:
            roots.append({'path': path, 'status': 'not_directory_or_symlink'})
            continue
        row = {'path': path, 'status': 'read', 'entries': 0, 'matching_elf_headers': 0,
               'symlinks_not_followed': 0, 'other_library_names': 0}
        for entry in fs.open_dir(inode=int(root.info.meta.addr)):
            info, meta = entry.info.name, entry.info.meta
            if not info or not info.name or not info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC:
                continue
            raw = bytes(info.name)
            if raw in (b'.', b'..'):
                continue
            row['entries'] += 1
            if row['entries'] > 5000:
                raise VndkApexError('APEX library directory entry limit exceeded')
            try:
                name = raw.decode('ascii', 'strict')
            except UnicodeError:
                continue
            if not abi.LIBNAME.fullmatch(name):
                continue
            if meta is None:
                row['other_library_names'] += 1
            elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
                row['symlinks_not_followed'] += 1
            elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_REG and abi.header_arch(
                    entry, int(meta.size)) == (bits, 40 if bits == 32 else 183, 3):
                row['matching_elf_headers'] += 1
                providers.add((bits, name))
            else:
                row['other_library_names'] += 1
        roots.append(row)
    return ({'inner_manifest': parse_apex_manifest(data),
             'inner_and_outer_manifest_bytes_identical': data == outer_manifest,
             'library_roots': roots}, providers)


def inspect_system_ext(image: Path, avb_verifier=None) -> tuple[dict, set[tuple[int, str]]]:
    disk, fs = elf._open_ext4(image)
    try:
        entry = fs.open(path=APEX_PATH)
    except (OSError, RuntimeError) as exc:
        raise VndkApexError('Pinned VNDK 30 APEX missing') from exc
    meta = entry.info.meta
    if (meta is None or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG
            or not meta.flags & inventory.pytsk3.TSK_FS_META_FLAG_ALLOC or int(meta.size) != EXPECTED_BYTES):
        raise VndkApexError('Pinned VNDK 30 APEX type or size mismatch')
    with tempfile.TemporaryDirectory(prefix='vndk30-apex-audit-', dir=image.parent) as temp:
        root = Path(temp)
        package, payload = root / 'package.apex', root / 'payload.img'
        digest = runtime.copy_tsk_entry(entry, EXPECTED_BYTES, package, runtime.MAX_APEX)
        if digest != EXPECTED_SHA256:
            raise VndkApexError('Pinned VNDK 30 APEX digest mismatch')
        with zipfile.ZipFile(package) as z:
            if len(z.infolist()) > runtime.MAX_MEMBERS:
                raise VndkApexError('APEX member count exceeded')
            manifest = small_member(z, 'apex_manifest.pb')
            key = small_member(z, 'apex_pubkey')
            outer = parse_apex_manifest(manifest)
        payload_info = runtime.extract_payload(package, payload)
        fmt = runtime.payload_format(payload)
        result = {'path': APEX_PATH, 'bytes': EXPECTED_BYTES, 'sha256': digest,
                  'outer_manifest': outer, 'bundled_public_key_sha256': hashlib.sha256(key).hexdigest(),
                  'payload': {**payload_info, 'filesystem': fmt,
                              'avb_structure': avb_header_observation(payload, key)},
                  'limitations': ['No device or candidate image was modified.',
                      'A matching embedded public key is not signature, signer trust, or boot verification.',
                      'Library names and ELF headers do not prove symbol ABI or Android linker reachability.']}
        if avb_verifier is not None:
            verification = avb_verifier(payload)
            if verification.get('input_sha256') != payload_info['sha256']:
                raise VndkApexError('Isolated AVB verifier input differs from extracted payload')
            result['payload']['avb_verification'] = verification
        if fmt == 'ext4':
            observations, providers = inspect_ext4_payload(payload, manifest)
            result['payload'].update(observations)
        else:
            providers = set()
            result['payload']['library_inventory'] = 'not_inspected_unsupported_filesystem'
        return result, providers


def summarize_vendor_references(collector: abi.Collector, providers: set[tuple[int, str]], available: bool) -> dict:
    result = {'vendor_executable_stats': dict(collector.stats),
              'vendor_unique_needed_bitness_name_pairs': len(collector.references),
              'apex_library_roots_scanned': available}
    if available:
        overlap = [(bits, name, refs) for (bits, name), refs in collector.references.items()
                   if (bits, name) in providers]
        overlap.sort(key=lambda item: (-item[2], item[0], item[1]))
        result.update({'candidate_vndk30_name_and_basic_elf_header_matches': len(overlap),
                       'dependency_edges_referencing_those_names': sum(x[2] for x in overlap),
                       'examples': [{'bits': b, 'name': n, 'referenced_by': r} for b, n, r in overlap[:20]]})
    return result
