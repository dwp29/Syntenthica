#!/usr/bin/env python3
"""Synthetic checks for the GitHub draft release transfer helper."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import github_release_transfer as ghtransfer
import transfer_candidate as server


class ReleaseTransferTests(unittest.TestCase):
    def test_parse_valid_temporary_capability(self):
        token = "A" * 48
        body = f"draft\nTRANSFER_URL=https://8765-test-id.e2b.app/archive\nTRANSFER_TOKEN={token}\n"
        self.assertEqual(ghtransfer.parse_transfer_details(body), ("https://8765-test-id.e2b.app/archive", token))

    def test_parse_rejects_invalid_or_duplicate_details(self):
        token = "A" * 48
        for url in ("http://8765-test.e2b.app/archive", "https://bad.example/archive",
                    "https://8765-test.e2b.app.evil.example/archive", "https://user@8765-test.e2b.app/archive",
                    "https://8765-test.e2b.app:123/archive", "https://8765-test.e2b.app/archive?key=secret"):
            with self.subTest(url=url), self.assertRaises(ghtransfer.TransferError):
                ghtransfer.parse_transfer_details(f"TRANSFER_URL={url}\nTRANSFER_TOKEN={token}\n")
        with self.assertRaises(ghtransfer.TransferError):
            ghtransfer.parse_transfer_details(f"TRANSFER_URL=https://1-x.e2b.app/archive\nTRANSFER_TOKEN={token}\nTRANSFER_TOKEN={token}\n")
        with self.assertRaises(ghtransfer.TransferError):
            ghtransfer.parse_transfer_details("TRANSFER_URL=https://1-x.e2b.app/archive\nTRANSFER_TOKEN=short\n")

    def test_asset_requires_name_state_size_and_digest(self):
        row = {"name": "x", "state": "uploaded", "size": 4, "digest": "sha256:abcd"}
        self.assertTrue(ghtransfer.asset_matches(row, name="x", size=4, sha256="abcd"))
        for k, v in (("name", "y"), ("state", "starter"), ("size", 3), ("digest", None)):
            altered = dict(row)
            altered[k] = v
            self.assertFalse(ghtransfer.asset_matches(altered, name="x", size=4, sha256="abcd"))

    def test_parts_are_uploaded_in_order_and_reassemble_exactly(self):
        data = bytes(range(251)) * 30
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            source.write_bytes(data)
            uploaded = []
            def check(path, sha):
                body = path.read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), sha)
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

    def test_resumed_download_verifies_full_hash(self):
        data = b"synthetic zip data" * 500
        token = "Z" * 48
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, partial = root / "source", root / "partial"
            original.write_bytes(data)
            partial.write_bytes(data[:321])
            digest = hashlib.sha256(data).hexdigest()
            snap = server.verify_input(original, len(data), digest)
            http = server.make_server("127.0.0.1", 0, original, len(data), token, snap)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                ghtransfer.download_exact(f"http://127.0.0.1:{http.server_address[1]}/archive", token,
                                          partial, len(data), digest)
                self.assertEqual(partial.read_bytes(), data)
            finally:
                http.shutdown()
                http.server_close()
                thread.join(timeout=3)

    def test_download_rejects_wrong_full_hash(self):
        data = b"synthetic data"
        token = "Z" * 48
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, output = root / "source", root / "out"
            original.write_bytes(data)
            snap = server.verify_input(original, len(data), hashlib.sha256(data).hexdigest())
            http = server.make_server("127.0.0.1", 0, original, len(data), token, snap)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(ghtransfer.TransferError):
                    ghtransfer.download_exact(f"http://127.0.0.1:{http.server_address[1]}/archive", token,
                                              output, len(data), "0" * 64)
            finally:
                http.shutdown()
                http.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
