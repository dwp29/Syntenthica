#!/usr/bin/env python3
"""Synthetic raw-super metadata checks, never a real image or device."""
from __future__ import annotations

import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("synthetica_lp", ROOT / "research/hyperos4/lp_metadata.py")
assert SPEC and SPEC.loader
lp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lp)


def name(value: str) -> bytes:
    return value.encode("ascii").ljust(36, b"\0")


def geometry(max_size=4096, slots=1, block_size=4096):
    data = bytearray(struct.pack("<II", lp.GEOMETRY_MAGIC, 52) + b"\0" * 32 + struct.pack("<III", max_size, slots, block_size))
    data[8:40] = hashlib.sha256(data).digest()
    return data


def metadata(*, extent_source=0, minor=0, system_sector=80, vendor_sector=96, device_bytes=131072):
    partitions = (
        name("system") + struct.pack("<IIII", 1, 0, 1, 0)
        + name("vendor") + struct.pack("<IIII", 1, 1, 1, 0)
    )
    extents = struct.pack("<QIQI", 8, 0, system_sector, extent_source) + struct.pack("<QIQI", 16, 0, vendor_sector, 0)
    groups = name("main") + struct.pack("<IQ", 0, 100_000)
    devices = struct.pack("<QIIQ", 48, 4096, 0, device_bytes) + name("super") + struct.pack("<I", 0)
    tables = partitions + extents + groups + devices
    size = 128 if minor < 2 else 256
    header = bytearray(size)
    struct.pack_into("<IHHI", header, 0, lp.HEADER_MAGIC, 10, minor, size)
    struct.pack_into("<I", header, 44, len(tables))
    header[48:80] = hashlib.sha256(tables).digest()
    cursor = 0
    for offset, count, entry_size in [(80, 2, 52), (92, 2, 24), (104, 1, 48), (116, 1, 64)]:
        struct.pack_into("<III", header, offset, cursor, count, entry_size)
        cursor += count * entry_size
    header[12:44] = hashlib.sha256(header).digest()
    return bytes(header) + tables


def image():
    data = bytearray(24 * 1024)
    geo, meta = geometry(), metadata()
    data[4096:4096 + len(geo)] = geo
    data[8192:8192 + len(geo)] = geo
    data[12288:12288 + len(meta)] = meta
    data[16384:16384 + len(meta)] = meta
    return data


