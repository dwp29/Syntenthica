#!/usr/bin/env python3
"""Read-only structural checks for Android boot v2 and DTBO images.

The parser never creates, modifies, signs, or flashes images. Its checksums
can compare already-existing copies, but say nothing about AVB verification,
bootloader state, overlay selection, kernel execution, or device behavior.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import struct

MAX_IMAGE = 1024 * 1024 * 1024
MAX_FDT = 16 * 1024 * 1024
MAX_DTBO_ENTRIES = 4096
BLOCK = 1024 * 1024
FDT_MAGIC = 0xD00DFEED
DTBO_MAGIC = 0xD7B7AB1E


@contextmanager
def readonly_file(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_IMAGE:
            raise ValueError("image must be a bounded regular file")
        yield f, before.st_size
        after = os.fstat(f.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("image changed while being inspected")


def read_exact(f, offset: int, size: int, file_size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise ValueError("image field outside file bounds")
    f.seek(offset)
    data = f.read(size)
    if len(data) != size:
        raise ValueError("short image read")
    return data


def hash_range(f, offset: int, size: int, file_size: int, *hashers) -> None:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise ValueError("image section outside file bounds")
    f.seek(offset)
    left = size
    while left:
        data = f.read(min(left, BLOCK))
        if not data:
            raise ValueError("short image section")
        for digest in hashers:
            digest.update(data)
        left -= len(data)


def hash_section(f, offset: int, size: int, file_size: int, legacy_id) -> dict:
    sha = hashlib.sha256()
    hash_range(f, offset, size, file_size, sha, legacy_id)
    legacy_id.update(struct.pack("<I", size))
    return {"offset": offset, "bytes": size, "sha256": sha.hexdigest() if size else None}


def footer(f, size: int) -> dict:
    """Recognize an end-of-file AVB footer, without authenticating vbmeta."""
    if size < 64:
        return {"footer_at_end": False}
    data = read_exact(f, size - 64, 64, size)
    if data[:4] != b"AVBf":
        return {"footer_at_end": False}
    _, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack(
        ">4sIIQQQ28s", data)
    if original_size > vbmeta_offset or vbmeta_offset + vbmeta_size > size - 64:
        raise ValueError("invalid AVB footer ranges")
    return {"footer_at_end": True, "version": f"{major}.{minor}",
            "original_image_size": original_size, "vbmeta_offset": vbmeta_offset,
            "vbmeta_bytes": vbmeta_size}


def inspect_fdt(blob: bytes) -> dict:
    """Validate bounded FDT v17 header, reservation map and structure tokens."""
    if len(blob) < 40 or len(blob) > MAX_FDT:
        raise ValueError("invalid FDT size")
    (magic, total, struct_off, strings_off, reserve_off, version, compatible_version,
     _, strings_size, struct_size) = struct.unpack_from(">10I", blob)
    if (magic != FDT_MAGIC or total < 40 or total > len(blob) or version != 17
            or compatible_version > version or struct_off % 4 or reserve_off % 8
            or min(struct_off, strings_off, reserve_off) < 40
            or struct_off + struct_size > total or strings_off + strings_size > total):
        raise ValueError("invalid or unsupported FDT header")
    if struct_off < strings_off + strings_size and strings_off < struct_off + struct_size:
        raise ValueError("overlapping FDT structure and string blocks")
    pos = reserve_off
    while True:
        if pos + 16 > total:
            raise ValueError("unterminated FDT reservation map")
        start, length = struct.unpack_from(">QQ", blob, pos)
        pos += 16
        if (start, length) == (0, 0):
            break
    if (reserve_off < struct_off + struct_size and struct_off < pos) or (
            reserve_off < strings_off + strings_size and strings_off < pos):
        raise ValueError("FDT reservation map overlaps another block")
    structure = blob[struct_off:struct_off + struct_size]
    strings = blob[strings_off:strings_off + strings_size]
    pos, depth, nodes, properties, roots = 0, 0, 0, 0, 0
    while pos + 4 <= len(structure):
        token = struct.unpack_from(">I", structure, pos)[0]
        pos += 4
        if token == 1:  # FDT_BEGIN_NODE
            if depth == 0:
                roots += 1
            end = structure.find(b"\0", pos)
            if end < 0:
                raise ValueError("unterminated FDT node name")
            pos = (end + 4) & ~3
            if pos > len(structure):
                raise ValueError("truncated FDT node name")
            depth += 1
            nodes += 1
        elif token == 2:  # FDT_END_NODE
            if depth == 0:
                raise ValueError("unbalanced FDT node")
            depth -= 1
        elif token == 3:  # FDT_PROP
            if depth == 0 or pos + 8 > len(structure):
                raise ValueError("invalid FDT property")
            length, nameoff = struct.unpack_from(">II", structure, pos)
            pos += 8
            if nameoff >= len(strings) or strings.find(b"\0", nameoff) < 0:
                raise ValueError("invalid FDT property name")
            pos = (pos + length + 3) & ~3
            if pos > len(structure):
                raise ValueError("truncated FDT property")
            properties += 1
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            if depth != 0 or roots != 1:
                raise ValueError("unbalanced or ambiguous FDT root")
            if any(structure[pos:]):
                raise ValueError("unexpected data after FDT end token")
            return {"bytes": total, "sha256": hashlib.sha256(blob[:total]).hexdigest(),
                    "version": version, "nodes": nodes, "properties": properties}
        else:
            raise ValueError("invalid FDT structure token")
    raise ValueError("missing FDT end token")


def inspect_boot(path: Path) -> dict:
    """Inspect only Android boot header v2; reject other layouts rather than guess."""
    with readonly_file(path) as (f, file_size):
        head = read_exact(f, 0, 1660, file_size)
        if head[:8] != b"ANDROID!":
            raise ValueError("not an Android boot image")
        (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr,
         tags_addr, page, version, os_version) = struct.unpack_from("<10I", head, 8)
        if version != 2:
            raise ValueError("only Android boot header v2 is supported")
        if page < 2048 or page > 65536 or page & (page - 1) or not kernel_size:
            raise ValueError("invalid boot page or kernel size")
        recovery_size, recovery_offset, header_size = struct.unpack_from("<IQI", head, 1632)
        dtb_size, dtb_addr = struct.unpack_from("<IQ", head, 1648)
        if header_size != 1660 or header_size > page:
            raise ValueError("invalid v2 boot header size")
        aligned = lambda n: (n + page - 1) // page * page
        pos = page
        offsets = {}
        for name, length in (("kernel", kernel_size), ("ramdisk", ramdisk_size),
                             ("second", second_size), ("recovery_dtbo", recovery_size),
                             ("dtb", dtb_size)):
            offsets[name] = (pos, length)
            pos += aligned(length)
        if pos > file_size:
            raise ValueError("boot sections exceed file bounds")
        if ((recovery_size and recovery_offset != offsets["recovery_dtbo"][0])
                or (not recovery_size and recovery_offset != 0)):
            raise ValueError("unexpected recovery DTBO offset")
        if dtb_size > MAX_FDT:
            raise ValueError("boot DTB exceeds inspection limit")
        legacy_id = hashlib.sha1()
        sections = {name: hash_section(f, off, length, file_size, legacy_id)
                    for name, (off, length) in offsets.items()}
        computed_id = legacy_id.digest() + b"\0" * 12
        dtb = inspect_fdt(read_exact(f, *offsets["dtb"], file_size)) if dtb_size else None
        magic = read_exact(f, offsets["ramdisk"][0], min(ramdisk_size, 6), file_size)
        ramdisk_format = ("newc_cpio" if magic in (b"070701", b"070702") else
                          "gzip" if magic.startswith(b"\x1f\x8b") else
                          "lz4_frame" if magic.startswith(b"\x04\x22\x4d\x18") else
                          "lz4_legacy" if magic.startswith(b"\x02\x21\x4c\x18") else
                          "empty" if not magic else "unknown")
        full = hashlib.sha256()
        hash_range(f, 0, file_size, file_size, full)
        avb = footer(f, file_size)
        if avb["footer_at_end"] and avb["original_image_size"] < pos:
            raise ValueError("AVB original image is shorter than the boot sections")
        return {
            "file_bytes": file_size,
            "file_sha256": full.hexdigest(),
            "header_version": version,
            "header_bytes": header_size,
            "page_size": page,
            "kernel_address": kernel_addr,
            "ramdisk_address": ramdisk_addr,
            "second_address": second_addr,
            "tags_address": tags_addr,
            "dtb_address": dtb_addr,
            "os_version_encoded": os_version,
            "board_field_sha256": hashlib.sha256(head[48:64]).hexdigest(),
            "cmdline_fields_sha256": hashlib.sha256(head[64:576] + head[608:1632]).hexdigest(),
            "legacy_boot_id_matches_sha1": head[576:608] == computed_id,
            "sections": sections,
            "ramdisk_format_guess": ramdisk_format,
            "dtb": dtb,
            "avb": avb,
            "scope": "Checksums and structure only; the legacy ID and AVB footer are not signature or boot verification.",
        }


def inspect_dtbo(path: Path) -> dict:
    with readonly_file(path) as (f, file_size):
        data = read_exact(f, 0, 32, file_size)
        magic, total, header_size, entry_size, count, entries_off, page, version = struct.unpack(">8I", data)
        if (magic != DTBO_MAGIC or version != 0 or not 32 <= header_size <= entries_off
                or entry_size < 32 or not 0 < count <= MAX_DTBO_ENTRIES
                or entries_off + entry_size * count > total or total > file_size
                or page < 512 or page > 65536 or page & (page - 1)):
            raise ValueError("invalid or unsupported Android DTBO table")
        entries, ranges = [], []
        table_end = entries_off + entry_size * count
        for i in range(count):
            row = read_exact(f, entries_off + i * entry_size, 32, file_size)
            length, off, ident, revision, *custom = struct.unpack(">8I", row)
            if length < 40 or length > MAX_FDT or off < table_end or off + length > total:
                raise ValueError("DTBO entry outside valid bounds")
            fdt = inspect_fdt(read_exact(f, off, length, file_size))
            entries.append({"offset": off, "bytes": length, "id": ident, "revision": revision,
                            "custom": custom, "fdt": fdt})
            ranges.append((off, off + length))
        overlaps = sum(a < d and c < b for i, (a, b) in enumerate(ranges)
                       for c, d in ranges[i + 1:])
        full = hashlib.sha256()
        hash_range(f, 0, file_size, file_size, full)
        avb = footer(f, file_size)
        if avb["footer_at_end"] and avb["original_image_size"] < total:
            raise ValueError("AVB original image is shorter than the DTBO table")
        return {"file_bytes": file_size, "file_sha256": full.hexdigest(), "table_bytes": total,
                "entry_count": count, "entry_size": entry_size, "page_size": page,
                "entries": entries, "overlapping_entry_pairs": overlaps,
                "avb": avb,
                "scope": "Entry structure only; active overlay and AVB trust require separate evidence."}


def compare_boot(reference: dict, candidate: dict, target_kernel_sha256: str) -> dict:
    """Compare existing images only. Identical bytes are not proof of safe boot."""
    fields = ("header_version", "header_bytes", "page_size", "kernel_address", "ramdisk_address",
              "second_address", "tags_address", "dtb_address", "os_version_encoded",
              "board_field_sha256", "cmdline_fields_sha256")
    stable_fields = {name: reference[name] == candidate[name] for name in fields}
    preserved = {name: (reference["sections"][name]["bytes"], reference["sections"][name]["sha256"])
                       == (candidate["sections"][name]["bytes"], candidate["sections"][name]["sha256"])
                 for name in ("ramdisk", "second", "recovery_dtbo", "dtb")}
    return {
        "stable_header_fields_match": stable_fields,
        "non_kernel_sections_match": preserved,
        "candidate_kernel_equals_bundle_image": candidate["sections"]["kernel"]["sha256"] == target_kernel_sha256,
        "candidate_legacy_boot_id_matches": candidate["legacy_boot_id_matches_sha1"],
        "scope": "Read-only byte comparison; no AVB verification, installer, boot, or device test.",
    }
