#!/usr/bin/env python3
"""Build the UNSIGNED Synthetica Manager 6.0.0 from the standalone source tree.

Unlike 2.0..5.0.1 this builder does not download or patch the upstream Manager:
`synthetica-manager/` in this repository *is* the Manager source tree. Only the
signed root daemon (`libksud.so`, UAPI v4) is injected from the pinned donor,
because binaries are never committed. Signing is a separate local step with the
original Synthetica certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / "synthetica-manager"
# The donor only has to carry the pinned libksud.so, and the pinned 2.0 release
# does: same size and same SHA-256, checked in inject_daemon(). ci-stage/step1/
# manager-aligned.apk used to serve here, but that file is a build *output* that
# stopped being committed in 3ae2b8c, which silently broke this script. Do not
# point this back at ci-stage.
DONOR = ROOT / "release" / "Synthetica-2.0.apk"
DEFAULT_OUT = ROOT / "artifacts" / "unsigned" / "Manager-6.0.0-UNSIGNED.apk"

APP_ID = "net.ember.labs"
VERSION_NAME = "6.0.0"
VERSION_CODE = 70000
UAPI = 4

# Pinned UAPI-4 daemon (same bytes used by every Synthetica Manager since 2.0).
KSUD_SHA256 = "c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427"
KSUD_SIZE = 5518544

REQUIRED_FILES = (
    "settings.gradle.kts",
    "build.gradle.kts",
    "gradle.properties",
    "gradlew",
    "gradle/wrapper/gradle-wrapper.jar",
    "gradle/wrapper/gradle-wrapper.properties",
    "gradle/libs.versions.toml",
    "app/build.gradle.kts",
    "app/proguard-rules.pro",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/cpp/CMakeLists.txt",
    "app/src/main/cpp/jni.cc",
    "app/src/main/cpp/ksu.cc",
    "app/src/main/cpp/ksu.h",
    "app/src/main/cpp/uapi/supercall.h",
    "app/src/main/cpp/uapi/ksu.h",
    "app/src/main/assets/synthetica-control40.sh",
    "app/src/main/assets/synthetica-boost40.sh",
    "app/src/main/assets/synthetica-universal60.sh",
    "app/src/main/java/com/rifsxd/ksunext/Natives.kt",
    "app/src/main/java/com/rifsxd/ksunext/ui/theme/VisualStyles.kt",
    "app/src/main/java/com/rifsxd/ksunext/ui/theme/AppearanceControls.kt",
    "app/src/main/java/com/rifsxd/ksunext/ui/util/PixelRootActions40.kt",
    "app/src/main/res/values/strings_manager50.xml",
    "app/src/main/res/values-in-rID/strings_manager50.xml",
    "scripts/update_binary.sh",
    "scripts/updater_script.sh",
    "LICENSE",
)

FORBIDDEN_SUFFIXES = (".p12", ".jks", ".keystore", ".pem", ".key", ".der")


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(message)


def verify_tree() -> None:
    """Static gates so a broken or secret-bearing tree can never be compiled."""
    if not TREE.is_dir():
        fail(f"Standalone Manager tree missing: {TREE}")
    for relative in REQUIRED_FILES:
        if not (TREE / relative).is_file():
            fail(f"Standalone tree is missing {relative}")
    for path in TREE.rglob("*"):
        if path.is_symlink():
            fail(f"Symlink in the standalone tree is not supported: {path.relative_to(TREE)}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"Secret material must never be committed: {path.relative_to(TREE)}")

    root_gradle = (TREE / "build.gradle.kts").read_text(encoding="utf-8")
    for anchor in (
        f"val managerVersionCode by extra({VERSION_CODE})",
        f'val managerVersionName by extra("{VERSION_NAME}")',
    ):
        if anchor not in root_gradle:
            fail(f"Root build.gradle.kts lacks {anchor!r}")

    app_gradle = (TREE / "app/build.gradle.kts").read_text(encoding="utf-8")
    if f'applicationId = "{APP_ID}"' not in app_gradle:
        fail(f"applicationId must be {APP_ID}")
    for forbidden in ("apksign {", "signingConfig =", "storeFileProperty"):
        if forbidden in app_gradle:
            fail("The CI build must stay unsigned; signing happens locally with the original key")
    if "Synthetica-6.0.0-Standalone-$name.apk" not in app_gradle:
        fail("Unexpected APK output name in app/build.gradle.kts")

    supercall = (TREE / "app/src/main/cpp/uapi/supercall.h").read_text(encoding="utf-8")
    if "static const __u32 KERNEL_SU_UAPI_VERSION = 4;" not in supercall:
        fail("The packaged UAPI header is not version 4")

    manifest = (TREE / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    if "android.permission.INTERNET" not in manifest:
        fail("Unexpected manifest: the Manager needs INTERNET for module downloads")

    print(f"[verify] {APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI {UAPI}; standalone tree OK", flush=True)


def inject_daemon(app_main: Path) -> str:
    if not DONOR.is_file():
        fail(f"Missing pinned donor APK for the root daemon: {DONOR}")
    with zipfile.ZipFile(DONOR) as donor:
        daemon = donor.read("lib/arm64-v8a/libksud.so")
    if len(daemon) != KSUD_SIZE or hashlib.sha256(daemon).hexdigest() != KSUD_SHA256:
        fail("The pinned UAPI-4 root daemon has changed")
    target = app_main / "jniLibs" / "arm64-v8a" / "libksud.so"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(daemon)
    os.chmod(target, 0o755)
    print(f"[ksud] Injected {KSUD_SIZE} bytes -> jniLibs/arm64-v8a/libksud.so", flush=True)
    return KSUD_SHA256


def prepare_copy(work: Path) -> Path:
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(
        TREE,
        work,
        ignore=shutil.ignore_patterns(
            "build", ".gradle", ".kotlin", ".idea", ".cxx", "local.properties", "*.iml", "jniLibs",
        ),
    )
    os.chmod(work / "gradlew", 0o755)
    return work


def build_gradle(work: Path) -> Path:
    env = os.environ.copy()
    env.setdefault("GRADLE_OPTS", "-Xmx4g -Dfile.encoding=UTF-8")
    run([str(work / "gradlew"), ":app:assembleRelease", "--no-daemon", "--stacktrace"], cwd=work, env=env)
    apks = sorted((work / "app" / "build" / "outputs" / "apk" / "release").glob("*.apk"))
    if len(apks) != 1:
        fail(f"Expected exactly one release APK, found {[p.name for p in apks]}")
    return apks[0]


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    if sdk:
        candidates = sorted(Path(sdk, "build-tools").glob(f"*/{name}"), reverse=True)
        if candidates:
            return str(candidates[0])
    fail(f"{name} not found in PATH or ANDROID_SDK_ROOT/build-tools")


def zipalign_apk(built_apk: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    run([find_tool("zipalign"), "-p", "-f", "4", str(built_apk), str(output)])
    print(f"[done] Aligned unsigned APK -> {output} ({output.stat().st_size} bytes)", flush=True)
    print(f"[done] SHA-256 {sha256(output)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="run the static gates; build nothing")
    parser.add_argument("--workdir", type=Path, help="temporary copy of the source tree")
    parser.add_argument("--output", type=Path, help="aligned unsigned APK destination")
    args = parser.parse_args()

    verify_tree()
    if args.verify_only:
        print("[done] Static gates only; no APK built")
        return 0

    output = args.output or DEFAULT_OUT
    work = args.workdir or Path(tempfile.mkdtemp(prefix="synthetica-manager60-")) / "manager"
    prepared = prepare_copy(work)
    inject_daemon(prepared / "app" / "src" / "main")
    built = build_gradle(prepared)
    zipalign_apk(built, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
