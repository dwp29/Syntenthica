#!/usr/bin/env python3
"""Read-only structural audit of the approved boot-first ZIPs and their installer.

This does NOT run an installer, write a partition, build a ROM, authenticate the
source author, or prove recovery/AVB/device-boot compatibility. The actual
archive and embedded installer hashes are pinned so that the output does not
silently describe some other package. Only small archive members are read into
memory; the large ZIPs are streamed for identity checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import stat
import struct
import sys
import zipfile
from pathlib import Path

SOURCE_BYTES = 4_512_854_711
SOURCE_SHA256 = "454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63"
CANDIDATE_BYTES = 4_713_790_032
CANDIDATE_SHA256 = "300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8"
SCRIPT = "META-INF/com/google/android/updater-script"
BINARY = "META-INF/com/google/android/update-binary"
METADATA = "META-INF/com/android/metadata"
METADATA_PB = "META-INF/com/android/metadata.pb"
SCRIPT_SHA256 = "36cd01421779bf943e40f725daa6ce5c860f01f1150ad6bf29c09483d8ec1985"
BINARY_SHA256 = "94fb81532b96bbf78f2e8d7e9d5426bf7a7d5eec6a35f208fda9209e38839d02"
METADATA_SHA256 = "70f51292e0858d4f4f23d6d58fc2fb8bf02f9ca86dd6dae13869139492cd228d"
CHUNK = 4 * 1024 * 1024
MAX_SMALL_MEMBER = 4 * 1024 * 1024
MAX_DEBUG = 8 * 1024 * 1024
LOCAL_HEADER = struct.Struct("<4sHHHHHIIIHH")


class AuditError(Exception):
    """An input did not match the bounded read-only audit requirements."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path, expected_bytes: int, expected_sha: str) -> dict:
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes:
            raise AuditError("Input is not a regular file of the expected size")
        h = hashlib.sha256()
        total = 0
        while chunk := stream.read(CHUNK):
            h.update(chunk)
            total += len(chunk)
        after = os.fstat(stream.fileno())
    compare_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, k) != getattr(after, k) for k in compare_fields):
        raise AuditError("Input changed while being hashed")
    if total != expected_bytes or h.hexdigest() != expected_sha:
        raise AuditError("Input size or SHA-256 did not match the locked identity")
    return {"bytes": total, "sha256": h.hexdigest(), "identity_matched": True}


def extra_fields(data: bytes) -> list[tuple[int, bytes]]:
    fields = []
    pos = 0
    while pos < len(data):
        if len(data) - pos < 4:
            raise AuditError("Truncated ZIP extra-field header")
        kind, size = struct.unpack_from("<HH", data, pos)
        pos += 4
        if size > len(data) - pos:
            raise AuditError("Truncated ZIP extra-field payload")
        fields.append((kind, data[pos:pos + size]))
        pos += size
    if sum(kind == 1 for kind, _ in fields) > 1:
        raise AuditError("Duplicate ZIP64 extra fields")
    return fields


