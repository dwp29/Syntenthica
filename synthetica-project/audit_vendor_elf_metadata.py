#!/usr/bin/env python3
"""Bounded static ELF/linker inventory from verified read-only ext4 copies.

No executable is launched, no package is unpacked, and no image is mounted or
changed. This observes vendor/bin ELF headers and a few framework paths only;
it cannot establish Android linker namespace, active APEX, kernel or runtime
compatibility.
"""
from __future__ import annotations

import re
import struct
from collections import Counter
from pathlib import Path

import audit_vintf_candidate as inventory

MAX_DEPTH = 12
MAX_ENTRIES = 40000
MAX_PHNUM = 512
MAX_PROGRAM_HEADER_SIZE = 256
MAX_INTERPRETER_BYTES = 256
VENDOR_BIN = '/bin'
SYSTEM_LINKERS = ('/system/bin/linker', '/system/bin/linker64')
RUNTIME_APEX_DIR = '/system/apex'
KNOWN_INTERPRETERS = {
    '/system/bin/linker', '/system/bin/linker64',
    '/apex/com.android.runtime/bin/linker', '/apex/com.android.runtime/bin/linker64',
}


class ElfMetadataError(RuntimeError):
    pass


def read_exact(entry, offset: int, amount: int, size: int) -> bytes:
    if offset < 0 or amount < 0 or offset + amount > size:
        raise ElfMetadataError('ELF read is outside the file')
    data = entry.read_random(offset, amount)
    if len(data) != amount:
        raise ElfMetadataError('ELF header read is incomplete')
    return data


def classify_elf(entry, size: int) -> dict | None:
    """Read only ELF/program headers and one bounded interpreter string."""
    if size < 4:
        return None
    if read_exact(entry, 0, 4, size) != b'\x7fELF':
        return None
    ident = read_exact(entry, 0, 16, size)
    if ident[4] not in (1, 2) or ident[5] != 1 or ident[6] != 1:
        raise ElfMetadataError('Unsupported ELF class, endian or version')
    elf_class = 32 if ident[4] == 1 else 64
    if elf_class == 32:
        header_size, fmt, phfmt = 52, '<16sHHIIIIIHHHHHH', '<IIIIIIII'
    else:
        header_size, fmt, phfmt = 64, '<16sHHIQQQIHHHHHH', '<IIQQQQQQ'
    header = struct.unpack(fmt, read_exact(entry, 0, header_size, size))
    kind, machine = header[1], header[2]
    phoff, phentsize, phnum = header[5], header[9], header[10]
    min_phsize = struct.calcsize(phfmt)
    if phnum > MAX_PHNUM or (phnum and not min_phsize <= phentsize <= MAX_PROGRAM_HEADER_SIZE):
        raise ElfMetadataError('ELF program header count or size exceeds limits')
    if phnum and (phoff < header_size or phoff + phnum * phentsize > size):
        raise ElfMetadataError('ELF program header table is outside the file')
    interpreters = []
    for index in range(phnum):
        program = struct.unpack(phfmt, read_exact(entry, phoff + index * phentsize, min_phsize, size))
        if program[0] != 3:  # PT_INTERP
            continue
        offset, length = (program[1], program[4]) if elf_class == 32 else (program[2], program[5])
        if length < 2 or length > MAX_INTERPRETER_BYTES:
            raise ElfMetadataError('Invalid ELF interpreter length')
        data = read_exact(entry, offset, length, size)
        if data[-1:] != b'\0' or b'\0' in data[:-1]:
            raise ElfMetadataError('Invalid ELF interpreter terminator')
        try:
            path = data[:-1].decode('ascii', 'strict')
        except UnicodeError as exc:
            raise ElfMetadataError('Non-ASCII ELF interpreter') from exc
        if not path.startswith('/') or any(ord(c) < 33 or ord(c) > 126 for c in path):
            raise ElfMetadataError('Invalid ELF interpreter path')
        interpreters.append(path if path in KNOWN_INTERPRETERS else 'other_absolute_path')
    if len(interpreters) > 1:
        raise ElfMetadataError('Multiple ELF interpreters')
    architecture = {40: 'ARM', 183: 'AArch64', 3: 'x86', 62: 'x86_64'}.get(machine, 'other')
    elf_type = {1: 'relocatable', 2: 'executable', 3: 'dynamic', 4: 'core'}.get(kind, 'other')
    return {'class': elf_class, 'architecture': architecture, 'type': elf_type,
            'interpreter': interpreters[0] if interpreters else None}


def _open_ext4(image: Path):
    if inventory.pytsk3 is None:
        raise ElfMetadataError('Missing read-only filesystem reader')
    disk = inventory.pytsk3.Img_Info(str(image))
    fs = inventory.pytsk3.FS_Info(disk)
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise ElfMetadataError('Expected an ext4 filesystem')
    # Keep Img_Info alive while the returned FS_Info is used.
    return disk, fs


