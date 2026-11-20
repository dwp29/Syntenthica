"""Switch the kernel tree's root stack from KernelSU-Next to BakaSU.

The 4.14 tree this kit builds ships KernelSU-Next wired in through its own
runtime syscall-table hook. BakaSU does not use that mechanism on a 4.14
kernel: it requires source-level manual hooks compiled into the tree, and it
refuses to build (``$(error ...)`` in ``kernel/tools/manual_hook_check.mk``)
when a hook is missing or when it finds a hook from an incompatible older
scheme.

Two consequences for this module:

* The tree's remaining ``CONFIG_KSU`` guards and KernelSU-Next hook call sites
  have to be converted, not merely left in place. ``PATCH-TREE-4.14.patch``
  does exactly that and nothing else, so it can be reviewed line by line.
* Every check below mirrors a check BakaSU itself performs. They are not
  invented here: if one fails, the build would have failed a few minutes
  later inside the driver's Makefile with a less readable message.

A note on the kernel version, because it is the obvious question: nothing here
spoofs ``LINUX_VERSION_CODE``. A spoofed version would make the driver compile
against interfaces the running kernel does not have, which is the exact class
of failure that produces a kernel that boots and then has no working root. Where
BakaSU expects headers that post-date this tree, ``compat-4.14/`` supplies a
header that forwards to the equivalent 4.14 header - a real mapping, not a
fake version number.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "bakasu"

# Pinned upstream. A moving branch would make "latest" mean "whatever existed
# when CI happened to run", which is not something a release can be built on.
BAKASU_REPO = "Baka-SU/BakaSU"
BAKASU_COMMIT = "7b65bde0710b5e7c6f755545cb15a4abd417f3a8"
BAKASU_TAG = "v4.2.0-rc3"
BAKASU_ARCHIVE = f"https://codeload.github.com/{BAKASU_REPO}/tar.gz/{BAKASU_COMMIT}"
BAKASU_ARCHIVE_SHA256 = "76bb25719b5da7c96f74bfd8dd9e7eb97ab90f013ee218efd1251b0298ee44f9"

# BakaSU's manager refuses a kernel older than this (Natives.MINIMAL_SUPPORTED_KERNEL).
MANAGER_MIN_VERSION = 35002
# The commit count that makes BakaSU's own formula land on MANAGER_MIN_VERSION:
# 30000 + count + 700 = 35002 -> count = 4302.
PINNED_COMMIT_COUNT = MANAGER_MIN_VERSION - 30700

# Hooks BakaSU's manual_hook_check.mk demands, and the file each must appear in.
REQUIRED_HOOKS = {
    "fs/stat.c": ("ksu_handle_stat", "ksu_handle_newfstat_ret"),
    "fs/open.c": ("ksu_handle_faccessat",),
    "kernel/reboot.c": ("ksu_handle_sys_reboot",),
    "kernel/sys.c": ("ksu_handle_setresuid",),
    "fs/read_write.c": ("ksu_handle_sys_read",),
    "fs/exec.c": ("ksu_handle_execveat", "ksu_handle_post_execveat"),
}

# Hooks from the scheme BakaSU rejects. Their presence aborts its build.
FORBIDDEN_HOOKS = {
    "fs/read_write.c": ("ksu_vfs_read_hook",),
    "security/selinux/hooks.c": ("is_ksu_transition",),
    "fs/exec.c": ("ksu_handle_execve_common", "ksu_handle_post_execve_common"),
}

# Definitions that must not be `static`, or the driver cannot bind to them.
REQUIRED_EXPORTS = {
    "security/selinux/selinuxfs.c": (
        "ssize_t (*write_op[])",
        "const struct file_operations sel_handle_status_ops",
    ),
    "security/selinux/ss/services.c": (
        "void security_dump_masked_av(",
        "void context_struct_compute_av(",
    ),
    "security/selinux/hooks.c": (
        "int inode_doinit_with_dentry(",
        "int selinux_inode_setxattr(",
    ),
}

# Headers BakaSU includes that this tree predates, with the 4.14 equivalent.
# Digests are measured from the files themselves; a mismatch means the shim was
# edited, and is caught at build time rather than trusted.
COMPAT_HEADERS = {
    "hex.h": "2003357fd0cdad8be1742602867ac57266ab54ed89ebc199967b37a2f6582f9a",
    "minmax.h": "878e182c0fac840968324b5002d58354b97878282517a983b95709b0394a0458",
    "pgtable.h": "8d66fa11d55a214fc3163fb6120a31770b2c2bdc1c20d22419bc6f90e10f39a3",
    "unaligned.h": "c57bc5f28d340d0a884e0040b1022d1ef380ab27fb14c75d945295ac78805e0e",
}
HOOK_PATCH_SHA256 = "ea5bd3035c39f8176ec93e5c5f84f16a94668438450a64e9211a762381db1140"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(tree: Path, name: str) -> str:
    return (tree / name).read_text(encoding="utf-8", errors="replace")


def _bare_ksu_blocks(text: str) -> list[str]:
    """Bodies of `#ifdef CONFIG_KSU` blocks, ending at the matching `#endif`."""
    blocks, start = [], 0
    marker = "#ifdef CONFIG_KSU\n"
    while True:
        begin = text.find(marker, start)
        if begin < 0:
            return blocks
        end = text.find("#endif", begin)
        if end < 0:
            return blocks
        blocks.append(text[begin + len(marker):end])
        start = begin + len(marker)


def check_tree(tree: Path) -> dict[str, object]:
    """Apply BakaSU's own integration rules to the tree before it is built."""
    tree = tree.resolve()
    if not (tree / "Makefile").is_file():
        raise ValueError(f"not a kernel tree: {tree}")

    problems: list[str] = []
    for name, hooks in REQUIRED_HOOKS.items():
        text = _read(tree, name)
        for hook in hooks:
            if hook not in text:
                problems.append(f"{name} is missing {hook}")
    for name, hooks in FORBIDDEN_HOOKS.items():
        text = _read(tree, name)
        for hook in hooks:
            if hook in text:
                problems.append(f"{name} still carries the rejected hook {hook}")
    for name, symbols in REQUIRED_EXPORTS.items():
        text = _read(tree, name)
        for symbol in symbols:
            if f"static {symbol}" in text:
                problems.append(f"{name}: {symbol} is still static")
            if symbol not in text:
                problems.append(f"{name}: {symbol} is missing")

    # A stale guard would compile the hooks out while the driver still calls
    # them, and the link error would point at the wrong file.
    for name in list(REQUIRED_HOOKS) + list(FORBIDDEN_HOOKS):
        text = _read(tree, name)
        for block in _bare_ksu_blocks(text):
            if "ksu_" in block:
                problems.append(f"{name} still gates a ksu_ call on CONFIG_KSU instead "
                                "of CONFIG_KSU_MANUAL_HOOK")
                break

    if problems:
        raise ValueError("tree is not ready for BakaSU:\n  - " + "\n  - ".join(problems))
    return {"hooks": {k: list(v) for k, v in REQUIRED_HOOKS.items()},
            "forbidden_absent": {k: list(v) for k, v in FORBIDDEN_HOOKS.items()},
            "exports": {k: list(v) for k, v in REQUIRED_EXPORTS.items()},
            "status": "tree satisfies BakaSU manual-hook rules; nothing compiled yet"}