def _read_exact(stream, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise AuditError("Unexpected end of input")
    return data


def archive_info(path: Path) -> tuple[dict, dict[str, bytes]]:
    """Inspect local headers and bounded member contents without extracting files."""
    with path.open("rb") as stream, zipfile.ZipFile(stream) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or len({info.filename for info in infos}) != len(infos):
            raise AuditError("Too many or duplicate ZIP names")
        names = {info.filename for info in infos}
        required = {SCRIPT, BINARY, METADATA, METADATA_PB, "super.img", "boot.img", "dtbo.img"}
        if not required.issubset(names):
            raise AuditError("Missing a required ZIP member")
        rows = []
        for info in infos:
            stream.seek(info.header_offset)
            raw = LOCAL_HEADER.unpack(_read_exact(stream, LOCAL_HEADER.size))
            (signature, version, flags, method, _time, _date, crc, compressed32,
             uncompressed32, name_len, extra_len) = raw
            if signature != b"PK\x03\x04" or name_len > 4096 or extra_len > 65535:
                raise AuditError("Invalid local ZIP header")
            name_raw = _read_exact(stream, name_len)
            local_extra = _read_exact(stream, extra_len)
            encoding = "utf-8" if flags & 0x800 else "cp437"
            try:
                local_name = name_raw.decode(encoding)
            except UnicodeError as exc:
                raise AuditError("Invalid ZIP local name encoding") from exc
            if local_name != info.filename or method != info.compress_type or flags != info.flag_bits:
                raise AuditError("ZIP local and central headers disagree")
            data_offset = info.header_offset + LOCAL_HEADER.size + name_len + extra_len
            if data_offset + info.compress_size > archive.start_dir:
                raise AuditError("Compressed ZIP data extends into the central directory")
            if flags & 1:
                raise AuditError("Encrypted ZIP entries are outside this audit")
            if not (flags & 8):
                if crc != info.CRC:
                    raise AuditError("ZIP local and central CRC fields disagree")
                if compressed32 != 0xFFFFFFFF and compressed32 != info.compress_size:
                    raise AuditError("ZIP local and central compressed sizes disagree")
                if uncompressed32 != 0xFFFFFFFF and uncompressed32 != info.file_size:
                    raise AuditError("ZIP local and central uncompressed sizes disagree")
            local_fields = extra_fields(local_extra)
            central_fields = extra_fields(info.extra)
            local_zip64 = [len(payload) for kind, payload in local_fields if kind == 1]
            central_zip64 = [len(payload) for kind, payload in central_fields if kind == 1]
            # The reference Android parser needs both size sentinels in a ZIP64 local header.
            if (compressed32 == 0xFFFFFFFF) != (uncompressed32 == 0xFFFFFFFF):
                raise AuditError("ZIP64 local size sentinels do not occur together")
            if compressed32 == uncompressed32 == 0xFFFFFFFF:
                payloads = [payload for kind, payload in local_fields if kind == 1]
                if len(payloads) != 1 or len(payloads[0]) < 16:
                    raise AuditError("ZIP64 local size payload is missing or too short")
                expanded, compressed = struct.unpack_from("<QQ", payloads[0])
                if not (flags & 8) and (expanded, compressed) != (info.file_size, info.compress_size):
                    raise AuditError("ZIP64 local and central sizes disagree")
            rows.append({
                "name": info.filename,
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
                "method": info.compress_type,
                "flags": info.flag_bits,
                "zip_version_needed": info.extract_version,
                "local_header_offset": info.header_offset,
                "data_offset": data_offset,
                "local_compressed_size_32": compressed32,
                "local_uncompressed_size_32": uncompressed32,
                "local_zip64_payload_bytes": local_zip64,
                "central_zip64_payload_bytes": central_zip64,
            })
        small = {}
        for name in (SCRIPT, BINARY, METADATA, METADATA_PB):
            info = archive.getinfo(name)
            if info.file_size > MAX_SMALL_MEMBER:
                raise AuditError("A small audit member exceeds the size cap")
            data = archive.read(info)  # Reads to EOF; zipfile verifies the CRC.
            if len(data) != info.file_size:
                raise AuditError("Short read of an audit member")
            small[name] = data
        return {"entries": rows, "entry_count": len(rows), "zip_comment_bytes": len(archive.comment),
                "central_directory_offset": archive.start_dir}, small


def standalone_writes(script: str) -> list[dict]:
    """Recognize only complete, stand-alone extract statements, not general edify."""
    line_pattern = re.compile(
        r'^\s*package_extract_file\(\s*"([^"\\]+)"\s*,\s*"([^"\\]+)"\s*\)\s*;\s*$'
    )
    result = []
    for number, line in enumerate(script.splitlines(), 1):
        match = line_pattern.fullmatch(line)
        if match:
            result.append({"line": number, "member": match.group(1),
                           "destination": match.group(2), "standalone_unchecked_result": True})
    return result


def metadata_offsets(metadata: str, rows: list[dict]) -> list[dict]:
    entries = {item["name"].rsplit("/", 1)[-1]: item for item in rows}
    value = next((line.split("=", 1)[1].strip() for line in metadata.splitlines()
                  if line.startswith("ota-property-files=")), "")
    result = []
    for item in value.split(",") if value else []:
        pieces = item.split(":")
        if len(pieces) != 3 or not pieces[1].isdigit() or not pieces[2].isdigit():
            raise AuditError("Unrecognized ota-property-files item")
        name, start, length = pieces[0], int(pieces[1]), int(pieces[2])
        row = entries.get(name)
        if row is None:
            raise AuditError("Metadata references a missing ZIP member")
        result.append({"name": name, "claimed_offset": start, "claimed_length": length,
                       "actual_data_offset": row["data_offset"],
                       "member_uncompressed_bytes": row["uncompressed_bytes"],
                       "compression_method": row["method"],
                       "offset_matches": start == row["data_offset"]})
    return result


def _bounded(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise AuditError("ELF data is out of bounds")
    return data[offset:offset + size]


def _elf_header(data: bytes) -> tuple:
    if len(data) < 64:
        raise AuditError("ELF header is too short")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    ident = header[0]
    if ident[:6] != b"\x7fELF\x02\x01" or header[2] != 183:
        raise AuditError("Updater is not an AArch64 little-endian ELF64")
    return header


def elf_sections(data: bytes) -> list[dict]:
    header = _elf_header(data)
    table, size, count, str_index = header[6], header[11], header[12], header[13]
    if size != 64 or not 0 < count <= 4096 or str_index >= count:
        raise AuditError("Unsupported ELF section table")
    _bounded(data, table, size * count)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, table + i * size) for i in range(count)]
    string_section = sections[str_index]
    name_bytes = _bounded(data, string_section[4], string_section[5])
    result = []
    for section in sections:
        name_start = section[0]
        if name_start >= len(name_bytes):
            raise AuditError("Invalid ELF section name")
        name_end = name_bytes.find(b"\0", name_start)
        if name_end < 0:
            raise AuditError("Unterminated ELF section name")
        name = name_bytes[name_start:name_end].decode("ascii", errors="replace")
        # SHT_NOBITS sections occupy no file bytes.
        payload = b"" if section[1] == 8 else _bounded(data, section[4], section[5])
        result.append({"name": name, "type": section[1], "link": section[6],
                       "entry_size": section[9], "payload": payload})
    return result


