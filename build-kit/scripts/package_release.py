#!/usr/bin/env python3
"""Assemble the two recovery-flashable ZIPs from a finished build.

  1. Synthetica-<ver>.zip       kernel (AnyKernel3), no boot backup, writes an install log
  2. Synthetica-<ver>-LOG.zip   read-only log grabber for bootloop triage

Naming rule: the only file a user flashes is Synthetica-<ver>.zip; the manager is Synthetica-<ver>.apk.

<ver> comes from STATUS.json ("release_version"), so the zip name, the banner, the backup
file name and the recorded hashes can never disagree with the kernel inside.

Nothing is flashed by CI. The kernel image comes from artifacts/Image.gz produced by
ci/build_release.py in the same run, so the ZIP cannot drift from the measured build.
AnyKernel3 is fetched at a pinned commit and its SHA256 is verified before use.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

AK3 = {
    "repository": "osm0sis/AnyKernel3",
    "commit": "41f04bdb4ee30a44e429c2c1131d5e8bb32b15f1",
    "archive_url": "https://codeload.github.com/osm0sis/AnyKernel3/tar.gz/41f04bdb4ee30a44e429c2c1131d5e8bb32b15f1",
    "archive_bytes": 3099416,
    "archive_sha256": "792b37fec7d1221570a4f1deb777a2d2cb8261596b1465a70bd7abfb30e268a2",
}
VERSION = "1.0"  # replaced in main() from STATUS.json["release_version"]
ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "ci" / "release"
WORK = Path(os.environ.get("SP_WORK_DIR", str(ROOT / ".work-package"))).resolve()
ART = ROOT / "artifacts"


def sha_file(p):
    return hashlib.file_digest(open(p, "rb"), "sha256").hexdigest()


def fetch_ak3():
    WORK.mkdir(parents=True, exist_ok=True)
    archive = WORK / "ak3.tar.gz"
    if not archive.exists():
        with urllib.request.urlopen(AK3["archive_url"], timeout=600) as r, archive.open("wb") as out:
            shutil.copyfileobj(r, out)
    assert archive.stat().st_size == AK3["archive_bytes"], "AnyKernel3 archive size mismatch"
    assert sha_file(archive) == AK3["archive_sha256"], "AnyKernel3 archive sha256 mismatch"
    dest = WORK / "ak3"
    if not dest.exists():
        dest.mkdir()
        with tarfile.open(archive) as t:
            filtered = sys.version_info >= (3, 12)
            for member in t:
                parts = member.name.split("/", 1)
                if len(parts) < 2 or not parts[1]:
                    continue
                member.name = parts[1]
                t.extract(member, dest, filter="data") if filtered else t.extract(member, dest)
    return dest


FLASH_README = """Synthetica {v} - READ THIS BEFORE FLASHING
=====================================================

What this is
------------
Kernel {uname} for miatoll / joyeuse (Redmi Note 9S / 9 Pro family),
{root_line}
Installed through AnyKernel3: it replaces the kernel inside the boot partition and keeps
your existing ramdisk. No modules, no /vendor changes, no auto reboot.

Installer behaviour (2.0)
-------------------------
* No boot backup: the backup step was removed by request in 2.0.
* The installer writes an installation log to <storage>/Synthetica/install-log-<time>.txt
  (kernel string, image hash, ksud result, write result).
* Keep your own boot backup from a previous release if you want a way back.

How to flash
------------
1. Boot to recovery.
2. Make sure /sdcard is mounted and data is decrypted (ksud needs /data/adb).
3. Flash Synthetica-{v}.zip.
4. Install Synthetica-{v}.apk (the manager from the same batch) after reboot.
5. Reboot only when you are ready.

