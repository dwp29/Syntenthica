#!/usr/bin/env python3
"""Test the exact guarded draft ZIP with its own updater, on a disposable host.

The three existing, unpublished release parts are downloaded and checked; the
assembled file lives only in RUNNER_TEMP. Nothing is uploaded to or modified in
the draft. The actual ZIP is mounted read-only in the same fail-closed sandbox
as audit_updater_emulation. Since the sandbox has no Android device properties,
the unmodified real script must reject the device before any fake target write.
Five additional scenarios use the exact script extracted from the actual ZIP,
with only the device-property expressions replaced, synthetic image data, and
regular-file/directory targets. There is no device, recovery, flash, or build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import audit_boot_first_installer as audit
import audit_updater_emulation as emu
import build_guarded_candidate as builder
import github_guarded_release as transfer
import github_guarded_report_relay as relay
import verify_preservation as guard

RELEASE_ID = 431299268
CANDIDATE_BYTES = 4_713_790_039
CANDIDATE_SHA256 = "395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372"
MANIFEST_SHA256 = "fee9a046be0de8958deb2fbd4dd5590be94b8284554a3e6dc8fdbc0ac9407411"
REPORT_SHA256 = "d18eab8f083e021bc24f793a1ebdc6baa0cbe4e46080741028393df409471c96"


class DraftTestError(RuntimeError):
    pass


def append_verified_part(path: Path, row: dict, combined, output) -> None:
    """Copy one locked regular-file part while verifying it and its identity."""
    with guard._open_regular(path)[0] as stream:
        before = guard._snapshot(os.fstat(stream.fileno()))
        if before[2] != row["bytes"]:
            raise DraftTestError("Downloaded part has an unexpected length")
        h = hashlib.sha256()
        count = 0
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
            combined.update(chunk)
            output.write(chunk)
            count += len(chunk)
        guard._check_unchanged(path, stream, before)
    if count != row["bytes"] or h.hexdigest() != row["sha256"]:
        raise DraftTestError("Downloaded part failed the pinned SHA-256 check")


def download_existing_draft(work: Path) -> Path:
    """Only read the exact draft; never PATCH, upload, or delete release assets."""
    transfer.validate_context()
    if not work.is_dir() or any(work.iterdir()):
        raise DraftTestError("Runner work directory must exist and be empty")
    if shutil.disk_usage(work).free < CANDIDATE_BYTES + transfer.PART_BYTES + 1024**3:
        raise DraftTestError("Insufficient runner storage for an existing ZIP and one downloaded part")
    release = transfer.read_release(RELEASE_ID)
    assets = relay.metadata_assets(release)
    report = relay.read_small(relay.download(transfer.REPORT_NAME, work), assets[transfer.REPORT_NAME])
    manifest = relay.read_small(relay.download(transfer.MANIFEST_NAME, work), assets[transfer.MANIFEST_NAME])
    if emu.digest(report) != REPORT_SHA256 or emu.digest(manifest) != MANIFEST_SHA256:
        raise DraftTestError("The report or manifest does not match the pinned original")
    report_obj, manifest_obj = json.loads(report), json.loads(manifest)
    rows = relay.validate_manifest(manifest_obj, report_obj, assets)
    if (manifest_obj.get("file_bytes") != CANDIDATE_BYTES
            or manifest_obj.get("file_sha256") != CANDIDATE_SHA256):
        raise DraftTestError("The draft manifest is not the pinned guarded candidate")
    output = work / transfer.FILE_NAME
    combined = hashlib.sha256()
    with output.open("xb") as out:
        for row in rows:
            print(f"Downloading and verifying existing draft part {row['number']}/3", flush=True)
            part = relay.download(row["name"], work)
            append_verified_part(part, row, combined, out)
            part.unlink()  # Only the just-checked temporary runner copy.
        out.flush()
        os.fsync(out.fileno())
    if output.stat().st_size != CANDIDATE_BYTES or combined.hexdigest() != CANDIDATE_SHA256:
        raise DraftTestError("Reassembled temporary copy is not the pinned candidate")
    if relay.stable_inventory(relay.metadata_assets(transfer.read_release(RELEASE_ID))) != relay.stable_inventory(assets):
        raise DraftTestError("Draft inventory changed during the read-only download")
    return output


def audit_guarded_candidate(candidate: Path, qemu: Path) -> dict:
    before = emu.regular_identity(candidate, CANDIDATE_BYTES, CANDIDATE_SHA256)
    qemu_identity = emu.regular_identity(qemu, None, emu.QEMU_SHA256)
    with zipfile.ZipFile(candidate, "r", allowZip64=True) as archive:
        script = archive.read(builder.SCRIPT)
        updater = archive.read(audit.BINARY)
        zip_comment_bytes = len(archive.comment)
    if (emu.digest(script) != builder.NEW_SCRIPT_SHA or len(script) != 1569
            or emu.digest(updater) != audit.BINARY_SHA256 or len(updater) != 2_353_664):
        raise DraftTestError("The actual candidate's updater or three-guard script has a wrong identity")
    if zip_comment_bytes != 0:
        raise DraftTestError("Unexpected whole-file-signature comment in the pinned draft")
    rows = []
    print("Running the actual updater against the actual guarded ZIP, read-only", flush=True)
    real = emu.run_sandbox(qemu, updater, candidate, None)
    emu.validate_real_archive(real)
    rows.append({"scenario": "actual_guarded_zip64_device_rejected", "input": "actual ZIP, mounted read-only", **real})
    payloads = emu.make_payloads()
    with tempfile.TemporaryDirectory(prefix="synthetica-real-guard-script-") as td:
        for right, failure in ((True, None), (False, None), (True, "super"),
                               (True, "boot"), (True, "dtbo")):
            name = "success" if right and not failure else ("wrong_device" if not right else failure + "_open_failure")
            synthetic = Path(td) / (name + ".zip")
            substituted = emu.substitute_properties(script, right)
            emu.write_synthetic_zip(synthetic, substituted, payloads)
            print(f"Running actual guarded script on disposable targets: {name}", flush=True)
            result = emu.run_sandbox(qemu, updater, synthetic, failure)
            emu.validate_synthetic(result, payloads, True, right, failure)
            rows.append({"scenario": "actual_guarded_script_" + name,
                         "input": "synthetic ZIP; fake property values and fake payloads",
                         "substituted_script_sha256": emu.digest(substituted), **result})
    after = emu.regular_identity(candidate, CANDIDATE_BYTES, CANDIDATE_SHA256)
    return {
        "schema": 1,
        "status": "all_scenarios_passed",
        "source": "existing unpublished draft; three independently checked assets",
        "candidate_before": before,
        "candidate_after": after,
        "updater_sha256": emu.digest(updater),
        "actual_guarded_script_sha256": emu.digest(script),
        "zip_comment_bytes": zip_comment_bytes,
        "qemu": qemu_identity,
        "qemu_source": emu.QEMU_SOURCE,
        "qemu_git_blob": emu.QEMU_BLOB,
        "isolation": {"user_mount_pid_network_namespaces": True, "chroot": True,
                      "readonly_bind_input": True, "capabilities_dropped": True,
                      "no_new_privileges": True, "fake_targets_are_regular_files_or_directories": True,
                      "device_access": False},
        "scenario_count": len(rows),
        "scenarios": rows,
        "limitations": [
            "The actual ZIP was opened by its bundled updater and stopped at device assertion; no actual ROM image was extracted from it.",
            "The five write-behavior scenarios use the actual guarded script with property expressions replaced and small synthetic image data.",
            "QEMU is a pinned community binary in a disposable sandbox, not OrangeFox or a real phone.",
            "Outer recovery ZIP acceptance, signature policy, encryption, AVB, rollback, real partition writes and boot were not tested.",
            "The guards cannot undo partial earlier writes or catch a failure that the updater does not report.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise DraftTestError("Report must be a new file in an existing directory")
    candidate = download_existing_draft(args.work)
    result = audit_guarded_candidate(candidate, args.qemu)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(f"Passed {result['scenario_count']} isolated scenarios on the exact existing guarded ZIP.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DraftTestError, emu.SimulationError, relay.RelayError, transfer.TransferError,
            guard.AuditError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"::error title=Read-only guarded ZIP emulation stopped::{exc}", file=sys.stderr)
        raise SystemExit(1)
