#!/usr/bin/env python3
"""Transfer one verified boot-first candidate into an existing GitHub draft.

Runs inside GitHub Actions. The exact candidate is downloaded from a temporary,
HTTPS bearer-protected transfer endpoint described in an unpublished draft
release; the bearer is not a GitHub credential and is never printed normally.
The complete ZIP is SHA-256/size checked, then divided into three raw parts
below GitHub's per-asset limit. Each GitHub asset's reported size and SHA-256
are checked before success. Neither the ROM nor the release is published,
signed, flashed, or considered device-tested by this script.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO = "dwp29/Syntenthica"
TAG = "synthetica-boot-first-20261102-01-draft"
RELEASE_ID = 431195621
FILE_NAME = "synthetica-boot-first-20261102-01.zip"
FILE_BYTES = 4713790032
FILE_SHA256 = "300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8"
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


def parse_transfer_details(body: str) -> tuple[str, str]:
    fields = {}
    for line in body.splitlines():
        for prefix in ("TRANSFER_URL=", "TRANSFER_TOKEN="):
            if line.startswith(prefix):
                if prefix in fields:
                    raise TransferError("Duplicate temporary transfer information")
                fields[prefix] = line[len(prefix):].strip()
    url, token = fields.get("TRANSFER_URL=", ""), fields.get("TRANSFER_TOKEN=", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".e2b.app")
            or parsed.username or parsed.password or parsed.port or parsed.path != "/archive"
            or parsed.query or parsed.fragment):
        raise TransferError("Temporary transfer URL is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,256}", token):
        raise TransferError("Temporary transfer token is invalid")
    return url, token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TransferError("Transfer endpoint attempted a redirect")


def download_exact(url: str, token: str, output: Path, expected_size: int, expected_sha256: str) -> None:
    opener = urllib.request.build_opener(NoRedirect)
    # Range resumption avoids restarting a multi-gigabyte transfer after a short disconnect.
    for attempt in range(1, 6):
        existing = output.stat().st_size if output.exists() else 0
        if existing > expected_size:
            raise TransferError("Temporary download is larger than expected")
        if existing == expected_size:
            break
        headers = {"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        try:
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=90) as response:
                if response.status != (206 if existing else 200):
                    raise TransferError("Transfer returned an unexpected status")
                if int(response.headers.get("Content-Length", "-1")) != expected_size - existing:
                    raise TransferError("Transfer returned an unexpected content length")
                if existing and response.headers.get("Content-Range") != f"bytes {existing}-{expected_size - 1}/{expected_size}":
                    raise TransferError("Transfer returned an invalid resume range")
                with output.open("ab" if existing else "xb") as out:
                    count = existing
                    while block := response.read(CHUNK):
                        count += len(block)
                        if count > expected_size:
                            raise TransferError("Transfer exceeded its expected size")
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
        except (OSError, TimeoutError, urllib.error.URLError, http.client.HTTPException):
            print(f"Transfer interrupted; retry {attempt}/5 using the verified offset.", flush=True)
            if attempt == 5:
                raise TransferError("Temporary transfer did not finish") from None
            time.sleep(min(attempt * 3, 15))
    if not output.exists() or output.stat().st_size != expected_size:
        raise TransferError("Downloaded candidate has the wrong size")
    digest = hashlib.sha256()
    with output.open("rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise TransferError("Downloaded candidate SHA-256 mismatch")


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
    matches = [asset for asset in read_release()["assets"] if asset.get("name") == path.name]
    if len(matches) != 1 or not asset_matches(matches[0], name=path.name, size=expected_size, sha256=sha256):
        raise TransferError(f"GitHub did not confirm the uploaded size and SHA-256: {path.name}")
    print(f"GitHub size and SHA-256 verified: {path.name}", flush=True)


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
            path.unlink()  # This is a CI-side temporary chunk; the local source remains untouched.
            rows.append(row)
        if f.read(1):
            raise TransferError("Verified candidate grew during splitting")
    if total != FILE_BYTES or combined.hexdigest() != FILE_SHA256:
        raise TransferError("Reconstructed part stream does not match the verified full candidate")
    return {"schema": "synthetica-github-release-parts-v1", "file_name": FILE_NAME,
            "file_bytes": FILE_BYTES, "file_sha256": FILE_SHA256, "part_bytes": part_bytes,
            "part_count": len(rows), "parts": rows,
            "warning": "Raw parts are not flashable; join all and verify SHA-256. Candidate is unsigned and untested on device."}


def send_finish(url: str, token: str) -> None:
    finish = url.removesuffix("/archive") + "/finish"
    req = urllib.request.Request(finish, data=b"", headers={"Authorization": f"Bearer {token}"}, method="POST")
    try:
        urllib.request.build_opener(NoRedirect).open(req, timeout=10).close()
    except (OSError, urllib.error.URLError, TransferError):
        print("Transfer server could not be stopped remotely; stop it from the original workspace.", flush=True)


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
    url = token = ""
    complete = False
    release_loaded = False
    try:
        if os.environ.get("GITHUB_REPOSITORY") != REPO or not os.environ.get("GH_TOKEN"):
            raise TransferError("This helper must run in the authorized repository CI context")
        release = read_release()
        release_loaded = True
        url, token = parse_transfer_details(release.get("body") or "")
        print(f"::add-mask::{token}", flush=True)
        root = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        if shutil.disk_usage(root).free < FILE_BYTES + PART_BYTES + 1024**3:
            raise TransferError("Runner has insufficient free space")
        with tempfile.TemporaryDirectory(prefix="synthetica-release-", dir=root) as temp:
            work = Path(temp)
            candidate = work / FILE_NAME
            print("Downloading the existing candidate to the CI runner...", flush=True)
            download_exact(url, token, candidate, FILE_BYTES, FILE_SHA256)
            print("Full candidate size and SHA-256 match the approved existing build.", flush=True)
            manifest = split_and_upload(candidate, work)
            manifest_path = work / "MANIFEST-GITHUB-BOOT-FIRST.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            upload_verified(manifest_path, manifest_sha)
            complete = True
            print("All parts and manifest were verified on the GitHub draft; device boot remains untested.", flush=True)
    except (TransferError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Transfer failed: {exc}", file=sys.stderr, flush=True)
    finally:
        if release_loaded:
            try:
                set_notes(complete)
            except (OSError, subprocess.SubprocessError):
                print("Could not remove temporary transfer details from the draft; clean them from the original workspace.", file=sys.stderr, flush=True)
                complete = False
        if token:
            send_finish(url, token)
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
