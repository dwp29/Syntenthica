#!/usr/bin/env python3
"""Build guard for Synthetica 3.0: the 2.0 recipe, without a flashable package.

The existing source pins and builder are copied, never edited in place. The
only source change in the disposable kernel tree fixes embedded IKCONFIG; the
only permitted Kconfig difference from the saved 2.0 build is LOCALVERSION.
These checks cannot prove boot, runtime features, module ABI, or module trust.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

V2_CONFIG_SHA256 = "248af9218b5ed9dd82202956d99991f97428c3010565a810eac3c9e6f71ff33b"
V2_IMAGE_SHA256 = "58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff"
SOURCE_MAKEFILE_SHA256 = "d237ad471f5ea1c1009493fa79227e3b3ba461e6eacd6fd1294567fcb9ce8913"
SOURCE = "Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795b557b7bf92220c91f05a42b456de7a74"
EXPECTED_RELEASE = "4.14.357-openela-Synthetica-3.0"
MIN_IMAGE_BYTES = 8 * 1024 * 1024
MAX_RAW_IMAGE = 128 * 1024 * 1024
PINNED_INPUTS = {
    "scripts/build_chronicle_base.py": "c92f32b1792d999008de18bd2d91418472219349798f0d546b7ef223e3747cdc",
    "ci/SOURCES_CHRONICLE_BASE.json": "9a09ae658bbc6e5f48f5404f56b108380c5659aba2786c108d87be253fb13912",
    "ci/rollercoaster/build-rollercoaster.sh": "033ea7e5789b129ac1226837a897c6d8735d8e15dc14fbb914b83dddd6c53715",
    "ci/rollercoaster/profiles/synthetica.config": "b2680e2cd32c76a2c64849a8a635d48c6a2a6df2699a7f75bde09c8efa3ec0e3",
    "ci/rollercoaster/profiles/00-common.config": "9bbcc9ddd63d9cc4aacc06b8a0dfd808f2888be9d6d59d9c93b286b8a4ab945e",
    "ci/rollercoaster/patches/kernelsu-1.0.0.patch": "d0b6cf8ffb87a7e65c08595d745b25896fa6078725d35422fbe451a4c662d622",
    "ci/rollercoaster/patches/aw8624-drop-timed_output.patch": "76bd2c897d0de24945d9b025dfcadaed7d0b5a9aad0fc91e82deff8a488f3795",
    "ci/rollercoaster/patches/apk-sign-accept-v3.patch": "042eff4b5275cad60ccc03ee8ff0bfadf05ea139957f2daa415be87e143ffe1f",
    "ci/rollercoaster/anykernel/ksud": "52ba3da465459bfbac98dd25c53f8d31f93ee5a8ee89d84f67a28fe0d18cdef2",
    "ci/rollercoaster/VERSION": "ac7c22c2fe44288eeef1c46a8ad6d22033656bd3aea3864ca36d09bb0126891b",
    "artifacts/manager/MANAGER.json": "4f5131b5dd6655c781482d67cb613949cda220030534c5d72ee8dafda0e7fa69",
}
REQUIRED_Y = (
    "IKCONFIG", "IKCONFIG_PROC", "MODULES", "MODVERSIONS", "MODULE_SIG",
    "MODULE_SIG_FORCE", "MODULE_SIG_ALL", "SECURITY", "SECURITY_SELINUX",
    "DM_VERITY", "KSU", "KSU_MANUAL_HOOK", "KSU_SUSFS", "NOMOUNT",
)
FORBIDDEN_Y = ("MODULE_FORCE_LOAD", "SECURITY_SELINUX_DISABLE")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_config(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        enabled = re.fullmatch(r"CONFIG_([A-Za-z0-9_]+)=(.*)", line)
        disabled = re.fullmatch(r"# CONFIG_([A-Za-z0-9_]+) is not set", line)
        if enabled:
            key, value = enabled.groups()
        elif disabled:
            key, value = disabled.group(1), "n"
        else:
            if line.startswith("CONFIG_") or line.startswith("# CONFIG_"):
                raise ValueError(f"invalid config line: {line[:120]}")
            continue
        if key in result:
            raise ValueError(f"duplicate config symbol: {key}")
        result[key] = value
    return result


def verified_baseline(path: Path) -> str:
    if digest(path) != V2_CONFIG_SHA256:
        raise ValueError("baseline does not match the saved Synthetica 2.0 build config")
    return path.read_text(encoding="utf-8")


def check_config(baseline: str, generated: str) -> dict[str, dict[str, str]]:
    old, new = read_config(baseline), read_config(generated)
    if old.get("LOCALVERSION") != '"-Synthetica-2.0"':
        raise ValueError("unexpected 2.0 LOCALVERSION")
    if new.get("LOCALVERSION") != '"-Synthetica-3.0"':
        raise ValueError("3.0 LOCALVERSION missing or incorrect")
    for symbol in REQUIRED_Y:
        if old.get(symbol) != "y" or new.get(symbol) != "y":
            raise ValueError(f"required 2.0 feature/security config is not y: {symbol}")
    for symbol in FORBIDDEN_Y:
        if old.get(symbol, "n") != "n" or new.get(symbol, "n") != "n":
            raise ValueError(f"unsafe config is enabled: {symbol}")
    changed = {
        symbol: {"2.0": old.get(symbol, "n"), "3.0": new.get(symbol, "n")}
        for symbol in sorted(set(old) | set(new))
        if old.get(symbol, "n") != new.get(symbol, "n")
    }
    unexpected = sorted(set(changed) - {"LOCALVERSION"})
    if unexpected:
        examples = ", ".join(f"{s}: {changed[s]['2.0']} -> {changed[s]['3.0']}" for s in unexpected[:12])
        raise ValueError(f"config differs from 2.0 beyond LOCALVERSION: {examples}")
    return changed


def fix_ikconfig(tree: Path) -> None:
    """Embed the generated .config instead of the pinned tree's stock_defconfig."""
    makefile = tree / "kernel/Makefile"
    if digest(makefile) != SOURCE_MAKEFILE_SHA256:
        raise ValueError("kernel/Makefile differs from the pinned 2.0 source")
    text = makefile.read_text(encoding="utf-8")
    before = "$(obj)/config_data.gz: $(KBUILD_SRC)/arch/arm64/configs/vendor/stock_defconfig FORCE"
    after = "$(obj)/config_data.gz: $(KCONFIG_CONFIG) FORCE"
    if text.count(before) != 1 or after in text:
        raise ValueError("unexpected IKCONFIG Makefile rule")
    makefile.write_text(text.replace(before, after), encoding="utf-8")
    print("IKCONFIG source corrected in disposable tree")


