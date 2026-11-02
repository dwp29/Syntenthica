#!/usr/bin/env python3
"""Create the separately approved boot-first installer-guard candidate.

The only allowed content change from the pinned first candidate is wrapping
three existing partition extraction statements in edify assertions. All image
and other member contents must remain identical, including the previously
approved non-executable identity file within super. This never runs the Android
installer, changes an input, touches a device, signs a ZIP, or proves boot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import struct
import sys
import zipfile
from pathlib import Path

import audit_boot_first_installer as static_audit
import build_boot_candidate as boot
import verify_preservation as guard

BASE_NAME = "synthetica-boot-first-20261102-01.zip"
BASE_BYTES = 4_713_790_032
BASE_SHA = "300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8"
BASE_SUPER_SHA = "3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673"
SCRIPT = "META-INF/com/google/android/updater-script"
OLD_SCRIPT_SHA = "36cd01421779bf943e40f725daa6ce5c860f01f1150ad6bf29c09483d8ec1985"
NEW_SCRIPT_SHA = "8053b434315f4511804cd6bb6066e442e984ec0523783d36334362427d787252"
OUTPUT_NAME = "synthetica-boot-first-20261102-02-installer-guard.zip"
PARTITIONS = ("super", "boot", "dtbo")
CHUNK = 4 * 1024 * 1024
LOCAL_HEADER = struct.Struct("<4sHHHHHIIIHH")


class GuardBuildError(Exception):
    """The input, requested scope, output, or independent verification failed."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard_script(original: bytes) -> bytes:
    """Apply exactly three approved wrappers to the pinned installer text."""
    if sha(original) != OLD_SCRIPT_SHA:
        raise GuardBuildError("Installer script did not match the pinned baseline")
    changed = original
    for partition in PARTITIONS:
        old = f'package_extract_file("{partition}.img", "/dev/block/bootdevice/by-name/{partition}");'.encode("ascii")
        new = b"assert(" + old[:-1] + b");"
        if changed.count(old) != 1 or new in changed:
            raise GuardBuildError("Expected standalone partition write is missing or duplicated")
        changed = changed.replace(old, new, 1)
    if sha(changed) != NEW_SCRIPT_SHA or len(changed) != len(original) + 24:
        raise GuardBuildError("Guarded installer differs from the exact approved edit")
    return changed


def file_identity(path: Path, expected_bytes: int, expected_sha: str) -> tuple[int, ...]:
    with guard._open_regular(path)[0] as f:
        opened = guard._snapshot(os.fstat(f.fileno()))
        if opened[2] != expected_bytes:
            raise GuardBuildError("Source ZIP size does not match the pinned first candidate")
        h = hashlib.sha256()
        while chunk := f.read(CHUNK):
            h.update(chunk)
        guard._check_unchanged(path, f, opened)
        if h.hexdigest() != expected_sha:
            raise GuardBuildError("Source ZIP SHA-256 does not match the pinned first candidate")
        return opened


def expectations(lock_path: Path, script: bytes) -> dict:
    lock = guard._read_lock(lock_path)
    if lock["zip_sha256"] != boot.EXPECTED_SOURCE:
        raise GuardBuildError("Stock baseline lock is not the approved original")
    entries = {name: dict(spec) for name, spec in lock["entries"].items()}
    if SCRIPT not in entries or "super.img" not in entries:
        raise GuardBuildError("Baseline lock lacks required members")
    if entries[SCRIPT].get("sha256") != OLD_SCRIPT_SHA:
        raise GuardBuildError("Baseline lock contains a different installer script")
    entries["super.img"]["sha256"] = BASE_SUPER_SHA
    entries[SCRIPT]["bytes"] = len(script)
    entries[SCRIPT]["sha256"] = NEW_SCRIPT_SHA
    return entries


def zip_members(z: zipfile.ZipFile, expected: dict) -> dict:
    infos = z.infolist()
    if len(infos) > guard.MAX_ENTRIES:
        raise GuardBuildError("Archive contains too many members")
    members = {}
    for info in infos:
        if (not guard._safe_name(info.filename, info.is_dir()) or info.filename in members
                or info.flag_bits & 1
                or (info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16))):
            raise GuardBuildError("Archive has an unsafe or duplicate member")
        members[info.filename] = info
    if set(members) != set(expected):
        raise GuardBuildError("Archive member names differ from the locked baseline")
    return members


