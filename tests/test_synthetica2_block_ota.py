"""Synthetic, host-only tests of the read-only full-block OTA extractor."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import extract_synthetica2_block_ota as ota  # noqa: E402


class TransferTests(unittest.TestCase):
    def test_sparse_and_out_of_order_ranges_map_stream_to_image(self):
        data = b"4\n3\n0\n0\nnew 2,4,6\nnew 2,0,1\n"
        length, ranges = ota.parse_transfer(data)
        self.assertEqual(length, 6 * ota.BLOCK)
        output = io.BytesIO()
        ota.write_ranges(io.BytesIO(b"a" * (2 * ota.BLOCK) + b"b" * ota.BLOCK), output, length, ranges)
        image = output.getvalue()
        self.assertEqual(image[:ota.BLOCK], b"b" * ota.BLOCK)
        self.assertEqual(image[ota.BLOCK:4 * ota.BLOCK], bytes(3 * ota.BLOCK))
        self.assertEqual(image[4 * ota.BLOCK:], b"a" * (2 * ota.BLOCK))

    def test_bad_incremental_unbounded_or_ambiguous_commands_fail_closed(self):
        invalid = [
            b"4\n2\n0\n0\nnew 2,0,1\n",  # declared mismatch
            b"4\n2\n0\n0\nnew 2,0,2\nnew 2,1,2\n",  # overlap/mismatch
            b"4\n2\n0\n0\nnew 2,0,2\nzero 2,0,2\n",
            b"4\n2\n1\n0\nnew 2,0,2\n",  # stashed/incremental
            b"4\n2\n0\n0\nmove 2,0,2\n",
            b"4\n2\n0\n0\nnew 3,0,2\n",
            b"4\n2\n0\n0\nnew 2,0,99999999\n",
            b"4\n2\n0\n0\nnew 2,-1,1\n",
            b"1\n2\nnew 2,0,2\n",
        ]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                ota.parse_transfer(text)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            ota.parse_transfer(b"4\n3\n0\n0\nnew 2,0,2\nnew 2,1,2\n")

    def test_truncated_and_extra_data_rejected(self):
        for payload, error in ((b"x" * (ota.BLOCK - 1), "truncated"),
                               (b"x" * (ota.BLOCK + 1), "exceeds")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                ota.write_ranges(io.BytesIO(payload), io.BytesIO(), ota.BLOCK, [(0, 1)])


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / "bin"
        self.binary.mkdir()
        # Fake identity decompressor to test streaming without an external binary.
        fake = self.binary / "brotli"
        fake.write_text("#!/bin/sh\nexec /bin/cat\n")
        fake.chmod(0o755)
        self.zip = self.root / "archive.zip"
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("vendor.transfer.list", b"4\n1\n0\n0\nnew 2,0,1\n")
            z.writestr("vendor.new.dat.br", b"V" * ota.BLOCK)
            z.writestr("vendor.patch.dat", b"")
            z.writestr("boot.img", b"boot fixture")
        self.digest = hashlib.sha256(self.zip.read_bytes()).hexdigest()

    def test_verified_archive_streams_only_requested_files(self):
        out = self.root / "images"
        with mock.patch.dict(os.environ, {"PATH": str(self.binary) + os.pathsep + os.environ.get("PATH", "")}):
            report = ota.extract(self.zip, out, self.digest, self.zip.stat().st_size)
        self.assertEqual((out / "vendor.img").read_bytes(), b"V" * ota.BLOCK)
        self.assertEqual((out / "boot.img").read_bytes(), b"boot fixture")
        self.assertEqual((out.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((out / "vendor.img").stat().st_mode & 0o777), 0o600)
        self.assertEqual(report["archive_sha256"], self.digest)
        self.assertEqual(report["vendor_image_bytes"], ota.BLOCK)
        self.assertEqual(hashlib.sha256(self.zip.read_bytes()).hexdigest(), self.digest)

    def test_wrong_digest_size_or_existing_destination_rejected(self):
        out = self.root / "images"
        for sha, size in (("0" * 64, self.zip.stat().st_size), (self.digest, self.zip.stat().st_size + 1)):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                ota.extract(self.zip, out, sha, size)
        self.assertFalse(out.exists())
        out.mkdir()
        with self.assertRaisesRegex(ValueError, "new directory"):
            ota.extract(self.zip, out, self.digest, self.zip.stat().st_size)

    def test_repo_output_and_symlink_archive_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            ota.extract(self.zip, ROOT / "temporary-ota-output", self.digest, self.zip.stat().st_size)
        link = self.root / "archive-link.zip"
        link.symlink_to(self.zip)
        with self.assertRaises(OSError):
            ota.extract(link, self.root / "images", self.digest, self.zip.stat().st_size)

    def test_duplicate_or_incremental_entry_is_rejected(self):
        with zipfile.ZipFile(self.zip, "a") as z:
            z.writestr("vendor.patch.dat", b"delta")
        with self.assertRaisesRegex(ValueError, "duplicated"):
            ota.extract(self.zip, self.root / "images", hashlib.sha256(self.zip.read_bytes()).hexdigest(), self.zip.stat().st_size)


if __name__ == "__main__":
    unittest.main()
