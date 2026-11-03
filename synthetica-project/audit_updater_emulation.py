#!/usr/bin/env python3
"""Exercise the pinned Android updater on synthetic files, never on a device.

This tool is intentionally restricted to the audited ZIP identities and a
pinned QEMU executable.  Each execution uses an unprivileged user+mount+PID+
network namespace, a chroot containing only disposable regular-file targets,
a read-only bind mount for its input ZIP, no inherited directory descriptors,
zero Linux capabilities, and no-new-privileges.  The original Android updater
is run only inside that sandbox.  No firmware is built, no device is opened,
and the synthetic ZIPs are not deliverables or valid ROMs.

Property expressions are substituted only in synthetic scripts. The two real
ZIP64 inputs are mounted read-only: one test stops at the device check, and
another uses a disposable fake Android property area plus directory targets to
force opening each destination to fail. Their ZIPs and scripts are unchanged.
QEMU and the source ZIPs must be supplied explicitly and match pinned hashes.
An unsupported sandbox fails closed; there is no unsafe fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import audit_boot_first_installer as audit
import build_guarded_candidate as builder

QEMU_SHA256 = "4f55e2e88dc05dc0f619562d5795b8eb25ed2ad2547504fb4835207a6911c350"
QEMU_SOURCE = "https://github.com/RuriOSS/qemu-user-static-x86_64/tree/adf37fd001dfa1f20d681b9cf0cedcba82b92bf9"
QEMU_BLOB = "df7501e7cff2e43df6fff8342710d28a6967c369"
DTBO_SHA256 = "9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2"
DTBO_SIZE = 25_165_824
PARTITIONS = ("super", "boot", "dtbo")
SENTINEL = b"SYNTHENTICA-DISPOSABLE-REGULAR-FILE-UNTOUCHED\n"
FINISHED_MESSAGE = "- Flashing completed. Have a good day."
MAX_TEST_FILE_BYTES = 9 * 1024**3  # disposable regular-file targets only
SCRIPT_PROPERTIES = (b'getprop("ro.product.device")', b'getprop("ro.build.product")')


class SimulationError(RuntimeError):
    """Refuse any test whose identities, isolation, or results are uncertain."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_identity(path: Path, size: int | None, expected: str) -> dict:
    """Reject symlinks and changes during the complete input hash pass."""
    path = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SimulationError(f"Cannot safely open input: {path}") from exc
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or (size is not None and before.st_size != size):
            raise SimulationError("Input is not a regular file of its expected size")
        h = hashlib.sha256()
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
        after = os.fstat(stream.fileno())
        now = os.stat(path, follow_symlinks=False)
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, a) != getattr(after, a) or getattr(before, a) != getattr(now, a)
           for a in attrs):
        raise SimulationError("Input changed while it was being checked")
    if h.hexdigest() != expected:
        raise SimulationError("Input SHA-256 does not match its pinned identity")
    return {"bytes": before.st_size, "sha256": h.hexdigest()}


def substitute_properties(script: bytes, right_device: bool) -> bytes:
    """Change only the property expressions, for synthetic ZIPs and targets."""
    literal = b'"joyeuse"' if right_device else b'"not-a-miatoll-device"'
    result = script
    for token, count in zip(SCRIPT_PROPERTIES, (6, 5)):
        if result.count(token) != count:
            raise SimulationError("Unexpected property expression count")
        result = result.replace(token, literal)
    if b"getprop(" in result:
        raise SimulationError("Unmocked property access in synthetic script")
    return result


def synthetic_script(old_script: bytes, guarded: bool, right_device: bool) -> bytes:
    """Change property reads to literals; preserve the three write expressions."""
    if digest(old_script) != builder.OLD_SCRIPT_SHA:
        raise SimulationError("Script is not the pinned original")
    result = builder.guard_script(old_script) if guarded else old_script
    return substitute_properties(result, right_device)


def fake_joyeuse_property_area() -> bytes:
    """A disposable pre-split Bionic property area containing one fake value.

    The fixture follows the documented AOSP prop_area/prop_bt/prop_info layout;
    it never reads, copies, or changes properties from a real Android device.
    """
    data = bytearray(128 * 1024)
    struct.pack_into("<IIII", data, 0, 308, 0, 0x504F5250, 0xFC6ED0AB)
    base = 128
    for off, name, prop, children in ((0, b"", 0, 112), (112, b"ro", 0, 136),
                                      (136, b"product", 0, 164), (164, b"device", 192, 0)):
        struct.pack_into("<IIIII", data, base + off, len(name), prop, 0, 0, children)
        data[base + off + 20:base + off + 20 + len(name)] = name
    struct.pack_into("<I", data, base + 192, 7 << 24)
    data[base + 196:base + 203] = b"joyeuse"
    name = b"ro.product.device"
    data[base + 288:base + 288 + len(name)] = name
    return bytes(data)


