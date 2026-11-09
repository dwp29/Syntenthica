#!/usr/bin/env python3
"""Collect strictly whitelisted build evidence, never a flashable package."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import build_synthetica40 as s40

RELEASE = "6.18.58-synthetica-4.0-dev0"
MAGIC = b"~Module signature appended~\n"


def sha(path: Path) -> str:
    return s40.sha256(path)


def check_arm64_elf(path: Path) -> None:
    with path.open("rb") as f:
        header = f.read(20)
    if len(header) < 20 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 183:
        raise ValueError(f"Not a little-endian AArch64 ELF: {path}")


def collect(out: Path, modules: Path, nm: Path, destination: Path, provenance: dict[str, str]) -> dict:
    if destination.exists() or destination.is_symlink():
        raise ValueError("Evidence destination already exists")
    actual = s40.parse_config(out / ".config")
    for key in ("CONFIG_KSU", "CONFIG_NOMOUNT", "CONFIG_KPROBES", "CONFIG_MODULE_SIG_FORCE",
                "CONFIG_MODULE_SIG_ALL", "CONFIG_MODULE_SIG_SHA512", "CONFIG_SECURITY_SELINUX",
                "CONFIG_SECCOMP_FILTER", "CONFIG_STACKPROTECTOR_STRONG", "CONFIG_LRU_GEN_ENABLED"):
        if actual.get(key) != "y":
            raise ValueError(f"Required build configuration not enabled: {key}")
    if actual.get("CONFIG_LOCALVERSION") != '"-synthetica-4.0-dev0"':
        raise ValueError("Unexpected localversion")
    if actual.get("CONFIG_LOCALVERSION_AUTO", "n") != "n":
        raise ValueError("Unexpected automatic localversion")

    image = out / "arch/arm64/boot/Image"
    image_bytes = image.read_bytes()
    if image_bytes[56:60] != b"ARM\x64" or struct.unpack_from("<Q", image_bytes, 16)[0] < len(image_bytes):
        raise ValueError("Invalid ARM64 kernel Image header")
    check_arm64_elf(out / "vmlinux")
    check_arm64_elf(nm)
    system_map = (out / "System.map").read_text(errors="strict")
    if "nomount_init" not in system_map or not any(x in system_map for x in ("kernelsu_init", "kernelsu_init_early")):
        raise ValueError("NoMount/KernelSU init symbols missing from System.map")
    # Identity is a compile-time check only; it does not prove that an APK is
    # accepted or speaks the new UAPI.
    if s40.CERT_HASH.encode() not in (out / "vmlinux").read_bytes():
        raise ValueError("Pinned Manager certificate digest not embedded")

    expected = [x for x in (out / "modules.order").read_text().splitlines() if x]
    installed_root = modules / "lib/modules" / RELEASE
    installed = sorted(installed_root.rglob("*.ko"))
    if not expected or len(installed) != len(expected):
        raise ValueError(f"Installed module count {len(installed)} != build count {len(expected)}")
    for module in installed:
        check_arm64_elf(module)
        data = module.read_bytes()
        if b"vermagic=" + RELEASE.encode() + b" " not in data or not data.endswith(MAGIC):
            raise ValueError(f"Module lacks expected vermagic/signature trailer: {module}")
    dtb_dir = out / "arch/arm64/boot/dts/qcom"
    boards = ("curtana", "joyeuse")
    panels = ("huaxing", "tianma")
    dtbs = [dtb_dir / f"sm7125-xiaomi-{board}-{panel}.dtb" for board in boards for panel in panels]
    for dtb in dtbs:
        if struct.unpack(">I", dtb.read_bytes()[:4])[0] != 0xD00DFEED:
            raise ValueError(f"Invalid DTB: {dtb}")

    selected = []
    for base in ("tcp_bic.ko", "tcp_htcp.ko", "tcp_westwood.ko"):
        matches = [p for p in installed if p.name == base]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one signed {base}, got {len(matches)}")
        selected.extend(matches)
    destination.mkdir(parents=True)
    (destination / "README-JANGAN-FLASH.txt").write_text(
        "BUKTI KOMPILASI EKSPERIMENTAL - JANGAN FLASH / DO NOT FLASH\n"
        "Ini bukan boot.img, installer recovery, atau release Synthetica 4.0.\n"
        "SUSFS 2.4 belum terintegrasi; Manager 5.0.1 UAPI 4 belum cocok dengan driver UAPI 5.\n"
        "Tidak ada bukti boot Joyeuse, ROM, root, enkripsi, radio, kamera, AVB, atau kepercayaan modul ROM.\n"
        "Modul yang disertakan hanya contoh bertanda tangan dari build ini. Private key tidak disertakan.\n"
    )
    (destination / "Image.gz.DO-NOT-FLASH").write_bytes(gzip.compress(image_bytes, compresslevel=9, mtime=0))
    for file, name in ((out / ".config", "generated.config.txt"),
                       (out / "Module.symvers", "Module.symvers.txt"),
                       (out / "System.map", "System.map.txt"),
                       (out / "certs/signing_key.x509", "kernel-module-public-cert.x509"),
                       (nm, "nm-arm64.DO-NOT-RUN"),
                       (ROOT / "build-kit/ci/synthetica40/inputs.json", "INPUTS.json")):
        shutil.copyfile(file, destination / name)
    (destination / "dtbs").mkdir()
    for dtb in dtbs:
        shutil.copyfile(dtb, destination / "dtbs" / (dtb.name + ".DO-NOT-FLASH"))
    (destination / "sample-signed-modules").mkdir()
    for module in selected:
        shutil.copyfile(module, destination / "sample-signed-modules" / (module.name + ".DO-NOT-LOAD"))
    result = {
        "kind": "EXPERIMENTAL_6_18_COMPILE_EVIDENCE_NOT_A_RELEASE",
        "kernelrelease": RELEASE,
        "kernel_source": s40.PINS["kernel"]["commit"],
        "ksun_source": s40.PINS["ksun"]["commit"],
        "nomount_source": s40.PINS["nomount"]["commit"],
        "image_sha256_uncompressed": hashlib.sha256(image_bytes).hexdigest(),
        "image_bytes": len(image_bytes),
        "image_runtime_size_bytes": struct.unpack_from("<Q", image_bytes, 16)[0],
        "all_module_count": len(installed),
        "all_modules_static_checks": ["arm64 ELF", "same vermagic", "signature trailer"],
        "dtbs": [p.name for p in dtbs],
        "nomount_protocol": 22,
        "ksun_uapi": 5,
        "manager_existing_uapi": 4,
        "susfs_2_4_included": False,
        "flashable": False,
        "physical_boot_tested": False,
        "runtime_root_tested": False,
        "target_rom_module_trust_tested": False,
        "provenance": provenance,
    }
    (destination / "EVIDENCE.json").write_text(json.dumps(result, indent=2) + "\n")
    files = sorted(p for p in destination.rglob("*") if p.is_file())
    if any(p.is_symlink() or p.suffix in {".pem", ".key", ".pk8", ".p12", ".jks"} for p in files):
        raise ValueError("Refusing to export a symlink or possible private key")
    (destination / "SHA256SUMS.txt").write_text(
        "".join(f"{sha(p)}  {p.relative_to(destination).as_posix()}\n" for p in files))
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("out", "modules", "nm", "destination"):
        p.add_argument(f"--{name}", type=Path, required=True)
    args = p.parse_args()
    provenance = {k: os.environ[k] for k in ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT") if k in os.environ}
    print(json.dumps(collect(args.out, args.modules, args.nm, args.destination, provenance), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, struct.error) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
