#!/usr/bin/env python3
"""Bounded package-name collision scan of ordinary preinstalled-app directories.

Existing APKs are data, not executed. If aapt badging cannot resolve a label,
independent aapt and aapt2 XML-tree readers must both agree on the manifest
package. No fallback is allowed for a timeout, malformed/ambiguous manifest,
duplicate manifest member, tool crash, or disagreement. APEX, symlink targets,
ODM/vendor, dynamic packages and runtime state are outside this bounded scan.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import zipfile
import zlib

import audit_vintf_candidate as vintf

ROOTS = {
    'system': ('/system/app', '/system/priv-app', '/app', '/priv-app'),
    'system_ext': ('/app', '/priv-app'),
    'product': ('/app', '/priv-app'),
}
MAX_APKS = 2500
MAX_APK_BYTES = 768 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
MAX_OUTPUT = 4 * 1024 * 1024
MAX_DEPTH = 12
CHUNK = 4 * 1024 * 1024
PACKAGE_RE = r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+'

class PackageScanError(RuntimeError):
    pass


def parse_package(output: str) -> str:
    matches = re.findall(r"^package: name='([A-Za-z0-9_.]+)'(?: |$)", output, re.M)
    if len(matches) != 1 or not re.fullmatch(PACKAGE_RE, matches[0]):
        raise PackageScanError('APK package name cannot be read safely')
    return matches[0]


def parse_xmltree_package(output: str) -> str:
    """Read only the unnamespaced package attribute of the root manifest node."""
    root_found = False
    package = []
    for line in output.splitlines():
        element = re.match(r'^(\s*)E:\s+(\S+)(?:\s|$)', line)
        if element:
            if not root_found:
                if element.group(2) != 'manifest':
                    raise PackageScanError('Manifest XML tree has an unexpected root')
                root_found = True
                continue
            break  # Root attributes must be printed before the first child element.
        if not root_found:
            continue
        attribute = re.match(r'^\s+A:\s+package(?:\(0x[0-9a-fA-F]+\))?="([^"]*)"(?:\s+\(Raw:\s+"([^"]*)"\))?\s*$', line)
        if attribute:
            value, raw = attribute.groups()
            if raw is not None and raw != value:
                raise PackageScanError('Manifest package raw and displayed values differ')
            package.append(value)
        elif re.match(r'^\s+A:\s+package(?:\(|=)', line):
            raise PackageScanError('Manifest package attribute format is unsupported')
    if not root_found or len(package) != 1 or not re.fullmatch(PACKAGE_RE, package[0]):
        raise PackageScanError('Manifest root package is absent or ambiguous')
    return package[0]


def check_manifest_archive(apk: Path) -> None:
    try:
        with zipfile.ZipFile(apk) as z:
            infos = z.infolist()
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                raise PackageScanError('Existing APK has too many archive entries')
            manifests = [i for i in infos if i.filename == 'AndroidManifest.xml']
            if len(manifests) != 1 or not 0 < manifests[0].file_size <= MAX_MANIFEST_BYTES:
                raise PackageScanError('Existing APK lacks one bounded manifest')
            if len(z.read(manifests[0])) != manifests[0].file_size:  # read checks ZIP CRC
                raise PackageScanError('Existing APK manifest is incomplete')
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError, EOFError, zlib.error) as exc:
        raise PackageScanError('Existing APK ZIP/manifest cannot be checked') from exc


def _tool_digest(path: str) -> str:
    tool = Path(path)
    if not tool.is_file() or not os.access(tool, os.X_OK) or not 0 < tool.stat().st_size <= 128 * 1024 * 1024:
        raise PackageScanError('A required Android host reader is missing or not executable')
    h = hashlib.sha256()
    with tool.open('rb') as f:
        while data := f.read(CHUNK):
            h.update(data)
    return h.hexdigest()


def _run_tool(args: list[str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if not re.search(r'(TOKEN|SECRET|PASSWORD|CREDENTIAL|KEYSTORE)', k, re.I)}
    env['LC_ALL'] = 'C'
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PackageScanError('APK inspection tool could not run or timed out') from exc
    if result.returncode < 0 or len(result.stdout) > MAX_OUTPUT or len(result.stderr) > MAX_OUTPUT:
        raise PackageScanError('APK inspection tool crashed or exceeded its output bound')
    return result


def _diagnostic(text: bytes) -> str:
    return ''.join(c if 32 <= ord(c) < 127 else ' ' for c in text.decode('utf-8', 'replace'))[:350].strip()


def package_from_apk(apk: Path, aapt: str, aapt2: str) -> tuple[str, str]:
    check_manifest_archive(apk)
    badging = _run_tool([aapt, 'dump', 'badging', str(apk)])
    if badging.returncode == 0:
        return parse_package(badging.stdout.decode('utf-8', 'replace')), 'aapt_badging'
    # Badging may fail later on unresolved labels after printing a valid package.
    # Never accept its partial output alone; two full XML readers must agree.
    xml1 = _run_tool([aapt, 'dump', 'xmltree', str(apk), 'AndroidManifest.xml'])
    xml2 = _run_tool([aapt2, 'dump', 'xmltree', '--file', 'AndroidManifest.xml', str(apk)])
    if xml1.returncode or xml2.returncode:
        raise PackageScanError('Both manifest XML readers did not succeed; aapt badging: ' + _diagnostic(badging.stderr))
    first = parse_xmltree_package(xml1.stdout.decode('utf-8', 'replace'))
    second = parse_xmltree_package(xml2.stdout.decode('utf-8', 'replace'))
    if first != second:
        raise PackageScanError('Independent APK manifest readers disagree')
    partial = badging.stdout.decode('utf-8', 'replace')
    if re.search(r'^package: name=', partial, re.M) and parse_package(partial) != first:
        raise PackageScanError('Partial badging and manifest readers disagree')
    return first, 'aapt_and_aapt2_xmltree'


def scan(images: dict[str, Path], aapt: str, scratch: Path, forbidden_package: str, *,
         aapt2: str | None = None, watch_packages: set[str] | None = None) -> dict:
    if vintf.pytsk3 is None:
        raise PackageScanError('pytsk3 is required')
    if not scratch.is_dir() or any(scratch.iterdir()):
        raise PackageScanError('Package-scan scratch directory must be empty')
    if set(images) != set(ROOTS):
        raise PackageScanError('Expected system, system_ext and product images')
    if not re.fullmatch(PACKAGE_RE, forbidden_package):
        raise PackageScanError('Invalid target application package')
    if watch_packages is None:
        watch_packages = set()
    if (not isinstance(watch_packages, set) or len(watch_packages) > 64
            or any(not isinstance(name, str) or not re.fullmatch(PACKAGE_RE, name) for name in watch_packages)):
        raise PackageScanError('Watched package set is invalid or exceeds its bound')
    watched = {name: [] for name in sorted(watch_packages)}
    if aapt2 is None:
        aapt2 = str(Path(aapt).with_name('aapt2'))
    tool_hashes = {'aapt_sha256': _tool_digest(aapt), 'aapt2_sha256': _tool_digest(aapt2)}
    if os.path.samefile(aapt, aapt2) or tool_hashes['aapt_sha256'] == tool_hashes['aapt2_sha256']:
        raise PackageScanError('Manifest readers are not distinct executables')
    checked, seen_paths, scanned_roots, missing_roots, fallback_paths = 0, set(), [], [], []
    temporary = scratch / 'existing-package.apk'
    for partition, image in images.items():
        disk = vintf.pytsk3.Img_Info(str(image))
        fs = vintf.pytsk3.FS_Info(disk)
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
                            try:
                                package, method = package_from_apk(temporary, aapt, aapt2)
                            except PackageScanError as exc:
                                raise PackageScanError('Could not inspect existing APK '+partition+':'+path+': '+str(exc)) from exc
                            if method != 'aapt_badging':
                                fallback_paths.append(partition+':'+path)
                            if package == forbidden_package:
                                raise PackageScanError('Application package already exists: ' + partition + ':' + path)
                            if package in watched:
                                h = hashlib.sha256()
                                with temporary.open('rb') as f:
                                    while data := f.read(CHUNK):
                                        h.update(data)
                                watched[package].append({'partition': partition, 'path': path, 'bytes': offset,
                                                         'sha256': h.hexdigest(), 'manifest_reader': method})
                        finally:
                            temporary.unlink(missing_ok=True)
    if not checked or not scanned_roots:
        raise PackageScanError('No preinstalled APKs were found in the checked roots')
    if tool_hashes != {'aapt_sha256': _tool_digest(aapt), 'aapt2_sha256': _tool_digest(aapt2)}:
        raise PackageScanError('A host reader changed during package scanning')
    return {'forbidden_package': forbidden_package, 'apks_checked': checked,
            'directories_scanned': scanned_roots, 'directories_missing': missing_roots,
            'tool_sha256': tool_hashes, 'apk_manifest_zip_crc_checked': True,
            'independent_xmltree_fallback_count': len(fallback_paths),
            'independent_xmltree_fallback_paths': fallback_paths,
            'watched_package_paths': watched,
            'collision_found_in_scanned_roots': False,
            'limitations': ['Only allocated regular APKs in the listed filesystem roots were scanned.',
                            'APEX payloads, symlink targets, ODM/vendor, dynamic packages and runtime were not scanned.',
                            'Host manifest parsing does not prove APK installation or runtime compatibility.']}
