import base64
import hashlib
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import github_guarded_report_relay as relay
from test_github_guarded_release import fake_report, release


def asset(name, content):
    return {"name": name, "size": len(content), "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            "state": "uploaded"}


def bundle():
    t = relay.transfer
    parts = [b"abcde", b"fghij", b"kl"]
    data = b"".join(parts)
    report = fake_report()
    report["output"]["bytes"] = len(data)
    report["output"]["sha256"] = hashlib.sha256(data).hexdigest()
    report_bytes = (json.dumps(report, indent=2) + "\n").encode()
    rows = []
    content = {t.REPORT_NAME: report_bytes}
    for i, part in enumerate(parts, 1):
        name = f"{t.FILE_NAME}.{i:03d}"
        content[name] = part
        rows.append({"number": i, "name": name, "bytes": len(part), "sha256": hashlib.sha256(part).hexdigest()})
    manifest = {"schema": "synthetica-guarded-github-parts-v1", "file_name": t.FILE_NAME,
                "file_bytes": len(data), "file_sha256": hashlib.sha256(data).hexdigest(),
                "part_bytes": 5, "part_count": 3, "parts": rows,
                "build_report": {"name": t.REPORT_NAME, "bytes": len(report_bytes),
                                 "sha256": hashlib.sha256(report_bytes).hexdigest()},
                "previous_candidate_sha256": t.builder.BASE_SHA,
                "guarded_script_sha256": t.builder.NEW_SCRIPT_SHA,
                "host_unzip_test_passed": True, "device_or_recovery_tested": False}
    content[t.MANIFEST_NAME] = (json.dumps(manifest, indent=2) + "\n").encode()
    assets = [asset(name, value) for name, value in content.items()]
    return report, manifest, content, assets


class IndependentRelayTests(unittest.TestCase):
    def test_asset_inventory_requires_exactly_five_verified_assets(self):
        _, _, _, assets = bundle()
        self.assertEqual(len(relay.metadata_assets({"assets": assets})), 5)
        for bad in (assets[:4], assets + [assets[0]], [{**a, "digest": None} for a in assets]):
            with self.subTest(length=len(bad)), self.assertRaises(relay.RelayError):
                relay.metadata_assets({"assets": bad})

    def test_valid_manifest_and_tampering_detection(self):
        report, manifest, _, raw_assets = bundle()
        assets = relay.metadata_assets({"assets": raw_assets})
        with mock.patch.object(relay.transfer, "PART_BYTES", 5):
            self.assertEqual(len(relay.validate_manifest(manifest, report, assets)), 3)
            for key, value in (("file_sha256", "0" * 64), ("file_name", "other"),
                               ("host_unzip_test_passed", False), ("device_or_recovery_tested", True),
                               ("part_count", 2), ("guarded_script_sha256", "0" * 64)):
                altered = json.loads(json.dumps(manifest))
                altered[key] = value
                with self.subTest(key=key), self.assertRaises(relay.RelayError):
                    relay.validate_manifest(altered, report, assets)
            for change in (lambda x: x["parts"].reverse(),
                           lambda x: x["parts"][1].update(sha256="0" * 64),
                           lambda x: x["parts"][2].update(bytes=3),
                           lambda x: x["build_report"].update(sha256="0" * 64)):
                altered = json.loads(json.dumps(manifest))
                change(altered)
                with self.assertRaises(relay.RelayError):
                    relay.validate_manifest(altered, report, assets)

    def test_inventory_ignores_download_counts_but_detects_replacement(self):
        _, _, _, assets = bundle()
        original = relay.metadata_assets({"assets": assets})
        altered = [{**row, "download_count": 100} for row in assets]
        self.assertEqual(relay.stable_inventory(original),
                         relay.stable_inventory(relay.metadata_assets({"assets": altered})))
        altered[0]["id"] = 987
        self.assertNotEqual(relay.stable_inventory(original),
                            relay.stable_inventory(relay.metadata_assets({"assets": altered})))

    def test_downloaded_part_is_hashed_and_added_to_combined_stream(self):
        data = b"independent bytes"
        row = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part"
            path.write_bytes(data)
            combined = hashlib.sha256()
            relay.verify_downloaded_part(path, row, combined)
            self.assertEqual(combined.hexdigest(), row["sha256"])
            with self.assertRaises(relay.RelayError):
                relay.verify_downloaded_part(path, {**row, "sha256": "0" * 64}, hashlib.sha256())

    def test_small_asset_requires_size_and_hash_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report"
            path.write_bytes(b"report")
            a = asset("report", b"report")
            self.assertEqual(relay.read_small(path, a), b"report")
            with self.assertRaises(relay.RelayError):
                relay.read_small(path, {**a, "digest": "sha256:" + "0" * 64})

    def test_encoded_relay_preserves_exact_report_and_manifest_bytes(self):
        extra = relay.encode_relay(b'{"r":1}\n', b'{"m":2}\n', "a" * 64)
        self.assertIn(relay.BEGIN, extra)
        self.assertIn(relay.END, extra)
        encoded = extra.split(relay.BEGIN, 1)[1].split(relay.END, 1)[0].strip()
        payload = json.loads(zlib.decompress(base64.b64decode(encoded)))
        self.assertEqual(base64.b64decode(payload["report_base64"]), b'{"r":1}\n')
        self.assertEqual(base64.b64decode(payload["manifest_base64"]), b'{"m":2}\n')
        self.assertTrue(payload["downloaded_three_parts_and_small_assets"])

    def test_end_to_end_with_in_memory_fake_assets_and_fake_api_only(self):
        _, manifest, content, assets = bundle()
        initial = release(body="UNGGAHAN SELESAI; DRAF TIDAK DIPUBLIKASIKAN.\n", assets=assets)
        state = {"release": initial, "downloads": []}

        def fake_download(name, work):
            state["downloads"].append(name)
            path = work / name
            path.write_bytes(content[name])
            return path

        def fake_run(command, *, input, stdout, stderr, check):
            self.assertEqual(command[:4], ["gh", "api", "--method", "PATCH"])
            new = json.loads(input)
            self.assertEqual(new["tag_name"], relay.transfer.TAG)
            self.assertEqual(new["target_commitish"], relay.transfer.BRANCH)
            self.assertNotIn("draft", new)
            state["release"] = {**initial, "body": new["body"]}
            return type("Result", (), {"returncode": 0})()

        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(relay.transfer, "PART_BYTES", 5), \
             mock.patch.object(relay.transfer, "read_release", side_effect=lambda _: state["release"]), \
             mock.patch.object(relay, "download", side_effect=fake_download), \
             mock.patch.object(relay.subprocess, "run", side_effect=fake_run):
            result = relay.relay(999, Path(directory))
            self.assertEqual(result["independently_downloaded_assets"], 5)
            self.assertEqual(result["combined_sha256"], manifest["file_sha256"])
            self.assertEqual(len(state["downloads"]), 5)
            self.assertIn(relay.BEGIN, state["release"]["body"])
            self.assertTrue(state["release"]["draft"])
            self.assertTrue(all(not (Path(directory) / f"{relay.transfer.FILE_NAME}.{i:03d}").exists()
                                for i in range(1, 4)))

    def test_incomplete_or_preexisting_relay_refuses_before_download(self):
        _, _, _, assets = bundle()
        for body in ("INCOMPLETE", "UNGGAHAN SELESAI\n" + relay.BEGIN,
                     "UNGGAHAN SELESAI\nDELTA_GZIP_BASE64=..."):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory, \
                 mock.patch.object(relay.transfer, "read_release", return_value=release(body=body, assets=assets)), \
                 mock.patch.object(relay, "download") as download:
                with self.assertRaises(relay.RelayError):
                    relay.relay(999, Path(directory))
                download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
