#!/usr/bin/env python3
"""Reconstruct the exact approved boot-first ZIP from a locked original and XOR delta.

This helper is for recovering a previously built artifact, not building a new
ROM, altering a device, or flashing. It accepts only the pinned original ZIP,
a small integrity-checked delta limited to the original system extent, and the
specific output ZIP SHA-256. The destination must be new. ZIP signature,
recovery compatibility, external AVB and device boot are NOT validated here.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import re
import stat
import sys
import zipfile
import zlib
from pathlib import Path

import build_boot_candidate as original_builder
import verify_preservation as guard

SOURCE_SHA = "454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63"
TARGET_SHA = "300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8"
TARGET_BYTES = 4713790032
OLD_SUPER_SHA = "2e440cfc9023c23c75a1ade13c8d1c32666ff8f3b253d4d7c4f245dd9540f6bf"
NEW_SUPER_SHA = "3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673"
DELTA_JSON_SHA = "62f7ca2f7c60d5ed4d4615986ece584f88db3930c0d5763cfe4ba6656cbb5c4c"
SUPER_BYTES = 8589934592
SYSTEM_BEGIN = 3893362688
SYSTEM_END = 5626232832
BLOCK = 4096
CHUNK = 4 * 1024 * 1024
MAX_DELTA_BYTES = 1024 * 1024
MAX_PATCH_BLOCKS = 4096


class ReconstructionError(Exception):
    pass


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as f:
        while data := f.read(CHUNK):
            digest.update(data)
            count += len(data)
    return count, digest.hexdigest()


def decode_delta(compressed: bytes) -> list[tuple[int, bytes]]:
    if not compressed or len(compressed) > MAX_DELTA_BYTES:
        raise ReconstructionError("Delta compressed size is invalid")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            raw = stream.read(MAX_DELTA_BYTES + 1)
        if len(raw) > MAX_DELTA_BYTES or hashlib.sha256(raw).hexdigest() != DELTA_JSON_SHA:
            raise ReconstructionError("Delta JSON size or SHA-256 mismatch")
        delta = json.loads(raw)
    except (OSError, EOFError, UnicodeError, ValueError) as exc:
        raise ReconstructionError("Delta could not be decoded") from exc
    exact = {
        "schema": "synthetica-boot-first-xor-delta-v1",
        "original_zip_sha256": SOURCE_SHA, "candidate_zip_sha256": TARGET_SHA,
        "original_super_sha256": OLD_SUPER_SHA, "candidate_super_sha256": NEW_SUPER_SHA,
        "super_bytes": SUPER_BYTES, "system_begin": SYSTEM_BEGIN, "system_end": SYSTEM_END,
        "block_bytes": BLOCK,
    }
    if not isinstance(delta, dict) or any(delta.get(k) != v for k, v in exact.items()):
        raise ReconstructionError("Delta identity or permitted extent is incorrect")
    rows = delta.get("blocks")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_PATCH_BLOCKS or delta.get("changed_block_count") != len(rows):
        raise ReconstructionError("Delta block count is invalid")
    changes = []
    previous = -1
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"offset", "xor_zlib_base64"}:
            raise ReconstructionError("Invalid delta block record")
        offset, encoded = row["offset"], row["xor_zlib_base64"]
        if (type(offset) is not int or offset % BLOCK or offset <= previous
                or offset < SYSTEM_BEGIN or offset + BLOCK > SYSTEM_END
                or not isinstance(encoded, str) or len(encoded) > BLOCK * 3):
            raise ReconstructionError("Delta block offset or encoding is invalid")
        try:
            packed = base64.b64decode(encoded, validate=True)
            inflater = zlib.decompressobj()
            mask = inflater.decompress(packed, BLOCK + 1)
            if len(mask) != BLOCK or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail or not any(mask):
                raise ReconstructionError("Delta block is invalid or too large")
        except (ValueError, zlib.error) as exc:
            raise ReconstructionError("Delta block could not be decoded") from exc
        changes.append((offset, mask))
        previous = offset
    return changes


def copy_verified(src, dst, spec: dict) -> None:
    digest = hashlib.sha256()
    count = 0
    while data := src.read(CHUNK):
        count += len(data)
        if count > spec["bytes"]:
            raise ReconstructionError("A source ZIP member exceeded its locked size")
        digest.update(data)
        dst.write(data)
    if count != spec["bytes"] or digest.hexdigest() != spec["sha256"]:
        raise ReconstructionError("A source ZIP member did not match the lock")


def transform_super(src, dst, changes: list[tuple[int, bytes]]) -> None:
    old, new = hashlib.sha256(), hashlib.sha256()
    total = index = 0
    while data := src.read(CHUNK):
        old.update(data)
        end = total + len(data)
        if end > SUPER_BYTES:
            raise ReconstructionError("Source super exceeds its pinned size")
        if index < len(changes) and changes[index][0] < end:
            modified = bytearray(data)
            while index < len(changes) and changes[index][0] < end:
                offset, mask = changes[index]
                within = offset - total
                if within < 0 or within + BLOCK > len(modified):
                    raise ReconstructionError("Delta block crosses an unexpected stream boundary")
                for j, value in enumerate(mask):
                    modified[within + j] ^= value
                index += 1
            data = bytes(modified)
        new.update(data)
        dst.write(data)
        total = end
        if total % (2 * 1024**3) == 0:
            print(f"Reconstructed {total // (1024**3)} / 8 GiB of super", flush=True)
    if (total != SUPER_BYTES or index != len(changes) or old.hexdigest() != OLD_SUPER_SHA
            or new.hexdigest() != NEW_SUPER_SHA):
        raise ReconstructionError("Reconstructed super size or SHA-256 mismatch")


def reconstruct(source: Path, lock_path: Path, compressed_delta: bytes, output: Path) -> dict:
    source, output = source.absolute(), output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ReconstructionError("Output must be a new file in an existing directory")
    lock = guard._read_lock(lock_path)
    if lock["zip_sha256"] != SOURCE_SHA or lock["entries"].get("super.img", {}).get("sha256") != OLD_SUPER_SHA:
        raise ReconstructionError("Baseline lock is not the approved original")
    changes = decode_delta(compressed_delta)
    partial = output.with_name(output.name + ".partial")
    if partial.exists() or partial.is_symlink():
        raise ReconstructionError("Partial output already exists")
    try:
        with guard._open_regular(source)[0] as src:
            before = guard._snapshot(os.fstat(src.fileno()))
            digest = hashlib.sha256()
            while block := src.read(CHUNK):
                digest.update(block)
            guard._check_unchanged(source, src, before)
            if before[2] != lock["zip_bytes"] or digest.hexdigest() != SOURCE_SHA:
                raise ReconstructionError("Source ZIP did not match the locked SHA-256 and size")
            src.seek(0)
            with zipfile.ZipFile(guard._BoundedZipReader(src), "r", allowZip64=True) as zin, \
                    zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED,
                                    allowZip64=True, compresslevel=1) as zout:
                infos = zin.infolist()
                if len(infos) > guard.MAX_ENTRIES:
                    raise ReconstructionError("Too many source ZIP members")
                names = set()
                for info in infos:
                    if (not guard._safe_name(info.filename, info.is_dir()) or info.filename in names
                            or info.flag_bits & 1 or (info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16))):
                        raise ReconstructionError("Unsafe source ZIP member")
                    names.add(info.filename)
                if names != set(lock["entries"]):
                    raise ReconstructionError("Source ZIP members differ from the lock")
                zout.comment = zin.comment
                for info in sorted(infos, key=lambda item: item.header_offset):
                    spec = lock["entries"][info.filename]
                    new_info = original_builder._new_zipinfo(info)
                    if info.is_dir():
                        if not spec.get("directory", False) or info.file_size != 0:
                            raise ReconstructionError("A source directory differs from the lock")
                        zout.writestr(new_info, b"")
                        continue
                    if spec.get("directory", False) or info.file_size != spec["bytes"]:
                        raise ReconstructionError("Source ZIP member type or size differs")
                    with zin.open(info) as member, zout.open(new_info, "w", force_zip64=info.file_size >= zipfile.ZIP64_LIMIT) as dest:
                        if info.filename == "super.img":
                            transform_super(member, dest, changes)
                        else:
                            copy_verified(member, dest, spec)
            guard._check_unchanged(source, src, before)
        actual_bytes, actual_sha = file_digest(partial)
        if actual_bytes != TARGET_BYTES or actual_sha != TARGET_SHA:
            raise ReconstructionError("Reconstructed ZIP does not match the previously verified candidate")
        os.link(partial, output, follow_symlinks=False)  # fails rather than overwriting an output
        partial.unlink()
        return {"status": "exact_candidate_reconstructed_not_device_tested", "file": output.name,
                "bytes": actual_bytes, "sha256": actual_sha, "changed_blocks": len(changes)}
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("delta", type=Path, help="gzip-compressed, SHA-locked delta")
    parser.add_argument("output", type=Path)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 11, 2) or zlib.ZLIB_RUNTIME_VERSION != "1.2.13":
        print("Reconstruction needs Python 3.11.2 with zlib 1.2.13 for exact ZIP bytes.", file=sys.stderr)
        return 1
    try:
        if args.delta.lstat().st_size > MAX_DELTA_BYTES:
            raise ReconstructionError("Delta file is too large")
        result = reconstruct(args.source, args.lock, args.delta.read_bytes(), args.output)
    except (ReconstructionError, guard.AuditError, original_builder.BuildError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Reconstruction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