def make_payloads(real_dtbo: bytes | None = None) -> dict[str, bytes]:
    data = {name: (f"synthetic-{name}-regular-file-only\n".encode() * 64)
            for name in PARTITIONS}
    if real_dtbo is not None:
        if len(real_dtbo) != DTBO_SIZE or digest(real_dtbo) != DTBO_SHA256:
            raise SimulationError("The DTBO bytes are not the pinned source member")
        data["dtbo"] = real_dtbo
    return data


def write_synthetic_zip(path: Path, script: bytes, payloads: dict[str, bytes]) -> None:
    if path.exists() or set(payloads) != set(PARTITIONS):
        raise SimulationError("Invalid synthetic archive destination or payload set")
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        archive.writestr(builder.SCRIPT, script)
        for name in PARTITIONS:
            archive.writestr(name + ".img", payloads[name])


# Runs on the host Python *after* unshare, before entering the empty chroot.
# Both mounts live only in the new mount namespace and disappear at exit.
_ISOLATED_LAUNCHER = r'''
import ctypes, os, resource, signal, stat, subprocess, sys
root, archive, limit = sys.argv[1:]
limit = int(limit)
if not 0 <= limit <= 9 * 1024 * 1024 * 1024:
    raise RuntimeError('invalid test-only file size limit')
mountpoint = root + '/input.zip'
subprocess.run(['/usr/bin/mount', '--bind', archive, mountpoint], check=True)
subprocess.run(['/usr/bin/mount', '-o', 'remount,bind,ro', mountpoint], check=True)
try:
    fd = os.open(mountpoint, os.O_WRONLY)
except OSError:
    pass
else:
    os.close(fd)
    raise RuntimeError('read-only bind mount verification failed')
for name in ('super', 'boot', 'dtbo'):
    st = os.lstat(root + '/dev/block/bootdevice/by-name/' + name)
    if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
        raise RuntimeError('fake target is not a regular file or test directory')
os.chroot(root)
os.chdir('/')
if os.path.exists('/home/user/Syntenthica') or os.path.exists('/proc'):
    raise RuntimeError('chroot unexpectedly contains host paths')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
if limit:
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
libc = ctypes.CDLL(None, use_errno=True)
class CapHeader(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class CapData(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32),
                ('inheritable', ctypes.c_uint32)]
header = CapHeader(0x20080522, 0)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'no_new_privs')
empty = (CapData * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(empty)) != 0:
    raise OSError(ctypes.get_errno(), 'drop capabilities')
actual = (CapData * 2)()
if libc.capget(ctypes.byref(header), ctypes.byref(actual)) != 0 or any(
    x.effective or x.permitted or x.inheritable for x in actual
):
    raise RuntimeError('capabilities were not cleared')
os.closerange(3, 4096)
os.execve('/qemu', ['qemu', '/update-binary', '3', '1', '/input.zip'],
          {'PATH': '/', 'LANG': 'C'})
'''


def _exec_isolated(root: Path, archive: Path, timeout: int = 45,
                   file_size_limit: int = 0) -> subprocess.CompletedProcess:
    """Fail closed if user namespaces, bind mounts, or the chroot are unavailable."""
    if type(file_size_limit) is not int or not 0 <= file_size_limit <= MAX_TEST_FILE_BYTES:
        raise SimulationError("Invalid test-only file size limit")
    unshare = shutil.which("unshare")
    if not unshare or not Path("/usr/bin/mount").is_file():
        raise SimulationError("The required user/mount namespace tooling is unavailable")
    args = [unshare, "--user", "--map-root-user", "--mount", "--net", "--pid", "--fork",
            sys.executable, "-I", "-S", "-c", _ISOLATED_LAUNCHER,
            str(root), str(archive), str(file_size_limit)]
    proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True,
                            env={"PATH": "/usr/bin:/bin", "LANG": "C"})
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise SimulationError("Isolated updater timed out; process group terminated") from exc
    if len(out) > 1_000_000 or len(err) > 1_000_000:
        raise SimulationError("Isolated updater produced an unexpectedly large log")
    return subprocess.CompletedProcess(args, proc.returncode, out.decode("utf-8", "replace"),
                                       err.decode("utf-8", "replace"))


