#!/usr/bin/env python3
"""Build the 2.1 Cyberbrutalist Manager, unsigned, against the proven UAPI-v4 base.

The Cyberbrutal UI originates from the user's 2.1 source archive.  The archive's
original builder targets UAPI v6; Synthetica 2.0 kernels use v4, so this wrapper
applies the UI to the exact v4 revision used by the working 2.0 APK.  The package
is unsigned here: the existing release identity must be applied locally afterwards.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build-kit" / "scripts"))
import build_manager_source as base  # reuse the verified pin, ksud donor, Gradle and zipalign


def load_ui_patcher():
    path = ROOT / "build-kit" / "ci" / "build_manager_cyberbrutal_patch.py"
    spec = importlib.util.spec_from_file_location("synthetica_cyberbrutal_patch", path)
    assert spec is not None and spec.loader is not None
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    return patcher


def replace_exact_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one anchor for {label}, found {count}")
    return text.replace(old, new, 1)


def apply_version_and_architecture(src: Path) -> None:
    gradle = src / "manager" / "build.gradle.kts"
    data = gradle.read_text(encoding="utf-8")
    for old, new, label in (
        ('abiFilters("arm64-v8a", "x86_64", "riscv64")', 'abiFilters("arm64-v8a")', "cmake ABIs"),
        ('abiFilters += listOf("arm64-v8a", "x86_64", "riscv64")', 'abiFilters += listOf("arm64-v8a")', "APK ABIs"),
        ('val managerVersionCode by extra(getVersionCode())', 'val managerVersionCode by extra(30004)', "version code"),
        ('val managerVersionName by extra(getVersionName())', 'val managerVersionName by extra("2.1.2")', "version name"),
    ):
        data = replace_exact_once(data, old, new, label)
    gradle.write_text(data, encoding="utf-8")

    app_gradle = src / "manager/app/build.gradle.kts"
    app = app_gradle.read_text(encoding="utf-8")
    if 'applicationId = "net.ember.labs"' not in app:
        raise RuntimeError("Manager package ID not set correctly")
    if "apksign {" in app or "signingConfig =" in app:
        raise RuntimeError("Release signing must be strictly local, not in CI")


def patch_localized_labels(src: Path) -> None:
    res = src / "manager/app/src/main/res"
    for strings in res.glob("values-*/strings.xml"):
        text = strings.read_text(encoding="utf-8")
        text = re.sub(r'(<string name="app_name"[^>]*>)[^<]*(</string>)', r'\g<1>Synthetica\g<2>', text)
        strings.write_text(text, encoding="utf-8")


def prepare_tree(src: Path) -> None:
    header = (src / "uapi/supercall.h").read_text(encoding="utf-8")
    if "KERNEL_SU_UAPI_VERSION = 4;" not in header:
        raise RuntimeError("The Manager must be built with KernelSU UAPI 4")
    patcher = load_ui_patcher()
    patcher.apply_overlays(src)
    patcher.patch_main_activity(src)
    patcher.patch_home_screen(src)
    patcher.patch_module_screen(src)
    patcher.patch_superuser_screen(src)
    patcher.patch_settings_and_customization(src)
    patcher.apply_package_label_and_resources(src)
    patcher.sanity_check_kotlin_sources(src)
    apply_version_and_architecture(src)
    patch_localized_labels(src)
    asset_dir = ROOT / "build-kit/ci/ksun-cyberbrutal/assets"
    target_dir = src / "manager/app/src/main/assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in ("synthetica-control.sh", "synthetica-boost-compat.sh"):
        shutil.copy2(asset_dir / name, target_dir / name)
    base.extract_ksud_arm64(src / "manager/app/src/main/jniLibs/arm64-v8a")
    print("[compat] Native source UAPI 4; 2.1.2 Cyberbrutal UI; package net.ember.labs; versionCode 30004", flush=True)


def main() -> int:
    # Local dry-run accepts a previously downloaded copy only for patch verification.
    if "--verify-patches-only" in sys.argv:
        local = Path(os.environ["SYNTHETICA_DRY_SOURCE"])
        target = Path(os.environ.get("SYNTHETICA_MANAGER_WORKDIR", "/tmp/synthetica21-ui-test"))
        if target.resolve() == local.resolve() or target.resolve() in local.resolve().parents:
            raise RuntimeError("Dry-run target must differ from the source directory")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(local, target)
        prepare_tree(target)
        print("[done] Patch-only verification succeeded; no APK built")
        return 0
    src = base.prepare_source()
    prepare_tree(src)
    built = base.build_gradle(src)
    base.zipalign_apk(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
