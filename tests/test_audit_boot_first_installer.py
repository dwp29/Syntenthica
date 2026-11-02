#!/usr/bin/env python3
"""Synthetic, host-only tests for the read-only installer audit."""
from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import audit_boot_first_installer as audit


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_zip(path: Path, *, duplicate: bool = False) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(audit.SCRIPT, b"installer")
            z.writestr(audit.BINARY, b"updater")
            z.writestr(audit.METADATA, b"ota-property-files=metadata:1:1,metadata.pb:2:1\n")
            z.writestr(audit.METADATA_PB, b"proto")
            with z.open("super.img", "w", force_zip64=True) as f:
                f.write(b"small synthetic super")
            z.writestr("boot.img", b"boot")
            z.writestr("dtbo.img", b"dtbo")
            if duplicate:
                z.writestr("boot.img", b"another boot")
    # Python can keep 32-bit size fields for a small force_zip64 fixture.
    # Mark both local fields as ZIP64 sentinels while retaining its valid extra.
    with zipfile.ZipFile(path) as z:
        offset = z.getinfo("super.img").header_offset
    data = bytearray(path.read_bytes())
    struct.pack_into("<II", data, offset + 18, 0xFFFFFFFF, 0xFFFFFFFF)
    path.write_bytes(data)


def fake_elf_with_calls() -> bytes:
    data = bytearray(0x140)
    ident = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into("<16sHHIQQQIHHHHHH", data, 0, ident, 2, 183, 1, 0x1000, 64, 0,
                     0, 64, 56, 1, 64, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0x100, 0x1000, 0, 16, 16, 0x1000)
    struct.pack_into("<IIII", data, 0x100, 0x94000008, 0x94000003, 0xD503201F, 0xD65F03C0)
    return bytes(data)


