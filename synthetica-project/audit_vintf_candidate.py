#!/usr/bin/env python3
"""Inventory VINTF declarations from the existing guarded candidate, read-only.

On a disposable host, reassemble the three already verified draft assets and
stream the pinned ZIP's super member to temporary files for four logical ext4
partitions. No input image is mounted, run, modified, or uploaded; only a small
metadata report is produced. VINTF inventory and level comparison are NOT a
libvintf/checkvintf verdict, recovery test, or evidence of device boot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/hyperos4"))
import lp_metadata as lp
import audit_guarded_zip64_draft as draft
import audit_updater_emulation as emu
import build_guarded_candidate as builder
import github_guarded_release as transfer
import github_guarded_report_relay as relay
import verify_preservation as guard

try:
    import pytsk3
except ImportError:
    pytsk3 = None

CHUNK = 4 * 1024 * 1024
SUPER_BYTES = 8_589_934_592
CANDIDATE_SYSTEM_SHA256 = "1a27a6d10de5bb55d2e5a0dc543af181e8227fb9970053f1880f0e86520d01f0"
MAX_XML_BYTES = 4 * 1024 * 1024
MAX_FILES = 1000
MAX_DEPTH = 8
RESERVE_BYTES = 1024**3
ROOTS = {
    "system": ("/system/etc/vintf",),
    "system_ext": ("/etc/vintf",),
    "vendor": ("/etc/vintf", "/odm/etc/vintf"),
    "product": ("/etc/vintf",),
}
PARTITIONS = ("system", "system_ext", "vendor", "product")
SELECTED_HALS = {
    "android.hardware.audio", "android.hardware.audio.effect", "android.hardware.bluetooth",
    "android.hardware.camera.provider", "android.hardware.health", "android.hardware.power",
    "android.hardware.graphics.composer", "android.hardware.sensors", "android.hardware.nfc",
    "android.hardware.light", "android.hardware.lights", "android.hardware.gatekeeper",
    "android.hardware.keymaster", "android.hardware.security.keymint", "android.hardware.radio",
    "android.hardware.biometrics.fingerprint", "android.hardware.biometrics.face",
}


class VintfAuditError(RuntimeError):
    """A bounded audit input or consistency requirement failed."""


def part_specs(lock: dict) -> dict:
    if (lock.get("identity", {}).get("zip_sha256") != "454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63"
            or not isinstance(lock.get("logical_partitions"), dict)):
        raise VintfAuditError("Unexpected source baseline lock")
    result = {}
    for name in PARTITIONS:
        item = lock["logical_partitions"].get(name, {})
        size, sha = item.get("bytes"), item.get("sha256")
        if type(size) is not int or size <= 0 or not isinstance(sha, str) or len(sha) != 64:
            raise VintfAuditError(f"Invalid locked identity for {name}")
        result[name] = {"bytes": size, "sha256": CANDIDATE_SYSTEM_SHA256 if name == "system" else sha}
    return result


def extent_windows(prefix: bytes, super_bytes: int, specs: dict) -> dict:
    metadata = lp.inspect_raw_super(prefix, super_bytes)
    if not metadata.get("geometry_copies_match") or not metadata.get("metadata_slots"):
        raise VintfAuditError("Logical-partition geometry is missing or inconsistent")
    all_slots = metadata["metadata_slots"]
    if any(slot.get("copies_match") is not True for slot in all_slots):
        raise VintfAuditError("Logical-partition metadata copies are inconsistent")
    selected = {}
    for slot in all_slots:
        rows = slot["primary"].get("partitions", [])
        devices = slot["primary"].get("block_devices", [])
        if not devices or devices[0].get("name") != "super":
            raise VintfAuditError("Missing logical super block-device metadata")
        first_data_byte = devices[0]["first_sector"] * lp.SECTOR_BYTES
        by_name = {row["name"]: row for row in rows}
        if len(by_name) != len(rows):
            raise VintfAuditError("Duplicate logical-partition names")
        current = {}
        for name, spec in specs.items():
            row = by_name.get(name, {})
            ext = row.get("first_extent") or {}
            if (row.get("bytes") != spec["bytes"] or row.get("extent_count") != 1
                    or ext.get("type") != 0 or ext.get("source_index") != 0
                    or type(ext.get("target_sector")) is not int):
                raise VintfAuditError(f"Unsupported or unexpected extent for {name}")
            start = ext["target_sector"] * lp.SECTOR_BYTES
            end = start + spec["bytes"]
            if start < first_data_byte or end > super_bytes:
                raise VintfAuditError(f"Out-of-bounds extent for {name}")
            current[name] = {"start": start, "end": end, **spec}
        if selected and current != selected:
            raise VintfAuditError("Logical partitions differ between metadata slots")
        selected = current
    ordered = sorted((value["start"], value["end"], name) for name, value in selected.items())
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise VintfAuditError("Logical partition extents overlap")
    return selected


def copy_windows(stream, prefix: bytes, windows: dict, outputs: dict, expected_bytes: int,
                 expected_sha256: str) -> dict:
    """Copy selected ranges and hash the *complete* decompressed member to EOF."""
    h = hashlib.sha256()
    part_hash = {name: hashlib.sha256() for name in outputs}
    counts = {name: 0 for name in outputs}
    pos = 0
    next_progress = 2 * 1024**3

    def consume(block: bytes) -> None:
        nonlocal pos, next_progress
        if pos + len(block) > expected_bytes:
            raise VintfAuditError("super member exceeds its pinned size")
        h.update(block)
        for name, out in outputs.items():
            w = windows[name]
            a, b = max(pos, w["start"]), min(pos + len(block), w["end"])
            if a < b:
                section = block[a - pos:b - pos]
                out.write(section)
                part_hash[name].update(section)
                counts[name] += len(section)
        pos += len(block)
        if pos >= next_progress:
            print(f"Verified stream progress: {pos}/{expected_bytes} bytes", flush=True)
            next_progress += 2 * 1024**3

    consume(prefix)
    while block := stream.read(CHUNK):
        consume(block)
    if pos != expected_bytes or h.hexdigest() != expected_sha256:
        raise VintfAuditError("Complete super member SHA-256 or size mismatch")
    for name, output in outputs.items():
        output.flush()
        if counts[name] != windows[name]["bytes"] or part_hash[name].hexdigest() != windows[name]["sha256"]:
            raise VintfAuditError(f"Partition extent did not match pinned identity: {name}")
    return {"bytes": pos, "sha256": h.hexdigest()}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(node, name: str):
    return [item for item in node if isinstance(item.tag, str) and _local(item.tag) == name]


def _text(node, name: str) -> list[str]:
    values = []
    for item in _children(node, name):
        value = (item.text or "").strip()
        if value and len(value) <= 512:
            values.append(value)
    return values


def parse_vintf(data: bytes, partition: str, path: str) -> dict:
    """Return bounded structural facts, never the raw XML or a verdict."""
    if not data or len(data) > MAX_XML_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise VintfAuditError(f"Unsafe or oversized XML: {partition}:{path}")
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError) as exc:
        raise VintfAuditError(f"Unreadable XML: {partition}:{path}") from exc
    root_tag = _local(root.tag)
    base = {"partition": partition, "path": path, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "root": root_tag}
    if root_tag not in ("manifest", "compatibility-matrix"):
        return {**base, "ignored_non_vintf_root": True}
    hals = _children(root, "hal")
    formats = {}
    selected = []
    for hal in hals:
        fmt = hal.get("format", "hidl")
        formats[fmt] = formats.get(fmt, 0) + 1
        names = _text(hal, "name")
        if root_tag != "manifest" or root.get("type") != "device" or len(names) != 1 or names[0] not in SELECTED_HALS:
            continue
        interfaces = []
        for interface in _children(hal, "interface"):
            interfaces.append({"name": _text(interface, "name"), "instances": _text(interface, "instance"),
                               "regex_instances": _text(interface, "regex-instance")})
        selected.append({"name": names[0], "format": fmt, "versions": _text(hal, "version"),
                         "fqnames": _text(hal, "fqname"), "interfaces": interfaces})
    return {**base, "type": root.get("type"), "level": root.get("level"),
            "target_level": root.get("target-level"), "hal_count": len(hals),
            "hal_formats": dict(sorted(formats.items())), "selected_device_hals": selected}


def _read_tsk_file(entry, size: int) -> bytes:
    if size <= 0 or size > MAX_XML_BYTES:
        raise VintfAuditError("VINTF file is empty or exceeds the XML size limit")
    blocks = []
    offset = 0
    while offset < size:
        block = entry.read_random(offset, min(CHUNK, size - offset))
        if not block or len(block) > size - offset:
            raise VintfAuditError("Cannot read an entire VINTF XML file")
        blocks.append(block)
        offset += len(block)
    return b"".join(blocks)


def scan_partition(image: Path, partition: str) -> tuple[list[dict], list[dict]]:
    if pytsk3 is None:
        raise VintfAuditError("The pinned pytsk3 host dependency is missing")
    docs, roots = [], []
    try:
        disk = pytsk3.Img_Info(str(image))
        fs = pytsk3.FS_Info(disk)
        if fs.info.ftype != pytsk3.TSK_FS_TYPE_EXT4:
            raise VintfAuditError(f"{partition} is not an ext4 filesystem")
        for root_path in ROOTS[partition]:
            try:
                root_file = fs.open(path=root_path)
            except (OSError, RuntimeError, IOError):
                roots.append({"partition": partition, "path": root_path, "status": "missing_or_unreadable"})
                continue
            meta = root_file.info.meta
            if meta is None or meta.type != pytsk3.TSK_FS_META_TYPE_DIR:
                roots.append({"partition": partition, "path": root_path, "status": "not_directory_or_symlink"})
                continue
            roots.append({"partition": partition, "path": root_path, "status": "read"})
            stack = [(root_path, int(meta.addr), 0)]
            visited = set()
            while stack:
                parent, inode, depth = stack.pop()
                if inode in visited or depth > MAX_DEPTH:
                    raise VintfAuditError("VINTF directory cycle or depth limit")
                visited.add(inode)
                for entry in fs.open_dir(inode=inode):
                    info, item = entry.info.name, entry.info.meta
                    if info is None or not info.name or not (info.flags & pytsk3.TSK_FS_NAME_FLAG_ALLOC):
                        continue
                    raw = bytes(info.name)
                    if raw in (b".", b".."):
                        continue
                    if b"/" in raw or b"\0" in raw or item is None:
                        raise VintfAuditError("Invalid VINTF directory entry")
                    name = raw.decode("utf-8", "strict")
                    path = parent.rstrip("/") + "/" + name
                    if item.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        stack.append((path, int(item.addr), depth + 1))
                    elif item.type == pytsk3.TSK_FS_META_TYPE_REG and name.lower().endswith(".xml"):
                        if len(docs) >= MAX_FILES:
                            raise VintfAuditError("VINTF XML file count exceeds limit")
                        docs.append(parse_vintf(_read_tsk_file(entry, int(item.size)), partition, path))
                    elif item.type == pytsk3.TSK_FS_META_TYPE_LNK:
                        roots.append({"partition": partition, "path": path, "status": "symlink_not_followed"})
        return docs, roots
    except VintfAuditError:
        raise
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeError) as exc:
        raise VintfAuditError(f"Cannot inventory VINTF on {partition}: {exc}") from exc


def compare_levels(docs: list[dict], roots: list[dict]) -> dict:
    primary = [doc for doc in docs if doc.get("partition") == "vendor"
               and doc.get("path") == "/etc/vintf/manifest.xml"
               and doc.get("root") == "manifest" and doc.get("type") == "device"]
    if len(primary) != 1:
        raise VintfAuditError("The primary vendor device manifest is missing or ambiguous")
    target = primary[0].get("target_level")
    matrices = [doc for doc in docs if doc.get("partition") in ("system", "system_ext", "product")
                and doc.get("root") == "compatibility-matrix" and doc.get("type") == "framework"]
    if not matrices:
        raise VintfAuditError("No framework compatibility matrix XML was readable")
    explicit = sorted({doc["level"] for doc in matrices if doc.get("level") is not None})
    matches = [f"{doc['partition']}:{doc['path']}" for doc in matrices
               if target is not None and doc.get("level") == target]
    unspecified = [f"{doc['partition']}:{doc['path']}" for doc in matrices if doc.get("level") is None]
    return {"vendor_primary_target_level": target, "framework_explicit_levels_seen": explicit,
            "visible_explicit_target_level_files": sorted(matches),
            "visible_unlevelled_framework_matrix_files": sorted(unspecified),
            "scan_roots_not_fully_read": [r for r in roots if r["status"] != "read"],
            "meaning": "inventory only; not a libvintf/checkvintf compatibility verdict"}


def audit_group(candidate: Path, work: Path, names: tuple[str, ...], specs: dict) -> tuple[list[dict], list[dict], dict]:
    if shutil.disk_usage(work).free < sum(specs[n]["bytes"] for n in names) + RESERVE_BYTES:
        raise VintfAuditError("Insufficient disposable storage for extents plus safety reserve")
    with tempfile.TemporaryDirectory(prefix="vintf-partitions-", dir=work) as td:
        td = Path(td)
        paths = {name: td / f"{name}.img" for name in names}
        outputs = {}
        try:
            for name, path in paths.items():
                outputs[name] = path.open("xb")
            with guard._open_regular(candidate)[0] as source:
                opened = guard._snapshot(os.fstat(source.fileno()))
                with zipfile.ZipFile(source, "r", allowZip64=True) as archive:
                    members = [item for item in archive.infolist() if item.filename == "super.img"]
                    if len(members) != 1 or members[0].is_dir() or members[0].file_size != SUPER_BYTES or members[0].flag_bits & 1:
                        raise VintfAuditError("Candidate does not contain the unique expected super image")
                    with archive.open(members[0], "r") as stream:
                        prefix = stream.read(lp.MAX_PREFIX)
                        if len(prefix) != lp.MAX_PREFIX:
                            raise VintfAuditError("super prefix is incomplete")
                        windows = extent_windows(prefix, SUPER_BYTES, specs)
                        super_result = copy_windows(stream, prefix, windows, outputs, SUPER_BYTES, builder.BASE_SUPER_SHA)
                        # zipfile checks the member CRC when its stream reaches EOF.
                        super_result["zip_crc_checked_at_eof"] = True
                guard._check_unchanged(candidate, source, opened)
        finally:
            for output in outputs.values():
                output.close()
        docs, roots, extents = [], [], {}
        for name, path in paths.items():
            print(f"Inspecting verified {name} VINTF XML without mounting", flush=True)
            before = emu.regular_identity(path, specs[name]["bytes"], specs[name]["sha256"])
            partition_docs, partition_roots = scan_partition(path, name)
            after = emu.regular_identity(path, specs[name]["bytes"], specs[name]["sha256"])
            docs.extend(partition_docs)
            roots.extend(partition_roots)
            extents[name] = {"before": before, "after": after}
        return docs, roots, {"super": super_result, "extents": extents}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="new, empty, disposable directory")
    parser.add_argument("--report", type=Path, required=True, help="new small JSON metadata report")
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise VintfAuditError("Report must be a new file in an existing directory")
    if not args.work.is_dir() or args.work.is_symlink() or any(args.work.iterdir()):
        raise VintfAuditError("Work directory must exist, be empty, and not be a symlink")
    with (ROOT / "synthetica-project/original-baseline.lock.json").open(encoding="utf-8") as f:
        specs = part_specs(json.load(f))
    candidate = draft.download_existing_draft(args.work)
    before = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    docs, roots, groups = [], [], []
    # Two passes limit peak temporary image storage. The entire super member is
    # hashed and CRC-checked on *each* pass, not merely the selected extents.
    for group in (("system", "system_ext", "vendor"), ("product",)):
        group_docs, group_roots, info = audit_group(candidate, args.work, group, specs)
        docs.extend(group_docs)
        roots.extend(group_roots)
        groups.append(info)
    after = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    result = {
        "schema": "synthetica-vintf-readonly-inventory-v1",
        "scope": "existing guarded candidate; temporary ext4 copies inspected without mount or device",
        "candidate_before": before, "candidate_after": after,
        "groups": groups, "scan_roots": roots,
        "documents": sorted(docs, key=lambda d: (d["partition"], d["path"])),
        "level_comparison": compare_levels(docs, roots),
        "limitations": [
            "Inventory is not checkvintf, libvintf, VTS, a recovery test, or device boot evidence.",
            "Runtime SKU/ODM/APEX fragments, mounted files, property overrides, kernel and HAL behavior can differ.",
            "Unlevelled framework matrices can be combined at the device level by AOSP libvintf; missing an explicitly labelled matrix is not by itself a failure.",
            "Declarations, hashes and target levels do not establish which HAL services run or whether the device is compatible.",
            "No ROM image was modified, uploaded, installed, or executed.",
        ],
    }
    with args.report.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(f"Read {len(docs)} bounded VINTF documents; no compatibility verdict was made.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VintfAuditError, lp.LPError, draft.DraftTestError, emu.SimulationError,
            relay.RelayError, transfer.TransferError, guard.AuditError,
            OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"::error title=Read-only VINTF inventory stopped::{exc}", file=sys.stderr)
        raise SystemExit(1)
