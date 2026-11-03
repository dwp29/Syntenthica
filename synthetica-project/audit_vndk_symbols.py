#!/usr/bin/env python3
"""Compare a narrow set of versioned ELF references with existing VNDK 30.

Only versioned undefined symbols in vendor executables and explicitly versioned
exports in nine selected on-disk VNDK libraries are compared. It is NOT an
Android dynamic linker: transitive libraries, unversioned symbols, namespaces,
weak-symbol behavior, symbol interposition, ODM and runtime activation are not
resolved. Neither match nor absence is an ABI, functional or boot verdict.
"""
from __future__ import annotations

import hashlib
import io
import re
import struct
from collections import Counter

import audit_vendor_abi as abi
import audit_vendor_elf_metadata as vendor_elf

try:
    from elftools.elf.elffile import ELFFile
    from elftools.common.exceptions import ELFError
except ImportError:
    ELFFile = None
    ELFError = ValueError

SELECTED_LIBRARIES = frozenset(('libc++.so', 'libcutils.so', 'libutils.so', 'libhidlbase.so',
                                'libbase.so', 'libhardware.so', 'libbinder.so', 'libcrypto.so', 'libssl.so'))
MAX_ELF = 32 * 1024 * 1024
MAX_SECTIONS = 512
MAX_SYMBOLS = 150000
MAX_VERSIONS = 10000
SYMBOL_RE = re.compile(r'[!-~]{1,1024}\Z')
VERSION_RE = re.compile(r'[!-~]{1,128}\Z')


class SymbolProbeError(RuntimeError):
    pass


def read_entry(entry, size: int) -> bytes:
    if not 0 < size <= MAX_ELF:
        raise SymbolProbeError('ELF file exceeds bounded size')
    result = bytearray()
    while len(result) < size:
        block = entry.read_random(len(result), min(1024 * 1024, size - len(result)))
        if not block or len(block) > size - len(result):
            raise SymbolProbeError('Short ELF read')
        result.extend(block)
    return bytes(result)


def elf_sections(data: bytes):
    if ELFFile is None:
        raise SymbolProbeError('Pinned pyelftools host reader is missing')
    if not 0 < len(data) <= MAX_ELF or data[:4] != b'\x7fELF':
        raise SymbolProbeError('Invalid or oversized ELF')
    try:
        elf = ELFFile(io.BytesIO(data))
        if elf.num_sections() > MAX_SECTIONS:
            raise SymbolProbeError('ELF section count exceeds bound')
        by_name, indexes = {}, {}
        for index, section in enumerate(elf.iter_sections()):
            name = section.name
            if name not in ('.dynsym', '.gnu.version', '.gnu.version_r', '.gnu.version_d'):
                continue
            if name in by_name:
                raise SymbolProbeError('Duplicate selected ELF section')
            header = section.header
            if (header['sh_type'] == 'SHT_NOBITS' or header['sh_offset'] > len(data)
                    or header['sh_size'] > len(data) - header['sh_offset']):
                raise SymbolProbeError('ELF section exceeds file bounds')
            by_name[name], indexes[name] = section, index
        dyn = by_name.get('.dynsym')
        if dyn is None or dyn.num_symbols() > MAX_SYMBOLS:
            raise SymbolProbeError('Missing or oversized dynamic symbol table')
        versym = by_name.get('.gnu.version')
        if versym and (versym.num_symbols() != dyn.num_symbols()
                       or versym.header['sh_link'] != indexes['.dynsym']):
            raise SymbolProbeError('ELF version and symbol tables do not correspond')
        for name in ('.gnu.version_r', '.gnu.version_d'):
            if name in by_name and by_name[name].header['sh_link'] != dyn.header['sh_link']:
                raise SymbolProbeError('ELF version strings differ from dynamic symbol strings')
        return elf, by_name, dyn, versym
    except (ELFError, ValueError, TypeError, IndexError, KeyError, ZeroDivisionError,
            OverflowError, EOFError, struct.error) as exc:
        raise SymbolProbeError(f'Unreadable bounded ELF: {type(exc).__name__}') from exc


