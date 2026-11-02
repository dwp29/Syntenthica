#!/usr/bin/env python3
"""Bounded DT_NEEDED observations for vendor executables and selected lib roots.

Files are data only, read from verified ext4 copies via pytsk3. This is not a
linker, ELF symbol/version check, or a complete search across APEX, ODM, vendor
subdirectories and Android namespaces. A missing name in these roots is not a
claim that the dependency is absent at runtime.
"""
from __future__ import annotations

import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

import audit_vendor_elf_metadata as elf
import audit_vintf_candidate as inventory

MAX_DYNAMIC = 4 * 1024**2
MAX_STRTAB = 8 * 1024**2
MAX_NEEDED = 512
MAX_LIB_ENTRIES = 50000
MAX_EXAMPLES = 25
LIBNAME = re.compile(r'[A-Za-z0-9_+@.-]{1,200}\.so(?:\.[0-9]+)*\Z')
LIB_ROOTS = {
    'system': {32: '/system/lib', 64: '/system/lib64'},
    'system_ext': {32: '/lib', 64: '/lib64'},
    'product': {32: '/lib', 64: '/lib64'},
    'vendor': {32: '/lib', 64: '/lib64'},
}


class AbiAuditError(RuntimeError):
    pass


def dynamic_needed(entry, size: int) -> tuple[list[str], int]:
    """Parse DT_NEEDED via bounded program headers, not section headers."""
    ident = elf.read_exact(entry, 0, 16, size)
    if ident[:4] != b'\x7fELF' or ident[4] not in (1, 2) or ident[5] != 1 or ident[6] != 1:
        raise AbiAuditError('Unsupported ELF header')
    bits = 32 if ident[4] == 1 else 64
    if bits == 32:
        hsize, hfmt, pfmt, dfmt = 52, '<16sHHIIIIIHHHHHH', '<IIIIIIII', '<iI'
    else:
        hsize, hfmt, pfmt, dfmt = 64, '<16sHHIQQQIHHHHHH', '<IIQQQQQQ', '<qQ'
    header = struct.unpack(hfmt, elf.read_exact(entry, 0, hsize, size))
    phoff, phentsize, phnum = header[5], header[9], header[10]
    phsize = struct.calcsize(pfmt)
    if (not phnum or phnum > elf.MAX_PHNUM or not phsize <= phentsize <= elf.MAX_PROGRAM_HEADER_SIZE or
            phoff < hsize or phoff + phentsize * phnum > size):
        raise AbiAuditError('Invalid ELF program header table')
    loads, dynamics = [], []
    for idx in range(phnum):
        p = struct.unpack(pfmt, elf.read_exact(entry, phoff + idx * phentsize, phsize, size))
        typ = p[0]
        off, va, filesz = (p[1], p[2], p[4]) if bits == 32 else (p[2], p[3], p[5])
        if off + filesz > size:
            raise AbiAuditError('ELF segment extends beyond file')
        if typ == 1:  # PT_LOAD, map dynamic string-table addresses to file offsets.
            loads.append((va, off, filesz))
        elif typ == 2:  # PT_DYNAMIC
            dynamics.append((off, filesz))
    if not dynamics:
        return [], 0
    if len(dynamics) != 1:
        raise AbiAuditError('Multiple dynamic segments')
    off, length = dynamics[0]
    entsize = struct.calcsize(dfmt)
    if not 0 < length <= MAX_DYNAMIC or length % entsize:
        raise AbiAuditError('Invalid or oversized dynamic segment')
    raw = elf.read_exact(entry, off, length, size)
    needed, strtab, strsz, terminated = [], None, None, False
    for pos in range(0, len(raw), entsize):
        tag, value = struct.unpack_from(dfmt, raw, pos)
        if tag == 0:
            terminated = True
            break
        if tag == 1:
            needed.append(value)
            if len(needed) > MAX_NEEDED:
                raise AbiAuditError('Too many DT_NEEDED entries')
        elif tag == 5:
            if strtab is not None:
                raise AbiAuditError('Duplicate DT_STRTAB')
            strtab = value
        elif tag == 10:
            if strsz is not None:
                raise AbiAuditError('Duplicate DT_STRSZ')
            strsz = value
    if not terminated:
        raise AbiAuditError('Unterminated dynamic segment')
    if not needed:
        return [], 0
    if strtab is None or strsz is None or not 0 < strsz <= MAX_STRTAB:
        raise AbiAuditError('Missing or oversized dynamic string table')
    candidates = [file_off + (strtab - va) for va, file_off, count in loads
                  if va <= strtab and strtab - va <= count and strsz <= count - (strtab - va)]
    if len(candidates) != 1:
        raise AbiAuditError('String table cannot be mapped uniquely to a load segment')
    strings = elf.read_exact(entry, candidates[0], strsz, size)
    names, invalid = [], 0
    for idx in needed:
        if idx >= len(strings):
            raise AbiAuditError('DT_NEEDED string offset out of range')
        end = strings.find(b'\0', idx, min(len(strings), idx + 256))
        if end < 0:
            raise AbiAuditError('DT_NEEDED string is not bounded')
        try:
            name = strings[idx:end].decode('ascii', 'strict')
        except UnicodeError:
            invalid += 1
            continue
        if not LIBNAME.fullmatch(name):
            invalid += 1
            continue
        names.append(name)
    return sorted(set(names)), invalid


