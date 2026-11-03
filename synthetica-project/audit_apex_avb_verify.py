#!/usr/bin/env python3
"""Host-only verification of a copied APEX payload with a pinned AOSP avbtool.

Synthetic positive and corrupt controls must pass first. The verifier runs with
no network or host filesystem, in a read-only chroot with a bounded tmpfs and
no capabilities. Verification uses the payload's own key: it cannot establish
who signed the APEX, outer APK signing, device AVB trust, activation, or boot.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
from pathlib import Path

AVB_TOOL_SHA256 = 'e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b'
AVB_REVISION = '761178607206f4cb2af79ed9eec52d8cbd814adb'
MAX_INPUT = 256 * 1024 * 1024
MAX_OUTPUT = 1024 * 1024


class AvbProbeError(RuntimeError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def prepare(sandbox: Path, avbtool: Path) -> dict:
    if avbtool.is_symlink() or not avbtool.is_file() or digest(avbtool) != AVB_TOOL_SHA256:
        raise AvbProbeError('AOSP avbtool source digest mismatch')
    tool = sandbox / 'tool/avbtool.py'
    shutil.copyfile(avbtool, tool)
    tool.chmod(0o444)
    openssl = Path('/usr/bin/openssl')
    if not openssl.is_file():
        raise AvbProbeError('Host OpenSSL unavailable')
    target = sandbox / 'tool/openssl'
    shutil.copyfile(openssl, target)
    target.chmod(0o555)
    libs = {}
    for name in ('libssl.so.3', 'libcrypto.so.3'):
        source = Path('/lib/x86_64-linux-gnu') / name
        if not source.is_file():
            raise AvbProbeError('Required host OpenSSL library unavailable')
        dest = sandbox / 'lib/x86_64-linux-gnu' / name
        shutil.copyfile(source, dest)
        dest.chmod(0o444)
        libs[name] = digest(dest)
    (sandbox / 'tool/openssl.cnf').write_bytes(b'')
    (sandbox / 'input-avb').mkdir()
    return {'avbtool_revision': AVB_REVISION, 'avbtool_sha256': AVB_TOOL_SHA256,
            'openssl_sha256': digest(target), 'openssl_host_libraries_sha256': libs,
            'public_source_signature_verified': False}


# Modules used by the pinned script and Python's tempfile machinery are
# imported before chroot. The only executable after chroot is the copied host
# OpenSSL, never anything from the APEX. Chroot contains no /dev, /proc or home.
_LAUNCHER = r'''
import argparse, binascii, bisect, contextlib, ctypes, hashlib, io, json, math, os
import random, resource, signal, struct, subprocess, sys, tempfile, time
root = sys.argv[1]
with open(root + '/tool/avbtool.py', 'rb') as f:
    source = f.read()
if hashlib.sha256(source).hexdigest() != 'e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b':
    raise RuntimeError('avbtool digest changed')
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
                'size=32m,nr_inodes=1024,mode=0700,nosuid,nodev,noexec',
                'tmpfs', root + '/out'], check=True)
os.chroot(root)
os.chdir('/')
if any(os.path.exists(x) for x in ('/proc', '/dev', '/home')):
    raise RuntimeError('unexpected host paths in isolated root')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
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
os.environ.clear()
os.environ.update(PATH='/tool', LANG='C', TMPDIR='/out', OPENSSL_CONF='/tool/openssl.cnf',
                  LD_LIBRARY_PATH='/lib/x86_64-linux-gnu')
tempfile.tempdir = '/out'
os.closerange(3, 4096)
namespace = {'__name__': 'pinned_avbtool', '__file__': '/tool/avbtool.py'}
exec(compile(source, '/tool/avbtool.py', 'exec'), namespace)
result = {'payload_signature_and_hashtree_verified_with_embedded_key': False,
          'root_read_only': True, 'tmpfs_bytes_limit': 32 * 1024 * 1024,
          'no_new_privs': True, 'capabilities_dropped': True,
          'signer_identity_or_trust_verified': False}
log = io.StringIO()
try:
    avb = namespace['Avb']()
    image = namespace['ImageHandler']('/input-avb/payload.img', read_only=True)
    footer, hdr, descriptors, _ = avb._parse_image(image)
    if footer is None or hdr.flags != 0:
        raise RuntimeError('missing footer or nonzero AVB flags')
    _, algorithm = namespace['lookup_algorithm_by_type'](hdr.algorithm_type)
    if not algorithm.hash_name or not hdr.signature_size or not hdr.public_key_size:
        raise RuntimeError('unsigned vbmeta is not accepted as a signature check')
    trees = [d for d in descriptors if isinstance(d, namespace['AvbHashtreeDescriptor'])]
    if len(trees) != 1 or not trees[0].root_digest:
        raise RuntimeError('expected exactly one anchored hashtree')
    if any(getattr(d, 'partition_name', '') for d in descriptors):
        raise RuntimeError('external partition descriptor refused')
    if any(isinstance(d, namespace['AvbChainPartitionDescriptor']) for d in descriptors):
        raise RuntimeError('chained partition descriptor refused')
    if trees[0].hash_algorithm not in ('sha256', 'sha512'):
        raise RuntimeError('unrecognized hashtree hash algorithm')
    expected = {'sha256': 32, 'sha512': 64}[trees[0].hash_algorithm]
    if len(trees[0].root_digest) != expected:
        raise RuntimeError('unexpected hashtree digest length')
    tree = trees[0]
    image_length = os.stat('/input-avb/payload.img').st_size
    if (tree.data_block_size != 4096 or tree.hash_block_size != 4096
            or not 0 < tree.image_size <= image_length or tree.image_size % 4096
            or not 0 < tree.tree_size <= image_length
            or tree.tree_offset < tree.image_size
            or tree.tree_offset > image_length or tree.tree_size > image_length - tree.tree_offset):
        raise RuntimeError('unbounded or unexpected hashtree layout')
    result.update(vbmeta_algorithm_type=hdr.algorithm_type, avb_flags=hdr.flags,
                  hashtree_algorithm=trees[0].hash_algorithm,
                  hashtree_root_digest_present=True, hashtree_count=len(trees))
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        avb.verify_image('/input-avb/payload.img', None, None, False, False)
    result['payload_signature_and_hashtree_verified_with_embedded_key'] = True
    result['verification_exit_code'] = 0
except Exception as exc:
    result['verification_exit_code'] = 1
    result['error_type'] = type(exc).__name__
output = log.getvalue().encode('utf-8', 'replace')
result['tool_output_bytes'] = len(output)
result['tool_output_sha256'] = hashlib.sha256(output).hexdigest()
print(json.dumps(result), flush=True)
'''


def verify_isolated(sandbox: Path, image: Path) -> dict:
    if not shutil.which('unshare') or not Path('/usr/bin/mount').is_file():
        raise AvbProbeError('Required user, mount and network isolation unavailable')
    if image.is_symlink() or not image.is_file() or not 0 < image.stat().st_size <= MAX_INPUT:
        raise AvbProbeError('AVB input is missing or outside bounded size')
    source = digest(image)
    dest = sandbox / 'input-avb/payload.img'
    if dest.exists() or dest.is_symlink():
        raise AvbProbeError('Unexpected existing AVB sandbox input')
    shutil.copyfile(image, dest)
    dest.chmod(0o444)
    if digest(dest) != source:
        raise AvbProbeError('AVB sandbox copy differs from input')
    args = [shutil.which('unshare'), '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            sys.executable, '-I', '-S', '-c', _LAUNCHER, str(sandbox)]
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    try:
        out, err = process.communicate(timeout=150)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise AvbProbeError('AVB isolated verifier timed out') from exc
    finally:
        dest.unlink(missing_ok=True)
    if process.returncode or len(out) + len(err) > MAX_OUTPUT:
        raise AvbProbeError(f'AVB isolated launcher failed ({process.returncode}); raw diagnostics withheld')
    try:
        result = json.loads(out)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AvbProbeError('Invalid AVB isolated result') from exc
    if (not isinstance(result, dict) or result.get('root_read_only') is not True
            or result.get('no_new_privs') is not True or result.get('capabilities_dropped') is not True
            or result.get('signer_identity_or_trust_verified') is not False
            or type(result.get('payload_signature_and_hashtree_verified_with_embedded_key')) is not bool
            or result.get('verification_exit_code') != (0 if result['payload_signature_and_hashtree_verified_with_embedded_key'] else 1)):
        raise AvbProbeError('AVB isolated result does not meet integrity checks')
    result['input_sha256'] = source
    return result


def run_controls(sandbox: Path, work: Path, avbtool: Path) -> list[dict]:
    """Create a disposable signed fixture and prove data corruption is rejected."""
    root = work / 'avb-synthetic'
    root.mkdir()
    key, image = root / 'ephemeral-test-key.pem', root / 'fixture.img'
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C'}
    try:
        subprocess.run(['/usr/bin/openssl', 'genrsa', '-out', str(key), '2048'], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, env=environment)
        image.write_bytes(b'synthetic VNDK fixture\n' + b'\0' * (1024 * 1024 - 23))
        subprocess.run([sys.executable, '-I', '-S', str(avbtool), 'add_hashtree_footer', '--image', str(image),
                        '--partition_size', str(4 * 1024 * 1024), '--partition_name', '',
                        '--algorithm', 'SHA256_RSA2048', '--key', str(key), '--hash_algorithm', 'sha256',
                        '--salt', '00' * 32, '--do_not_generate_fec'], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, env=environment)
    finally:
        # The throwaway synthetic signing key is never used on a ROM or persisted.
        key.unlink(missing_ok=True)
    valid_hash = digest(image)
    positive = verify_isolated(sandbox, image)
    if positive.get('payload_signature_and_hashtree_verified_with_embedded_key') is not True:
        raise AvbProbeError(f'AVB positive synthetic control failed: {positive}')
    with image.open('r+b') as f:
        first = f.read(1)
        f.seek(0)
        f.write(bytes([first[0] ^ 1]))
    negative = verify_isolated(sandbox, image)
    if negative.get('payload_signature_and_hashtree_verified_with_embedded_key') is not False:
        raise AvbProbeError('AVB corrupt data synthetic control unexpectedly passed')
    with image.open('r+b') as f:
        f.write(first)
    if digest(image) != valid_hash:
        raise AvbProbeError('Synthetic fixture restoration failed')
    # AVB's signature offset is relative to the authentication block.
    from audit_vndk_apex import HEADER_FORMAT
    with image.open('r+b') as f:
        f.seek(-64, 2)
        footer = struct.unpack('>4sIIQQQ28s', f.read(64))
        offset = footer[4]
        f.seek(offset)
        header = struct.unpack(HEADER_FORMAT, f.read(256))
        signature_offset, signature_size = header[8], header[9]
        if footer[0] != b'AVBf' or header[0] != b'AVB0' or not signature_size:
            raise AvbProbeError('Unexpected synthetic signed fixture structure')
        f.seek(offset + 256 + signature_offset + signature_size // 2)
        byte = f.read(1)
        f.seek(-1, 1)
        f.write(bytes([byte[0] ^ 1]))
    invalid_signature = verify_isolated(sandbox, image)
    if invalid_signature.get('payload_signature_and_hashtree_verified_with_embedded_key') is not False:
        raise AvbProbeError('AVB corrupt signature synthetic control unexpectedly passed')
    unsigned = root / 'unsigned.img'
    unsigned.write_bytes(b'\0' * (1024 * 1024))
    subprocess.run([sys.executable, '-I', '-S', str(avbtool), 'add_hashtree_footer', '--image', str(unsigned),
                    '--partition_size', str(4 * 1024 * 1024), '--partition_name', '', '--algorithm', 'NONE',
                    '--hash_algorithm', 'sha256', '--salt', '00' * 32, '--do_not_generate_fec'],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   timeout=60, env=environment)
    invalid_unsigned = verify_isolated(sandbox, unsigned)
    if invalid_unsigned.get('payload_signature_and_hashtree_verified_with_embedded_key') is not False:
        raise AvbProbeError('AVB unsigned synthetic control unexpectedly passed')
    return [{'scenario': 'synthetic_valid_signed_hashtree', 'verification_exit_code': positive['verification_exit_code']},
            {'scenario': 'synthetic_corrupted_payload', 'verification_exit_code': negative['verification_exit_code'], 'rejected': True},
            {'scenario': 'synthetic_corrupted_signature', 'verification_exit_code': invalid_signature['verification_exit_code'], 'rejected': True},
            {'scenario': 'synthetic_unsigned', 'verification_exit_code': invalid_unsigned['verification_exit_code'], 'rejected': True}]