def _snapshot_fake_targets(base: Path) -> dict:
    out = {}
    for name in PARTITIONS:
        path = base / name
        st = path.lstat()
        if stat.S_ISDIR(st.st_mode):
            out[name] = {"type": "directory"}
        elif stat.S_ISREG(st.st_mode):
            data = path.read_bytes()
            out[name] = {"type": "regular", "bytes": len(data), "sha256": digest(data),
                         "unchanged_sentinel": data == SENTINEL}
        else:
            raise SimulationError("A fake target changed into an unexpected file type")
    return out


def run_sandbox(qemu: Path, updater: bytes, archive: Path, failure: str | tuple | None,
                file_size_limit: int = 0, fake_joyeuse: bool = False) -> dict:
    failures = (failure,) if isinstance(failure, str) else (() if failure is None else failure)
    if (not isinstance(failures, tuple) or any(not isinstance(name, str) for name in failures)
            or len(failures) != len(set(failures)) or any(name not in PARTITIONS for name in failures)
            or type(fake_joyeuse) is not bool):
        raise SimulationError("Unknown synthetic failure target or property fixture")
    with tempfile.TemporaryDirectory(prefix="synthetica-updater-sandbox-") as td:
        root = Path(td) / "root"
        base = root / "dev/block/bootdevice/by-name"
        base.mkdir(parents=True)
        shutil.copyfile(qemu, root / "qemu")
        (root / "qemu").chmod(0o755)
        (root / "update-binary").write_bytes(updater)
        (root / "update-binary").chmod(0o755)
        (root / "input.zip").touch()
        if fake_joyeuse:
            properties = root / "dev/__properties__"
            properties.write_bytes(fake_joyeuse_property_area())
            properties.chmod(0o444)
        for name in PARTITIONS:
            target = base / name
            if name in failures:
                target.mkdir()
            else:
                target.write_bytes(SENTINEL)
        run = _exec_isolated(root, archive.absolute(), file_size_limit=file_size_limit)
        states = _snapshot_fake_targets(base)
        return {"exit_code": run.returncode,
                "reported_completed": FINISHED_MESSAGE in run.stdout,
                "device_rejected": "E3004:" in run.stdout,
                "open_failure_reported": "can't open /dev/block/bootdevice/by-name/" in run.stdout,
                "failed_open_targets": [p for p in PARTITIONS if
                    "can't open /dev/block/bootdevice/by-name/" + p + " for write" in run.stdout],
                "file_limit_failure_reported": "File too large" in run.stdout and "I/O error" in run.stdout,
                "assert_failed": "assert failed: package_extract_file(" in run.stdout,
                "fake_targets": states,
                "stderr_selinux_fixture_warning": "No path given to file labeling backend" in run.stderr,
                "stdout_tail": run.stdout[-1200:], "stderr_tail": run.stderr[-1200:]}


def _expected_state(name: str, payloads: dict[str, bytes], state: dict, written: bool) -> bool:
    expected = payloads[name] if written else SENTINEL
    return (state.get("type") == "regular" and state.get("bytes") == len(expected)
            and state.get("sha256") == digest(expected))


def validate_synthetic(result: dict, payloads: dict[str, bytes], guarded: bool,
                       right_device: bool, failure: str | None) -> None:
    if not right_device:
        if (result["exit_code"] == 0 or not result["device_rejected"] or result["reported_completed"]
                or not all(_expected_state(p, payloads, result["fake_targets"][p], False)
                           for p in PARTITIONS)):
            raise SimulationError("Synthetic wrong-device behavior did not match expectations")
        return
    if failure is None:
        if (result["exit_code"] != 0 or not result["reported_completed"]
                or not all(_expected_state(p, payloads, result["fake_targets"][p], True)
                           for p in PARTITIONS)):
            raise SimulationError("Synthetic success did not write exactly the fake payloads")
        return
    if (not result["open_failure_reported"]
            or result["fake_targets"][failure].get("type") != "directory"):
        raise SimulationError("Injected fake-target failure was not observed")
    index = PARTITIONS.index(failure)
    for i, name in enumerate(PARTITIONS):
        if name == failure:
            continue
        written = i < index or not guarded
        if not _expected_state(name, payloads, result["fake_targets"][name], written):
            raise SimulationError("Unexpected writes after a synthetic failure")
    if guarded:
        if result["exit_code"] == 0 or result["reported_completed"] or not result["assert_failed"]:
            raise SimulationError("Guarded script did not abort on the injected failure")
    elif result["exit_code"] != 0 or not result["reported_completed"]:
        raise SimulationError("Original script did not exhibit the observed continuation")


