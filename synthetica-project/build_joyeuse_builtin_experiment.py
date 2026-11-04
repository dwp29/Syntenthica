#!/usr/bin/env python3
"""Prepare and verify a non-flashable Joyeuse kernel experiment.

The existing Synthetica build is never modified. The actual kernel compilation
is done by its pinned builder in a disposable copy. This experiment does not
patch vendor modules, ROM images, SELinux policy, AVB or boot partitions.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

BASELINE_SHA256 = "248af9218b5ed9dd82202956d99991f97428c3010565a810eac3c9e6f71ff33b"
PINNED_INPUTS = {
    "ci/rollercoaster/build-rollercoaster.sh": "033ea7e5789b129ac1226837a897c6d8735d8e15dc14fbb914b83dddd6c53715",
    "ci/rollercoaster/profiles/synthetica.config": "b2680e2cd32c76a2c64849a8a635d48c6a2a6df2699a7f75bde09c8efa3ec0e3",
    "scripts/build_chronicle_base.py": "c92f32b1792d999008de18bd2d91418472219349798f0d546b7ef223e3747cdc",
    "ci/SOURCES_CHRONICLE_BASE.json": "9a09ae658bbc6e5f48f5404f56b108380c5659aba2786c108d87be253fb13912",
    "artifacts/manager/MANAGER.json": "4f5131b5dd6655c781482d67cb613949cda220030534c5d72ee8dafda0e7fa69",
}
REQUIRED = (
    "BRIDGE_NETFILTER", "USB_GSPCA", "LCD_CLASS_DEVICE", "QCOM_LLCC_PERFMON",
    "QCA_CLD_WLAN", "EXFAT_FS", "MODULES", "MODVERSIONS", "MODULE_SIG",
    "MODULE_SIG_FORCE", "MODULE_SIG_ALL", "SECURITY", "SECURITY_SELINUX",
)
DISABLED = ("MODULE_FORCE_LOAD", "SECURITY_SELINUX_DISABLE")
SECURITY_PREFIXES = (
    "SECURITY", "MODULE_SIG", "MODULE_FORCE_", "MODVERSIONS", "SECCOMP", "AUDIT",
    "INTEGRITY", "IMA", "EVM", "DM_VERITY", "DEFAULT_SECURITY", "CMDLINE",
    "RANDOMIZE_BASE", "HARDENED_USERCOPY", "STACKPROTECTOR", "ARM64_PAN",
)
REQUIRED_SYMBOLS = (
    "br_netfilter_init", "gspca_dev_probe", "lcd_device_register", "llcc_perfmon_probe",
)
EXPECTED_RELEASE = "4.14.357-openela-Synthetica-2.0-JOYEUSE-EXPERIMENT"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_config(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        set_match = re.fullmatch(r"CONFIG_([A-Z0-9_]+)=(.*)", line)
        off_match = re.fullmatch(r"# CONFIG_([A-Z0-9_]+) is not set", line)
        if set_match:
            key, value = set_match.groups()
        elif off_match:
            key, value = off_match.group(1), "n"
        else:
            continue
        if key in result:
            raise ValueError(f"duplicate config symbol: {key}")
        result[key] = value
    return result


def check_fragment(fragment: str) -> None:
    expected = {**dict.fromkeys(REQUIRED, "y"), **dict.fromkeys(DISABLED, "n")}
    if read_config(fragment) != expected:
        raise ValueError("experiment config differs from the reviewed allowlist")


def check_config(baseline: str, generated: str) -> dict[str, dict[str, str]]:
    old, new = read_config(baseline), read_config(generated)
    for sym in REQUIRED:
        if new.get(sym) != "y":
            raise ValueError(f"required built-in/security config is not y: {sym}")
    for sym in DISABLED:
        if new.get(sym, "n") != "n":
            raise ValueError(f"forbidden config is enabled: {sym}")
    for sym in sorted(set(old) | set(new)):
        if sym.startswith(SECURITY_PREFIXES) and old.get(sym, "n") != new.get(sym, "n"):
            raise ValueError(f"security configuration changed: {sym}: {old.get(sym, 'n')} -> {new.get(sym, 'n')}")
    return {
        sym: {"baseline": old.get(sym, "n"), "experiment": new.get(sym, "n")}
        for sym in sorted(set(old) | set(new))
        if old.get(sym, "n") != new.get(sym, "n")
    }


def verified_baseline(path: Path) -> str:
    if digest(path) != BASELINE_SHA256:
        raise ValueError("baseline config is not the pinned Synthetica 2.0 config")
    return path.read_text()


def prepare(source: Path, destination: Path, fragment_path: Path) -> None:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("disposable build kit must be outside the original build kit")
    if destination.exists():
        raise ValueError("refusing to overwrite a pre-existing disposable build kit")
    fragment = fragment_path.read_text()
    check_fragment(fragment)
    for name, expected in PINNED_INPUTS.items():
        if digest(source / name) != expected:
            raise ValueError(f"input has changed; refusing to patch it: {name}")
    # Exclude all existing outputs: only the pinned manager identity is copied back.
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("artifacts", ".git", "__pycache__"))
    mgr = destination / "artifacts/manager/MANAGER.json"
    mgr.parent.mkdir(parents=True)
    shutil.copy2(source / "artifacts/manager/MANAGER.json", mgr)

    profile = destination / "ci/rollercoaster/profiles/synthetica.config"
    profile.write_text(profile.read_text() + "\n# --- Joyeuse experimental built-ins ---\n" + fragment)

    builder = destination / "ci/rollercoaster/build-rollercoaster.sh"
    text = builder.read_text()
    anchor = 'make "${MO[@]}" olddefconfig >/dev/null\n'
    if text.count(anchor) != 1:
        raise ValueError("expected olddefconfig anchor not found exactly once")
    guard = '''\n# Refuse to compile if any security option changed or a built-in was lost.
: "${SP_EXPERIMENT_GUARD:?guard path required}"
: "${SP_EXPERIMENT_BASELINE_CONFIG:?baseline config path required}"
python3 "$SP_EXPERIMENT_GUARD" check-config --baseline "$SP_EXPERIMENT_BASELINE_CONFIG" --generated "$OUT/.config"
'''
    text = text.replace(anchor, anchor + guard)
    marker = "# --- kemas AnyKernel3 "
    if text.count(marker) != 1:
        raise ValueError("expected packaging marker not found exactly once")
    # A test image only: do not even create an AnyKernel/flashable package.
    text = text[:text.index(marker)] + '\necho "EXPERIMENT ONLY: packaging disabled; DO NOT FLASH"\nexit 0\n'
    builder.write_text(text)

    driver = destination / "scripts/build_chronicle_base.py"
    text = driver.read_text()
    start, end_marker = "    status = {\n", '\n\nif __name__ == "__main__":'
    if text.count(start) != 1 or text.count(end_marker) != 1:
        raise ValueError("unexpected builder metadata layout")
    # The stock status claims only an identity change and an installer. Both
    # would be misleading here; generate our own status after verification.
    text = text[:text.index(start)] + '    say("EXPERIMENT ONLY: compilation finished; verification still required")\n' + text[text.index(end_marker):]
    driver.write_text(text)
    print(f"Prepared isolated, non-flashable build kit: {destination}")


def finish(kit: Path, out: Path, baseline_path: Path, result: Path) -> None:
    baseline = verified_baseline(baseline_path)
    generated_path, system_map = out / ".config", out / "System.map"
    changes = check_config(baseline, generated_path.read_text())
    symbols = {line.split()[-1] for line in system_map.read_text().splitlines() if line.split()}
    missing = sorted(set(REQUIRED_SYMBOLS) - symbols)
    if missing:
        raise ValueError("built-in symbols not linked in System.map: " + ", ".join(missing))
    image = kit / "artifacts/Image.gz"
    if image.stat().st_size <= 8 * 1024 * 1024:
        raise ValueError("compiled image is unexpectedly small")
    with gzip.open(image, "rb") as f:
        raw = f.read(96 * 1024 * 1024)
    match = re.search(rb"Linux version ([^\s]+)", raw)
    if not match or match.group(1).decode("ascii") != EXPECTED_RELEASE:
        raise ValueError("compiled image release does not match experiment")
    if result.exists():
        raise ValueError("refusing to overwrite existing result directory")
    result.mkdir(parents=True)
    image_name = "DO-NOT-FLASH-JOYEUSE-BUILTIN-Image.gz"
    shutil.copy2(image, result / image_name)
    shutil.copy2(generated_path, result / "generated.config.txt")
    shutil.copy2(system_map, result / "System.map.txt")
    symvers = out / "Module.symvers"
    if symvers.is_file():
        shutil.copy2(symvers, result / "Module.symvers.txt")
    log = kit / "artifacts/build.log"
    if log.is_file():
        shutil.copy2(log, result / "build.log.txt")
    status = {
        "status": "COMPILED_ONLY_DO_NOT_FLASH",
        "device": "joyeuse / miatoll; physical device not tested",
        "release": EXPECTED_RELEASE,
        "image_sha256": digest(image),
        "image_bytes": image.stat().st_size,
        "config_sha256": digest(generated_path),
        "security_baseline_config_sha256": BASELINE_SHA256,
        "security_config_unchanged": True,
        "required_symbols_linked": list(REQUIRED_SYMBOLS),
        "config_changes": changes,
        "boot_test": "NOT_RUN",
        "vendor_module_compatibility": "NOT_PROVEN; module signatures and CRC mismatches remain",
        "source": "Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795b557b7bf92220c91f05a42b456de7a74",
        "private_module_signing_key_exported": False,
        "rom_or_boot_image_modified": False,
    }
    (result / "STATUS.json").write_text(json.dumps(status, indent=2) + "\n")
    (result / "README-DO-NOT-FLASH.txt").write_text(
        "DO NOT FLASH. Experimental kernel Image.gz only; no boot image or installer.\n"
        "Compiled with selected in-tree drivers built in. This does not prove vendor\n"
        "module compatibility, hardware behavior, bootability, or ROM readiness.\n"
        "No ROM, boot image, AVB settings, or SELinux policy was modified.\n"
        "Module signature enforcement and MODVERSIONS remain enabled.\n"
    )
    print(json.dumps(status, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--destination", type=Path, required=True)
    prep.add_argument("--fragment", type=Path, required=True)
    chk = sub.add_parser("check-config")
    chk.add_argument("--baseline", type=Path, required=True)
    chk.add_argument("--generated", type=Path, required=True)
    fin = sub.add_parser("finish")
    fin.add_argument("--kit", type=Path, required=True)
    fin.add_argument("--out", type=Path, required=True)
    fin.add_argument("--baseline", type=Path, required=True)
    fin.add_argument("--result", type=Path, required=True)
    args = p.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.destination, args.fragment)
    elif args.command == "check-config":
        changes = check_config(verified_baseline(args.baseline), args.generated.read_text())
        print(f"Security configuration preserved; {len(changes)} config differences")
    else:
        finish(args.kit, args.out, args.baseline, args.result)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"EXPERIMENT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
