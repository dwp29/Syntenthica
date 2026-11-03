#!/usr/bin/env python3
"""Add one ordinary application to a copy of an ext4 image, with preservation checks.

Only /app/SpatialFlow and its single APK may be added. Existing allocated,
reachable paths and inode statistics are compared, including extended
attributes. The original is not modified. This is NOT a device, signature,
AVB, package-manager or boot test.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

import compare_ext4_boot as guard

PARENT = '/app'
DIRECTORY = '/app/SpatialFlow'
APK_PATH = DIRECTORY + '/SpatialFlow.apk'
LABEL = b'u:object_r:system_file:s0\0'
DEBUGFS = '/usr/sbin/debugfs'
E2FSCK = '/usr/sbin/e2fsck'
RESIZE2FS = '/usr/sbin/resize2fs'
MAX_GROWTH = 64 * 1024 * 1024
CHUNK = 4 * 1024 * 1024

class FeatureImageError(RuntimeError):
    pass


def digest(path: Path) -> tuple[int, str]:
    size = 0
    h = hashlib.sha256()
    with path.open('rb') as f:
        while data := f.read(CHUNK):
            h.update(data)
            size += len(data)
    return size, h.hexdigest()


def check_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise FeatureImageError('Input must be an ordinary file, not a symlink')


def compare(before: Path, after: Path, apk_size: int, apk_sha256: str) -> dict:
    if guard.pytsk3 is None:
        raise FeatureImageError('The pinned ext4 reader is not available')
    old, old_block = guard.inventory(before)
    new, new_block = guard.inventory(after)
    if old_block != new_block or PARENT not in old or PARENT not in new:
        raise FeatureImageError('Missing application directory or changed ext4 block size')
    if DIRECTORY in old or APK_PATH in old:
        raise FeatureImageError('Application path was already present')
    if set(new) - set(old) != {DIRECTORY, APK_PATH} or set(old) - set(new):
        raise FeatureImageError('Filesystem paths changed beyond the two approved additions')
    directory, apk = new[DIRECTORY], new[APK_PATH]
    tsk = guard.pytsk3
    if (directory['type'] != tsk.TSK_FS_META_TYPE_DIR or directory['mode'] != 0o755
            or directory['uid'] != 0 or directory['gid'] != 0 or directory['nlink'] != 2):
        raise FeatureImageError('New application directory has unexpected type, ownership or mode')
    if (apk['type'] != tsk.TSK_FS_META_TYPE_REG or apk['mode'] != 0o644
            or apk['uid'] != 0 or apk['gid'] != 0 or apk['nlink'] != 1
            or apk['size'] != apk_size or apk.get('content_sha256') != apk_sha256):
        raise FeatureImageError('New application file content, type, ownership or mode is incorrect')
    ignored_parent_fields = {'size', 'nlink', 'mtime', 'mtime_nano', 'ctime', 'ctime_nano'}
    for path, a in old.items():
        b = new[path]
        if path == PARENT:
            if b['size'] < a['size'] or b['size'] > a['size'] + old_block:
                raise FeatureImageError('Application parent directory grew unexpectedly')
            # ext4 dir_nlink can use 1 as the overflow/unknown sentinel.
            expected_links = {a['nlink'] + 1} | ({1} if a['nlink'] == 1 else set())
            if b['nlink'] not in expected_links:
                raise FeatureImageError('Application parent link count changed unexpectedly')
            a = {k: v for k, v in a.items() if k not in ignored_parent_fields}
            b = {k: v for k, v in b.items() if k not in ignored_parent_fields}
        if a != b:
            raise FeatureImageError('Existing filesystem entry changed: ' + path)
    old_inodes = {int(x['addr']) for x in old.values()}
    old_stats = guard._stat_records(before, old_inodes, DEBUGFS)
    new_stats = guard._stat_records(after, old_inodes, DEBUGFS)
    parent_inode = int(old[PARENT]['addr'])
    for inode in sorted(old_inodes):
        if inode == parent_inode:
            if guard._xattrs(old_stats[inode]) != guard._xattrs(new_stats[inode]):
                raise FeatureImageError('Application parent extended attributes changed')
        elif old_stats[inode] != new_stats[inode]:
            raise FeatureImageError('An existing inode statistic or displayed xattr changed')
    new_inodes = {int(directory['addr']), int(apk['addr'])}
    if len(new_inodes) != 2 or new_inodes & old_inodes:
        raise FeatureImageError('New file or directory shares an existing inode')
    added_stats = guard._stat_records(after, new_inodes, DEBUGFS)
    required_label = 'security.selinux (26) = "u:object_r:system_file:s0\\000"'
    for inode in new_inodes:
        if required_label not in guard._xattrs(added_stats[inode]):
            raise FeatureImageError('New file or directory has an unexpected SELinux label')
    return {'status': 'only_nonprivileged_spatialflow_paths_added',
            'existing_reachable_paths_checked': len(old),
            'existing_regular_file_paths_sha256_checked': sum(1 for x in old.values() if x['type'] == tsk.TSK_FS_META_TYPE_REG),
            'existing_inode_stats_and_displayed_xattrs_checked': len(old_inodes),
            'directory': DIRECTORY, 'apk_path': APK_PATH, 'apk_bytes': apk_size,
            'apk_sha256': apk_sha256, 'uid': 0, 'gid': 0,
            'directory_mode': '0755', 'apk_mode': '0644',
            'selinux_label': 'u:object_r:system_file:s0',
            'limitations': ['Reachable path and displayed-xattr comparison is not a comparison of unallocated space.',
                            'Neither package-manager behavior nor SELinux runtime labeling was tested.']}


def edit(before: Path, after: Path, apk: Path, scratch: Path, expected_sha256: str, *, grow_by: int = 0) -> dict:
    if type(grow_by) is not int or grow_by < 0 or grow_by > MAX_GROWTH or grow_by % 4096:
        raise FeatureImageError('Filesystem growth is outside the bounded 4 KiB-aligned allowance')
    for p in (before, apk):
        check_regular(p)
    if after.exists() or after.is_symlink() or not after.parent.is_dir():
        raise FeatureImageError('Output image must be a new path in an existing directory')
    if not scratch.is_dir() or any(scratch.iterdir()):
        raise FeatureImageError('Scratch directory must be empty and already exist')
    if not all(re.fullmatch(r'[A-Za-z0-9_./-]+', str(p.absolute())) for p in (before, after, apk, scratch)):
        raise FeatureImageError('Paths contain unsupported debugfs command characters')
    apk_size, apk_sha = digest(apk)
    if apk_size <= 0 or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256) or apk_sha != expected_sha256:
        raise FeatureImageError('Application does not match the expected digest')
    before_size, before_sha = digest(before)
    if before_size < 64:
        raise FeatureImageError('The input image is too small')
    with before.open('rb') as f:
        f.seek(-64, os.SEEK_END)
        if f.read(4) == b'AVBf':
            raise FeatureImageError('AVB footer is present; this recipe cannot re-sign it')
    # Refuse absence or divergence of the existing product app SELinux label.
    existing_label = scratch / 'existing-label'
    env = {**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC', 'E2FSPROGS_FAKE_TIME': '1230768000'}
    get_label = subprocess.run([DEBUGFS, '-R', f'ea_get -f {existing_label.absolute()} {PARENT} security.selinux', str(before)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if get_label.returncode or not existing_label.is_file() or existing_label.read_bytes() != LABEL:
        raise FeatureImageError('Existing app directory does not have the expected system_file label')
    label = scratch / 'new-label'
    label.write_bytes(LABEL)
    commands = scratch / 'debugfs-commands'
    commands.write_text(
        f'mkdir {DIRECTORY}\n'
        f'sif {DIRECTORY} mode 040755\n'
        f'sif {DIRECTORY} uid 0\n'
        f'sif {DIRECTORY} gid 0\n'
        f'ea_set -f {label.absolute()} {DIRECTORY} security.selinux\n'
        f'write {apk.absolute()} {APK_PATH}\n'
        f'sif {APK_PATH} mode 0100644\n'
        f'sif {APK_PATH} uid 0\n'
        f'sif {APK_PATH} gid 0\n'
        f'ea_set -f {label.absolute()} {APK_PATH} security.selinux\n', encoding='ascii')
    shutil.copyfile(before, after)
    if grow_by:
        with after.open('r+b') as out:
            out.truncate(before_size + grow_by)
        resize = subprocess.run([RESIZE2FS, str(after)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, check=False)
        if resize.returncode:
            raise FeatureImageError(f'resize2fs rejected the disposable product copy (exit {resize.returncode})')
        check_grown = subprocess.run([E2FSCK, '-f', '-n', str(after)], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, check=False)
        if check_grown.returncode:
            raise FeatureImageError(f'e2fsck rejected the resized copy (exit {check_grown.returncode})')
    run = subprocess.run([DEBUGFS, '-w', '-f', str(commands), str(after)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if run.returncode or b'Allocated inode:' not in run.stdout:
        raise FeatureImageError('debugfs did not successfully allocate the application file')
    check = subprocess.run([E2FSCK, '-f', '-n', str(after)], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, check=False)
    if check.returncode:
        raise FeatureImageError(f'Read-only e2fsck rejected the modified image (exit {check.returncode})')
    result = compare(before, after, apk_size, apk_sha)
    if digest(before) != (before_size, before_sha) or digest(apk) != (apk_size, apk_sha):
        raise FeatureImageError('Input image or application changed during edit')
    out_size, out_sha = digest(after)
    if out_size != before_size + grow_by or out_sha == before_sha:
        raise FeatureImageError('Modified image length or hash is unexpected')
    return {**result, 'before_bytes': before_size, 'before_sha256': before_sha,
            'after_bytes': out_size, 'after_sha256': out_sha, 'e2fsck_read_only_exit': 0,
            'growth_bytes': grow_by, 'source_image_and_apk_unchanged': True}
