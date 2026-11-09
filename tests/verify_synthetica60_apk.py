#!/usr/bin/env python3
"""Static verification for a Synthetica Manager 6.0.0 APK (signed or unsigned).

Bytes and metadata only. This is NOT a device, root, update or boot test.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_synthetica21_apk import REFERENCE, SYMBOL, get_symbol_code, normalized_native

TREE = ROOT / "synthetica-manager"
KSUD_SHA256 = "c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427"
HELPERS = ("synthetica-control40.sh", "synthetica-boost40.sh", "synthetica-universal60.sh")

DEX_MARKERS = (
    b"PIXEL // MANAGER 6.0.0",
    b"CYBERPUNK // MANAGER 6.0.0",
    b"GLASS // MANAGER 6.0.0",
    b"NEON // MANAGER 6.0.0",
    b"synthetica-universal60.sh",
    b"kmod_status",
    b"diag_pstore",
    b"manager_anim_speed",
    b"synthetica-manager-6.0.0",
    b"manager_visual_style",
)


def string_pool(arsc: bytes) -> bytes:
    """Return the resource string pool bytes so names can be searched reliably."""
    if len(arsc) < 12:
        raise ValueError("resources.arsc is truncated")
    _, header_size, _ = struct.unpack_from("<HHI", arsc, 0)
    return arsc[header_size:]


def verify(apk: Path) -> None:
    with zipfile.ZipFile(apk) as z, zipfile.ZipFile(REFERENCE) as previous:
        bad = z.testzip()
        if bad:
            raise ValueError(f"APK ZIP CRC mismatch: {bad}")
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate APK ZIP entries")

        # Binary AXML stores literals UTF-16LE, sometimes pooled as UTF-8.
        manifest = z.read("AndroidManifest.xml")
        if "net.ember.labs".encode() not in manifest and "net.ember.labs".encode("utf-16-le") not in manifest:
            raise ValueError("AndroidManifest.xml lacks the net.ember.labs package id")
        # versionCode/versionName live in the binary AXML integer/string pools.
        if "versionName".encode("utf-16-le") not in manifest:
            raise ValueError("AndroidManifest.xml lacks a versionName attribute")

        native = z.read("lib/arm64-v8a/libkernelsu.so")
        if get_symbol_code(native, SYMBOL) != bytes.fromhex("80008052c0035fd6"):
            raise ValueError("Manager JNI accessor does not return UAPI 4")
        if normalized_native(native) != normalized_native(previous.read("lib/arm64-v8a/libkernelsu.so")):
            raise ValueError("Manager JNI differs from the 2.0 baseline except the ELF build ID")
        adbroot = "lib/arm64-v8a/libadbroot.so"
        if normalized_native(z.read(adbroot)) != normalized_native(previous.read(adbroot)):
            raise ValueError("ADB root native code differs from the 2.0 baseline except the ELF build ID")

        daemon = z.read("lib/arm64-v8a/libksud.so")
        if hashlib.sha256(daemon).hexdigest() != KSUD_SHA256:
            raise ValueError("Root daemon is not the pinned UAPI-4 libksud.so")

        other_arch = [n for n in names if n.startswith("lib/") and n.endswith(".so")
                      and not n.startswith("lib/arm64-v8a/")]
        if other_arch:
            raise ValueError(f"Unexpected native ABI: {other_arch}")

        for name in ("META-INF/com/google/android/update-binary", "META-INF/com/google/android/updater-script"):
            if z.read(name) != previous.read(name):
                raise ValueError(f"Installer asset changed: {name}")

        for helper in HELPERS:
            packaged = z.read(f"assets/{helper}")
            if packaged != (TREE / "app/src/main/assets" / helper).read_bytes():
                raise ValueError(f"Bundled helper differs from the standalone tree: {helper}")
        for helper in HELPERS:
            if not (TREE / "app/src/main/assets" / helper).read_bytes().startswith(b"#!/system/bin/sh"):
                raise ValueError(f"{helper} lost its shebang")

        dex = b"".join(z.read(n) for n in names if n.endswith(".dex"))
        for marker in DEX_MARKERS:
            if marker not in dex:
                raise ValueError(f"6.0.0 DEX marker missing: {marker!r}")
        if b"MANAGER 5.0.1" in dex or b"v5.0.1" in dex:
            raise ValueError("Stale 5.0.1 label still present in the 6.0.0 DEX")

        arsc = string_pool(z.read("resources.arsc")) if "resources.arsc" in names else b""
        for key in (b"manager60_telemetry_group", b"manager60_kmod_group", b"manager60_diag_dmesg",
                    b"manager60_universal_bridge_title", b"manager60_export_json", b"manager60_bridge_native"):
            if key not in arsc and not any(key.decode() in n for n in names):
                raise ValueError(f"resource string missing from APK: {key!r}")
        for emblem in ("ic_emblem_pixel", "ic_emblem_cyberpunk", "ic_emblem_ios_glass", "ic_emblem_neon"):
            if emblem.encode() not in arsc and not any(emblem in n for n in names):
                raise ValueError(f"theme PNG emblem missing from APK: {emblem}")

        png_hashes = {hashlib.sha256(z.read(n)).hexdigest() for n in names
                      if n.startswith("res/") and n.endswith(".png")}
        if len(png_hashes) < 4:
            raise ValueError("Expected at least 4 distinct PNG emblems")

    print("Manager 6.0.0 static gates passed:")
    print("  identity net.ember.labs / 6.0.0, UAPI 4 JNI, pinned UAPI-4 libksud.so")
    print("  Universal Root Bridge, telemetry, .ko loader and diag markers in DEX")
    print("  4 PNG emblems, 4 splash tags, localized manager60_* strings")
    print("  installer scripts unchanged from the 2.0 baseline")
    print("Not verified: Android install, live su/root, real module loading or boot behaviour.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} APK")
    verify(Path(sys.argv[1]))
