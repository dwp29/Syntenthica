#!/usr/bin/env python3
"""Synthetic checks for the GitHub draft release upload helper."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import github_release_transfer as ghtransfer


class ReleaseTransferTests(unittest.TestCase):
    def test_parse_hash_locked_delta(self):
        compressed = b"synthetic gzip payload"
        digest = hashlib.sha256(compressed).hexdigest()
        body = f"draft\nDELTA_GZIP_BASE64={base64.b64encode(compressed).decode()}\n"
        with mock.patch.object(ghtransfer, "DELTA_GZIP_SHA256", digest), \
             mock.patch.object(ghtransfer.rebuild, "decode_delta", return_value=[]):
            self.assertEqual(ghtransfer.parse_delta_body(body), compressed)

    def test_parse_rejects_missing_duplicate_corrupt_and_oversized_delta(self):
        compressed = b"synthetic"
        encoded = base64.b64encode(compressed).decode()
        with mock.patch.object(ghtransfer, "DELTA_GZIP_SHA256", hashlib.sha256(compressed).hexdigest()), \
             mock.patch.object(ghtransfer.rebuild, "decode_delta", return_value=[]):
            for body in ("", f"DELTA_GZIP_BASE64={encoded}\nDELTA_GZIP_BASE64={encoded}\n",
                         "DELTA_GZIP_BASE64=!!!\n", "DELTA_GZIP_BASE64=" + "A" * (16 * 1024 + 1)):
                with self.subTest(length=len(body)), self.assertRaises(ghtransfer.TransferError):
                    ghtransfer.parse_delta_body(body)
        with mock.patch.object(ghtransfer, "DELTA_GZIP_SHA256", "0" * 64):
            with self.assertRaises(ghtransfer.TransferError):
                ghtransfer.parse_delta_body(f"DELTA_GZIP_BASE64={encoded}\n")

    def test_asset_requires_name_state_size_and_digest(self):
        row = {"name": "x", "state": "uploaded", "size": 4, "digest": "sha256:abcd"}
        self.assertTrue(ghtransfer.asset_matches(row, name="x", size=4, sha256="abcd"))
        for key, value in (("name", "y"), ("state", "starter"), ("size", 3), ("digest", None)):
            altered = dict(row)
            altered[key] = value
            self.assertFalse(ghtransfer.asset_matches(altered, name="x", size=4, sha256="abcd"))

    def test_parts_are_uploaded_in_order_and_reassemble_exactly(self):
        data = bytes(range(251)) * 30
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            source.write_bytes(data)
            uploaded = []
            def check(path, digest):
                body = path.read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), digest)
                uploaded.append((path.name, body))
            with mock.patch.object(ghtransfer, "FILE_NAME", "candidate.zip"), \
                 mock.patch.object(ghtransfer, "FILE_BYTES", len(data)), \
                 mock.patch.object(ghtransfer, "FILE_SHA256", hashlib.sha256(data).hexdigest()), \
                 mock.patch.object(ghtransfer, "upload_verified", side_effect=check):
                manifest = ghtransfer.split_and_upload(source, root, part_bytes=2048)
            self.assertEqual(b"".join(body for _, body in uploaded), data)
            self.assertEqual([name for name, _ in uploaded], [f"candidate.zip.{i:03d}" for i in range(1, 5)])
            self.assertEqual(manifest["part_count"], 4)
            self.assertTrue(all(not (root / row["name"]).exists() for row in manifest["parts"]))

    def test_existing_mismatched_asset_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.001"
            path.write_bytes(b"content")
            existing = {"assets": [{"name": path.name, "state": "uploaded", "size": 7, "digest": "sha256:wrong"}]}
            with mock.patch.object(ghtransfer, "read_release", return_value=existing), \
                 mock.patch.object(ghtransfer.subprocess, "run") as run:
                with self.assertRaises(ghtransfer.TransferError):
                    ghtransfer.upload_verified(path, hashlib.sha256(b"content").hexdigest())
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
