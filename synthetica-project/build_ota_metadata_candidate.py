#!/usr/bin/env python3
"""Build candidate 03: repair ONLY the two OTA property-file entries.

The input is the pinned, separately held candidate 02, never a live device.
Both metadata encodings are updated together, stored uncompressed per AOSP's
property-files contract, and checked against actual ZIP local offsets. All
other uncompressed contents and compressed streams must remain byte-identical.
This does not sign the archive, repair VINTF/AVB, or authorize flashing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "third_party/aosp_ota_metadata"))
import ota_metadata_pb2  # noqa: E402
from google.protobuf.message import DecodeError  # noqa: E402

import audit_boot_first_installer as audit
import build_boot_candidate as boot
import build_guarded_candidate as previous
import verify_preservation as guard

BASE_NAME = previous.OUTPUT_NAME
BASE_BYTES = 4_713_790_039
BASE_SHA = "395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372"
OUTPUT_NAME = "synthetica-boot-first-20261102-03-ota-metadata.zip"
METADATA = audit.METADATA
METADATA_PB = audit.METADATA_PB
CHANGED = frozenset((METADATA, METADATA_PB))
PROPERTY_NAMES = frozenset(("ota-property-files", "ota-streaming-property-files"))
RESERVED = 96
MAX_METADATA = 64 * 1024
CHUNK = 4 * 1024 * 1024


class OtaBuildError(Exception):
    """Input identity, authorized scope, or independent verification failed."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_legacy(data: bytes) -> tuple[list[tuple[bytes, bytes]], dict[str, str]]:
    if len(data) > MAX_METADATA or not data.endswith(b"\n") or b"\r" in data:
        raise OtaBuildError("Legacy OTA metadata must be bounded, newline-terminated UTF-8")
    lines = []
    values = {}
    try:
        for line in data.splitlines(keepends=True):
            if not line.endswith(b"\n") or b"=" not in line:
                raise OtaBuildError("Malformed legacy OTA metadata line")
            key, value = line[:-1].split(b"=", 1)
            k = key.decode("ascii")
            v = value.decode("utf-8")
            if not k or k in values:
                raise OtaBuildError("Duplicate or empty legacy metadata key")
            values[k] = v
            lines.append((key, value))
    except UnicodeError as exc:
        raise OtaBuildError("Invalid legacy metadata encoding") from exc
    return lines, values


def parse_proto(data: bytes):
    if not data or len(data) > MAX_METADATA:
        raise OtaBuildError("OTA protobuf must be bounded and nonempty")
    msg = ota_metadata_pb2.OtaMetadata()
    try:
        msg.ParseFromString(data)
    except DecodeError as exc:
        raise OtaBuildError("Malformed AOSP OTA metadata protobuf") from exc
    return msg


def nonproperty_proto(msg) -> bytes:
    clone = ota_metadata_pb2.OtaMetadata()
    clone.CopyFrom(msg)
    clone.ClearField("property_files")
    return clone.SerializeToString(deterministic=True)


def token_names(value: str) -> list[str]:
    tokens = []
    for token in value.strip().split(","):
        match = re.fullmatch(r"(metadata(?:\.pb)?):([0-9]+):([0-9]+)", token)
        if not match:
            raise OtaBuildError("Only the two existing metadata property-file tokens are supported")
        tokens.append(match.group(1))
    if len(tokens) != 2 or set(tokens) != {"metadata", "metadata.pb"}:
        raise OtaBuildError("Property files must reference metadata and metadata.pb exactly once")
    return tokens


def property_values(legacy: bytes, protobuf: bytes) -> tuple[dict[str, str], dict[str, list[str]]]:
    _, text = parse_legacy(legacy)
    proto = parse_proto(protobuf)
    props = dict(proto.property_files)
    if not props or not set(props).issubset(PROPERTY_NAMES):
        raise OtaBuildError("Unexpected or absent protobuf property-files fields")
    text_prop_keys = {name for name in text if name in PROPERTY_NAMES or name.endswith("property-files")}
    if text_prop_keys != set(props):
        raise OtaBuildError("Legacy and protobuf property-file keys differ")
    names = {}
    for key, value in props.items():
        if text[key] != value:
            raise OtaBuildError("Legacy and protobuf property-file values differ")
        names[key] = token_names(value)
    return props, names


def rewrite_legacy(original: bytes, replacements: dict[str, str]) -> bytes:
    lines, _ = parse_legacy(original)
    found = set()
    out = bytearray()
    for key, value in lines:
        name = key.decode("ascii")
        if name in replacements:
            value = replacements[name].encode("ascii")
            found.add(name)
        out.extend(key + b"=" + value + b"\n")
    if found != set(replacements):
        raise OtaBuildError("Legacy property-file key disappeared during rewrite")
    return bytes(out)


