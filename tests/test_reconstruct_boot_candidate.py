#!/usr/bin/env python3
"""Synthetic round-trip and rejection tests for exact ZIP reconstruction."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import build_boot_candidate as builder
import reconstruct_boot_candidate as rebuild


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReconstructTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "original.zip"
        self.target = self.root / "target.zip"
        self.output = self.root / "restored.zip"
        self.lock = self.root / "lock.json"
        self.old_super = (b"A" * 4096) + (b"B" * 4096) + (b"C" * 4096) + (b"D" * 4096)
        self.new_super = self.old_super[:4096] + (b"X" * 4096) + self.old_super[8192:]
        with zipfile.ZipFile(self.source, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
            z.writestr("META-INF/", b"")
            z.writestr("META-INF/updater-script", b"stock installer")
            z.writestr("boot.img", b"stock boot")
            z.writestr("super.img", self.old_super)
        # Independently build a reference using the same deliberately pinned ZIP recipe.
        with zipfile.ZipFile(self.source) as zin, zipfile.ZipFile(self.target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zout:
            zout.comment = zin.comment
            for info in sorted(zin.infolist(), key=lambda item: item.header_offset):
                clone = builder._new_zipinfo(info)
                if info.is_dir():
                    zout.writestr(clone, b"")
                else:
                    data = self.new_super if info.filename == "super.img" else zin.read(info)
                    with zout.open(clone, "w", force_zip64=info.file_size >= zipfile.ZIP64_LIMIT) as out:
                        out.write(data)
        entries = []
        with zipfile.ZipFile(self.source) as zin:
            for info in zin.infolist():
                if info.is_dir():
                    entries.append({"name": info.filename, "directory": True})
                else:
                    data = zin.read(info)
                    entries.append({"name": info.filename, "bytes": len(data), "sha256": sha(data)})
        source_data, target_data = self.source.read_bytes(), self.target.read_bytes()
        self.lock.write_text(json.dumps({"schema": "synthetica-stock-baseline-lock-v1", "identity": {
            "zip_bytes": len(source_data), "zip_sha256": sha(source_data), "entries": entries}}))
        xor = bytes(a ^ b for a, b in zip(self.old_super[4096:8192], self.new_super[4096:8192]))
        self.delta = {"schema": "synthetica-boot-first-xor-delta-v1", "original_zip_sha256": sha(source_data),
                      "candidate_zip_sha256": sha(target_data), "original_super_sha256": sha(self.old_super),
                      "candidate_super_sha256": sha(self.new_super), "super_bytes": len(self.old_super),
                      "system_begin": 4096, "system_end": 12288, "block_bytes": 4096,
                      "changed_block_count": 1, "blocks": [{"offset": 4096,
                          "xor_zlib_base64": base64.b64encode(zlib.compress(xor)).decode("ascii")}]}
        self.constants = {"SOURCE_SHA": sha(source_data), "TARGET_SHA": sha(target_data),
                          "TARGET_BYTES": len(target_data), "OLD_SUPER_SHA": sha(self.old_super),
                          "NEW_SUPER_SHA": sha(self.new_super), "SUPER_BYTES": len(self.old_super),
                          "SYSTEM_BEGIN": 4096, "SYSTEM_END": 12288}

    def tearDown(self):
        self.tmp.cleanup()

    def patch_bytes(self, data=None):
        raw = (json.dumps(data or self.delta, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        return gzip.compress(raw, mtime=0), sha(raw)

    def test_reconstructs_exact_reference_and_never_overwrites(self):
        delta, digest = self.patch_bytes()
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA=digest):
            result = rebuild.reconstruct(self.source, self.lock, delta, self.output)
            self.assertEqual(self.output.read_bytes(), self.target.read_bytes())
            self.assertEqual(result["status"], "exact_candidate_reconstructed_not_device_tested")
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.reconstruct(self.source, self.lock, delta, self.output)

    def test_rejects_changed_source_and_cleans_partial(self):
        delta, digest = self.patch_bytes()
        self.source.write_bytes(self.source.read_bytes() + b"changed")
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA=digest):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.reconstruct(self.source, self.lock, delta, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "restored.zip.partial").exists())

    def test_rejects_corrupt_delta_and_wrong_target(self):
        delta, digest = self.patch_bytes()
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA="0" * 64):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.reconstruct(self.source, self.lock, delta, self.output)
        bad_constants = dict(self.constants)
        bad_constants["TARGET_BYTES"] += 1
        with mock.patch.multiple(rebuild, **bad_constants, DELTA_JSON_SHA=digest):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.reconstruct(self.source, self.lock, delta, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_delta_outside_allowed_extent(self):
        invalid = json.loads(json.dumps(self.delta))
        invalid["blocks"][0]["offset"] = 0
        delta, digest = self.patch_bytes(invalid)
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA=digest):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.decode_delta(delta)

    def test_rejects_duplicate_delta_offsets(self):
        invalid = json.loads(json.dumps(self.delta))
        invalid["blocks"].append(invalid["blocks"][0])
        invalid["changed_block_count"] = 2
        delta, digest = self.patch_bytes(invalid)
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA=digest):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.decode_delta(delta)

    def test_rejects_invalid_xor_compression(self):
        invalid = json.loads(json.dumps(self.delta))
        invalid["blocks"][0]["xor_zlib_base64"] = base64.b64encode(zlib.compress(b"too short")).decode()
        delta, digest = self.patch_bytes(invalid)
        with mock.patch.multiple(rebuild, **self.constants, DELTA_JSON_SHA=digest):
            with self.assertRaises(rebuild.ReconstructionError):
                rebuild.decode_delta(delta)


if __name__ == "__main__":
    unittest.main()