def version_index(value):
    return (value & 0x7fff) if isinstance(value, int) else None


def _version_need(section, allowed: set[str]) -> dict:
    result, count = {}, 0
    if section.num_versions() > MAX_VERSIONS:
        raise SymbolProbeError('Too many ELF version requirements')
    for item, auxs in section.iter_versions():
        if item['vn_cnt'] > MAX_VERSIONS:
            raise SymbolProbeError('Too many ELF version auxiliaries')
        library = item.name
        for aux in auxs:
            count += 1
            if count > MAX_VERSIONS:
                raise SymbolProbeError('ELF version requirement limit exceeded')
            idx, version = version_index(aux['vna_other']), aux.name
            if idx is None or idx <= 1:
                continue
            if idx in result:
                raise SymbolProbeError('Duplicate ELF required version index')
            if library in allowed and VERSION_RE.fullmatch(version):
                result[idx] = (library, version)
    return result


def _version_def(section) -> dict:
    result, count = {}, 0
    if section.num_versions() > MAX_VERSIONS:
        raise SymbolProbeError('Too many ELF version definitions')
    for item, auxs in section.iter_versions():
        if item['vd_cnt'] > MAX_VERSIONS:
            raise SymbolProbeError('Too many ELF version definition auxiliaries')
        idx = version_index(item['vd_ndx'])
        values = []
        for aux in auxs:
            count += 1
            if count > MAX_VERSIONS:
                raise SymbolProbeError('ELF version definition limit exceeded')
            values.append(aux.name)
        if idx is None or idx <= 1:
            continue
        if idx in result or not values or not VERSION_RE.fullmatch(values[0]):
            raise SymbolProbeError('Malformed ELF version definition')
        result[idx] = values[0]
    return result


def consumer_references(data: bytes, needed: set[str]) -> dict:
    _, sections, dyn, versym = elf_sections(data)
    section = sections.get('.gnu.version_r')
    if versym is None or section is None:
        return {'status': 'no_version_requirements', 'references': set()}
    try:
        versions = _version_need(section, set(needed) & SELECTED_LIBRARIES)
        refs = set()
        for idx, symbol in enumerate(dyn.iter_symbols()):
            if symbol['st_shndx'] != 'SHN_UNDEF':
                continue
            binding = symbol['st_info']['bind']
            if binding not in ('STB_GLOBAL', 'STB_WEAK'):
                continue
            version = versions.get(version_index(versym.get_symbol(idx).entry['ndx']))
            if version and SYMBOL_RE.fullmatch(symbol.name):
                refs.add((version[0], symbol.name, version[1], 'weak' if binding == 'STB_WEAK' else 'strong'))
        return {'status': 'read', 'references': refs}
    except (ELFError, ValueError, TypeError, IndexError, KeyError, ZeroDivisionError,
            OverflowError, EOFError, struct.error) as exc:
        raise SymbolProbeError(f'Unreadable version requirements: {type(exc).__name__}') from exc


def provider_exports(data: bytes) -> dict:
    _, sections, dyn, versym = elf_sections(data)
    section = sections.get('.gnu.version_d')
    if versym is None or section is None:
        return {'status': 'no_explicit_version_definitions', 'exports': set()}
    try:
        versions = _version_def(section)
        exports = set()
        for idx, symbol in enumerate(dyn.iter_symbols()):
            if symbol['st_shndx'] == 'SHN_UNDEF' or symbol['st_info']['bind'] not in ('STB_GLOBAL', 'STB_WEAK'):
                continue
            if symbol['st_other']['visibility'] not in ('STV_DEFAULT', 'STV_PROTECTED'):
                continue
            version = versions.get(version_index(versym.get_symbol(idx).entry['ndx']))
            if version and SYMBOL_RE.fullmatch(symbol.name):
                exports.add((symbol.name, version))
        return {'status': 'read', 'exports': exports}
    except (ELFError, ValueError, TypeError, IndexError, KeyError, ZeroDivisionError,
            OverflowError, EOFError, struct.error) as exc:
        raise SymbolProbeError(f'Unreadable version definitions: {type(exc).__name__}') from exc