def rewrite_proto(original: bytes, replacements: dict[str, str]) -> bytes:
    msg = parse_proto(original)
    if set(msg.property_files) != set(replacements):
        raise OtaBuildError("Protobuf property-file keys disappeared during rewrite")
    before = nonproperty_proto(msg)
    for key, value in replacements.items():
        msg.property_files[key] = value
    if nonproperty_proto(msg) != before:
        raise OtaBuildError("Non-property OTA protobuf fields unexpectedly changed")
    return msg.SerializeToString(deterministic=True)


def cloned_info(info: zipfile.ZipInfo, content: bytes | None = None) -> zipfile.ZipInfo:
    # Candidate 02 uses no encryption, data descriptors or encoding flags. Fail
    # closed on different local layouts instead of guessing descriptor length.
    if info.flag_bits != 0:
        raise OtaBuildError("Unexpected ZIP flags or data descriptor in candidate 02")
    result = boot._new_zipinfo(info)
    result.flag_bits = info.flag_bits
    result.reserved = info.reserved
    if content is None:
        result.CRC = info.CRC
        result.file_size = info.file_size
        result.compress_size = info.compress_size
    else:
        result.compress_type = zipfile.ZIP_STORED
        result.CRC = zlib.crc32(content) & 0xFFFFFFFF
        result.file_size = result.compress_size = len(content)
    return result


def planned_metadata(old_text: bytes, old_proto: bytes, source_infos: dict) -> tuple[bytes, bytes, dict]:
    _, names = property_values(old_text, old_proto)
    placeholders = {key: " " * RESERVED for key in names}
    p = rewrite_proto(old_proto, placeholders)
    t = rewrite_legacy(old_text, placeholders)
    # AOSP WriteMetadata writes protobuf first, then legacy metadata. The
    # property-file values are fixed-width (space-padded) so final offsets and
    # sizes do not change when actual numbers replace placeholders.
    pinfo = cloned_info(source_infos[METADATA_PB], p)
    tinfo = cloned_info(source_infos[METADATA], t)
    p_offset = len(pinfo.FileHeader())
    t_offset = p_offset + len(p) + len(tinfo.FileHeader())
    positions = {"metadata": (t_offset, len(t)), "metadata.pb": (p_offset, len(p))}
    replacement = {}
    for key, ordered in names.items():
        value = ",".join(f"{name}:{positions[name][0]}:{positions[name][1]}" for name in ordered)
        if len(value) > RESERVED:
            raise OtaBuildError("Reserved property-file value is insufficient")
        replacement[key] = value.ljust(RESERVED)
    final_p = rewrite_proto(old_proto, replacement)
    final_t = rewrite_legacy(old_text, replacement)
    if len(final_p) != len(p) or len(final_t) != len(t):
        raise OtaBuildError("OTA metadata finalization changed a reserved length")
    property_values(final_t, final_p)
    return final_t, final_p, positions


def add_precompressed(zout: zipfile.ZipFile, source_file, info: zipfile.ZipInfo) -> None:
    """Write a new local header and copy one already-verified raw stream.

    zipfile writes the central directory and ZIP64 records at close. Member
    data is never recompressed. A separately reopened archive verifies all
    content/CRCs, header offsets, and raw stream identity after this step.
    """
    clone = cloned_info(info)
    clone.header_offset = zout.fp.tell()
    zout.fp.write(clone.FileHeader())
    source_file.seek(previous._raw_data_offset(source_file, info))
    remaining = info.compress_size
    while remaining:
        block = source_file.read(min(CHUNK, remaining))
        if not block:
            raise OtaBuildError("Short compressed source stream")
        zout.fp.write(block)
        remaining -= len(block)
    zout.filelist.append(clone)
    zout.NameToInfo[clone.filename] = clone
    zout.start_dir = zout.fp.tell()


def add_stored(zout: zipfile.ZipFile, info: zipfile.ZipInfo, content: bytes) -> None:
    clone = cloned_info(info, content)
    clone.header_offset = zout.fp.tell()
    zout.fp.write(clone.FileHeader())
    zout.fp.write(content)
    zout.filelist.append(clone)
    zout.NameToInfo[clone.filename] = clone
    zout.start_dir = zout.fp.tell()


