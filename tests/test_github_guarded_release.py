import base64
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import github_guarded_release as transfer

LOCK = ROOT / "synthetica-project/original-baseline.lock.json"


def fake_report():
    lock = transfer.guard._read_lock(LOCK)
    entries = []
    for name, spec in lock["entries"].items():
        if spec.get("directory"):
            continue
        digest = spec["sha256"]
        if name == "super.img":
            digest = transfer.builder.BASE_SUPER_SHA
        elif name == transfer.builder.SCRIPT:
            digest = transfer.builder.NEW_SCRIPT_SHA
        size = 1569 if name == transfer.builder.SCRIPT else spec["bytes"]
        entries.append({"name": name, "bytes": size, "sha256": digest, "zip_crc_verified_at_eof": True})
    return {
        "schema": "synthetica-boot-first-installer-guard-v1",
        "status": "host_verified_not_device_tested_not_flash_approved",
        "old_script_sha256": transfer.builder.OLD_SCRIPT_SHA,
        "new_script_sha256": transfer.builder.NEW_SCRIPT_SHA,
        "unchanged_member_uncompressed_content_verified": True,
        "unchanged_member_compressed_streams_identical": True,
        "source": {"sha256": transfer.builder.BASE_SHA, "bytes": transfer.builder.BASE_BYTES},
        "output": {"name": transfer.FILE_NAME, "bytes": 100, "sha256": "a" * 64,
                   "signed_by_this_recipe": False},
        "zip_header_audit": {"entry_count": len(lock["entries"]), "zip_comment_bytes": 0},
        "updater_assert_static_observation": {
            "updater_sha256": transfer.builder.static_audit.BINARY_SHA256,
            "evaluate_call_address": 0x351EEC, "selected_string_length_zero_branch_address": 0x351F08},
        "output_members": entries,
    }


def release(number=999, **changes):
    result = {"id": number, "draft": True, "tag_name": transfer.TAG,
              "target_commitish": transfer.BRANCH, "assets": [], "body": "draft"}
    result.update(changes)
    return result


