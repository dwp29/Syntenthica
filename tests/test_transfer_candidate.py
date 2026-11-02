#!/usr/bin/env python3
"""Synthetic tests for the temporary authenticated ZIP transfer helper."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import transfer_candidate as transfer


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "artifact.zip"
        self.payload = b"test payload" * 100
        self.path.write_bytes(self.payload)
        self.token = "A" * 48
        snap = transfer.verify_input(self.path, len(self.payload), hashlib.sha256(self.payload).hexdigest())
        self.server = transfer.make_server("127.0.0.1", 0, self.path, len(self.payload), self.token, snap)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, path, *, headers=None, method="GET"):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers or {}, method=method), timeout=5)

    def test_status_public_archive_private(self):
        with self.request("/") as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/archive")
        self.assertEqual(caught.exception.code, 401)

    def test_correct_token_gets_exact_content(self):
        with self.request("/archive", headers={"Authorization": f"Bearer {self.token}"}) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), self.payload)

    def test_range_for_resuming(self):
        with self.request("/archive", headers={"Authorization": f"Bearer {self.token}", "Range": "bytes=22-"}) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), self.payload[22:])
            self.assertEqual(response.headers["Content-Range"], f"bytes 22-{len(self.payload)-1}/{len(self.payload)}")

    def test_invalid_range_and_wrong_token_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/archive", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(caught.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/archive", headers={"Authorization": f"Bearer {self.token}", "Range": "bytes=2-5"})
        self.assertEqual(caught.exception.code, 416)

    def test_head_reports_size_without_body(self):
        with self.request("/archive", method="HEAD", headers={"Authorization": f"Bearer {self.token}"}) as response:
            self.assertEqual(int(response.headers["Content-Length"]), len(self.payload))
            self.assertEqual(response.read(), b"")

    def test_changed_file_is_rejected(self):
        self.path.write_bytes(b"different data")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/archive", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(caught.exception.code, 409)

    def test_verify_rejects_wrong_digest_size_and_symlink(self):
        with self.assertRaises(ValueError):
            transfer.verify_input(self.path, len(self.payload), "0" * 64)
        with self.assertRaises(ValueError):
            transfer.verify_input(self.path, len(self.payload) + 1, hashlib.sha256(self.payload).hexdigest())
        symlink = self.path.with_name("link.zip")
        symlink.symlink_to(self.path)
        with self.assertRaises(ValueError):
            transfer.verify_input(symlink, len(self.payload), hashlib.sha256(self.payload).hexdigest())

    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):
            transfer.make_server("127.0.0.1", 0, self.path, len(self.payload), "short", self.path.stat())

    def test_finish_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/finish", method="POST")
        self.assertEqual(caught.exception.code, 401)

    def test_finish_stops_server_with_valid_token(self):
        with self.request("/finish", method="POST", headers={"Authorization": f"Bearer {self.token}"}) as response:
            self.assertEqual(response.status, 200)
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
