#!/usr/bin/env python3
"""Compare pinned SUSFS source ABIs without installing or enabling anything.

Only the published 2.4.0 userspace/kernel definitions and the separate 2.3.0
LKM included in KSUN 3.4.2 are inspected. Source declarations are extracted,
then independently cross-compiled for the arm64 kernel and Android ABIs into
small inert ELF objects. No syscall, module load, Android SDK, or device access
is performed. This is NOT a SUSFS port or a behavior/security/runtime test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_synthetica40 as s40

PINS = json.loads((ROOT / 'build-kit/ci/s40-susfs-abi/inputs.json').read_text())
FEATURE_PREFIX = 'ksu_susfs/jni/features/'
USER_COMMON = 'ksu_susfs/jni/includes/susfs_defs.h'
SUSFS_HEADER = 'kernel_patches/include/linux/susfs.h'
SUSFS_DEFS = 'kernel_patches/include/linux/susfs_def.h'
SUSFS_GLUE = 'kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch'
KSUN_ABI = 'kernel/susfs/susfs_abi.h'
KSUN_DISPATCH = 'kernel/susfs/susfs_supercall.c'
PRIORITY = 'CMD_SUSFS_SET_PRIORITY_UID_FILTER'


def read_checked_sources(roots: dict[str, Path]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for group, expected_files in PINS['sources'].items():
        root = roots[group].resolve(strict=True)
        result[group] = {}
        for name, expected_hash in expected_files.items():
            rel = Path(name)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('Unsafe pinned source path')
            path = root / rel
            cursor = root
            for part in rel.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError(f'Symlinked source path: {path}')
            if not path.is_file():
                raise ValueError(f'Missing pinned source: {path}')
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError(f'Source SHA-256 mismatch: {path}')
            result[group][name] = content.decode('utf-8')
    return result


def without_comments(text: str) -> str:
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def numeric_defines(texts: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    rx = re.compile(r'^\s*#define\s+([A-Za-z_]\w*)\s+(0[xX][0-9a-fA-F]+|[0-9]+)\s*$', re.M)
    for text in texts:
        for name, raw in rx.findall(without_comments(text)):
            value = int(raw, 0)
            if name in result and result[name] != value:
                raise ValueError(f'Conflicting numeric definitions for {name}')
            result[name] = value
    return result


def kstat_flags(texts: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    rx = re.compile(r'^\s*#define\s+(KSTAT_SPOOF_\w+)\s+\(\s*1\s*<<\s*(\d+)\s*\)\s*$', re.M)
    for text in texts:
        for name, shift in rx.findall(without_comments(text)):
            value = 1 << int(shift)
            if name in result and result[name] != value:
                raise ValueError(f'Conflicting KSTAT flag: {name}')
            result[name] = value
    return result


def uid_scheme(text: str) -> dict[str, int]:
    match = re.search(r'\benum\s+UID_SCHEME\s*\{(.*?)\}\s*;', without_comments(text), re.S)
    if not match:
        raise ValueError('UID_SCHEME enum missing')
    result: dict[str, int] = {}
    value = -1
    for entry in match.group(1).split(','):
        entry = entry.strip()
        if not entry:
            continue
        field = re.fullmatch(r'(UID_[A-Z_]+)(?:\s*=\s*(\d+))?', entry)
        if not field or field.group(1) in result:
            raise ValueError('Unexpected UID_SCHEME entry')
        value = int(field.group(2)) if field.group(2) else value + 1
        result[field.group(1)] = value
    return result


def extract_structs(texts: list[str], wanted: set[str] | None = None) -> dict[str, dict]:
    """Extract only plain public wire structs; reject unsupported declarations."""
    structs: dict[str, dict] = {}
    rx = re.compile(r'^struct\s+(st_susfs_\w+)\s*\{(.*?)^\};', re.M | re.S)
    field_rx = re.compile(r'(bool|char|int|unsigned int|long|unsigned long|long long)\s+'
                          r'([A-Za-z_]\w*)\s*(?:\[\s*([^\]]+)\s*\])?\s*')
    for text in texts:
        for match in rx.finditer(without_comments(text)):
            name, body = match.groups()
            if wanted is not None and name not in wanted:
                continue
            if name in structs:
                raise ValueError(f'Duplicate struct: {name}')
            fields = []
            for declaration in body.split(';'):
                declaration = declaration.strip()
                if not declaration:
                    continue
                field = field_rx.fullmatch(declaration)
                if not field:
                    raise ValueError(f'Unexpected declaration in {name}: {declaration}')
                kind, field_name, array = field.groups()
                if any(existing['name'] == field_name for existing in fields):
                    raise ValueError(f'Duplicate field: {name}.{field_name}')
                fields.append({'name': field_name, 'type': kind + ('[]' if array else ''),
                               'array_expression': array})
            if not fields:
                raise ValueError(f'Empty wire struct: {name}')
            structs[name] = {'definition': f'struct {name} {{{body}\n}};', 'fields': fields}
    return structs


def elf_section(data: bytes, name: str, words: int) -> list[int]:
    """Read one fixed-size, inert section from a bounded ELF64/AArch64 object."""
    if len(data) > 1024 * 1024 or len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Compiler output is not a bounded little-endian ELF64 object')
    if struct.unpack_from('<HH', data, 16) != (1, 183):
        raise ValueError('Compiler output is not an AArch64 relocatable object')
    shoff = struct.unpack_from('<Q', data, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', data, 58)
    if (shentsize != 64 or not 0 < shnum <= 1024 or shstrndx >= shnum or
            shoff > len(data) or shnum * shentsize > len(data) - shoff):
        raise ValueError('Invalid ELF section table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * 64) for i in range(shnum)]

    def contents(section: tuple) -> bytes:
        offset, size = section[4], section[5]
        if offset > len(data) or size > len(data) - offset:
            raise ValueError('ELF section exceeds file')
        return data[offset:offset + size]

    if sections[shstrndx][1] != 3:  # SHT_STRTAB
        raise ValueError('ELF section-name table missing')
    names = contents(sections[shstrndx])
    found = []
    for section in sections:
        offset = section[0]
        if offset >= len(names):
            raise ValueError('Invalid ELF section name')
        end = names.find(b'\0', offset)
        if end < 0:
            raise ValueError('Unterminated ELF section name')
        if names[offset:end] == name.encode('ascii'):
            found.append(section)
    if len(found) != 1 or found[0][1] != 1:
        raise ValueError('Expected exactly one PROGBITS ABI section')
    raw = contents(found[0])
    if len(raw) != words * 8:
        raise ValueError('Unexpected ABI section length')
    return list(struct.unpack(f'<{words}Q', raw))


def compile_layouts(structs: dict[str, dict], constants: dict[str, int], triple: str, clang: str) -> dict[str, dict]:
    """Cross-compile extracted declarations; objects contain only numeric facts."""
    if not structs:
        raise ValueError('No ABI structs to compile')
    arrays = [f['array_expression'] for item in structs.values() for f in item['fields'] if f['array_expression']]
    tokens = {token for expression in arrays for token in re.findall(r'[A-Za-z_]\w*', expression)}
    if tokens - constants.keys():
        raise ValueError(f'Missing struct array constants: {sorted(tokens - constants.keys())}')
    definitions = '\n'.join(f'#define {name} {constants[name]}' for name in sorted(tokens))
    definitions += '\n' + '\n'.join(structs[name]['definition'] for name in sorted(structs))
    expressions = []
    for name in sorted(structs):
        expressions.extend((f'sizeof(struct {name})', f'_Alignof(struct {name})'))
        for field in structs[name]['fields']:
            f = field['name']
            expressions.extend((f'__builtin_offsetof(struct {name}, {f})',
                                f'sizeof(((struct {name} *)0)->{f})'))
    program = f'''typedef _Bool bool;
_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8 && sizeof(int) == 4 && sizeof(bool) == 1, "not LP64");
{definitions}
__attribute__((used, section(".s40abi"), aligned(8)))
const unsigned long long s40_layouts[] = {{ {', '.join(expressions)} }};
'''
    with tempfile.TemporaryDirectory(prefix='s40-susfs-abi-') as temporary:
        source, output = Path(temporary) / 'layout.c', Path(temporary) / 'layout.o'
        source.write_text(program)
        result = subprocess.run([clang, '-target', triple, '-std=c11', '-ffreestanding', '-nostdinc',
                                 '-c', str(source), '-o', str(output)],
                                text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f'arm64 ABI compilation failed: {result.stderr[-4000:]}')
        values = iter(elf_section(output.read_bytes(), '.s40abi', len(expressions)))
    layouts: dict[str, dict] = {}
    for name in sorted(structs):
        layout = {'size': next(values), 'alignment': next(values), 'fields': []}
        for field in structs[name]['fields']:
            layout['fields'].append({'name': field['name'], 'type': field['type'],
                                     'offset': next(values), 'size': next(values)})
        layouts[name] = layout
    return layouts


def compare_layouts(reference: dict[str, dict], other: dict[str, dict]) -> list[dict]:
    differences = []
    for name in sorted(reference.keys() | other.keys()):
        if name not in reference or name not in other:
            differences.append({'struct': name, 'issue': 'missing',
                                'side': 'reference' if name not in reference else 'other'})
            continue
        a, b = reference[name], other[name]
        for key in ('size', 'alignment'):
            if a[key] != b[key]:
                differences.append({'struct': name, 'issue': key, 'reference': a[key], 'other': b[key]})
        af, bf = a['fields'], b['fields']
        if [f['name'] for f in af] != [f['name'] for f in bf]:
            differences.append({'struct': name, 'issue': 'field_order_or_names'})
            continue
        for x, y in zip(af, bf):
            for key in ('type', 'offset', 'size'):
                if x[key] != y[key]:
                    differences.append({'struct': name, 'field': x['name'], 'issue': key,
                                        'reference': x[key], 'other': y[key]})
    return differences


def function_cases(text: str, function: str) -> set[str]:
    # These pinned functions close at column zero; nested blocks are indented.
    match = re.search(r'\b' + re.escape(function) + r'\s*\([^)]*\)\s*\{(.*?)^\}',
                      without_comments(text), re.M | re.S)
    if not match:
        raise ValueError(f'Dispatch function missing: {function}')
    return set(re.findall(r'\bcase\s+(CMD_SUSFS_\w+)\s*:', match.group(1)))


def audit(roots: dict[str, Path], clang: str) -> dict:
    if (PINS['kernel_commit'] != s40.PINS['kernel']['commit'] or
            PINS['ksun_commit'] != s40.PINS['ksun']['commit'] or
            PINS['susfs_commit'] != s40.PINS['susfs_research_only']['commit']):
        raise ValueError('ABI source pins disagree with the 4.0 source pins')
    texts = read_checked_sources(roots)
    sus, ks, kernel = texts['susfs'], texts['ksun'], texts['kernel']
    features = [sus[name] for name in sorted(sus) if name.startswith(FEATURE_PREFIX) and name.endswith('.c')]
    if len(features) != 11:
        raise ValueError('Unexpected 2.4 userspace feature source set')
    user_constants = numeric_defines(features + [sus[USER_COMMON]])
    kernel_constants = numeric_defines([sus[SUSFS_DEFS], sus[SUSFS_HEADER], kernel['include/uapi/linux/utsname.h']])
    lkm_constants = numeric_defines([ks[KSUN_ABI], kernel['include/uapi/linux/utsname.h']])
    user_cmd = {k: v for k, v in user_constants.items() if k.startswith('CMD_SUSFS_')}
    kern_cmd = {k: v for k, v in kernel_constants.items() if k.startswith('CMD_SUSFS_')}
    lkm_cmd = {k: v for k, v in lkm_constants.items() if k.startswith('CMD_SUSFS_')}
    if len(user_cmd) != 16 or any(kern_cmd.get(k) != v for k, v in user_cmd.items()):
        raise ValueError('Official 2.4 userspace and kernel command IDs differ')
    if len(set(user_cmd.values())) != len(user_cmd):
        raise ValueError('Duplicate active SUSFS command IDs')
    user_calls = set(re.findall(r'syscall\s*\(\s*SYS_reboot\s*,\s*KSU_INSTALL_MAGIC1\s*,\s*SUSFS_MAGIC\s*,\s*(CMD_SUSFS_\w+)',
                                without_comments('\n'.join(features))))
    kernel_cases = set(re.findall(r'^\+\s*case\s+(CMD_SUSFS_\w+)\s*:', sus[SUSFS_GLUE], re.M))
    if user_calls != user_cmd.keys() or kernel_cases != user_cmd.keys():
        raise ValueError('2.4 userspace calls or proposed kernel dispatcher do not cover the active commands')
    if (user_constants.get('KSU_INSTALL_MAGIC1') != 0xDEADBEEF or
            user_constants.get('SUSFS_MAGIC') != 0xFAFAFAFA or
            kernel_constants.get('SUSFS_MAGIC') != 0xFAFAFAFA or
            lkm_constants.get('KSU_INSTALL_MAGIC1') != 0xDEADBEEF or
            lkm_constants.get('SUSFS_MAGIC') != 0xFAFAFAFA):
        raise ValueError('SUSFS reboot magic differs')
    if user_cmd.get(PRIORITY) != 0x60030:
        raise ValueError('2.4 priority UID filter command unexpectedly changed')
    if ('APP_ABI := arm64-v8a' not in sus['ksu_susfs/jni/Application.mk'] or
            '"set_priority_uid_filter"' not in sus['ksu_susfs/jni/main.c'] or
            'void susfs_set_priority_uid_filter(' not in sus['kernel_patches/fs/susfs.c'] or
            'bool susfs_is_priority_uid_filtered(' not in sus['kernel_patches/fs/susfs.c']):
        raise ValueError('Expected 2.4 arm64 userspace or priority filter source missing')
    ksu_magic = re.search(r'KSU_INSTALL_MAGIC2\s*=\s*(0x[0-9a-fA-F]+)', ks['uapi/supercall.h'])
    if not ksu_magic or int(ksu_magic.group(1), 16) != 0xCAFEBABE:
        raise ValueError('Unexpected KSUN fd-install reboot magic')
    if int(ksu_magic.group(1), 16) == user_constants['SUSFS_MAGIC']:
        raise ValueError('KSUN and SUSFS second reboot magics collide')
    flags = kstat_flags(features)
    if len(flags) != 12 or flags != kstat_flags([sus[SUSFS_HEADER]]) or flags != kstat_flags([ks[KSUN_ABI]]):
        raise ValueError('KSTAT spoof flag definitions differ')
    user_uid = uid_scheme('\n'.join(features))
    if user_uid != uid_scheme(sus[SUSFS_HEADER]) or user_uid != uid_scheme(ks[KSUN_ABI]):
        raise ValueError('UID_SCHEME enumeration differs')
    if '#define SUSFS_VERSION "v2.4.0"' not in sus[SUSFS_HEADER] or '#define SUSFS_VERSION_STR "v2.3.0"' not in ks[KSUN_ABI]:
        raise ValueError('Unexpected SUSFS source version')
    if 'obj-m += susfs_guard_lkm.o' not in ks['kernel/susfs/Makefile']:
        raise ValueError('Expected a separate KSUN SUSFS LKM Makefile')
    if re.search(r'\bsusfs\b', without_comments(ks['kernel/Kbuild']), re.I):
        raise ValueError('Parent KernelSU Kbuild unexpectedly references SUSFS')
    if ('#define REBOOT_SYMBOL "__arm64_sys_reboot"' not in ks['kernel/include/arch.h'] or
            '.symbol_name = REBOOT_SYMBOL' not in ks['kernel/supercall/supercall.c'] or
            '.symbol_name = "__arm64_sys_reboot"' not in ks[KSUN_DISPATCH]):
        raise ValueError('Expected shared arm64 reboot hook references missing')
    accepted = function_cases(ks[KSUN_DISPATCH], 'susfs_cmd_handled')
    handled = function_cases(ks[KSUN_DISPATCH], 'susfs_tw_func')
    if accepted != handled or not accepted <= lkm_cmd.keys():
        raise ValueError('LKM accepted-command list and dispatcher differ')
    user_structs = extract_structs(features)
    if len(user_structs) != 13:
        raise ValueError('Unexpected official userspace wire struct set')
    kernel_structs = extract_structs([sus[SUSFS_HEADER]], set(user_structs))
    lkm_structs = extract_structs([ks[KSUN_ABI]], set(user_structs))
    user_layouts = compile_layouts(user_structs, user_constants, 'aarch64-linux-android26', clang)
    kernel_layouts = compile_layouts(kernel_structs, kernel_constants, 'aarch64-unknown-linux-gnu', clang)
    lkm_layouts = compile_layouts(lkm_structs, lkm_constants, 'aarch64-unknown-linux-gnu', clang)
    mismatch = compare_layouts(user_layouts, kernel_layouts)
    if mismatch:
        raise ValueError(f'Official 2.4 arm64 userspace/kernel layout mismatch: {mismatch}')
    lkm_mismatches = compare_layouts(user_layouts, lkm_layouts)
    lkm_missing_commands = sorted(set(user_cmd) - accepted)
    changed_ids = {k: {'userspace': v, 'lkm': lkm_cmd.get(k)}
                   for k, v in user_cmd.items() if k in lkm_cmd and lkm_cmd[k] != v}
    version = subprocess.run([clang, '--version'], text=True, capture_output=True, check=True).stdout.splitlines()[0]
    return {
        'scope': 'PINNED_SOURCE_ARM64_ABI_RESEARCH_ONLY',
        'compiler': version,
        'targets': ['aarch64-linux-android26', 'aarch64-unknown-linux-gnu'],
        'official_2_4_source': {
            'active_userspace_commands': len(user_cmd),
            'userspace_kernel_and_glue_command_ids_match': True,
            'userspace_kernel_wire_structs_match': len(user_layouts),
            'kstat_flag_bits_match': len(flags),
            'uid_schemes_match': len(user_uid),
            'priority_uid_filter_command': hex(user_cmd[PRIORITY]),
            'priority_uid_filter_layout': user_layouts['st_susfs_priority_uid_filter'],
        },
        'ksun_3_4_2_separate_lkm_source': {
            'version_in_source': '2.3.0',
            'parent_ksun_kbuild_references_lkm': False,
            'separate_lkm_makefile_present': True,
            'active_2_4_command_names_not_handled': lkm_missing_commands,
            'active_command_id_differences': changed_ids,
            'arm64_wire_layout_differences_against_2_4_userspace': lkm_mismatches,
            'shares_arm64_reboot_hook_symbol_with_ksun': True,
            'ksun_fd_install_and_susfs_second_magics_differ': True,
        },
        'susfs_2_4_integrated': False,
        'syscalls_run_or_modules_loaded': False,
        'runtime_behavior_security_or_nomount_tested': False,
        'flashable_or_release': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    archives = sub.add_parser('verify-archives')
    for name in ('kernel', 'ksun', 'susfs'):
        archives.add_argument(f'--{name}', type=Path, required=True)
    scan = sub.add_parser('audit')
    for name in ('kernel', 'ksun', 'susfs'):
        scan.add_argument(f'--{name}', type=Path, required=True)
    scan.add_argument('--clang', default='clang')
    args = parser.parse_args()
    if args.command == 'verify-archives':
        for name in ('kernel', 'ksun', 'susfs'):
            s40.verify_archive('susfs_research_only' if name == 'susfs' else name, getattr(args, name))
            print(f'{name} archive SHA-256 OK')
    else:
        print(json.dumps(audit({n: getattr(args, n) for n in ('kernel', 'ksun', 'susfs')}, args.clang), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, struct.error) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