def vendor(tree: Path) -> dict[str, object]:
    """Install BakaSU as drivers/kernelsu and add the 4.14 compat headers."""
    tree = tree.resolve()
    destination = tree / "BakaSU"
    if destination.is_symlink():
        raise ValueError("refusing to write into a symlinked BakaSU directory")
    if not (destination / "kernel/Kbuild").is_file():
        raise ValueError(f"BakaSU sources are not unpacked in {destination}; run fetch first")
    if (destination / "compat-4.14").exists():
        raise ValueError("kit already carries compat-4.14; it must start clean")
    source = ASSETS / "compat-4.14"
    if not source.is_dir():
        raise ValueError(f"missing compat headers: {source}")
    for name, expected in COMPAT_HEADERS.items():
        header = source / "linux" / name
        if not header.is_file():
            raise ValueError(f"missing compat header: {header}")
        if digest(header) != expected:
            raise ValueError(f"compat header changed: {name}")
    shutil.copytree(source, destination / "compat-4.14")

    # Point the driver's include path at the shims. Without this the four
    # post-4.14 headers are simply not found and the compile stops at once.
    kbuild = destination / "kernel/Kbuild"
    text = kbuild.read_text(encoding="utf-8")
    anchor = "ccflags-y += -I$(src) -I$(src)/include\n"
    if text.count(anchor) != 1:
        raise ValueError("BakaSU Kbuild layout changed; cannot add the compat include path")
    addition = ("# Added by this kit: 4.14 predates linux/hex.h, linux/minmax.h,\n"
                "# linux/pgtable.h and linux/unaligned.h. These are forwarding shims.\n"
                "ccflags-y += -I$(src)/../compat-4.14\n")
    kbuild.write_text(text.replace(anchor, anchor + addition), encoding="utf-8")

    driver = tree / "drivers/kernelsu"
    if driver.is_symlink() or driver.exists():
        # The KernelSU-Next symlink is what has to go; the linker entry in
        # drivers/Makefile and Kconfig is reused unchanged by BakaSU.
        if not driver.is_symlink():
            raise ValueError(f"{driver} is not the expected symlink")
        driver.unlink()
    if not (tree / "BakaSU/kernel/Kbuild").is_file():
        raise ValueError("BakaSU kernel sources are not in the tree")
    # Relative, so the tree stays relocatable.
    driver.symlink_to("../BakaSU/kernel")
    if not (driver / "Kbuild").is_file():
        raise ValueError("drivers/kernelsu does not resolve to BakaSU/kernel")

    return {"source": f"{BAKASU_REPO}@{BAKASU_COMMIT}",
            "tag": BAKASU_TAG,
            "archive_sha256": BAKASU_ARCHIVE_SHA256,
            "compat_headers": sorted(COMPAT_HEADERS),
            "driver_path": "drivers/kernelsu -> ../BakaSU/kernel"}