def validate_fake_file_limit(result: dict, payloads: dict[str, bytes], guarded: bool) -> None:
    """The disposable super file was truncated before the induced I/O failure."""
    state = result["fake_targets"]["super"]
    if (not result["file_limit_failure_reported"] or state.get("type") != "regular"
            or state.get("bytes") != 0 or state.get("sha256") != digest(b"")):
        raise SimulationError("File-size limit did not expose the expected fake-file truncation")
    for name in ("boot", "dtbo"):
        if not _expected_state(name, payloads, result["fake_targets"][name], not guarded):
            raise SimulationError("Unexpected later fake-file state after the size-limit failure")
    if guarded:
        if result["exit_code"] == 0 or result["reported_completed"] or not result["assert_failed"]:
            raise SimulationError("Guarded script did not abort after the synthetic I/O failure")
    elif result["exit_code"] != 0 or not result["reported_completed"]:
        raise SimulationError("Original script did not continue after the synthetic I/O failure")


def validate_real_original_directories(result: dict) -> None:
    if (result["exit_code"] != 0 or not result["reported_completed"] or result["device_rejected"]
            or result["failed_open_targets"] != list(PARTITIONS)
            or not all(result["fake_targets"][p].get("type") == "directory" for p in PARTITIONS)):
        raise SimulationError("Real original script did not continue after three fake directory failures")


def validate_real_guarded_super(result: dict) -> None:
    if (result["exit_code"] == 0 or result["reported_completed"] or result["device_rejected"]
            or not result["assert_failed"] or result["failed_open_targets"] != ["super"]
            or result["fake_targets"]["super"].get("type") != "directory"
            or not all(result["fake_targets"][p].get("unchanged_sentinel") for p in ("boot", "dtbo"))):
        raise SimulationError("Real guarded script did not stop at the fake super directory")


def validate_real_archive(result: dict) -> None:
    if (result["exit_code"] == 0 or not result["device_rejected"] or result["reported_completed"]
            or not all(result["fake_targets"][p].get("unchanged_sentinel") for p in PARTITIONS)):
        raise SimulationError("Read-only real ZIP did not stop safely at the device check")


