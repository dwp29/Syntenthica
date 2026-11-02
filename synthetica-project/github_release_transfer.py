#!/usr/bin/env python3
"""Reconstruct and upload the exact approved candidate to a GitHub draft.

Runs on GitHub Actions, using a hash-locked original ZIP and a tiny delta held
in an unpublished draft's notes. The output ZIP must match the earlier,
independently audited candidate byte for byte before any asset is uploaded.
This does not publish the release, sign the ZIP, flash a device, or prove boot.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

import reconstruct_boot_candidate as rebuild

REPO = "dwp29/Syntenthica"
TAG = "synthetica-boot-first-20261102-01-draft"
RELEASE_ID = 431195621
FILE_NAME = "synthetica-boot-first-20261102-01.zip"
FILE_BYTES = 4713790032
FILE_SHA256 = "300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8"
DELTA_GZIP_SHA256 = "0997373e942e05878cbe77962c38479286f0938a0b73bbd0f4f23153c5619a4b"
PART_BYTES = 1536 * 1024 * 1024  # 1.5 GiB, strictly below 2 GiB.
CHUNK = 1024 * 1024


class TransferError(Exception):
    pass


def gh_json(endpoint: str) -> dict:
    run = subprocess.run(["gh", "api", endpoint], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if run.returncode:
        raise TransferError("GitHub release metadata could not be read")
    try:
        data = json.loads(run.stdout)
    except (UnicodeError, ValueError) as exc:
        raise TransferError("GitHub returned invalid release metadata") from exc
    if not isinstance(data, dict):
        raise TransferError("GitHub returned unexpected release metadata")
    return data


def read_release() -> dict:
    release = gh_json(f"repos/{REPO}/releases/{RELEASE_ID}")
    if release.get("id") != RELEASE_ID or release.get("tag_name") != TAG or release.get("draft") is not True:
        raise TransferError("Release identity changed or the release is not a draft")
    if not isinstance(release.get("assets"), list):
        raise TransferError("Release asset list is unavailable")
    return release


def parse_delta_body(body: str) -> bytes:
    matches = [line.removeprefix("DELTA_GZIP_BASE64=").strip() for line in body.splitlines()
               if line.startswith("DELTA_GZIP_BASE64=")]
    if len(matches) != 1 or len(matches[0]) > 16 * 1024:
        raise TransferError("Draft delta is missing, duplicated or too large")
    try:
        compressed = base64.b64decode(matches[0], validate=True)
    except ValueError as exc:
        raise TransferError("Draft delta encoding is invalid") from exc
    if hashlib.sha256(compressed).hexdigest() != DELTA_GZIP_SHA256:
        raise TransferError("Draft delta gzip SHA-256 mismatch")
    rebuild.decode_delta(compressed)
    return compressed


def asset_matches(asset: dict, *, name: str, size: int, sha256: str) -> bool:
    return (asset.get("name") == name and asset.get("state") == "uploaded"
            and asset.get("size") == size and asset.get("digest") == f"sha256:{sha256}")


def upload_verified(path: Path, sha256: str) -> None:
    expected_size = path.stat().st_size
    matches = [asset for asset in read_release()["assets"] if asset.get("name") == path.name]
    if len(matches) > 1:
        raise TransferError(f"Duplicate release asset: {path.name}")
    if matches:
        if not asset_matches(matches[0], name=path.name, size=expected_size, sha256=sha256):
            raise TransferError(f"Existing release asset does not match: {path.name}")
        print(f"Already present and verified: {path.name}", flush=True)
        return
    print(f"Uploading: {path.name} ({expected_size} bytes)", flush=True)
    result = subprocess.run(["gh", "release", "upload", TAG, str(path), "--repo", REPO], check=False)
    if result.returncode:
        raise TransferError(f"GitHub upload failed: {path.name}")
    for attempt in range(3):
        matches = [asset for asset in read_release()["assets"] if asset.get("name") == path.name]
        if len(matches) == 1 and asset_matches(matches[0], name=path.name, size=expected_size, sha256=sha256):
            print(f"GitHub size and SHA-256 verified: {path.name}", flush=True)
            return
        if attempt < 2:
            time.sleep(2)
    raise TransferError(f"GitHub did not confirm the uploaded size and SHA-256: {path.name}")


def split_and_upload(source: Path, work: Path, part_bytes: int = PART_BYTES) -> dict:
    rows = []
    combined = hashlib.sha256()
    total = 0
    with source.open("rb") as f:
        for number in range(1, (FILE_BYTES + part_bytes - 1) // part_bytes + 1):
            name = f"{FILE_NAME}.{number:03d}"
            path = work / name
            digest = hashlib.sha256()
            written = 0
            with path.open("xb") as out:
                while written < part_bytes and total < FILE_BYTES:
                    block = f.read(min(CHUNK, part_bytes - written, FILE_BYTES - total))
                    if not block:
                        raise TransferError("Verified candidate ended during splitting")
                    out.write(block)
                    digest.update(block)
                    combined.update(block)
                    written += len(block)
                    total += len(block)
                out.flush()
                os.fsync(out.fileno())
            row = {"number": number, "name": name, "bytes": written, "sha256": digest.hexdigest()}
            upload_verified(path, row["sha256"])
            path.unlink()  # CI-only temporary chunk; local ROM/source are untouched.
            rows.append(row)
        if f.read(1):
            raise TransferError("Verified candidate grew during splitting")
    if total != FILE_BYTES or combined.hexdigest() != FILE_SHA256:
        raise TransferError("Reconstructed part stream does not match the verified full candidate")
    return {"schema": "synthetica-github-release-parts-v1", "file_name": FILE_NAME,
            "file_bytes": FILE_BYTES, "file_sha256": FILE_SHA256, "part_bytes": part_bytes,
            "part_count": len(rows), "parts": rows,
            "warning": "Raw parts are not flashable; join all and verify SHA-256. Candidate is unsigned and untested on device."}


def set_notes(complete: bool) -> None:
    prefix = "UNGGAHAN SELESAI DAN HASH DIPERIKSA" if complete else "UNGGAHAN BELUM LENGKAP"
    notes = (
        f"{prefix}. Draf ini tidak dipublikasikan.\n\n"
        "Kandidat eksperimental berbasis ROM asli diza untuk joyeuse/miatoll; "
        "hanya berkas identitas Synthetica ditambahkan. Tidak ada fitur atau modul tambahan. "
        "Semua modul Magisk/KSU tetap ditahan.\n\n"
        "BELUM DIUJI BOOT ATAU RECOVERY; ZIP HASIL REPACK TIDAK DITANDATANGANI. "
        "JANGAN FLASH sebelum review recovery, AVB, enkripsi, backup dan keputusan terpisah.\n\n"
        "Bagian ZIP adalah potongan mentah, bukan ROM yang dapat di-flash sendiri. "
        f"Jika sudah lengkap, gabungkan berurutan dan pastikan ukuran {FILE_BYTES} byte serta "
        f"SHA-256 {FILE_SHA256}.\n"
    )
    subprocess.run(["gh", "release", "edit", TAG, "--repo", REPO, "--notes", notes],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def main() -> int:
    complete = False
    release_loaded = False
    try:
        if os.environ.get("GITHUB_REPOSITORY") != REPO or not os.environ.get("GH_TOKEN"):
            raise TransferError("This helper must run in the authorized repository CI context")
        if sys.version_info[:3] != (3, 11, 2) or zlib.ZLIB_RUNTIME_VERSION != "1.2.13":
            raise TransferError("Exact reconstruction requires Python 3.11.2 and zlib 1.2.13")
        release = read_release()
        release_loaded = True
        compressed_delta = parse_delta_body(release.get("body") or "")
        root = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        source = root / "synthetica-original-locked.zip"
        if shutil.disk_usage(root).free < FILE_BYTES + PART_BYTES + 1024**3:
            raise TransferError("Runner has insufficient free space")
        with tempfile.TemporaryDirectory(prefix="synthetica-release-", dir=root) as temp:
            work = Path(temp)
            candidate = work / FILE_NAME
            lock = Path(__file__).with_name("original-baseline.lock.json")
            print("Reconstructing the exact existing candidate from the SHA-locked original and delta...", flush=True)
            result = rebuild.reconstruct(source, lock, compressed_delta, candidate)
            if result["bytes"] != FILE_BYTES or result["sha256"] != FILE_SHA256:
                raise TransferError("Reconstructed candidate did not match the approved existing build")
            print("Full candidate size and SHA-256 match the existing build.", flush=True)
            manifest = split_and_upload(candidate, work)
            manifest_path = work / "MANIFEST-GITHUB-BOOT-FIRST.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            upload_verified(manifest_path, manifest_sha)
            complete = True
            print("All parts and manifest were verified on the GitHub draft; device boot remains untested.", flush=True)
    except (TransferError, rebuild.ReconstructionError, rebuild.guard.AuditError,
            rebuild.original_builder.BuildError, zipfile.BadZipFile, OSError, ValueError,
            subprocess.SubprocessError) as exc:
        print(f"::error title=Draft transfer failed::{exc}", file=sys.stderr, flush=True)
    finally:
        if release_loaded:
            try:
                set_notes(complete)
            except (OSError, subprocess.SubprocessError):
                print("Could not update the draft notes; review the release in GitHub.", file=sys.stderr, flush=True)
                complete = False
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
