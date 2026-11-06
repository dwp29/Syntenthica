#!/usr/bin/env python3
"""Read-only comparison of extracted ROM modules with a 2.0 experiment build.

Inputs and the detailed report stay outside the repository. This is bounded
static evidence, not proof of an installed ROM, active keyring, module loading,
bootability, or device behavior. No module signatures or checks are bypassed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

import audit_synthetica3_vendor as vendor
import build_synthetica2_experimental as s2x
import verify_synthetica3_modules as modules

MAX_IMAGE = 64 * 1024 * 1024
MAX_TEXT = 32 * 1024 * 1024
MAX_MODULES = 1000


def load_candidate(directory: Path, baseline: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("candidate must be a nonsymlink directory")
    status = json.loads(vendor.read_regular(directory / "STATUS.json", MAX_TEXT))
    if (status.get("kind") != "EXPERIMENTAL_COMPILED_ONLY_DO_NOT_FLASH" or
            status.get("release") != s2x.EXPECTED_RELEASE or status.get("base_source") != s2x.v3.SOURCE or
            status.get("installer_created") is not False or status.get("private_key_exported") is not False):
        raise ValueError("candidate is not a verified-format experimental compile-only result")
    mode = status.get("mglru", {}).get("variant")
    if mode not in ("on", "off") or status["mglru"].get("enabled_by_default") != (mode == "on"):
        raise ValueError("candidate MGLRU status is ambiguous")
    names = {"image_sha256": "Image.gz.DO-NOT-FLASH", "config_sha256": "generated.config.txt",
             "module_symvers_sha256": "Module.symvers", "system_map_sha256": "System.map",
             "module_public_cert_sha256": "module-signing-public-cert.x509"}
    data = {}
    for field, name in names.items():
        content = vendor.read_regular(directory / name, MAX_IMAGE if name.startswith("Image") else MAX_TEXT)
        if hashlib.sha256(content).hexdigest() != status.get(field):
            raise ValueError(f"candidate {name} does not match its status digest")
        data[name] = content
    config = data["generated.config.txt"]
    s2x.check_config(s2x.v3.verified_baseline(baseline), config.decode("utf-8"), mode)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data["Image.gz.DO-NOT-FLASH"])) as image:
            raw = image.read(s2x.v3.MAX_RAW_IMAGE + 1)
    except (OSError, EOFError) as exc:
        raise ValueError("candidate image is not valid gzip") from exc
    cert = data["module-signing-public-cert.x509"]
    banner = re.search(rb"Linux version ([^\s]+)", raw)
    if (len(raw) > s2x.v3.MAX_RAW_IMAGE or not cert or raw.count(cert) != 1 or not banner or
            banner.group(1).decode("ascii", "replace") != s2x.EXPECTED_RELEASE):
        raise ValueError("candidate image, release or embedded build certificate did not match")
    s2x.v3.verify_embedded_config(raw, config)
    symvers_text = data["Module.symvers"].decode("ascii")
    symvers = modules.symvers_records(symvers_text)
    if status.get("module_layout_crc") != f"0x{symvers['module_layout']:08x}":
        raise ValueError("candidate module_layout CRC disagrees with its status")
    map_types: dict[str, set[str]] = {}
    for line in data["System.map"].decode("ascii").splitlines():
        fields = line.split()
        if len(fields) != 3 or not re.fullmatch(r"[0-9a-fA-F]+", fields[0]) or len(fields[1]) != 1:
            raise ValueError("invalid System.map entry")
        map_types.setdefault(fields[2], set()).add(fields[1])
    builtins = {parts[1] for line in symvers_text.splitlines() if len(parts := line.split()) >= 3
                and parts[2] == "vmlinux"}
    bundled_names = set(status.get("same_build_modules_static_checks", {}))
    return {"release": status["release"], "mode": mode, "cert": cert, "symvers": symvers,
            "map_names": set(map_types), "map_types": map_types, "builtins": builtins,
            "module_srcversions": {}, "export_providers": vendor.export_provider_index(symvers_text, bundled_names),
            "image_sha256": status["image_sha256"], "certificate_sha256": status["module_public_cert_sha256"]}


def module_paths(directory: Path) -> tuple[list[Path], list[str]]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("module input must be a nonsymlink directory")
    paths, skipped = [], []
    for root, dirs, files in os.walk(directory, followlinks=False):
        base = Path(root)
        safe_dirs = []
        for name in sorted(dirs):
            path = base / name
            if path.is_symlink():
                skipped.append(str(path.relative_to(directory)))
            else:
                safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in sorted(files):
            path = base / name
            if path.is_symlink():
                skipped.append(str(path.relative_to(directory)))
            elif name.endswith(".ko"):
                paths.append(path)
            elif re.search(r"\.ko\.(gz|xz|zst)$", name):
                skipped.append(str(path.relative_to(directory)))
            if len(paths) + len(skipped) > MAX_MODULES:
                raise ValueError("module input exceeds the bounded inventory")
    if not paths:
        raise ValueError("no uncompressed regular .ko files found in input")
    return paths, skipped


def audit(directory: Path, target: dict) -> dict:
    paths, skipped = module_paths(directory)
    rows, errors = [], []
    expected_vermagic = target["release"] + " SMP preempt mod_unload modversions aarch64"
    for path in paths:
        relative = str(path.relative_to(directory))
        try:
            row = vendor.audit_one(path, target, loaded=False)
            row["relative_path"] = relative
            row["listed_in_modules_load"] = "not checked"
            row["vermagic_matches_candidate"] = row["vermagic"] == expected_vermagic
            rows.append(row)
        except (ValueError, OSError, UnicodeError) as exc:
            errors.append({"relative_path": relative, "reason": str(exc)})
    summary = {
        "module_files_found": len(paths), "module_files_parsed": len(rows), "module_files_unparsed": len(errors),
        "symlinks_or_compressed_entries_skipped": len(skipped),
        "module_layout_matches": sum(row["module_layout_matches_bundle"] for row in rows),
        "vermagic_matches": sum(row["vermagic_matches_candidate"] for row in rows),
        "verified_with_exported_build_certificate": sum(
            row["signature_result"] == "verified_with_bundle_certificate" for row in rows),
        "missing_appended_signature": sum(row["signature_result"] == "no_appended_signature" for row in rows),
    }
    return {"scope": "Static comparison only; supplied files may not be loaded or from the installed ROM. "
                     "The build certificate is not an exhaustive runtime keyring audit; no device test was performed.",
            "target_release": target["release"], "mglru_variant": target["mode"],
            "target_image_sha256": target["image_sha256"], "target_certificate_sha256": target["certificate_sha256"],
            "summary": summary, "modules": rows, "unparsed": errors, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="new private report outside all inputs and the repository")
    args = parser.parse_args()
    try:
        target = load_candidate(args.candidate, args.baseline)
        report = audit(args.modules, target)
        vendor.write_private(args.report, report, [args.modules, args.candidate])
        print(json.dumps({"mglru_variant": report["mglru_variant"], "summary": report["summary"],
                          "scope": report["scope"]}, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ROM module audit did not complete: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