def mini_symbols(updater: bytes) -> list[dict]:
    sections = elf_sections(updater)
    debug = next((item["payload"] for item in sections if item["name"] == ".gnu_debugdata"), None)
    if debug is None:
        raise AuditError("Updater has no embedded mini-debug information")
    try:
        dec = lzma.LZMADecompressor(memlimit=64 * 1024 * 1024)
        decoded = dec.decompress(debug, max_length=MAX_DEBUG + 1)
        if not dec.eof or dec.unused_data or len(decoded) > MAX_DEBUG:
            raise AuditError("Mini-debug data is too large or incomplete")
    except lzma.LZMAError as exc:
        raise AuditError("Mini-debug data could not be decoded") from exc
    sections = elf_sections(decoded)
    result = []
    for section in sections:
        if section["type"] != 2:  # SHT_SYMTAB
            continue
        if section["entry_size"] != 24 or section["link"] >= len(sections):
            raise AuditError("Unsupported ELF symbol table")
        names = sections[section["link"]]["payload"]
        table = section["payload"]
        if len(table) % 24 or len(table) // 24 > 200_000:
            raise AuditError("Invalid ELF symbol table size")
        for pos in range(0, len(table), 24):
            name_offset, info, _other, _section, address, length = struct.unpack_from("<IBBHQQ", table, pos)
            if (info & 15) != 2 or not length:  # STT_FUNC
                continue
            if name_offset >= len(names):
                raise AuditError("Invalid ELF symbol name")
            end = names.find(b"\0", name_offset)
            if end < 0:
                raise AuditError("Unterminated ELF symbol name")
            result.append({"name": names[name_offset:end].decode("ascii", errors="replace"),
                           "address": address, "bytes": length})
    return result