def compare_compressed(source: Path, output: Path, source_infos: dict, output_infos: dict) -> None:
    with source.open("rb") as old, output.open("rb") as new:
        for name, a in source_infos.items():
            if name in CHANGED or a.is_dir():
                continue
            b = output_infos[name]
            if (a.compress_type, a.compress_size) != (b.compress_type, b.compress_size):
                raise OtaBuildError(f"Unchanged compressed stream metadata differs: {name}")
            old.seek(previous._raw_data_offset(old, a))
            new.seek(previous._raw_data_offset(new, b))
            remaining = a.compress_size
            while remaining:
                count = min(CHUNK, remaining)
                left, right = old.read(count), new.read(count)
                if len(left) != count or len(right) != count or left != right:
                    raise OtaBuildError(f"Unchanged compressed stream differs: {name}")
                remaining -= count


def verify_ota(path: Path, old_text: bytes, old_proto: bytes) -> dict:
    layout, small = audit.archive_info(path)  # independent local/central & ZIP64 audit
    text, proto = small[METADATA], small[METADATA_PB]
    props, ordered = property_values(text, proto)
    old_lines, _ = parse_legacy(old_text)
    new_lines, _ = parse_legacy(text)
    if len(old_lines) != len(new_lines):
        raise OtaBuildError("A non-property legacy OTA metadata line changed")
    for (ok, ov), (nk, nv) in zip(old_lines, new_lines):
        if ok != nk or (ok.decode("ascii") not in props and ov != nv):
            raise OtaBuildError("A non-property legacy OTA metadata field changed")
    if nonproperty_proto(parse_proto(old_proto)) != nonproperty_proto(parse_proto(proto)):
        raise OtaBuildError("A non-property protobuf OTA metadata field changed")
    rows = {item["name"]: item for item in layout["entries"]}
    by_short = {"metadata": METADATA, "metadata.pb": METADATA_PB}
    observations = []
    with path.open("rb") as raw:
        for key, value in props.items():
            tokens = value.strip().split(",")
            if [part.split(":")[0] for part in tokens] != ordered[key]:
                raise OtaBuildError("Property token order changed")
            for token in tokens:
                short, offset, length = token.split(":")
                name = by_short[short]
                row = rows[name]
                offset, length = int(offset), int(length)
                if (row["method"] != zipfile.ZIP_STORED or row["compressed_bytes"] != length
                        or row["uncompressed_bytes"] != length or row["data_offset"] != offset):
                    raise OtaBuildError(f"Incorrect actual OTA offset/length or compression: {name}")
                raw.seek(offset)
                if raw.read(length) != small[name]:
                    raise OtaBuildError("Direct range bytes differ from the uncompressed metadata")
                observations.append({"property": key, "name": short, "offset": offset,
                                     "bytes": length, "stored": True, "direct_range_matches": True})
    return {"property_files": observations, "entry_count": layout["entry_count"],
            "zip_comment_bytes": layout["zip_comment_bytes"],
            "central_directory_offset": layout["central_directory_offset"],
            "legacy_and_protobuf_values_equal": True,
            "nonproperty_fields_unchanged": True}