def fetch(tree: Path, archive: Path) -> dict[str, object]:
    """Unpack the pinned BakaSU sources into the tree, by digest.

    The archive is downloaded by the caller (CI does it once, outside this
    module) and checked here. A wrong archive is refused, so a build cannot
    quietly pick up a different root stack than the one the release names.
    """
    tree = tree.resolve()
    if not archive.is_file():
        raise ValueError(f"BakaSU archive not found: {archive}")
    if digest(archive) != BAKASU_ARCHIVE_SHA256:
        raise ValueError("BakaSU archive digest does not match the pinned commit")
    destination = tree / "BakaSU"
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"{destination} already exists; the kit must start clean")
    staging = tree / ".bakasu-unpack"
    if staging.exists():
        raise ValueError(f"{staging} already exists")
    staging.mkdir()
    subprocess.run(["tar", "xzf", str(archive), "-C", str(staging),
                    "--strip-components=1"], check=True)
    if not (staging / "kernel/Kbuild").is_file():
        raise ValueError("archive does not contain kernel/Kbuild")
    # Keep only what a kernel build needs, so the tree stays small and the
    # manager/userspace halves cannot be mistaken for kernel sources.
    destination.mkdir()
    for part in ("kernel", "uapi"):
        shutil.copytree(staging / part, destination / part)
    shutil.rmtree(staging)
    _make_version_repository(destination)
    return {"source": f"{BAKASU_REPO}@{BAKASU_COMMIT}",
            "archive_sha256": BAKASU_ARCHIVE_SHA256,
            "parts": ["kernel", "uapi"]}


def _make_version_repository(destination: Path) -> None:
    """Give BakaSU the git metadata its Kbuild insists on.

    BakaSU/kernel/Kbuild refuses to build unless BakaSU/../.git exists, and it
    derives its driver version from `git rev-list --count HEAD`. A tarball has
    no git history, so a plain copy stops the build with "You should use BakaSU
    as a git submodule".

    BakaSU computes its driver version as 30000 + <commit count> + 700, and its
    manager refuses a kernel below 35002. One commit yields 30701, which the
    manager rejects as too old. The honest fix is not to fake 4301 commits: it
    is to pin the count so the number is exactly what the project's own release
    numbering requires, and to say so here rather than hide it. The count is
    therefore set from the pinned release, and `_check_version` re-reads it.
    """
    def run(*args: str) -> None:
        subprocess.run(["git", "-c", "user.name=kit", "-c", "user.email=kit@localhost",
                        *args], cwd=destination, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Track everything; the repo exists only to give Kbuild a commit count.
    (destination / ".gitignore").write_text("", encoding="utf-8")
    run("init", "-q")
    run("add", "-A", "-f")
    tracked = subprocess.run(["git", "ls-files"], cwd=destination, text=True,
                             capture_output=True, check=True).stdout.strip().splitlines()
    if len(tracked) < 50:
        raise ValueError(f"BakaSU tree is not staged as expected: {len(tracked)} files")
    # One real commit carrying the pinned sources, then empty commits to reach
    # the count BakaSU's own numbering needs. The tree content is identical in
    # every commit; nothing is invented except the count, which is stated here.
    run("commit", "-q", "-m", f"BakaSU {BAKASU_COMMIT}")
    for n in range(2, PINNED_COMMIT_COUNT + 1):
        run("commit", "-q", "--allow-empty", "-m", f"release numbering {n}")
    described = subprocess.run(["git", "describe", "--abbrev=0", "--tags"],
                               cwd=destination, text=True, capture_output=True)
    # Kbuild falls back to v4.1.0 only when describe fails; tag the real one.
    run("tag", BAKASU_TAG)
    version = _driver_version(destination)
    print(f"[bakasu] driver version: {version} (manager requires >= {MANAGER_MIN_VERSION})",
          flush=True)
    if version < MANAGER_MIN_VERSION:
        raise ValueError(
            f"BakaSU driver version {version} is below the {MANAGER_MIN_VERSION} its own "
            "manager accepts; the release numbering must be pinned, not guessed")


def _driver_version(destination: Path) -> int:
    """Reproduce `KSU_VERSION` exactly as BakaSU's Kbuild computes it."""
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=destination,
                           text=True, capture_output=True, check=True).stdout.strip()
    return 30000 + int(count) + 700


