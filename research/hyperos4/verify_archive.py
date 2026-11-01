#!/usr/bin/env python3
"""Read-only identity and ZIP-directory preflight for the referenced ROM.

Accept one file or ordered raw split parts. This does not extract, execute,
repair, install, or prove the safety/authenticity of any archive contents.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import stat
import sys
import zipfile
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO

EXPECTED_SIZE = 4_512_854_711
EXPECTED_SHA256 = "454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63"
CHUNK_SIZE = 4 * 1024 * 1024
MAX_READ = 64 * 1024 * 1024
MAX_REPORTED_ENTRIES = 2_048
MAX_REPORTED_FINDINGS = 2_048
MAX_SUPER_BYTES = 12 * 1024 * 1024 * 1024
CORE_REFERENCE = {
    "boot.img": {
        "bytes": 134_217_728,
        "sha256": "57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d",
    },
    "dtbo.img": {
        "bytes": 25_165_824,
        "sha256": "9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2",
    },
}


class PreflightError(Exception):
    """Invalid or changing input; stop rather than infer a clean result."""


def stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def identity(f: BinaryIO) -> tuple[int, int, int, int, int]:
    return stat_identity(os.fstat(f.fileno()))


def ensure_unchanged(paths: list[Path], files: list[BinaryIO], snapshots: list[tuple[int, ...]]) -> None:
    for path, f, original in zip(paths, files, snapshots):
        if identity(f) != original or stat_identity(path.stat()) != original:
            raise PreflightError("Input changed or was replaced during inspection")


class JoinedReader:
    """Seekable, read-only view of already-opened, ordered raw byte parts."""

    def __init__(self, files: list[BinaryIO], sizes: list[int]):
        if not files or len(files) != len(sizes) or any(n < 0 for n in sizes):
            raise PreflightError("Input parts or their sizes are invalid")
        self.files = files
        self.starts = []
        self.total = 0
        for size in sizes:
            self.starts.append(self.total)
            self.total += size
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        base = {os.SEEK_SET: 0, os.SEEK_CUR: self.pos, os.SEEK_END: self.total}.get(whence)
        if base is None or base + offset < 0:
            raise ValueError("Invalid seek")
        self.pos = base + offset
        return self.pos

    def read(self, count: int = -1) -> bytes:
        available = max(0, self.total - self.pos)
        if count is None or count < 0:
            count = available
        else:
            count = min(count, available)
        if count > MAX_READ:
            raise PreflightError("A ZIP directory read exceeded the 64 MiB safety limit")
        result = bytearray()
        while count:
            idx = bisect.bisect_right(self.starts, self.pos) - 1
            if idx < 0 or idx >= len(self.files):
                raise PreflightError("Invalid split-file offset")
            end = self.starts[idx + 1] if idx + 1 < len(self.starts) else self.total
            length = min(count, end - self.pos)
            if length <= 0:
                raise PreflightError("Invalid or changing split-file length")
            part = self.files[idx]
            part.seek(self.pos - self.starts[idx])
            block = part.read(length)
            if len(block) != length:
                raise PreflightError("Input changed or became unreadable during inspection")
            result.extend(block)
            self.pos += length
            count -= length
        return bytes(result)


def path_findings(info: zipfile.ZipInfo) -> list[str]:
    name = info.filename
    normalized = name.replace("\\", "/")
    flags = []
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        flags.append("absolute_path")
    if ".." in normalized.split("/"):
        flags.append("parent_path_component")
    # Unix file-type bits are meaningful only when the entry declares Unix origin.
    if info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16):
        flags.append("symlink")
    if info.flag_bits & 1:
        flags.append("encrypted")
    return flags


def inspect_zip(reader: JoinedReader) -> dict:
    reader.seek(0)
    with zipfile.ZipFile(reader, "r", allowZip64=True) as archive:
        entries = archive.infolist()
        seen: set[str] = set()
        reported = []
        findings = []
        finding_count = 0
        total_declared = 0
        for entry in entries:
            total_declared += entry.file_size
            flags = path_findings(entry)
            if entry.filename in seen:
                flags.append("duplicate_name")
            seen.add(entry.filename)
            if len(reported) < MAX_REPORTED_ENTRIES:
                reported.append({
                    "name": entry.filename,
                    "compressed_bytes_declared": entry.compress_size,
                    "uncompressed_bytes_declared": entry.file_size,
                    "compression_method": entry.compress_type,
                    "crc32_declared": f"{entry.CRC:08x}",
                })
            if flags:
                finding_count += 1
                if len(findings) < MAX_REPORTED_FINDINGS:
                    findings.append({"name": entry.filename, "flags": flags})
        return {
            "directory_only": True,
            "entry_count": len(entries),
            "reported_entry_count": len(reported),
            "entries_truncated": len(reported) != len(entries),
            "declared_uncompressed_bytes": total_declared,
            "entries": reported,
            "finding_count": finding_count,
            "findings_truncated": finding_count > len(findings),
            "findings": findings,
            "crc_and_contents_verified": False,
        }


def inspect_super_prefix(prefix: bytes) -> dict:
    """Identify basic on-disk format; this is not an LP metadata validator."""
    if len(prefix) >= 28 and prefix[:4] == b"\x3a\xff\x26\xed":
        import struct

        magic, major, minor, file_header, chunk_header, block_size, blocks, chunks, checksum = (
            struct.unpack_from("<I4H4I", prefix)
        )
        return {
            "format": "android_sparse",
            "major": major,
            "minor": minor,
            "file_header_bytes": file_header,
            "chunk_header_bytes": chunk_header,
            "block_bytes": block_size,
            "expanded_bytes_declared": block_size * blocks,
            "chunks_declared": chunks,
            "image_checksum_declared": f"{checksum:08x}",
            "validated": False,
        }
    if len(prefix) >= 4100 and prefix[4096:4100] == b"gDla":
        return {"format": "raw_super_with_lp_geometry_magic", "validated": False}
    return {"format": "unknown", "validated": False}


def inspect_core_members(reader: JoinedReader, reference: dict) -> dict:
    """Stream exactly three ZIP members, without extracting or executing them.

    zipfile checks each member's CRC at EOF. Hashes describe uncompressed image
    bytes. Limits are checked before decompression; all other archive members
    remain unchecked. This does not validate images or certify bootability.
    """
    result = {"members": {}, "matches_reference": {}, "super_prefix": None}
    reader.seek(0)
    with zipfile.ZipFile(reader, "r", allowZip64=True) as archive:
        by_name = {entry.filename: entry for entry in archive.infolist()}
        missing = [name for name in ("boot.img", "dtbo.img", "super.img") if name not in by_name]
        if missing:
            raise PreflightError("Required root ZIP members absent: " + ", ".join(missing))
        for name in ("boot.img", "dtbo.img", "super.img"):
            info = by_name[name]
            if info.is_dir() or info.flag_bits & 1:
                raise PreflightError(f"Core member is a directory or encrypted: {name}")
            if name == "super.img":
                if not 0 < info.file_size <= MAX_SUPER_BYTES:
                    raise PreflightError("Declared super.img size is outside the safe audit limit")
            elif name in reference and info.file_size != reference[name]["bytes"]:
                # A clear mismatch must not be treated as a clean identity match.
                result["matches_reference"][name] = False
                raise PreflightError(f"Declared size differs from provided reference: {name}")
            digest = hashlib.sha256()
            count = 0
            prefix = b""
            with archive.open(info, "r") as member:
                while block := member.read(CHUNK_SIZE):
                    count += len(block)
                    if count > info.file_size or (name == "super.img" and count > MAX_SUPER_BYTES):
                        raise PreflightError(f"Unexpected streamed member size: {name}")
                    digest.update(block)
                    if name == "super.img" and len(prefix) < 8192:
                        prefix += block[: 8192 - len(prefix)]
            if count != info.file_size:
                raise PreflightError(f"Truncated core member: {name}")
            sha256 = digest.hexdigest()
            result["members"][name] = {
                "bytes": count,
                "sha256": sha256,
                "zip_crc_verified_at_eof": True,
            }
            if name in reference:
                result["matches_reference"][name] = (
                    count == reference[name]["bytes"] and sha256 == reference[name]["sha256"]
                )
            if name == "super.img":
                result["super_prefix"] = inspect_super_prefix(prefix)
    return result


def preflight(
    paths: list[Path],
    expected_size: int,
    expected_sha256: str,
    *,
    inspect_core: bool = False,
    core_reference: dict | None = None,
) -> tuple[int, dict]:
    result = {
        "mode": "read-only; no extraction, execution, installation, or device access",
        "expected": {"bytes": expected_size, "sha256": expected_sha256.lower()},
        "parts": [],
        "observed": {"bytes": None, "sha256": None},
        "matches": {"size": None, "sha256": None},
        "archive": None,
        "core_members": None,
        "status": "error",
        "limitations": [
            "The expected digest is publisher metadata, not an author signature or safety certification.",
            "A ZIP directory is not proof of valid member content, CRCs, bootability, or device compatibility.",
            "Optional core inspection checks only three members; it never validates or executes the installer.",
        ],
    }
    try:
        with ExitStack() as stack:
            files = []
            snapshots = []
            for path in paths:
                initial = path.stat()
                if not stat.S_ISREG(initial.st_mode):
                    raise PreflightError("Each part must be a regular file")
                # A nonblocking open avoids hanging on a FIFO swapped in after stat().
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
                try:
                    f = os.fdopen(fd, "rb")
                except BaseException:
                    os.close(fd)
                    raise
                f = stack.enter_context(f)
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != (initial.st_dev, initial.st_ino):
                    raise PreflightError("Input changed or is not a regular file")
                snapshot = identity(f)
                if any(snapshot[:2] == prior[:2] for prior in snapshots):
                    raise PreflightError("The same file was supplied more than once")
                files.append(f)
                snapshots.append(snapshot)
                result["parts"].append({"name": path.name, "bytes": st.st_size})
            if not files:
                raise PreflightError("No input files supplied")
            reader = JoinedReader(files, [x[2] for x in snapshots])
            result["observed"]["bytes"] = reader.total
            result["matches"]["size"] = reader.total == expected_size
            if not result["matches"]["size"]:
                result["status"] = "size_mismatch"
                return 2, result
            digest = hashlib.sha256()
            while block := reader.read(CHUNK_SIZE):
                digest.update(block)
            ensure_unchanged(paths, files, snapshots)
            actual_sha256 = digest.hexdigest()
            result["observed"]["sha256"] = actual_sha256
            result["matches"]["sha256"] = actual_sha256 == expected_sha256.lower()
            if not result["matches"]["sha256"]:
                result["status"] = "sha256_mismatch"
                return 2, result
            result["archive"] = inspect_zip(reader)
            ensure_unchanged(paths, files, snapshots)
            if result["archive"]["finding_count"]:
                result["status"] = "matched_with_findings"
                return 4, result
            if inspect_core:
                ref = CORE_REFERENCE if core_reference is None else core_reference
                result["core_members"] = inspect_core_members(reader, ref)
                ensure_unchanged(paths, files, snapshots)
                if not all(result["core_members"]["matches_reference"].values()):
                    result["status"] = "component_mismatch"
                    return 4, result
            result["status"] = "matched"
            return 0, result
    except (OSError, ValueError, zipfile.BadZipFile, PreflightError, NotImplementedError, RuntimeError) as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return 3, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts", nargs="+", type=Path, help="One ZIP or its raw split parts, in order")
    parser.add_argument("--expected-size", type=int, default=EXPECTED_SIZE)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    parser.add_argument(
        "--inspect-core",
        action="store_true",
        help="After identity/directory checks, stream boot.img, dtbo.img and super.img for SHA-256/CRC",
    )
    args = parser.parse_args(argv)
    if args.expected_size < 0 or not re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_sha256):
        parser.error("Expected size must be nonnegative and SHA-256 must contain 64 hex digits")
    exit_code, result = preflight(args.parts, args.expected_size, args.expected_sha256, inspect_core=args.inspect_core)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