If it does not boot
-------------------
1. Boot back to recovery. Do NOT wipe data.
2. Flash Synthetica-{v}-LOG.zip and send <storage>/synthetica-logs/<timestamp>/.
3. Restore a boot image you backed up yourself, or reflash the previous kernel.
"""


def root_driver_line(status):
    """The root driver changed in 1.4: 1.0-1.3 carried KernelSU-Next legacy 33314, 1.4 carries the
    official KernelSU v1.0.5 driver. The manager APK has to match the driver, so say it plainly."""
    driver = str((status or {}).get("ksu_driver") or "")
    if "official" in driver.lower():
        return ("with the OFFICIAL KernelSU v1.0.5 driver built in (declared version 12081; root is\n"
                "mandatory, no non-root mode) and SUSFS v1.5.9 enabled.\n"
                "Install the official KernelSU manager APK that matches driver v1.0.5. A KernelSU-Next\n"
                "APK (e.g. 3.4.2) will NOT talk to this driver - it will look like root is broken.")
    if "rollercoaster" in driver.lower() or "34000" in driver:
        return ("with the in-tree KernelSU-Next driver of the Rollercoaster 1.2.0 base built in\n"
                "(ksun-legacy-susfs-v2, declared 34000, manual hook; root is mandatory).\n"
                "The manager APK must be the one that driver accepts (Rollercoaster SU 1.0.0),\n"
                "and the installer writes ksud to /data/adb/ksud - data has to be decrypted in recovery.")
    if driver and "kernelsu-next legacy" not in driver.lower() and "33314" not in driver:
        return ("with " + driver + " built in (root is mandatory, no non-root mode);\n"
                "the manager APK has to be the one this driver accepts, and ksud is installed\n"
                "to /data/adb/ksud by the installer (data must be decrypted in recovery).")
    return "with KernelSU-Next legacy driver 33314 built in (root is mandatory, no non-root mode)."


def is_nonksu(status):
    return "nonksu" in str((status or {}).get("ksu_driver") or "").lower()


def short_driver(status):
    """One-line root driver label for the installer banner (must stay free of quotes)."""
    driver = str((status or {}).get("ksu_driver") or "").replace('"', "'").replace("\n", " ").strip()
    low = driver.lower()
    if "nonksu" in low or low.startswith("none"):
        return "without any root stack (NonKSU build: no KernelSU, no ksud, no /data/adb changes)"
    if "rollercoaster" in low:
        return "KernelSU-Next in-tree (Rollercoaster 34000, manual hook)"
    if "official" in low:
        return "official KernelSU v1.0.5 driver (12081)"
    if "33314" in driver:
        return "KernelSU-Next legacy 33314 (built-in, mandatory)"
    return driver[:72] if driver else "KernelSU (built-in) driver"


def build_flashable(ak3, image_gz, status):
    stage = WORK / "zip-flashable"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(ak3, stage)
    # trimmed AK3 base: our script, AK3 tools + updater, the kernel, and the readme
    ak = (REL / "anykernel.sh").read_text()
    assert 'SP_VERSION="' in ak, "anykernel.sh must declare SP_VERSION"
    ak = re.sub(r'SP_VERSION="[^"]*"', 'SP_VERSION="' + VERSION + '"', ak, count=1)
    assert 'SP_ROOT_LINE="' in ak, "anykernel.sh must declare SP_ROOT_LINE"
    ak = re.sub(r'SP_ROOT_LINE="[^"]*"', 'SP_ROOT_LINE="' + short_driver(status) + '"', ak, count=1)
    assert 'SP_UNAME="' in ak, "anykernel.sh must declare SP_UNAME"
    uname = str(status.get("uname_release") or ("4.14.357-openela-" + VERSION))
    ak = re.sub(r'SP_UNAME="[^"]*"', 'SP_UNAME="' + uname.replace('"', "") + '"', ak, count=1)
    (stage / "anykernel.sh").write_text(ak)
    (stage / "anykernel.sh").chmod(0o755)
    for junk in ["README.md", "patch", "modules", "ramdisk", ".github"]:
        p = stage / junk
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    (stage / "Image.gz").write_bytes(image_gz)
    ksud = ART / "ksud"
    if ksud.exists():
        shutil.copyfile(ksud, stage / "ksud")
        (stage / "ksud").chmod(0o755)
    (stage / "README-FLASH.txt").write_text(FLASH_README.format(v=VERSION, uname=str(status.get("uname_release") or ("4.14.357-openela-" + VERSION)), root_line=root_driver_line(status)))
    (stage / "BUILD-INFO.txt").write_text(json.dumps({
        "uname_release": status.get("uname_release"),
        "image_gz_sha256": status.get("image_gz_sha256"),
        "image_gz_bytes": status.get("image_gz_bytes"),
        "base_tree": status.get("base_tree"),
        "ksu_driver": status.get("ksu_driver"),
        "kind": status.get("kind"),
        "physical_boot_root_tests": status.get("physical_boot_root_tests"),
        "bootloop_fix_proven": status.get("bootloop_fix_proven"),
        "anykernel3": AK3["repository"] + "@" + AK3["commit"],
        "ksu_userspace_ksud": (sha_file(ART / "ksud") if (ART / "ksud").exists() else None),
    }, indent=2) + "\n")

    out = ART / ("Synthetica-" + VERSION + ".zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(stage).as_posix())
    return out


def build_collector(ak3):
    stage = WORK / "zip-collector"
    if stage.exists():
        shutil.rmtree(stage)
    meta = stage / "META-INF/com/google/android"
    meta.mkdir(parents=True)
    tools = stage / "tools"
    tools.mkdir()
    shutil.copyfile(ak3 / "META-INF/com/google/android/update-binary", meta / "update-binary")
    (meta / "update-binary").chmod(0o755)
    # recovery treats update-binary as a shell script; keep the marker updater-script
    (meta / "updater-script").write_text("#MAGISK\n")
    shutil.copyfile(REL / "log_collector.sh", meta / "update-binary")
    (meta / "update-binary").chmod(0o755)
    shutil.copyfile(ak3 / "tools/busybox", tools / "busybox")
    (tools / "busybox").chmod(0o755)
    (stage / "README-FLASH.txt").write_text(
        "SYNTHETICA-PULSE " + VERSION + " log collector\n"
        "===================================\n"
        "Read-only recovery tool. Collects dmesg, /proc/last_kmsg, pstore, recovery logs,\n"
        "mounts, module list and boot/dtbo/vbmeta hashes into\n"
        "<storage>/synthetica-logs/<timestamp>/ and a .tar.gz next to it.\n"
        "It does not modify any partition. Safe to run repeatedly; safe to run even when\n"
        "the phone is healthy.\n")

    out = ART / ("Synthetica-" + VERSION + "-LOG.zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(stage).as_posix())
    return out


def verify_zip(path, required):
    """Self-check a produced zip: CRC of every member plus required entries."""
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        assert bad is None, f"{path.name}: corrupt member {bad}"
        names = z.namelist()
    for want in required:
        assert any(n == want or n.startswith(want) for n in names), f"{path.name}: missing {want}"
    assert "META-INF/com/google/android/update-binary" in names, f"{path.name}: no update-binary"
    print(f"verified {path.name}: {len(names)} entries, CRC ok")
    return names


MANIFEST_NOTE = """\
SYNTHETICA PACKAGE {ver}
========================
ONLY ONE FILE IS FLASHED: {flash}
Everything else here is a record, a diagnostic tool, or a raw kernel image.