def scan_vendor(image: Path) -> dict:
    disk, fs = _open_ext4(image)  # keep the image handle alive during the scan
    try:
        root = fs.open(path=VENDOR_BIN)
    except (OSError, RuntimeError):
        return {'root': VENDOR_BIN, 'status': 'missing_or_unreadable'}
    meta = root.info.meta
    if meta is None or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_DIR:
        return {'root': VENDOR_BIN, 'status': 'not_directory_or_symlink'}
    stack, visited = [(int(meta.addr), 0)], set()
    entry_count = regular = symlinks = not_elf = malformed = 0
    categories: Counter[tuple] = Counter()
    while stack:
        inode, depth = stack.pop()
        if inode in visited or depth > MAX_DEPTH:
            raise ElfMetadataError('Vendor bin directory cycle or depth limit')
        visited.add(inode)
        for entry in fs.open_dir(inode=inode):
            info, item = entry.info.name, entry.info.meta
            if info is None or not info.name or not (info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
                continue
            if bytes(info.name) in (b'.', b'..'):
                continue
            entry_count += 1
            if entry_count > MAX_ENTRIES:
                raise ElfMetadataError('Vendor bin entry limit exceeded')
            if item is None:
                continue
            if item.type == inventory.pytsk3.TSK_FS_META_TYPE_DIR:
                stack.append((int(item.addr), depth + 1))
            elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
                symlinks += 1
            elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_REG:
                regular += 1
                try:
                    data = classify_elf(entry, int(item.size))
                except ElfMetadataError:
                    malformed += 1
                    continue
                if data is None:
                    not_elf += 1
                else:
                    categories[(data['class'], data['architecture'], data['type'], data['interpreter'])] += 1
    results = [{'class': c, 'architecture': a, 'type': t, 'interpreter': interp, 'count': n}
               for (c, a, t, interp), n in sorted(categories.items(),
                   key=lambda pair: (pair[0][0], pair[0][1], pair[0][2], pair[0][3] or ''))]
    return {'root': VENDOR_BIN, 'status': 'read', 'directory_count': len(visited),
            'entries': entry_count, 'regular_files': regular, 'symlinks_not_followed': symlinks,
            'non_elf_files': not_elf, 'malformed_or_unsupported_elf': malformed, 'elf_categories': results}


def scan_system(image: Path) -> dict:
    disk, fs = _open_ext4(image)  # keep the image handle alive during the scan
    paths = []
    for path in SYSTEM_LINKERS:
        row = {'path': path}
        try:
            entry = fs.open(path=path)
        except (OSError, RuntimeError):
            paths.append({**row, 'status': 'missing_or_unreadable'})
            continue
        meta = entry.info.meta
        if meta is None:
            paths.append({**row, 'status': 'missing_or_unreadable'})
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            raw = meta.link or b''
            if isinstance(raw, str):
                raw = raw.encode('utf-8', 'replace')
            target = raw.decode('utf-8', 'replace')
            paths.append({**row, 'status': 'symlink_not_followed',
                          'target': target if target in KNOWN_INTERPRETERS else 'other_or_unreadable'})
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_REG:
            try:
                elf = classify_elf(entry, int(meta.size))
                paths.append({**row, 'status': 'regular', 'bytes': int(meta.size), 'elf': elf})
            except ElfMetadataError:
                paths.append({**row, 'status': 'regular_unparsed', 'bytes': int(meta.size)})
        else:
            paths.append({**row, 'status': 'not_regular'})
    packages = {'path': RUNTIME_APEX_DIR}
    try:
        directory = fs.open(path=RUNTIME_APEX_DIR)
    except (OSError, RuntimeError):
        packages['status'] = 'missing_or_unreadable'
        return {'system_linker_paths': paths, 'runtime_apex_candidates': packages}
    meta = directory.info.meta
    if meta is None or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_DIR:
        packages['status'] = 'not_directory_or_symlink'
        return {'system_linker_paths': paths, 'runtime_apex_candidates': packages}
    found, count = [], 0
    for entry in fs.open_dir(inode=int(meta.addr)):
        info, item = entry.info.name, entry.info.meta
        if info is None or not info.name or not (info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
            continue
        raw = bytes(info.name)
        if raw in (b'.', b'..'):
            continue
        count += 1
        if count > MAX_ENTRIES:
            raise ElfMetadataError('APEX directory entry limit exceeded')
        if not re.fullmatch(rb'com\.android\.runtime(?:\.[a-zA-Z0-9_-]+)*\.(?:apex|capex)', raw):
            continue
        if item is None:
            kind, size = 'unknown', None
        elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_REG:
            kind, size = 'regular', int(item.size)
        elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            kind, size = 'symlink_not_followed', None
        else:
            kind, size = 'not_regular', None
        found.append({'name': raw.decode('ascii'), 'type': kind, 'bytes': size})
    packages.update({'status': 'read', 'candidates': sorted(found, key=lambda x: x['name'])})
    return {'system_linker_paths': paths, 'runtime_apex_candidates': packages,
            'limitations': [
                'Only vendor/bin regular files were inspected; symlinks and other directories were not followed.',
                'This header/path inventory does not execute code or unpack APEX packages.',
                'An APEX package on disk does not prove activation, linker availability, namespaces, ABI or runtime compatibility.',
                'Kernel 32-bit support, libraries, services, SELinux, AVB and actual device boot were not tested.',
            ]}