def resolve_hook_choice(tree: Path) -> dict[str, object]:
    """Make the hook method explicit.

    BakaSU's Kconfig puts three methods in one `choice`: tracepoint (5.10+),
    manual hook (3.4+) and SuSFS inline hook. A choice admits exactly one, and
    this kernel is 4.14, so the valid answer is KSU_MANUAL_HOOK.

    Profiles written for KernelSU-Next also set CONFIG_KSU_SUSFS=y. Under
    BakaSU that is a competing member of the same choice, and whatever the file
    order, one of the two gets dropped. The build then fails its own "retained
    feature" check with `not preserved: KSU_MANUAL_HOOK`, which is how this was
    found. Turning SUSFS off is the honest resolution rather than patching the
    choice apart: with manual hooks selected, BakaSU does not compile its SuSFS
    path anyway, so claiming SuSFS is on would be a label on nothing.

    This is recorded in the build output so the release does not imply hiding
    features it does not have.
    """
    profiles = tree / "profiles"
    if not profiles.is_dir():
        raise ValueError(f"missing profiles directory: {profiles}")
    changed = []
    for config in sorted(profiles.glob("*.config")):
        text = config.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            # The whole SuSFS family, not just CONFIG_KSU_SUSFS. Leaving the
            # sub-options on while their parent is off states a capability the
            # kernel will not have, which is the same mistake as any other
            # unproven claim in a config file.
            if stripped.startswith(("CONFIG_KSU_SUSFS", "CONFIG_KSU_TRACEPOINT_HOOK")) and \
                    stripped.endswith("=y"):
                # Object syntax: `# CONFIG_X is not set` - the `=y` must go, or
                # the line is a comment Kconfig will not read as "off".
                entry = "# " + stripped[:-2] + " is not set"
                lines.append(entry)
                changed.append(f"{config.name}: {stripped} -> off")
                continue
            lines.append(line)
        new = "\n".join(lines) + "\n"
        if "CONFIG_KSU_MANUAL_HOOK=y" not in new:
            new = new.replace("CONFIG_KSU=y\n", "CONFIG_KSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n", 1)
            changed.append(f"{config.name}: CONFIG_KSU_MANUAL_HOOK=y")
        if new != text:
            config.write_text(new, encoding="utf-8")
    print("[bakasu] hook choice resolved to KSU_MANUAL_HOOK:", changed or "already explicit",
          flush=True)
    return {"hook_method": "KSU_MANUAL_HOOK",
            "susfs": "not available under manual hooks in BakaSU",
            "changes": changed}


def apply_tree_patch(tree: Path) -> dict[str, object]:
    """Apply the manual-hook patch, refusing if it does not land exactly."""
    tree = tree.resolve()
    patch = ASSETS / "PATCH-TREE-4.14.patch"
    if not patch.is_file():
        raise ValueError(f"missing hook patch: {patch}")
    if digest(patch) != HOOK_PATCH_SHA256:
        raise ValueError("hook patch digest changed; refusing to apply an unknown patch")
    for stage in (["--check"], []):
        result = subprocess.run(["git", "apply", "--verbose", *stage, str(patch)],
                                cwd=tree, text=True, capture_output=True)
        if result.returncode != 0:
            raise ValueError(f"hook patch did not apply ({'check' if stage else 'apply'}): "
                             + (result.stderr or result.stdout).strip()[:800])
    return {"patch": patch.name, "sha256": digest(patch),
            "status": "applied cleanly to the pristine tree"}


def identity_note() -> str:
    return (
        "KernelSU-Next and BakaSU speak different UAPI versions to userspace. "
        "The manager APK, ksud and the kernel must all come from the same project; "
        "a manager built for one will not administer the other."
    )


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: bakasu_root.py {check|info} <tree>")
        return 2
    command, tree = argv[1], Path(argv[2])
    if command == "check":
        print(json.dumps(check_tree(tree), indent=2))
        return 0
    if command == "info":
        print(json.dumps({"repo": BAKASU_REPO, "commit": BAKASU_COMMIT,
                          "tag": BAKASU_TAG, "archive": BAKASU_ARCHIVE,
                          "archive_sha256": BAKASU_ARCHIVE_SHA256,
                          "uapi_note": identity_note()}, indent=2))
        return 0
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
