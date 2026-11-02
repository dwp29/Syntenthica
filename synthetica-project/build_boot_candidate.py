#!/usr/bin/env python3
"""Build the specifically approved, experimental boot-first ROM candidate.

Scope: from the byte-locked original ZIP, add exactly one non-executable
/system/etc/synthetica-build-info.txt to a copy of its ext4 system filesystem,
embed that filesystem at its original extent within super.img, and repack the
original installer and images. No other file, application, boot image, DTBO,
vendor partition, firmware, recovery, AVB setting, or module is intentionally
changed. The output is untested on a device and is NOT a claim of safe flash.

This script never accesses a device, runs the Android installer, signs the ZIP,
or modifies its input. It fails closed on an unexpected difference. It uses
external e2fsprogs and pytsk3; see README for pinning and limitations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import compare_ext4_boot as ext4_guard
import verify_preservation as guard

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("synthetica_lp_metadata", ROOT / "research/hyperos4/lp_metadata.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load the bounded LP metadata parser")
lp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lp)

BUILD_ID = "synthetica-boot-first-20261102-01"
EXPECTED_SOURCE = "454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63"
MARKER_BYTES = (
    "Synthetica-Project\n"
    f"Build: {BUILD_ID}\n"
    "Stage: experimental boot-first; device boot not yet verified\n"
    "Base: original diza HyperOS 4 miatoll port\n"
    f"Original ZIP SHA-256: {EXPECTED_SOURCE}\n"
    "Scope: non-executable build identification only; no additional features or modules\n"
).encode("ascii")
SCHEMA = "synthetica-boot-first-candidate-v1"
CHUNK = 4 * 1024 * 1024
SAFETY_MARGIN = 2 * 1024 * 1024 * 1024
DEBUGFS = "/usr/sbin/debugfs"
E2FSCK = "/usr/sbin/e2fsck"
FIXED_TIME = "1230768000"  # 2009-01-01 00:00:00 UTC; matches baseline image timestamps.


class BuildError(Exception):
    """An input, verification, or approved-change gate failed."""


def digest_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
            count += len(block)
    return count, digest.hexdigest()


def _snapshot(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _check_source(source: Path, expected: tuple[int, ...]) -> None:
    if _snapshot(source.lstat()) != expected:
        raise BuildError("Source archive changed or was replaced")


def choose_system_extent(prefix: bytes, super_bytes: int, locked_partitions: dict) -> tuple[dict, list[dict]]:
    """Accept only matching LP geometry/metadata and one nonoverlapping extent per partition."""
    result = lp.inspect_raw_super(prefix, super_bytes)
    if not result.get("geometry_copies_match"):
        raise BuildError("LP primary/backup geometry does not match")
    slots = result.get("metadata_slots", [])
    if not slots or any(not slot.get("copies_match") for slot in slots):
        raise BuildError("LP primary/backup metadata copies do not match")
    first = slots[0]["primary"]
    if any(slot["primary"].get("header_and_tables_sha256") != first.get("header_and_tables_sha256") for slot in slots):
        raise BuildError("LP metadata slots differ")
    parts = first.get("partitions", [])
    if set(p["name"] for p in parts) != set(locked_partitions):
        raise BuildError("Unexpected logical partition set")
    devices = first.get("block_devices", [])
    if len(devices) != 1 or devices[0]["name"] != "super" or devices[0]["size_bytes_declared"] != super_bytes:
        raise BuildError("Unsupported or unexpected super block device")
    extents = []
    for part in parts:
        extent = part.get("first_extent")
        expected = locked_partitions[part["name"]]
        if (part.get("extent_count") != 1 or not extent or extent.get("type") != 0
                or extent.get("source_index") != 0 or part.get("bytes") != expected.get("bytes")):
            raise BuildError("A partition has an unsupported extent or unexpected size")
        begin = extent["target_sector"] * 512
        end = begin + part["bytes"]
        if begin < 1024 * 1024 or end > super_bytes or end <= begin:
            raise BuildError("Partition extent overlaps metadata or is outside super")
        extents.append({"name": part["name"], "begin": begin, "end": end, "bytes": part["bytes"]})
    ordered = sorted(extents, key=lambda p: p["begin"])
    if any(a["end"] > b["begin"] for a, b in zip(ordered, ordered[1:])):
        raise BuildError("Logical partition extents overlap")
    system = next((p for p in ordered if p["name"] == "system"), None)
    if system is None:
        raise BuildError("The locked system partition is missing")
    return system, ordered


def extract_system(source: Path, lock: dict, work: Path) -> tuple[dict, list[dict], Path]:
    expected = {e["name"]: e for e in lock["identity"]["entries"] if not e.get("directory")}
    super_spec = expected["super.img"]
    system_path = work / "system-original.img"
    super_hash, system_hash = hashlib.sha256(), hashlib.sha256()
    count = written = 0
    with zipfile.ZipFile(source, "r", allowZip64=True) as z, z.open("super.img") as src, system_path.open("xb") as dst:
        prefix = src.read(lp.MAX_PREFIX)
        if len(prefix) != min(lp.MAX_PREFIX, super_spec["bytes"]):
            raise BuildError("Could not read the LP metadata prefix")
        system, parts = choose_system_extent(prefix, super_spec["bytes"], lock["logical_partitions"])
        for block in _prepend(prefix, src):
            end = count + len(block)
            super_hash.update(block)
            if count < system["end"] and end > system["begin"]:
                selected = block[max(0, system["begin"] - count):min(len(block), system["end"] - count)]
                dst.write(selected)
                system_hash.update(selected)
                written += len(selected)
            count = end
            if count and count % (2 * 1024**3) == 0:
                print(f"Read {count // (1024**3)} / 8 GiB of original super", flush=True)
        dst.flush()
        os.fsync(dst.fileno())
    system_spec = lock["logical_partitions"]["system"]
    if (count != super_spec["bytes"] or super_hash.hexdigest() != super_spec["sha256"]
            or written != system_spec["bytes"] or system_hash.hexdigest() != system_spec["sha256"]):
        raise BuildError("Source super or extracted system differs from its lock")
    if digest_file(system_path) != (written, system_hash.hexdigest()):
        raise BuildError("Original system copy failed readback")
    return system, parts, system_path


def _prepend(first: bytes, stream):
    if first:
        yield first
    while block := stream.read(CHUNK):
        yield block


def edit_system(original: Path, work: Path) -> tuple[Path, dict]:
    candidate = work / "system-candidate.img"
    shutil.copyfile(original, candidate)
    marker = work / "marker.txt"
    label = work / "label.bin"
    marker.write_bytes(MARKER_BYTES)
    label.write_bytes(b"u:object_r:system_file:s0\0")
    for path in (original, candidate):
        with path.open("rb") as f:
            f.seek(-64, os.SEEK_END)
            if f.read(4) == b"AVBf":
                raise BuildError("An AVB footer is present; this edit recipe does not change or sign AVB")
    # The directory is private, newly created, and deliberately restricted to
    # shell/debugfs-safe path characters; no user input is interpolated as code.
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", str(work)):
        raise BuildError("Work directory contains unsupported debugfs path characters")
    command_file = work / "debugfs.commands"
    command_file.write_text(
        f"write {marker} {ext4_guard.MARKER}\n"
        f"sif {ext4_guard.MARKER} mode 0100644\n"
        f"sif {ext4_guard.MARKER} uid 0\n"
        f"sif {ext4_guard.MARKER} gid 0\n"
        f"ea_set -f {label} {ext4_guard.MARKER} security.selinux\n",
        encoding="ascii",
    )
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "E2FSPROGS_FAKE_TIME": FIXED_TIME}
    run = subprocess.run([DEBUGFS, "-w", "-f", str(command_file), str(candidate)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    (work / "debugfs-build.log").write_bytes(run.stdout + run.stderr)
    if run.returncode or b"Allocated inode:" not in run.stdout:
        raise BuildError("debugfs did not create the marker")
    check = subprocess.run([E2FSCK, "-f", "-n", str(candidate)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    (work / "e2fsck-candidate.log").write_bytes(check.stdout + check.stderr)
    if check.returncode != 0:
        raise BuildError(f"Read-only e2fsck rejected the candidate (exit {check.returncode})")
    result = ext4_guard.compare(original, candidate, MARKER_BYTES, DEBUGFS)
    return candidate, result


def _strip_zip64(extra: bytes) -> bytes:
    pos, kept = 0, bytearray()
    while pos < len(extra):
        if pos + 4 > len(extra):
            raise BuildError("Malformed ZIP extra field")
        kind, length = struct.unpack_from("<HH", extra, pos)
        end = pos + 4 + length
        if end > len(extra):
            raise BuildError("Truncated ZIP extra field")
        if kind != 1:  # Fresh ZIP64 offsets/sizes are generated for the output.
            kept.extend(extra[pos:end])
        pos = end
    return bytes(kept)


def _new_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise BuildError("Unsupported source ZIP compression method")
    out = zipfile.ZipInfo(info.filename, info.date_time)
    out.compress_type = info.compress_type
    out.create_system = info.create_system
    out.create_version = info.create_version
    out.extract_version = info.extract_version
    out.internal_attr = info.internal_attr
    out.external_attr = info.external_attr
    out.comment = info.comment
    out.extra = _strip_zip64(info.extra)
    out.file_size = info.file_size
    out._compresslevel = 1  # Fast, deterministic for a fixed Python/zlib toolchain.
    return out


def _replace_system(src, dst, replacement, system: dict, expected_old_sha: str,
                    expected_new_system_sha: str) -> dict:
    old_hash, new_hash, replacement_hash = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    count = replaced = 0
    while block := src.read(CHUNK):
        end = count + len(block)
        old_hash.update(block)
        if count < system["end"] and end > system["begin"]:
            lo = max(0, system["begin"] - count)
            hi = min(len(block), system["end"] - count)
            data = replacement.read(hi - lo)
            if len(data) != hi - lo:
                raise BuildError("Candidate system image ended early")
            replacement_hash.update(data)
            replaced += len(data)
            block = block[:lo] + data + block[hi:]
        dst.write(block)
        new_hash.update(block)
        count = end
        if count and count % (2 * 1024**3) == 0:
            print(f"Repacked {count // (1024**3)} / 8 GiB of super", flush=True)
    if (old_hash.hexdigest() != expected_old_sha or replacement_hash.hexdigest() != expected_new_system_sha
            or replaced != system["bytes"] or replacement.read(1)):
        raise BuildError("Super replacement input/hash/size verification failed")
    return {"bytes": count, "old_sha256": old_hash.hexdigest(), "sha256": new_hash.hexdigest()}


def package(source: Path, lock: dict, candidate_system: Path, system: dict, output: Path) -> dict:
    expected = {e["name"]: e for e in lock["identity"]["entries"] if not e.get("directory")}
    new_system_bytes, new_system_sha = digest_file(candidate_system)
    if new_system_bytes != system["bytes"]:
        raise BuildError("Candidate system size changed")
    super_result = None
    with zipfile.ZipFile(source, "r", allowZip64=True) as zin, zipfile.ZipFile(
            output, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True, compresslevel=1) as zout:
        zout.comment = zin.comment
        infos = sorted(zin.infolist(), key=lambda item: item.header_offset)
        for info in infos:
            new_info = _new_zipinfo(info)
            if info.is_dir():
                zout.writestr(new_info, b"")
                continue
            with zin.open(info, "r") as src, zout.open(
                    new_info, "w", force_zip64=info.file_size >= zipfile.ZIP64_LIMIT) as dst:
                if info.filename == "super.img":
                    with candidate_system.open("rb") as replacement:
                        super_result = _replace_system(src, dst, replacement, system,
                                                       expected["super.img"]["sha256"], new_system_sha)
                    if super_result["bytes"] != expected["super.img"]["bytes"]:
                        raise BuildError("Output super size is incorrect")
                else:
                    digest, count = hashlib.sha256(), 0
                    while block := src.read(CHUNK):
                        dst.write(block)
                        digest.update(block)
                        count += len(block)
                    item = expected.get(info.filename)
                    if item is None or count != item["bytes"] or digest.hexdigest() != item["sha256"]:
                        raise BuildError(f"Source ZIP member changed: {info.filename}")
    if super_result is None or super_result["sha256"] == super_result["old_sha256"]:
        raise BuildError("Output does not contain the approved system change")
    with output.open("rb") as f:
        os.fsync(f.fileno())
    return {"system_bytes": new_system_bytes, "system_sha256": new_system_sha, "super": super_result}


def compare_super_streams(source: Path, candidate: Path, system: dict, parts: list[dict], lock: dict,
                          expected_new_system_sha: str) -> dict:
    """Compare every super byte outside system, and hash all candidate partitions."""
    part_hashes = {part["name"]: hashlib.sha256() for part in parts}
    part_counts = {part["name"]: 0 for part in parts}
    offset = 0
    with zipfile.ZipFile(source) as oldzip, zipfile.ZipFile(candidate) as newzip, \
            oldzip.open("super.img") as old, newzip.open("super.img") as new:
        while True:
            a, b = old.read(CHUNK), new.read(CHUNK)
            if len(a) != len(b):
                raise BuildError("Super images have different stream lengths")
            if not a:
                break
            end = offset + len(a)
            if offset < system["begin"]:
                n = min(len(a), system["begin"] - offset)
                if a[:n] != b[:n]:
                    raise BuildError("Super bytes before system changed")
            if end > system["end"]:
                n = max(0, system["end"] - offset)
                if a[n:] != b[n:]:
                    raise BuildError("Super bytes after system changed")
            for part in parts:
                if offset < part["end"] and end > part["begin"]:
                    data = b[max(0, part["begin"] - offset):min(len(b), part["end"] - offset)]
                    part_hashes[part["name"]].update(data)
                    part_counts[part["name"]] += len(data)
            offset = end
            if offset and offset % (2 * 1024**3) == 0:
                print(f"Compared {offset // (1024**3)} / 8 GiB of super", flush=True)
    result = []
    for part in parts:
        name = part["name"]
        actual = part_hashes[name].hexdigest()
        expected = expected_new_system_sha if name == "system" else lock["logical_partitions"][name]["sha256"]
        if part_counts[name] != part["bytes"] or actual != expected:
            raise BuildError(f"Candidate partition readback failed: {name}")
        result.append({"name": name, "bytes": part_counts[name], "sha256": actual,
                       "matches_original": name != "system"})
    return {"super_bytes_compared": offset, "outside_system_exactly_unchanged": True,
            "zip_crc_checked_at_eof_for_both": True, "partitions": result}


def build(source: Path, lock_path: Path, output_dir: Path) -> dict:
    source = source.absolute()
    output_dir = output_dir.absolute()
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", str(output_dir)):
        raise BuildError("Output directory contains unsupported characters")
    if output_dir.exists() or output_dir.is_symlink():
        raise BuildError("Output directory already exists")
    if not output_dir.parent.is_dir():
        raise BuildError("Output directory parent does not exist")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("identity", {}).get("zip_sha256") != EXPECTED_SOURCE:
        raise BuildError("This recipe only accepts the specifically approved original ZIP")
    if ext4_guard.pytsk3 is None or ext4_guard.pytsk3.get_version() != "20260715":
        raise BuildError("The pinned pytsk3 20260715 comparator is required")
    with guard._open_regular(source)[0] as f:
        before = _snapshot(os.fstat(f.fileno()))
    audit = guard.audit_candidate(lock_path, source)
    if audit.get("status") != "exact_original_not_a_new_build":
        raise BuildError("Source failed the complete original-ZIP preservation guard")
    _check_source(source, before)
    system_bytes = lock["logical_partitions"]["system"]["bytes"]
    required = system_bytes * 2 + lock["identity"]["zip_bytes"] + SAFETY_MARGIN
    if shutil.disk_usage(output_dir.parent).free < required:
        raise BuildError("Insufficient free space for separate input, images, output, and safety margin")
    output_dir.mkdir(mode=0o700)
    partial = output_dir / f"{BUILD_ID}.zip.partial"
    final = output_dir / f"{BUILD_ID}.zip"
    try:
        print("Source lock and complete original ZIP verified", flush=True)
        system, parts, original_system = extract_system(source, lock, output_dir)
        _check_source(source, before)
        print("Original system extracted and rechecked", flush=True)
        candidate_system, filesystem_audit = edit_system(original_system, output_dir)
        print("Approved marker created; e2fsck and filesystem comparison passed", flush=True)
        package_result = package(source, lock, candidate_system, system, partial)
        _check_source(source, before)
        print("Candidate ZIP written; starting independent readback", flush=True)
        output_audit = guard.audit_candidate(lock_path, partial)
        if (output_audit.get("status") != "content_changed_review_required"
                or output_audit.get("mismatches") != [{"name": "super.img", "reason": "sha256_changed"}]):
            raise BuildError("Output ZIP differs in an unapproved member, is corrupt, or was not changed")
        readback = compare_super_streams(source, partial, system, parts, lock, package_result["system_sha256"])
        _check_source(source, before)
        source_bytes, source_sha = digest_file(source)
        _check_source(source, before)
        if source_bytes != lock["identity"]["zip_bytes"] or source_sha != EXPECTED_SOURCE:
            raise BuildError("Source archive final SHA-256 does not match its lock")
        candidate_bytes, candidate_sha = digest_file(partial)
        os.replace(partial, final)
        report = {
            "schema": SCHEMA,
            "build_id": BUILD_ID,
            "status": "experimental_candidate_host_verified_not_device_tested",
            "approved_change": "One non-executable build-identification file in system; no additional features or modules",
            "source": {"zip_bytes": source_bytes, "sha256": source_sha, "matches_lock": True},
            "output": {"name": final.name, "zip_bytes": candidate_bytes, "sha256": candidate_sha,
                       "signed_by_this_recipe": False},
            "filesystem_audit": filesystem_audit,
            "packaging": package_result,
            "zip_member_preservation": output_audit,
            "super_comparison": readback,
            "module_policy": "all Magisk/KSU modules remain on hold; none added",
            "limitations": [
                "No device boot, firmware, recovery, encryption, or physical partition test was performed.",
                "An absent AVB footer on the system image does not prove compatibility with external vbmeta/AVB.",
                "The ZIP was repacked without signing; original installer and OTA metadata are preserved, but recovery acceptance is unverified.",
                "Do not consider this stable or flash-ready solely on host checks; backup and a separate device/recovery review are required."
            ],
        }
        (output_dir / "BUILD-REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
        return report
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Byte-locked original ZIP; read only")
    parser.add_argument("output_dir", type=Path, help="New private work directory; must not already exist")
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.lock, args.output_dir)
    except (BuildError, ext4_guard.ComparisonError, OSError, ValueError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