def streamed_copy(src, dst, expected_size: int, expected_hash: str) -> None:
    h = hashlib.sha256()
    count = 0
    while block := src.read(CHUNK):
        count += len(block)
        if count > expected_size:
            raise GuardBuildError("A source member exceeds its locked size")
        h.update(block)
        dst.write(block)
    if count != expected_size or h.hexdigest() != expected_hash:
        raise GuardBuildError("A source member did not match its locked content")


def inspect_member(z: zipfile.ZipFile, info: zipfile.ZipInfo, spec: dict) -> dict:
    if info.is_dir() or info.file_size != spec["bytes"]:
        raise GuardBuildError(f"Wrong output member size or type: {info.filename}")
    h = hashlib.sha256()
    count = 0
    with z.open(info, "r") as src:
        while block := src.read(CHUNK):
            count += len(block)
            if count > spec["bytes"]:
                raise GuardBuildError("A verified member exceeded its locked size")
            h.update(block)
    if count != spec["bytes"] or h.hexdigest() != spec["sha256"]:
        raise GuardBuildError(f"Output member content or size mismatch: {info.filename}")
    return {"name": info.filename, "bytes": count, "sha256": h.hexdigest(),
            "zip_crc_verified_at_eof": True}


def actual_updater_assert_shape(updater: bytes) -> dict:
    """Recognize a narrow, pinned ARM64 assertion pattern without executing it.

    The string representation/branch interpretation is a static inference,
    not proof of the source revision or of real recovery/device behavior.
    """
    if sha(updater) != static_audit.BINARY_SHA256:
        raise GuardBuildError("Updater binary did not match the known SHA-256")
    symbols = static_audit.mini_symbols(updater)
    asserts = [s for s in symbols if s["name"].startswith("_Z8AssertFn")]
    evaluates = [s for s in symbols if s["name"].startswith("_Z8EvaluateP")]
    if len(asserts) != 1 or len(evaluates) != 1:
        raise GuardBuildError("Pinned updater lacks unique assert/Evaluate symbols")
    fn, evaluate = asserts[0], evaluates[0]
    code = static_audit.code_bytes(updater, fn["address"], fn["bytes"])
    words = [struct.unpack_from("<I", code, i)[0] for i in range(0, len(code) - 3, 4)]
    calls = [i for i, word in enumerate(words)
             if static_audit.direct_bl_target(word, fn["address"] + i * 4) == evaluate["address"]]
    if len(calls) != 1:
        raise GuardBuildError("Expected assert-to-Evaluate call was not found")
    pos = calls[0]
    # TBZ on Evaluate's success; libc++ short/long-string length selection;
    # CBZ on that selected length. Exact words are safe because updater is pinned.
    expected = [0x36000B00, 0x394083E8, 0xF94017E9, 0xD341FD0A,
                0x7200011F, 0x9A890149, 0xB4000169]
    if words[pos + 1:pos + 8] != expected:
        raise GuardBuildError("Expected assert failure/empty-string branch shape was not found")
    null_return = 0x352060
    null_index = (null_return - fn["address"]) // 4
    if (null_return < fn["address"] or null_index >= len(words) or words[null_index] != 0xAA1F03E0):
        raise GuardBuildError("Expected assertion null-return instruction was not found")
    return {
        "updater_sha256": static_audit.BINARY_SHA256,
        "assert_function_address": fn["address"],
        "evaluate_call_address": fn["address"] + pos * 4,
        "evaluate_failure_branch_address": fn["address"] + (pos + 1) * 4,
        "selected_string_length_zero_branch_address": fn["address"] + (pos + 7) * 4,
        "null_return_address": null_return,
        "interpretation": "Static ARM64 shape is consistent with the reference assert aborting on null or empty; not an execution or source-identity proof.",
    }


def _raw_data_offset(stream, info: zipfile.ZipInfo) -> int:
    stream.seek(info.header_offset)
    raw = stream.read(LOCAL_HEADER.size)
    if len(raw) != LOCAL_HEADER.size:
        raise GuardBuildError("Short ZIP local header")
    fields = LOCAL_HEADER.unpack(raw)
    if fields[0] != b"PK\x03\x04":
        raise GuardBuildError("Invalid ZIP local header")
    return info.header_offset + LOCAL_HEADER.size + fields[-2] + fields[-1]


