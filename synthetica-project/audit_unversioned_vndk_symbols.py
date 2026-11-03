#!/usr/bin/env python3
"""Read-only, bounded *name* observations for unversioned vendor ELF symbols.

For each selected vendor executable, unversioned undefined GLOBAL/WEAK names
are compared only to the union of names exported by its directly named, selected
VNDK 30 APEX libraries of the same bitness. An undefined ELF symbol is NOT
attributed to a particular DT_NEEDED library: other direct and transitive
providers can satisfy it. Neither a matching nor an unseen name proves linker
resolution, missing libraries, ABI compatibility, APEX activation or boot.
No candidate binaries are executed and no image or device is modified.
"""
from __future__ import annotations

import hashlib
import struct
from collections import Counter

import audit_vendor_abi as abi
import audit_vendor_elf_metadata as vendor_elf
import audit_vndk_symbols as versions

# Bound aggregation independently of the per-file ELF/section/symbol limits.
MAX_REFERENCE_EDGES = 2_000_000


class UnversionedProbeError(RuntimeError):
    pass


def _version(versym, idx: int) -> tuple[int, bool]:
    if versym is None:
        return 1, False
    value = versym.get_symbol(idx).entry['ndx']
    if value == 'VER_NDX_LOCAL':
        return 0, False
    if value == 'VER_NDX_GLOBAL':
        return 1, False
    if isinstance(value, int) and 0 <= value <= 0xffff:
        return value & 0x7fff, bool(value & 0x8000)
    raise UnversionedProbeError('Unknown ELF symbol version index')


def undefined_names(data: bytes) -> dict:
    """Read unversioned undefined global/weak names; do not assign a provider."""
    try:
        _, _, dyn, versym = versions.elf_sections(data)
        names, counts = set(), Counter()
        for idx, symbol in enumerate(dyn.iter_symbols()):
            if symbol['st_shndx'] != 'SHN_UNDEF':
                continue
            binding = symbol['st_info']['bind']
            if binding not in ('STB_GLOBAL', 'STB_WEAK'):
                continue
            version, hidden = _version(versym, idx)
            if version != 1 or hidden:
                counts['versioned_local_or_hidden_undefined_symbols_excluded'] += 1
                continue
            if not versions.SYMBOL_RE.fullmatch(symbol.name):
                counts['nonstandard_or_empty_symbol_names_excluded'] += 1
                continue
            names.add((symbol.name, 'weak' if binding == 'STB_WEAK' else 'strong'))
        return {'names': names, 'counts': counts}
    except (versions.SymbolProbeError, versions.ELFError, ValueError, TypeError, IndexError, KeyError,
            ZeroDivisionError, OverflowError, EOFError, struct.error) as exc:
        raise UnversionedProbeError(f'Unreadable dynamic undefined symbols: {type(exc).__name__}') from exc


def exported_names(data: bytes) -> dict:
    """Read externally visible definition names, not whether a linker selects them."""
    try:
        _, _, dyn, versym = versions.elf_sections(data)
        names, counts = set(), Counter()
        for idx, symbol in enumerate(dyn.iter_symbols()):
            if symbol['st_shndx'] == 'SHN_UNDEF' or symbol['st_info']['bind'] not in ('STB_GLOBAL', 'STB_WEAK'):
                continue
            if symbol['st_other']['visibility'] not in ('STV_DEFAULT', 'STV_PROTECTED'):
                counts['nonpublic_visibility_definitions_excluded'] += 1
                continue
            version, hidden = _version(versym, idx)
            # A non-default version is not a safe same-name candidate for an
            # unversioned lookup. Versions, types, and namespace are not resolved.
            if version == 0 or hidden:
                counts['local_or_nondefault_version_definitions_excluded'] += 1
                continue
            if not versions.SYMBOL_RE.fullmatch(symbol.name):
                counts['nonstandard_or_empty_symbol_names_excluded'] += 1
                continue
            names.add(symbol.name)
        return {'names': names, 'counts': counts}
    except (versions.SymbolProbeError, versions.ELFError, ValueError, TypeError, IndexError, KeyError,
            ZeroDivisionError, OverflowError, EOFError, struct.error) as exc:
        raise UnversionedProbeError(f'Unreadable dynamic exported symbols: {type(exc).__name__}') from exc


def _header_matches(entry, size: int, bits: int, kinds: tuple[int, ...]) -> bool:
    expected_machine = 40 if bits == 32 else 183 if bits == 64 else None
    header = abi.header_arch(entry, size)
    return bool(expected_machine is not None and header and header[:2] == (bits, expected_machine)
                and header[2] in kinds)


def _identity(names: set[str]) -> str:
    # Report a stable set digest instead of raw binary symbol names.
    return hashlib.sha256(''.join(name + '\n' for name in sorted(names)).encode('ascii')).hexdigest()


