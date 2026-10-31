#!/usr/bin/env python3
"""Build SYNTHETICA-PULSE 1.14 "CHRONICLE-BASE": the recipe of the kernel that boots.

Why this exists
---------------
Ten builds (1.0 .. 1.13) from our own kernel tree never booted this phone, while
Rollercoaster-Chronicle 1.2.0 (graziemille) does boot it. Comparing configs and patch
files inside *our* tree produced no answer, because the two kernels are not built from the
same tree, the same KernelSU fork, or the same defconfig base.

This build removes that ambiguity by rebuilding the proven recipe itself:

  tree      Saamitk/kernel_xiaomi_sm6250-switchoff @ c1e6f795b557b7bf92220c91f05a42b456de7a74
            (branch `a`, the only branch that carried the Rollercoaster 1.2.0 sources)
  sources   ci/rollercoaster/ (profiles + patches, byte-for-byte from the 1.2.0 bundle)
  profile   `chronicle` -> CONFIG_KSU=y, CONFIG_KSU_MANUAL_HOOK=y, SuSFS, NOMOUNT, no KPROBES
  builder   ci/rollercoaster/build-rollercoaster.sh (their builder, unchanged)

The kernel image is then packaged with OUR installer: the boot partition is backed up
before it is written, and /data/adb/ksud is installed, because a built-in KernelSU driver
without ksud on /data cannot bring root up (that gap existed in every earlier zip).

What this build can and cannot prove
------------------------------------
It proves whether the difference between "boots" and "does not boot" is the tree/KSU fork
or our own code. It proves nothing about our tree. Nothing here has been flashed on a
device, so the status is COMPILED_ONLY_UNVERIFIED until the user reports the result.

Reference-only zip
------------------
Their builder also emits Rollercoaster-Chronicle-1.2.0.zip. That zip has NO boot backup, so
it is renamed to REFERENCE-NOT-FOR-FLASH-... and must not be flashed.
"""
from pathlib import Path
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
WORK = Path(os.environ.get("SP_WORK_DIR", str(ROOT / ".work-chronicle-base"))).resolve()
RC = ROOT / "ci" / "rollercoaster"
SCRIPT = RC / "build-rollercoaster.sh"
PIN_FILE = ROOT / "ci" / "SOURCES_CHRONICLE_BASE.json"

TREE = {
    "repository": "Saamitk/kernel_xiaomi_sm6250-switchoff",
    "commit": "c1e6f795b557b7bf92220c91f05a42b456de7a74",
    "ref": "a",
    "archive_url": "https://codeload.github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/tar.gz/c1e6f795b557b7bf92220c91f05a42b456de7a74",
}

VERSION = os.environ.get("SP_RELEASE_VERSION", "1.16")
# Identity of the release string. 1.15 is the first build that carries OUR name: the kernel is
# still the chronicle-base recipe byte for byte, only CONFIG_LOCALVERSION changes (and with it the
# vermagic). That is the single variable of this build.
BUILD_NAME = os.environ.get("SP_BUILD_NAME", "SYNTHETICA-PULSE")
# Which rollercoaster profile to build. `chronicle` is the one proven on this device; `critical`
# differs only in tunables (HZ=300, gaming governor) and `lite` drops the root stack entirely.
PROFILE = os.environ.get("SP_PROFILE", "chronicle")
HAS_ROOT = PROFILE not in ("lite",)
BUILD_KVER = os.environ.get("SP_BUILD_KVER", VERSION)
EXPECT_RELEASE = os.environ.get("SP_EXPECT_RELEASE", "4.14.357-openela-" + BUILD_NAME + "-" + BUILD_KVER)
JOBS = os.environ.get("SP_JOBS", "4")
LOG = ART / "build.log"


def sha_file(path):
    return hashlib.file_digest(open(path, "rb"), "sha256").hexdigest()


def say(msg):
    print(msg, flush=True)
    with LOG.open("a") as f:
        f.write(msg + "\n")


