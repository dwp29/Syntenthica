#!/usr/bin/env python3
"""Build-stage support for a non-flashable mi_memory kernel experiment.

The mi_memory code is a pinned donor from a different SoC. This is a linking
experiment, not a validated replacement for the Joyeuse vendor module.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("joyeuse_builtin_build", HERE / "build_joyeuse_builtin_experiment.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load built-in build helper")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

RELEASE = "4.14.357-openela-Synthetica-2.0-JOYEUSE-MIMEM-EXPERIMENT"
MI_SYMBOLS = ("mi_memory_sysfs_init", "set_ufs_hba_data", "ufs_get_string_desc", "memblock_mem_size_in_gb")
DONOR = "projects-nexus/nexus_kernel_xiaomi_sm8250@d26c193dcd97812a9a565ac40fe5092cc9a18fbf"
OMITTED = ["tag_stats", "err_state", "err_reason", "req_stats"]


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("expected build-stage anchor is absent or duplicated")
    return text.replace(old, new)


def prepare(source: Path, destination: Path, fragment: Path) -> None:
    base.prepare(source, destination, fragment)
    profile = destination / "ci/rollercoaster/profiles/synthetica.config"
    profile.write_text(profile.read_text() + "\n# COMPILE-ONLY different-SoC mi_memory candidate.\nCONFIG_MI_MEMORY_SYSFS=y\n")
    builder = destination / "ci/rollercoaster/build-rollercoaster.sh"
    old = 'python3 "$SP_EXPERIMENT_GUARD" check-config --baseline "$SP_EXPERIMENT_BASELINE_CONFIG" --generated "$OUT/.config"\n'
    guard = old + '''grep -qx 'CONFIG_MI_MEMORY_SYSFS=y' "$OUT/.config" || { echo "MI_MEMORY_SYSFS is not built-in"; exit 1; }
if grep -q '^CONFIG_DEBUG_FS=' "$OUT/.config"; then echo "DEBUG_FS changed; refusing build"; exit 1; fi
'''
    builder.write_text(replace_once(builder.read_text(), old, guard))
    driver = destination / "scripts/build_chronicle_base.py"
    old = '    tree = extract(archive, WORK / "tree")\n'
    hook = old + '''    subprocess.run([sys.executable, os.environ["SP_MI_MEMORY_PROBE"], "apply",
                    "--tree", str(tree), "--donor", os.environ["SP_MI_MEMORY_DONOR"]], check=True)
'''
    driver.write_text(replace_once(driver.read_text(), old, hook))
    print("Prepared isolated mi_memory build; no flashable package will be created")


def finish(kit: Path, out: Path, baseline: Path, result: Path) -> None:
    config = base.read_config((out / ".config").read_text())
    if config.get("MI_MEMORY_SYSFS") != "y" or config.get("DEBUG_FS", "n") != "n":
        raise ValueError("mi_memory not built-in or DEBUG_FS is unexpectedly enabled")
    base.EXPECTED_RELEASE = RELEASE
    base.REQUIRED_SYMBOLS = base.REQUIRED_SYMBOLS + MI_SYMBOLS
    base.finish(kit, out, baseline, result)
    status_path = result / "STATUS.json"
    status = json.loads(status_path.read_text())
    status["mi_memory_backport"] = {
        "source": DONOR,
        "different_soc_source": True,
        "matches_joyeuse_module": "NOT_PROVEN",
        "unsupported_debug_attributes_omitted": OMITTED,
        "module_equivalence_or_ufs_runtime_safety": "NOT_PROVEN",
        "device_test": "NOT_RUN",
    }
    status["vendor_module_compatibility"] = "NOT_PROVEN; this is not a complete vendor module replacement"
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    (result / "README-DO-NOT-FLASH.txt").write_text(
        "DO NOT FLASH. Kernel linking experiment only; not a boot image, ROM or installer.\n"
        "mi_memory is adapted from an sm8250 source tree, not proven equivalent to Joyeuse.\n"
        "Four unsupported debug sysfs attributes are omitted; UFS lifetime, device behavior,\n"
        "module signatures, CRCs, boot and SELinux/AVB runtime have NOT been validated.\n"
        "Module signature enforcement and MODVERSIONS remain enabled. No ROM is modified.\n"
    )
    print("mi_memory backport remains unverified: no runtime or flash approval")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--fragment", type=Path, required=True)
    f = commands.add_parser("finish")
    f.add_argument("--kit", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--baseline", type=Path, required=True)
    f.add_argument("--result", type=Path, required=True)
    a = parser.parse_args()
    if a.command == "prepare":
        prepare(a.source, a.destination, a.fragment)
    else:
        finish(a.kit, a.out, a.baseline, a.result)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"MI-MEMORY KERNEL EXPERIMENT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
