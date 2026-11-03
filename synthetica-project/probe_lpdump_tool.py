#!/usr/bin/env python3
"""Cross-check LP metadata using a pinned, isolated, third-party lpdump prebuilt.

The prebuilt's source-to-binary provenance is NOT verified. It executes only
inside a read-only, network-isolated chroot with no inherited credentials or
capabilities. Synthetic positive and corrupted controls must pass. This is not
an official Android binary or a device/recovery/boot test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

import expand_product_lp as expand
import preflight_spatialflow as pre

BLOB = 'd90449a803e1bf3df2ebb5a2a466f89bbc3f29a4'
SHA256 = 'a7877918d01a98466d88980b2163756acd5926b602e97c2efb9e8de8a5a27a39'
SIZE = 5_440_440
COMMIT = '1e13871960cb71ceeba0c780c0878176ca665e53'

class LPToolError(RuntimeError): pass


def prepare(binary: Path, sandbox: Path) -> dict:
    if pre.digest_file(binary) != (SIZE, SHA256):
        raise LPToolError('Third-party lpdump binary SHA-256 or size mismatch')
    data = binary.read_bytes()
    git_blob = hashlib.sha1(f'blob {len(data)}\0'.encode('ascii') + data).hexdigest()
    if git_blob != BLOB:
        raise LPToolError('Third-party lpdump Git blob identity mismatch')
    readelf = subprocess.run(['readelf', '-h', '-l', str(binary)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=False, timeout=30)
    elf = readelf.stdout.decode('utf-8', 'replace')
    if (readelf.returncode or 'ELF64' not in elf or 'X86-64' not in elf.upper()
            or re.search(r'\bINTERP\b', elf)):
        raise LPToolError('lpdump is not the expected static x86-64 ELF')
    if sandbox.exists() or sandbox.is_symlink():
        raise LPToolError('Sandbox already exists')
    sandbox.mkdir(mode=0o700)
    (sandbox / 'tool').mkdir(); (sandbox / 'input').mkdir()
    target = sandbox / 'tool/lpdump'
    shutil.copyfile(binary, target); target.chmod(0o555)
    if pre.digest_file(target) != (SIZE, SHA256):
        raise LPToolError('Sandbox tool readback differs from pinned binary')
    (sandbox / 'readonly-marker').write_bytes(b'guard\n')
    return {'source': 'ravindu644/android-lptools-static-x86_64', 'source_commit': COMMIT,
            'git_blob_sha1': BLOB, 'bytes': SIZE, 'sha256': SHA256,
            'source_to_binary_provenance_verified': False,
            'isolated_without_network_or_capabilities': True}


def metadata_file(prefix: bytes, size: int, path: Path) -> None:
    if path.exists() or path.is_symlink() or size < len(prefix):
        raise LPToolError('Invalid synthetic or metadata-only image destination')
    with path.open('xb') as f:
        f.write(prefix)
        f.truncate(size)


_LAUNCHER = r'''
import ctypes, os, resource, subprocess, sys
root, mode, name, slot = sys.argv[1:]
if mode not in ('json', 'human') or not name.endswith('.img') or '/' in name or slot not in ('0', '1'):
    raise RuntimeError('invalid fixed lpdump arguments')
subprocess.run(['/usr/bin/mount', '--make-rprivate', '/'], check=True)
subprocess.run(['/usr/bin/mount', '--bind', root, root], check=True)
subprocess.run(['/usr/bin/mount', '-o', 'remount,bind,ro', root], check=True)
try:
    fd = os.open(root + '/readonly-marker', os.O_WRONLY)
except OSError:
    pass
else:
    os.close(fd)
    raise RuntimeError('read-only root verification failed')
os.chroot(root); os.chdir('/')
if any(os.path.exists(x) for x in ('/proc', '/dev', '/home')):
    raise RuntimeError('unexpected host path in isolated root')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
libc = ctypes.CDLL(None, use_errno=True)
class Header(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class Data(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32), ('inheritable', ctypes.c_uint32)]
header = Header(0x20080522, 0)
if libc.prctl(38, 1, 0, 0, 0) != 0: raise OSError(ctypes.get_errno(), 'no_new_privs')
empty = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(empty)) != 0: raise OSError(ctypes.get_errno(), 'capset')
actual = (Data * 2)()
if libc.capget(ctypes.byref(header), ctypes.byref(actual)) != 0 or any(x.effective or x.permitted or x.inheritable for x in actual):
    raise RuntimeError('capabilities were not cleared')
os.closerange(3, 4096)
args = ['/tool/lpdump'] + (['--json'] if mode == 'json' else []) + ['--slot=' + slot, '/input/' + name]
os.execve('/tool/lpdump', args, {'PATH': '/empty', 'LANG': 'C'})
'''


def isolated(sandbox: Path, image: Path, slot: int, mode: str) -> str:
    if (mode not in ('json', 'human') or slot not in (0, 1)
            or image.parent != sandbox / 'input' or not re.fullmatch(r'[A-Za-z0-9_.-]+\.img', image.name)):
        raise LPToolError('Invalid isolated lpdump input')
    unshare = shutil.which('unshare')
    if not unshare or not Path('/usr/bin/mount').is_file():
        raise LPToolError('Required namespace isolation is unavailable')
    args = [unshare, '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            sys.executable, '-I', '-S', '-c', _LAUNCHER, str(sandbox), mode, image.name, str(slot)]
    p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    try:
        out, err = p.communicate(timeout=75)
    except subprocess.TimeoutExpired as exc:
        os.killpg(p.pid, signal.SIGKILL); p.communicate()
        raise LPToolError('Isolated lpdump timed out') from exc
    if p.returncode or len(out) + len(err) > 4 * 1024 * 1024:
        raise LPToolError(f'Isolated lpdump failed (exit {p.returncode}): ' + err.decode('utf-8','replace')[:1200])
    return out.decode('utf-8', 'replace')


def read_sizes(sandbox: Path, image: Path, slot: int = 0) -> dict[str, int]:
    output = isolated(sandbox, image, slot, 'json')
    try:
        decoded = json.loads(output)
        parts = decoded['partitions']
        sizes = {p['name']: int(p['size']) for p in parts}
    except (ValueError, TypeError, KeyError) as exc:
        raise LPToolError('Isolated lpdump did not report partition sizes') from exc
    if len(sizes) != len(parts) or not sizes:
        raise LPToolError('Isolated lpdump reported no or duplicate partition names')
    return sizes


def parse_human_layout(text: str) -> dict[str, list[dict]]:
    section = text.split('Partition table:\n', 1)
    if len(section) != 2 or 'Super partition layout:' not in section[1]:
        raise LPToolError('lpdump human output has no bounded partition table')
    body = section[1].split('Super partition layout:', 1)[0]
    result = {}; current = None
    for line in body.splitlines():
        match = re.fullmatch(r'  Name: ([A-Za-z0-9_]+)', line)
        if match:
            current = match.group(1)
            if current in result: raise LPToolError('Duplicate partition in lpdump output')
            result[current] = []; continue
        match = re.fullmatch(r'    ([0-9]+) \.\. ([0-9]+) linear ([A-Za-z0-9_]+) ([0-9]+)', line)
        if match:
            if current is None: raise LPToolError('Extent appeared before a partition')
            a, b, device, physical = match.groups(); a, b, physical = int(a), int(b), int(physical)
            if b < a or device != 'super': raise LPToolError('Unsupported lpdump extent')
            result[current].append({'logical_start': a, 'sectors': b-a+1, 'physical_start': physical, 'device': device})
    if not result or any(not rows for rows in result.values()):
        raise LPToolError('lpdump did not report linear partition extents')
    return result


def read_layout(sandbox: Path, image: Path, slot: int = 0) -> dict[str, list[dict]]:
    return parse_human_layout(isolated(sandbox, image, slot, 'human'))


def probe(binary: Path, work: Path) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise LPToolError('Tool work directory must be empty')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
    from test_expand_product_lp import synthetic
    sandbox = work / 'sandbox'; info = prepare(binary, sandbox)
    before = synthetic(); after, plan = expand.build(before, 1_048_576, 64 * 1024)
    old_image, new_image, corrupt_image = (sandbox/'input'/x for x in ('old.img','new.img','corrupt.img'))
    metadata_file(before, 1_048_576, old_image); metadata_file(after, 1_048_576, new_image)
    corrupt = bytearray(before); corrupt[4096+10] ^= 1; corrupt[8192+10] ^= 1
    metadata_file(bytes(corrupt), 1_048_576, corrupt_image)
    old_sizes, new_sizes = read_sizes(sandbox, old_image), read_sizes(sandbox, new_image)
    old_layout, new_layout = read_layout(sandbox, old_image), read_layout(sandbox, new_image)
    if (len(old_layout.get('product', [])) != 1 or len(new_layout.get('product', [])) != 2
            or old_layout.get('system') != new_layout.get('system')):
        raise LPToolError('lpdump did not agree with the synthetic extent layout')
    if old_sizes != {'product': 8192, 'system': 8192} or new_sizes != {'product': 73728, 'system': 8192}:
        raise LPToolError('lpdump does not agree with the synthetic expected sizes')
    tail = new_layout['product'][1]
    if tail['physical_start'] * 512 != plan['product_new_extent']['start'] or tail['sectors'] * 512 != 64*1024:
        raise LPToolError('lpdump reported an unexpected synthetic added extent')
    try: read_sizes(sandbox, corrupt_image)
    except LPToolError: rejected = True
    else: rejected = False
    if not rejected: raise LPToolError('lpdump did not reject corrupted synthetic geometry')
    return {'schema': 'synthetica-lpdump-independent-control-v1', 'status': 'SYNTHETIC_CONTROLS_PASSED',
            'tool': info, 'before_partition_sizes': old_sizes, 'after_partition_sizes': new_sizes,
            'before_extent_layout': old_layout, 'after_extent_layout': new_layout, 'corrupted_geometry_rejected': True,
            'limitations': ['Third-party binary provenance is not authenticated.',
                            'Synthetic host controls do not prove device, recovery, AVB or boot compatibility.']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', required=True, type=Path); p.add_argument('--work', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    args = p.parse_args()
    try:
        result = probe(args.binary, args.work); args.report.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))
        return 0
    except (LPToolError, expand.LPExpandError, pre.PreflightError, OSError, ValueError) as exc:
        result = {'schema': 'synthetica-lpdump-independent-control-v1', 'status': 'FAILED_HOLD', 'error': str(exc)}
        args.report.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result), file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