class AuditPrimitivesTests(unittest.TestCase):
    def test_extra_fields_and_rejection(self):
        self.assertEqual(audit.extra_fields(b"\x01\x00\x02\x00ab"), [(1, b"ab")])
        with self.assertRaises(audit.AuditError):
            audit.extra_fields(b"\x01\x00\x03\x00ab")
        with self.assertRaises(audit.AuditError):
            audit.extra_fields(b"\x01\x00\x00\x00\x01\x00\x00\x00")

    def test_standalone_write_is_not_mistaken_for_asserted_write(self):
        script = '''assert(package_extract_file("checked.img", "/dev/block/checked"));
# package_extract_file("comment.img", "/dev/block/comment");
package_extract_file("super.img", "/dev/block/super");
  package_extract_file("boot.img", "/dev/block/boot");
'''
        found = audit.standalone_writes(script)
        self.assertEqual([item["member"] for item in found], ["super.img", "boot.img"])
        self.assertTrue(all(item["standalone_unchecked_result"] for item in found))

    def test_branch_target_handles_positive_negative_and_non_branch(self):
        self.assertEqual(audit.direct_bl_target(0x94000008, 0x1000), 0x1020)
        self.assertEqual(audit.direct_bl_target(0x97FFFFFF, 0x1000), 0x0FFC)
        self.assertIsNone(audit.direct_bl_target(0xD503201F, 0x1000))

    def test_direct_calls_only_match_selected_targets(self):
        data = fake_elf_with_calls()
        calls = audit.direct_calls(data, {"address": 0x1000, "bytes": 16}, {0x1020})
        self.assertEqual(calls, [{"call_address": 0x1000, "target_address": 0x1020}])
        with self.assertRaises(audit.AuditError):
            audit.direct_calls(data, {"address": 0x9999, "bytes": 16}, {0x1020})

    def test_sequence_shape_accepts_null_check_and_rejects_unrelated_code(self):
        data = bytearray(fake_elf_with_calls())
        # Indirect call, CBZ X0 past the later indirect call, NOP, indirect call.
        struct.pack_into("<IIII", data, 0x100, 0xD63F0120, 0xB4000060, 0xD503201F, 0xD63F0120)
        # Extend segment by four bytes to place the target after the second call.
        data += bytes(4)
        struct.pack_into("<Q", data, 64 + 32, 20)
        struct.pack_into("<Q", data, 64 + 40, 20)
        found = audit.sequence_null_check(bytes(data), {"address": 0x1000, "bytes": 20})
        self.assertTrue(found["non_null_path_reaches_next_call"])
        with self.assertRaises(audit.AuditError):
            audit.sequence_null_check(fake_elf_with_calls(), {"address": 0x1000, "bytes": 16})

    def test_rejects_invalid_elf(self):
        with self.assertRaises(audit.AuditError):
            audit.mini_symbols(b"not an ELF")
        with self.assertRaises(audit.AuditError):
            audit._elf_header(b"\x7fELF" + bytes(60))

    def test_metadata_offsets_report_mismatch_and_method(self):
        rows = [{"name": "META-INF/com/android/metadata", "data_offset": 123,
                 "uncompressed_bytes": 3, "method": 8}]
        items = audit.metadata_offsets("ota-property-files=metadata:69:3\n", rows)
        self.assertFalse(items[0]["offset_matches"])
        self.assertEqual(items[0]["actual_data_offset"], 123)
        self.assertEqual(items[0]["compression_method"], 8)
        with self.assertRaises(audit.AuditError):
            audit.metadata_offsets("ota-property-files=metadata:no:3\n", rows)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.zip"
        make_zip(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_zip64_local_header_and_small_members_without_modification(self):
        before = self.path.read_bytes()
        layout, small = audit.archive_info(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(layout["entry_count"], 7)
        super_row = next(row for row in layout["entries"] if row["name"] == "super.img")
        self.assertEqual(super_row["local_uncompressed_size_32"], 0xFFFFFFFF)
        self.assertEqual(super_row["local_compressed_size_32"], 0xFFFFFFFF)
        self.assertEqual(super_row["local_zip64_payload_bytes"], [16])
        self.assertEqual(small[audit.SCRIPT], b"installer")
        self.assertEqual(small[audit.BINARY], b"updater")

    def test_duplicate_entries_are_rejected(self):
        make_zip(self.path, duplicate=True)
        with self.assertRaises(audit.AuditError):
            audit.archive_info(self.path)

    def test_local_name_mismatch_is_rejected(self):
        data = bytearray(self.path.read_bytes())
        self.assertEqual(data[:4], b"PK\x03\x04")
        data[30] = ord("X")
        self.path.write_bytes(data)
        with self.assertRaises(audit.AuditError):
            audit.archive_info(self.path)

    def test_local_zip64_size_mismatch_is_rejected(self):
        with zipfile.ZipFile(self.path) as z:
            info = z.getinfo("super.img")
            offset = info.header_offset
        data = bytearray(self.path.read_bytes())
        struct.pack_into("<I", data, offset + 18, 0)
        self.path.write_bytes(data)
        with self.assertRaises(audit.AuditError):
            audit.archive_info(self.path)

    def test_local_regular_size_mismatch_is_rejected(self):
        with zipfile.ZipFile(self.path) as z:
            offset = z.getinfo("boot.img").header_offset
        data = bytearray(self.path.read_bytes())
        struct.pack_into("<I", data, offset + 22, 999)
        self.path.write_bytes(data)
        with self.assertRaises(audit.AuditError):
            audit.archive_info(self.path)

    def test_identity_matches_and_rejects_changed_input(self):
        data = self.path.read_bytes()
        self.assertTrue(audit.identity(self.path, len(data), sha(data))["identity_matched"])
        with self.assertRaises(audit.AuditError):
            audit.identity(self.path, len(data), "0" * 64)
        with self.assertRaises(audit.AuditError):
            audit.identity(self.path, len(data) + 1, sha(data))


if __name__ == "__main__":
    unittest.main()