def header_arch(entry, size: int) -> tuple[int, int, int] | None:
    if size < 20:
        return None
    try:
        head = elf.read_exact(entry, 0, 20, size)
    except elf.ElfMetadataError:
        return None
    if head[:4] != b'\x7fELF' or head[4] not in (1, 2) or head[5] != 1 or head[6] != 1:
        return None
    return (32 if head[4] == 1 else 64, struct.unpack_from('<H', head, 18)[0],
            struct.unpack_from('<H', head, 16)[0])


class Collector:
    def __init__(self):
        self.references = Counter()
        self.stats = Counter()
        self.providers = defaultdict(lambda: defaultdict(set))
        self.roots = []

    def capture_vendor_file(self, entry, size: int, parsed: dict) -> None:
        bits, arch, interpreter = parsed['class'], parsed['architecture'], parsed['interpreter']
        if ((bits, arch) not in ((32, 'ARM'), (64, 'AArch64')) or
                parsed['type'] not in ('dynamic', 'executable') or interpreter not in elf.KNOWN_INTERPRETERS):
            return
        self.stats['eligible_vendor_executables'] += 1
        try:
            names, invalid = dynamic_needed(entry, size)
        except (AbiAuditError, elf.ElfMetadataError, struct.error, OSError, RuntimeError):
            self.stats['dynamic_parse_errors'] += 1
            return
        self.stats['parsed_vendor_executables'] += 1
        self.stats['nonstandard_needed_names_not_reported'] += invalid
        if not names:
            self.stats['executables_without_reportable_needed_names'] += 1
        for name in names:
            self.references[(bits, name)] += 1

    def scan_library_roots(self, image: Path, partition: str) -> None:
        if partition not in LIB_ROOTS:
            raise AbiAuditError('Unexpected partition')
        disk, fs = elf._open_ext4(image)  # retain the image handle for this scan
        for bits, path in LIB_ROOTS[partition].items():
            try:
                root = fs.open(path=path)
            except (OSError, RuntimeError):
                self.roots.append({'partition': partition, 'path': path, 'bits': bits,
                                   'status': 'missing_or_unreadable'})
                continue
            meta = root.info.meta
            if meta is None or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_DIR:
                self.roots.append({'partition': partition, 'path': path, 'bits': bits,
                                   'status': 'not_directory_or_symlink'})
                continue
            row = {'partition': partition, 'path': path, 'bits': bits, 'status': 'read',
                   'entries': 0, 'valid_library_names': 0}
            for entry in fs.open_dir(inode=int(meta.addr)):
                name_info, item = entry.info.name, entry.info.meta
                if name_info is None or not name_info.name or not (name_info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
                    continue
                raw = bytes(name_info.name)
                if raw in (b'.', b'..'):
                    continue
                row['entries'] += 1
                if row['entries'] > MAX_LIB_ENTRIES:
                    raise AbiAuditError('Library root exceeds entry limit')
                try:
                    name = raw.decode('ascii', 'strict')
                except UnicodeError:
                    continue
                if not LIBNAME.fullmatch(name):
                    continue
                row['valid_library_names'] += 1
                if item is None:
                    kind = 'other_or_unreadable'
                elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
                    kind = 'symlink_not_followed'
                elif item.type == inventory.pytsk3.TSK_FS_META_TYPE_REG:
                    expected = (bits, 40 if bits == 32 else 183, 3)  # ET_DYN, not merely an ARM ELF
                    kind = 'matching_elf_header' if header_arch(entry, int(item.size)) == expected else 'other_or_unreadable'
                else:
                    kind = 'other_or_unreadable'
                self.providers[(bits, name)][kind].add(partition)
            self.roots.append(row)

    def summarize(self) -> dict:
        categories = defaultdict(list)
        for (bits, name), references in self.references.items():
            providers = self.providers[(bits, name)]
            if providers.get('matching_elf_header'):
                category = 'matching_name_and_basic_elf_header_seen'
            elif providers.get('symlink_not_followed'):
                category = 'only_symlink_name_seen_unresolved'
            elif providers.get('other_or_unreadable'):
                category = 'only_nonmatching_or_unreadable_entry_seen'
            else:
                category = 'not_seen_in_selected_library_roots'
            categories[category].append({'bits': bits, 'name': name, 'referenced_by': references,
                                         'partitions': sorted(set().union(*providers.values())) if providers else []})
        output = {}
        for category in ('matching_name_and_basic_elf_header_seen', 'only_symlink_name_seen_unresolved',
                         'only_nonmatching_or_unreadable_entry_seen', 'not_seen_in_selected_library_roots'):
            rows = sorted(categories[category], key=lambda r: (-r['referenced_by'], r['bits'], r['name']))
            output[category] = {'unique_bitness_name_pairs': len(rows),
                                'executable_dependency_edges': sum(r['referenced_by'] for r in rows),
                                'examples': rows[:MAX_EXAMPLES], 'examples_truncated': len(rows) > MAX_EXAMPLES}
        counts = {key: self.stats[key] for key in ('eligible_vendor_executables', 'parsed_vendor_executables',
                  'dynamic_parse_errors', 'nonstandard_needed_names_not_reported',
                  'executables_without_reportable_needed_names')}
        return {'vendor_dynamic_executable_counts': counts, 'library_roots': self.roots,
                'needed_name_pair_categories': output,
                'limitations': [
                    'Only vendor/bin ARM/AArch64 regular ELF files with a known interpreter are counted.',
                    'Only direct lib and lib64 roots of four partitions were searched; symlinks were not followed.',
                    'APEX, ODM, hardware subdirectories, linker namespaces, symbol versions and runtime state were not resolved.',
                    'Matching names/basic headers do not prove ABI compatibility; unseen names do not prove missing runtime libraries.',
                    'No ROM binary was executed and no image or device was changed.',
                ]}