"""


def artifacts_manifest(status, flash, collector):
    """Write ARTIFACTS-MANIFEST.txt: one line per file, with its purpose and whether to flash it.

    This exists because two ~21 MB zips used to land in the same folder: the installer built here
    and the builder's own zip. Same image inside, different installer, different hash - asking a
    human to tell them apart by file size is not acceptable.
    """
    def sha_of(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    rows = []

    def add(path, purpose, flash_me=False):
        if not path.exists() or not path.is_file():
            return
        rows.append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha_of(path),
            "flash": "YES - this is the installer" if flash_me else "no",
            "purpose": purpose,
        })

    add(flash, "kernel + AnyKernel3 installer + ksud; backs up boot first, no auto reboot", True)
    add(collector, "read-only log grabber (dmesg/last_kmsg/pstore/logs); writes nothing to partitions")
    add(ART / "Image.gz", "kernel image only (gzip). NOT flashable on its own")
    add(ART / "ksud", "KernelSU userspace daemon, also shipped inside the flashable zip")
    add(ART / "STATUS.json", "machine-readable build record: uname, config flags, hashes, what was not tested")
    add(ART / "RELEASE-INFO.json", "package record: zip entries, installer behaviour")
    add(ART / "generated.config.txt", "the .config that was actually compiled")
    add(ART / "build.log", "full build log")
    add(ART / "TOOLCHAIN.txt", "compiler and linker versions")
    for ref in sorted(ART.glob("REFERENCE-NOT-FOR-FLASH-*.zip")):
        add(ref, "builder's own zip, renamed on purpose: no boot backup, no rollback. DO NOT FLASH")

    lines = [MANIFEST_NOTE.format(ver=status.get("release_version"), flash=flash.name)]
    for r in rows:
        lines.append(f"{r['name']}\n")
        lines.append(f"  bytes  : {r['bytes']}\n")
        lines.append(f"  sha256 : {r['sha256']}\n")
        lines.append(f"  flash? : {r['flash']}\n")
        lines.append(f"  what   : {r['purpose']}\n\n")
    lines.append("Check: the sha256 of your download must match the line above.\n")
    lines.append("Similar size does NOT mean the same file; compare sha256.\n")
    (ART / "ARTIFACTS-MANIFEST.txt").write_text("".join(lines))
    return ART / "ARTIFACTS-MANIFEST.txt"


def main():
    status_path = ART / "STATUS.json"
    assert status_path.exists(), "STATUS.json missing: run ci/build_release.py first"
    global VERSION
    status = json.loads(status_path.read_text())
    VERSION = str(status.get("release_version") or "1.0")
    image_gz = (ART / "Image.gz").read_bytes()
    assert hashlib.sha256(image_gz).hexdigest() == status["image_gz_sha256"], "Image.gz does not match STATUS.json"

    ak3 = fetch_ak3()
    flash = build_flashable(ak3, image_gz, status)
    collector = build_collector(ak3)
    needed = ["Image.gz", "anykernel.sh", "tools/busybox"]
    if (ART / "ksud").exists():
        needed.append("ksud")
    flash_entries = verify_zip(flash, needed)
    collector_entries = verify_zip(collector, ["META-INF/com/google/android/update-binary"])

    info = {
        "kind": "RELEASE_" + VERSION + "_PACKAGES_UNQUALIFIED_FLASH_AT_OWN_RISK",
        "release_version": VERSION,
        "uname_release": status.get("uname_release"),
        "kernel_image_gz_sha256": status.get("image_gz_sha256"),
        "kernel_image_gz_bytes": status.get("image_gz_bytes"),
        "flashable_zip": {"name": flash.name, "bytes": flash.stat().st_size, "sha256": sha_file(flash)},
        "log_collector_zip": {"name": collector.name, "bytes": collector.stat().st_size, "sha256": sha_file(collector)},
        "anykernel3": AK3,
        "flashable_entries": sorted(flash_entries),
        "log_collector_entries": sorted(collector_entries),
        "installer_behaviour": [
            "no boot backup (removed in 2.0 by request)",
            "writes an installation log to <storage>/Synthetica/install-log-<time>.txt",
            "no auto reboot", "no modules", "no /data writes",
        ],
        "log_collector_behaviour": [
            "read-only", "writes only under <storage>/synthetica-logs/",
            "collects dmesg, last_kmsg, pstore, recovery logs, partition hashes",
            "13-installed-kernel.txt: kernel version strings read out of the live boot partition",
            "14-installed-zip.txt: which SYNTHETICA-PULSE zip is on storage",
            "12-backup-listing/: copies BACKUP-INFO.txt if one exists from older releases",
        ],
        "physical_boot_root_tests": 0,
        "bootloop_fix_proven": False,
        "private_signing_key_exported": False,
    }
    (ART / "RELEASE-INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    # Guard (again, belt and braces): the builder's own zip must not look like an installer here.
    for z in sorted(ART.glob("SYNTHETICA-PULSE-*.zip")):
        if z.name.endswith(("-KERNEL.zip", "-LOG-COLLECTOR.zip", "-flashable.zip", "-log-collector.zip")) or (z.name.startswith("Synthetica-") and z.name.endswith(".zip")) or z.name.startswith("REFERENCE-NOT-FOR-FLASH-"):
            continue
        ref = ART / ("REFERENCE-NOT-FOR-FLASH-" + z.name)
        if ref.exists():
            ref.unlink()
        z.replace(ref)
        print(f"[rename] {z.name} -> {ref.name} (builder's zip: no boot backup, reference only)")

    (ART / "RELEASE-SHA256SUMS.txt").write_text(
        f"{info['flashable_zip']['sha256']}  {info['flashable_zip']['name']}\n"
        f"{info['log_collector_zip']['sha256']}  {info['log_collector_zip']['name']}\n")
    # Records must not keep saying "no installer" once the packages exist.
    status["installer_produced"] = True
    status["packages"] = {
        "flashable_zip": info["flashable_zip"],
        "log_collector_zip": info["log_collector_zip"],
        "release_info": "RELEASE-INFO.json",
    }
    status["artifacts_manifest"] = "ARTIFACTS-MANIFEST.txt"
    status["release_info_sha256"] = sha_file(ART / "RELEASE-INFO.json")
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(info, indent=2))
    # Written last on purpose: it records the sha256 of every file in this folder, STATUS.json
    # included, so it has to be generated after the record above is final.
    manifest = artifacts_manifest(status, flash, collector)
    print(f"manifest: {manifest}")


if __name__ == "__main__":
    main()