def run_audit(original: Path, first: Path, qemu: Path) -> dict:
    print("Hashing the two pinned ZIP inputs and QEMU; no files on a phone are accessed.", flush=True)
    identities = {
        "source": regular_identity(original, audit.SOURCE_BYTES, audit.SOURCE_SHA256),
        "first_candidate": regular_identity(first, builder.BASE_BYTES, builder.BASE_SHA),
        "qemu": regular_identity(qemu, None, QEMU_SHA256),
    }
    with zipfile.ZipFile(first, "r", allowZip64=True) as archive:
        old = archive.read(builder.SCRIPT)
        updater = archive.read(audit.BINARY)
        dtbo = archive.read("dtbo.img")
    if len(updater) != 2_353_664 or digest(updater) != audit.BINARY_SHA256:
        raise SimulationError("Updater binary did not match the known original")
    guarded = builder.guard_script(old)
    payloads = make_payloads()
    real_dtbo_payloads = make_payloads(dtbo)
    rows = []
    for label, path in (("original_zip64_device_rejected", original),
                        ("first_candidate_zip64_device_rejected", first)):
        print(f"Read-only real ZIP64 parser/device-check test: {label}", flush=True)
        result = run_sandbox(qemu, updater, path, None)
        validate_real_archive(result)
        rows.append({"scenario": label, "input": "actual ZIP, mounted read-only", **result})
        print(f"Real ZIP with fake joyeuse property and three directory targets: {label}", flush=True)
        result = run_sandbox(qemu, updater, path, PARTITIONS, fake_joyeuse=True)
        validate_real_original_directories(result)
        rows.append({"scenario": label.replace("device_rejected", "fake_device_all_open_failures"),
                     "input": "actual ZIP and script, read-only; fake property and three fake directories", **result})
    with tempfile.TemporaryDirectory(prefix="synthetica-synthetic-inputs-") as td:
        temp = Path(td)
        for is_guarded in (False, True):
            kind = "guarded" if is_guarded else "original"
            for right, failure in ((True, None), (False, None), (True, "super"),
                                   (True, "boot"), (True, "dtbo")):
                tag = "success" if right and not failure else ("wrong_device" if not right else failure + "_open_failure")
                label = kind + "_" + tag
                path = temp / (label + ".zip")
                script = synthetic_script(old, is_guarded, right)
                write_synthetic_zip(path, script, payloads)
                print(f"Actual updater / synthetic targets: {label}", flush=True)
                result = run_sandbox(qemu, updater, path, failure)
                validate_synthetic(result, payloads, is_guarded, right, failure)
                rows.append({"scenario": label, "input": "synthetic ZIP; fake property values",
                             "script_sha256": digest(script), **result})
        larger_payloads = dict(payloads)
        larger_payloads["super"] = b"SYNTHETICA-FAKE-SUPER-FILE-SIZE-LIMIT\n" * 50_000
        for is_guarded in (False, True):
            label = ("guarded" if is_guarded else "original") + "_super_file_size_limit"
            path = temp / (label + ".zip")
            write_synthetic_zip(path, synthetic_script(old, is_guarded, True), larger_payloads)
            print(f"Actual updater / induced fake-file I/O limit: {label}", flush=True)
            result = run_sandbox(qemu, updater, path, None, file_size_limit=32_768)
            validate_fake_file_limit(result, larger_payloads, is_guarded)
            rows.append({"scenario": label, "input": "synthetic ZIP; regular-file size limit",
                         "file_size_limit": 32_768, **result})
        path = temp / "guarded-real-dtbo-synthetic.zip"
        write_synthetic_zip(path, synthetic_script(old, True, True), real_dtbo_payloads)
        print("Actual updater / fake regular file: original 24 MiB DTBO member", flush=True)
        result = run_sandbox(qemu, updater, path, None)
        validate_synthetic(result, real_dtbo_payloads, True, True, None)
        rows.append({"scenario": "guarded_actual_dtbo_to_regular_file", "input": "synthetic ZIP with unchanged DTBO",
                     **result})
    print("Rehashing both source ZIPs after the read-only tests.", flush=True)
    after = {"source": regular_identity(original, audit.SOURCE_BYTES, audit.SOURCE_SHA256),
             "first_candidate": regular_identity(first, builder.BASE_BYTES, builder.BASE_SHA)}
    return {
        "schema": 1,
        "status": "all_scenarios_passed",
        "identities_before": identities,
        "identities_after": after,
        "updater_sha256": digest(updater),
        "original_script_sha256": digest(old),
        "guarded_script_sha256": digest(guarded),
        "dtbo_sha256": digest(dtbo),
        "qemu_source": QEMU_SOURCE,
        "qemu_git_blob": QEMU_BLOB,
        "isolation": {"user_mount_pid_network_namespaces": True, "chroot": True,
                      "readonly_bind_input": True, "capabilities_dropped": True,
                      "no_new_privileges": True, "fake_targets_are_regular_files_or_directories": True,
                      "device_access": False},
        "synthetic_scope": "In synthetic ZIPs only getprop expressions are replaced; image entries are fake except the separately identified DTBO case. Separate real-ZIP tests use an entirely fake Android property area and fake directory targets without modifying the ZIP or script.",
        "scenario_count": len(rows),
        "scenarios": rows,
        "limitations": [
            "QEMU emulates the bundled Android updater, not OrangeFox itself or its outer ZIP reader.",
            "The actual candidate 02 ZIP was not available locally for this test; its approved script was regenerated from the pinned first script and hash-checked.",
            "Real ZIPs stopped at the device assertion without properties, and were also run with a fake property area against directories; no real image member was extracted.",
            "The synthetic ZIP property expressions were substituted; no actual phone, physical partition, recovery, encryption, AVB, rollback, or boot was tested.",
            "The file-size-limit scenarios use a regular file; their truncation behavior cannot be assumed for a physical block device.",
            "An assertion cannot undo already-written data or detect a failure the updater does not report.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--first-candidate", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise SimulationError("Report must be a new file in an existing directory")
    result = run_audit(args.original, args.first_candidate, args.qemu)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(f"Passed {result['scenario_count']} sandbox scenarios; report: {args.report}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SimulationError, OSError, zipfile.BadZipFile, builder.GuardBuildError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
