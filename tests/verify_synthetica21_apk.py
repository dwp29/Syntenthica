#!/usr/bin/env python3
"""Static compatibility gates for an unsigned or signed Synthetica 2.1 APK.

This verifies bytes and metadata only; it is not an Android device/root test.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "release/Synthetica-2.0.apk"
SYMBOL = b"Java_com_rifsxd_ksunext_Natives_getManagerUAPIVersion"


def elf_sections(blob: bytes):
    if blob[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected a little-endian ELF64")
    shoff = struct.unpack_from("<Q", blob, 40)[0]
    entsize, count, names_index = struct.unpack_from("<HHH", blob, 58)
    headers = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + i * entsize) for i in range(count)]
    name_header = headers[names_index]
    names = blob[name_header[4]:name_header[4] + name_header[5]]
    def cstring(table: bytes, offset: int) -> bytes:
        return table[offset:table.find(b"\0", offset)]
    return headers, {cstring(names, h[0]): h for h in headers}, cstring


def get_symbol_code(blob: bytes, symbol: bytes) -> bytes:
    headers, sections, cstring = elf_sections(blob)
    dynsym = sections[b".dynsym"]
    strings = headers[dynsym[6]]
    strtab = blob[strings[4]:strings[4] + strings[5]]
    value = size = None
    for pos in range(dynsym[4], dynsym[4] + dynsym[5], dynsym[9]):
        name, info, other, shndx, addr, length = struct.unpack_from("<IBBHQQ", blob, pos)
        if cstring(strtab, name) == symbol:
            value, size = addr, length
            break
    if value is None or size != 8:
        raise ValueError("Expected eight-byte exported JNI UAPI accessor")
    phoff = struct.unpack_from("<Q", blob, 32)[0]
    entsize, count = struct.unpack_from("<HH", blob, 54)
    for i in range(count):
        typ, flags, file_offset, vaddr, _paddr, file_size, _memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", blob, phoff + i * entsize
        )
        if typ == 1 and vaddr <= value and value + size <= vaddr + file_size:
            start = file_offset + value - vaddr
            return blob[start:start + size]
    raise ValueError("JNI symbol not mapped by a load segment")


def normalized_native(blob: bytes) -> bytes:
    _, sections, _ = elf_sections(blob)
    build_id = sections[b".note.gnu.build-id"]
    data = bytearray(blob)
    data[build_id[4]:build_id[4] + build_id[5]] = b"\0" * build_id[5]
    return bytes(data)


def main(apk: Path) -> None:
    with zipfile.ZipFile(apk) as candidate, zipfile.ZipFile(REFERENCE) as previous:
        if candidate.testzip() is not None:
            raise ValueError("APK ZIP integrity check failed")
        libname = "lib/arm64-v8a/libkernelsu.so"
        daemon_name = "lib/arm64-v8a/libksud.so"
        native = candidate.read(libname)
        old_native = previous.read(libname)
        if get_symbol_code(native, SYMBOL) != bytes.fromhex("80008052c0035fd6"):
            raise ValueError("Manager JNI accessor does not return UAPI 4")
        if normalized_native(native) != normalized_native(old_native):
            raise ValueError("Manager JNI differs from the 2.0 reference beyond its ELF build ID")
        daemon = candidate.read(daemon_name)
        if daemon != previous.read(daemon_name):
            raise ValueError("Manager daemon differs from the working 2.0 reference")
        assets = ROOT / "build-kit/ci/ksun-cyberbrutal/assets"
        for name in ("synthetica-control.sh", "synthetica-boost-compat.sh"):
            if candidate.read("assets/" + name) != (assets / name).read_bytes():
                raise ValueError(f"APK asset {name} does not match the tested source")
        print("APK ZIP CRC: OK")
        print("JNI accessor: UAPI 4; code matches 2.0 except ELF build ID")
        print("libksud.so:", hashlib.sha256(daemon).hexdigest(), "matches 2.0")
        print("Bundled runtime helpers match tested source")
        print("Runtime/device behavior: NOT TESTED")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} APK")
    main(Path(sys.argv[1]))
