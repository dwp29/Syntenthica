#!/usr/bin/env python3
"""
Synthetica 2.0 — Manager APK source builder (UAPI v4 + iOS Liquid Glass).
Builds Manager APK from pinned KernelSU-Next source tree (ea51427ff7, UAPI=4)
with Synthetica 2.0 package/branding, 3D Liquid Glass icon set, real-time GPU
BlurEffect theme, APK 1.16 menu layout, and UAPI=4 arm64 ksud payload.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERLAY_DIR = ROOT / "build-kit" / "ci" / "ksun-overlay"
BRAND_DIR = ROOT / "build-kit" / "ci" / "branding"
BASE_APK = ROOT / "build-kit" / "ci" / "rollercoaster" / "manager" / "base.apk"
WORK_DIR = Path(os.environ.get("SYNTHETICA_MANAGER_WORKDIR", "/tmp/synthetica-ksun-src"))
OUT_UNSIGNED = Path(
    os.environ.get(
        "SYNTHETICA_UNSIGNED_APK",
        str(ROOT / "artifacts" / "unsigned" / "manager-aligned.apk"),
    )
)

# Pinned KernelSU-Next UAPI v4 commit matching kernel-tree (c1e6f795, UAPI=4)
KSUN_REPO = "https://github.com/KernelSU-Next/KernelSU-Next.git"
KSUN_COMMIT = "ea51427ff700f73909e7e8c8717cc3241322ee1e"

APP_ID = "net.ember.labs"
APP_NAME = "Synthetica"
VER_NAME = "2.0"
VER_CODE = 10000


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def prepare_source() -> Path:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=WORK_DIR)
    run(["git", "remote", "add", "origin", KSUN_REPO], cwd=WORK_DIR)
    run(["git", "fetch", "--depth", "1", "origin", KSUN_COMMIT], cwd=WORK_DIR)
    run(["git", "checkout", "FETCH_HEAD"], cwd=WORK_DIR)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORK_DIR, text=True).strip()
    if actual != KSUN_COMMIT:
        raise RuntimeError(f"Unexpected KSUN commit: {actual} != {KSUN_COMMIT}")
    uapi_hdr = (WORK_DIR / "uapi" / "supercall.h").read_text(encoding="utf-8")
    if "KERNEL_SU_UAPI_VERSION = 4;" not in uapi_hdr:
        raise RuntimeError("Expected KERNEL_SU_UAPI_VERSION = 4 in uapi/supercall.h")
    return WORK_DIR


def extract_ksud_arm64(dst_jni_arm64: Path) -> None:
    if not BASE_APK.is_file():
        raise FileNotFoundError(f"Missing donor APK for ksud binary: {BASE_APK}")
    dst_jni_arm64.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BASE_APK, "r") as zf:
        data = zf.read("lib/arm64-v8a/libksud.so")
    out = dst_jni_arm64 / "libksud.so"
    out.write_bytes(data)
    os.chmod(out, 0o755)
    print(f"[ksud] Extracted arm64 libksud.so ({len(data)} bytes) -> {out}")


def patch_module_screen_glass(app_dir: Path) -> None:
    mod_kt = app_dir / "src" / "main" / "java" / "com" / "rifsxd" / "ksunext" / "ui" / "screen" / "Module.kt"
    txt = mod_kt.read_text(encoding="utf-8")
    if "import com.rifsxd.ksunext.ui.theme.iosGlass" not in txt:
        txt = txt.replace(
            "package com.rifsxd.ksunext.ui.screen\n",
            "package com.rifsxd.ksunext.ui.screen\n\nimport com.rifsxd.ksunext.ui.theme.iosGlass\n",
            1,
        )
    # Localize header title to match BottomBar ("Modules" / "Modul")
    txt = txt.replace(
        "text = stringResource(R.string.module),\n                        style = MaterialTheme.typography.titleLarge,\n                        fontWeight = FontWeight.Black,",
        "text = stringResource(R.string.ios_nav_modules),\n                        style = MaterialTheme.typography.titleLarge,\n                        fontWeight = FontWeight.Bold,",
        1,
    )
    # Upgrade ModuleItem Card to real GPU-blurred Liquid Glass card
    old_card = """    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .combinedClickable("""
    new_card = """    Card(
        colors = CardDefaults.cardColors(containerColor = Color.Transparent),
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(shape = MaterialTheme.shapes.large)
            .combinedClickable("""
    if old_card not in txt:
        raise RuntimeError("Expected ModuleItem Card block not found in Module.kt")
    txt = txt.replace(old_card, new_card, 1)
    txt = txt.replace('getBoolean("amoled_mode", false)', 'getBoolean("enable_amoled", false)')
    mod_kt.write_text(txt, encoding="utf-8")


def apply_synthetica_patch(src: Path) -> None:
    mgr = src / "manager"
    app = mgr / "app"

    # 1. Root manager/build.gradle.kts: arm64-v8a only + fixed version 2.0 (10000)
    root_gradle = mgr / "build.gradle.kts"
    rg = root_gradle.read_text(encoding="utf-8")
    rg = rg.replace(
        'abiFilters("arm64-v8a", "x86_64", "riscv64")',
        'abiFilters("arm64-v8a")',
    )
    rg = rg.replace(
        'abiFilters += listOf("arm64-v8a", "x86_64", "riscv64")',
        'abiFilters += listOf("arm64-v8a")',
    )
    rg = re.sub(
        r"val managerVersionCode by extra\(getVersionCode\(\)\)",
        f"val managerVersionCode by extra({VER_CODE})",
        rg,
    )
    rg = re.sub(
        r"val managerVersionName by extra\(getVersionName\(\)\)",
        f'val managerVersionName by extra("{VER_NAME}")',
        rg,
    )
    root_gradle.write_text(rg, encoding="utf-8")

    # 2. app/build.gradle.kts: applicationId = net.ember.labs, unsigned release output
    app_gradle = app / "build.gradle.kts"
    ag = app_gradle.read_text(encoding="utf-8")
    ag = re.sub(r"\s*alias\(libs\.plugins\.lsplugin\.apksign\)\n", "\n", ag)
    ag = re.sub(r"apksign\s*\{[^}]*\}\s*", "", ag, flags=re.S)
    ag = ag.replace(
        'namespace = "com.rifsxd.ksunext"',
        'namespace = "com.rifsxd.ksunext"\n    defaultConfig {\n        applicationId = "net.ember.labs"\n    }',
        1,
    )
    ag = ag.replace(
        'signingConfig = signingConfigs.getByName("debug")',
        "// unsigned release APK; signed strictly locally with Synthetica 2.0 certificate",
    )
    ag = re.sub(
        r'output\.outputFileName\s*=\s*"KernelSU_Next_[^"]*"',
        'output.outputFileName = "Synthetica-2.0-$name.apk"',
        ag,
    )
    app_gradle.write_text(ag, encoding="utf-8")

    # 3. App name in values/strings.xml -> Synthetica
    strings_xml = app / "src" / "main" / "res" / "values" / "strings.xml"
    sx = strings_xml.read_text(encoding="utf-8")
    sx, n_rep = re.subn(
        r'<string name="app_name"[^>]*>.*?</string>',
        f'<string name="app_name">{APP_NAME}</string>',
        sx,
    )
    if n_rep == 0:
        raise RuntimeError("Failed to patch app_name in strings.xml")
    strings_xml.write_text(sx, encoding="utf-8")

    # Also patch app_name in any translated strings.xml that overrides app_name
    for loc_strings in (app / "src" / "main" / "res").glob("values-*/strings.xml"):
        lsx = loc_strings.read_text(encoding="utf-8")
        if '<string name="app_name"' in lsx:
            lsx = re.sub(
                r'<string name="app_name"[^>]*>.*?</string>',
                f'<string name="app_name">{APP_NAME}</string>',
                lsx,
            )
            loc_strings.write_text(lsx, encoding="utf-8")

    # 4. Copy full Synthetica 2.0 iOS Liquid Glass Kotlin & XML resource overlays
    shutil.copytree(OVERLAY_DIR / "java", app / "src" / "main" / "java", dirs_exist_ok=True)
    shutil.copytree(OVERLAY_DIR / "res", app / "src" / "main" / "res", dirs_exist_ok=True)

    # 5. Upgrade Module.kt cards to real GPU-blurred Liquid Glass
    patch_module_screen_glass(app)

    # 6. Install redesigned 3D Liquid Glass launcher icons & in-app emblem
    res_dir = app / "src" / "main" / "res"
    densities = ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")
    for d in densities:
        mip = res_dir / f"mipmap-{d}"
        mip.mkdir(parents=True, exist_ok=True)
        for stale in list(mip.glob("ic_launcher*")):
            stale.unlink()
        shutil.copy2(BRAND_DIR / f"ic_launcher-{d}.png", mip / "ic_launcher.png")
        shutil.copy2(BRAND_DIR / f"ic_launcher-{d}.png", mip / "ic_launcher_round.png")
        shutil.copy2(BRAND_DIR / f"ic_foreground-{d}.png", mip / "ic_launcher_foreground.png")
        shutil.copy2(BRAND_DIR / f"ic_background-{d}.png", mip / "ic_launcher_background.png")

    mono_map = {
        "mdpi": "ic_mono-24.png",
        "hdpi": "ic_mono-48.png",
        "xhdpi": "ic_mono-48.png",
        "xxhdpi": "ic_mono-96.png",
        "xxxhdpi": "ic_mono-192.png",
    }
    for d, fname in mono_map.items():
        drw = res_dir / f"drawable-{d}"
        drw.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BRAND_DIR / fname, drw / "ic_launcher_monochrome.png")

    nodpi = res_dir / "drawable-nodpi"
    nodpi.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND_DIR / "ic_synthetica_emblem.png", nodpi / "ic_synthetica_emblem.png")

    # Remove upstream vector foreground/monochrome drawables that could shadow mipmaps
    for old_vec in (
        res_dir / "drawable" / "ic_launcher_foreground.xml",
        res_dir / "drawable" / "ic_launcher_monochrome.xml",
    ):
        if old_vec.exists():
            old_vec.unlink()

    anydpi = res_dir / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    adaptive_xml = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
    <monochrome android:drawable="@drawable/ic_launcher_monochrome"/>
</adaptive-icon>
"""
    (anydpi / "ic_launcher.xml").write_text(adaptive_xml, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive_xml, encoding="utf-8")

    # 7. Inject UAPI=4 arm64 ksud payload into jniLibs/arm64-v8a/libksud.so
    extract_ksud_arm64(app / "src" / "main" / "jniLibs" / "arm64-v8a")


def build_gradle(src: Path) -> Path:
    mgr = src / "manager"
    gradlew = mgr / "gradlew"
    os.chmod(gradlew, 0o755)
    env = os.environ.copy()
    env.setdefault("GRADLE_OPTS", "-Xmx4g -Dfile.encoding=UTF-8")
    run(
        [
            str(gradlew),
            ":app:assembleRelease",
            "--no-daemon",
            "--stacktrace",
        ],
        cwd=mgr,
        env=env,
    )
    apks = list((mgr / "app" / "build" / "outputs" / "apk" / "release").glob("*.apk"))
    if not apks:
        raise FileNotFoundError("No release APK produced by Gradle")
    return apks[0]


def zipalign_apk(built_apk: Path) -> None:
    OUT_UNSIGNED.parent.mkdir(parents=True, exist_ok=True)
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    zipalign = shutil.which("zipalign")
    if not zipalign and sdk:
        candidates = sorted(Path(sdk, "build-tools").glob("*/zipalign"), reverse=True)
        if candidates:
            zipalign = str(candidates[0])
    if not zipalign:
        raise FileNotFoundError("zipalign not found in PATH or ANDROID_SDK_ROOT/build-tools")
    if OUT_UNSIGNED.exists():
        OUT_UNSIGNED.unlink()
    run([zipalign, "-p", "-f", "-v", "4", str(built_apk), str(OUT_UNSIGNED)])
    print(f"[done] Aligned unsigned APK ready -> {OUT_UNSIGNED} ({OUT_UNSIGNED.stat().st_size} bytes)")


def main() -> int:
    src = prepare_source()
    apply_synthetica_patch(src)
    built_apk = build_gradle(src)
    zipalign_apk(built_apk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