def verify_embedded_config(raw_image: bytes, expected_config: bytes) -> None:
    start, end = b"IKCFG_ST", b"IKCFG_ED"
    if raw_image.count(start) != 1 or raw_image.count(end) != 1:
        raise ValueError("image has missing or ambiguous IKCONFIG markers")
    a = raw_image.index(start) + len(start)
    b = raw_image.index(end)
    if b <= a or b - a > 4 * 1024 * 1024:
        raise ValueError("invalid embedded IKCONFIG size")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw_image[a:b])) as config_gzip:
            embedded = config_gzip.read(len(expected_config) + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError("embedded IKCONFIG is not valid gzip") from exc
    if embedded != expected_config:
        raise ValueError("embedded IKCONFIG differs from generated .config")


def verify_image(raw: bytes, config: bytes, manager: dict[str, object]) -> None:
    match = re.search(rb"Linux version ([^\s]+)", raw)
    if not match or match.group(1).decode("ascii", "replace") != EXPECTED_RELEASE:
        raise ValueError("image release is not Synthetica 3.0")
    verify_embedded_config(raw, config)
    # This checks that the pinned identity was linked in, not that root works.
    for key in ("package", "cert_sha256"):
        value = manager.get(key)
        if not isinstance(value, str) or not value or value.encode("ascii") not in raw:
            raise ValueError(f"pinned manager {key} not found in image")
    if b"KernelSU" not in raw:
        raise ValueError("KernelSU identity not found in image")


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError("refusing to overwrite an existing build kit")
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("disposable build kit must be outside the original build kit")
    verified_baseline(baseline)
    if digest(source.parent / "artifacts/Image.gz") != V2_IMAGE_SHA256:
        raise ValueError("reference image does not match the archived 2.0 build")
    for name, expected in PINNED_INPUTS.items():
        if digest(source / name) != expected:
            raise ValueError(f"2.0 input changed; refusing to build: {name}")

    # Copy only inputs used by the 2.0 kernel build, never prior output or keys.
    # The port-only bypass patch is deliberately unavailable in this copy.
    (destination / "scripts").mkdir(parents=True)
    (destination / "ci").mkdir()
    shutil.copy2(source / "scripts/build_chronicle_base.py", destination / "scripts/build_chronicle_base.py")
    shutil.copy2(source / "ci/SOURCES_CHRONICLE_BASE.json", destination / "ci/SOURCES_CHRONICLE_BASE.json")
    shutil.copytree(source / "ci/rollercoaster", destination / "ci/rollercoaster",
                    ignore=shutil.ignore_patterns("artifacts", ".git", "__pycache__", ".work-*",
                                                  "secretkey", "*.pem", "*.der", "*.key", "*.pk8",
                                                  "*.p12", "*.jks", "*.keystore",
                                                  "port-allow-foreign-vermagic.patch"))
    manager = destination / "artifacts/manager/MANAGER.json"
    manager.parent.mkdir(parents=True)
    shutil.copy2(source / "artifacts/manager/MANAGER.json", manager)

    builder = destination / "ci/rollercoaster/build-rollercoaster.sh"
    text = builder.read_text(encoding="utf-8")
    anchor = 'make "${MO[@]}" olddefconfig >/dev/null\n'
    marker = "# --- kemas AnyKernel3 "
    if text.count(anchor) != 1 or text.count(marker) != 1:
        raise ValueError("unexpected 2.0 builder layout")
    guard = '''\n# 3.0 must keep the whole 2.0 config and must not apply the port bypass.
[ "$PROFILE" = synthetica ] || { echo "wrong profile"; exit 1; }
: "${S3_HELPER:?helper path required}" "${S3_BASELINE:?baseline config required}"
if grep -Fq 'diterima (Rollercoaster-Port)' "$TREE/kernel/module.c"; then
  echo "foreign vermagic bypass found; build refused"; exit 1
fi
python3 "$S3_HELPER" check-config --baseline "$S3_BASELINE" --generated "$OUT/.config"
'''
    text = text.replace(anchor, anchor + guard)
    text = text[:text.index(marker)] + '\necho "Image only: no installer or flashable package"\nexit 0\n'
    builder.write_text(text, encoding="utf-8")

    driver = destination / "scripts/build_chronicle_base.py"
    text = driver.read_text(encoding="utf-8")
    anchor = '    tree = extract(archive, WORK / "tree")\n'
    status_start, main_start = "    status = {\n", '\n\nif __name__ == "__main__":'
    if text.count(anchor) != 1 or text.count(status_start) != 1 or text.count(main_start) != 1:
        raise ValueError("unexpected 2.0 driver layout")
    hook = '''    # Enforce the archive pin even if Python assertions are disabled, and do
    # not reuse an existing source/output tree from a prior build.
    if sha_file(PIN_FILE) != "9a09ae658bbc6e5f48f5404f56b108380c5659aba2786c108d87be253fb13912":
        raise ValueError("source pin changed after preparation")
    pin = json.loads(PIN_FILE.read_text())
    if measured["archive_sha256"] != pin["archive_sha256"] or measured["archive_bytes"] != pin["archive_bytes"]:
        raise ValueError("kernel source archive does not match the pin")
    if (WORK / "tree").exists():
        raise ValueError("refusing to reuse an existing kernel tree")
    tree = extract(archive, WORK / "tree")
    subprocess.run([sys.executable, os.environ["S3_HELPER"],
                    "fix-ikconfig", "--tree", str(tree)], check=True)
'''
    text = text.replace(anchor, hook)
    # The 2.0 status refers to its installer and historical tests. Neither is
    # evidence for this build; finish() creates a truthful status instead.
    text = text[:text.index(status_start)] + '    say("Image compiled; 3.0 verification still required")\n' + text[text.index(main_start):]
    driver.write_text(text, encoding="utf-8")
    print(f"Prepared isolated 2.0-based 3.0 build kit: {destination}")


def finish(kit: Path, out: Path, baseline: Path, reference_image: Path, result: Path) -> None:
    baseline_text = verified_baseline(baseline)
    if digest(reference_image) != V2_IMAGE_SHA256:
        raise ValueError("reference image does not match the archived 2.0 build")
    cfg = (out / ".config").read_bytes()
    if cfg != (kit / "artifacts/generated.config.txt").read_bytes():
        raise ValueError("collected config differs from compiler output")
    changes = check_config(baseline_text, cfg.decode("utf-8"))
    image = kit / "artifacts/Image.gz"
    if image.stat().st_size <= MIN_IMAGE_BYTES:
        raise ValueError("compiled Image.gz is unexpectedly small")
    try:
        with gzip.open(image, "rb") as f:
            raw = f.read(MAX_RAW_IMAGE + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError("compiled Image.gz is not valid gzip") from exc
    if len(raw) > MAX_RAW_IMAGE:
        raise ValueError("uncompressed image exceeds safety limit")
    manager_file = kit / "artifacts/manager/MANAGER.json"
    if digest(manager_file) != PINNED_INPUTS["artifacts/manager/MANAGER.json"]:
        raise ValueError("manager identity changed after preparation")
    manager = json.loads(manager_file.read_text(encoding="utf-8"))
    verify_image(raw, cfg, manager)

    symvers = out / "Module.symvers"
    matches = re.findall(r"(?m)^(0x[0-9a-fA-F]{8})\s+module_layout\s+", symvers.read_text(encoding="utf-8"))
    if len(matches) != 1 or int(matches[0], 16) == 0:
        raise ValueError("Module.symvers does not have a unique, non-zero module_layout CRC")
    system_map = out / "System.map"
    if not system_map.is_file() or system_map.stat().st_size == 0:
        raise ValueError("missing System.map")

    # Copy only the public certificate, after parsing it and checking that the
    # identical DER certificate is embedded in the image. Never export the key.
    cert = out / "certs/signing_key.x509"
    parsed = subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(cert), "-outform", "DER"],
                            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    if not parsed or parsed != cert.read_bytes() or parsed not in raw:
        raise ValueError("public module certificate is missing from the image")
    try:
        with gzip.open(reference_image, "rb") as f:
            old_raw = f.read(MAX_RAW_IMAGE + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError("reference 2.0 Image.gz is not valid gzip") from exc
    if len(old_raw) > MAX_RAW_IMAGE:
        raise ValueError("reference 2.0 image exceeds safety limit")
    cert_also_in_v2 = parsed in old_raw
    if result.exists() or result.is_symlink():
        raise ValueError("refusing to overwrite an existing result directory")
    result.mkdir(parents=True)
    files = {
        "DO-NOT-FLASH-Synthetica-3.0-Image.gz": image,
        "generated.config.txt": out / ".config",
        "Module.symvers.txt": symvers,
        "System.map.txt": system_map,
        "kernel-module-public-cert.x509": cert,
    }
    for name, path in files.items():
        shutil.copyfile(path, result / name)
    status = {
        "status": "COMPILED_ONLY_DO_NOT_FLASH",
        "device_target": "joyeuse / miatoll, HOS4",
        "prior_test": "User reports Synthetica 2.0 booted with HOS4; tested image hash was not independently confirmed.",
        "source": SOURCE,
        "reference_2_0_image_sha256": V2_IMAGE_SHA256,
        "reference_2_0_generated_config_sha256": V2_CONFIG_SHA256,
        "uname_release": EXPECTED_RELEASE,
        "config_changes": changes,
        "embedded_config_matches_generated": True,
        "module_layout_crc": matches[0].lower(),
        "module_public_cert_embedded_in_image": True,
        "same_public_certificate_found_in_2_0_image": cert_also_in_v2,
        "pinned_manager_identity_strings_found": True,
        "checks_not_proofs": [
            "A certificate byte comparison does not establish which ROM module signers are trusted.",
            "Matching config and linked identity strings do not prove root or runtime features.",
            "Kernel release changed; vendor module vermagic, CRCs, and signer trust are not verified.",
            "No 3.0 physical boot, hardware functionality, AVB, or SELinux runtime test was performed.",
        ],
        "private_signing_key_exported": False,
        "rom_or_device_modified": False,
        "output_sha256": {name: digest(result / name) for name in files},
    }
    (result / "STATUS.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    (result / "README-DO-NOT-FLASH.txt").write_text(
        "DO NOT FLASH. This is an untested kernel image, not an installer or boot image.\n"
        "The 2.0 config is retained except LOCALVERSION and IKCONFIG metadata is fixed.\n"
        "Vendor-module ABI/signatures, physical boot, and runtime features are unverified.\n"
        "Module signature enforcement and MODVERSIONS remain enabled; no bypass is applied.\n",
        encoding="utf-8",
    )
    names = sorted([*files, "STATUS.json", "README-DO-NOT-FLASH.txt"])
    (result / "SHA256SUMS.txt").write_text(
        "".join(f"{digest(result / name)}  {name}\n" for name in names), encoding="utf-8")
    print(json.dumps(status, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--destination", type=Path, required=True)
    prep.add_argument("--baseline", type=Path, required=True)
    check = sub.add_parser("check-config")
    check.add_argument("--baseline", type=Path, required=True)
    check.add_argument("--generated", type=Path, required=True)
    fix = sub.add_parser("fix-ikconfig")
    fix.add_argument("--tree", type=Path, required=True)
    final = sub.add_parser("finish")
    final.add_argument("--kit", type=Path, required=True)
    final.add_argument("--out", type=Path, required=True)
    final.add_argument("--baseline", type=Path, required=True)
    final.add_argument("--reference-image", type=Path, required=True)
    final.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.destination, args.baseline)
    elif args.command == "check-config":
        changes = check_config(verified_baseline(args.baseline), args.generated.read_text(encoding="utf-8"))
        print("2.0 config preserved except LOCALVERSION:", changes)
    elif args.command == "fix-ikconfig":
        fix_ikconfig(args.tree)
    else:
        finish(args.kit, args.out, args.baseline, args.reference_image, args.result)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"Synthetica 3.0 build refused: {exc}", file=sys.stderr)
        sys.exit(1)
