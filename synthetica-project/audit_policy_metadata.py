#!/usr/bin/env python3
"""Inventory selected split-SEPolicy file metadata, never its policy contents.

Only verified ext4 copies are read through pytsk3, with no filesystem mount.
This is independent of the previous init-detail JSON and does not reproduce or
transfer it. Names, sizes, SHA-256, a bounded numeric version, and comparisons
of small digest files are the only output. Runtime paths, ODM overrides and
policy compilation on the phone are not established.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import audit_vintf_candidate as inventory

MAX_FILE_BYTES = 64 * 1024**2
MAX_MAP_ENTRIES = 1000
MAX_TEXT_BYTES = 512
CHUNK = 1024 * 1024

FILES = {
    'system': (
        '/system/etc/selinux/plat_sepolicy.cil',
        '/system/etc/selinux/plat_sepolicy_and_mapping.sha256',
        '/system/bin/secilc',
    ),
    'system_ext': (
        '/etc/selinux/system_ext_sepolicy.cil',
        '/etc/selinux/system_ext_sepolicy_and_mapping.sha256',
    ),
    'product': (
        '/etc/selinux/product_sepolicy.cil',
        '/etc/selinux/product_sepolicy_and_mapping.sha256',
    ),
    'vendor': (
        '/etc/selinux/plat_sepolicy_vers.txt',
        '/etc/selinux/vendor_sepolicy.cil',
        '/etc/selinux/plat_pub_versioned.cil',
        '/etc/selinux/precompiled_sepolicy',
        '/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256',
        '/etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256',
        '/etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256',
        '/odm/etc/selinux/precompiled_sepolicy',
    ),
}
MAPPING_DIRS = {
    'system': '/system/etc/selinux/mapping',
    'system_ext': '/etc/selinux/mapping',
    'product': '/etc/selinux/mapping',
}
TEXT_FILES = {
    ('vendor', '/etc/selinux/plat_sepolicy_vers.txt'): 'vendor_mapping_version',
    ('system', '/system/etc/selinux/plat_sepolicy_and_mapping.sha256'): 'system',
    ('system_ext', '/etc/selinux/system_ext_sepolicy_and_mapping.sha256'): 'system_ext',
    ('product', '/etc/selinux/product_sepolicy_and_mapping.sha256'): 'product',
    ('vendor', '/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256'): 'vendor_system',
    ('vendor', '/etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256'): 'vendor_system_ext',
    ('vendor', '/etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256'): 'vendor_product',
}


class PolicyMetadataError(RuntimeError):
    pass


def _read_and_hash(entry, size: int, keep_text: bool) -> tuple[str, bytes | None]:
    if size < 0 or size > MAX_FILE_BYTES or (keep_text and size > MAX_TEXT_BYTES):
        raise PolicyMetadataError('Selected policy file exceeds its bounded size')
    h, collected, offset = hashlib.sha256(), bytearray(), 0
    while offset < size:
        block = entry.read_random(offset, min(CHUNK, size - offset))
        if not block or len(block) > size - offset:
            raise PolicyMetadataError('Cannot read a complete selected policy file')
        h.update(block)
        if keep_text:
            collected.extend(block)
        offset += len(block)
    return h.hexdigest(), bytes(collected) if keep_text else None


def scan(image: Path, partition: str, rows: list[dict], mappings: list[dict],
         private_text: dict) -> None:
    """Gather metadata for a single filesystem while its verified copy exists."""
    if partition not in FILES or inventory.pytsk3 is None:
        raise PolicyMetadataError('Unsupported partition or missing filesystem reader')
    disk = inventory.pytsk3.Img_Info(str(image))
    fs = inventory.pytsk3.FS_Info(disk)
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise PolicyMetadataError('Expected an ext4 filesystem')
    for path in FILES[partition]:
        row = {'partition': partition, 'path': path}
        try:
            entry = fs.open(path=path)
        except (OSError, RuntimeError):
            rows.append({**row, 'status': 'missing_or_unreadable'})
            continue
        meta = entry.info.meta
        if meta is None or not (meta.flags & inventory.pytsk3.TSK_FS_META_FLAG_ALLOC):
            rows.append({**row, 'status': 'missing_or_unreadable'})
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            rows.append({**row, 'status': 'symlink_not_followed'})
        elif meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG:
            rows.append({**row, 'status': 'not_regular'})
        elif int(meta.size) > MAX_FILE_BYTES:
            rows.append({**row, 'status': 'too_large_not_read', 'bytes': int(meta.size)})
        else:
            text_key = TEXT_FILES.get((partition, path))
            if text_key and int(meta.size) > MAX_TEXT_BYTES:
                rows.append({**row, 'status': 'text_too_large_not_read', 'bytes': int(meta.size)})
                continue
            digest, text = _read_and_hash(entry, int(meta.size), text_key is not None)
            rows.append({**row, 'status': 'read', 'bytes': int(meta.size), 'sha256': digest})
            if text_key is not None:
                try:
                    first = text.decode('ascii', 'strict').splitlines()[0]
                except (UnicodeError, IndexError):
                    first = ''
                # Keep only internally, for comparison; never put this content
                # in the report or in logs. The mapping version is separately
                # validated as a bounded numeric value before being exposed.
                private_text[text_key] = first
    if partition not in MAPPING_DIRS:
        return
    directory_path = MAPPING_DIRS[partition]
    try:
        directory_file = fs.open(path=directory_path)
    except (OSError, RuntimeError):
        mappings.append({'partition': partition, 'path': directory_path, 'status': 'missing_or_unreadable'})
        return
    meta = directory_file.info.meta
    if meta is None or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_DIR:
        mappings.append({'partition': partition, 'path': directory_path, 'status': 'not_directory_or_symlink'})
        return
    versions = []
    entries = 0
    for entry in fs.open_dir(inode=int(meta.addr)):
        info, item = entry.info.name, entry.info.meta
        if info is None or not info.name or not (info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
            continue
        name = bytes(info.name)
        if name in (b'.', b'..'):
            continue
        entries += 1
        if entries > MAX_MAP_ENTRIES:
            raise PolicyMetadataError('Too many entries in mapping directory')
        if not re.fullmatch(rb'\d+(?:\.\d+)?(?:\.compat)?\.cil', name):
            continue
        if item is None:
            kind = 'unknown'
        elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_REG:
            kind = 'regular'
        elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            kind = 'symlink_not_followed'
        else:
            kind = 'not_regular'
        versions.append({'name': name.decode('ascii'), 'type': kind})
    mappings.append({'partition': partition, 'path': directory_path, 'status': 'read',
                     'numeric_mapping_files': sorted(versions, key=lambda x: x['name'])})


def summarize(rows: list[dict], mappings: list[dict], private_text: dict) -> dict:
    """Report facts and pairwise hash-file equality, not policy validity."""
    version = private_text.get('vendor_mapping_version')
    if version is not None and not re.fullmatch(r'\d+(?:\.\d+)?', version):
        version = None
    comparisons = {}
    for part in ('system', 'system_ext', 'product'):
        actual, expected = private_text.get(part), private_text.get('vendor_' + part)
        valid_actual = bool(actual and re.fullmatch(r'[0-9a-fA-F]{64}', actual))
        valid_expected = bool(expected and re.fullmatch(r'[0-9a-fA-F]{64}', expected))
        if valid_actual and valid_expected:
            comparisons[part] = 'both_read_equal' if actual == expected else 'both_read_different'
        else:
            comparisons[part] = 'not_comparable_missing_unreadable_or_invalid'
    return {'scope': 'selected static file metadata only; policy contents are never included',
            'vendor_mapping_version': version,
            'policy_files': rows, 'mapping_directories': mappings,
            'precompiled_digest_file_comparisons': comparisons,
            'limitations': [
                'Missing or unreadable is not proof of absence at runtime; final symlinks are not followed.',
                'ODM and mounted runtime paths may differ; equal hash-file text does not prove a policy loads.',
                'No SELinux policy was compiled, executed, modified, disabled, or validated on a device.',
            ]}