class Collector:
    def __init__(self):
        if versions.ELFFile is None:
            raise UnversionedProbeError('Pinned pyelftools host reader is missing')
        self.providers = {}
        self.records = []
        self.stats = Counter()
        self.reference_edges = 0

    def capture_provider(self, entry, size: int, bits: int, library: str) -> None:
        if library not in versions.SELECTED_LIBRARIES:
            return
        key = (bits, library)
        if bits not in (32, 64) or key in self.providers:
            raise UnversionedProbeError('Invalid or duplicate selected APEX provider')
        try:
            if not _header_matches(entry, size, bits, (3,)):
                raise UnversionedProbeError('Selected provider ELF header does not match bitness')
            data = versions.read_entry(entry, size)
            parsed = exported_names(data)
            result = {'status': 'read', 'names': parsed['names'],
                      'sha256': hashlib.sha256(data).hexdigest(), 'counts': parsed['counts']}
        except (UnversionedProbeError, versions.SymbolProbeError, OSError, RuntimeError):
            result = {'status': 'malformed_oversized_or_unreadable', 'names': set(), 'counts': {}}
        self.providers[key] = result

    def capture_consumer(self, entry, size: int, parsed: dict) -> None:
        bits, arch, interpreter = parsed['class'], parsed['architecture'], parsed['interpreter']
        if ((bits, arch) not in ((32, 'ARM'), (64, 'AArch64'))
                or parsed['type'] not in ('dynamic', 'executable')
                or interpreter not in vendor_elf.KNOWN_INTERPRETERS):
            return
        self.stats['eligible_executables'] += 1
        try:
            if not _header_matches(entry, size, bits, (2, 3)):
                raise UnversionedProbeError('Consumer ELF header does not match bitness')
            needed, invalid = abi.dynamic_needed(entry, size)
            self.stats['nonstandard_needed_names_not_reported'] += invalid
            selected = tuple(sorted(set(needed) & versions.SELECTED_LIBRARIES))
            if not selected:
                self.stats['without_selected_direct_dependency'] += 1
                return
            data = versions.read_entry(entry, size)
            result = undefined_names(data)
        except (UnversionedProbeError, versions.SymbolProbeError, abi.AbiAuditError,
                vendor_elf.ElfMetadataError, OSError, RuntimeError, struct.error, OverflowError):
            self.stats['malformed_oversized_or_unreadable'] += 1
            return
        self.reference_edges += len(result['names'])
        if self.reference_edges > MAX_REFERENCE_EDGES:
            raise UnversionedProbeError('Aggregate undefined symbol reference limit exceeded')
        self.records.append((bits, selected, result['names']))
        self.stats['parsed_executables'] += 1
        self.stats.update(result['counts'])
        if not result['names']:
            self.stats['without_unversioned_global_or_weak_names'] += 1

    def summarize(self) -> dict:
        providers = []
        for bits in (32, 64):
            for library in sorted(versions.SELECTED_LIBRARIES):
                info = self.providers.get((bits, library))
                row = {'bits': bits, 'library': library,
                       'status': info['status'] if info else 'not_observed'}
                if info and info['status'] == 'read':
                    row.update({'sha256': info['sha256'], 'exported_name_count': len(info['names']),
                                'exported_names_sha256': _identity(info['names'])})
                providers.append(row)

        groups, per_provider = {}, {}
        for bits, needed, names in self.records:
            readable = {name: self.providers[(bits, name)]['names'] for name in needed
                        if (bits, name) in self.providers and self.providers[(bits, name)]['status'] == 'read'}
            complete = len(readable) == len(needed)
            for symbol, binding in names:
                hits = [name for name, exports in readable.items() if symbol in exports]
                if hits:
                    category = 'same_name_seen_in_selected_direct_apex_provider'
                elif not readable:
                    category = 'not_compared_no_readable_selected_apex_provider'
                elif not complete:
                    category = 'not_seen_but_selected_provider_coverage_incomplete'
                else:
                    category = 'not_seen_in_selected_direct_apex_providers'
                key = (bits, binding, category)
                group = groups.setdefault(key, {'names': set(), 'edges': 0})
                group['names'].add(symbol)
                group['edges'] += 1
                for library in hits:
                    key = (bits, library, binding)
                    item = per_provider.setdefault(key, {'names': set(), 'edges': 0})
                    item['names'].add(symbol)
                    item['edges'] += 1

        observations = []
        for (bits, binding, category), group in sorted(groups.items()):
            observations.append({'bits': bits, 'binding': binding, 'observation': category,
                                 'distinct_names': len(group['names']),
                                 'distinct_names_sha256': _identity(group['names']),
                                 'executable_symbol_edges': group['edges']})
        by_provider = []
        for (bits, library, binding), group in sorted(per_provider.items()):
            by_provider.append({'bits': bits, 'library': library, 'binding': binding,
                                'distinct_matching_names': len(group['names']),
                                'executable_symbol_edges': group['edges']})
        return {'selected_library_names': sorted(versions.SELECTED_LIBRARIES),
                'consumer_executable_stats': {**self.stats, 'unversioned_executable_symbol_edges': self.reference_edges},
                'selected_apex_providers': providers, 'observations': observations,
                'same_name_by_selected_direct_provider': by_provider,
                'limitations': [
                    'Only unversioned undefined GLOBAL/WEAK names from vendor executables are compared.',
                    'Undefined names are not assigned to a DT_NEEDED library; other direct or transitive libraries can supply them.',
                    'A same-name observation is not a symbol-type, version, namespace, interposition, ABI or boot verdict.',
                    'A name unseen among selected providers is not an unresolved symbol or missing-library verdict.',
                    'Weak undefined symbols may legally remain unresolved; ODM, vendor shared-library consumers and runtime state are not inspected.',
                    'Provider unreadability and selected-provider coverage are reported separately; no candidate binary is run.',
                ]}
