#!/usr/bin/env python3
"""Isolated inspection of two files from one bounded EROFS payload.

The verified public AOSP host fsck.erofs runs with no token/network/caps in a
read-only chroot. Its extraction is confined to a size/inode-limited tmpfs;
only fixed-path hashes and ELF headers leave the namespace. ROM programs are
never executed or installed. Synthetic good and bad fixtures must pass first.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

FSCK_SHA256 = 'dd61160aa49a3d63da41ed2ff13e0e42be37d4a09a88f9d459002b2ca0cc2db7'
MKFS_SHA256 = 'b254640c783f9626b81b90d483c35d0e998c42113ba1259d1f3f5accfd0dc8e0'
MAX_INPUT = 256 * 1024**2
MAX_TOOL = 64 * 1024**2
MAX_LOG = 1024 * 1024


class ErofsAuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        while block := src.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def prepare_tools(archive: Path, sandbox: Path, host_libs: tuple[str, ...]) -> dict:
    """The archive's pinned identity is verified by the caller beforehand."""
    expected = {'bin/fsck.erofs': FSCK_SHA256, 'bin/mkfs.erofs': MKFS_SHA256}
    with zipfile.ZipFile(archive) as z:
        for name, digest in expected.items():
            rows = [i for i in z.infolist() if i.filename == name]
            if len(rows) != 1:
                raise ErofsAuditError('Missing or duplicate official EROFS tool')
            item = rows[0]
            if (item.is_dir() or item.flag_bits & 1 or not 0 < item.file_size <= MAX_TOOL or
                    stat.S_ISLNK(item.external_attr >> 16)):
                raise ErofsAuditError('Unsafe official EROFS tool archive entry')
            target = sandbox / 'tool' / Path(name).name
            with z.open(item) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            if sha256(target) != digest:
                raise ErofsAuditError('Official EROFS host tool digest mismatch')
            target.chmod(0o555)
            proc = subprocess.run(['readelf', '-d', str(target)], capture_output=True, text=True, check=True)
            needed = set(re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', proc.stdout))
            if needed != set(host_libs):
                raise ErofsAuditError('Unexpected EROFS host tool dependencies')
    (sandbox / 'input').mkdir()
    (sandbox / 'out').mkdir()
    return {'source': 'Android CI otatools build 16644040',
            'fsck_erofs_sha256': FSCK_SHA256, 'mkfs_erofs_sha256': MKFS_SHA256,
            'tool_probe_run': 41462548664, 'tool_probe_positive_negative_passed': True,
            'statement_signature_verified': False}


# The launcher runs only after unshare creates user, mount, PID and network
# namespaces. It remounts its root read-only, mounts a bounded tmpfs, drops all
# capabilities and sets no_new_privs. Only fixed file metadata crosses stdout.
_LAUNCHER = r'''
import ctypes, hashlib, json, os, resource, signal, stat, struct, subprocess, sys
root, mode = sys.argv[1:3]
if mode not in ('control', 'candidate'):
    raise RuntimeError('invalid audit mode')
subprocess.run(['/usr/bin/mount', '--make-rprivate', '/'], check=True)
subprocess.run(['/usr/bin/mount', '--bind', root, root], check=True)
subprocess.run(['/usr/bin/mount', '-o', 'remount,bind,ro', root], check=True)
try:
    fd = os.open(root + '/readonly-marker', os.O_WRONLY)
except OSError:
    pass
else:
    os.close(fd)
    raise RuntimeError('isolated root is not read-only')
subprocess.run(['/usr/bin/mount', '-t', 'tmpfs', '-o',
                'size=128m,nr_inodes=4096,mode=0700,nosuid,nodev,noexec',
                'tmpfs', root + '/out'], check=True)
os.chroot(root)
os.chdir('/')
if any(os.path.exists(x) for x in ('/proc', '/dev', '/home')):
    raise RuntimeError('unexpected host path in isolated root')
os.mkdir('/out/extracted', 0o700)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
libc = ctypes.CDLL(None, use_errno=True)
class Header(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class Data(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32),
                ('inheritable', ctypes.c_uint32)]
header = Header(0x20080522, 0)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'no_new_privs')
empty = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(empty)) != 0:
    raise OSError(ctypes.get_errno(), 'capset')
actual = (Data * 2)()
if libc.capget(ctypes.byref(header), ctypes.byref(actual)) != 0 or any(
        x.effective or x.permitted or x.inheritable for x in actual):
    raise RuntimeError('capabilities were not cleared')
os.closerange(3, 4096)
with open('/out/fsck.log', 'wb') as log:
    proc = subprocess.run(['/tool/fsck.erofs', '--no-xattrs', '--no-preserve',
                           '--extract=/out/extracted', '/input/payload.erofs'],
                          input=b'', stdout=log, stderr=log,
                          env={'PATH': '/empty', 'LANG': 'C',
                               'LD_LIBRARY_PATH': '/lib/x86_64-linux-gnu'}, timeout=75)
# No subprocess may race the fixed-path inspection; PID namespace limits kill.
try:
    os.kill(-1, signal.SIGKILL)
except ProcessLookupError:
    pass
with open('/out/fsck.log', 'rb') as f:
    log_data = f.read(32 * 1024 * 1024 + 1)
result = {'tool_exit_code': proc.returncode, 'tool_log_bytes': len(log_data),
          'tool_log_sha256': hashlib.sha256(log_data).hexdigest(), 'files': [],
          'root_read_only': True, 'tmpfs_bytes_limit': 128 * 1024 * 1024,
          'tmpfs_inode_limit': 4096, 'no_new_privs': True, 'capabilities_dropped': True}
if mode == 'control':
    result['synthetic_log'] = log_data[:8192].decode('utf-8', 'replace')
if proc.returncode == 0:
    try:
        binfd = os.open('/out/extracted/bin', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        binfd = None
    for name in ('linker', 'linker64'):
        row = {'path': '/bin/' + name}
        if binfd is None:
            row['status'] = 'missing_unreadable_or_symlink_parent'
            result['files'].append(row)
            continue
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=binfd)
        except OSError:
            row['status'] = 'missing_unreadable_or_symlink'
            result['files'].append(row)
            continue
        with os.fdopen(fd, 'rb') as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= 32 * 1024 * 1024:
                row['status'] = 'not_regular_or_oversized'
            else:
                h, prefix = hashlib.sha256(), b''
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    if len(prefix) < 64:
                        prefix = (prefix + data)[:64]
                    h.update(data)
                row.update(status='read', bytes=st.st_size, sha256=h.hexdigest())
                if len(prefix) >= 20 and prefix[:4] == b'\x7fELF' and prefix[5] == 1:
                    eclass, machine, etype = prefix[4], struct.unpack_from('<H', prefix, 18)[0], struct.unpack_from('<H', prefix, 16)[0]
                    row['elf'] = {'class': {1: 32, 2: 64}.get(eclass),
                                  'architecture': {40: 'ARM', 183: 'AArch64', 3: 'x86', 62: 'x86_64'}.get(machine, 'other'),
                                  'type': {1: 'relocatable', 2: 'executable', 3: 'dynamic', 4: 'core'}.get(etype, 'other')}
                else:
                    row['elf'] = None
        result['files'].append(row)
    if binfd is not None:
        os.close(binfd)
print(json.dumps(result), flush=True)
'''


def isolated_extract(sandbox: Path, image: Path, control: bool) -> dict:
    if not shutil.which('unshare') or not Path('/usr/bin/mount').is_file():
        raise ErofsAuditError('Required namespace or mount tools unavailable')
    if not image.is_file() or not 0 < image.stat().st_size <= MAX_INPUT:
        raise ErofsAuditError('EROFS payload exceeds input bounds')
    source_hash = sha256(image)
    destination = sandbox / 'input/payload.erofs'
    if destination.exists() or destination.is_symlink():
        raise ErofsAuditError('Unexpected existing EROFS sandbox input')
    shutil.copyfile(image, destination)
    destination.chmod(0o444)
    if sha256(destination) != source_hash:
        raise ErofsAuditError('EROFS sandbox copy digest mismatch')
    args = [shutil.which('unshare'), '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            sys.executable, '-I', '-S', '-c', _LAUNCHER, str(sandbox), 'control' if control else 'candidate']
    proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    try:
        out, err = proc.communicate(timeout=95)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise ErofsAuditError('Isolated EROFS check exceeded its time limit') from exc
    finally:
        destination.unlink(missing_ok=True)
    if len(out) + len(err) > MAX_LOG or proc.returncode:
        safe = err.decode('utf-8', 'replace')[:2000] if control else 'raw candidate diagnostic withheld'
        raise ErofsAuditError(f'Isolated EROFS launcher failed ({proc.returncode}): {safe}')
    try:
        result = json.loads(out)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ErofsAuditError('Invalid isolated EROFS metadata output') from exc
    result['input_sha256'] = source_hash
    return result


def run_controls(sandbox: Path, work: Path) -> list[dict]:
    """Stop before candidate access unless positive and malformed controls work."""
    root = work / 'erofs-synthetic'
    tree = root / 'tree/bin'
    tree.mkdir(parents=True)
    samples = {'linker': b'synthetic-32-bit-linker-only-data\n',
               'linker64': b'synthetic-64-bit-linker-only-data\n'}
    for name, data in samples.items():
        (tree / name).write_bytes(data)
    mkfs = sandbox / 'tool/mkfs.erofs'
    image = root / 'good.erofs'
    cmd = [shutil.which('unshare'), '--user', '--map-root-user', '--net', '--pid', '--fork',
           str(mkfs), str(image), str(root / 'tree')]
    proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=40, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    if proc.returncode or len(proc.stdout) + len(proc.stderr) > MAX_LOG:
        raise ErofsAuditError('Synthetic EROFS construction failed')
    good = isolated_extract(sandbox, image, control=True)
    expected = {f'/bin/{k}': hashlib.sha256(v).hexdigest() for k, v in samples.items()}
    got = {row['path']: row.get('sha256') for row in good.get('files', []) if row.get('status') == 'read'}
    if good['tool_exit_code'] != 0 or got != expected:
        raise ErofsAuditError(f'Synthetic EROFS positive control failed: {good}')
    bad = root / 'bad.erofs'
    bad.write_bytes(b'not an EROFS filesystem')
    negative = isolated_extract(sandbox, bad, control=True)
    if negative['tool_exit_code'] == 0:
        raise ErofsAuditError('Synthetic EROFS malformed control unexpectedly succeeded')
    # Raw logs and synthetic file hashes are unnecessary in final result.
    return [{'scenario': 'synthetic_valid', 'tool_exit_code': good['tool_exit_code'],
             'fixed_files_match': True},
            {'scenario': 'synthetic_malformed', 'tool_exit_code': negative['tool_exit_code'],
             'rejected': True}]
