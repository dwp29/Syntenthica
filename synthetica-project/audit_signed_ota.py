#!/usr/bin/env python3
"""Fail-closed host audit of one signed OTA against a pinned unsigned reference.

This does not sign or build anything, access a device, establish the recovery's
trusted keys, validate AVB, or approve a flash. Both ZIP SHA-256 pins and the
public-key pin must come from an independent, trusted source. The archives are
streamed; no ROM members are extracted or executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
import sys
import zipfile
from pathlib import Path

import audit_recovery_signature as signature
import build_ota_metadata_candidate as ota
import verify_preservation as guard

CHUNK = guard.CHUNK
OTACERT = 'META-INF/com/android/otacert'
REQUIRED = {
    ota.METADATA, ota.METADATA_PB, OTACERT,
    'META-INF/com/google/android/updater-script',
    'META-INF/com/google/android/update-binary',
    'super.img', 'boot.img', 'dtbo.img',
}
CHANGED = {ota.METADATA, ota.METADATA_PB, OTACERT}
LOCAL = struct.Struct('<4sHHHHHIIIHH')
HEX_SHA256 = re.compile(r'^[0-9a-f]{64}$')


class SignedOtaError(Exception):
    """The input failed a bounded identity, preservation, or OTA check."""


def _hash_open(stream, length: int) -> str:
    stream.seek(0)
    digest, remaining = hashlib.sha256(), length
    while remaining:
        data = stream.read(min(CHUNK, remaining))
        if not data:
            raise SignedOtaError('Archive ended while being hashed')
        digest.update(data)
        remaining -= len(data)
    return digest.hexdigest()


def _index(z: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = z.infolist()
    if not 1 <= len(infos) <= guard.MAX_ENTRIES:
        raise SignedOtaError('ZIP entry count is outside the audit limit')
    seen, files, total = set(), {}, 0
    for info in infos:
        name, directory = info.filename, info.is_dir()
        if (info.orig_filename != name or not guard._safe_name(name, directory)
                or name in seen):
            raise SignedOtaError('Unsafe, truncated, or duplicate ZIP entry name')
        seen.add(name)
        mode = stat.S_IFMT(info.external_attr >> 16)
        if mode not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
            raise SignedOtaError(f'Special or inconsistent ZIP member type: {name}')
        if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise SignedOtaError(f'Encrypted or unsupported ZIP member: {name}')
        if info.file_size < 0 or info.compress_size < 0:
            raise SignedOtaError(f'Invalid ZIP member size: {name}')
        if directory:
            if info.file_size or info.compress_size:
                raise SignedOtaError(f'Directory has file content: {name}')
            continue  # SignApk may omit directory records.
        total += info.file_size
        if total > guard.MAX_TOTAL_EXPANDED:
            raise SignedOtaError('ZIP expanded contents exceed the 16 GiB audit limit')
        files[name] = info
    if not REQUIRED <= files.keys():
        raise SignedOtaError('ZIP is missing required OTA, installer, image or otacert members')
    return files


def _small(z: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if not 0 < info.file_size <= limit:
        raise SignedOtaError(f'Empty or oversized small member: {info.filename}')
    # ZipFile.read reaches EOF and verifies the central-directory CRC.
    data = z.read(info)
    if len(data) != info.file_size:
        raise SignedOtaError(f'Incomplete member: {info.filename}')
    return data


def _stored_data_offset(z: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    """Cross-check the local header for a small, stored property-file member."""
    if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & (1 | 8):
        raise SignedOtaError(f'Property-file entry is not directly readable STORED data: {info.filename}')
    if info.header_offset < 0 or info.header_offset + LOCAL.size > z.start_dir:
        raise SignedOtaError('Property-file local header is outside the data region')
    f = z.fp
    f.seek(info.header_offset)
    data = f.read(LOCAL.size)
    if len(data) != LOCAL.size:
        raise SignedOtaError('Truncated local ZIP header')
    magic, _, flags, method, _, _, crc, compressed, expanded, nlen, xlen = LOCAL.unpack(data)
    name, extra = f.read(nlen), f.read(xlen)
    if (magic != b'PK\x03\x04' or flags != info.flag_bits or method != info.compress_type
            or name != info.filename.encode('utf-8') or len(extra) != xlen or crc != info.CRC):
        raise SignedOtaError(f'Property-file local/central header mismatch: {info.filename}')
    if compressed == 0xffffffff or expanded == 0xffffffff:
        if compressed != 0xffffffff or expanded != 0xffffffff:
            raise SignedOtaError('Unsupported partial ZIP64 property-file size')
        values, pos = None, 0
        while pos < len(extra):
            if len(extra) - pos < 4:
                raise SignedOtaError('Truncated ZIP extra field')
            kind, size = struct.unpack_from('<HH', extra, pos)
            pos += 4
            if size > len(extra) - pos:
                raise SignedOtaError('Truncated ZIP extra data')
            if kind == 1:
                if values is not None or size < 16:
                    raise SignedOtaError('Invalid duplicate/short ZIP64 extra field')
                values = struct.unpack_from('<QQ', extra, pos)
            pos += size
        if values != (info.file_size, info.compress_size):
            raise SignedOtaError('ZIP64 property-file sizes differ from the central directory')
    elif (expanded, compressed) != (info.file_size, info.compress_size):
        raise SignedOtaError('Property-file local sizes differ from the central directory')
    offset = info.header_offset + LOCAL.size + nlen + xlen
    if offset + info.compress_size > z.start_dir:
        raise SignedOtaError('Property-file data overlaps the central directory')
    return offset


def _metadata(reference: zipfile.ZipFile, rfiles: dict, signed: zipfile.ZipFile, sfiles: dict) -> dict:
    old_text = _small(reference, rfiles[ota.METADATA], ota.MAX_METADATA)
    old_pb = _small(reference, rfiles[ota.METADATA_PB], ota.MAX_METADATA)
    new_text = _small(signed, sfiles[ota.METADATA], ota.MAX_METADATA)
    new_pb = _small(signed, sfiles[ota.METADATA_PB], ota.MAX_METADATA)
    old_props, old_order = ota.property_values(old_text, old_pb)
    new_props, new_order = ota.property_values(new_text, new_pb)
    if old_props.keys() != new_props.keys() or old_order != new_order:
        raise SignedOtaError('OTA property keys or referenced member order changed')
    old_lines, _ = ota.parse_legacy(old_text)
    new_lines, _ = ota.parse_legacy(new_text)
    if len(old_lines) != len(new_lines):
        raise SignedOtaError('A legacy OTA metadata line was added or removed')
    for (old_key, old_value), (new_key, new_value) in zip(old_lines, new_lines):
        if old_key != new_key or (old_key.decode('ascii') not in old_props and old_value != new_value):
            raise SignedOtaError('A non-property legacy OTA metadata field changed')
    if ota.nonproperty_proto(ota.parse_proto(old_pb)) != ota.nonproperty_proto(ota.parse_proto(new_pb)):
        raise SignedOtaError('A non-property protobuf OTA metadata field changed')
    short_names = {'metadata': ota.METADATA, 'metadata.pb': ota.METADATA_PB}
    contents = {ota.METADATA: new_text, ota.METADATA_PB: new_pb}
    offsets = {name: _stored_data_offset(signed, sfiles[name]) for name in short_names.values()}
    observations = []
    for key, value in new_props.items():
        for token in value.strip().split(','):
            short, advertised_offset, advertised_size = token.split(':')
            name = short_names[short]
            info, content = sfiles[name], contents[name]
            actual_offset, actual_size = offsets[name], len(content)
            if (int(advertised_offset) != actual_offset or int(advertised_size) != actual_size
                    or info.file_size != actual_size or info.compress_size != actual_size):
                raise SignedOtaError(f'Final OTA property offset/size does not match signed ZIP: {name}')
            signed.fp.seek(actual_offset)
            if signed.fp.read(actual_size) != content:
                raise SignedOtaError(f'Final OTA property range does not match member bytes: {name}')
            observations.append({'property': key, 'member': short, 'offset': actual_offset,
                                 'bytes': actual_size, 'direct_range_matches': True})
    return {'property_files': observations, 'legacy_and_protobuf_values_equal': True,
            'nonproperty_fields_unchanged': True}


def _compare_members(reference: zipfile.ZipFile, rfiles: dict, signed: zipfile.ZipFile, sfiles: dict) -> list[dict]:
    if rfiles.keys() != sfiles.keys():
        missing = sorted(rfiles.keys() - sfiles.keys())
        added = sorted(sfiles.keys() - rfiles.keys())
        raise SignedOtaError(f'Regular ZIP member set changed (missing={missing}, added={added})')
    rows = []
    for name in sorted(rfiles.keys() - CHANGED):
        a, b = rfiles[name], sfiles[name]
        if a.file_size != b.file_size:
            raise SignedOtaError(f'Uncompressed member length changed: {name}')
        digest, count = hashlib.sha256(), 0
        with reference.open(a) as left, signed.open(b) as right:
            while True:
                ldata, rdata = left.read(CHUNK), right.read(CHUNK)
                if ldata != rdata:
                    raise SignedOtaError(f'Uncompressed member content changed: {name}')
                if not ldata:
                    break
                digest.update(ldata)
                count += len(ldata)
        if count != a.file_size:
            raise SignedOtaError(f'Incomplete member comparison: {name}')
        rows.append({'name': name, 'bytes': count, 'sha256': digest.hexdigest()})
    return rows


def audit(reference_path: Path, signed_path: Path, certificate: Path, reference_sha256: str,
          signed_sha256: str, public_key_sha256: str) -> dict:
    for label, value in (('reference', reference_sha256), ('signed', signed_sha256), ('public key', public_key_sha256)):
        if not isinstance(value, str) or not HEX_SHA256.fullmatch(value):
            raise SignedOtaError(f'{label} pin must be a lowercase SHA-256 digest')
    # The verifier authenticates the bytes against an independently supplied public key.
    # It intentionally does not infer recovery trust from the ZIP or embedded certificate.
    signature_result = signature.audit(signed_path, certificate, signed_sha256, public_key_sha256)
    reference_file, reference_snapshot = guard._open_regular(reference_path)
    try:
        signed_file, signed_snapshot = guard._open_regular(signed_path)
        try:
            if reference_snapshot[:2] == signed_snapshot[:2]:
                raise SignedOtaError('Reference and signed ZIP must be different files')
            if _hash_open(reference_file, reference_snapshot[2]) != reference_sha256:
                raise SignedOtaError('Reference ZIP SHA-256 does not match the supplied pin')
            # Rehash the held descriptor, binding all subsequent checks to the same bytes
            # verified by the signature auditor even if a path is swapped in between.
            if _hash_open(signed_file, signed_snapshot[2]) != signed_sha256:
                raise SignedOtaError('Signed ZIP SHA-256 does not match the supplied pin')
            guard._check_unchanged(reference_path, reference_file, reference_snapshot)
            guard._check_unchanged(signed_path, signed_file, signed_snapshot)
            with zipfile.ZipFile(guard._BoundedZipReader(reference_file)) as refzip, \
                    zipfile.ZipFile(guard._BoundedZipReader(signed_file)) as signedzip:
                rfiles, sfiles = _index(refzip), _index(signedzip)
                metadata_result = _metadata(refzip, rfiles, signedzip, sfiles)
                embedded = _small(signedzip, sfiles[OTACERT], signature.MAX_CERTIFICATE)
                _, embedded_spki, _, _ = signature._certificate_data(embedded)
                if hashlib.sha256(embedded_spki).hexdigest() != public_key_sha256:
                    raise SignedOtaError('Signed ZIP otacert public key differs from the explicit signer pin')
                compared = _compare_members(refzip, rfiles, signedzip, sfiles)
            guard._check_unchanged(reference_path, reference_file, reference_snapshot)
            guard._check_unchanged(signed_path, signed_file, signed_snapshot)
        finally:
            signed_file.close()
    finally:
        reference_file.close()
    return {
        'status': 'signature_offsets_and_members_match_supplied_references_only_not_flash_approval',
        'reference_zip': {'bytes': reference_snapshot[2], 'sha256': reference_sha256},
        'signed_zip': {'bytes': signed_snapshot[2], 'sha256': signed_sha256},
        'signature': signature_result,
        'embedded_otacert_public_key_matches_explicit_pin': True,
        'ota_metadata': metadata_result,
        'unchanged_uncompressed_members': compared,
        'limitations': [
            'Pins and the public certificate are caller-supplied; their provenance and recovery trust are not established.',
            'This is not the installed recovery verifier or a ZIP64/device interoperability test.',
            'No AVB, rollback, SELinux, VINTF, ABI, encryption, device write or boot check is performed.',
            'Directory records and compressed byte streams may differ; complete preservation beyond the compared uncompressed contents is not claimed.',
            'No private key, signing operation, ROM build, flash or device access is involved.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-zip', type=Path, required=True)
    parser.add_argument('--reference-sha256', required=True)
    parser.add_argument('--signed-zip', type=Path, required=True)
    parser.add_argument('--signed-sha256', required=True)
    parser.add_argument('--certificate', type=Path, required=True, help='independently obtained public certificate only')
    parser.add_argument('--public-key-sha256', required=True, help='independently obtained SHA-256 of DER SubjectPublicKeyInfo')
    args = parser.parse_args()
    try:
        result = audit(args.reference_zip, args.signed_zip, args.certificate, args.reference_sha256,
                       args.signed_sha256, args.public_key_sha256)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (SignedOtaError, signature.RecoverySignatureError, ota.OtaBuildError, guard.AuditError,
            OSError, ValueError, EOFError, zipfile.BadZipFile, NotImplementedError) as exc:
        print(json.dumps({'status': 'rejected_or_outside_audit_scope', 'error': str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
