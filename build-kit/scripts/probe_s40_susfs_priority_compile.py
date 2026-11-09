#!/usr/bin/env python3
"""Compile a tiny SUSFS priority-filter research slice, NEVER a bootable kernel.

Two pinned upstream 2.4 priority-hook hunks are extracted for each syscall
file, together with the declaration hunk. The 2.4 filter and a separately
pinned research-only race guard are compiled as ARM64 objects against the
prepared 6.18 tree and KSUN 3.4.2. A second pending-refresh candidate is also
compiled but still has a known failed-thread-start race. A stalled-marker
candidate adds no automatic retry. A tiny adapter maps the upstream domain
query to the KSUN symbol *for this compile experiment only*; its runtime
semantics are NOT established. The objects are partially linked to check a few
symbol references, while hundreds of unrelated kernel symbols may remain
unresolved. There is no dispatcher, full SUSFS build, image, module, device
operation or production integration. Never load or ship the objects.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_s40_susfs_abi as abi
import build_synthetica40 as s40
import probe_s40_susfs_priority as priority
import probe_s40_susfs_pending as pending_probe
import probe_s40_susfs_stalled as stalled_probe

PINS = abi.PINS['priority_compile_research']
PATCH = 'kernel_patches/50_add_susfs_in_gki-android14-6.1.patch'
MARKER = 'S40-PRIORITY-RESEARCH.json'
FLAG = 'CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER'
OUTPUT_SOURCES = {'original': 'fs/s40_priority_original.c',
                  'guarded': 'fs/s40_priority_guarded.c',
                  'pending': 'fs/s40_priority_pending.c',
                  'stalled': 'fs/s40_priority_stalled.c'}


def checked_file(root: Path, relative: str, expected: str) -> str:
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe source path')
    path = root.resolve(strict=True)
    for part in rel.parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f'Symlinked source path: {path}')
    if not path.is_file() or s40.sha256(path) != expected:
        raise ValueError(f'Missing or unpinned source: {path}')
    return path.read_text()


def selected_patch(upstream: str) -> str:
    """Retain ONLY the six priority-specific hunks from the pinned patch."""
    if hashlib.sha256(upstream.encode()).hexdigest() != PINS['upstream_kernel_patch_sha256']:
        raise ValueError('Upstream kernel patch SHA-256 mismatch')
    sections = re.split(r'(?=^diff --git )', upstream, flags=re.M)
    selected: dict[str, str] = {}
    for section in sections:
        match = re.match(r'diff --git a/([^\s]+) b/([^\s]+)\n', section)
        if not match or match.group(1) not in PINS['kernel_files']:
            continue
        path = match.group(1)
        if path != match.group(2) or path in selected:
            raise ValueError('Unexpected or duplicate upstream patch path')
        first = re.search(r'^@@ ', section, re.M)
        if not first or f'--- a/{path}\n+++ b/{path}\n' not in section[:first.start()]:
            raise ValueError('Unexpected upstream patch header')
        header = section[:first.start()]
        hunks = re.split(r'(?=^@@ )', section[first.start():], flags=re.M)
        matches = [hunk for hunk in hunks if f'+#ifdef {FLAG}\n' in hunk]
        if len(matches) != PINS['kernel_files'][path]['selected_hunks']:
            raise ValueError(f'Unexpected priority hunk count: {path}')
        selected[path] = header + ''.join(matches)
    if set(selected) != set(PINS['kernel_files']):
        raise ValueError('A priority syscall patch is missing')
    result = ''.join(selected[path] for path in PINS['kernel_files'])
    if hashlib.sha256(result.encode()).hexdigest() != PINS['selected_priority_hunks_sha256']:
        raise ValueError('Selected priority hunks SHA-256 mismatch')
    return result


PREAMBLE = r'''/* S40 research-only fragment: no dispatcher, no image, DO NOT LOAD. */
#include <linux/cred.h>
#include <linux/fs.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/kthread.h>
#include <linux/bitmap.h>
#include <linux/rcupdate.h>
#include <linux/vmalloc.h>
#include <linux/string.h>
#include <linux/limits.h>
#include <linux/printk.h>
#define SUSFS_APP_STR_BUF_SIZE 65535
#define SUSFS_LOGI(fmt, ...) pr_info("s40-priority-research: " fmt, ##__VA_ARGS__)
#define SUSFS_LOGE(fmt, ...) pr_err("s40-priority-research: " fmt, ##__VA_ARGS__)
/* Prototypes checked against pinned KSUN header and implementation before
 * generating this test. The full header uses non-strict prototypes. */
extern void setup_selinux(const char *, struct cred *);
extern bool is_ksu_domain(void);
/* Compile-only adapter. Equivalence to SUSFS's own domain test is unproven. */
static bool susfs_is_current_ksu_domain(void) { return is_ksu_domain(); }
void susfs_set_priority_uid_filter(void __user **user_info);
void susfs_parse_priority_app_strings(void);
bool susfs_is_priority_uid_filtered(uid_t uid);
'''


def fragment(source: str, header: str) -> str:
    """Build a translation unit containing exact 2.4 functions and test glue."""
    digest = hashlib.sha256(source.encode()).hexdigest()
    if digest not in {abi.PINS['sources']['susfs'][priority.SOURCE],
                      abi.PINS['research_priority_guard']['guarded_susfs_c_sha256'],
                      abi.PINS['research_priority_pending']['pending_guarded_susfs_c_sha256'],
                      abi.PINS['research_priority_stalled']['stalled_susfs_c_sha256']}:
        raise ValueError('Priority fragment source is not pinned')
    if hashlib.sha256(header.encode()).hexdigest() != abi.PINS['sources']['susfs'][priority.HEADER]:
        raise ValueError('Priority header is not pinned')
    if abi.numeric_defines([header]).get('SUSFS_APP_STR_BUF_SIZE') != 65535:
        raise ValueError('Unexpected priority payload size constant')
    payload = abi.extract_structs([header], {'st_susfs_priority_uid_filter'})
    if set(payload) != {'st_susfs_priority_uid_filter'}:
        raise ValueError('Priority wire struct missing')
    for declaration in ('void susfs_set_priority_uid_filter(void __user **user_info);',
                        'void susfs_parse_priority_app_strings(void);'):
        if header.count(declaration) != 1:
            raise ValueError('Unexpected upstream priority prototypes')
    marker = '#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER\n/*****************************************/\n/* getpriority uid filter (bitmap)'
    end_marker = '#endif // #ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER'
    if source.count(marker) != 1:
        raise ValueError('Priority implementation block not found exactly once')
    start = source.index(marker)
    end = source.find(end_marker, start)
    if end < 0:
        raise ValueError('Unterminated priority implementation block')
    end += len(end_marker)
    functions = [priority.extract_function(source, 'static struct cred *susfs_switch_to_ksu_domain('),
                 priority.extract_function(source, 'static void susfs_restore_creds(')]
    return '\n'.join((PREAMBLE, payload['st_susfs_priority_uid_filter']['definition'],
                      *functions, source[start:end], ''))


def run(command: list[str], *, cwd: Path | None = None, input: str | None = None,
        env: dict[str, str] | None = None, stream: bool = False) -> str:
    result = subprocess.run(command, cwd=cwd, input=input, env=env, text=True,
                            stdout=sys.stderr if stream else subprocess.PIPE,
                            stderr=sys.stderr if stream else subprocess.PIPE)
    if result.returncode:
        detail = '' if stream else '\n' + (result.stdout + '\n' + result.stderr)[-4000:]
        raise RuntimeError(f'{Path(command[0]).name} returned {result.returncode}{detail}')
    return '' if stream else result.stdout


def prepare(kernel: Path, ksun: Path, nomount: Path, susfs: Path, work: Path) -> Path:
    # Verify the particularly relevant files before creating any work directory.
    for path, expected in PINS['kernel_files'].items():
        checked_file(kernel, path, expected['original_sha256'])
    ksu = {path: checked_file(ksun, path, expected) for path, expected in PINS['ksun_files'].items()}
    ksu_c, ksu_h = ksu['kernel/selinux/selinux.c'], ksu['kernel/selinux/selinux.h']
    if (ksu_h.count('void setup_selinux(const char *, struct cred *);') != 1 or
            ksu_h.count('bool is_ksu_domain();') != 1 or
            ksu_c.count('void setup_selinux(const char *domain, struct cred *cred)') != 1 or
            ksu_c.count('bool is_ksu_domain(void)') != 1):
        raise ValueError('Unexpected KSUN domain adapter prototypes')
    original = priority.checked_susfs_file(susfs, priority.SOURCE)
    header = priority.checked_susfs_file(susfs, priority.HEADER)
    patch = selected_patch(checked_file(susfs, PATCH, PINS['upstream_kernel_patch_sha256']))
    with tempfile.TemporaryDirectory(prefix='s40-guard-extraction-') as temp:
        guarded = priority.apply_candidate(original, Path(temp) / 'generation')
        pending = pending_probe.apply_pending(guarded, Path(temp) / 'pending')
        stalled = stalled_probe.apply_stalled(pending, Path(temp) / 'stalled')
    generated = {'original': fragment(original, header), 'guarded': fragment(guarded, header),
                 'pending': fragment(pending, header), 'stalled': fragment(stalled, header)}
    generated_hashes = {key: hashlib.sha256(value.encode()).hexdigest() for key, value in generated.items()}
    if generated_hashes != PINS['generated_fragment_sha256']:
        raise ValueError('Generated priority fragment SHA-256 mismatch')
    s40.check_work_directory(work, [kernel, ksun, nomount, susfs])
    dst = s40.prepare(kernel, ksun, nomount, work)
    run(['git', 'apply', '--check', '-'], cwd=dst, input=patch)
    run(['git', 'apply', '-'], cwd=dst, input=patch)
    for path, expected in PINS['kernel_files'].items():
        checked_file(dst, path, expected['research_output_sha256'])
    for mode, relative in OUTPUT_SOURCES.items():
        path = dst / relative
        if path.exists() or path.is_symlink():
            raise ValueError(f'Research source already exists: {path}')
        path.write_text(generated[mode])
    marker = {
        'scope': 'DO_NOT_LOAD_SELECTED_SOURCE_OBJECTS_ONLY',
        'upstream_patch_sha256': PINS['upstream_kernel_patch_sha256'],
        'selected_hunks_sha256': PINS['selected_priority_hunks_sha256'],
        'fragment_sha256': generated_hashes,
    }
    (work / MARKER).write_text(json.dumps(marker, indent=2) + '\n')
    return dst


def checked_work(work: Path) -> tuple[Path, Path, dict]:
    if work.is_symlink() or not work.is_dir():
        raise ValueError('Research work directory is missing or symlinked')
    resolved = work.resolve(strict=True)
    repo, home = ROOT.resolve(), Path.home().resolve()
    if (resolved == home or resolved in home.parents or resolved == repo or
            resolved in repo.parents or repo in resolved.parents):
        raise ValueError('Refusing to compile in the repository or a protected ancestor')
    marker_path, src, out = resolved / MARKER, resolved / 'kernel', resolved / 'out'
    if marker_path.is_symlink() or not marker_path.is_file() or src.is_symlink() or out.is_symlink():
        raise ValueError('Invalid research work marker or directory')
    marker = json.loads(marker_path.read_text())
    if (marker.get('scope') != 'DO_NOT_LOAD_SELECTED_SOURCE_OBJECTS_ONLY' or
            marker.get('upstream_patch_sha256') != PINS['upstream_kernel_patch_sha256'] or
            marker.get('selected_hunks_sha256') != PINS['selected_priority_hunks_sha256'] or
            marker.get('fragment_sha256') != PINS['generated_fragment_sha256']):
        raise ValueError('Invalid research work marker')
    for path, expected in PINS['kernel_files'].items():
        checked_file(src, path, expected['research_output_sha256'])
    for path, expected in PINS['ksun_files'].items():
        checked_file(src / 'drivers/kernelsu', path.removeprefix('kernel/'), expected)
    for mode, path in OUTPUT_SOURCES.items():
        checked_file(src, path, marker['fragment_sha256'][mode])
    if any('s40_priority_' in (src / path).read_text() for path in ('fs/Makefile', 'fs/Kconfig')):
        raise ValueError('Research objects must not be registered in the kernel build')
    config_file = out / '.config'
    if config_file.is_symlink() or not config_file.is_file():
        raise ValueError('Configure the isolated 6.18 output first')
    # Kbuild creates just this one legitimate symlink. Refuse any other output
    # symlink before allowing make or removing/rebuilding the selected objects.
    for parent, dirs, files in os.walk(out, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            if path.is_symlink() and not (path == out / 'source' and path.resolve() == src):
                raise ValueError(f'Unexpected symlink in research output: {path}')
    fragments = [src / 'miatoll/configs/sm7125-prune.config',
                 src / 'miatoll/configs/miatoll.config', src / 'miatoll/configs/lineage1.config',
                 ROOT / 'build-kit/ci/synthetica40/experimental.config']
    with contextlib.redirect_stdout(sys.stderr):
        s40.check_config(config_file, fragments)
    config = s40.parse_config(config_file)
    for name in ('CONFIG_ARM64', 'CONFIG_KSU', 'CONFIG_NOMOUNT', 'CONFIG_LTO_NONE'):
        if config.get(name) != 'y':
            raise ValueError(f'Research config must enable {name}')
    for name in ('CONFIG_KSU_SUSFS', FLAG):
        if config.get(name, 'n') != 'n':
            raise ValueError(f'{name} must remain absent from the real config')
    return src, out, marker


def is_arm64_relocatable(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Missing or symlinked object: {path}')
    with path.open('rb') as source:
        header = source.read(64)
    if (len(header) != 64 or header[:6] != b'\x7fELF\x02\x01' or
            struct.unpack_from('<HH', header, 16) != (1, 183)):
        raise ValueError(f'Object is not little-endian AArch64 ET_REL: {path}')


def symbols(path: Path, nm: str = 'llvm-nm') -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for line in run([nm, str(path)]).splitlines():
        match = re.fullmatch(r'(?:[0-9a-fA-F]+)?\s*([A-Za-z?])\s+(\S+)', line.strip())
        if match:
            found.setdefault(match.group(2), set()).add(match.group(1))
    return found


def require_symbol(table: dict[str, set[str]], name: str, kind: str) -> None:
    if table.get(name) != {kind}:
        raise ValueError(f'Expected exactly {kind} for {name}, got {table.get(name)}')


def verify_objects(out: Path, *, nm: str = 'llvm-nm', ld: str = 'ld.lld',
                   readelf: str = 'readelf') -> dict:
    objects = {
        'sys': out / 'kernel/sys.o', 'ioprio': out / 'block/ioprio.o',
        'ksu_selinux': out / 'drivers/kernelsu/selinux/selinux.o',
        **{mode: out / path.replace('.c', '.o') for mode, path in OUTPUT_SOURCES.items()},
    }
    for obj in objects.values():
        is_arm64_relocatable(obj)
    for name in ('sys', 'ioprio'):
        require_symbol(symbols(objects[name], nm), 'susfs_is_priority_uid_filtered', 'U')
        relocations = run([readelf, '-Wr', str(objects[name])])
        calls = len(re.findall(r'\bR_AARCH64_CALL26\b[^\n]*\bsusfs_is_priority_uid_filtered\b', relocations))
        if calls != 2:
            raise ValueError(f'Expected two priority call relocations in {name}, got {calls}')
    selinux = symbols(objects['ksu_selinux'], nm)
    for name in ('setup_selinux', 'is_ksu_domain'):
        require_symbol(selinux, name, 'T')
    for mode in OUTPUT_SOURCES:
        table = symbols(objects[mode], nm)
        require_symbol(table, 'susfs_is_priority_uid_filtered', 'T')
        for name in ('setup_selinux', 'is_ksu_domain'):
            require_symbol(table, name, 'U')
    unresolved_counts = {}
    # A partial link resolves these three symbols only. It is NOT a complete
    # kernel link and must never be treated as a runnable or loadable object.
    with tempfile.TemporaryDirectory(prefix='s40-priority-partial-link-') as temp:
        for mode in OUTPUT_SOURCES:
            output = Path(temp) / f'{mode}-DO-NOT-LOAD.o'
            run([ld, '-r', '-o', str(output), *(str(objects[name]) for name in
                (mode, 'sys', 'ioprio', 'ksu_selinux'))])
            is_arm64_relocatable(output)
            linked = symbols(output, nm)
            for name in ('susfs_is_priority_uid_filtered', 'setup_selinux', 'is_ksu_domain'):
                require_symbol(linked, name, 'T')
            unresolved_counts[mode] = sum('U' in kinds for kinds in linked.values())
            if not unresolved_counts[mode]:
                raise ValueError('Unexpected fully resolved link; this is not a full kernel build')
    return {
        'scope': 'ARM64_SELECTED_OBJECTS_AND_PARTIAL_LINK_ONLY_DO_NOT_LOAD',
        'upstream_and_research_guarded_priority_fragments_compiled': True,
        'research_pending_candidate_also_compiled': True,
        'pending_candidate_failed_thread_start_race_fixed': False,
        'research_stalled_candidate_also_compiled': True,
        'stalled_candidate_guarantees_automatic_retry': False,
        'sys_and_ioprio_priority_call_relocations_each': 2,
        'three_selected_symbols_resolved_in_partial_link': True,
        'unresolved_other_symbols': unresolved_counts,
        'ksun_domain_adapter_runtime_equivalence_proven': False,
        'full_susfs_kernel_image_or_module_built': False,
        'device_syscalls_or_selinux_tested': False,
        'susfs_2_4_integrated_in_synthetica': False,
    }


def compile_probe(work: Path, jobs: int) -> dict:
    if not 1 <= jobs <= 8:
        raise ValueError('jobs must be between 1 and 8')
    src, out, marker = checked_work(work)
    env = os.environ.copy()
    env.update(ARCH='arm64', LLVM='1', KBUILD_BUILD_USER='synthetica',
               KBUILD_BUILD_HOST='research', KBUILD_BUILD_TIMESTAMP='2026-10-26 00:00:00 +0000',
               KBUILD_BUILD_VERSION='1')
    base = ['make', '-C', str(src), f'O={out}', 'HOSTCC=gcc', f'-j{jobs}']
    targets = tuple(path.replace('.c', '.o') for path in OUTPUT_SOURCES.values()) + (
        'kernel/sys.o', 'block/ioprio.o', 'drivers/kernelsu/selinux/selinux.o')
    # Force these exact research objects to be freshly compiled even on a
    # repeated invocation. checked_work() established that this is scratch
    # and contains no unexpected output symlinks.
    for target in targets:
        obj = out / target
        if obj.exists():
            if not obj.is_file():
                raise ValueError(f'Unexpected non-file output: {obj}')
            obj.unlink()
    run([*base, 'security/selinux/'], env=env, stream=True)
    run([*base, f'KCFLAGS=-D{FLAG}=1', *targets], env=env, stream=True)
    report = verify_objects(out)
    report['fragment_sha256'] = marker['fragment_sha256']
    report['compiler_version'] = run(['clang', '--version']).splitlines()[0]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('kernel', 'ksun', 'nomount', 'susfs', 'work'):
        prep.add_argument(f'--{name}', type=Path, required=True)
    compile_cmd = sub.add_parser('compile')
    compile_cmd.add_argument('--work', type=Path, required=True)
    compile_cmd.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(f'Prepared RESEARCH-ONLY source: {prepare(args.kernel, args.ksun, args.nomount, args.susfs, args.work)}')
    else:
        print(json.dumps(compile_probe(args.work, args.jobs), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
