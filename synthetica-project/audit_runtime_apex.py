#!/usr/bin/env python3
"""Inspect two linker headers inside a temporary copy of the runtime APEX.

This only reads a verified ext4 copy and a single APK/ZIP member. The package
and payload copies are temporary, never mounted or executed; no policy, image,
or device is changed. A package on disk does not prove APEX activation or
signature validity. Unsupported filesystems and unreadable inputs are reported
without guessing their contents.
"""
from __future__ import annotations

import hashlib
import stat
import tempfile
import zipfile
from pathlib import Path

import audit_vintf_candidate as inventory
import audit_vendor_elf_metadata as elf

APEX_PATH = '/system/apex/com.android.runtime.apex'
PAYLOAD_MEMBER = 'apex_payload.img'
MAX_APEX = 128 * 1024**2
MAX_PAYLOAD = 256 * 1024**2
MAX_MEMBERS = 2000
MAX_LINKER = 32 * 1024**2
CHUNK = 1024 * 1024


class ApexAuditError(RuntimeError):
    pass


def copy_tsk_entry(entry, size: int, destination: Path, limit: int) -> str:
    if size <= 0 or size > limit:
        raise ApexAuditError('Selected APEX entry exceeds size limits')
    h, offset = hashlib.sha256(), 0
    with destination.open('xb') as out:
        while offset < size:
            data = entry.read_random(offset, min(CHUNK, size - offset))
            if not data or len(data) > size - offset:
                raise ApexAuditError('Incomplete APEX entry read')
            out.write(data)
            h.update(data)
            offset += len(data)
    destination.chmod(0o400)
    return h.hexdigest()


def extract_payload(apex: Path, destination: Path) -> dict:
    """Copy one bounded, exact ZIP member without interpreting any path."""
    try:
        with zipfile.ZipFile(apex) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                raise ApexAuditError('APEX ZIP has too many members')
            selected = [m for m in members if m.filename == PAYLOAD_MEMBER]
            if len(selected) != 1:
                raise ApexAuditError('APEX payload member missing or duplicated')
            member = selected[0]
            mode = member.external_attr >> 16
            if (member.is_dir() or stat.S_ISLNK(mode) or member.flag_bits & 1 or
                    member.file_size <= 0 or member.file_size > MAX_PAYLOAD):
                raise ApexAuditError('Unsafe or oversized APEX payload member')
            h, written = hashlib.sha256(), 0
            with archive.open(member, 'r') as source, destination.open('xb') as out:
                while data := source.read(CHUNK):
                    written += len(data)
                    if written > member.file_size or written > MAX_PAYLOAD:
                        raise ApexAuditError('APEX payload exceeded declared length')
                    out.write(data)
                    h.update(data)
            if written != member.file_size:
                raise ApexAuditError('APEX payload length mismatch')
            # ZipExtFile validates the ZIP member CRC on a complete read.
            destination.chmod(0o400)
            return {'bytes': written, 'sha256': h.hexdigest(), 'zip_crc_checked_at_eof': True}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError, EOFError) as exc:
        raise ApexAuditError(f'Cannot read bounded runtime APEX payload: {type(exc).__name__}') from exc


def payload_format(payload: Path) -> str:
    with payload.open('rb') as stream:
        stream.seek(1024)
        block = stream.read(64)
    if len(block) >= 58 and block[56:58] == b'\x53\xef':
        return 'ext4'
    if block[:4] == b'\xe2\xe1\xf5\xe0':
        return 'erofs'
    return 'unknown'


def hash_tsk_entry(entry, size: int) -> str:
    if size <= 0 or size > MAX_LINKER:
        raise ApexAuditError('Linker size exceeds limit')
    h, offset = hashlib.sha256(), 0
    while offset < size:
        data = entry.read_random(offset, min(CHUNK, size - offset))
        if not data or len(data) > size - offset:
            raise ApexAuditError('Incomplete linker read')
        h.update(data)
        offset += len(data)
    return h.hexdigest()


def inspect_ext4_payload(payload: Path) -> list[dict]:
    try:
        disk = inventory.pytsk3.Img_Info(str(payload))
        fs = inventory.pytsk3.FS_Info(disk)
    except (OSError, RuntimeError) as exc:
        raise ApexAuditError('Cannot read ext4 runtime APEX payload') from exc
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise ApexAuditError('Unexpected runtime APEX filesystem type')
    rows = []
    for path in ('/bin/linker', '/bin/linker64'):
        try:
            entry = fs.open(path=path)
        except (OSError, RuntimeError):
            rows.append({'path': path, 'status': 'missing_or_unreadable'})
            continue
        meta = entry.info.meta
        if meta is None:
            rows.append({'path': path, 'status': 'missing_or_unreadable'})
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            rows.append({'path': path, 'status': 'symlink_not_followed'})
        elif meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG:
            rows.append({'path': path, 'status': 'not_regular'})
        else:
            size = int(meta.size)
            try:
                parsed = elf.classify_elf(entry, size)
            except elf.ElfMetadataError:
                parsed = None
            rows.append({'path': path, 'status': 'regular', 'bytes': size,
                         'sha256': hash_tsk_entry(entry, size), 'elf': parsed})
    return rows


def inspect_system(image: Path) -> dict:
    if inventory.pytsk3 is None:
        raise ApexAuditError('Missing filesystem reader')
    disk = inventory.pytsk3.Img_Info(str(image))
    fs = inventory.pytsk3.FS_Info(disk)
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise ApexAuditError('Expected ext4 system image')
    try:
        entry = fs.open(path=APEX_PATH)
    except (OSError, RuntimeError):
        return {'path': APEX_PATH, 'status': 'missing_or_unreadable'}
    meta = entry.info.meta
    if meta is None:
        return {'path': APEX_PATH, 'status': 'missing_or_unreadable'}
    if meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG:
        return {'path': APEX_PATH, 'status': 'not_regular_or_symlink'}
    size = int(meta.size)
    with tempfile.TemporaryDirectory(prefix='runtime-apex-audit-', dir=image.parent) as temp:
        root = Path(temp)
        package, payload = root / 'runtime.apex', root / 'payload.img'
        digest = copy_tsk_entry(entry, size, package, MAX_APEX)
        payload_result = extract_payload(package, payload)
        fmt = payload_format(payload)
        result = {'path': APEX_PATH, 'status': 'read', 'bytes': size, 'sha256': digest,
                  'payload': {**payload_result, 'filesystem': fmt},
                  'apex_signature_verified': False,
                  'limitations': [
                      'Package and payload were inspected only as data, in temporary copies; no code was executed.',
                      'ZIP CRC and hashes are not APEX signature verification.',
                      'On-disk contents do not prove runtime APEX activation, 32-bit kernel support or compatibility.',
                  ]}
        if fmt == 'ext4':
            result['payload']['linker_headers'] = inspect_ext4_payload(payload)
        else:
            result['payload']['linker_headers'] = 'not_inspected_unsupported_filesystem'
        return result
