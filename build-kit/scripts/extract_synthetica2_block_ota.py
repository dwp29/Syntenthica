#!/usr/bin/env python3
"""Bounded, read-only extraction of a full block OTA's vendor and boot images.

The input archive is hash-checked, never modified, and its scripts are never
executed. Only full `new` transfer commands are supported; delta, erase/zero,
unknown and overlapping operations fail closed. Output must be a new directory
outside the repository. This is not an installer or a compatibility verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BLOCK = 4096
MAX_TRANSFER = 1024 * 1024
MAX_ARCHIVE = 6_000_000_000
MAX_VENDOR_COMPRESSED = 1_500_000_000
MAX_VENDOR_IMAGE = 4_000_000_000
MAX_BOOT = 256 * 1024 * 1024
MAX_COMMANDS = 100_000


def parse_transfer(data: bytes) -> tuple[int, list[tuple[int, int]]]:
    if len(data) > MAX_TRANSFER:
        raise ValueError("transfer list is too large")
    try:
        rows = [line.strip() for line in data.decode("ascii").splitlines() if line.strip()]
        if len(rows) < 5 or rows[0] not in {"2", "3", "4"}:
            raise ValueError("unsupported transfer list header")
        declared = int(rows[1])
        if declared <= 0 or int(rows[2]) != 0 or int(rows[3]) != 0:
            raise ValueError("empty or incremental/stashed transfer list")
        if len(rows) - 4 > MAX_COMMANDS:
            raise ValueError("too many transfer commands")
        ranges = []
        for row in rows[4:]:
            fields = row.split()
            if len(fields) != 2 or fields[0] != "new":
                raise ValueError("only full OTA new commands are supported")
            pieces = fields[1].split(",")
            numbers = [int(piece) for piece in pieces]
            if (not numbers or numbers[0] <= 0 or numbers[0] % 2 or
                    numbers[0] != len(numbers) - 1):
                raise ValueError("malformed transfer ranges")
            for start, end in zip(numbers[1::2], numbers[2::2]):
                if start < 0 or end <= start or end * BLOCK > MAX_VENDOR_IMAGE:
                    raise ValueError("vendor transfer range outside bounds")
                ranges.append((start, end))
                if len(ranges) > MAX_COMMANDS:
                    raise ValueError("too many vendor ranges")
        if sum(end - start for start, end in ranges) != declared:
            raise ValueError("transfer declared block count mismatch")
        ordered = sorted(ranges)
        if any(a_end > b_start for (_, a_end), (b_start, _) in zip(ordered, ordered[1:])):
            raise ValueError("overlapping vendor transfer ranges")
        return max(end for _, end in ranges) * BLOCK, ranges
    except (UnicodeError, OverflowError) as exc:
        raise ValueError("invalid transfer encoding") from exc


def write_ranges(stream, output, image_bytes: int, ranges: list[tuple[int, int]]) -> None:
    output.truncate(image_bytes)
    for start, end in ranges:
        output.seek(start * BLOCK)
        left = (end - start) * BLOCK
        while left:
            chunk = stream.read(min(left, 1024 * 1024))
            if not chunk:
                raise ValueError("truncated vendor new-data stream")
            output.write(chunk)
            left -= len(chunk)
    if stream.read(1):
        raise ValueError("vendor new-data stream exceeds transfer list")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def info_once(archive: zipfile.ZipFile, name: str, limit: int) -> zipfile.ZipInfo:
    found = [item for item in archive.infolist() if item.filename == name]
    if len(found) != 1:
        raise ValueError(f"missing or duplicated OTA entry: {name}")
    info = found[0]
    if info.is_dir() or info.flag_bits & 1 or info.file_size > limit:
        raise ValueError(f"unsupported or oversized OTA entry: {name}")
    return info


def extract_vendor(archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path,
                   image_bytes: int, ranges: list[tuple[int, int]]) -> None:
    if not shutil.which("brotli"):
        raise ValueError("brotli decompressor is required")
    errors: list[Exception] = []
    with tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(["brotli", "-d", "-c"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=stderr)
        assert process.stdin is not None and process.stdout is not None

        def feed() -> None:
            try:
                with archive.open(info) as source:
                    shutil.copyfileobj(source, process.stdin, length=1024 * 1024)
                process.stdin.close()
            except (OSError, EOFError, zipfile.BadZipFile, RuntimeError) as exc:
                errors.append(exc)
                try:
                    process.stdin.close()
                except OSError:
                    pass

        thread = threading.Thread(target=feed, daemon=True)
        thread.start()
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as output:
                write_ranges(process.stdout, output, image_bytes, ranges)
            code = process.wait(timeout=120)
            thread.join(timeout=10)
            if thread.is_alive() or errors or code:
                raise ValueError("Brotli decompression or ZIP CRC verification failed")
        except BaseException:
            process.kill()
            process.wait()
            thread.join(timeout=10)
            destination.unlink(missing_ok=True)
            raise
        finally:
            process.stdout.close()


def extract(archive_path: Path, destination: Path, expected_sha256: str, expected_bytes: int) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or not 0 < expected_bytes <= MAX_ARCHIVE:
        raise ValueError("invalid expected archive identity")
    if not archive_path.is_absolute() or not destination.is_absolute():
        raise ValueError("input and output paths must be absolute")
    parent = destination.parent.resolve(strict=True)
    if parent == ROOT or ROOT in parent.parents or destination.exists() or destination.is_symlink():
        raise ValueError("output must be a new directory outside the repository")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(archive_path, flags)
    with os.fdopen(fd, "rb") as raw:
        before = os.fstat(raw.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes:
            raise ValueError("archive is not a regular file of the expected size")
        digest = hashlib.sha256()
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError("archive SHA-256 does not match expected identity")
        raw.seek(0)
        with zipfile.ZipFile(raw) as archive:
            if len(archive.infolist()) > 10000:
                raise ValueError("too many OTA entries")
            transfer_info = info_once(archive, "vendor.transfer.list", MAX_TRANSFER)
            data_info = info_once(archive, "vendor.new.dat.br", MAX_VENDOR_COMPRESSED)
            boot_info = info_once(archive, "boot.img", MAX_BOOT)
            patch = info_once(archive, "vendor.patch.dat", 0)
            if patch.file_size:
                raise ValueError("incremental vendor patch data is not supported")
            image_bytes, ranges = parse_transfer(archive.read(transfer_info))
            if shutil.disk_usage(parent).free < image_bytes + boot_info.file_size + 256 * 1024 * 1024:
                raise ValueError("insufficient temporary space for extracted images")
            destination.mkdir(mode=0o700)
            extract_vendor(archive, data_info, destination / "vendor.img", image_bytes, ranges)
            boot_path = destination / "boot.img"
            outfd = os.open(boot_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(outfd, "wb") as output, archive.open(boot_info) as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if boot_path.stat().st_size != boot_info.file_size:
                raise ValueError("boot image length mismatch")
            after = os.fstat(raw.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("archive changed during inspection")
    report = {"archive_sha256": expected_sha256, "archive_bytes": expected_bytes,
              "vendor_image_sha256": file_digest(destination / "vendor.img"),
              "vendor_image_bytes": image_bytes, "new_block_ranges": len(ranges),
              "boot_image_sha256": file_digest(destination / "boot.img"),
              "boot_image_bytes": boot_info.file_size,
              "scope": "Read-only full block OTA extraction; installed device identity, trust and runtime are not verified."}
    (destination / "extraction-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--bytes", type=int, required=True)
    args = parser.parse_args()
    try:
        report = extract(args.archive, args.out, args.sha256, args.bytes)
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, EOFError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"Block OTA extraction refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
