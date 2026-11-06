#!/usr/bin/env python3
"""Isolated Synthetica 2.0 scheduler/MGLRU experiment; never make an installer.

The pinned 2.0 kit, APK, release and 3.0 inputs remain untouched. This reuses
3.0's input guards and module verifier, but permits only the explicitly listed
new config symbols. Passing these host checks is NOT proof of device safety.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "build-kit/ci/synthetica2-experimental"
EXPECTED_RELEASE = "4.14.357-openela-Synthetica-2.0-exp"
PATCHES = {
    "0001-mglru-4.14.patch": "6c77c69bef438211859903ded71b35245d14f5cd7282fb5db605103d30d449e2",
    "0002-uclamp-walt-stune.patch": "44004efb1dcb451962fca536a596fc0f112827ab8b256efbfde5d6120dac42a7",
}
FEATURE_CONFIG_SHA = "4a6097a894e92790c347d8016b520b5c9923bb4dd5e33acf97ea3bd0159358ff"
NEUTRON_SHA = "531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30"
NEUTRON_SIZE = 77768187
MANAGER_APK_SHA = "7bded761808c560fa5511acf32d3ce728adedce663002820815d00176526b567"
MANAGER_CERT_SHA = "fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140"
ALLOWED_CHANGES = {
    "LOCALVERSION": ('"-Synthetica-2.0"', '"-Synthetica-2.0-exp"'),
    "UCLAMP_TASK": ("n", "y"),
    "UCLAMP_TASK_GROUP": ("n", "y"),
    "UCLAMP_BUCKETS_COUNT": ("n", "5"),
    "LRU_GEN": ("n", "y"),
    "NR_LRU_GENS": ("n", "7"),
    "TIERS_PER_GEN": ("n", "4"),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v3 = load_module("synthetica3_guards", ROOT / "build-kit/scripts/build_synthetica3.py")
modules = load_module("synthetica3_modules", ROOT / "build-kit/scripts/verify_synthetica3_modules.py")


def check_inputs() -> None:
    manifest = json.loads((INPUTS / "SOURCES.json").read_text(encoding="utf-8"))
    for name, expected in PATCHES.items():
        path = INPUTS / "patches" / name
        if v3.digest(path) != expected:
            raise ValueError(f"experimental patch digest changed: {name}")
    if v3.digest(INPUTS / "features.config") != FEATURE_CONFIG_SHA:
        raise ValueError("experimental feature config digest changed")
    for key, name in (("mglru", "0001-mglru-4.14.patch"), ("uclamp", "0002-uclamp-walt-stune.patch")):
        if manifest[key]["sha256"] != PATCHES[name] or manifest[key]["patch"] != "patches/" + name:
            raise ValueError(f"source manifest is inconsistent for {key}")
    if (manifest["feature_config_sha256"] != FEATURE_CONFIG_SHA or
            manifest["neutron"]["sha256"] != NEUTRON_SHA or
            manifest["neutron"]["bytes"] != NEUTRON_SIZE):
        raise ValueError("feature config or Neutron manifest pin changed")


def ensure_disposable(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError("refusing a symlinked tree or output directory")
    path = path.resolve()
    if path == ROOT or ROOT in path.parents or path in ROOT.parents:
        raise ValueError("experimental trees and outputs must be outside the repository")
    return path


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("unexpected upstream build kit layout: " + old[:100])
    return text.replace(old, new, 1)


def verify_manager() -> dict[str, object]:
    data = json.loads((ROOT / "release/MANAGER.json").read_text(encoding="utf-8"))
    if (data.get("package") != "net.ember.labs" or data.get("cert_der_bytes") != 1381 or
            data.get("cert_sha256") != MANAGER_CERT_SHA or
            data.get("output_apk", {}).get("sha256") != MANAGER_APK_SHA or
            v3.digest(ROOT / "release/Synthetica-2.0.apk") != MANAGER_APK_SHA):
        raise ValueError("actual Synthetica 2.0 Manager identity does not match the pin")
    return data


def check_config(baseline: str, generated: str) -> dict[str, dict[str, str]]:
    old, new = v3.read_config(baseline), v3.read_config(generated)
    for symbol in (*v3.REQUIRED_Y, "SCHED_WALT", "SCHED_TUNE", "CPU_FREQ_GOV_SCHEDUTIL",
                   "CPU_FREQ_DEFAULT_GOV_SCHEDUTIL", "CGROUP_SCHED"):
        if old.get(symbol) != "y" or new.get(symbol) != "y":
            raise ValueError(f"required baseline, thermal/security or scheduler feature not preserved: {symbol}")
    for symbol in (*v3.FORBIDDEN_Y, "LRU_GEN_ENABLED", "LRU_GEN_STATS"):
        if new.get(symbol, "n") != "n":
            raise ValueError(f"unsafe or premature experimental option enabled: {symbol}")
    changed = {
        k: {"2.0": old.get(k, "n"), "experiment": new.get(k, "n")}
        for k in sorted(old.keys() | new.keys()) if old.get(k, "n") != new.get(k, "n")
    }
    expected = {k: {"2.0": a, "experiment": b} for k, (a, b) in ALLOWED_CHANGES.items()}
    if changed != expected:
        bad = sorted(k for k in changed.keys() | expected.keys() if changed.get(k) != expected.get(k))
        raise ValueError("unexpected configuration difference(s): " + ", ".join(bad[:20]))
    return changed


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    check_inputs()
    verify_manager()
    destination = ensure_disposable(destination)
    # This verifies every pinned 2.0 input before copying; no original is edited.
    v3.prepare(source, destination, baseline)
    manager = json.loads((destination / "artifacts/manager/MANAGER.json").read_text(encoding="utf-8"))
    if (manager.get("package") != "net.ember.labs" or manager.get("cert_der_bytes") != 1381 or
            manager.get("cert_sha256") != MANAGER_CERT_SHA):
        raise ValueError("disposable kit would use a different Manager identity")

    profile = destination / "ci/rollercoaster/profiles/synthetica.config"
    with profile.open("a", encoding="utf-8") as out:
        out.write("\n# Synthetica 2.0 experiment only\n")
        out.write((INPUTS / "features.config").read_text(encoding="utf-8"))

    builder = destination / "ci/rollercoaster/build-rollercoaster.sh"
    text = builder.read_text(encoding="utf-8")
    text = replace_once(text,
        'export PATH="/usr/lib/llvm-18/bin:/usr/lib/ccache:/usr/bin:/bin:$PATH"',
        '''# The baseline hardcodes LLVM 18. In this disposable copy only, use the
# explicitly selected absolute toolchain directory; do not fall back silently.
: "${S2X_TOOLCHAIN_BIN:?absolute toolchain directory required}"
case "$S2X_TOOLCHAIN_BIN" in /*) ;; *) echo "toolchain path is not absolute"; exit 1 ;; esac
for tool in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-readelf llvm-strip llvm-size; do
  [ -x "$S2X_TOOLCHAIN_BIN/$tool" ] || { echo "missing $tool in selected toolchain"; exit 1; }
done
export PATH="$S2X_TOOLCHAIN_BIN:/usr/lib/ccache:/usr/bin:/bin:$PATH"
[ "$(command -v clang)" = "$S2X_TOOLCHAIN_BIN/clang" ] || { echo "wrong clang on PATH"; exit 1; }
clang --version
ld.lld --version''')
    text = text.replace("S3_HELPER", "S2X_HELPER").replace("S3_BASELINE", "S2X_BASELINE")
    text = text.replace("synthetica3-modules", "synthetica2-experimental-modules")
    text = text.replace("3.0 must keep the whole 2.0 config", "Experiment permits only the reviewed feature config changes")
    builder.write_text(text, encoding="utf-8")

    driver = destination / "scripts/build_chronicle_base.py"
    text = driver.read_text(encoding="utf-8")
    text = text.replace("S3_HELPER", "S2X_HELPER")
    text = replace_once(text, '"fix-ikconfig", "--tree", str(tree)', '"prepare-tree", "--tree", str(tree)')
    text = text.replace("Image compiled; 3.0 verification still required",
                        "Experimental image compiled; verification and device tests still required")
    driver.write_text(text, encoding="utf-8")
    print(f"Prepared disposable 2.0 experiment kit: {destination}")


def prepare_tree(tree: Path) -> None:
    check_inputs()
    tree = ensure_disposable(tree)
    if not (tree / "kernel/Makefile").is_file():
        raise ValueError("not a kernel source tree")
    for name in PATCHES:
        patch = INPUTS / "patches" / name
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=tree, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True)
        print("Applied", name, flush=True)
    v3.fix_ikconfig(tree)


def toolchain_info(kind: str, toolchain_bin: Path, neutron_archive: Path | None) -> dict[str, object]:
    if kind not in ("clang18", "neutron"):
        raise ValueError("unknown compiler")
    if not toolchain_bin.is_absolute():
        raise ValueError("toolchain directory must be absolute")
    toolchain_bin = toolchain_bin.resolve(strict=True)
    clang, lld = toolchain_bin / "clang", toolchain_bin / "ld.lld"
    cv = subprocess.run([str(clang), "--version"], check=True, text=True, capture_output=True).stdout.strip()
    lv = subprocess.run([str(lld), "--version"], check=True, text=True, capture_output=True).stdout.strip()
    required_version = "18.1.3" if kind == "clang18" else "24.0.0"
    if required_version not in cv or required_version not in lv:
        raise ValueError(f"wrong {kind} clang/lld version")
    if kind == "neutron":
        if (neutron_archive is None or neutron_archive.stat().st_size != NEUTRON_SIZE or
                v3.digest(neutron_archive) != NEUTRON_SHA):
            raise ValueError("Neutron archive does not match the pinned release")
    return {"kind": kind, "clang_version": cv, "lld_version": lv,
            "clang_sha256": v3.digest(clang), "lld_sha256": v3.digest(lld),
            "neutron_archive_sha256": NEUTRON_SHA if kind == "neutron" else None}


def finish(kit: Path, out: Path, baseline: Path, result: Path, kind: str,
           toolchain_bin: Path, neutron_archive: Path | None) -> None:
    check_inputs()
    manager = verify_manager()
    toolchain = toolchain_info(kind, toolchain_bin, neutron_archive)
    kit, out, result = map(ensure_disposable, (kit, out, result))
    if result.exists():
        raise ValueError("refusing to overwrite existing results")
    baseline_text = v3.verified_baseline(baseline)
    cfg = (out / ".config").read_bytes()
    if cfg != (kit / "artifacts/generated.config.txt").read_bytes():
        raise ValueError("built and collected configurations differ")
    changes = check_config(baseline_text, cfg.decode("utf-8"))
    image = kit / "artifacts/Image.gz"
    if image.stat().st_size <= v3.MIN_IMAGE_BYTES:
        raise ValueError("image is unexpectedly small")
    with gzip.open(image, "rb") as f:
        raw = f.read(v3.MAX_RAW_IMAGE + 1)
    if len(raw) > v3.MAX_RAW_IMAGE:
        raise ValueError("raw image exceeds size limit")
    match = re.search(rb"Linux version ([^\s]+)", raw)
    if not match or match.group(1).decode("ascii", "replace") != EXPECTED_RELEASE:
        raise ValueError("unexpected image release string")
    v3.verify_embedded_config(raw, cfg)
    if (b"KernelSU" not in raw or manager["package"].encode() not in raw or
            manager["cert_sha256"].encode() not in raw):
        raise ValueError("pinned KernelSU Manager identity not found in image")
    kit_manager = kit / "artifacts/manager/MANAGER.json"
    if v3.digest(kit_manager) != v3.PINNED_INPUTS["artifacts/manager/MANAGER.json"]:
        raise ValueError("disposable kit's Manager identity changed after preparation")

    symvers = (out / "Module.symvers").read_text(encoding="utf-8")
    crc = modules.symvers_records(symvers)["module_layout"]
    system_map = out / "System.map"
    if not system_map.is_file() or system_map.stat().st_size == 0:
        raise ValueError("missing System.map")
    cert = out / "certs/signing_key.x509"
    cert_data = subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(cert), "-outform", "DER"],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    if not cert_data or cert_data != cert.read_bytes() or raw.count(cert_data) != 1:
        raise ValueError("build's public module certificate is not present exactly once in image")
    stage = out / "synthetica2-experimental-modules/lib/modules" / EXPECTED_RELEASE / "kernel"
    checked_modules = modules.collect(stage, config=v3.read_config(cfg.decode("utf-8")),
        release=EXPECTED_RELEASE, certificate_der=cert_data, raw_kernel=raw, symvers_text=symvers)

    report = {
        "kind": "EXPERIMENTAL_COMPILED_ONLY_DO_NOT_FLASH",
        "release": EXPECTED_RELEASE,
        "base_source": v3.SOURCE,
        "compiler": toolchain,
        "image_sha256": v3.digest(image),
        "config_sha256": v3.digest(out / ".config"),
        "changes_from_saved_2_0_config": changes,
        "walt_and_schedtune": "compiled in; runtime interaction not tested",
        "uclamp": "compiled in; neutral defaults; runtime interaction not tested",
        "mglru": "compiled in, disabled by default; runtime not tested",
        "manager": {"package": manager["package"], "cert_der_bytes": 1381, "cert_sha256": MANAGER_CERT_SHA,
                    "apk_sha256": MANAGER_APK_SHA, "runtime_pairing_tested": False},
        "module_layout_crc": f"0x{crc:08x}",
        "same_build_modules_static_checks": {name: item[1] for name, item in checked_modules.items()},
        "rom_vendor_module_abi_and_trust": "NOT VERIFIED",
        "physical_boot_root_thermal_battery_suspend_charging_tests": "NOT RUN",
        "installer_created": False,
        "private_key_exported": False,
    }
    result.mkdir(parents=True)
    shutil.copy2(image, result / "Image.gz.DO-NOT-FLASH")
    shutil.copy2(out / ".config", result / "generated.config.txt")
    shutil.copy2(system_map, result / "System.map")
    shutil.copy2(out / "Module.symvers", result / "Module.symvers")
    (result / "STATUS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (result / "README-DO-NOT-FLASH.txt").write_text(
        "EXPERIMENTAL COMPILE EVIDENCE ONLY. No installer is provided.\n"
        "Boot, Manager, vendor module ABI/trust, suspend, charging, thermal and battery are NOT tested.\n"
        "MGLRU is compiled in but disabled by default; do not enable it on an unvalidated device.\n",
        encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for name in ("source", "destination", "baseline"):
        prep.add_argument("--" + name, type=Path, required=True)
    tree = sub.add_parser("prepare-tree")
    tree.add_argument("--tree", type=Path, required=True)
    cfg = sub.add_parser("check-config")
    cfg.add_argument("--baseline", type=Path, required=True)
    cfg.add_argument("--generated", type=Path, required=True)
    done = sub.add_parser("finish")
    for name in ("kit", "out", "baseline", "result", "toolchain-bin"):
        done.add_argument("--" + name, type=Path, required=True)
    done.add_argument("--compiler", choices=("clang18", "neutron"), required=True)
    done.add_argument("--neutron-archive", type=Path)
    args = p.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.destination, args.baseline)
    elif args.command == "prepare-tree":
        prepare_tree(args.tree)
    elif args.command == "check-config":
        check_inputs()
        print(json.dumps(check_config(v3.verified_baseline(args.baseline),
                                      args.generated.read_text(encoding="utf-8")), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.result, args.compiler,
               args.toolchain_bin, args.neutron_archive)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f"Experimental build refused: {exc}", file=sys.stderr)
        sys.exit(1)