class GuardedTransferTests(unittest.TestCase):
    def test_context_and_id_are_constrained(self):
        env = {"GITHUB_REPOSITORY": transfer.REPO, "GITHUB_REF": "refs/heads/" + transfer.BRANCH,
               "GH_TOKEN": "synthetic"}
        with mock.patch.dict(os.environ, env, clear=True):
            transfer.validate_context()
            self.assertEqual(transfer.release_id_arg("999"), 999)
            for bad in ("0", "-1", "123x", "1/../../", str(transfer.OLD_RELEASE_ID)):
                with self.subTest(bad=bad), self.assertRaises(transfer.TransferError):
                    transfer.release_id_arg(bad)
        for key in env:
            changed = dict(env)
            changed[key] = "wrong" if key != "GH_TOKEN" else ""
            with mock.patch.dict(os.environ, changed, clear=True), self.assertRaises(transfer.TransferError):
                transfer.validate_context()

    def test_prior_release_is_never_read(self):
        with mock.patch.object(transfer, "gh_json") as query:
            with self.assertRaises(transfer.TransferError):
                transfer.read_release(transfer.OLD_RELEASE_ID)
            query.assert_not_called()

    def test_requires_exact_new_draft_and_no_foreign_assets(self):
        with mock.patch.object(transfer, "gh_json", return_value=release()):
            self.assertEqual(transfer.read_release(999)["id"], 999)
        for data in (release(draft=False), release(id=998), release(tag_name="other"),
                     release(target_commitish="main"), release(assets=[{"name": "foreign"}]),
                     release(assets=[{"name": transfer.MANIFEST_NAME}, {"name": transfer.MANIFEST_NAME}])):
            with self.subTest(data=data), mock.patch.object(transfer, "gh_json", return_value=data):
                with self.assertRaises(transfer.TransferError):
                    transfer.read_release(999)

    def test_delta_must_be_unique_bounded_and_hash_locked(self):
        data = b"synthetic compressed delta"
        encoded = base64.b64encode(data).decode()
        valid = "draft\nDELTA_GZIP_BASE64=" + encoded + "\n"
        with mock.patch.object(transfer, "DELTA_SHA", hashlib.sha256(data).hexdigest()), \
             mock.patch.object(transfer.rebuild, "decode_delta", return_value=[]):
            self.assertEqual(transfer.parse_delta_body(valid), data)
            for body in ("", valid + valid, "DELTA_GZIP_BASE64=!!", "DELTA_GZIP_BASE64=" + "A" * 17000):
                with self.subTest(length=len(body)), self.assertRaises(transfer.TransferError):
                    transfer.parse_delta_body(body)
        with mock.patch.object(transfer, "DELTA_SHA", "0" * 64):
            with self.assertRaises(transfer.TransferError):
                transfer.parse_delta_body(valid)

    def test_build_report_requires_all_locked_hashes_and_unsigned_status(self):
        good = fake_report()
        transfer.validate_report(good, LOCK)
        mutations = [
            lambda x: x.update(status="okay"),
            lambda x: x.update(new_script_sha256="0" * 64),
            lambda x: x["output"].update(signed_by_this_recipe=True),
            lambda x: x["source"].update(sha256="0" * 64),
            lambda x: x["zip_header_audit"].update(zip_comment_bytes=1),
            lambda x: x["output_members"][0].update(sha256="0" * 64),
            lambda x: x["output_members"][0].update(zip_crc_verified_at_eof=False),
            lambda x: x["output_members"].append(dict(x["output_members"][0])),
            lambda x: x.update(unchanged_member_compressed_streams_identical=False),
        ]
        for mutate in mutations:
            data = json.loads(json.dumps(good))
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(transfer.TransferError):
                transfer.validate_report(data, LOCK)

    def test_asset_requires_exact_state_size_and_sha256(self):
        a = {"name": "a", "state": "uploaded", "size": 3, "digest": "sha256:abc"}
        self.assertTrue(transfer.asset_matches(a, "a", 3, "abc"))
        for key, value in (("name", "b"), ("state", "starter"), ("size", 4), ("digest", None)):
            b = dict(a)
            b[key] = value
            self.assertFalse(transfer.asset_matches(b, "a", 3, "abc"))

    def test_existing_conflicting_asset_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            part = Path(directory) / f"{transfer.FILE_NAME}.001"
            part.write_bytes(b"data")
            existing = {"assets": [{"name": part.name, "state": "uploaded", "size": 4,
                                    "digest": "sha256:wrong"}]}
            with mock.patch.object(transfer, "read_release", return_value=existing), \
                 mock.patch.object(transfer.subprocess, "run") as run:
                with self.assertRaises(transfer.TransferError):
                    transfer.upload_verified(999, part, hashlib.sha256(b"data").hexdigest())
                run.assert_not_called()
                self.assertEqual(part.read_bytes(), b"data")

    def test_three_uploaded_parts_reassemble_and_are_only_temporaries_removed(self):
        data = bytes(range(251)) * 20
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = work / "full.zip"
            source.write_bytes(data)
            uploaded = []
            def fake_upload(number, path, digest):
                body = path.read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), digest)
                uploaded.append((path.name, body))
            sha = hashlib.sha256(data).hexdigest()
            with mock.patch.object(transfer, "upload_verified", side_effect=fake_upload):
                rows = transfer.split_and_upload(999, source, work, len(data), sha, part_bytes=2000)
            self.assertEqual(b"".join(body for _, body in uploaded), data)
            self.assertEqual([r["number"] for r in rows], [1, 2, 3])
            self.assertEqual(source.read_bytes(), data)
            self.assertTrue(all(not (work / r["name"]).exists() for r in rows))

    def test_wrong_source_digest_or_part_count_fails_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = work / "full.zip"
            source.write_bytes(b"1234567")
            with mock.patch.object(transfer, "upload_verified") as upload:
                with self.assertRaises(transfer.TransferError):
                    transfer.split_and_upload(999, source, work, 7, "0" * 64, part_bytes=3)
                with self.assertRaises(transfer.TransferError):
                    transfer.split_and_upload(999, source, work, 7, hashlib.sha256(b"1234567").hexdigest(),
                                              part_bytes=5)
                upload.assert_not_called()

    def test_final_asset_inventory_requires_exact_verified_set(self):
        rows = [{"name": "a", "bytes": 1, "sha256": "123"}, {"name": "b", "bytes": 2, "sha256": "456"}]
        assets = [{"name": r["name"], "size": r["bytes"], "digest": "sha256:" + r["sha256"],
                   "state": "uploaded"} for r in rows]
        with mock.patch.object(transfer, "read_release", return_value={"assets": assets}):
            transfer.verify_final_assets(999, rows)
        with mock.patch.object(transfer, "read_release", return_value={"assets": assets[:1]}):
            with self.assertRaises(transfer.TransferError):
                transfer.verify_final_assets(999, rows)
        assets[0]["digest"] = "sha256:wrong"
        with mock.patch.object(transfer, "read_release", return_value={"assets": assets}):
            with self.assertRaises(transfer.TransferError):
                transfer.verify_final_assets(999, rows)

    def test_final_notes_retain_safety_warnings_and_no_delta(self):
        notes = transfer.final_notes(1234, "a" * 64)
        for text in ("DRAF", "tidak ditandatangani", "Jangan flash", "parsial", "Jangan campur", "1234"):
            self.assertIn(text, notes)
        self.assertNotIn("DELTA_GZIP_BASE64=", notes)


if __name__ == "__main__":
    unittest.main()