def load_segments(data: bytes) -> list[tuple[int, int, int, int]]:
    header = _elf_header(data)
    table, size, count = header[5], header[9], header[10]
    if size != 56 or count > 1024:
        raise AuditError("Unsupported ELF program table")
    _bounded(data, table, size * count)
    segments = []
    for i in range(count):
        kind, flags, offset, address, _paddr, filesz, _memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, table + i * size)
        if kind == 1:  # PT_LOAD
            _bounded(data, offset, filesz)
            segments.append((address, address + filesz, offset, flags))
    return segments


def code_bytes(data: bytes, address: int, size: int) -> bytes:
    for begin, end, offset, flags in load_segments(data):
        if flags & 1 and begin <= address and size <= end - address:
            return _bounded(data, offset + address - begin, size)
    raise AuditError("ELF function is not in an executable load segment")


def direct_bl_target(word: int, pc: int) -> int | None:
    if word & 0xFC000000 != 0x94000000:  # AArch64 BL imm26
        return None
    imm = word & 0x03FFFFFF
    if imm & 0x02000000:
        imm -= 0x04000000
    return pc + (imm << 2)


def direct_calls(updater: bytes, function: dict, addresses: set[int]) -> list[dict]:
    start, length = function["address"], function["bytes"]
    if start % 4 or length % 4 or length > 1024 * 1024:
        raise AuditError("Unsupported AArch64 function bounds")
    body = code_bytes(updater, start, length)
    calls = []
    for offset in range(0, length, 4):
        word = struct.unpack_from("<I", body, offset)[0]
        target = direct_bl_target(word, start + offset)
        if target in addresses:
            calls.append({"call_address": start + offset, "target_address": target})
    return calls


