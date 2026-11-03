#!/usr/bin/env python3
"""Validate pinned AOSP lpdump against synthetic original and expanded super metadata."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import zipfile

import audit_checkvintf_snapshot as reference
import expand_product_lp as expand
import preflight_spatialflow as pre

class LPToolError(RuntimeError): pass


def prepare(archive: Path, tool: Path) -> dict:
    if pre.digest_file(archive) != (reference.AOSP_ZIP_BYTES, reference.AOSP_ZIP_SHA256):
        raise LPToolError('Pinned official Android otatools archive identity mismatch')
    if tool.exists() or tool.is_symlink():
        raise LPToolError('Tool output already exists')
    with zipfile.ZipFile(archive) as z:
        matches = [i for i in z.infolist() if i.filename == 'bin/lpdump']
        if len(matches) != 1:
            names = [i.filename for i in z.infolist() if 'lpdump' in i.filename.lower() or 'lpmake' in i.filename.lower()]
            raise LPToolError('Pinned otatools lacks exactly one bin/lpdump: ' + json.dumps(names[:30]))
        info = matches[0]
        if info.is_dir() or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16) or not 0 < info.file_size <= 64 * 1024**2:
            raise LPToolError('Unexpected lpdump ZIP member')
        with z.open(info) as src, tool.open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    tool.chmod(0o555)
    size, sha = pre.digest_file(tool)
    return {'aosp_build': reference.AOSP_BUILD, 'otatools_sha256': reference.AOSP_ZIP_SHA256,
            'lpdump_bytes': size, 'lpdump_sha256': sha,
            'in_toto_statement_signature_verified': False}


def metadata_file(prefix: bytes, size: int, path: Path) -> None:
    if path.exists() or path.is_symlink() or size < len(prefix):
        raise LPToolError('Invalid synthetic or metadata-only image destination')
    with path.open('xb') as f:
        f.write(prefix)
        f.truncate(size)


def read_sizes(tool: Path, image: Path, slot: int = 0) -> dict[str, int]:
    proc = subprocess.run([str(tool), '--json', f'--slot={slot}', str(image)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, timeout=60, check=False)
    if proc.returncode or len(proc.stdout) > 4 * 1024 * 1024:
        raise LPToolError('AOSP lpdump did not return bounded JSON (exit ' + str(proc.returncode) +
                          '): ' + proc.stderr.decode('utf-8', 'replace')[:1000])
    try:
        decoded = json.loads(proc.stdout)
        parts = decoded['partitions']
        sizes = {p['name']: int(p['size']) for p in parts}
    except (ValueError, TypeError, KeyError) as exc:
        raise LPToolError('AOSP lpdump did not report partition sizes') from exc
    if len(sizes) != len(parts) or not sizes:
        raise LPToolError('AOSP lpdump reported no or duplicate partition names')
    return sizes


def probe(archive: Path, work: Path) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise LPToolError('Tool work directory must be empty')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
    from test_expand_product_lp import synthetic
    tool = work / 'lpdump'
    info = prepare(archive, tool)
    before = synthetic()
    after, _ = expand.build(before, 1_048_576, 64 * 1024)
    old_image, new_image, corrupt_image = work/'old.img', work/'new.img', work/'corrupt.img'
    metadata_file(before, 1_048_576, old_image)
    metadata_file(after, 1_048_576, new_image)
    corrupt = bytearray(before)
    corrupt[4096+10] ^= 1; corrupt[8192+10] ^= 1
    metadata_file(bytes(corrupt), 1_048_576, corrupt_image)
    old_sizes = read_sizes(tool, old_image)
    new_sizes = read_sizes(tool, new_image)
    if old_sizes != {'product': 8192, 'system': 8192} or new_sizes != {'product': 73728, 'system': 8192}:
        raise LPToolError('AOSP lpdump does not agree with the synthetic expected sizes')
    try:
        read_sizes(tool, corrupt_image)
    except LPToolError:
        rejected = True
    else:
        rejected = False
    if not rejected:
        raise LPToolError('AOSP lpdump did not reject the corrupted synthetic geometry')
    return {'schema': 'synthetica-lpdump-independent-control-v1', 'status': 'SYNTHETIC_CONTROLS_PASSED',
            'tool': info, 'before_partition_sizes': old_sizes, 'after_partition_sizes': new_sizes,
            'corrupted_geometry_rejected': True,
            'limitations': ['Synthetic host controls do not prove device, recovery, AVB or boot compatibility.']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True, type=Path); p.add_argument('--work', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    args = p.parse_args()
    try:
        result = probe(args.archive, args.work); args.report.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))
        return 0
    except (LPToolError, expand.LPExpandError, OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        result = {'schema': 'synthetica-lpdump-independent-control-v1', 'status': 'FAILED_HOLD', 'error': str(exc)}
        args.report.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result), file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
