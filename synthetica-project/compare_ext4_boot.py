#!/usr/bin/env python3
"""Compare two ext4 images read-only for the approved boot-first marker change.

The only permitted new path is a regular, non-executable marker. All existing
reachable regular-file contents, symlink targets and selected inode metadata
are compared, and debugfs inode-stat output (including displayed xattrs) is
compared for every existing inode. This is not an Android boot, AVB, recovery,
cryptographic signature, or physical-device test.

Requires pytsk3 and e2fsprogs debugfs on the host. Never mounts either image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pytsk3
except ImportError:
    pytsk3 = None

MARKER = "/system/etc/synthetica-build-info.txt"
PARENT = "/system/etc"
MAX_PATHS = 50_000
MAX_DEPTH = 100
CHUNK = 4 * 1024 * 1024


class ComparisonError(Exception):
    """The images differ outside the approved change, or could not be checked."""


def _metadata(meta) -> dict:
    keys = ("addr", "type", "mode", "uid", "gid", "size", "nlink", "flags", "mtime", "mtime_nano",
            "atime", "atime_nano", "ctime", "ctime_nano", "crtime", "crtime_nano", "seq")
    item = {key: getattr(meta, key) for key in keys}
    link = meta.link
    item["link"] = bytes(link).decode("utf-8", "surrogateescape") if link is not None else None
    return item


def _hash_file(file, size: int) -> str:
    if size < 0:
        raise ComparisonError("A file has a negative size")
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        block = file.read_random(offset, min(CHUNK, size - offset))
        if not block or len(block) > min(CHUNK, size - offset):
            raise ComparisonError("An ext4 file could not be read completely")
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def inventory(image: Path) -> tuple[dict, int]:
    """Inventory allocated, reachable paths without following symlinks."""
    if pytsk3 is None:
        raise ComparisonError("pytsk3 is required for the filesystem comparison")
    try:
        raw = pytsk3.Img_Info(str(image))
        fs = pytsk3.FS_Info(raw)
        if fs.info.ftype != pytsk3.TSK_FS_TYPE_EXT4:
            raise ComparisonError("Only ext4 filesystems are accepted")
        root = fs.open_meta(inode=fs.info.root_inum)
        if root.info.meta is None or root.info.meta.type != pytsk3.TSK_FS_META_TYPE_DIR:
            raise ComparisonError("Missing ext4 root directory")
        items = {"/": _metadata(root.info.meta)}
        stack = [("/", fs.info.root_inum, 0)]
        visited_dirs = set()
        hashed_inodes = {}
        while stack:
            parent, inode, depth = stack.pop()
            if depth > MAX_DEPTH or inode in visited_dirs:
                raise ComparisonError("Directory depth or cycle exceeds the audit limit")
            visited_dirs.add(inode)
            directory = fs.open_dir(inode=inode)
            for entry in directory:
                name_info = entry.info.name
                if name_info is None or not name_info.name:
                    continue
                name_bytes = bytes(name_info.name)
                if name_bytes in (b".", b"..") or not (name_info.flags & pytsk3.TSK_FS_NAME_FLAG_ALLOC):
                    continue
                if b"/" in name_bytes or b"\0" in name_bytes:
                    raise ComparisonError("Unsafe ext4 directory name")
                meta = entry.info.meta
                if meta is None:
                    raise ComparisonError("Allocated entry has no inode metadata")
                if meta.type in (pytsk3.TSK_FS_META_TYPE_VIRT, pytsk3.TSK_FS_META_TYPE_VIRT_DIR):
                    # libtsk's synthetic $OrphanFiles is not an on-disk path.
                    continue
                name = name_bytes.decode("utf-8", "surrogateescape")
                path = ("" if parent == "/" else parent) + "/" + name
                if path in items or len(items) >= MAX_PATHS:
                    raise ComparisonError("Duplicate path or too many ext4 entries")
                item = _metadata(meta)
                if meta.type == pytsk3.TSK_FS_META_TYPE_REG:
                    key = (meta.addr, meta.size)
                    if key not in hashed_inodes:
                        hashed_inodes[key] = _hash_file(entry, meta.size)
                    item["content_sha256"] = hashed_inodes[key]
                elif meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                    stack.append((path, meta.addr, depth + 1))
                items[path] = item
        return items, fs.info.block_size
    except ComparisonError:
        raise
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeError) as exc:
        raise ComparisonError(f"Could not inventory ext4 image: {exc}") from exc


def _stat_records(image: Path, inodes: set[int], debugfs: str) -> dict[int, str]:
    """Collect debugfs's complete, human-readable stat for every old inode."""
    commands = "".join(f"stat <{inode}>\n" for inode in sorted(inodes))
    with tempfile.TemporaryDirectory(prefix="synthetica-ext4-stat-") as tmp:
        cmdfile = Path(tmp) / "commands"
        cmdfile.write_text(commands, encoding="ascii")
        env = {**os.environ, "LC_ALL": "C", "TZ": "UTC"}
        run = subprocess.run([debugfs, "-f", str(cmdfile), str(image)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if run.returncode != 0:
        raise ComparisonError("debugfs failed while reading inode statistics")
    stderr = run.stderr.decode("utf-8", "replace").strip().splitlines()
    if any(not line.startswith("debugfs ") for line in stderr if line):
        raise ComparisonError("debugfs reported an inode-stat error: " + " | ".join(stderr[:3]))
    text = run.stdout.decode("utf-8", "backslashreplace")
    chunks = re.split(r"(?m)^debugfs: stat <([0-9]+)>\n", text)
    if not chunks or chunks[0].strip() or len(chunks) % 2 == 0:
        raise ComparisonError("Unexpected debugfs inode-stat output")
    records = {}
    for i in range(1, len(chunks), 2):
        inode = int(chunks[i])
        body = chunks[i + 1].rstrip() + "\n"
        if inode in records or not body.startswith(f"Inode: {inode} "):
            raise ComparisonError("Missing, repeated or unreadable inode-stat record")
        records[inode] = body
    if set(records) != inodes:
        raise ComparisonError("debugfs did not report all existing inodes")
    return records


def _xattrs(record: str) -> str:
    """Extract displayed ext4 extended attributes from a debugfs stat record."""
    lines = record.splitlines()
    if "Extended attributes:" not in lines:
        return ""
    start = lines.index("Extended attributes:") + 1
    selected = []
    for line in lines[start:]:
        if not line.startswith("  "):
            break
        selected.append(line)
    return "\n".join(selected)


def compare(before: Path, after: Path, marker_bytes: bytes, debugfs: str = "/usr/sbin/debugfs") -> dict:
    """Fail closed unless only the approved marker was added to /system/etc."""
    if not marker_bytes or len(marker_bytes) > 4096:
        raise ComparisonError("Marker content must be between 1 and 4096 bytes")
    old, old_block = inventory(before)
    new, new_block = inventory(after)
    if old_block != new_block:
        raise ComparisonError("The ext4 block size changed")
    if MARKER in old or PARENT not in old or PARENT not in new:
        raise ComparisonError("Marker already exists or the expected parent is missing")
    if set(new) - set(old) != {MARKER} or set(old) - set(new):
        raise ComparisonError("Unexpected added or removed filesystem paths")
    marker = new[MARKER]
    if (marker["type"] != pytsk3.TSK_FS_META_TYPE_REG or marker["mode"] != 0o644
            or marker["uid"] != 0 or marker["gid"] != 0 or marker["nlink"] != 1
            or marker["size"] != len(marker_bytes)
            or marker.get("content_sha256") != hashlib.sha256(marker_bytes).hexdigest()):
        raise ComparisonError("Marker content or owner/mode is not the approved value")
    parent_ignored = {"size", "mtime", "mtime_nano", "ctime", "ctime_nano"}
    for path in old:
        a, b = old[path], new[path]
        if path == PARENT:
            if b["size"] < a["size"] or b["size"] > a["size"] + old_block:
                raise ComparisonError("Marker parent directory grew unexpectedly")
            a = {k: v for k, v in a.items() if k not in parent_ignored}
            b = {k: v for k, v in b.items() if k not in parent_ignored}
        if a != b:
            raise ComparisonError(f"Existing path changed: {path}")
    inodes = {int(item["addr"]) for item in old.values()}
    stats_old = _stat_records(before, inodes, debugfs)
    stats_new = _stat_records(after, inodes, debugfs)
    parent_inode = int(old[PARENT]["addr"])
    for inode in sorted(inodes):
        if inode == parent_inode:
            if _xattrs(stats_old[inode]) != _xattrs(stats_new[inode]):
                raise ComparisonError("Extended attributes of the marker parent changed")
        elif stats_old[inode] != stats_new[inode]:
            raise ComparisonError(f"Existing inode stat or displayed xattrs changed: {inode}")
    marker_stat = _stat_records(after, {int(marker["addr"])}, debugfs)[int(marker["addr"])]
    if 'security.selinux (26) = "u:object_r:system_file:s0\\000"' not in _xattrs(marker_stat):
        raise ComparisonError("Marker SELinux label is not the expected system_file value")
    regular_files = sum(1 for item in old.values() if item["type"] == pytsk3.TSK_FS_META_TYPE_REG)
    symlinks = sum(1 for item in old.values() if item["type"] == pytsk3.TSK_FS_META_TYPE_LNK)
    return {
        "status": "only_approved_marker_detected",
        "existing_reachable_paths_checked": len(old),
        "existing_regular_file_paths_sha256_checked": regular_files,
        "existing_symlink_paths_checked": symlinks,
        "existing_inode_stats_and_displayed_xattrs_checked": len(inodes),
        "marker": {"path": MARKER, "bytes": len(marker_bytes),
                   "sha256": hashlib.sha256(marker_bytes).hexdigest(),
                   "mode": "0644", "uid": 0, "gid": 0,
                   "selinux": "u:object_r:system_file:s0"},
        "limitations": [
            "Compares allocated reachable paths and displayed inode statistics, not deleted or unallocated data.",
            "The marker parent directory and ext4 allocation/superblock metadata may change to add the file.",
            "Does not establish ZIP signature, external vbmeta/AVB compatibility, recovery behavior, or device boot."
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("marker", type=Path, help="Expected marker bytes, read-only")
    parser.add_argument("--debugfs", default="/usr/sbin/debugfs")
    args = parser.parse_args(argv)
    try:
        result = compare(args.before, args.after, args.marker.read_bytes(), args.debugfs)
    except (ComparisonError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