def sequence_null_check(updater: bytes, function: dict) -> dict:
    """Find the narrow BLR / CBZ X0 / subsequent BLR pattern in SequenceFn.

    This is a static control-flow observation, not a complete disassembly or
    execution trace. The updater bytes are pinned separately by SHA-256.
    """
    start, size = function["address"], function["bytes"]
    body = code_bytes(updater, start, size)
    words = [struct.unpack_from("<I", body, pos)[0] for pos in range(0, len(body) - 3, 4)]
    for index in range(len(words) - 2):
        if words[index] & 0xFFFFFC1F != 0xD63F0000:  # BLR register
            continue
        cbz = words[index + 1]
        if cbz & 0xFF00001F != 0xB4000000:  # CBZ X0, signed imm19
            continue
        offset = (cbz >> 5) & 0x7FFFF
        if offset & 0x40000:
            offset -= 0x80000
        check_address = start + 4 * (index + 1)
        target = check_address + 4 * offset
        if not check_address < target < start + size:
            continue
        for later in range(index + 2, min((target - start) // 4, len(words))):
            if words[later] & 0xFFFFFC1F == 0xD63F0000:
                return {"first_indirect_call": start + 4 * index, "null_check": check_address,
                        "null_branch_target": target, "next_indirect_call": start + 4 * later,
                        "non_null_path_reaches_next_call": True}
    raise AuditError("Expected edify sequence null-check shape was not found")


def inspect_updater(updater: bytes) -> dict:
    symbols = mini_symbols(updater)
    packages = [s for s in symbols if "PackageExtractFileFn" in s["name"]]
    finds = [s for s in symbols if "FindEntry" in s["name"] and "ZipEntry64" in s["name"]]
    writers = [s for s in symbols if "extractToWriter" in s["name"] and "ZipEntry64" in s["name"]]
    sequences = [s for s in symbols if "SequenceFn" in s["name"]]
    if len(packages) != 1 or not finds or not writers or len(sequences) != 1:
        raise AuditError("Required updater mini-debug function symbols were not found")
    find_calls = direct_calls(updater, packages[0], {s["address"] for s in finds})
    write_calls = direct_calls(updater, packages[0], {s["address"] for s in writers})
    if not find_calls or not write_calls:
        raise AuditError("Expected ZIP64-related direct calls were not found")
    return {
        "format": "ELF64 little-endian AArch64",
        "sha256": digest(updater),
        "package_extract_file_symbol": packages[0],
        "zip_entry_64_find_symbols": finds,
        "zip_entry_64_writer_symbols": writers,
        "direct_calls_to_find_entry64": find_calls,
        "direct_calls_to_writer64": write_calls,
        "edify_sequence_symbol": sequences[0],
        "edify_sequence_null_check_shape": sequence_null_check(updater, sequences[0]),
        "zip64_error_strings_present": b"Zip64 eocd record signature not found" in updater,
        "limitations": [
            "Static call and symbol evidence only; the updater was not executed.",
            "This is not the recovery ZIP parser and does not establish installation or boot success.",
        ],
    }


def audit(source: Path, candidate: Path) -> dict:
    source_id = identity(source, SOURCE_BYTES, SOURCE_SHA256)
    candidate_id = identity(candidate, CANDIDATE_BYTES, CANDIDATE_SHA256)
    source_layout, source_small = archive_info(source)
    candidate_layout, candidate_small = archive_info(candidate)
    expected = {SCRIPT: SCRIPT_SHA256, BINARY: BINARY_SHA256, METADATA: METADATA_SHA256}
    for name, sha in expected.items():
        if digest(source_small[name]) != sha or digest(candidate_small[name]) != sha:
            raise AuditError("A pinned installer/metadata member did not match")
    if source_small[METADATA_PB] != candidate_small[METADATA_PB]:
        raise AuditError("Binary metadata differs between the two ZIPs")
    try:
        script = candidate_small[SCRIPT].decode("utf-8")
        meta_source = source_small[METADATA].decode("utf-8")
        meta_candidate = candidate_small[METADATA].decode("utf-8")
    except UnicodeError as exc:
        raise AuditError("Installer or metadata text is not UTF-8") from exc
    writes = standalone_writes(script)
    expected_writes = [
        ("super.img", "/dev/block/bootdevice/by-name/super"),
        ("boot.img", "/dev/block/bootdevice/by-name/boot"),
        ("dtbo.img", "/dev/block/bootdevice/by-name/dtbo"),
    ]
    if [(w["member"], w["destination"]) for w in writes] != expected_writes:
        raise AuditError("Standalone installer writes did not match the pinned script")
    metadata_fields = dict(line.split("=", 1) for line in meta_candidate.splitlines() if "=" in line)
    return {
        "schema": "synthetica-boot-first-read-only-installer-audit-v1",
        "status": "host_static_evidence_only_not_a_flash_or_boot_approval",
        "source": {"identity": source_id, "layout": source_layout,
                   "metadata_offsets": metadata_offsets(meta_source, source_layout["entries"])},
        "candidate": {"identity": candidate_id, "layout": candidate_layout,
                      "metadata_offsets": metadata_offsets(meta_candidate, candidate_layout["entries"])},
        "same_pinned_installer_and_metadata": {name: sha for name, sha in expected.items()},
        "standalone_partition_writes": writes,
        "metadata_post_security_patch_level": metadata_fields.get("post-security-patch-level"),
        "updater_static_analysis": inspect_updater(candidate_small[BINARY]),
        "limitations": [
            "No installer, recovery, ROM or device was executed or modified.",
            "Host ZIP readability and ARM64 symbols do not prove recovery compatibility, signature acceptance, AVB or boot.",
            "Standalone write statements are a review warning, not proof that a write will fail.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("report already exists; refusing to overwrite it")
    try:
        result = audit(args.source, args.candidate)
        # Exclusive creation avoids replacing an existing user file.
        with args.report.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
            out.write("\n")
    except (AuditError, OSError, zipfile.BadZipFile) as exc:
        print(f"Audit stopped: {exc}", file=sys.stderr)
        return 1
    print("Host-only read-only installer audit completed; no device or installer was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