def run(cmd, cwd=None, env=None):
    say("\n$ " + " ".join(str(c) for c in cmd) + (f"   (cwd={cwd})" if cwd else ""))
    t0 = time.time()
    with LOG.open("a") as f:
        p = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        f.write(p.stdout or "")
    tail = "\n".join((p.stdout or "").splitlines()[-25:])
    say(tail)
    say(f"[exit {p.returncode} in {time.time() - t0:.0f}s]")
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd)}")
    return p


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        say(f"[cache] {dest} ({dest.stat().st_size} bytes) already present")
        return
    say(f"[download] {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=1800) as r, dest.open("wb") as out:
        shutil.copyfileobj(r, out, length=1 << 20)
    say(f"[download] {dest.stat().st_size} bytes -> {dest}")


def extract(archive, dest):
    if dest.exists() and any(dest.iterdir()):
        say(f"[extract] {dest} already populated")
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    say(f"[extract] {archive} -> {dest}")
    with tarfile.open(archive) as t:
        filtered = sys.version_info >= (3, 12)
        for member in t:
            parts = member.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            member.name = parts[1]
            if filtered:
                t.extract(member, dest, filter="data")
            else:
                t.extract(member, dest)
    return dest


def kernel_release(image_gz):
    """Read the release string straight out of the image; never guess it."""
    with gzip.open(image_gz, "rb") as g:
        blob = g.read(1 << 26)
    i = blob.find(b"Linux version ")
    if i < 0:
        return "UNKNOWN"
    end = blob.find(b"\n", i)
    line = blob[i:end if end > 0 else i + 300].decode("utf-8", "replace")
    m = re.match(r"Linux version (\S+)", line)
    return m.group(1) if m else line[:120]


def config_flags(path):
    want = ["KSU", "KSU_MANUAL_HOOK", "KSU_KPROBES_HOOK", "KSU_SUSFS", "KSU_SUSFS_SUS_PATH",
            "NOMOUNT", "KPROBES", "KRETPROBES", "MODULE_SIG_FORCE", "MODVERSIONS",
            "EROFS_FS", "BPF_EVENTS", "PREEMPT", "LOCALVERSION",
            # gaming tunables - recorded so a report never has to guess what a variant did
            "HZ", "HZ_300", "CPU_FREQ_DEFAULT_GOV_PERFORMANCE", "CPU_BOOST", "MSM_PERFORMANCE",
            "SCHED_TUNE", "DEFAULT_IOSCHED", "IOSCHED_DEADLINE", "FUNCTION_TRACER", "FTRACE"]
    out = {}
    seen = {}
    for line in path.read_text().splitlines():
        if not line.startswith(("CONFIG_", "# CONFIG_")):
            continue
        if line.startswith("# CONFIG_") and line.endswith(" is not set"):
            k, v = line[2:].split(" ")[0], "n"
        elif "=" in line:
            k, v = line.split("=", 1)
        else:
            continue
        seen[k] = v
    for k in want:
        out[k] = seen.get("CONFIG_" + k)
    return out


def main():
    ART.mkdir(exist_ok=True)
    LOG.write_text(f"# SYNTHETICA-PULSE {VERSION} CHRONICLE-BASE build log\n")
    say(f"release={VERSION} jobs={JOBS}")

    # ---- 0. inputs we ship ourselves (their profiles/patches, our pin) -----------------
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert (RC / "profiles" / (PROFILE + ".config")).exists(), "missing profile " + PROFILE
    assert (RC / "patches" / "kernelsu-1.0.0.patch").exists(), "missing kernelsu patch"
    if HAS_ROOT:
        assert (RC / "anykernel" / "ksud").exists(), "missing ksud userspace binary"
    say(f"[inputs] ci/rollercoaster sources OK (builder sha256 {sha_file(SCRIPT)[:16]}...)")

    # ---- 1. base tree, pinned ---------------------------------------------------------
    WORK.mkdir(parents=True, exist_ok=True)
    archive = WORK / "tree.tar.gz"
    download(TREE["archive_url"], archive)
    measured = {"repository": TREE["repository"], "commit": TREE["commit"], "ref": TREE["ref"],
                "archive_url": TREE["archive_url"], "archive_bytes": archive.stat().st_size,
                "archive_sha256": sha_file(archive)}
    say(json.dumps({"base_tree": measured}, indent=2))
    if PIN_FILE.exists():
        pin = json.loads(PIN_FILE.read_text())
        assert pin.get("archive_sha256") == measured["archive_sha256"], \
            "base tree archive sha256 changed - refusing to build an unpinned tree"
        assert pin.get("archive_bytes") == measured["archive_bytes"], "base tree archive size changed"
        say("[pin] base tree matches ci/SOURCES_CHRONICLE_BASE.json")
        pin_state = "VERIFIED"
    else:
        say("[pin] FIRST RUN: recording the measurement; commit ci/SOURCES_CHRONICLE_BASE.json "
            "so the next build is pinned")
        (ART / "SOURCES_CHRONICLE_BASE.measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        pin_state = "FIRST_RUN_RECORDED"

    tree = extract(archive, WORK / "tree")

    # ---- 2. their builder, chronicle profile ------------------------------------------
    env = os.environ.copy()
    env["OUTDIR"] = str(ART)
    env["LC_ALL"] = "C"
    # ---- manager identity (only when this run repackaged the APK) ------------------------
    # The kernel accepts a manager only if sha256(DER cert) and its length match what it was
    # built with. ci/build_manager.py measures the repackaged APK; those exact numbers go into
    # the build here, so the APK and the kernel can never disagree.
    manager = None
    # Priority: the identity pinned in the repo (ci/manager-pinned/MANAGER.json) wins over anything
    # produced in this run, because the pinned APK is the one users actually have installed. A
    # same-run MANAGER.json only exists when this batch deliberately re-minted the manager.
    pinned = ROOT / "ci" / "manager-pinned" / "MANAGER.json"
    mgr_json = ART / "manager" / "MANAGER.json"
    if not mgr_json.exists() and pinned.exists():
        mgr_json = pinned
        say(f"[manager] using the pinned identity from {pinned.relative_to(ROOT)}")
    if mgr_json.exists():
        m = json.loads(mgr_json.read_text())
        assert m.get("cert_sha256") and m.get("cert_der_bytes") and m.get("package"), \
            "MANAGER.json incomplete"
        env["KSU_MANAGER_CERT_SIZE"] = str(m["cert_size_hex"])
        env["KSU_MANAGER_CERT_HASH"] = m["cert_sha256"]
        env["KSU_MANAGER_PKG"] = m["package"]
        manager = {
            "package": m["package"], "package_was": m.get("package_was"),
            "cert_der_bytes": m["cert_der_bytes"], "cert_size_hex": m["cert_size_hex"],
            "cert_sha256": m["cert_sha256"],
            "apk": m.get("output_apk"),
            "note": ("kernel built with this certificate; the old manager APK is not accepted "
                     "by this kernel and the new APK is not accepted by older kernels"),
        }
        say(f"[manager] package {m['package']} cert {m['cert_der_bytes']} B {m['cert_sha256'][:16]}...")
    else:
        say("[manager] no MANAGER.json - kernel keeps the shipped Rollercoaster manager identity")

    env["SP_BUILD_NAME"] = BUILD_NAME
    env["SP_BUILD_KVER"] = BUILD_KVER
    say(f"[identity] release string will be {EXPECT_RELEASE}")
    run(["bash", SCRIPT, tree, PROFILE, JOBS], cwd=tree, env=env)

    # ---- 3. collect the artefacts -----------------------------------------------------
    image_gz = tree / ("out-" + PROFILE) / "arch" / "arm64" / "boot" / "Image.gz"
    assert image_gz.exists(), f"builder finished without {image_gz}"
    assert image_gz.stat().st_size > 8 * 1024 * 1024, "Image.gz suspiciously small"
    shutil.copyfile(image_gz, ART / "Image.gz")
    img_sha, img_bytes = sha_file(ART / "Image.gz"), (ART / "Image.gz").stat().st_size

    cfg_src = tree / ("out-" + PROFILE) / ".config"
    assert cfg_src.exists(), "no .config from the builder"
    shutil.copyfile(cfg_src, ART / "generated.config.txt")
    flags = config_flags(ART / "generated.config.txt")
    say(json.dumps(flags, indent=2))

    # the builder already audits these; failing here means the tree drifted from the recipe
    if HAS_ROOT:
        assert flags["KSU"] == "y", "CONFIG_KSU is not y - this build would not carry root"
        assert flags["KSU_MANUAL_HOOK"] == "y", "manual hook mode is not y - not the proven recipe"
    else:
        assert flags["KSU"] == "n", "lite profile asked for no root but CONFIG_KSU is set"

    release = kernel_release(ART / "Image.gz")
    say(f"[uname] {release}")
    assert release.startswith("4.14.357"), f"unexpected kernel release: {release}"
    assert release == EXPECT_RELEASE, f"release string is {release}, expected {EXPECT_RELEASE}"

    if HAS_ROOT:
        shutil.copyfile(RC / "anykernel" / "ksud", ART / "ksud")
        (ART / "ksud").chmod(0o755)
    elif (ART / "ksud").exists():
        (ART / "ksud").unlink()  # a NonKSU zip must not ship ksud

    # The builder's own zip has no boot backup and no rollback, so it must never sit in the same
    # folder looking like an installer. It used to be renamed only when it was called
    # Rollercoaster-*.zip; since the release name became ours it is SYNTHETICA-PULSE-<ver>.zip, so
    # both patterns are matched here (our own -flashable / -log-collector outputs are skipped).
    ours = ("-KERNEL.zip", "-LOG-COLLECTOR.zip", "-flashable.zip", "-log-collector.zip")
    for z in sorted(set(ART.glob("Rollercoaster-*.zip")) | set(ART.glob("SYNTHETICA-PULSE-*.zip")) | set(ART.glob("Synthetica-*.zip"))):
        if z.name.endswith(ours) or z.name.startswith("REFERENCE-NOT-FOR-FLASH-"):
            continue
        target = ART / ("REFERENCE-NOT-FOR-FLASH-" + z.name)
        if target.exists():
            target.unlink()
        z.replace(target)
        say(f"[rename] {z.name} -> {target.name} (no boot backup inside; reference only)")

    status = {
        "kind": (("VARIANT_" + PROFILE + "_" + VERSION + "_COMPILED_ONLY_UNVERIFIED") if PROFILE != "chronicle"
                 else ("REBRAND_OF_THE_BOOTING_BASE_" + VERSION + "_COMPILED_ONLY_UNVERIFIED"
                 if EXPECT_RELEASE != "4.14.357-openela-Rollercoaster-Chronicle-1.2.0"
                 else "BASELINE_CLONE_OF_THE_KERNEL_THAT_BOOTS_COMPILED_ONLY_UNVERIFIED")),
        "release_version": VERSION,
        "uname_release": release,
        "base_tree": f"{TREE['repository']}@{TREE['commit']} (branch {TREE['ref']})",
        "base_tree_archive": measured,
        "base_tree_pin_state": pin_state,
        "build_recipe": "ci/rollercoaster/build-rollercoaster.sh <tree> chronicle (graziemille 1.2.0 sources)",
        "profile": PROFILE,
        "ksu_driver": ("KernelSU-Next legacy, in-tree (Rollercoaster ksun-legacy-susfs-v2, declared 34000)"
                       if HAS_ROOT else "none (NonKSU build: no root stack, no ksud, no /data/adb changes)"),
        "ksu_hook_mode": "manual (CONFIG_KSU_MANUAL_HOOK=y, CONFIG_KPROBES=n)" if HAS_ROOT else "n/a",
        "ksu_userspace": ("ksud 5518552 B shipped in the zip, installed to /data/adb/ksud"
                          if HAS_ROOT else "none - this build intentionally carries no root"),
        "manager": manager if manager else {
            "package": "com.rifsxd.ksunext",
            "note": "shipped Rollercoaster SU 1.0.0 manager, unchanged",
        },
        "mandatory_KSU": HAS_ROOT,
        "compile_exit_code": 0,
        "image_gz_bytes": img_bytes,
        "image_gz_sha256": img_sha,
        "config_sha256": sha_file(ART / "generated.config.txt"),
        "features": flags,
        "module_signatures_verified": False,
        "physical_boot_root_tests": "NOT_RUN",
        "bootloop_fix_proven": False,
        "private_signing_key_exported": False,
        "installer": "ci/release/anykernel.sh (boot backup + rollback before write, ksud install, no auto reboot)",
        "why": ("1.14 proved the chronicle-base recipe boots and gives root on this phone. This build "
                "only replaces the release identity with ours (CONFIG_LOCALVERSION -> "
                + EXPECT_RELEASE + "), so the next step is not taken on an unproven base. "
                "Every other config value, patch and tool is identical to 1.14."),
        "identity_change": {
            "release_string": EXPECT_RELEASE,
            "was": "4.14.357-openela-Rollercoaster-Chronicle-1.2.0 (1.14, known-good)",
            "only_knob": "CONFIG_LOCALVERSION (byte-identical sources, patches, profiles and toolchain)",
            "expected_side_effect": ("vermagic changes, so /vendor modules built for this ROM keep "
                                     "being rejected - exactly as they already were"),
        },
        "known_good_reference": {
            "version": "1.14",
            "run": "40813125790",
            "flashable_sha256": "36b4af73e06aae172194a09b58d896fc573618199a0687d23d5400fad795928d",
            "device_result": "boot + root confirmed on 2026-10-29 (su in Termux gave uid 0)",
        },
        "provenance_note": ("Kernel sources are GPL-2.0 upstream + graziemille's Rollercoaster changes; "
                            "see ci/rollercoaster/README.md and licenses/ for attribution."),
        "policy": ("module signature enforcement left as the recipe sets it; nothing disabled, "
                   "no SELinux bypass, no vbmeta/firmware writes"),
        "test_protocol": [
            "boot must be observed on the device before any claim of a fix",
            "installer backs up the current boot partition first; restore it if the device does not boot",
            "on failure: flash the log collector and send <storage>/synthetica-logs/<timestamp>/",
        ],
    }
    (ART / "STATUS.json").write_text(json.dumps(status, indent=2) + "\n")
    say("\nSTATUS.json\n" + json.dumps(status, indent=2))
    say(f"\nDONE: Image.gz {img_bytes} B sha256 {img_sha}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        ART.mkdir(exist_ok=True)
        (ART / "FAILED.txt").write_text(
            f"SYNTHETICA-PULSE {VERSION} CHRONICLE-BASE build failed\n\n{tb}\n")
        print(tb, file=sys.stderr)
        sys.exit(1)
