#!/usr/bin/env python3
"""Bounded package-name collision scan of ordinary preinstalled-app directories.

The Android APKs are treated as untrusted data by host aapt. This does not
inspect APEX payloads, overlay partitions, dynamic packages or runtime state.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess

import audit_vintf_candidate as vintf

ROOTS = {
    'system': ('/system/app', '/system/priv-app', '/app', '/priv-app'),
    'system_ext': ('/app', '/priv-app'),
    'product': ('/app', '/priv-app'),
}
MAX_APKS = 2500
MAX_APK_BYTES = 768 * 1024 * 1024
MAX_DEPTH = 12
CHUNK = 4 * 1024 * 1024

class PackageScanError(RuntimeError):
    pass


def parse_package(output: str) -> str:
    match = re.search(r"^package: name='([A-Za-z0-9_.]+)'(?: |$)", output, re.M)
    if not match or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', match.group(1)):
        raise PackageScanError('APK package name cannot be read safely')
    return match.group(1)


def scan(images: dict[str, Path], aapt: str, scratch: Path, forbidden_package: str) -> dict:
    if vintf.pytsk3 is None:
        raise PackageScanError('pytsk3 is required')
    if not scratch.is_dir() or any(scratch.iterdir()):
        raise PackageScanError('Package-scan scratch directory must be empty')
    if set(images) != set(ROOTS):
        raise PackageScanError('Expected system, system_ext and product images')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', forbidden_package):
        raise PackageScanError('Invalid target application package')
    checked, seen_paths, scanned_roots, missing_roots = 0, set(), [], []
    temporary = scratch / 'existing-package.apk'
    for partition, image in images.items():
        fs = vintf.pytsk3.FS_Info(vintf.pytsk3.Img_Info(str(image)))
        if fs.info.ftype != vintf.pytsk3.TSK_FS_TYPE_EXT4:
            raise PackageScanError('Expected ext4 filesystem')
        for root in ROOTS[partition]:
            try:
                rootfile = fs.open(path=root)
            except (RuntimeError, OSError, IOError):
                missing_roots.append(partition + ':' + root)
                continue
            meta = rootfile.info.meta
            if not meta or meta.type != vintf.pytsk3.TSK_FS_META_TYPE_DIR:
                raise PackageScanError('Application root is not a directory: ' + root)
            visited = set()
            stack = [(root, int(meta.addr), 0)]
            scanned_roots.append(partition + ':' + root)
            while stack:
                directory, inode, depth = stack.pop()
                if inode in visited or depth > MAX_DEPTH:
                    raise PackageScanError('Directory cycle or excessive depth in application root')
                visited.add(inode)
                for entry in fs.open_dir(inode=inode):
                    info, meta = entry.info.name, entry.info.meta
                    if not info or not info.name or not (info.flags & vintf.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
                        continue
                    name = bytes(info.name)
                    if name in (b'.', b'..'):
                        continue
                    if b'/' in name or b'\0' in name or meta is None:
                        raise PackageScanError('Unsafe filesystem entry in application root')
                    path = directory + '/' + name.decode('utf-8', 'surrogateescape')
                    if (partition, path) in seen_paths:
                        continue
                    seen_paths.add((partition, path))
                    if meta.type == vintf.pytsk3.TSK_FS_META_TYPE_DIR:
                        stack.append((path, int(meta.addr), depth + 1))
                    elif meta.type == vintf.pytsk3.TSK_FS_META_TYPE_REG and path.lower().endswith('.apk'):
                        checked += 1
                        if checked > MAX_APKS or not 0 < meta.size <= MAX_APK_BYTES:
                            raise PackageScanError('Application scan exceeds the APK count/size limit')
                        try:
                            with temporary.open('xb') as out:
                                offset = 0
                                while offset < meta.size:
                                    data = entry.read_random(offset, min(CHUNK, meta.size - offset))
                                    if not data or len(data) > meta.size - offset:
                                        raise PackageScanError('Could not read an existing APK completely')
                                    out.write(data)
                                    offset += len(data)
                            run = subprocess.run([aapt, 'dump', 'badging', str(temporary)], stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE, timeout=60, check=False)
                            if run.returncode or len(run.stdout) > 4 * 1024 * 1024:
                                raise PackageScanError('Could not inspect an existing APK package name: ' + partition + ':' + path)
                            package = parse_package(run.stdout.decode('utf-8', 'replace'))
                            if package == forbidden_package:
                                raise PackageScanError('Application package already exists: ' + partition + ':' + path)
                        finally:
                            temporary.unlink(missing_ok=True)
    if not checked or not scanned_roots:
        raise PackageScanError('No preinstalled APKs were found in the checked roots')
    return {'forbidden_package': forbidden_package, 'apks_checked': checked,
            'directories_scanned': scanned_roots, 'directories_missing': missing_roots,
            'collision_found_in_scanned_roots': False,
            'limitations': ['Only allocated APKs in the listed filesystem roots were scanned.',
                            'APEX payloads, symlink targets, ODM/vendor, dynamic packages and runtime were not scanned.']}
