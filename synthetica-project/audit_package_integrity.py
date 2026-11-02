#!/usr/bin/env python3
"""Repeat a bounded read-only package, AVB-footer and OTA metadata check.

This only verifies pinned ZIP member bytes/CRC and records footer/metadata
observations. It does not verify a signing authority or device AVB/vbmeta,
rollback indexes, recovery behavior, encryption, or boot.
"""
from __future__ import annotations

import hashlib
import re
import struct
import zipfile
from pathlib import Path, PurePosixPath

import audit_boot_first_installer as installer

EXPECTED_IMAGES = {
    'boot.img': {'bytes': 134217728, 'sha256': '57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d'},
    'dtbo.img': {'bytes': 25165824, 'sha256': '9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2'},
}
CHUNK = 1024 * 1024
MAX_VBMETA = 100


class IntegrityAuditError(RuntimeError):
    pass


def footer_observation(tail: bytes, image_size: int) -> dict:
    if len(tail) < 64 or tail[-64:-60] != b'AVBf':
        return {'status': 'canonical_avb_footer_not_seen'}
    _, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack('>4sIIQQQ28s', tail[-64:])
    bounded = (image_size >= 64 and original_size <= image_size and
               vbmeta_offset <= image_size - 64 and vbmeta_size <= image_size - 64 - vbmeta_offset)
    return {'status': 'footer_present' if bounded else 'footer_present_invalid_bounds',
            'version': f'{major}.{minor}', 'bounds_valid': bounded,
            'original_image_bytes': original_size, 'vbmeta_offset': vbmeta_offset, 'vbmeta_bytes': vbmeta_size}


def stream_image(archive: zipfile.ZipFile, name: str, expected: dict) -> dict:
    info = archive.getinfo(name)
    if info.is_dir() or info.flag_bits & 1 or info.file_size != expected['bytes']:
        raise IntegrityAuditError('Image entry has unexpected type or size')
    digest, total, tail = hashlib.sha256(), 0, b''
    with archive.open(info) as stream:
        while data := stream.read(CHUNK):
            total += len(data)
            if total > expected['bytes']:
                raise IntegrityAuditError('Image entry exceeded expected size')
            digest.update(data)
            tail = (tail + data)[-64:]
    if total != expected['bytes'] or digest.hexdigest() != expected['sha256']:
        raise IntegrityAuditError('Pinned image identity mismatch')
    return {'bytes': total, 'sha256': digest.hexdigest(), 'zip_crc_checked_at_eof': True,
            'avb_footer': footer_observation(tail, total)}


def inspect(candidate: Path, expected_images: dict | None = None) -> dict:
    expected_images = EXPECTED_IMAGES if expected_images is None else expected_images
    info, small = installer.archive_info(candidate)
    metadata = small[installer.METADATA].decode('utf-8', 'strict')
    offsets = installer.metadata_offsets(metadata, info['entries'])
    names = [row['name'] for row in info['entries']]
    vbmeta = [name for name in names if re.fullmatch(r'vbmeta(?:_[A-Za-z0-9_.-]+)?\.img', PurePosixPath(name).name)]
    if len(vbmeta) > MAX_VBMETA:
        raise IntegrityAuditError('Unexpected vbmeta entry count')
    with zipfile.ZipFile(candidate, 'r', allowZip64=True) as archive:
        images = {name: stream_image(archive, name, expected) for name, expected in expected_images.items()}
        comment_bytes = len(archive.comment)
    return {'archive_entry_count': info['entry_count'], 'zip_comment_bytes': comment_bytes,
            'whole_file_android_ota_signature_footer': ('not_present_empty_zip_comment' if not comment_bytes
                                                         else 'not_verified_nonempty_zip_comment'),
            'vbmeta_image_entries': sorted(vbmeta), 'boot_and_dtbo': images,
            'ota_metadata_offsets': [{'name': x['name'], 'offset_matches': x['offset_matches']} for x in offsets],
            'ota_metadata_offsets_status': ('read' if offsets else 'missing_or_empty'),
            'limitations': [
                'ZIP CRC and SHA-256 identify bytes but do not prove the signer, recovery acceptance or device compatibility.',
                'A missing image footer or vbmeta ZIP entry does not rule out a separate device vbmeta chain.',
                'No device rollback index, hardware partition size, AVB enforcement, recovery, encryption or boot was measured.',
                'No image, archive, security setting or device was modified.',
            ]}
