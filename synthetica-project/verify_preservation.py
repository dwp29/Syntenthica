#!/usr/bin/env python3
"""Read-only comparison of a candidate ROM ZIP with a stock-baseline lock.

This is an identity/unchanged-content gate, not a build, signing verifier,
installer, or proof that a ROM boots. A repacked archive requires review even
when every member matches because ZIP metadata/signatures can affect recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import zipfile
import zlib
from pathlib import Path, PurePosixPath

CHUNK = 4 * 1024 * 1024
MAX_LOCK_BYTES = 1024 * 1024
MAX_CANDIDATE_BYTES = 16 * 1024 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_TOTAL_EXPANDED = 16 * 1024 * 1024 * 1024
MAX_ZIP_READ = 8 * 1024 * 1024
LOCK_SCHEMA = "synthetica-stock-baseline-lock-v1"


class AuditError(Exception):
    """Input is unsupported, unsafe, corrupt, or changed during audit."""


def _snapshot(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _safe_name(name: object, directory: bool) -> bool:
    if not isinstance(name, str) or not name or "\\" in name or "\0" in name or "//" in name:
        return False
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return False
    if any(part in (".", "..", "") for part in name.rstrip("/").split("/")):
        return False
    return (name.endswith("/") == directory) and not PurePosixPath(name).is_absolute()


def _read_lock(path: Path) -> dict:
    with _open_regular(path)[0] as f:
        opened = _snapshot(os.fstat(f.fileno()))
        if opened[2] > MAX_LOCK_BYTES:
            raise AuditError("Baseline lock must be no larger than 1 MiB")
        raw = f.read(MAX_LOCK_BYTES + 1)
        _check_unchanged(path, f, opened)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("schema") != LOCK_SCHEMA or not isinstance(data.get("identity"), dict):
        raise AuditError("Unsupported baseline lock schema")
    identity = data["identity"]
    zip_bytes, zip_hash, entries = identity.get("zip_bytes"), identity.get("zip_sha256"), identity.get("entries")
    if type(zip_bytes) is not int or not 0 < zip_bytes <= MAX_CANDIDATE_BYTES:
        raise AuditError("Invalid locked archive size")
    if not isinstance(zip_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", zip_hash):
        raise AuditError("Invalid locked archive SHA-256")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise AuditError("Invalid locked entry count")
    expected = {}
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuditError("Invalid locked entry")
        name = entry.get("name")
        directory = entry.get("directory", False)
        if type(directory) is not bool or not _safe_name(name, directory) or name in expected:
            raise AuditError("Unsafe or duplicate locked entry")
        if not directory:
            size, sha = entry.get("bytes"), entry.get("sha256")
            if type(size) is not int or size < 0:
                raise AuditError("Invalid locked entry size")
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise AuditError("Invalid locked entry SHA-256")
            total += size
            if total > MAX_TOTAL_EXPANDED:
                raise AuditError("Locked contents exceed the 16 GiB inspection limit")
        expected[name] = entry
    return {"zip_bytes": zip_bytes, "zip_sha256": zip_hash, "entries": expected}


def _open_regular(path: Path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise AuditError("Candidate must be a regular file, not a symlink or special file")
    if before.st_size <= 0 or before.st_size > MAX_CANDIDATE_BYTES:
        raise AuditError("Candidate size is outside the audit limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        f = os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise
    if _snapshot(os.fstat(f.fileno())) != _snapshot(before):
        f.close()
        raise AuditError("Candidate changed while opening")
    return f, _snapshot(before)


def _check_unchanged(path: Path, f, expected: tuple[int, ...]) -> None:
    if _snapshot(os.fstat(f.fileno())) != expected or _snapshot(path.lstat()) != expected:
        raise AuditError("Candidate changed or was replaced during audit")


class _BoundedZipReader:
    """Restrict individual reads made by zipfile, including central directories."""

    def __init__(self, f):
        self.f = f

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = max(0, os.fstat(self.f.fileno()).st_size - self.f.tell())
        if size > MAX_ZIP_READ:
            raise AuditError("A ZIP read exceeded the 8 MiB safety limit")
        return self.f.read(size)

    def tell(self) -> int:
        return self.f.tell()

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self.f.seek(offset, whence)

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True


def audit_candidate(lock_path: Path, candidate: Path) -> dict:
    """Compare archive bytes and all locked members without extracting files."""
    result = {
        "scope": "read-only ZIP comparison; no extraction, execution, build, or device access",
        "candidate_name": candidate.name,
        "status": "error",
        "archive": None,
        "entries": [],
        "mismatches": [],
        "limitations": [
            "Checksums identify bytes, not author identity, installation safety, or runtime compatibility.",
            "A repacked ZIP requires separate signature/recovery review even when its member bytes match.",
            "A byte-identical copy is the original ROM, not a newly built Synthetica ROM.",
        ],
    }
    try:
        lock = _read_lock(lock_path)
        expected = lock["entries"]
        with _open_regular(candidate)[0] as f:
            opened = _snapshot(os.fstat(f.fileno()))
            digest = hashlib.sha256()
            while block := f.read(CHUNK):
                digest.update(block)
            _check_unchanged(candidate, f, opened)
            whole_sha = digest.hexdigest()
            same_archive = opened[2] == lock["zip_bytes"] and whole_sha == lock["zip_sha256"]
            result["archive"] = {
                "bytes": opened[2], "sha256": whole_sha,
                "matches_locked_archive": same_archive,
            }
            f.seek(0)
            with zipfile.ZipFile(_BoundedZipReader(f), "r", allowZip64=True) as z:
                infos = z.infolist()
                if len(infos) > MAX_ENTRIES:
                    raise AuditError("Candidate contains too many ZIP entries")
                by_name = {}
                for info in infos:
                    name = info.filename
                    if not _safe_name(name, info.is_dir()) or name in by_name:
                        raise AuditError("Candidate has unsafe or duplicate ZIP entry names")
                    if info.flag_bits & 1:
                        raise AuditError("Encrypted ZIP entries cannot be audited")
                    if info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16):
                        raise AuditError("ZIP symlinks are not allowed")
                    by_name[name] = info
                result["mismatches"].extend({"name": n, "reason": "missing"} for n in sorted(expected.keys() - by_name.keys()))
                result["mismatches"].extend({"name": n, "reason": "extra"} for n in sorted(by_name.keys() - expected.keys()))
                for name in sorted(expected.keys() & by_name.keys()):
                    spec, info = expected[name], by_name[name]
                    if spec.get("directory", False):
                        if not info.is_dir() or info.file_size != 0:
                            result["mismatches"].append({"name": name, "reason": "directory_changed"})
                        continue
                    if info.is_dir() or info.file_size != spec["bytes"]:
                        result["mismatches"].append({"name": name, "reason": "size_or_type_changed"})
                        continue
                    member_hash = hashlib.sha256()
                    count = 0
                    with z.open(info, "r") as member:
                        while block := member.read(CHUNK):
                            count += len(block)
                            if count > spec["bytes"]:
                                raise AuditError("A member exceeded its locked size")
                            member_hash.update(block)
                    if count != spec["bytes"]:
                        raise AuditError("A member ended before its locked size")
                    member_sha = member_hash.hexdigest()
                    matches = member_sha == spec["sha256"]
                    result["entries"].append({
                        "name": name, "bytes": count, "sha256": member_sha,
                        "matches_locked_sha256": matches, "zip_crc_verified_at_eof": True,
                    })
                    if not matches:
                        result["mismatches"].append({"name": name, "reason": "sha256_changed"})
            _check_unchanged(candidate, f, opened)
        if result["mismatches"]:
            result["status"] = "content_changed_review_required"
        elif same_archive:
            result["status"] = "exact_original_not_a_new_build"
        else:
            result["status"] = "repacked_review_required"
    except (AuditError, OSError, ValueError, TypeError, EOFError, zlib.error, zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="Candidate ZIP; opened read-only")
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    args = parser.parse_args(argv)
    result = audit_candidate(args.lock, args.candidate)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if result["status"] == "exact_original_not_a_new_build":
        return 0
    if result["status"] in ("content_changed_review_required", "repacked_review_required"):
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
