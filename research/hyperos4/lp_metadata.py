#!/usr/bin/env python3
"""Bounded, read-only inspection of raw Android logical-partition metadata.

The parser uses only an already-collected prefix. It checks SHA-256 fields,
versions, table bounds and basic extent references, but is not a substitute
for liblp, lpdump, filesystem validation, or inspection of the actual device.
Structure and offsets are documented by AOSP's liblp/metadata_format.h.
"""
from __future__ import annotations

import hashlib
import re
import struct

GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
GEOMETRY_BYTES = 4096
RESERVED_BYTES = 4096
METADATA_START = RESERVED_BYTES + 2 * GEOMETRY_BYTES
MAX_PREFIX = 4 * 1024 * 1024
MAX_SLOTS = 8
MAX_ENTRIES = 512
SECTOR_BYTES = 512


class LPError(ValueError):
    """Metadata is unsupported, unavailable within the prefix, or malformed."""


def _require(data: bytes, offset: int, size: int, what: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise LPError(f"{what} is outside the captured prefix")
    return data[offset : offset + size]


def _named(raw: bytes, what: str) -> str:
    head, separator, tail = raw.partition(b"\0")
    if separator and any(tail):
        raise LPError(f"{what} contains nonzero bytes after terminator")
    try:
        text = head.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LPError(f"{what} is not ASCII") from exc
    if not re.fullmatch(r"[A-Za-z0-9_]+", text):
        raise LPError(f"{what} has unsupported characters")
    return text


def _geometry(prefix: bytes, offset: int) -> dict:
    data = _require(prefix, offset, 52, "geometry")
    magic, struct_size = struct.unpack_from("<II", data)
    if magic != GEOMETRY_MAGIC or struct_size != 52:
        raise LPError("unrecognized geometry magic or structure size")
    checksum = data[8:40]
    hashed = data[:8] + b"\0" * 32 + data[40:]
    if hashlib.sha256(hashed).digest() != checksum:
        raise LPError("geometry SHA-256 mismatch")
    max_size, slots, block_size = struct.unpack_from("<III", data, 40)
    if max_size < 512 or max_size % SECTOR_BYTES or max_size > MAX_PREFIX:
        raise LPError("unsupported metadata allocation size")
    if not 1 <= slots <= MAX_SLOTS:
        raise LPError("unsupported metadata slot count")
    if block_size < SECTOR_BYTES or block_size % SECTOR_BYTES:
        raise LPError("invalid logical block size")
    return {
        "metadata_max_bytes": max_size,
        "slot_count": slots,
        "logical_block_bytes": block_size,
        "sha256_valid": True,
    }


def _metadata(prefix: bytes, offset: int, max_size: int, image_bytes: int) -> dict:
    fixed = _require(prefix, offset, 128, "metadata header")
    magic, major, minor, header_size = struct.unpack_from("<IHHI", fixed)
    if magic != HEADER_MAGIC:
        raise LPError("metadata header magic mismatch")
    if major != 10 or minor > 2:
        raise LPError("unsupported logical-partition metadata version")
    expected_header = 128 if minor < 2 else 256
    if header_size != expected_header or header_size > max_size:
        raise LPError("unsupported metadata header size")
    header = _require(prefix, offset, header_size, "metadata header")
    expected_header_sha = header[12:44]
    clean_header = header[:12] + b"\0" * 32 + header[44:]
    if hashlib.sha256(clean_header).digest() != expected_header_sha:
        raise LPError("metadata header SHA-256 mismatch")
    table_size = struct.unpack_from("<I", header, 44)[0]
    if table_size > max_size - header_size:
        raise LPError("metadata table exceeds allocated slot")
    tables = _require(prefix, offset + header_size, table_size, "metadata tables")
    if hashlib.sha256(tables).digest() != header[48:80]:
        raise LPError("metadata table SHA-256 mismatch")

    descriptors = {}
    for name, desc_offset, entry_size in (
        ("partitions", 80, 52), ("extents", 92, 24), ("groups", 104, 48), ("block_devices", 116, 64)
    ):
        start, count, size = struct.unpack_from("<III", header, desc_offset)
        if size != entry_size or count > MAX_ENTRIES or start + count * size > len(tables):
            raise LPError(f"invalid {name} table descriptor")
        descriptors[name] = (start, count, size)

    def rows(name: str):
        start, count, size = descriptors[name]
        for index in range(count):
            yield tables[start + index * size : start + (index + 1) * size]

    groups = []
    for row in rows("groups"):
        flags, maximum = struct.unpack_from("<IQ", row, 36)
        groups.append({"name": _named(row[:36], "group name"), "flags": flags, "maximum_bytes": maximum})
    if len({group["name"] for group in groups}) != len(groups):
        raise LPError("duplicate group names")

    devices = []
    for row in rows("block_devices"):
        first_sector, alignment, alignment_offset, size = struct.unpack_from("<QIIQ", row)
        name = _named(row[24:60], "block device name")
        flags = struct.unpack_from("<I", row, 60)[0]
        if size <= 0 or first_sector * SECTOR_BYTES > size:
            raise LPError("invalid block-device size")
        devices.append({
            "name": name, "size_bytes_declared": size, "first_sector": first_sector,
            "alignment_bytes": alignment, "alignment_offset_bytes": alignment_offset, "flags": flags,
        })
    if not devices or len({device["name"] for device in devices}) != len(devices):
        raise LPError("missing or duplicate block-device names")

    extents = []
    for row in rows("extents"):
        sectors, kind, target, source = struct.unpack("<QIQI", row)
        if kind == 0:
            if source >= len(devices) or (target + sectors) * SECTOR_BYTES > devices[source]["size_bytes_declared"]:
                raise LPError("linear extent points outside its declared device")
            if source == 0 and (target + sectors) * SECTOR_BYTES > image_bytes:
                raise LPError("linear extent points outside the available super image")
        elif kind == 1:
            if source != 0 or target != 0:
                raise LPError("zero extent has a nonzero target")
        else:
            raise LPError("unsupported extent type")
        extents.append({"sectors": sectors, "type": kind, "target_sector": target, "source_index": source})

    partitions = []
    for row in rows("partitions"):
        name = _named(row[:36], "partition name")
        attributes, first, count, group = struct.unpack_from("<IIII", row, 36)
        if first + count > len(extents) or group >= len(groups):
            raise LPError("partition refers outside extent/group tables")
        selected = extents[first : first + count]
        partitions.append({
            "name": name, "attributes": attributes, "group": groups[group]["name"],
            "bytes": sum(extent["sectors"] * SECTOR_BYTES for extent in selected),
            "extent_count": count, "first_extent": selected[0] if selected else None,
        })
    if len({partition["name"] for partition in partitions}) != len(partitions):
        raise LPError("duplicate partition names")
    return {
        "version": f"{major}.{minor}",
        "header_sha256_valid": True,
        "tables_sha256_valid": True,
        "header_and_tables_sha256": hashlib.sha256(header + tables).hexdigest(),
        "groups": groups,
        "block_devices": devices,
        "partitions": partitions,
        # A metadata claim about a block device is not a measurement of real hardware.
        "image_bytes": image_bytes,
    }


def inspect_raw_super(prefix: bytes, image_bytes: int) -> dict:
    """Inspect primary/backup metadata copies using at most MAX_PREFIX bytes."""
    if len(prefix) > MAX_PREFIX:
        raise ValueError("prefix exceeds safety bound")
    result = {
        "scope": "captured raw super prefix only",
        "geometry_primary": None,
        "geometry_backup": None,
        "geometry_copies_match": None,
        "metadata_slots": [],
        "limitations": [
            "Checks are bounded and do not prove full liblp consistency, filesystem integrity or bootability.",
            "Block-device sizes come from image metadata, not a physical device measurement.",
        ],
    }
    for name, offset in (("geometry_primary", RESERVED_BYTES), ("geometry_backup", RESERVED_BYTES + GEOMETRY_BYTES)):
        try:
            result[name] = {"status": "valid", **_geometry(prefix, offset)}
        except LPError as exc:
            result[name] = {"status": "unavailable_or_invalid", "error": str(exc)}
    a, b = result["geometry_primary"], result["geometry_backup"]
    if a["status"] == "valid" and b["status"] == "valid":
        result["geometry_copies_match"] = a == b
    chosen = a if a["status"] == "valid" else b
    if chosen["status"] != "valid":
        return result
    alloc, slots = chosen["metadata_max_bytes"], chosen["slot_count"]
    for slot in range(slots):
        item = {"slot": slot}
        for name, offset in (
            ("primary", METADATA_START + alloc * slot),
            ("backup", METADATA_START + alloc * slots + alloc * slot),
        ):
            try:
                item[name] = {"status": "valid", **_metadata(prefix, offset, alloc, image_bytes)}
            except LPError as exc:
                item[name] = {"status": "unavailable_or_invalid", "error": str(exc)}
        item["copies_match"] = (
            item["primary"]["header_and_tables_sha256"] == item["backup"]["header_and_tables_sha256"]
            if item["primary"]["status"] == item["backup"]["status"] == "valid" else None
        )
        result["metadata_slots"].append(item)
    return result


class RawSuperScanner:
    """Capture a bounded prefix and a few filesystem-magic bytes in one pass.

    Magic probes only use the first linear extent of each partition in primary
    slot 0 (or its backup if primary is invalid) and source block device 0.
    Classification is indicative only; no filesystem is mounted or validated.
    """

    def __init__(self, image_bytes: int):
        if image_bytes <= 0:
            raise ValueError("image size must be positive")
        self.image_bytes = image_bytes
        self.position = 0
        self.prefix = bytearray()
        self.metadata = None
        self.initialized = False
        self.windows: list[dict] = []
        self.probe_info: list[dict] = []

    def _initialize(self) -> None:
        if self.initialized:
            return
        self.initialized = True
        if not (self.prefix[4096:4100] == b"gDla" or self.prefix[8192:8196] == b"gDla"):
            return
        self.metadata = inspect_raw_super(bytes(self.prefix), self.image_bytes)
        slots = self.metadata["metadata_slots"]
        if not slots:
            return
        slot = slots[0]
        source = "primary" if slot["primary"]["status"] == "valid" else "backup"
        data = slot[source]
        if data["status"] != "valid":
            return
        for partition in data["partitions"]:
            first = partition["first_extent"]
            item = {"partition": partition["name"], "metadata_copy": source, "format": None, "reason": None}
            self.probe_info.append(item)
            if not first:
                item["reason"] = "partition has no extents"
                continue
            if first["type"] != 0 or first["source_index"] != 0:
                item["reason"] = "first extent is not linear on the captured super device"
                continue
            if first["sectors"] * SECTOR_BYTES < 1082:
                item["reason"] = "first extent is too small for the magic offsets"
                continue
            base = first["target_sector"] * SECTOR_BYTES
            for kind, offset, size in (("f2fs_erofs", 1024, 4), ("ext4", 1080, 2)):
                self.windows.append({
                    "item": item, "kind": kind, "start": base + offset,
                    "data": bytearray(size), "filled": bytearray(size),
                })
        self._observe(0, self.prefix)

    def _observe(self, start: int, block: bytes | bytearray) -> None:
        end = start + len(block)
        for window in self.windows:
            target = window["start"]
            begin, stop = max(start, target), min(end, target + len(window["data"]))
            if begin < stop:
                dest, src = begin - target, begin - start
                amount = stop - begin
                window["data"][dest : dest + amount] = block[src : src + amount]
                window["filled"][dest : dest + amount] = b"\x01" * amount

    def feed(self, block: bytes) -> None:
        if self.position + len(block) > self.image_bytes:
            raise ValueError("stream exceeds declared super image size")
        start = self.position
        if len(self.prefix) < MAX_PREFIX:
            self.prefix.extend(block[: MAX_PREFIX - len(self.prefix)])
        if len(self.prefix) >= min(MAX_PREFIX, self.image_bytes):
            self._initialize()
        if self.initialized:
            self._observe(start, block)
        self.position += len(block)

    def finish(self) -> dict:
        if self.position != self.image_bytes:
            raise ValueError("stream ended before declared super image size")
        self._initialize()
        for item in self.probe_info:
            selected = [window for window in self.windows if window["item"] is item]
            if not selected:
                continue
            if not all(all(window["filled"]) for window in selected):
                item["reason"] = "magic offsets not read"
                continue
            matches = []
            for window in selected:
                raw = bytes(window["data"])
                if window["kind"] == "ext4" and raw == b"\x53\xef":
                    matches.append("ext4")
                elif window["kind"] == "f2fs_erofs":
                    if raw == b"\xe2\xe1\xf5\xe0":
                        matches.append("erofs")
                    elif raw == b"\x10\x20\xf5\xf2":
                        matches.append("f2fs")
            item["format"] = matches[0] if len(matches) == 1 else ("ambiguous" if matches else "unknown")
            item["reason"] = "magic bytes only; filesystem not validated"
        return {
            "metadata": self.metadata,
            "filesystem_magic_probes": self.probe_info,
            "filesystem_limitations": "Magic-only probes are not filesystem, fstab, hardware, or boot validation.",
        }
