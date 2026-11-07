#!/usr/bin/env python3
"""Guarded 3.0 release-candidate build based on the user-tested 2.0 experiment.

This reuses its pinned source, feature patches, Neutron toolchain and guards. The
only new source change preserves inherited seccomp for the Manager on 4.14;
root-profile and other root-allowed app behavior is deliberately unchanged. A
separate test installer may be made only from verified evidence. Neither this
script nor host tests prove device boot, root, seccomp, camera or module trust.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "build-kit/ci/synthetica3-rc"
PATCH = INPUTS / "0001-ksu-manager-preserve-seccomp.patch"
PATCH_SHA256 = "b28e7233d31973b268ed3063f1402f443b5dfa1475e000b03bc39832bfe77123"
SETUID_SOURCE_SHA256 = "a10d40e94cbe4db04062a2da80c111f504ea2d5e23f9f2fc1ee728f88bba501b"
SETUID_PATCHED_SHA256 = "ac5d7b33688b39017ea6f2e8b88e493f8930be4f5b52fd660a1b94b9aeafde47"
ROOT_PROFILE_SHA256 = "57aac0553c531c8eac10f466557cc64b7e6c3ac38d13390d5a2fded17141dcc6"
TESTED_CONFIG_SHA256 = "c72503550d74446f5af3573288b4e93dc1407854c5df338d20681d1866ccb96c"
TESTED_IMAGE_SHA256 = "3a9f39f8f7ea79c9251a896050dfeb60395f1194a064f91a85a8fe8ae38adaea"
TESTED_CERT_SHA256 = "3a9abf2050e245223eed64e346365b99b0085f54ff0d5b845fa3ce8e5ff17a2a"
EXPECTED_RELEASE = "4.14.357-openela-Synthetica-3.0-rc1"
EXPECTED_LOCALVERSION = '"-Synthetica-3.0-rc1"'


def load_s2x():
    path = ROOT / "build-kit/scripts/build_synthetica2_experimental.py"
    spec = importlib.util.spec_from_file_location("synthetica2_for_3rc", path)
    if spec is None or spec.loader is None:
        raise ValueError("2.0 experiment helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # A private imported instance: the existing 2.0 guards remain unchanged.
    module.EXPECTED_RELEASE = EXPECTED_RELEASE
    module.ALLOWED_CHANGES = dict(module.ALLOWED_CHANGES)
    module.ALLOWED_CHANGES["LOCALVERSION"] = ('"-Synthetica-2.0"', EXPECTED_LOCALVERSION)
    return module


s2x = load_s2x()


def check_inputs() -> None:
    s2x.check_inputs()
    s2x.verify_manager()
    if s2x.v3.digest(PATCH) != PATCH_SHA256:
        raise ValueError("3.0 Manager seccomp patch digest changed")


def verify_source(tree: Path, patched: bool) -> None:
    setuid = tree / "KernelSU-Next/kernel/hook/setuid_hook.c"
    root_profile = tree / "KernelSU-Next/kernel/policy/app_profile.c"
    expected = SETUID_PATCHED_SHA256 if patched else SETUID_SOURCE_SHA256
    if s2x.v3.digest(setuid) != expected:
        raise ValueError("unexpected Manager setuid-hook source")
    if s2x.v3.digest(root_profile) != ROOT_PROFILE_SHA256:
        raise ValueError("KernelSU root profile or seccomp escape behavior changed")


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    check_inputs()
    # Produces a disposable 2.0 experiment kit with all existing input checks.
    s2x.prepare(source, destination, baseline, "on")
    driver = destination / "scripts/build_chronicle_base.py"
    text = driver.read_text(encoding="utf-8")
    text = s2x.replace_once(text, "Experimental image compiled; verification and device tests still required",
                            "3.0-rc1 compiled; verification and device tests still required")
    driver.write_text(text, encoding="utf-8")
    print(f"Prepared disposable 3.0-rc1 kit: {destination}")


def prepare_tree(tree: Path) -> None:
    check_inputs()
    tree = s2x.ensure_disposable(tree)
    verify_source(tree, patched=False)
    s2x.prepare_tree(tree)
    subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=tree, check=True)
    subprocess.run(["git", "apply", str(PATCH)], cwd=tree, check=True)
    verify_source(tree, patched=True)
    print("Applied Manager-only seccomp preservation patch", flush=True)


def compare_tested_config(tested: Path, generated: str) -> dict[str, dict[str, str]]:
    if s2x.v3.digest(tested) != TESTED_CONFIG_SHA256:
        raise ValueError("tested 2.0 experiment config digest changed")
    old = s2x.v3.read_config(tested.read_text(encoding="utf-8"))
    new = s2x.v3.read_config(generated)
    changes = {key: {"tested_2.0_exp": old.get(key, "n"), "3.0_rc1": new.get(key, "n")}
               for key in sorted(old.keys() | new.keys())
               if old.get(key, "n") != new.get(key, "n")}
    expected = {"LOCALVERSION": {"tested_2.0_exp": '"-Synthetica-2.0-exp"',
                                 "3.0_rc1": EXPECTED_LOCALVERSION}}
    if changes != expected:
        bad = sorted(key for key in changes.keys() | expected.keys()
                     if changes.get(key) != expected.get(key))
        raise ValueError("3.0 config differs from the tested experiment beyond LOCALVERSION: " + ", ".join(bad[:20]))
    for key in ("SECCOMP", "SECCOMP_FILTER", "LRU_GEN", "LRU_GEN_ENABLED", "UCLAMP_TASK",
                "UCLAMP_TASK_GROUP", "SCHED_TUNE", "SCHED_WALT", "THERMAL", "KSU",
                "KSU_MANUAL_HOOK", "MODULE_SIG_FORCE", "MODVERSIONS"):
        if new.get(key) != "y":
            raise ValueError("required feature/security config missing: " + key)
    return changes


def check_config(baseline: Path, generated: Path, tested: Path, mglru: str) -> dict[str, object]:
    if mglru != "on":
        raise ValueError("3.0-rc1 requires MGLRU enabled by default")
    cfg = generated.read_text(encoding="utf-8")
    changes_from_2 = s2x.check_config(s2x.v3.verified_baseline(baseline), cfg, "on")
    changes_from_tested = compare_tested_config(tested, cfg)
    return {"changes_from_saved_2_0": changes_from_2,
            "changes_from_user_tested_experiment": changes_from_tested}


def verify_hook_object(out: Path) -> dict[str, str]:
    obj = out / "drivers/kernelsu/hook/setuid_hook.o"
    objdump = Path("/usr/bin/aarch64-linux-gnu-objdump")
    data = subprocess.run([str(objdump), "-t", str(obj)], check=True, text=True,
                          capture_output=True).stdout
    if not re.search(r"\bksu_handle_setresuid\s*$", data, re.MULTILINE):
        raise ValueError("compiled KernelSU setuid hook is missing")
    return {"sha256": s2x.v3.digest(obj), "symbol": "ksu_handle_setresuid",
            "note": "object and source verified statically; execution on device not tested"}


def finish(kit: Path, out: Path, baseline: Path, tested: Path, result: Path,
           toolchain_bin: Path, neutron_archive: Path) -> None:
    check_inputs()
    out = s2x.ensure_disposable(out)
    verify_source(out.parent, patched=True)
    changes = check_config(baseline, out / ".config", tested, "on")
    hook = verify_hook_object(out)
    # The inherited helper checks the compiler archive, embedded config, Manager
    # identity, signed same-build modules and image before producing evidence.
    s2x.finish(kit, out, baseline, result, "neutron", toolchain_bin, neutron_archive, "on")
    status_path = result / "STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update({
        "kind": "SYNTHETICA_3_RC1_COMPILED_ONLY_DO_NOT_FLASH",
        "candidate": "3.0-rc1; not the previously documented baseline 3.0 build",
        "tested_2_0_experiment_image_sha256": TESTED_IMAGE_SHA256,
        "tested_2_0_experiment_config_sha256": TESTED_CONFIG_SHA256,
        "tested_2_0_experiment_module_public_cert_sha256": TESTED_CERT_SHA256,
        "config_comparison": changes,
        "manager_seccomp_patch_sha256": PATCH_SHA256,
        "setuid_hook_object": hook,
        "seccomp_scope": "Preserve Manager's inherited filter on kernel 4.14; no UI spoof. Other root-allowed UIDs and the root escape retain their existing behavior.",
        "seccomp_on_device": "NOT TESTED; depends on ROM filter and actual calling thread",
        "camera_0_6x": "User reports freeze with 2.0 experiment; no camera change or fix in this candidate",
        "previous_2_0_experiment_user_report": "Booted; user reports MGLRU enabled=1 and features generally work except camera 0.6x",
        "device_tests_for_this_image": "NOT RUN",
        "module_public_cert_note": "A fresh build uses a fresh auto-generated public certificate; trust of installed ROM modules is unknown.",
    })
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    (result / "README-DO-NOT-FLASH.txt").write_text(
        "3.0-rc1 COMPILE EVIDENCE ONLY. No installer is included.\n"
        "The previous 2.0 experiment was user-reported to boot; this new image is NOT DEVICE TESTED.\n"
        "Manager seccomp/root, camera 0.6x, module trust and AVB are NOT verified.\n"
        "Fresh module signing public certificate only; no private key is exported.\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for name in ("source", "destination", "baseline"):
        prep.add_argument("--" + name, type=Path, required=True)
    tree = sub.add_parser("prepare-tree")
    tree.add_argument("--tree", type=Path, required=True)
    cfg = sub.add_parser("check-config")
    cfg.add_argument("--baseline", type=Path, required=True)
    cfg.add_argument("--generated", type=Path, required=True)
    cfg.add_argument("--mglru", default="on")
    cfg.add_argument("--tested-config", type=Path,
                     default=Path(os.environ["S3RC_TESTED_CONFIG"]) if os.environ.get("S3RC_TESTED_CONFIG") else None)
    done = sub.add_parser("finish")
    for name in ("kit", "out", "baseline", "tested-config", "result", "toolchain-bin", "neutron-archive"):
        done.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.destination, args.baseline)
    elif args.command == "prepare-tree":
        prepare_tree(args.tree)
    elif args.command == "check-config":
        if args.tested_config is None:
            raise ValueError("tested experiment config is required")
        check_inputs()
        print(json.dumps(check_config(args.baseline, args.generated, args.tested_config, args.mglru), indent=2))
    else:
        finish(args.kit, args.out, args.baseline, args.tested_config, args.result,
               args.toolchain_bin, args.neutron_archive)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f"3.0-rc1 build refused: {exc}", file=sys.stderr)
        sys.exit(1)
