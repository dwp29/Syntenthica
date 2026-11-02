#!/usr/bin/env python3
"""Read-only inventory of VNDK declarations and on-disk candidates.

This inspects only fixed paths in verified temporary ext4 extents. It does not
install an APEX, alter a manifest, follow final-component symlinks, verify a
signer, establish linker namespace/ABI compatibility, or prove device boot.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import audit_vintf_candidate as inventory

APEX_DIR = {'system': '/system/apex', 'system_ext': '/apex', 'product': '/apex', 'vendor': '/apex'}
LINK_PATHS = {
    'system': ('/system/lib/vndk-30', '/system/lib/vndk-sp-30',
               '/system/lib64/vndk-30', '/system/lib64/vndk-sp-30'),
    'system_ext': ('/lib/vndk-30', '/lib/vndk-sp-30', '/lib64/vndk-30', '/lib64/vndk-sp-30'),
    'vendor': ('/lib/vndk-30', '/lib/vndk-sp-30', '/lib64/vndk-30', '/lib64/vndk-sp-30'),
    'product': (),
}
PROP_PATHS = {
    'system': ('/system/build.prop',), 'system_ext': ('/etc/build.prop',),
    'product': ('/etc/build.prop',), 'vendor': ('/default.prop', '/build.prop', '/etc/build.prop'),
}
PROP_KEYS = frozenset(('ro.vndk.version', 'ro.product.vndk.version',
                       'ro.vendor.build.version.sdk', 'ro.product.first_api_level'))
MAX_APEX = 256 * 1024 * 1024
MAX_PROP = 1024 * 1024
MAX_ENTRIES = 5000
MAX_XML = 2 * 1024 * 1024
APEX_PATTERN = re.compile(rb'com\.android\.vndk\.v([0-9]{1,3})\.(apex|capex)\Z')
LIBRARY = re.compile(r'[A-Za-z0-9_+@.-]{1,200}\.so\Z')


class VndkAuditError(RuntimeError):
    pass


def _open(fs, path):
    try:
        return fs.open(path=path)
    except (OSError, RuntimeError):
        return None


def _type(entry):
    if entry is None or entry.info.meta is None:
        return 'missing_or_unreadable'
    meta = entry.info.meta
    tsk = inventory.pytsk3
    if not meta.flags & tsk.TSK_FS_META_FLAG_ALLOC:
        return 'unallocated'
    return {tsk.TSK_FS_META_TYPE_REG: 'regular', tsk.TSK_FS_META_TYPE_DIR: 'directory',
            tsk.TSK_FS_META_TYPE_LNK: 'symlink_not_followed'}.get(meta.type, 'other')


def _read_bounded(entry, limit):
    size = int(entry.info.meta.size)
    if size < 0 or size > limit:
        raise VndkAuditError('Selected file exceeds its bounded read limit')
    data = bytearray()
    while len(data) < size:
        block = entry.read_random(len(data), min(1024 * 1024, size - len(data)))
        if not block or len(block) > size - len(data):
            raise VndkAuditError('Short filesystem read')
        data.extend(block)
    return bytes(data)


def _hash_bounded(entry, limit):
    size = int(entry.info.meta.size)
    if size < 0 or size > limit:
        raise VndkAuditError('Selected file exceeds its bounded hash limit')
    h = hashlib.sha256()
    offset = 0
    while offset < size:
        block = entry.read_random(offset, min(1024 * 1024, size - offset))
        if not block or len(block) > size - offset:
            raise VndkAuditError('Short filesystem hash read')
        h.update(block)
        offset += len(block)
    return h.hexdigest()


def parse_properties(data: bytes) -> dict:
    """Only bounded numeric version fields, never a raw build.prop."""
    if len(data) > MAX_PROP:
        raise VndkAuditError('Property file exceeds bound')
    values = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith(b'#') or b'=' not in line:
            continue
        key, value = line.split(b'=', 1)
        try:
            key = key.decode('ascii', 'strict')
        except UnicodeDecodeError:
            continue
        if key not in PROP_KEYS:
            continue
        if key in values:
            raise VndkAuditError('Duplicate selected property')
        value = value.strip()
        if not re.fullmatch(rb'[A-Za-z0-9_.-]{1,64}', value):
            raise VndkAuditError('Unexpected selected property value')
        values[key] = value.decode('ascii')
    return values


def parse_vndk_xml(data: bytes, expected_root: str, expected_type: str) -> dict:
    if (not data or len(data) > MAX_XML or b'<!DOCTYPE' in data.upper()
            or b'<!ENTITY' in data.upper()):
        raise VndkAuditError('Unsafe or oversized VINTF document')
    root = ET.fromstring(data)
    if root.tag != expected_root or root.get('type') != expected_type:
        raise VndkAuditError('Unexpected VINTF root/type')
    result = []
    for item in root.findall('./vendor-ndk'):
        versions = [(e.text or '').strip() for e in item.findall('./version')]
        libraries = [(e.text or '').strip() for e in item.findall('./library')]
        if (len(versions) != 1 or not re.fullmatch(r'[0-9]{1,3}', versions[0])
                or len(libraries) > 5000 or len(libraries) != len(set(libraries))
                or any(not LIBRARY.fullmatch(n) for n in libraries)):
            raise VndkAuditError('Unexpected VNDK version or library declaration')
        result.append({'version': versions[0], 'library_count': len(libraries),
                       'libraries_sha256': hashlib.sha256('\n'.join(sorted(libraries)).encode()).hexdigest(),
                       'library_examples': sorted(libraries)[:20]})
    return {'root': expected_root, 'type': expected_type, 'vendor_ndk': result,
            'xml_sha256': hashlib.sha256(data).hexdigest()}


def scan_fs(fs, partition: str) -> dict:
    if partition not in APEX_DIR:
        raise VndkAuditError('Unexpected partition')
    tsk = inventory.pytsk3
    apex_path = APEX_DIR[partition]
    root = _open(fs, apex_path)
    apex = {'path': apex_path, 'status': _type(root), 'packages': []}
    if apex['status'] == 'directory':
        count = 0
        for entry in fs.open_dir(inode=int(root.info.meta.addr)):
            name, meta = entry.info.name, entry.info.meta
            if name is None or not name.name or not name.flags & tsk.TSK_FS_NAME_FLAG_ALLOC:
                continue
            raw = bytes(name.name)
            if raw in (b'.', b'..'):
                continue
            count += 1
            if count > MAX_ENTRIES:
                raise VndkAuditError('APEX directory exceeds entry limit')
            match = APEX_PATTERN.fullmatch(raw)
            if match is None:
                continue
            status = _type(entry)
            row = {'name': raw.decode('ascii'), 'version': match.group(1).decode('ascii'),
                   'format': match.group(2).decode('ascii'), 'status': status}
            if status == 'regular':
                size = int(meta.size)
                if size > MAX_APEX:
                    raise VndkAuditError('Selected VNDK APEX exceeds bound')
                row.update({'bytes': size, 'sha256': _hash_bounded(entry, MAX_APEX)})
            apex['packages'].append(row)
        apex['packages'].sort(key=lambda x: x['name'])
        apex['directory_entries'] = count
    links = []
    for path in LINK_PATHS[partition]:
        entry = _open(fs, path)
        status = _type(entry)
        row = {'path': path, 'status': status}
        if status == 'symlink_not_followed':
            raw = entry.info.meta.link or b''
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', 'replace')
            # Report only the narrowly expected VNDK targets, not arbitrary paths.
            row['target'] = raw if re.fullmatch(r'/apex/com\.android\.vndk\.v30/(?:lib|lib64)', raw) else 'other_or_unreadable'
        links.append(row)
    properties = []
    for path in PROP_PATHS[partition]:
        entry = _open(fs, path)
        status = _type(entry)
        row = {'path': path, 'status': status}
        if status == 'regular':
            data = _read_bounded(entry, MAX_PROP)
            row.update({'sha256': hashlib.sha256(data).hexdigest(), 'selected': parse_properties(data)})
        properties.append(row)
    return {'partition': partition, 'apex_directory': apex, 'vndk30_links': links,
            'selected_properties': properties,
            'limitations': ['On-disk names or symlinks do not establish APEX activation, signer trust, ABI or boot.']}


def snapshot_declarations(snapshot: Path, seen: dict) -> list[dict]:
    # These are the exact XML documents already compared with the previous
    # independent inventory. A missing or changed file fails closed.
    sources = (
        ('system', '/system/etc/vintf/manifest.xml', 'manifest', 'framework'),
        ('system_ext', '/system_ext/etc/vintf/manifest.xml', 'manifest', 'framework'),
        ('vendor', '/vendor/etc/vintf/compatibility_matrix.xml', 'compatibility-matrix', 'device'),
    )
    result = []
    for partition, guest, root, kind in sources:
        expected = seen.get(guest)
        path = snapshot / guest.lstrip('/')
        if not expected or path.is_symlink() or not path.is_file():
            raise VndkAuditError('Expected VINTF declaration not present in verified snapshot')
        data = path.read_bytes()
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise VndkAuditError('VINTF declaration differs from verified snapshot')
        result.append({'partition': partition, 'path': guest, **parse_vndk_xml(data, root, kind)})
    return result


def scan_partition(image: Path, partition: str) -> dict:
    if inventory.pytsk3 is None:
        raise VndkAuditError('Read-only ext4 reader is unavailable')
    disk = inventory.pytsk3.Img_Info(str(image))
    fs = inventory.pytsk3.FS_Info(disk)
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise VndkAuditError('Expected a verified ext4 extent')
    return scan_fs(fs, partition)
