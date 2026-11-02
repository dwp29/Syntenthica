#!/usr/bin/env python3
"""Synthetic tests only; no ROM images, devices, or installer execution."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("preservation", ROOT / "synthetica-project/verify_preservation.py")
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def write_zip(path: Path, entries: list[tuple[str, bytes]], *, compression=zipfile.ZIP_STORED, comment=b"") -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", compression=compression) as z:
            z.comment = comment
            for name, data in entries:
                z.writestr(name, data)


def make_lock(source: Path, path: Path) -> None:
    entries = []
    with zipfile.ZipFile(source) as z:
        for info in z.infolist():
            if info.is_dir():
                entries.append({"name": info.filename, "directory": True})
            else:
                data = z.read(info)
                entries.append({"name": info.filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    path.write_text(json.dumps({"schema": checker.LOCK_SCHEMA, "identity": {
        "zip_bytes": source.stat().st_size,
        "zip_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "entries": entries,
    }}))


class ROMPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stock = self.root / "stock.zip"
        self.lock = self.root / "lock.json"
        self.entries = [("META-INF/", b""), ("META-INF/update", b"installer"), ("boot.img", b"stock boot")]
        write_zip(self.stock, self.entries)
        make_lock(self.stock, self.lock)

    def audit(self, candidate: Path | None = None) -> dict:
        return checker.audit_candidate(self.lock, candidate or self.stock)

    def candidate(self, entries=None, **kwargs) -> Path:
        path = self.root / "candidate.zip"
        write_zip(path, self.entries if entries is None else entries, **kwargs)
        return path

    def test_exact_original_streams_and_checks_all_files(self):
        before = self.stock.stat()
        result = self.audit()
        self.assertEqual(result["status"], "exact_original_not_a_new_build")
        self.assertTrue(result["archive"]["matches_locked_archive"])
        self.assertEqual(len(result["entries"]), 2)
        self.assertTrue(all(e["matches_locked_sha256"] and e["zip_crc_verified_at_eof"] for e in result["entries"]))
        after = self.stock.stat()
        self.assertEqual((before.st_ino, before.st_size, before.st_mtime_ns), (after.st_ino, after.st_size, after.st_mtime_ns))

    def test_repacked_same_files_is_not_silently_accepted(self):
        result = self.audit(self.candidate(compression=zipfile.ZIP_DEFLATED))
        self.assertEqual(result["status"], "repacked_review_required")
        self.assertFalse(result["archive"]["matches_locked_archive"])
        self.assertEqual(result["mismatches"], [])

    def test_zip_comment_change_also_requires_review(self):
        result = self.audit(self.candidate(comment=b"changed container metadata"))
        self.assertEqual(result["status"], "repacked_review_required")

    def test_changed_file_same_size_reported(self):
        result = self.audit(self.candidate([("META-INF/", b""), ("META-INF/update", b"installer"), ("boot.img", b"other boot")]))
        self.assertEqual(result["status"], "content_changed_review_required")
        self.assertIn({"name": "boot.img", "reason": "sha256_changed"}, result["mismatches"])

    def test_changed_file_size_is_reported_without_streaming(self):
        result = self.audit(self.candidate([("META-INF/", b""), ("META-INF/update", b"installer"), ("boot.img", b"short")]))
        self.assertEqual(result["status"], "content_changed_review_required")
        self.assertIn({"name": "boot.img", "reason": "size_or_type_changed"}, result["mismatches"])

    def test_missing_file_and_extra_file_reported(self):
        result = self.audit(self.candidate([("META-INF/", b""), ("new.img", b"x")]))
        self.assertEqual(result["status"], "content_changed_review_required")
        self.assertIn({"name": "boot.img", "reason": "missing"}, result["mismatches"])
        self.assertIn({"name": "new.img", "reason": "extra"}, result["mismatches"])

    def test_duplicate_candidate_name_is_rejected(self):
        result = self.audit(self.candidate(self.entries + [("boot.img", b"stock boot")]))
        self.assertEqual(result["status"], "error")
        self.assertIn("duplicate", result["error"])

    def test_parent_path_and_absolute_path_are_rejected(self):
        for name in ("../outside", "/absolute", "C:/drive", "foo//bar", "foo\\bar"):
            with self.subTest(name=name):
                result = self.audit(self.candidate(self.entries + [(name, b"x")]))
                self.assertEqual(result["status"], "error")
                self.assertIn("unsafe", result["error"])

    def test_symlink_entry_is_rejected(self):
        path = self.candidate()
        with zipfile.ZipFile(path, "a") as z:
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "target")
        self.assertIn("symlinks", self.audit(path)["error"])

    def test_input_symlink_and_fifo_are_not_opened(self):
        link = self.root / "candidate-link.zip"
        link.symlink_to(self.stock)
        self.assertEqual(self.audit(link)["status"], "error")
        fifo = self.root / "candidate-fifo"
        os.mkfifo(fifo)
        self.assertEqual(self.audit(fifo)["status"], "error")

    def test_lock_symlink_is_not_followed(self):
        link = self.root / "lock-link.json"
        link.symlink_to(self.lock)
        self.assertEqual(checker.audit_candidate(link, self.stock)["status"], "error")

    def test_corrupt_crc_is_error_not_clean_result(self):
        candidate = self.candidate()
        raw = bytearray(candidate.read_bytes())
        index = raw.find(b"stock boot")
        self.assertGreaterEqual(index, 0)
        raw[index] ^= 1
        candidate.write_bytes(raw)
        self.assertEqual(self.audit(candidate)["status"], "error")

    def test_non_zip_is_error(self):
        candidate = self.root / "plain"
        candidate.write_bytes(b"not a zip")
        self.assertEqual(self.audit(candidate)["status"], "error")

    def test_invalid_lock_duplicate_and_invalid_hash_are_rejected(self):
        lock = json.loads(self.lock.read_text())
        lock["identity"]["entries"].append(lock["identity"]["entries"][0])
        self.lock.write_text(json.dumps(lock))
        self.assertIn("duplicate", self.audit()["error"])
        lock["identity"]["entries"].pop()
        lock["identity"]["zip_sha256"] = "wrong"
        self.lock.write_text(json.dumps(lock))
        self.assertIn("SHA-256", self.audit()["error"])

    def test_malformed_lock_root_is_reported_as_error(self):
        self.lock.write_text("[]")
        result = self.audit()
        self.assertEqual(result["status"], "error")
        self.assertIn("schema", result["error"])

    def test_oversized_lock_and_zip_reads_are_bounded(self):
        with mock.patch.object(checker, "MAX_LOCK_BYTES", 10):
            result = self.audit()
            self.assertEqual(result["status"], "error")
            self.assertIn("lock", result["error"].lower())
        with mock.patch.object(checker, "MAX_ZIP_READ", 10):
            result = self.audit()
            self.assertEqual(result["status"], "error")
            self.assertIn("safety limit", result["error"])

    def test_encrypted_flag_is_rejected_before_decompression(self):
        candidate = self.candidate()
        raw = bytearray(candidate.read_bytes())
        central = raw.find(b"PK\x01\x02")
        self.assertGreaterEqual(central, 0)
        raw[central + 8] |= 1
        candidate.write_bytes(raw)
        result = self.audit(candidate)
        self.assertEqual(result["status"], "error")
        self.assertIn("Encrypted", result["error"])

    def test_candidate_mutation_during_audit_is_rejected(self):
        candidate = self.candidate()
        open_zip = checker.zipfile.ZipFile

        def mutate_then_open(*args, **kwargs):
            with candidate.open("ab") as f:
                f.write(b"changed")
            return open_zip(*args, **kwargs)

        with mock.patch.object(checker.zipfile, "ZipFile", side_effect=mutate_then_open):
            result = self.audit(candidate)
        self.assertEqual(result["status"], "error")
        self.assertIn("changed", result["error"])

    def test_cli_exit_codes_do_not_call_repack_a_success(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main([str(self.stock), "--lock", str(self.lock)]), 0)
            self.assertEqual(checker.main([str(self.candidate(comment=b"different")), "--lock", str(self.lock)]), 2)
            self.assertEqual(checker.main([str(self.root / "missing"), "--lock", str(self.lock)]), 3)


if __name__ == "__main__":
    unittest.main()
