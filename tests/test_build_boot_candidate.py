#!/usr/bin/env python3
"""Synthetic end-to-end tests for the approved boot-first build; no ROMs/devices."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import build_boot_candidate as build
import compare_ext4_boot as ext4
import verify_preservation as guard


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def name(value: str) -> bytes:
    return value.encode("ascii").ljust(36, b"\0")


def metadata(super_size: int, specs: list[tuple[str, int, int]]) -> bytes:
    partitions, extents = bytearray(), bytearray()
    for index, (part, begin, size) in enumerate(specs):
        partitions += name(part) + struct.pack("<IIII", 0, index, 1, 0)
        extents += struct.pack("<QIQI", size // 512, 0, begin // 512, 0)
    groups = name("main") + struct.pack("<IQ", 0, super_size)
    devices = struct.pack("<QIIQ", 2048, 1048576, 0, super_size) + name("super") + struct.pack("<I", 0)
    tables = bytes(partitions + extents + groups + devices)
    head = bytearray(128)
    struct.pack_into("<IHHI", head, 0, build.lp.HEADER_MAGIC, 10, 0, 128)
    struct.pack_into("<I", head, 44, len(tables))
    head[48:80] = hashlib.sha256(tables).digest()
    cursor = 0
    for offset, count, stride in ((80, len(specs), 52), (92, len(specs), 24), (104, 1, 48), (116, 1, 64)):
        struct.pack_into("<III", head, offset, cursor, count, stride)
        cursor += count * stride
    head[12:44] = hashlib.sha256(head).digest()
    return bytes(head) + tables


def make_super(system_image: Path) -> tuple[bytes, dict]:
    unit = 1024 * 1024
    system = system_image.read_bytes()
    specs = [("product", 1 * unit, unit), ("system", 2 * unit, len(system)),
             ("system_ext", 2 * unit + len(system), unit), ("vendor", 3 * unit + len(system), unit)]
    total = 4 * unit + len(system)
    raw = bytearray(total)
    geo = bytearray(struct.pack("<II", build.lp.GEOMETRY_MAGIC, 52) + b"\0" * 32 + struct.pack("<III", 4096, 1, 4096))
    geo[8:40] = hashlib.sha256(geo).digest()
    raw[4096:4096 + len(geo)] = geo
    raw[8192:8192 + len(geo)] = geo
    meta = metadata(total, specs)
    raw[12288:12288 + len(meta)] = meta
    raw[16384:16384 + len(meta)] = meta
    content = {"product": b"P" * unit, "system": system, "system_ext": b"E" * unit, "vendor": b"V" * unit}
    locked = {}
    for part, begin, size in specs:
        raw[begin:begin + size] = content[part]
        locked[part] = {"bytes": size, "sha256": sha(content[part])}
    return bytes(raw), locked


def create_original_archive(path: Path, system_image: Path, lock_path: Path) -> dict:
    super_image, parts = make_super(system_image)
    members = [("META-INF/", b""), ("META-INF/com/google/android/update-binary", b"original installer"),
               ("META-INF/com/google/android/updater-script", b"original update-script"),
               ("boot.img", b"original boot"), ("dtbo.img", b"original dtbo"), ("super.img", super_image)]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True, compresslevel=1) as z:
        for member, content in members:
            z.writestr(member, content)
    entries = []
    for member, content in members:
        if member.endswith("/"):
            entries.append({"name": member, "directory": True})
        else:
            entries.append({"name": member, "bytes": len(content), "sha256": sha(content)})
    lock = {"schema": guard.LOCK_SCHEMA, "identity": {"zip_bytes": path.stat().st_size,
            "zip_sha256": sha(path.read_bytes()), "entries": entries}, "logical_partitions": parts}
    lock_path.write_text(json.dumps(lock))
    return lock


def debugfs(image: Path, command: str) -> None:
    result = subprocess.run([build.DEBUGFS, "-w", "-R", command, str(image)],
                            capture_output=True, env={**os.environ, "E2FSPROGS_FAKE_TIME": build.FIXED_TIME})
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))


@unittest.skipUnless(ext4.pytsk3 is not None and Path(build.DEBUGFS).exists() and Path(build.E2FSCK).exists(),
                     "Requires pytsk3 and e2fsprogs")
class BootCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="synthetica-boot-fixture-")
        cls.root = Path(cls.temp.name)
        cls.original = cls.root / "original-system.img"
        with cls.original.open("wb") as f:
            f.truncate(32 * 1024 * 1024)
        subprocess.run(["/usr/sbin/mke2fs", "-F", "-q", "-t", "ext4", "-b", "4096",
                        "-O", "^metadata_csum,^64bit,^has_journal", str(cls.original)], check=True)
        cls.base_file = cls.root / "base.txt"
        cls.base_file.write_bytes(b"existing application data\n")
        cls.label = cls.root / "label.bin"
        cls.label.write_bytes(b"u:object_r:system_file:s0\0")
        for cmd in ("mkdir /system", "mkdir /system/etc", f"write {cls.base_file} /system/etc/existing.txt",
                    "symlink /etc /system/etc", f"ea_set -f {cls.label} /system/etc security.selinux"):
            debugfs(cls.original, cmd)
        cls.source = cls.root / "source.zip"
        cls.lock_path = cls.root / "lock.json"
        cls.lock = create_original_archive(cls.source, cls.original, cls.lock_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(prefix="synthetica-boot-case-")
        self.addCleanup(self.temp_case.cleanup)
        self.case = Path(self.temp_case.name)

    def edited(self):
        work = self.case / "work"
        work.mkdir()
        return build.edit_system(self.original, work)

    def test_correct_marker_only_and_clean_ext4(self):
        candidate, report = self.edited()
        self.assertEqual(report["status"], "only_approved_marker_detected")
        self.assertEqual(report["marker"]["path"], ext4.MARKER)
        self.assertNotEqual(build.digest_file(self.original), build.digest_file(candidate))
        self.assertEqual(subprocess.run([build.E2FSCK, "-f", "-n", str(candidate)],
                                        capture_output=True).returncode, 0)

    def test_two_identical_builds_produce_same_system_bytes(self):
        first, _ = self.edited()
        second_work = self.case / "second"
        second_work.mkdir()
        second, _ = build.edit_system(self.original, second_work)
        self.assertEqual(build.digest_file(first), build.digest_file(second))

    def test_extra_path_is_rejected(self):
        candidate, _ = self.edited()
        debugfs(candidate, f"write {self.base_file} /system/etc/extra.txt")
        with self.assertRaisesRegex(ext4.ComparisonError, "Unexpected added or removed"):
            ext4.compare(self.original, candidate, build.MARKER_BYTES)

    def test_existing_file_change_is_rejected(self):
        candidate, _ = self.edited()
        debugfs(candidate, "rm /system/etc/existing.txt")
        changed = self.case / "changed.txt"
        changed.write_bytes(b"different existing content\n")
        debugfs(candidate, f"write {changed} /system/etc/existing.txt")
        with self.assertRaisesRegex(ext4.ComparisonError, "Existing path changed"):
            ext4.compare(self.original, candidate, build.MARKER_BYTES)

    def test_existing_xattr_change_is_rejected(self):
        candidate, _ = self.edited()
        different = self.case / "different-label"
        different.write_bytes(b"u:object_r:vendor_file:s0\0")
        debugfs(candidate, f"ea_set -f {different} /system/etc security.selinux")
        with self.assertRaisesRegex(ext4.ComparisonError, "Extended attributes"):
            ext4.compare(self.original, candidate, build.MARKER_BYTES)

    def test_marker_wrong_content_is_rejected(self):
        candidate, _ = self.edited()
        with self.assertRaisesRegex(ext4.ComparisonError, "Marker content or owner/mode"):
            ext4.compare(self.original, candidate, b"wrong content")

    def test_marker_executable_is_rejected(self):
        candidate, _ = self.edited()
        debugfs(candidate, f"sif {ext4.MARKER} mode 0100755")
        with self.assertRaisesRegex(ext4.ComparisonError, "Marker content or owner/mode"):
            ext4.compare(self.original, candidate, build.MARKER_BYTES)

    def test_marker_missing_selinux_label_is_rejected(self):
        candidate, _ = self.edited()
        debugfs(candidate, f"ea_rm {ext4.MARKER} security.selinux")
        with self.assertRaisesRegex(ext4.ComparisonError, "SELinux label"):
            ext4.compare(self.original, candidate, build.MARKER_BYTES)

    def test_marker_already_present_is_rejected(self):
        candidate, _ = self.edited()
        second = self.case / "second"
        second.mkdir()
        with self.assertRaises((ext4.ComparisonError, build.BuildError)):
            build.edit_system(candidate, second)

    def test_existing_output_directory_is_never_touched(self):
        existing = self.case / "existing"
        existing.mkdir()
        sentinel = existing / "do-not-delete"
        sentinel.write_text("keep")
        with self.assertRaisesRegex(build.BuildError, "already exists"):
            build.build(self.source, self.lock_path, existing)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_end_to_end_rebuild_changes_only_system(self):
        original_sha = sha(self.source.read_bytes())
        out = self.case / "actual"
        with mock.patch.object(build, "EXPECTED_SOURCE", original_sha), mock.patch.object(build, "SAFETY_MARGIN", 0):
            result = build.build(self.source, self.lock_path, out)
        self.assertEqual(result["status"], "experimental_candidate_host_verified_not_device_tested")
        self.assertTrue(result["super_comparison"]["outside_system_exactly_unchanged"])
        self.assertEqual(result["zip_member_preservation"]["mismatches"], [{"name": "super.img", "reason": "sha256_changed"}])
        self.assertEqual(sha(self.source.read_bytes()), original_sha)
        output = out / result["output"]["name"]
        self.assertTrue(output.is_file())
        self.assertFalse((out / (output.name + ".partial")).exists())
        self.assertEqual(sha(output.read_bytes()), result["output"]["sha256"])
        self.assertEqual(json.loads((out / "BUILD-REPORT.json").read_text())["schema"], build.SCHEMA)

    def test_two_synthetic_end_to_end_builds_are_reproducible(self):
        original_sha = sha(self.source.read_bytes())
        with mock.patch.object(build, "EXPECTED_SOURCE", original_sha), mock.patch.object(build, "SAFETY_MARGIN", 0):
            first = build.build(self.source, self.lock_path, self.case / "first")
            second = build.build(self.source, self.lock_path, self.case / "second")
        self.assertEqual(first["output"]["sha256"], second["output"]["sha256"])
        self.assertEqual(first["packaging"]["system_sha256"], second["packaging"]["system_sha256"])
        self.assertEqual(first["packaging"]["super"]["sha256"], second["packaging"]["super"]["sha256"])

    def test_modified_input_is_rejected_before_output_created(self):
        altered = self.case / "altered.zip"
        shutil.copyfile(self.source, altered)
        with altered.open("ab") as f:
            f.write(b"mutation")
        out = self.case / "out"
        with mock.patch.object(build, "EXPECTED_SOURCE", self.lock["identity"]["zip_sha256"]):
            with self.assertRaisesRegex(build.BuildError, "preservation guard"):
                build.build(altered, self.lock_path, out)
        self.assertFalse(out.exists())


class PackagingUnitTests(unittest.TestCase):
    def test_stream_replacement_across_many_chunk_boundaries(self):
        old = bytes(range(40))
        replacement = b"X" * 19
        part = {"begin": 7, "end": 26, "bytes": 19}
        dst = io.BytesIO()
        with mock.patch.object(build, "CHUNK", 5):
            result = build._replace_system(io.BytesIO(old), dst, io.BytesIO(replacement), part, sha(old), sha(replacement))
        expected = old[:7] + replacement + old[26:]
        self.assertEqual(dst.getvalue(), expected)
        self.assertEqual(result["sha256"], sha(expected))

    def test_stream_replacement_rejects_short_or_wrong_system(self):
        old = b"abcde12345fghij"
        spec = {"begin": 5, "end": 10, "bytes": 5}
        for replacement in (b"xyz", b"wrong", b"longer"):
            with self.subTest(replacement=replacement):
                with self.assertRaises(build.BuildError):
                    build._replace_system(io.BytesIO(old), io.BytesIO(), io.BytesIO(replacement), spec, sha(old), sha(b"other"))

    def test_zip64_extra_is_removed_but_other_extra_is_preserved(self):
        zip64 = struct.pack("<HHQ", 1, 8, 42)
        other = struct.pack("<HH4s", 0xCAFE, 4, b"data")
        self.assertEqual(build._strip_zip64(zip64 + other), other)

    def test_malformed_extra_is_rejected(self):
        for data in (b"x", b"\x01\x00\x08\x00a"):
            with self.subTest(data=data), self.assertRaises(build.BuildError):
                build._strip_zip64(data)

    def test_mismatched_lp_metadata_is_rejected(self):
        with self.assertRaisesRegex(build.BuildError, "geometry"):
            build.choose_system_extent(bytes(16384), 32 * 1024 * 1024, {})


if __name__ == "__main__":
    unittest.main()