def build(source: Path, output: Path, lock_path: Path) -> dict:
    source, output = source.absolute(), output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise OtaBuildError("Output must be a new regular path in an existing directory")
    partial = output.with_name(output.name + ".partial")
    if partial.exists() or partial.is_symlink():
        raise OtaBuildError("Refusing to overwrite a partial output")
    snapshot = previous.file_identity(source, BASE_BYTES, BASE_SHA)
    owned_partial = False
    with guard._open_regular(source)[0] as source_file:
        before = guard._snapshot(os.fstat(source_file.fileno()))
        if before != snapshot:
            raise OtaBuildError("Source changed after its identity check")
        try:
            with zipfile.ZipFile(guard._BoundedZipReader(source_file), "r", allowZip64=True) as zin:
                if zin.comment:
                    raise OtaBuildError("Candidate 02 must have the audited empty ZIP comment")
                script = zin.read(previous.SCRIPT)
                if len(script) != 1569 or digest(script) != previous.NEW_SCRIPT_SHA:
                    raise OtaBuildError("Candidate 02 installer script is not the pinned guarded script")
                expected = previous.expectations(lock_path, script)
                source_infos = previous.zip_members(zin, expected)
                old_text = zin.read(METADATA)
                old_proto = zin.read(METADATA_PB)
                for name, data in ((METADATA, old_text), (METADATA_PB, old_proto)):
                    spec = expected[name]
                    if len(data) != spec["bytes"] or digest(data) != spec["sha256"]:
                        raise OtaBuildError(f"Source metadata does not match the locked baseline: {name}")
                text, proto, planned = planned_metadata(old_text, old_proto, source_infos)
                # Check every source member's SHA-256 and ZIP CRC before raw copying.
                for info in source_infos.values():
                    spec = expected[info.filename]
                    if info.is_dir():
                        if not spec.get("directory") or info.file_size or info.compress_size:
                            raise OtaBuildError("A source directory differs from its lock")
                    else:
                        previous.inspect_member(zin, info, spec)
                    if info.flag_bits != 0:
                        raise OtaBuildError("Unsupported source ZIP flags")
                print("Source ZIP, all members and CRCs verified; writing candidate 03.", flush=True)
                with zipfile.ZipFile(partial, "x", allowZip64=True) as zout:
                    owned_partial = True
                    zout.comment = zin.comment
                    add_stored(zout, source_infos[METADATA_PB], proto)
                    add_stored(zout, source_infos[METADATA], text)
                    for info in sorted(source_infos.values(), key=lambda item: item.header_offset):
                        if info.filename not in CHANGED:
                            add_precompressed(zout, source_file, info)
                guard._check_unchanged(source, source_file, before)
                print("Candidate written; independently verifying contents and compressed streams.", flush=True)
                output_expected = {name: dict(spec) for name, spec in expected.items()}
                for name, data in ((METADATA, text), (METADATA_PB, proto)):
                    output_expected[name]["bytes"] = len(data)
                    output_expected[name]["sha256"] = digest(data)
                with zipfile.ZipFile(partial, "r", allowZip64=True) as check:
                    output_infos = previous.zip_members(check, output_expected)
                    if check.comment != zin.comment:
                        raise OtaBuildError("ZIP comment changed")
                    verified = []
                    for name, info in output_infos.items():
                        src = source_infos[name]
                        if name not in CHANGED and previous.metadata_tuple(info) != previous.metadata_tuple(src):
                            raise OtaBuildError(f"Unexpected ZIP member attributes changed: {name}")
                        spec = output_expected[name]
                        if spec.get("directory"):
                            if not info.is_dir() or info.file_size or info.compress_size:
                                raise OtaBuildError("Output directory entry changed")
                        else:
                            verified.append(previous.inspect_member(check, info, spec))
                    compare_compressed(source, partial, source_infos, output_infos)
                guard._check_unchanged(source, source_file, before)
            ota = verify_ota(partial, old_text, old_proto)
            if ota["zip_comment_bytes"] != 0:
                raise OtaBuildError("Output unexpectedly has a ZIP comment")
            for item in ota["property_files"]:
                if (item["offset"], item["bytes"]) != planned[item["name"]]:
                    raise OtaBuildError("Final offset differs from the precomputed position")
            output_bytes, output_sha = boot.digest_file(partial)
            guard._check_unchanged(source, source_file, before)
            with partial.open("rb") as result:
                os.fsync(result.fileno())
            os.link(partial, output, follow_symlinks=False)  # do not overwrite a racing path
            partial.unlink()
            return {
                "schema": "synthetica-boot-first-ota-metadata-repair-v1",
                "status": "host_verified_not_device_tested_not_flash_approved",
                "source": {"name": source.name, "bytes": BASE_BYTES, "sha256": BASE_SHA},
                "output": {"name": output.name, "bytes": output_bytes, "sha256": output_sha,
                           "signed_by_this_recipe": False},
                "approved_change": "Only OTA property-file values in metadata and metadata.pb; store both uncompressed",
                "changed_members": sorted(CHANGED),
                "metadata_original_sha256": {METADATA: digest(old_text), METADATA_PB: digest(old_proto)},
                "output_members": verified,
                "source_all_member_hashes_and_crc_verified": True,
                "unchanged_member_uncompressed_content_verified": True,
                "unchanged_member_compressed_streams_identical": True,
                "source_unchanged_during_build": True,
                "ota_metadata_verification": ota,
                "aosp_schema_commit": "045a3d6a3e359633a14853a5a5e1e4f2a11cbdae",
                "limitations": [
                    "This repairs OTA packaging metadata only, not the system, vendor, kernel or security policy.",
                    "A partial VINTF snapshot previously reported incompatibilities; device compatibility remains unproven.",
                    "The ZIP is not signed by this recipe; trusted recovery signature and device AVB chain are unverified.",
                    "No recovery, partition, flash, wipe or device boot was tested or performed.",
                    "Installer guards cannot undo prior writes and do not guarantee successful writes or boot.",
                ],
            }
        finally:
            if owned_partial and partial.exists():
                partial.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("original-baseline.lock.json"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise OtaBuildError("Report must be a new path in an existing directory")
    report = build(args.source, args.output, args.lock)
    with args.report.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Candidate 03 SHA-256: {report['output']['sha256']}", flush=True)
    print("HOLD: unsigned; VINTF/AVB/device boot are not verified.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OtaBuildError, previous.GuardBuildError, boot.BuildError, guard.AuditError,
            audit.AuditError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"OTA metadata build refused: {exc}")