def compare_raw_compressed(source: Path, output: Path, source_infos: dict, output_infos: dict) -> None:
    """Require identical compressed streams for every member except the installer script."""
    with source.open("rb") as old, output.open("rb") as new:
        for name, a in source_infos.items():
            b = output_infos[name]
            if name == SCRIPT or a.is_dir():
                continue
            if a.compress_type != b.compress_type or a.compress_size != b.compress_size:
                raise GuardBuildError(f"Compressed stream metadata changed: {name}")
            old.seek(_raw_data_offset(old, a))
            new.seek(_raw_data_offset(new, b))
            remaining = a.compress_size
            while remaining:
                length = min(CHUNK, remaining)
                aa, bb = old.read(length), new.read(length)
                if len(aa) != length or len(bb) != length or aa != bb:
                    raise GuardBuildError(f"Compressed data changed for an unchanged member: {name}")
                remaining -= length


def metadata_tuple(info: zipfile.ZipInfo) -> tuple:
    return (info.date_time, info.compress_type, info.create_system, info.internal_attr,
            info.external_attr, info.flag_bits, info.comment, boot._strip_zip64(info.extra))


def build(source: Path, output: Path, lock_path: Path) -> dict:
    source, output = source.absolute(), output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise GuardBuildError("Output must be a new file in an existing directory")
    partial = output.with_name(output.name + ".partial")
    if partial.exists() or partial.is_symlink():
        raise GuardBuildError("Partial output already exists")
    verified_source = file_identity(source, BASE_BYTES, BASE_SHA)
    with guard._open_regular(source)[0] as source_file:
        before = guard._snapshot(os.fstat(source_file.fileno()))
        if before != verified_source:
            raise GuardBuildError("Source was replaced after its identity check")
        owned_partial = False
        try:
            with zipfile.ZipFile(guard._BoundedZipReader(source_file), "r", allowZip64=True) as zin:
                try:
                    script_info = zin.getinfo(SCRIPT)
                except KeyError as exc:
                    raise GuardBuildError("Pinned installer script is missing") from exc
                if script_info.is_dir() or script_info.file_size != 1545:
                    raise GuardBuildError("Pinned installer script size or type is incorrect")
                with zin.open(script_info) as script_file:
                    old_script = script_file.read(1546)
                if len(old_script) != 1545:
                    raise GuardBuildError("Could not read the complete pinned installer script")
                new_script = guard_script(old_script)
                expected = expectations(lock_path, new_script)
                original_specs = {name: dict(spec) for name, spec in expected.items()}
                original_specs[SCRIPT]["bytes"] = len(old_script)
                original_specs[SCRIPT]["sha256"] = OLD_SCRIPT_SHA
                source_infos = zip_members(zin, original_specs)
                with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED,
                                     allowZip64=True, compresslevel=1) as zout:
                    owned_partial = True
                    zout.comment = zin.comment
                    for info in sorted(source_infos.values(), key=lambda item: item.header_offset):
                        spec = original_specs[info.filename]
                        clone = boot._new_zipinfo(info)
                        if info.is_dir():
                            if not spec.get("directory", False) or info.file_size != 0:
                                raise GuardBuildError("Source directory differs from its lock")
                            zout.writestr(clone, b"")
                            continue
                        if spec.get("directory", False) or info.file_size != spec["bytes"]:
                            raise GuardBuildError(f"Source member size differs from lock: {info.filename}")
                        with zin.open(info) as src, zout.open(
                                clone, "w", force_zip64=info.file_size >= zipfile.ZIP64_LIMIT) as dst:
                            if info.filename == SCRIPT:
                                data = src.read(len(old_script) + 1)
                                if data != old_script or sha(data) != OLD_SCRIPT_SHA:
                                    raise GuardBuildError("Installer script changed during input reading")
                                dst.write(new_script)
                            else:
                                streamed_copy(src, dst, spec["bytes"], spec["sha256"])
                        if info.filename == "super.img":
                            print("Unchanged super content copied and hashed.", flush=True)
                guard._check_unchanged(source, source_file, before)
                print("New ZIP written; independently verifying every output member.", flush=True)
                with zipfile.ZipFile(partial, "r", allowZip64=True) as check:
                    output_infos = zip_members(check, expected)
                    if check.comment != zin.comment:
                        raise GuardBuildError("ZIP archive comment unexpectedly changed")
                    rows = []
                    for name, info in output_infos.items():
                        srcinfo = source_infos[name]
                        if metadata_tuple(info) != metadata_tuple(srcinfo):
                            raise GuardBuildError(f"Unexpected ZIP member metadata change: {name}")
                        spec = expected[name]
                        if spec.get("directory", False):
                            if not info.is_dir() or info.file_size:
                                raise GuardBuildError("Output directory entry changed")
                            continue
                        rows.append(inspect_member(check, info, spec))
                    compare_raw_compressed(source, partial, source_infos, output_infos)
                    guard._check_unchanged(source, source_file, before)
            old_layout, old_small = static_audit.archive_info(source)
            new_layout, new_small = static_audit.archive_info(partial)
            if new_small[SCRIPT] != new_script:
                raise GuardBuildError("Independent ZIP-header audit found an unexpected installer")
            for name in (static_audit.BINARY, static_audit.METADATA, static_audit.METADATA_PB):
                if new_small[name] != old_small[name]:
                    raise GuardBuildError(f"Independent ZIP-header audit found changed bytes: {name}")
            updater_assert = actual_updater_assert_shape(new_small[static_audit.BINARY])
            old_meta = static_audit.metadata_offsets(old_small[static_audit.METADATA].decode("utf-8"), old_layout["entries"])
            new_meta = static_audit.metadata_offsets(new_small[static_audit.METADATA].decode("utf-8"), new_layout["entries"])
            guard._check_unchanged(source, source_file, before)
            output_bytes, output_sha = boot.digest_file(partial)
            with partial.open("rb") as result:
                os.fsync(result.fileno())
            os.link(partial, output, follow_symlinks=False)  # refuse overwrite
            partial.unlink()
            return {
                "schema": "synthetica-boot-first-installer-guard-v1",
                "status": "host_verified_not_device_tested_not_flash_approved",
                "source": {"name": source.name, "bytes": BASE_BYTES, "sha256": BASE_SHA},
                "output": {"name": output.name, "bytes": output_bytes, "sha256": output_sha,
                           "signed_by_this_recipe": False},
                "approved_change": "Add result assertions to the three original partition writes only",
                "old_script_sha256": OLD_SCRIPT_SHA, "new_script_sha256": NEW_SCRIPT_SHA,
                "partitions_in_original_order": list(PARTITIONS),
                "output_members": rows,
                "unchanged_member_uncompressed_content_verified": True,
                "unchanged_member_compressed_streams_identical": True,
                "zip_container_repacked": True,
                "zip_header_audit": {"entry_count": new_layout["entry_count"],
                                     "zip_comment_bytes": new_layout["zip_comment_bytes"],
                                     "entries": new_layout["entries"],
                                     "prior_ota_metadata_offsets": old_meta,
                                     "new_ota_metadata_offsets": new_meta},
                "updater_assert_static_observation": updater_assert,
                "module_policy": "All Magisk/KSU modules remain on hold; none were added.",
                "limitations": [
                    "Only reported extract failures stop subsequent script steps; silent or partial write failures are not undone.",
                    "No installer, recovery, device, AVB chain, encryption, or device boot was tested.",
                    "Repacked ZIP is unsigned by this recipe and recovery acceptance is unproven.",
                    "OTA property-file offsets were not corrected; see the explicit offset comparisons.",
                ],
            }
        except BaseException:
            if owned_partial:
                partial.unlink(missing_ok=True)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Report must not exist")
    try:
        result = build(args.source, args.output, args.lock)
        with args.report.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
            out.write("\n")
    except (GuardBuildError, guard.AuditError, static_audit.AuditError, boot.BuildError, OSError, ValueError,
            RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Guarded build failed: {exc}", file=sys.stderr)
        return 1
    print("Guarded candidate built and host-verified; device boot remains untested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
