#!/usr/bin/env python3
"""Prepare and check a *non-flashable* Linux 6.18 Synthetica experiment.

Inputs must be obtained from the exact archives in inputs.json. The checkout is
never modified: a new disposable work directory is created from those inputs.
SUSFS is deliberately NOT claimed or included until its 6.18/UAPI port exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "build-kit/ci/synthetica40"
PINS = json.loads((ASSETS / "inputs.json").read_text())
CERT_HASH = PINS["manager_identity"]["certificate_sha256"]
CERT_SIZE = PINS["manager_identity"]["certificate_der_bytes"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_archive(name: str, path: Path) -> None:
    expected = PINS[name]["archive_sha256"]
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{name} archive SHA-256 mismatch: {actual} != {expected}")


def verify_source(name: str, path: Path) -> None:
    if not path.is_dir():
        raise ValueError(f"{name} source directory not found: {path}")
    for relative, expected in PINS[name]["sentinels"].items():
        file = path / relative
        if not file.is_file() or file.is_symlink() or sha256(file) != expected:
            raise ValueError(f"{name} source sentinel mismatch: {relative}")


def replace_once(path: Path, before: str, after: str) -> None:
    original = path.read_text()
    count = original.count(before)
    if count != 1:
        raise ValueError(f"{path}: expected one exact anchor, found {count}")
    path.write_text(original.replace(before, after, 1))


def append_once(path: Path, text: str) -> None:
    original = path.read_text()
    if text.strip() in original:
        raise ValueError(f"{path}: integration is already present")
    path.write_text(original.rstrip() + "\n\n" + text.rstrip() + "\n")


def protocol_enum(header: str) -> list[str]:
    match = re.search(r"enum\s*\{\s*(NM_CMD_UNSPEC\s*=\s*0\s*,.*?)\};", header, re.S)
    if not match:
        raise ValueError("NoMount command enum is missing")
    return [re.sub(r"\s+", "", entry) for entry in match.group(1).split(",") if entry.strip()]


def protocol_struct(header: str, name: str) -> list[str]:
    match = re.search(r"struct\s+" + re.escape(name) + r"\s*\{(.*?)\}\s*__attribute__\s*\(\(packed\)\)", header, re.S)
    if not match:
        raise ValueError(f"NoMount packed structure {name} is missing")
    fields = re.sub(r"/\*.*?\*/|//[^\n]*", "", match.group(1), flags=re.S)
    fields = re.sub(r"\bunsigned\s+long\s+long\b|\bu64\b", "uint64", fields)
    fields = re.sub(r"\bunsigned\s+int\b|\bu32\b", "uint32", fields)
    fields = re.sub(r"\bunsigned\s+short\b|\bu16\b", "uint16", fields)
    return [re.sub(r"\s+", "", field) for field in fields.split(";") if field.strip()]


def check_nomount_protocol(nomount: Path) -> None:
    kernel = (nomount / "kernel/src/nomount.h").read_text()
    user = (nomount / "userspace/src/nm.h").read_text()
    if '#define NOMOUNT_BASE_VERSION "22"' not in kernel:
        raise ValueError("NoMount kernel is not protocol 22")
    if protocol_enum(kernel) != protocol_enum(user):
        raise ValueError("NoMount kernel/userspace command numbers differ")
    for name in ("nm_payload", "nm_rule_hdr", "nm_del_hdr"):
        if protocol_struct(kernel, name) != protocol_struct(user, name):
            raise ValueError(f"NoMount kernel/userspace {name} differs")
    for header in (kernel, user):
        if "0x4E4F4D4F554E54ULL" not in header:
            raise ValueError("NoMount protocol magic differs")
    if 'sizeof(struct nm_payload) == 4096' not in user:
        raise ValueError("NoMount userspace lost its payload-size assertion")


def check_work_directory(work: Path, source_paths: list[Path]) -> None:
    resolved = work.resolve()
    protected = [ROOT.resolve(), Path.home().resolve(), *(p.resolve() for p in source_paths)]
    # Disallow a workspace inside this checkout, inside any input, or an ancestor
    # of one. Never remove/reuse existing directories, even if they look empty.
    if any(resolved == p or resolved in p.parents or p in resolved.parents for p in protected):
        raise ValueError(f"Refusing unsafe work directory: {work}")
    if work.exists() or work.is_symlink():
        raise ValueError(f"Work directory already exists: {work}")


def prepare(kernel: Path, ksun: Path, nomount: Path, work: Path) -> Path:
    for name, source in (("kernel", kernel), ("ksun", ksun), ("nomount", nomount)):
        verify_source(name, source)
    check_nomount_protocol(nomount)
    check_work_directory(work, [kernel, ksun, nomount])
    work.mkdir(parents=True)
    dst = work / "kernel"
    shutil.copytree(kernel, dst, symlinks=True)

    driver = dst / "drivers/kernelsu"
    if driver.exists() or driver.is_symlink():
        raise ValueError("kernel already contains drivers/kernelsu")
    shutil.copytree(ksun / "kernel", driver, symlinks=True)
    # Upstream's include/uapi is a symlink into its original repository. Make
    # this disposable integrated tree self-contained without following it.
    uapi_link = driver / "include/uapi"
    if not uapi_link.is_symlink() or uapi_link.readlink().as_posix() != "../../uapi":
        raise ValueError("unexpected KernelSU UAPI layout")
    uapi_link.unlink()
    shutil.copytree(ksun / "uapi", uapi_link)

    kbuild = driver / "Kbuild"
    replace_once(kbuild, "KSU_VERSION_FALLBACK := 1\n", "KSU_VERSION_FALLBACK := 33355\n")
    replace_once(kbuild, "KSU_VERSION_TAG_FALLBACK := v0.0.1\n", "KSU_VERSION_TAG_FALLBACK := v3.4.2\n")
    replace_once(kbuild, "KSU_NEXT_MANAGER_SIZE := 0x3e6\n", f"KSU_NEXT_MANAGER_SIZE := 0x{CERT_SIZE:x}\n")
    replace_once(kbuild, "KSU_NEXT_MANAGER_HASH := 79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7\n", f"KSU_NEXT_MANAGER_HASH := {CERT_HASH}\n")
    replace_once(kbuild, "ifdef KSU_MANAGER_PACKAGE\n", "KSU_MANAGER_PACKAGE ?= net.ember.labs\n\nifdef KSU_MANAGER_PACKAGE\n")

    # The Synthetica public certificate is 1381 bytes, above upstream's 1024
    # byte ceiling. Keep a bounded allocation and exact digest check, rather
    # than disabling signature checks or consuming 2 KiB of kernel stack.
    signer = driver / "manager/apk_sign.c"
    replace_once(signer, "#define CERT_MAX_LENGTH 1024\n", "#define CERT_MAX_LENGTH 2048\n")
    replace_once(signer,
        "\tchar cert[CERT_MAX_LENGTH];\n"
        "\tif (!read_exact(fp, cert, certificate_size, pos, certificates_end))\n"
        "\t\treturn false;\n\n"
        "\tunsigned char digest[SHA256_DIGEST_SIZE];\n"
        "\tif (ksu_sha256(cert, certificate_size, digest)) {\n",
        "\tunsigned char digest[SHA256_DIGEST_SIZE];\n"
        "\tchar *cert = kmalloc(certificate_size, GFP_KERNEL);\n"
        "\tint digest_result;\n"
        "\tif (!cert)\n"
        "\t\treturn false;\n"
        "\tif (!read_exact(fp, cert, certificate_size, pos, certificates_end)) {\n"
        "\t\tkfree(cert);\n"
        "\t\treturn false;\n"
        "\t}\n"
        "\tdigest_result = ksu_sha256(cert, certificate_size, digest);\n"
        "\tkfree(cert);\n"
        "\tif (digest_result) {\n")
    append_once(dst / "drivers/Makefile", "obj-$(CONFIG_KSU) += kernelsu/")
    append_once(dst / "drivers/Kconfig", 'source "drivers/kernelsu/Kconfig"')

    nm_driver = dst / "fs/nomount"
    if nm_driver.exists() or nm_driver.is_symlink():
        raise ValueError("kernel already contains fs/nomount")
    shutil.copytree(nomount / "kernel/src", nm_driver)
    # Do not weaken stack-protector settings for this added code.
    replace_once(nm_driver / "Makefile", " -fno-stack-protector\n", "\n")
    append_once(dst / "fs/Makefile", "obj-$(CONFIG_NOMOUNT) += nomount/")
    append_once(dst / "fs/Kconfig", 'source "fs/nomount/Kconfig"')
    (work / "INPUTS.json").write_text(json.dumps(PINS, indent=2) + "\n")
    return dst


def parse_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        if raw.startswith("CONFIG_") and "=" in raw:
            key, value = raw.split("=", 1)
            values[key] = value
        elif raw.startswith("# CONFIG_") and raw.endswith(" is not set"):
            values[raw[2:-11]] = "n"
    return values


def check_config(actual_path: Path, fragments: list[Path]) -> None:
    requested: dict[str, str] = {}
    for fragment in fragments:
        requested.update(parse_config(fragment))
    actual = parse_config(actual_path)
    missing = [f"{key}: wanted {value}, got {actual.get(key, 'n')}"
               for key, value in requested.items() if actual.get(key, "n") != value]
    if missing:
        raise ValueError("Unresolved configuration:\n" + "\n".join(missing))
    print(f"Verified {len(requested)} effective fragment requests")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    archives = sub.add_parser("verify-archives")
    for name in ("kernel", "ksun", "nomount"):
        archives.add_argument(f"--{name}", type=Path, required=True)
    prep = sub.add_parser("prepare")
    for name in ("kernel", "ksun", "nomount", "work"):
        prep.add_argument(f"--{name}", type=Path, required=True)
    config = sub.add_parser("check-config")
    config.add_argument("actual", type=Path)
    config.add_argument("fragments", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "verify-archives":
        for name in ("kernel", "ksun", "nomount"):
            verify_archive(name, getattr(args, name))
            print(f"{name} archive: SHA-256 OK")
    elif args.command == "prepare":
        print(f"Prepared experimental source: {prepare(args.kernel, args.ksun, args.nomount, args.work)}")
    else:
        check_config(args.actual, args.fragments)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
