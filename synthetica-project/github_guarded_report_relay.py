#!/usr/bin/env python3
"""Independently redownload and verify a guarded *draft* and relay its reports.

Runs only on a disposable GitHub Actions host. All three draft parts are
redownloaded and hashed, in order, against both release metadata and the
manifest, including the reconstructed full ZIP SHA-256. No ZIP is executed,
extracted, published or installed. The report and manifest are relayed as
compressed data in the draft's private notes so the connected Drive can save
them; the caller can then remove only that temporary note block.
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
import zlib
from pathlib import Path

import github_guarded_release as transfer
import verify_preservation as guard

BEGIN = "<!-- SYNTHETICA_GUARDED_RELAY_BEGIN"
END = "SYNTHETICA_GUARDED_RELAY_END -->"
MAX_SMALL = 1024 * 1024
CHUNK = 1024 * 1024


class RelayError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadata_assets(release: dict) -> dict:
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 5:
        raise RelayError("Expected precisely three parts, one manifest and one report")
    result = {item.get("name"): item for item in assets}
    names = {f"{transfer.FILE_NAME}.{i:03d}" for i in range(1, 4)} | {
        transfer.REPORT_NAME, transfer.MANIFEST_NAME}
    if len(result) != 5 or set(result) != names:
        raise RelayError("Draft assets are duplicated, missing, or unexpected")
    for name, asset in result.items():
        if (asset.get("state") != "uploaded" or type(asset.get("size")) is not int
                or asset["size"] <= 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(asset.get("digest")))):
            raise RelayError(f"Draft asset metadata is not fully verified: {name}")
    return result


def stable_inventory(assets: dict) -> dict:
    """Ignore mutable download counters while detecting asset replacement."""
    return {name: {key: item.get(key) for key in ("id", "name", "state", "size", "digest")}
            for name, item in assets.items()}


def download(name: str, directory: Path) -> Path:
    if name not in {f"{transfer.FILE_NAME}.{i:03d}" for i in range(1, 4)} | {
            transfer.REPORT_NAME, transfer.MANIFEST_NAME}:
        raise RelayError("Refusing an unexpected download name")
    path = directory / name
    if path.exists() or path.is_symlink():
        raise RelayError("Refusing to overwrite an existing local file")
    proc = subprocess.run(["gh", "release", "download", transfer.TAG, "--repo", transfer.REPO,
                           "--pattern", name, "--dir", str(directory)], check=False)
    if proc.returncode:
        raise RelayError(f"GitHub asset download failed: {name}")
    return path


def read_small(path: Path, metadata: dict) -> bytes:
    with guard._open_regular(path)[0] as f:
        before = guard._snapshot(os.fstat(f.fileno()))
        if before[2] > MAX_SMALL or before[2] != metadata["size"]:
            raise RelayError("Small asset has unexpected size")
        data = f.read(MAX_SMALL + 1)
        guard._check_unchanged(path, f, before)
    if len(data) != before[2] or metadata["digest"] != f"sha256:{digest(data)}":
        raise RelayError("Downloaded small asset SHA-256 differs from GitHub metadata")
    return data


def validate_manifest(manifest: dict, report: dict, assets: dict) -> list[dict]:
    if not isinstance(manifest, dict) or not isinstance(report, dict):
        raise RelayError("Downloaded report or manifest is not an object")
    transfer.validate_report(report, Path(__file__).with_name("original-baseline.lock.json"))
    output = report["output"]
    if (manifest.get("schema") != "synthetica-guarded-github-parts-v1"
            or manifest.get("file_name") != transfer.FILE_NAME
            or manifest.get("file_bytes") != output["bytes"]
            or manifest.get("file_sha256") != output["sha256"]
            or manifest.get("part_count") != 3 or manifest.get("part_bytes") != transfer.PART_BYTES
            or manifest.get("previous_candidate_sha256") != transfer.builder.BASE_SHA
            or manifest.get("guarded_script_sha256") != transfer.builder.NEW_SCRIPT_SHA
            or manifest.get("host_unzip_test_passed") is not True
            or manifest.get("device_or_recovery_tested") is not False):
        raise RelayError("Manifest identity or test limitations do not match the build report")
    rr = manifest.get("build_report", {})
    report_asset = assets[transfer.REPORT_NAME]
    if not transfer.asset_matches(report_asset, transfer.REPORT_NAME, rr.get("bytes"), rr.get("sha256")):
        raise RelayError("Manifest report identity differs from GitHub metadata")
    rows = manifest.get("parts")
    if not isinstance(rows, list) or len(rows) != 3:
        raise RelayError("Manifest does not contain exactly three parts")
    total = 0
    for index, row in enumerate(rows, 1):
        name = f"{transfer.FILE_NAME}.{index:03d}"
        if not isinstance(row, dict) or row.get("number") != index or row.get("name") != name:
            raise RelayError("Manifest parts are out of order")
        size = row.get("bytes")
        expected_size = min(transfer.PART_BYTES, output["bytes"] - total)
        if (type(size) is not int or size != expected_size or size <= 0
                or not transfer.asset_matches(assets[name], name, size, row.get("sha256"))):
            raise RelayError("Manifest part identity differs from GitHub metadata")
        total += size
    if total != output["bytes"]:
        raise RelayError("Manifest part sizes do not total the full ZIP size")
    return rows


def verify_downloaded_part(path: Path, row: dict, combined) -> None:
    with guard._open_regular(path)[0] as f:
        before = guard._snapshot(os.fstat(f.fileno()))
        if before[2] != row["bytes"]:
            raise RelayError("Downloaded part size differs from manifest")
        single = hashlib.sha256()
        count = 0
        while data := f.read(CHUNK):
            single.update(data)
            combined.update(data)
            count += len(data)
        guard._check_unchanged(path, f, before)
    if count != row["bytes"] or single.hexdigest() != row["sha256"]:
        raise RelayError("Downloaded part SHA-256 differs from manifest")


def encode_relay(report_bytes: bytes, manifest_bytes: bytes, combined_sha: str) -> str:
    payload = {
        "schema": "synthetica-guarded-independent-download-v1",
        "report_base64": base64.b64encode(report_bytes).decode("ascii"),
        "manifest_base64": base64.b64encode(manifest_bytes).decode("ascii"),
        "downloaded_three_parts_and_small_assets": True,
        "combined_sha256": combined_sha,
    }
    encoded = base64.b64encode(zlib.compress(json.dumps(payload, separators=(",", ":")).encode(), 9)).decode()
    return f"\n\n{BEGIN}\n{encoded}\n{END}\n"


def relay(number: int, work: Path) -> dict:
    release = transfer.read_release(number)
    assets = metadata_assets(release)
    body = release.get("body") or ""
    if ("UNGGAHAN SELESAI" not in body or "DELTA_GZIP_BASE64=" in body
            or BEGIN in body or END in body):
        raise RelayError("Draft is not complete or already contains a temporary relay")
    report_bytes = read_small(download(transfer.REPORT_NAME, work), assets[transfer.REPORT_NAME])
    manifest_bytes = read_small(download(transfer.MANIFEST_NAME, work), assets[transfer.MANIFEST_NAME])
    report = json.loads(report_bytes)
    manifest = json.loads(manifest_bytes)
    rows = validate_manifest(manifest, report, assets)
    combined = hashlib.sha256()
    for row in rows:
        path = download(row["name"], work)
        verify_downloaded_part(path, row, combined)
        path.unlink()  # A verified copy on this disposable runner, not the release asset.
        print(f"Independently downloaded and SHA-256 checked: {row['name']}", flush=True)
    combined_sha = combined.hexdigest()
    if combined_sha != manifest["file_sha256"]:
        raise RelayError("The redownloaded parts do not reassemble to the full ZIP SHA-256")
    extra = encode_relay(report_bytes, manifest_bytes, combined_sha)
    if len((body + extra).encode("utf-8")) > 100_000:
        raise RelayError("Temporary report relay exceeds the safe draft-notes size")
    # Recheck draft and assets immediately before PATCH; change only the notes.
    checked = transfer.read_release(number)
    if checked.get("body") != body or stable_inventory(metadata_assets(checked)) != stable_inventory(assets):
        raise RelayError("Draft changed during independent verification")
    # Explicitly preserve the tag/target: GitHub may reset a draft tag when
    # a body-only PATCH omits them. The draft flag is never changed.
    payload = {"body": body + extra, "tag_name": transfer.TAG, "target_commitish": transfer.BRANCH}
    proc = subprocess.run(["gh", "api", "--method", "PATCH", f"repos/{transfer.REPO}/releases/{number}",
                           "--input", "-"], input=json.dumps(payload).encode(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise RelayError("Cannot relay verified reports to the draft notes")
    after = transfer.read_release(number)
    if after.get("body") != body + extra or stable_inventory(metadata_assets(after)) != stable_inventory(assets):
        raise RelayError("Temporary draft relay could not be verified")
    print("All five assets redownloaded and verified; draft remains unpublished.", flush=True)
    return {"independently_downloaded_assets": 5, "combined_sha256": combined_sha,
            "report_sha256": digest(report_bytes), "manifest_sha256": digest(manifest_bytes)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args()
    try:
        transfer.validate_context()
        number = transfer.release_id_arg(args.release_id)
        if not args.work.is_dir():
            raise RelayError("Disposable work directory is missing")
        result = relay(number, args.work)
        print(json.dumps(result, indent=2))
        return 0
    except (RelayError, transfer.TransferError, guard.AuditError, OSError, ValueError, TypeError,
            subprocess.SubprocessError) as exc:
        print(f"::error title=Independent guarded draft verification stopped::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
