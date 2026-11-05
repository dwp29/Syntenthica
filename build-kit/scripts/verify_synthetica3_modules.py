#!/usr/bin/env python3
"""Verify the six modules selected by the Synthetica 2.0 configuration.

These must be built and signed alongside the 3.0 kernel. Verification is static;
it does not load a module or establish compatibility with the ROM/device.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path

MODULE_CONFIG = {
    "tcp_bic": "TCP_CONG_BIC",
    "tcp_westwood": "TCP_CONG_WESTWOOD",
    "tcp_htcp": "TCP_CONG_HTCP",
    "gspca_main": "USB_GSPCA",
    "rmnet_perf": "RMNET_PERF",
    "rmnet_shs": "RMNET_SHS",
}
SIG_MAGIC = b"~Module signature appended~\n"
MAX_MODULE = 32 * 1024 * 1024


def split_signature(data: bytes) -> tuple[bytes, bytes]:
    if len(data) > MAX_MODULE or not data.endswith(SIG_MAGIC):
        raise ValueError("module signature is absent or module is oversized")
    end = len(data) - len(SIG_MAGIC)
    if end < 12:
        raise ValueError("truncated module signature descriptor")
    desc = struct.unpack_from(">8BI", data, end - 12)
    if desc[:8] != (0, 0, 2, 0, 0, 0, 0, 0):
        raise ValueError("unsupported module signature descriptor")
    start = end - 12 - desc[8]
    if desc[8] < 128 or start <= 0:
        raise ValueError("invalid signature length")
    return data[:start], data[start:end - 12]


def elf_sections(payload: bytes) -> dict[str, bytes]:
    if len(payload) < 64:
        raise ValueError("truncated ELF module")
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", payload, 0)
    ident, kind, machine, version = h[:4]
    shoff, ehsize, shentsize, shnum, shstrndx = h[6], h[8], h[11], h[12], h[13]
    if (ident[:7] != b"\x7fELF\x02\x01\x01" or kind != 1 or machine != 183 or version != 1
            or ehsize != 64 or shentsize != 64 or not 0 < shnum <= 4096 or shstrndx >= shnum
            or shoff < 64 or shoff + shentsize * shnum > len(payload)):
        raise ValueError("expected bounded AArch64 little-endian ELF64 ET_REL")
    rows = [struct.unpack_from("<IIQQQQIIQQ", payload, shoff + 64 * i) for i in range(shnum)]
    names_row = rows[shstrndx]
    if names_row[4] + names_row[5] > len(payload) or names_row[1] != 3:
        raise ValueError("invalid ELF section names")
    names = payload[names_row[4]:names_row[4] + names_row[5]]
    sections: dict[str, bytes] = {}
    for row in rows:
        name_offset, section_type, _, _, offset, size, _, _, _, _ = row
        if name_offset >= len(names):
            raise ValueError("invalid ELF section name offset")
        end = names.find(b"\0", name_offset)
        if end < 0:
            raise ValueError("unterminated ELF section name")
        try:
            name = names[name_offset:end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII ELF section name") from exc
        if section_type != 8 and offset + size > len(payload):
            raise ValueError("ELF section exceeds payload")
        if name in (".modinfo", "__versions"):
            if name in sections:
                raise ValueError("duplicate required module section")
            if section_type != 1:  # SHT_PROGBITS
                raise ValueError("invalid required module section type")
            sections[name] = payload[offset:offset + size]
    if set(sections) != {".modinfo", "__versions"}:
        raise ValueError("missing module info or MODVERSIONS")
    return sections


def module_info(section: bytes) -> dict[str, str]:
    if not section or not section.endswith(b"\0"):
        raise ValueError("invalid .modinfo")
    entries: dict[str, str] = {}
    for row in section.split(b"\0"):
        # Descriptive fields such as author may legitimately contain non-ASCII
        # bytes. The signed payload still covers them; only the identity and
        # dependency fields used for compatibility must decode as ASCII.
        key, sep, raw_value = row.partition(b"=")
        if sep and key in (b"name", b"vermagic", b"depends"):
            name = key.decode("ascii")
            try:
                value = raw_value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError(f"non-ASCII required .modinfo field: {name}") from exc
            if name in entries:
                raise ValueError(f"duplicate .modinfo field: {name}")
            entries[name] = value
    if not entries.get("name") or not entries.get("vermagic"):
        raise ValueError("missing module name or vermagic")
    return entries


def version_records(data: bytes) -> dict[str, int]:
    # The 4.14 arm64 modversion_info layout is u64 CRC + 56-byte symbol name.
    if not data or len(data) % 64 or len(data) > 1024 * 1024:
        raise ValueError("invalid MODVERSIONS record size")
    records: dict[str, int] = {}
    for offset in range(0, len(data), 64):
        crc = struct.unpack_from("<Q", data, offset)[0]
        name, sep, padding = data[offset + 8:offset + 64].partition(b"\0")
        if not sep or not name or any(padding) or crc > 0xffffffff:
            raise ValueError("invalid MODVERSIONS record")
        try:
            symbol = name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII MODVERSIONS symbol") from exc
        if symbol in records:
            raise ValueError(f"duplicate MODVERSIONS symbol: {symbol}")
        records[symbol] = crc
    if "module_layout" not in records:
        raise ValueError("module_layout version missing")
    return records


def symvers_records(text: str) -> dict[str, int]:
    records: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3 or not re.fullmatch(r"0x[0-9a-fA-F]{1,8}", fields[0]):
            raise ValueError("invalid Module.symvers record")
        crc, name = int(fields[0], 16), fields[1]
        if name in records and records[name] != crc:
            raise ValueError(f"conflicting CRCs for {name}")
        records[name] = crc
    if not records.get("module_layout"):
        raise ValueError("kernel module_layout CRC missing or zero")
    return records


def verify_pkcs7(payload: bytes, signature: bytes, certificate_der: bytes) -> None:
    """Require a valid signature using exactly the certificate embedded in this kernel.

    OpenSSL is given that certificate as the sole trust anchor and is forbidden
    to use certificates embedded in the PKCS#7. Nothing is changed on-device.
    """
    with tempfile.TemporaryDirectory(prefix="synthetica3-signature-") as tmp:
        root = Path(tmp)
        (root / "module").write_bytes(payload)
        (root / "signature.der").write_bytes(signature)
        (root / "cert.der").write_bytes(certificate_der)
        cert = root / "cert.pem"
        commands = (
            ["openssl", "x509", "-inform", "DER", "-in", str(root / "cert.der"), "-out", str(cert)],
            ["openssl", "cms", "-verify", "-binary", "-inform", "DER", "-in", str(root / "signature.der"),
             "-content", str(root / "module"), "-certfile", str(cert), "-CAfile", str(cert),
             "-nointern", "-purpose", "any", "-partial_chain", "-out", os.devnull],
        )
        for command in commands:
            completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if completed.returncode:
                raise ValueError("module signature did not verify with the kernel certificate")


def verify_module(data: bytes, *, name: str, release: str, certificate_der: bytes,
                  raw_kernel: bytes, symvers: dict[str, int]) -> dict[str, object]:
    if name not in MODULE_CONFIG:
        raise ValueError(f"unexpected module name: {name}")
    if not certificate_der or raw_kernel.count(certificate_der) != 1:
        raise ValueError("kernel does not contain exactly one matching module certificate")
    payload, signature = split_signature(data)
    sections = elf_sections(payload)
    info = module_info(sections[".modinfo"])
    # These flags follow the guarded, immutable 2.0 config and arm64 target.
    expected_vermagic = release + " SMP preempt mod_unload modversions aarch64"
    if info["name"] != name or info["vermagic"] != expected_vermagic:
        raise ValueError(f"module name or vermagic differs: {name}")
    deps = [dep for dep in info.get("depends", "").split(",") if dep]
    if any(dep not in MODULE_CONFIG for dep in deps):
        raise ValueError(f"module has an unbundled loadable dependency: {name}")
    versions = version_records(sections["__versions"])
    for symbol, crc in versions.items():
        if symvers.get(symbol) != crc:
            raise ValueError(f"MODVERSIONS mismatch or missing export: {name}/{symbol}")
    verify_pkcs7(payload, signature, certificate_der)
    return {
        "name": name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "vermagic": info["vermagic"],
        "dependencies": deps,
        "module_layout_crc": f"0x{versions['module_layout']:08x}",
        "version_records_verified": len(versions),
        "signature_verified_with_embedded_certificate": True,
    }


def collect(stage: Path, *, config: dict[str, str], release: str, certificate_der: bytes,
            raw_kernel: bytes, symvers_text: str) -> dict[str, tuple[bytes, dict[str, object]]]:
    """Return exactly the configured modules after all signature/ABI checks pass."""
    configured = {symbol for symbol, value in config.items() if value == "m"}
    if configured != set(MODULE_CONFIG.values()):
        raise ValueError("2.0 module config set is not preserved")
    if not stage.is_dir() or stage.is_symlink():
        raise ValueError("missing or unsafe modules staging directory")
    paths: dict[str, Path] = {}
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in modules staging directory")
        if path.is_file() and path.suffix == ".ko":
            if path.stem in paths:
                raise ValueError(f"duplicate module: {path.stem}")
            paths[path.stem] = path
    if set(paths) != set(MODULE_CONFIG):
        raise ValueError("missing or unexpected module set in staging directory")
    symvers = symvers_records(symvers_text)
    modules: dict[str, tuple[bytes, dict[str, object]]] = {}
    errors: list[str] = []
    for name in MODULE_CONFIG:
        path = paths[name]
        if path.stat().st_size > MAX_MODULE:
            errors.append(f"{name}: module too large")
            continue
        data = path.read_bytes()
        try:
            checked = verify_module(data, name=name, release=release, certificate_der=certificate_der,
                                    raw_kernel=raw_kernel, symvers=symvers)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue
        modules[name] = (data, checked)
    if errors:
        raise ValueError("module verification failed: " + "; ".join(errors))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValueError("cyclic module dependencies")
        if name in visited:
            return
        visiting.add(name)
        for dependency in modules[name][1]["dependencies"]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in modules:
        visit(name)
    return modules