class LPMetadataTests(unittest.TestCase):
    def test_valid_raw_super_geometry_primary_backup_and_partitions(self):
        result = lp.inspect_raw_super(bytes(image()), image_bytes=131072)
        self.assertEqual(result["geometry_primary"]["status"], "valid")
        self.assertEqual(result["geometry_backup"]["status"], "valid")
        self.assertTrue(result["geometry_copies_match"])
        slot = result["metadata_slots"][0]
        self.assertTrue(slot["copies_match"])
        primary = slot["primary"]
        self.assertTrue(primary["header_sha256_valid"])
        self.assertTrue(primary["tables_sha256_valid"])
        self.assertEqual(primary["version"], "10.0")
        parts = {p["name"]: p for p in primary["partitions"]}
        self.assertEqual(parts["system"]["bytes"], 4096)
        self.assertEqual(parts["vendor"]["bytes"], 8192)
        self.assertEqual(parts["system"]["first_extent"]["target_sector"], 80)
        self.assertEqual(primary["block_devices"][0]["size_bytes_declared"], 131072)

    def test_primary_geometry_corruption_falls_back_to_backup(self):
        data = image()
        data[4096 + 20] ^= 1
        result = lp.inspect_raw_super(bytes(data), image_bytes=131072)
        self.assertIn("SHA-256", result["geometry_primary"]["error"])
        self.assertEqual(result["geometry_backup"]["status"], "valid")
        self.assertIsNone(result["geometry_copies_match"])
        self.assertEqual(result["metadata_slots"][0]["primary"]["status"], "valid")

    def test_backup_table_corruption_is_not_marked_valid(self):
        data = image()
        data[16384 + 128] ^= 1
        slot = lp.inspect_raw_super(bytes(data), image_bytes=131072)["metadata_slots"][0]
        self.assertEqual(slot["primary"]["status"], "valid")
        self.assertIn("table SHA-256", slot["backup"]["error"])
        self.assertIsNone(slot["copies_match"])

    def test_header_corruption_is_rejected(self):
        data = image()
        data[12288 + 20] ^= 1
        slot = lp.inspect_raw_super(bytes(data), image_bytes=131072)["metadata_slots"][0]
        self.assertIn("header SHA-256", slot["primary"]["error"])
        self.assertEqual(slot["backup"]["status"], "valid")

    def test_checksums_do_not_hide_invalid_extent_reference(self):
        data = image()
        invalid = metadata(extent_source=7)
        data[12288:12288 + len(invalid)] = invalid
        primary = lp.inspect_raw_super(bytes(data), image_bytes=131072)["metadata_slots"][0]["primary"]
        self.assertIn("outside its declared device", primary["error"])

    def test_extent_cannot_point_outside_available_image(self):
        primary = lp.inspect_raw_super(bytes(image()), image_bytes=42000)["metadata_slots"][0]["primary"]
        self.assertIn("outside the available super image", primary["error"])

    def test_truncated_prefix_is_reported_not_assumed_valid(self):
        result = lp.inspect_raw_super(bytes(image()[:14000]), image_bytes=131072)
        slot = result["metadata_slots"][0]
        self.assertEqual(slot["primary"]["status"], "valid")
        self.assertIn("outside the captured prefix", slot["backup"]["error"])

    def test_excessive_geometry_is_not_followed(self):
        data = image()
        geo = geometry(slots=100_000)
        data[4096:4096 + len(geo)] = geo
        data[8192:8192 + len(geo)] = geo
        result = lp.inspect_raw_super(bytes(data), image_bytes=131072)
        self.assertIn("slot count", result["geometry_primary"]["error"])
        self.assertEqual(result["metadata_slots"], [])

    def test_prefix_larger_than_bound_is_rejected(self):
        with self.assertRaises(ValueError):
            lp.inspect_raw_super(b"\0" * (lp.MAX_PREFIX + 1), image_bytes=0)

    def test_unsupported_version_does_not_parse_as_valid(self):
        data = image()
        unsupported = metadata(minor=3)
        data[12288:12288 + len(unsupported)] = unsupported
        primary = lp.inspect_raw_super(bytes(data), image_bytes=131072)["metadata_slots"][0]["primary"]
        self.assertIn("unsupported logical-partition metadata version", primary["error"])

    def test_streamed_filesystem_magic_inside_prefix_and_chunk_boundaries(self):
        data = bytearray(131072)
        data[:len(image())] = image()
        data[80 * 512 + 1080:80 * 512 + 1082] = b"\x53\xef"  # ext4
        data[96 * 512 + 1024:96 * 512 + 1028] = b"\xe2\xe1\xf5\xe0"  # erofs
        scanner = lp.RawSuperScanner(len(data))
        for offset in range(0, len(data), 1001):
            scanner.feed(data[offset:offset + 1001])
        result = scanner.finish()
        probes = {p["partition"]: p for p in result["filesystem_magic_probes"]}
        self.assertEqual(probes["system"]["format"], "ext4")
        self.assertEqual(probes["vendor"]["format"], "erofs")
        self.assertIn("not validated", probes["system"]["reason"])

    def test_streamed_magic_beyond_four_megabyte_prefix(self):
        size = 6 * 1024 * 1024
        data = bytearray(size)
        data[:len(image())] = image()
        meta = metadata(system_sector=9000, vendor_sector=9100, device_bytes=size)
        data[12288:12288 + len(meta)] = meta
        data[16384:16384 + len(meta)] = meta
        data[9000 * 512 + 1080:9000 * 512 + 1082] = b"\x53\xef"
        data[9100 * 512 + 1024:9100 * 512 + 1028] = b"\x10\x20\xf5\xf2"
        scanner = lp.RawSuperScanner(size)
        for offset in range(0, len(data), 65537):
            scanner.feed(data[offset:offset + 65537])
        result = scanner.finish()
        self.assertEqual(len(scanner.prefix), lp.MAX_PREFIX)
        probes = {p["partition"]: p for p in result["filesystem_magic_probes"]}
        self.assertEqual(probes["system"]["format"], "ext4")
        self.assertEqual(probes["vendor"]["format"], "f2fs")

    def test_stream_scanner_does_not_accept_incomplete_or_oversized_input(self):
        scanner = lp.RawSuperScanner(16)
        scanner.feed(b"123")
        with self.assertRaises(ValueError):
            scanner.finish()
        with self.assertRaises(ValueError):
            scanner.feed(b"a" * 14)

    def test_slot_both_valid_but_different_tables_do_not_match(self):
        data = image()
        changed = bytearray(metadata())
        # Alter a group name, then recompute both hashes as a separate valid copy.
        pos = 128 + 2 * 52 + 2 * 24
        changed[pos:pos + 4] = b"othr"
        changed[48:80] = hashlib.sha256(changed[128:]).digest()
        changed[12:44] = b"\0" * 32
        changed[12:44] = hashlib.sha256(changed[:128]).digest()
        data[16384:16384 + len(changed)] = changed
        slot = lp.inspect_raw_super(bytes(data), image_bytes=131072)["metadata_slots"][0]
        self.assertEqual(slot["backup"]["status"], "valid")
        self.assertFalse(slot["copies_match"])


if __name__ == "__main__":
    unittest.main()
