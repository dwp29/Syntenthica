#!/usr/bin/env python3
"""Transfer the separately approved guarded candidate to a distinct draft only.

This script never publishes a release or touches the previous draft. It only
accepts the hash-locked old candidate reconstruction delta, the guarded build
report, and a verified new ZIP. Existing assets are reused only when their
GitHub size and SHA-256 already match; conflicting assets are never deleted
or overwritten. No device or recovery is accessed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import build_guarded_candidate as builder
import reconstruct_boot_candidate as rebuild
import verify_preservation as guard

REPO = "dwp29/Syntenthica"
BRANCH = "arena/96cbd65a-syntenthica"
TAG = "synthetica-boot-first-20261102-02-installer-guard-draft"
OLD_RELEASE_ID = 431195621
DELTA_SHA = "0997373e942e05878cbe77962c38479286f0938a0b73bbd0f4f23153c5619a4b"
FILE_NAME = builder.OUTPUT_NAME
REPORT_NAME = "BUILD-REPORT-BOOT-FIRST-02.json"
MANIFEST_NAME = "MANIFEST-GITHUB-BOOT-FIRST-02.json"
PART_BYTES = 1536 * 1024 * 1024
CHUNK = 1024 * 1024


class TransferError(Exception):
    pass


def validate_context() -> None:
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or not os.environ.get("GH_TOKEN")):
        raise TransferError("Transfer requires the authorized branch and repository Actions context")


def release_id_arg(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise TransferError("Release ID must be a positive integer")
    number = int(value)
    if number == OLD_RELEASE_ID:
        raise TransferError("The prior draft is explicitly protected")
    return number


def gh_json(endpoint: str) -> dict:
    proc = subprocess.run(["gh", "api", endpoint], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise TransferError("Cannot read GitHub release metadata")
    try:
        result = json.loads(proc.stdout)
    except (ValueError, UnicodeError) as exc:
        raise TransferError("GitHub returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise TransferError("GitHub release metadata has the wrong type")
    return result


def read_release(number: int) -> dict:
    if number == OLD_RELEASE_ID:
        raise TransferError("The prior draft is explicitly protected")
    data = gh_json(f"repos/{REPO}/releases/{number}")
    if (data.get("id") != number or data.get("draft") is not True or data.get("tag_name") != TAG
            or data.get("target_commitish") != BRANCH or not isinstance(data.get("assets"), list)):
        raise TransferError("The new release identity, target branch, or draft state is invalid")
    names = [a.get("name") for a in data["assets"]]
    allowed = {f"{FILE_NAME}.{i:03d}" for i in range(1, 4)} | {REPORT_NAME, MANIFEST_NAME}
    if len(names) != len(set(names)) or any(name not in allowed for name in names):
        raise TransferError("New draft contains duplicate or unexpected assets; no files were overwritten")
    return data


def parse_delta_body(body: str) -> bytes:
    matches = [line.removeprefix("DELTA_GZIP_BASE64=").strip() for line in body.splitlines()
               if line.startswith("DELTA_GZIP_BASE64=")]
    if len(matches) != 1 or len(matches[0]) > 16 * 1024:
        raise TransferError("New draft lacks one bounded reconstruction delta")
    try:
        value = base64.b64decode(matches[0], validate=True)
    except ValueError as exc:
        raise TransferError("Reconstruction delta base64 is invalid") from exc
    if hashlib.sha256(value).hexdigest() != DELTA_SHA:
        raise TransferError("Reconstruction delta SHA-256 mismatch")
    rebuild.decode_delta(value)
    return value


def save_delta(number: int, path: Path) -> None:
    data = parse_delta_body(read_release(number).get("body") or "")
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    print("Pinned reconstruction delta verified from the new draft.", flush=True)


def asset_matches(asset: dict, name: str, size: int, sha256: str) -> bool:
    return (asset.get("name") == name and asset.get("state") == "uploaded" and asset.get("size") == size
            and asset.get("digest") == f"sha256:{sha256}")


def upload_verified(number: int, path: Path, sha256: str) -> None:
    size = path.stat().st_size
    current = [item for item in read_release(number)["assets"] if item.get("name") == path.name]
    if current:
        if len(current) != 1 or not asset_matches(current[0], path.name, size, sha256):
            raise TransferError(f"Existing draft asset does not match and will not be overwritten: {path.name}")
        print(f"Already present and verified: {path.name}", flush=True)
        return
    print(f"Uploading new draft asset: {path.name} ({size} bytes)", flush=True)
    proc = subprocess.run(["gh", "release", "upload", TAG, str(path), "--repo", REPO], check=False)
    if proc.returncode:
        raise TransferError(f"Upload failed: {path.name}")
    for attempt in range(4):
        current = [item for item in read_release(number)["assets"] if item.get("name") == path.name]
        if len(current) == 1 and asset_matches(current[0], path.name, size, sha256):
            print(f"GitHub reports matching size and SHA-256: {path.name}", flush=True)
            return
        if attempt != 3:
            time.sleep(2)
    raise TransferError(f"GitHub did not confirm the uploaded asset's size and SHA-256: {path.name}")


def validate_report(report: dict, lock_path: Path) -> None:
    if (report.get("schema") != "synthetica-boot-first-installer-guard-v1"
            or report.get("status") != "host_verified_not_device_tested_not_flash_approved"
            or report.get("old_script_sha256") != builder.OLD_SCRIPT_SHA
            or report.get("new_script_sha256") != builder.NEW_SCRIPT_SHA
            or report.get("unchanged_member_uncompressed_content_verified") is not True
            or report.get("unchanged_member_compressed_streams_identical") is not True
            or report.get("source", {}).get("sha256") != builder.BASE_SHA
            or report.get("source", {}).get("bytes") != builder.BASE_BYTES):
        raise TransferError("Build report does not confirm the exact approved change")
    output = report.get("output", {})
    if (output.get("name") != FILE_NAME or type(output.get("bytes")) is not int
            or not 0 < output["bytes"] <= guard.MAX_CANDIDATE_BYTES
            or not isinstance(output.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", output["sha256"])
            or output.get("signed_by_this_recipe") is not False):
        raise TransferError("Build report has invalid output identity or signing status")
    lock = guard._read_lock(lock_path)
    expected = {name: {"sha256": spec["sha256"], "bytes": spec["bytes"]}
                for name, spec in lock["entries"].items() if not spec.get("directory")}
    expected["super.img"]["sha256"] = builder.BASE_SUPER_SHA
    expected[builder.SCRIPT].update({"sha256": builder.NEW_SCRIPT_SHA, "bytes": 1569})
    rows = report.get("output_members")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise TransferError("Build report has missing or unexpected member records")
    seen = set()
    for item in rows:
        if not isinstance(item, dict):
            raise TransferError("Build report has a malformed member record")
        name = item.get("name")
        if (name not in expected or name in seen or item.get("sha256") != expected[name]["sha256"]
                or item.get("bytes") != expected[name]["bytes"]
                or item.get("zip_crc_verified_at_eof") is not True):
            raise TransferError("Build report has a wrong or duplicated member hash")
        seen.add(name)
    if seen != set(expected):
        raise TransferError("Build report is missing a locked member")
    layout = report.get("zip_header_audit", {})
    if layout.get("entry_count") != len(lock["entries"]) or layout.get("zip_comment_bytes") != 0:
        raise TransferError("ZIP header verification is missing or unexpected")
    observation = report.get("updater_assert_static_observation", {})
    if (observation.get("updater_sha256") != builder.static_audit.BINARY_SHA256
            or observation.get("evaluate_call_address") != 0x351EEC
            or observation.get("selected_string_length_zero_branch_address") != 0x351F08):
        raise TransferError("Pinned updater's static assertion observation is missing")


def verify_regular_digest(path: Path, size: int, expected: str) -> tuple[int, ...]:
    with guard._open_regular(path)[0] as stream:
        snapshot = guard._snapshot(os.fstat(stream.fileno()))
        if snapshot[2] != size:
            raise TransferError("Candidate size differs from its report")
        digest = hashlib.sha256()
        while block := stream.read(CHUNK):
            digest.update(block)
        guard._check_unchanged(path, stream, snapshot)
        if digest.hexdigest() != expected:
            raise TransferError("Candidate SHA-256 differs from its report")
        return snapshot


def split_and_upload(number: int, source: Path, work: Path, size: int, expected_sha: str,
                     part_bytes: int = PART_BYTES) -> list[dict]:
    if part_bytes <= 0 or part_bytes >= 2 * 1024**3:
        raise TransferError("Part size must be positive and smaller than 2 GiB")
    count = (size + part_bytes - 1) // part_bytes
    if count != 3:
        raise TransferError("This transfer expects exactly three parts")
    snapshot = verify_regular_digest(source, size, expected_sha)
    rows = []
    combined = hashlib.sha256()
    total = 0
    with guard._open_regular(source)[0] as stream:
        if guard._snapshot(os.fstat(stream.fileno())) != snapshot:
            raise TransferError("Candidate was replaced after the digest check")
        for index in range(1, count + 1):
            name = f"{FILE_NAME}.{index:03d}"
            path = work / name
            digest = hashlib.sha256()
            written = 0
            with path.open("xb") as out:
                while written < part_bytes and total < size:
                    block = stream.read(min(CHUNK, part_bytes - written, size - total))
                    if not block:
                        raise TransferError("Candidate ended while generating parts")
                    out.write(block)
                    digest.update(block)
                    combined.update(block)
                    written += len(block)
                    total += len(block)
                out.flush()
                os.fsync(out.fileno())
            row = {"number": index, "name": name, "bytes": written, "sha256": digest.hexdigest()}
            upload_verified(number, path, row["sha256"])
            path.unlink()  # Only this disposable runner's just-uploaded temporary chunk.
            rows.append(row)
        if stream.read(1):
            raise TransferError("Candidate grew during splitting")
        guard._check_unchanged(source, stream, snapshot)
    if total != size or combined.hexdigest() != expected_sha:
        raise TransferError("The concatenated part stream differs from the full candidate")
    return rows


def verify_final_assets(number: int, rows: list[dict]) -> None:
    release = read_release(number)
    assets = release["assets"]
    if len(assets) != len(rows) or {a["name"] for a in assets} != {r["name"] for r in rows}:
        raise TransferError("Final draft does not contain exactly the expected assets")
    for row in rows:
        a = next(item for item in assets if item["name"] == row["name"])
        if not asset_matches(a, row["name"], row["bytes"], row["sha256"]):
            raise TransferError(f"Final draft asset verification failed: {row['name']}")


def final_notes(size: int, sha256: str) -> str:
    return (
        "UNGGAHAN SELESAI; DRAF TIDAK DIPUBLIKASIKAN.\n\n"
        "Kandidat eksperimental joyeuse berbasis kandidat boot-first sebelumnya; hanya tiga "
        "pemeriksaan hasil penulisan installer ditambahkan. Seluruh image dan komponen ROM "
        "tetap identik; semua modul Magisk/KSU tetap ditahan.\n\n"
        "PERINGATAN: belum diuji pada perangkat atau recovery. ZIP repack tidak ditandatangani. "
        "Jangan flash sebelum peninjauan terpisah terhadap recovery, ZIP, AVB, enkripsi, backup, "
        "dan risiko pemulihan. Pemeriksaan tidak mengembalikan penulisan parsial dan tidak menjamin boot.\n\n"
        "Tiga potongan adalah bagian mentah, bukan ZIP yang dapat di-flash secara terpisah. "
        "Jangan campur dengan 50 potongan Drive atau kandidat sebelumnya. Gabungkan ketiganya "
        f"sesuai nomor; ukuran gabungan {size} byte dan SHA-256 {sha256}.\n"
    )


def finish_notes(number: int, size: int, digest: str) -> None:
    # GitHub can reset a draft's tag when PATCH omits it. Reassert the exact
    # existing tag/target along with the body; never send draft=false.
    read_release(number)
    notes = final_notes(size, digest)
    result = subprocess.run(["gh", "api", "--method", "PATCH", f"repos/{REPO}/releases/{number}",
                             "-f", f"body={notes}", "-f", f"tag_name={TAG}",
                             "-f", f"target_commitish={BRANCH}"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise TransferError("Cannot replace completed draft notes")
    release = read_release(number)
    if release.get("body") != notes or "DELTA_GZIP_BASE64=" in release.get("body", ""):
        raise TransferError("Completed notes or delta cleanup could not be verified")


def publish_assets(number: int, candidate: Path, report_path: Path, work: Path, unzip_log: Path,
                   lock_path: Path) -> dict:
    read_release(number)
    if candidate.name != FILE_NAME or report_path.name != REPORT_NAME:
        raise TransferError("Candidate or report name does not match the separate draft")
    if not work.is_dir() or report_path.stat().st_size > 1024 * 1024 or unzip_log.stat().st_size > 1024 * 1024:
        raise TransferError("Runner work directory or bounded report is invalid")
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    validate_report(report, lock_path)
    if "No errors detected in compressed data of " not in unzip_log.read_text(encoding="utf-8"):
        raise TransferError("Independent unzip verification is absent")
    result = report["output"]
    size, digest = result["bytes"], result["sha256"]
    rows = split_and_upload(number, candidate, work, size, digest)
    report_row = {"name": REPORT_NAME, "bytes": len(report_bytes), "sha256": hashlib.sha256(report_bytes).hexdigest()}
    upload_verified(number, report_path, report_row["sha256"])
    manifest = {
        "schema": "synthetica-guarded-github-parts-v1", "file_name": FILE_NAME,
        "file_bytes": size, "file_sha256": digest, "part_bytes": PART_BYTES,
        "part_count": len(rows), "parts": rows, "build_report": report_row,
        "previous_candidate_sha256": builder.BASE_SHA, "guarded_script_sha256": builder.NEW_SCRIPT_SHA,
        "recipe_commit": os.environ.get("GITHUB_SHA", ""),
        "host_unzip_test_passed": True, "device_or_recovery_tested": False,
        "warning": "Raw parts are not flashable. Join only this set and verify the full SHA-256. ZIP is unsigned and boot is untested.",
    }
    manifest_path = work / MANIFEST_NAME
    with manifest_path.open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    manifest_row = {"name": MANIFEST_NAME, "bytes": manifest_path.stat().st_size,
                    "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    upload_verified(number, manifest_path, manifest_row["sha256"])
    all_rows = rows + [report_row, manifest_row]
    verify_final_assets(number, all_rows)
    finish_notes(number, size, digest)
    verify_final_assets(number, all_rows)
    print("New draft assets and metadata verified; the release remains unpublished.", flush=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("get-delta", "upload"))
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--delta", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--unzip-log", type=Path)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    args = parser.parse_args()
    try:
        validate_context()
        number = release_id_arg(args.release_id)
        if args.action == "get-delta":
            if args.delta is None:
                raise TransferError("get-delta requires --delta")
            save_delta(number, args.delta)
        else:
            if any(value is None for value in (args.candidate, args.report, args.work, args.unzip_log)):
                raise TransferError("upload requires candidate, report, work directory and unzip log")
            manifest = publish_assets(number, args.candidate, args.report, args.work, args.unzip_log, args.lock)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
    except (TransferError, guard.AuditError, rebuild.ReconstructionError, OSError, ValueError,
            TypeError, subprocess.SubprocessError) as exc:
        print(f"::error title=Guarded draft transfer stopped::{exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
