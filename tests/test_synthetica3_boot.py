"""Boot/DTBO parser tests using synthetic images only; never flash fixtures."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import audit_synthetica3_boot as audit  # noqa: E402

PAGE = 4096


def align(data: bytes, size: int) -> bytes:
    return data + b"\0" * ((-len(data)) % size)


def fdt(value: bytes = b"test,synthetic\0") -> bytes:
    strings = b"compatible\0"
    structure = (struct.pack(">I", 1) + b"\0\0\0\0" + struct.pack(">III", 3, len(value), 0)
                 + align(value, 4) + struct.pack(">II", 2, 9))
    reserve_off, structure_off = 40, 56
    strings_off = structure_off + len(structure)
    total = strings_off + len(strings)
    header = struct.pack(">10I", audit.FDT_MAGIC, total, structure_off, strings_off, reserve_off,
                         17, 16, 0, len(strings), len(structure))
    return header + b"\0" * 16 + structure + strings


def boot(kernel: bytes = b"synthetic-kernel", ramdisk: bytes = b"070701synthetic",
         tree: bytes | None = None, command: bytes = b"synthetic=1",
         recovery: bytes = b"", second: bytes = b"") -> bytes:
    tree = fdt() if tree is None else tree
    header = bytearray(PAGE)
    header[:8] = b"ANDROID!"
    struct.pack_into("<10I", header, 8, len(kernel), 0x8000, len(ramdisk), 0x1000000,
                     len(second), 0xf00000, 0x100, PAGE, 2, 0x12345678)
    header[48:64] = b"board".ljust(16, b"\0")
    header[64:576] = command.ljust(512, b"\0")
    off = PAGE + len(align(kernel, PAGE)) + len(align(ramdisk, PAGE)) + len(align(second, PAGE))
    struct.pack_into("<IQI", header, 1632, len(recovery), off if recovery else 0, 1660)
    struct.pack_into("<IQ", header, 1648, len(tree), 0x1f00000)
    legacy = hashlib.sha1()
    for part in (kernel, ramdisk, second, recovery, tree):
        legacy.update(part)
        legacy.update(struct.pack("<I", len(part)))
    header[576:608] = legacy.digest() + b"\0" * 12
    return bytes(header) + b"".join(align(part, PAGE) for part in (kernel, ramdisk, second, recovery, tree))


def dtbo(trees: list[bytes]) -> bytes:
    header_size, entry_size = 32, 32
    offset = header_size + len(trees) * entry_size
    rows = []
    for i, tree in enumerate(trees):
        rows.append(struct.pack(">8I", len(tree), offset, i + 1, 0, 0, 0, 0, 0))
        offset += len(tree)
    header = struct.pack(">8I", audit.DTBO_MAGIC, offset, header_size, entry_size,
                         len(trees), header_size, PAGE, 0)
    return header + b"".join(rows) + b"".join(trees)


class FDTTests(unittest.TestCase):
    def test_valid_minimal_fdt(self):
        tree = fdt()
        result = audit.inspect_fdt(tree)
        self.assertEqual(result["bytes"], len(tree))
        self.assertEqual(result["nodes"], 1)
        self.assertEqual(result["properties"], 1)

    def test_bounds_version_tokens_and_strings_are_checked(self):
        tree = fdt()
        changes = []
        bad = bytearray(tree)
        struct.pack_into(">I", bad, 4, len(tree) + 1)
        changes.append(bad)
        bad = bytearray(tree)
        struct.pack_into(">I", bad, 20, 16)
        changes.append(bad)
        bad = bytearray(tree)
        struct.pack_into(">I", bad, 56, 0xffff)
        changes.append(bad)
        bad = bytearray(tree)
        struct.pack_into(">I", bad, 72, 5000)  # property name offset
        changes.append(bad)
        for item in changes:
            with self.subTest(value=item[:8]):
                with self.assertRaises(ValueError):
                    audit.inspect_fdt(bytes(item))

    def test_truncated_reservation_map_and_missing_end_are_rejected(self):
        tree = bytearray(fdt())
        # Point the reservation map into the structure block, where it overlaps.
        struct.pack_into(">I", tree, 16, 56)
        with self.assertRaises(ValueError):
            audit.inspect_fdt(bytes(tree))
        tree = bytearray(fdt())
        offset = struct.unpack_from(">I", tree, 8)[0]
        size = struct.unpack_from(">I", tree, 36)[0]
        struct.pack_into(">I", tree, offset + size - 4, 4)
        with self.assertRaisesRegex(ValueError, "end token"):
            audit.inspect_fdt(bytes(tree))


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_v2_structures_and_legacy_id_are_checked_without_modifying_input(self):
        original = boot(second=b"extra", recovery=b"recovery")
        path = self.write("boot.img", original)
        result = audit.inspect_boot(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(result["header_version"], 2)
        self.assertTrue(result["legacy_boot_id_matches_sha1"])
        self.assertEqual(result["sections"]["second"]["bytes"], 5)
        self.assertEqual(result["sections"]["recovery_dtbo"]["bytes"], 8)
        self.assertEqual(result["ramdisk_format_guess"], "newc_cpio")
        self.assertFalse(result["avb"]["footer_at_end"])
        self.assertIn("not signature or boot verification", result["scope"])

    def test_comparison_detects_kernel_ramdisk_and_header_changes(self):
        original = audit.inspect_boot(self.write("original.img", boot()))
        new_kernel = b"new synthetic kernel, not executable"
        candidate = audit.inspect_boot(self.write("candidate.img", boot(kernel=new_kernel)))
        result = audit.compare_boot(original, candidate, hashlib.sha256(new_kernel).hexdigest())
        self.assertTrue(all(result["stable_header_fields_match"].values()))
        self.assertTrue(all(result["non_kernel_sections_match"].values()))
        self.assertTrue(result["candidate_kernel_equals_bundle_image"])
        self.assertTrue(result["candidate_legacy_boot_id_matches"])
        self.assertFalse(audit.compare_boot(original, candidate, "0" * 64)
                         ["candidate_kernel_equals_bundle_image"])
        altered = audit.inspect_boot(self.write("altered.img", boot(
            kernel=new_kernel, ramdisk=b"different ramdisk", command=b"changed=1")))
        changes = audit.compare_boot(original, altered, hashlib.sha256(new_kernel).hexdigest())
        self.assertFalse(changes["non_kernel_sections_match"]["ramdisk"])
        self.assertFalse(changes["stable_header_fields_match"]["cmdline_fields_sha256"])

    def test_legacy_id_does_not_protect_os_patch_metadata(self):
        reference = audit.inspect_boot(self.write("reference.img", boot()))
        changed = bytearray(boot(kernel=b"candidate"))
        encoded = struct.unpack_from("<I", changed, 44)[0]
        struct.pack_into("<I", changed, 44, encoded & ~0x7ff)
        candidate = audit.inspect_boot(self.write("changed-patch.img", changed))
        result = audit.compare_boot(reference, candidate, hashlib.sha256(b"candidate").hexdigest())
        self.assertTrue(candidate["legacy_boot_id_matches_sha1"])
        self.assertFalse(result["stable_header_fields_match"]["os_version_encoded"])
        self.assertTrue(all(result["non_kernel_sections_match"].values()))

    def test_invalid_version_header_offsets_and_truncation_fail_closed(self):
        original = boot(recovery=b"data")
        invalid = []
        changed = bytearray(original)
        struct.pack_into("<I", changed, 40, 3)
        invalid.append(changed)
        changed = bytearray(original)
        struct.pack_into("<I", changed, 1644, 1648)
        invalid.append(changed)
        changed = bytearray(original)
        struct.pack_into("<Q", changed, 1636, 1)
        invalid.append(changed)
        invalid.append(original[:-1])
        invalid.append(b"not a boot image")
        for index, raw in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(ValueError):
                audit.inspect_boot(self.write(f"bad-{index}.img", raw))

    def test_legacy_id_mismatch_is_reported_not_a_signature_verdict(self):
        raw = bytearray(boot())
        raw[576] ^= 1
        result = audit.inspect_boot(self.write("id.img", raw))
        self.assertFalse(result["legacy_boot_id_matches_sha1"])
        self.assertFalse(result["avb"]["footer_at_end"])

    def test_symlinks_are_not_followed(self):
        target = self.write("target.img", boot())
        link = self.root / "symlink.img"
        link.symlink_to(target)
        with self.assertRaises(OSError):
            audit.inspect_boot(link)
        self.assertEqual(target.read_bytes(), boot())

    def test_dtbo_entries_and_fdt_bounds(self):
        image = dtbo([fdt(), fdt(b"test,other\0")])
        path = self.write("dtbo.img", image)
        result = audit.inspect_dtbo(path)
        self.assertEqual(path.read_bytes(), image)
        self.assertEqual(result["entry_count"], 2)
        self.assertEqual(result["overlapping_entry_pairs"], 0)
        self.assertEqual(result["entries"][0]["fdt"]["nodes"], 1)
        self.assertFalse(result["avb"]["footer_at_end"])
        broken = bytearray(image)
        struct.pack_into(">I", broken, 36, 0)  # first FDT offset points into table
        with self.assertRaisesRegex(ValueError, "bounds"):
            audit.inspect_dtbo(self.write("broken.img", broken))
        broken = bytearray(image)
        struct.pack_into(">I", broken, 28, 1)  # unsupported table version
        with self.assertRaisesRegex(ValueError, "unsupported"):
            audit.inspect_dtbo(self.write("bad-version.img", broken))

    def test_footer_detection_does_not_verify_avb(self):
        raw = boot()
        fake_vbmeta = b"AVB0" + b"x" * 28
        avb = struct.pack(">4sIIQQQ28s", b"AVBf", 1, 0, len(raw), len(raw), len(fake_vbmeta), b"\0" * 28)
        result = audit.inspect_boot(self.write("footer.img", raw + fake_vbmeta + avb))
        self.assertTrue(result["avb"]["footer_at_end"])
        self.assertIn("not signature", result["scope"])
        invalid_footer = struct.pack(">4sIIQQQ28s", b"AVBf", 1, 0, 123456, len(raw), len(fake_vbmeta), b"\0" * 28)
        with self.assertRaisesRegex(ValueError, "footer ranges"):
            audit.inspect_boot(self.write("bad-footer.img", raw + fake_vbmeta + invalid_footer))
        short = struct.pack(">4sIIQQQ28s", b"AVBf", 1, 0, 1, 1, 1, b"\0" * 28)
        with self.assertRaisesRegex(ValueError, "shorter than the boot sections"):
            audit.inspect_boot(self.write("short-original.img", raw + short))
        with self.assertRaisesRegex(ValueError, "shorter than the DTBO table"):
            audit.inspect_dtbo(self.write("short-original-dtbo.img", dtbo([fdt()]) + short))

    def test_fdt_rejects_nonzero_structure_after_end(self):
        blob = bytearray(fdt())
        total, strings_off, struct_size = struct.unpack_from(">I4xI20xI", blob, 4)
        blob[strings_off:strings_off] = struct.pack(">I", 4)
        struct.pack_into(">I", blob, 4, total + 4)
        struct.pack_into(">I", blob, 12, strings_off + 4)
        struct.pack_into(">I", blob, 36, struct_size + 4)
        with self.assertRaisesRegex(ValueError, "after FDT end"):
            audit.inspect_fdt(bytes(blob))


if __name__ == "__main__":
    unittest.main()