class Collector:
    def __init__(self):
        if ELFFile is None:
            raise SymbolProbeError('Pinned pyelftools host reader is missing')
        self.providers = {}
        self.references = Counter()
        self.stats = Counter()

    def capture_provider(self, entry, size: int, bits: int, library: str) -> None:
        if library not in SELECTED_LIBRARIES:
            return
        key = (bits, library)
        if key in self.providers:
            raise SymbolProbeError('Duplicate selected APEX provider')
        try:
            data = read_entry(entry, size)
            result = provider_exports(data)
            result['sha256'] = hashlib.sha256(data).hexdigest()
        except (SymbolProbeError, OSError, RuntimeError):
            result = {'status': 'malformed_oversized_or_unreadable', 'exports': set()}
        self.providers[key] = result

    def capture_consumer(self, entry, size: int, parsed: dict) -> None:
        bits, arch, interpreter = parsed['class'], parsed['architecture'], parsed['interpreter']
        if ((bits, arch) not in ((32, 'ARM'), (64, 'AArch64'))
                or parsed['type'] not in ('dynamic', 'executable')
                or interpreter not in vendor_elf.KNOWN_INTERPRETERS):
            return
        self.stats['eligible_executables'] += 1
        try:
            names, _ = abi.dynamic_needed(entry, size)
            if not set(names) & SELECTED_LIBRARIES:
                self.stats['without_selected_direct_dependency'] += 1
                return
            data = read_entry(entry, size)
            result = consumer_references(data, set(names))
        except (SymbolProbeError, abi.AbiAuditError, vendor_elf.ElfMetadataError, OSError,
                RuntimeError, struct.error, OverflowError):
            self.stats['malformed_oversized_or_unreadable'] += 1
            return
        self.stats['parsed_executables'] += 1
        if result['status'] == 'no_version_requirements':
            self.stats['without_version_requirements'] += 1
        elif not result['references']:
            self.stats['without_selected_versioned_references'] += 1
        else:
            self.stats['with_selected_versioned_references'] += 1
        for library, symbol, version, binding in result['references']:
            self.references[(bits, library, symbol, version, binding)] += 1

    def summarize(self) -> dict:
        providers = []
        for bits in (32, 64):
            for name in sorted(SELECTED_LIBRARIES):
                info = self.providers.get((bits, name))
                row = {'bits': bits, 'library': name, 'status': info['status'] if info else 'not_observed'}
                if info:
                    row['sha256'] = info.get('sha256')
                    if info['status'] == 'read':
                        row['versioned_export_pairs'] = len(info['exports'])
                providers.append(row)
        groups = {}
        for (bits, library, symbol, version, binding), references in self.references.items():
            provider = self.providers.get((bits, library))
            if not provider or provider['status'] != 'read':
                category = 'not_compared_no_readable_version_definitions'
            elif (symbol, version) in provider['exports']:
                category = 'same_symbol_and_version_seen_in_named_apex_library'
            else:
                category = 'same_symbol_and_version_not_seen_in_named_apex_library'
            key = (bits, library, binding, category)
            row = groups.setdefault(key, {'bits': bits, 'library': library, 'binding': binding,
                                          'observation': category, 'distinct_symbol_version_pairs': 0,
                                          'executable_reference_edges': 0})
            row['distinct_symbol_version_pairs'] += 1
            row['executable_reference_edges'] += references
        return {'selected_library_names': sorted(SELECTED_LIBRARIES),
                'consumer_executable_stats': dict(self.stats), 'selected_apex_providers': providers,
                'observations': [groups[k] for k in sorted(groups)],
                'limitations': ['Only selected libraries and direct versioned executable references were compared.',
                    'Unversioned symbols, shared-library consumers, ODM, namespaces, interposition and transitive dependencies were not resolved.',
                    'Absence in the named APEX library does not establish runtime failure; matches do not establish ABI or boot.']}
