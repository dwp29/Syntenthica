#!/usr/bin/env python3
"""Synthetic, host-only tests. No ROM image or device is required."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import random
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "hyperos4" / "verify_archive.py"
SPEC = importlib.util.spec_from_file_location("hyperos4_preflight", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class HyperOSPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rom = self.root / "synthetic.zip"
        with zipfile.ZipFile(self.rom, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            # Must remain data. The verifier must never execute this script.
            z.writestr("META-INF/com/google/android/updater-script", "touch should_not_exist")
            with z.open("boot.img", "w", force_zip64=True) as image:
                image.write(b"synthetic boot image")
            z.writestr("dtbo.img", b"synthetic dtbo")
            z.writestr("super.img", b"synthetic super")
        self.data = self.rom.read_bytes()
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.size = len(self.data)

    def check(self, paths: list[Path], size: int | None = None, sha: str | None = None):
        return preflight.preflight(paths, self.size if size is None else size, self.sha if sha is None else sha)

    def test_single_file_identity_and_directory_only(self) -> None:
        code, result = self.check([self.rom])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["observed"], {"bytes": self.size, "sha256": self.sha})
        self.assertFalse(result["archive"]["crc_and_contents_verified"])
        self.assertEqual(result["archive"]["entry_count"], 4)
        self.assertEqual({e["name"] for e in result["archive"]["entries"]}, {
            "META-INF/com/google/android/updater-script", "boot.img", "dtbo.img", "super.img"
        })
        self.assertFalse((self.root / "should_not_exist").exists())
        self.assertEqual(hashlib.sha256(self.rom.read_bytes()).hexdigest(), self.sha)

    def test_split_parts_in_order_match_single_file_and_zip_directory(self) -> None:
        # Include empty parts and boundaries inside the ZIP structures.
        cut = [0, 1, 7, 25, len(self.data) // 2, len(self.data) - 10, len(self.data)]
        parts = []
        empty = self.root / "000.part"
        empty.write_bytes(b"")
        parts.append(empty)
        for n, (a, b) in enumerate(zip(cut, cut[1:]), start=1):
            p = self.root / f"{n:03}.part"
            p.write_bytes(self.data[a:b])
            parts.append(p)
        code, actual = self.check(parts)
        _, single = self.check([self.rom])
        self.assertEqual(code, 0)
        self.assertEqual(actual["observed"], single["observed"])
        self.assertEqual(actual["archive"], single["archive"])
        self.assertEqual([p.read_bytes() for p in parts][0], b"")

    def test_reordered_split_parts_fail_sha_before_zip_inspection(self) -> None:
        midpoint = self.size // 2
        a, b = self.root / "a", self.root / "b"
        a.write_bytes(self.data[:midpoint])
        b.write_bytes(self.data[midpoint:])
        code, result = self.check([b, a])
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "sha256_mismatch")
        self.assertIsNone(result["archive"])

    def test_wrong_size_does_not_claim_hash_was_tested(self) -> None:
        code, result = self.check([self.rom], size=self.size + 1)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "size_mismatch")
        self.assertIsNone(result["observed"]["sha256"])
        self.assertIsNone(result["matches"]["sha256"])
        self.assertIsNone(result["archive"])

    def test_wrong_hash_stops_before_zip_inspection(self) -> None:
        code, result = self.check([self.rom], sha="0" * 64)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "sha256_mismatch")
        self.assertIsNone(result["archive"])

    def test_matching_non_zip_returns_error(self) -> None:
        bogus = self.root / "not.zip"
        bogus.write_bytes(b"this is not a zip")
        code, result = self.check([bogus], size=bogus.stat().st_size,
                                  sha=hashlib.sha256(bogus.read_bytes()).hexdigest())
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["archive"])

    def test_duplicate_same_input_file_rejected(self) -> None:
        code, result = self.check([self.rom, self.rom], size=self.size * 2)
        self.assertEqual(code, 3)
        self.assertIn("same file", result["error"])

    def test_unsafe_path_symlink_and_duplicate_are_findings_not_clean(self) -> None:
        suspect = self.root / "suspect.zip"
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(suspect, "w") as z:
                z.writestr("../escape", "no execution")
                z.writestr("/absolute", "no execution")
                z.writestr("a/../../escape", "no execution")
                z.writestr("same", "one")
                z.writestr("same", "two")
                z.writestr(link, "outside")
        data = suspect.read_bytes()
        code, result = self.check([suspect], size=len(data), sha=hashlib.sha256(data).hexdigest())
        self.assertEqual(code, 4)
        self.assertEqual(result["status"], "matched_with_findings")
        flags = {flag for finding in result["archive"]["findings"] for flag in finding["flags"]}
        self.assertTrue({"parent_path_component", "absolute_path", "duplicate_name", "symlink"} <= flags)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_fifo_is_rejected_without_blocking(self) -> None:
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFOs not supported")
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        code, result = self.check([fifo], size=0, sha=hashlib.sha256(b"").hexdigest())
        self.assertEqual(code, 3)
        self.assertIn("regular file", result["error"])

    def test_file_change_during_directory_read_is_rejected(self) -> None:
        real_inspect = preflight.inspect_zip
        def mutate_after_read(reader):
            result = real_inspect(reader)
            with self.rom.open("ab") as f:
                f.write(b"changed")
            return result
        with mock.patch.object(preflight, "inspect_zip", side_effect=mutate_after_read):
            code, result = self.check([self.rom])
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "error")
        self.assertIn("changed", result["error"])

    def test_file_replaced_during_directory_read_is_rejected(self) -> None:
        real_inspect = preflight.inspect_zip
        def replace_after_read(reader):
            result = real_inspect(reader)
            replacement = self.root / "replacement.zip"
            replacement.write_bytes(self.data)
            os.replace(replacement, self.rom)
            return result
        with mock.patch.object(preflight, "inspect_zip", side_effect=replace_after_read):
            code, result = self.check([self.rom])
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "error")
        self.assertIn("changed or was replaced", result["error"])

    def test_joined_reader_random_seek_matches_reference(self) -> None:
        segments = [b"abc", b"", b"defgh", b"i", b"", b"jklmnop", b""]
        reader = preflight.JoinedReader([io.BytesIO(x) for x in segments], [len(x) for x in segments])
        expected = b"".join(segments)
        rng = random.Random(8)
        for _ in range(200):
            offset = rng.randrange(0, len(expected) + 5)
            count = rng.randrange(0, 10)
            reader.seek(offset)
            self.assertEqual(reader.read(count), expected[offset:offset + count])
            self.assertEqual(reader.tell(), offset + len(expected[offset:offset + count]))
        reader.seek(-3, os.SEEK_END)
        self.assertEqual(reader.read(), expected[-3:])
        with self.assertRaises(ValueError):
            reader.seek(-1)

    def synthetic_reference(self):
        return {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in (("boot.img", b"synthetic boot image"), ("dtbo.img", b"synthetic dtbo"))
        }

    def test_optional_core_stream_hashes_and_checks_only_three_members(self) -> None:
        code, result = preflight.preflight(
            [self.rom], self.size, self.sha, inspect_core=True, core_reference=self.synthetic_reference()
        )
        self.assertEqual(code, 0)
        self.assertTrue(all(result["core_members"]["matches_reference"].values()))
        core = result["core_members"]["members"]
        self.assertEqual(set(core), {"boot.img", "dtbo.img", "super.img"})
        self.assertEqual(core["super.img"]["sha256"], hashlib.sha256(b"synthetic super").hexdigest())
        self.assertTrue(all(entry["zip_crc_verified_at_eof"] for entry in core.values()))
        self.assertFalse(result["archive"]["crc_and_contents_verified"])
        self.assertEqual(result["core_members"]["super_prefix"]["format"], "unknown")
        self.assertFalse((self.root / "should_not_exist").exists())
        self.assertEqual(hashlib.sha256(self.rom.read_bytes()).hexdigest(), self.sha)

    def test_core_stream_works_with_ordered_raw_split_files(self) -> None:
        midpoint = self.size // 2
        a, b = self.root / "a", self.root / "b"
        a.write_bytes(self.data[:midpoint])
        b.write_bytes(self.data[midpoint:])
        code, result = preflight.preflight(
            [a, b], self.size, self.sha, inspect_core=True, core_reference=self.synthetic_reference()
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["core_members"]["members"]["super.img"]["bytes"], len(b"synthetic super"))

    def test_core_reference_digest_mismatch_is_not_success(self) -> None:
        ref = self.synthetic_reference()
        ref["boot.img"]["sha256"] = "0" * 64
        code, result = preflight.preflight([self.rom], self.size, self.sha, inspect_core=True, core_reference=ref)
        self.assertEqual(code, 4)
        self.assertEqual(result["status"], "component_mismatch")
        self.assertFalse(result["core_members"]["matches_reference"]["boot.img"])
        self.assertTrue(result["core_members"]["matches_reference"]["dtbo.img"])

    def test_core_reference_size_mismatch_aborts_before_reading_image(self) -> None:
        ref = self.synthetic_reference()
        ref["boot.img"]["bytes"] += 1
        code, result = preflight.preflight([self.rom], self.size, self.sha, inspect_core=True, core_reference=ref)
        self.assertEqual(code, 3)
        self.assertIn("Declared size differs", result["error"])
        self.assertIsNone(result["core_members"])

    def test_core_missing_root_member_fails(self) -> None:
        path = self.root / "nested.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("subdir/boot.img", b"boot")
            z.writestr("dtbo.img", b"dtbo")
            z.writestr("super.img", b"super")
        data = path.read_bytes()
        code, result = preflight.preflight([path], len(data), hashlib.sha256(data).hexdigest(), inspect_core=True)
        self.assertEqual(code, 3)
        self.assertIn("Required root ZIP members absent: boot.img", result["error"])

    def test_unsafe_directory_stops_before_optional_core_stream(self) -> None:
        path = self.root / "unsafe.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("../unsafe", b"data")
        data = path.read_bytes()
        with mock.patch.object(preflight, "inspect_core_members") as inspect:
            code, result = preflight.preflight([path], len(data), hashlib.sha256(data).hexdigest(), inspect_core=True)
        self.assertEqual(code, 4)
        self.assertEqual(result["status"], "matched_with_findings")
        inspect.assert_not_called()

    def test_core_crc_corruption_is_reported_even_when_whole_file_hash_matches(self) -> None:
        path = self.root / "corrupt.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("boot.img", b"synthetic boot image")
            z.writestr("dtbo.img", b"synthetic dtbo")
            z.writestr("super.img", b"synthetic super")
        with zipfile.ZipFile(path) as z:
            start = z.getinfo("super.img").header_offset
        data = bytearray(path.read_bytes())
        name_len, extra_len = struct.unpack_from("<HH", data, start + 26)
        data[start + 30 + name_len + extra_len] ^= 1
        path.write_bytes(data)
        code, result = preflight.preflight(
            [path], len(data), hashlib.sha256(data).hexdigest(), inspect_core=True,
            core_reference=self.synthetic_reference(),
        )
        self.assertEqual(code, 3)
        self.assertIn("CRC", result["error"])
        self.assertIsNone(result["core_members"])

    def test_core_respects_super_size_bound(self) -> None:
        with mock.patch.object(preflight, "MAX_SUPER_BYTES", 8):
            code, result = preflight.preflight(
                [self.rom], self.size, self.sha, inspect_core=True, core_reference=self.synthetic_reference()
            )
        self.assertEqual(code, 3)
        self.assertIn("safe audit limit", result["error"])

    def test_input_mutation_during_core_read_is_rejected(self) -> None:
        inspect = preflight.inspect_core_members
        def mutate(reader, ref):
            result = inspect(reader, ref)
            with self.rom.open("ab") as f:
                f.write(b"changed")
            return result
        with mock.patch.object(preflight, "inspect_core_members", side_effect=mutate):
            code, result = preflight.preflight(
                [self.rom], self.size, self.sha, inspect_core=True, core_reference=self.synthetic_reference()
            )
        self.assertEqual(code, 3)
        self.assertIn("changed", result["error"])

    def test_super_prefix_detection_is_explicitly_unvalidated(self) -> None:
        raw = b"\0" * 4096 + b"gDla" + b"\0" * 20
        self.assertEqual(preflight.inspect_super_prefix(raw), {
            "format": "raw_super_with_lp_geometry_magic", "validated": False
        })
        sparse = struct.pack("<I4H4I", 0xED26FF3A, 1, 0, 28, 12, 4096, 500, 6, 0)
        result = preflight.inspect_super_prefix(sparse)
        self.assertEqual(result["format"], "android_sparse")
        self.assertEqual(result["expanded_bytes_declared"], 4096 * 500)
        self.assertFalse(result["validated"])

    def test_cli_json_and_exit_code(self) -> None:
        cmd = [sys.executable, str(SCRIPT), "--expected-size", str(self.size),
               "--expected-sha256", self.sha, str(self.rom)]
        done = subprocess.run(cmd, check=False, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "matched")
        self.assertEqual(done.stderr, "")

    def test_cli_rejects_invalid_sha(self) -> None:
        cmd = [sys.executable, str(SCRIPT), "--expected-sha256", "not-a-sha", str(self.rom)]
        self.assertEqual(subprocess.run(cmd, check=False, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
