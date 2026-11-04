#!/usr/bin/env python3
"""Build a private Joyeuse boot-layout experiment, never a flashable image.

The source is the previously verified compact host-only boot candidate. The
kernel is the separately verified Synthetica built-ins experiment. The only
command-line change replaces the original permissive SELinux request with an
explicit enforcing request. The original ramdisk and DTB are copied unchanged;
AVB signing, actual SELinux enforcement and device boot are NOT established.
No original ROM image, device or signing key is touched.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import stat
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("builtins_experiment", ROOT / "synthetica-project/build_joyeuse_builtin_experiment.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load kernel build validation")
builtins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builtins)

SOURCE_SPEC = (16_703_488, "ba4c2db0e2cfc5ba1c0a365f3582b9daabcc401f5fd746367584a53855a5bb22")
KERNEL_SPEC = (14_596_472, "4cdf79d6aec8d9b5421cb548f92c0af4693b9b71e91413e1d12f53ab5132e597")
CONFIG_SHA256 = "732918ef50347bb8c9eb88258545c25a7a6a51d132ab8f259ae9df8aa0ca9f69"
RAMDISK_SHA256 = "15ae97371512295b638a0f688b9bbea6594c33e820dae1ab5371b54a4a704413"
DTB_SHA256 = "b6bb267472a9b5cdc37a0e7b8289ee0d1dae72b40e15b935e926764dd765c126"
OLD_KERNEL_SHA256 = "58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff"
PAGE = 4096
HEADER_BYTES = 1660
OLD_TOKEN = b"androidboot.selinux=permissive"
NEW_TOKEN = b"androidboot.selinux=enforcing"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def boot_id(kernel: bytes, ramdisk: bytes, dtb: bytes) -> bytes:
    h = hashlib.sha1()
    for part in (kernel, ramdisk, b"", b"", dtb):
        h.update(part)
        h.update(struct.pack("<I", len(part)))
    return h.digest() + b"\0" * 12


def _field(raw: bytes) -> bytes:
    value, separator, tail = raw.partition(b"\0")
    if separator and any(tail):
        raise ValueError("nonzero data after a boot header string")
    try:
        value.decode("ascii")
    except UnicodeError as exc:
        raise ValueError("non-ASCII boot command line") from exc
    if any(c < 32 or c > 126 for c in value):
        raise ValueError("unsupported control character in command line")
    return value


def _align(size: int) -> int:
    return (size + PAGE - 1) & ~(PAGE - 1)


def parse(image: bytes) -> tuple[dict[str, bytes], tuple[bytes, bytes]]:
    if len(image) < PAGE or len(image) > 128 * 1024 * 1024 or image[:8] != b"ANDROID!":
        raise ValueError("invalid or oversized Android boot image")
    ksize, _, rsize, _, second, _, _, page, version, _ = struct.unpack_from("<10I", image, 8)
    recovery_size = struct.unpack_from("<I", image, 1632)[0]
    recovery_offset = struct.unpack_from("<Q", image, 1636)[0]
    header_size = struct.unpack_from("<I", image, 1644)[0]
    dtb_size = struct.unpack_from("<I", image, 1648)[0]
    if (page != PAGE or version != 2 or header_size != HEADER_BYTES or second or recovery_size
            or not ksize or not rsize or not dtb_size or any(image[HEADER_BYTES:PAGE])):
        raise ValueError("unsupported or noncanonical boot-v2 layout")
    positions = {"kernel": (PAGE, ksize), "ramdisk": (PAGE + _align(ksize), rsize)}
    positions["dtb"] = (positions["ramdisk"][0] + _align(rsize), dtb_size)
    if recovery_offset not in (0, positions["dtb"][0]):
        raise ValueError("unexpected recovery DTBO offset")
    end = positions["dtb"][0] + _align(dtb_size)
    if end != len(image):
        raise ValueError("unexpected extra or missing image bytes")
    parts = {}
    for name, (offset, size) in positions.items():
        if offset < PAGE or offset + _align(size) > len(image):
            raise ValueError("boot component out of bounds")
        parts[name] = image[offset:offset + size]
        if any(image[offset + size:offset + _align(size)]):
            raise ValueError("nonzero boot component padding")
    if image[576:608] != boot_id(parts["kernel"], parts["ramdisk"], parts["dtb"]):
        raise ValueError("boot ID checksum does not match the components")
    return parts, (_field(image[64:576]), _field(image[608:1632]))


def construct(source: bytes, kernel: bytes) -> tuple[bytes, dict]:
    if not kernel or len(kernel) > 32 * 1024 * 1024:
        raise ValueError("invalid replacement kernel length")
    parts, fields = parse(source)
    before = b"".join(fields)
    tokens = before.split()
    selinux = [t for t in tokens if t.startswith(b"androidboot.selinux=")]
    if selinux != [OLD_TOKEN] or sum(field.split().count(OLD_TOKEN) for field in fields) != 1:
        raise ValueError("expected exactly one permissive SELinux request")
    header = bytearray(source[:PAGE])
    updated = []
    for (start, end), value in zip(((64, 576), (608, 1632)), fields):
        if OLD_TOKEN in value.split():
            pattern = rb"(?<!\S)" + re.escape(OLD_TOKEN) + rb"(?!\S)"
            new, count = re.subn(pattern, NEW_TOKEN, value)
            if count != 1:
                raise ValueError("ambiguous SELinux command-line token")
        else:
            new = value
        if len(new) >= end - start:
            raise ValueError("updated command line exceeds header field")
        header[start:end] = new + b"\0" * (end - start - len(new))
        updated.append(new)
    expected_tokens = [NEW_TOKEN if t == OLD_TOKEN else t for t in tokens]
    if b"".join(updated).split() != expected_tokens:
        raise ValueError("unexpected command-line modification")
    struct.pack_into("<I", header, 8, len(kernel))
    header[576:608] = boot_id(kernel, parts["ramdisk"], parts["dtb"])
    def padded(part: bytes) -> bytes:
        return part + b"\0" * ((-len(part)) % PAGE)
    result = bytes(header) + padded(kernel) + padded(parts["ramdisk"]) + padded(parts["dtb"])
    reread, after_fields = parse(result)
    if reread != {"kernel": kernel, "ramdisk": parts["ramdisk"], "dtb": parts["dtb"]}:
        raise ValueError("rebuilt boot component readback mismatch")
    if b"".join(after_fields).split() != expected_tokens:
        raise ValueError("rebuilt boot command-line readback mismatch")
    old_header, new_header = bytearray(source[:PAGE]), bytearray(result[:PAGE])
    for start, end in ((8, 12), (64, 576), (576, 608), (608, 1632)):
        new_header[start:end] = old_header[start:end]
    if new_header != old_header:
        raise ValueError("unexpected boot header modification")
    return result, {"source_kernel_sha256": sha(parts["kernel"]), "ramdisk_sha256": sha(parts["ramdisk"]),
                    "dtb_sha256": sha(parts["dtb"]), "source_cmdline_sha256": sha(before),
                    "candidate_cmdline_sha256": sha(b"".join(after_fields)),
                    "boot_id_sha1_not_signature": result[576:596].hex()}


def read_locked(path: Path, size: int, expected_sha: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            raise ValueError("locked input is not a regular file of the expected size")
        data = f.read(size + 1)
        after = os.fstat(f.fileno())
        path_stat = os.stat(path, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if identity(before) != identity(after) or identity(before) != identity(path_stat):
            raise ValueError("locked input changed while being read")
    if len(data) != size or sha(data) != expected_sha:
        raise ValueError("locked input size or SHA-256 mismatch")
    return data


def write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def build(source: Path, kernel: Path, config: Path, status_path: Path, output: Path) -> dict:
    private_root = (ROOT / ".work-private").resolve()
    output = output.absolute()
    if (output.exists() or output.is_symlink() or "NOT-FOR-FLASH" not in output.name
            or not output.parent.is_dir() or not output.resolve().is_relative_to(private_root)):
        raise ValueError("output must be a new NOT-FOR-FLASH directory inside .work-private")
    source_data = read_locked(source, *SOURCE_SPEC)
    kernel_data = read_locked(kernel, *KERNEL_SPEC)
    config_data = config.read_bytes()
    if sha(config_data) != CONFIG_SHA256:
        raise ValueError("kernel configuration differs from the verified build")
    status = json.loads(status_path.read_text())
    if (status.get("status") != "COMPILED_ONLY_DO_NOT_FLASH" or status.get("image_sha256") != KERNEL_SPEC[1]
            or status.get("config_sha256") != CONFIG_SHA256 or status.get("security_config_unchanged") is not True
            or status.get("embedded_config_matches_generated") is not True or status.get("boot_test") != "NOT_RUN"):
        raise ValueError("kernel build status is not the pinned non-flashable build")
    builtins.check_config(builtins.verified_baseline(ROOT / "artifacts/generated.config.txt"), config_data.decode())
    builtins.verify_embedded_config(gzip.decompress(kernel_data), config_data)
    image, checks = construct(source_data, kernel_data)
    if (checks["source_kernel_sha256"] != OLD_KERNEL_SHA256 or checks["ramdisk_sha256"] != RAMDISK_SHA256
            or checks["dtb_sha256"] != DTB_SHA256):
        raise ValueError("private source boot components differ from pinned references")
    output.mkdir(mode=0o700)
    image_path = output / "DO-NOT-FLASH-joyeuse-boot.img"
    write_exclusive(image_path, image)
    if read_locked(image_path, len(image), sha(image)) != image:
        raise ValueError("boot output failed readback")
    report = {
        "status": "HOST_ONLY_DO_NOT_FLASH", "device": "joyeuse / miatoll", "flashable": False,
        "image_bytes": len(image), "image_sha256": sha(image),
        "source_compact_boot_sha256": SOURCE_SPEC[1], "kernel_sha256": KERNEL_SPEC[1],
        **checks, "command_line_change": "androidboot.selinux=permissive -> androidboot.selinux=enforcing",
        "selinux_runtime_enforcing": "NOT_VERIFIED", "avb_or_boot_signature": "NOT_VERIFIED",
        "vendor_module_abi_and_signatures": "NOT_VERIFIED", "physical_device_test": "NOT_RUN",
        "original_ramdisk_security_note": "Original ramdisk is unchanged; KEEPVERITY=false, KEEPFORCEENCRYPT=false and AVB mount configuration require separate review.",
        "spatialflow_added": False,
    }
    write_exclusive(output / "STATUS.json", (json.dumps(report, indent=2) + "\n").encode())
    write_exclusive(output / "README-DO-NOT-FLASH.txt", (
        "DO NOT FLASH. Host-only boot layout experiment, not a ROM or installer.\n"
        "No AVB signature, physical boot, module ABI/signature or runtime SELinux test.\n"
        "The header requests enforcing instead of permissive; runtime is NOT verified.\n"
        "Original ramdisk and DTB are unchanged. Original ramdisk contains security-relevant\n"
        "KEEPVERITY=false and KEEPFORCEENCRYPT=false; AVB mount configuration remains unverified.\n"
        "No original ROM, partitions, device or signing key was modified.\n"
    ).encode())
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-boot", type=Path, required=True)
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--status", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.source_boot, args.kernel, args.config, args.status, args.output), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError, struct.error) as exc:
        print(f"BOOT EXPERIMENT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
