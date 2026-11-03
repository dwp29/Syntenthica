#!/usr/bin/env python3
"""Diagnose aapt failure on the pinned ROM Shell APK, read-only and without upload.

Reconstructs the already-verified candidate 03 in a disposable directory,
checks its full super stream and system extent, and runs host manifest readers
on one bounded copy. Reports only APK hashes and small tool diagnostics; no
APK, device data, or modified ROM is published by this script.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import audit_vintf_candidate as vintf
import preflight_spatialflow as pre

APK_PATH = '/system/priv-app/Shell/Shell.apk'
MAX_APK = 128 * 1024 * 1024
MAX_MANIFEST = 8 * 1024 * 1024
CHUNK = 4 * 1024 * 1024

class ProbeError(RuntimeError):
    pass


def excerpt(text: bytes) -> str:
    # Prevent terminal controls or giant tool output from entering check metadata.
    return ''.join(c if 32 <= ord(c) < 127 or c in '\n\t' else '?' for c in text.decode('utf-8', 'replace'))[:1200]


def tool_result(args: list[str]) -> dict:
    env = {k: v for k, v in os.environ.items() if not re.search(r'(TOKEN|SECRET|PASSWORD|CREDENTIAL)', k, re.I)}
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'exit': None, 'error': type(exc).__name__}
    output = p.stdout[:4 * 1024 * 1024]
    lines = output.decode('utf-8', 'replace').splitlines()
    selected = [line for line in lines if re.search(r"(^package:|\bmanifest\b|\bpackage[=(])", line, re.I)][:8]
    return {'exit': p.returncode, 'stdout_bytes': len(p.stdout), 'stderr_bytes': len(p.stderr),
            'stdout_selected': excerpt('\n'.join(selected).encode()),
            'stderr': excerpt(p.stderr)}


def extract_apk(image: Path, output: Path) -> tuple[int, str]:
    if vintf.pytsk3 is None:
        raise ProbeError('Pinned pytsk3 reader unavailable')
    disk = vintf.pytsk3.Img_Info(str(image)); fs = vintf.pytsk3.FS_Info(disk)
    if fs.info.ftype != vintf.pytsk3.TSK_FS_TYPE_EXT4:
        raise ProbeError('System extent is not ext4')
    file = fs.open(path=APK_PATH)
    meta = file.info.meta
    if meta is None or meta.type != vintf.pytsk3.TSK_FS_META_TYPE_REG or not 0 < meta.size <= MAX_APK:
        raise ProbeError('Shell APK is not a bounded regular file')
    h = hashlib.sha256(); offset = 0
    with output.open('xb') as out:
        while offset < meta.size:
            data = file.read_random(offset, min(CHUNK, meta.size - offset))
            if not data or len(data) > meta.size - offset:
                raise ProbeError('Shell APK could not be read completely')
            out.write(data); h.update(data); offset += len(data)
    if pre.digest_file(output) != (offset, h.hexdigest()):
        raise ProbeError('Extracted APK readback mismatch')
    return offset, h.hexdigest()


def inspect_archive(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist(); names = [x.filename for x in infos]
            if names.count('AndroidManifest.xml') != 1 or len(infos) > 100_000:
                raise ProbeError('APK has no unique manifest or too many entries')
            manifest = z.getinfo('AndroidManifest.xml')
            if not 0 < manifest.file_size <= MAX_MANIFEST:
                raise ProbeError('APK manifest has unexpected size')
            data = z.read(manifest)  # ZIP implementation verifies the manifest CRC.
            return {'entries': len(infos), 'duplicate_names': len(names) - len(set(names)),
                    'manifest_bytes': len(data), 'manifest_sha256': hashlib.sha256(data).hexdigest(),
                    'manifest_first_8_bytes_hex': data[:8].hex()}
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ProbeError('Shell APK ZIP/manifest validation failed: ' + type(exc).__name__) from exc


def run(work: Path, aapt: str, aapt2: str, apkanalyzer: str | None) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise ProbeError('Work directory must be empty')
    source = pre.download_candidate(work)
    lock = json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text())
    specs = vintf.part_specs(lock)
    system = work/'system.img'
    with zipfile.ZipFile(source) as z, z.open('super.img') as stream, system.open('xb') as out:
        prefix = stream.read(vintf.lp.MAX_PREFIX)
        windows = vintf.extent_windows(prefix, vintf.SUPER_BYTES, specs)
        vintf.copy_windows(stream, prefix, windows, {'system': out}, vintf.SUPER_BYTES, pre.SUPER_SHA256)
    if pre.digest_file(system) != (windows['system']['bytes'], windows['system']['sha256']):
        raise ProbeError('System extent readback mismatch')
    apk = work/'shell.apk'; size, sha = extract_apk(system, apk)
    archive = inspect_archive(apk)
    tools = {
        'aapt_badging': tool_result([aapt, 'dump', 'badging', str(apk)]),
        'aapt_xmltree': tool_result([aapt, 'dump', 'xmltree', str(apk), 'AndroidManifest.xml']),
        'aapt2_badging': tool_result([aapt2, 'dump', 'badging', str(apk)]),
        'aapt2_xmltree': tool_result([aapt2, 'dump', 'xmltree', '--file', 'AndroidManifest.xml', str(apk)]),
    }
    if apkanalyzer:
        tools['apkanalyzer_application_id'] = tool_result([apkanalyzer, 'manifest', 'application-id', str(apk)])
    if pre.digest_file(source) != (pre.SOURCE_SIZE, pre.SOURCE_SHA256) or pre.digest_file(apk) != (size, sha):
        raise ProbeError('Verified input changed during diagnosis')
    return {'status': 'READ_ONLY_DIAGNOSTIC_COMPLETED_HOLD', 'apk_path': 'system:' + APK_PATH,
            'apk_bytes': size, 'apk_sha256': sha, 'archive': archive, 'tools': tools,
            'source_candidate03_sha256': pre.SOURCE_SHA256,
            'limitations': ['Host tool output does not prove app/runtime validity or device safety.',
                            'No APK, image, ZIP or device was modified or published.']}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', required=True, type=Path); p.add_argument('--report', required=True, type=Path)
    p.add_argument('--aapt', required=True); p.add_argument('--aapt2', required=True); p.add_argument('--apkanalyzer')
    args = p.parse_args()
    try:
        result = run(args.work, args.aapt, args.aapt2, args.apkanalyzer); code = 0
    except (ProbeError, pre.PreflightError, vintf.VintfAuditError, OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {'status': 'DIAGNOSTIC_FAILED_HOLD', 'error': str(exc), 'device_modified': False}; code = 1
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, separators=(',', ':')), flush=True)
    return code

if __name__ == '__main__': sys.exit(main())
