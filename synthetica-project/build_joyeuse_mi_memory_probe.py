#!/usr/bin/env python3
"""Compile-only probe for a possible mi_memory built-in on Joyeuse.

The donor is from sm8250, NOT established as the Joyeuse implementation.
This deliberately produces no kernel, ROM or flashable artifact. It prepares
an isolated, pinned source tree for compiler diagnostics and future port work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

DONOR_REPO = "projects-nexus/nexus_kernel_xiaomi_sm8250"
DONOR_COMMIT = "d26c193dcd97812a9a565ac40fe5092cc9a18fbf"
DONOR_BLOBS = {
    "Kconfig": "5fe1d0cd3274918afadec6d1189115462aa9c994",
    "Makefile": "f96f30ef6a0464d517d26faacbe476c889ec9d47",
    "mem_interface.c": "638956c1f8cd82943dad25eaaa7adc8e1e010fe0",
    "mem_interface.h": "d96fc948fd920522887b40b535a78888f8466bb6",
    "mi_dram_info.c": "77055c6ee66fead3a1e7cdb6debf69d24a9a01fb",
    "mi_memory_sysfs.c": "ec999622b8fa481da57c07a42419db2a3c6254af",
    "mi_memory_sysfs.h": "6f6d256a591eb2b5be6001b24790a4642e49a9b8",
    "mi_ufs_info.c": "dddf7d8d115bf372f8ec1b8dcc7075f439b2c353",
    "mv.c": "d07443be3aae124eee9590ac5299874cb51cf238",
    "mv.h": "da6ab75794cd89071ab29454fe94624db83b7634",
}
BASE_SHA256 = {
    "drivers/misc/Kconfig": "2d0a2adc89e32bf50f6a012d3bf5a2fb6a03b1023245cb1877b08d61331d0b35",
    "drivers/misc/Makefile": "113b3ac346179e006d095486d4a24c30f17171158c6bcbcbbf56a209c1410f0b",
    "drivers/scsi/ufs/ufshcd.c": "299975ff323fdfd7b48506f3fca6d5a6a4bc54379da2db310eda3027cc7875b4",
}


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def replace_exact(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise ValueError(f"expected {count} exact anchor(s), found {text.count(old)}: {old[:75]!r}")
    return text.replace(old, new)


def fetch_donor(destination: Path) -> None:
    if destination.exists():
        raise ValueError("refusing to overwrite donor directory")
    destination.mkdir(parents=True)
    for name, oid in DONOR_BLOBS.items():
        cmd = ["gh", "api", "-H", "Accept: application/vnd.github.raw+json", f"repos/{DONOR_REPO}/git/blobs/{oid}"]
        data = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
        if git_blob_id(data) != oid:
            raise ValueError(f"donor Git blob mismatch: {name}")
        (destination / name).write_bytes(data)
    print(f"Fetched {len(DONOR_BLOBS)} pinned GPL-kernel source blobs from {DONOR_REPO}@{DONOR_COMMIT}")


def apply_probe(tree: Path, donor: Path) -> None:
    tree, donor = tree.resolve(), donor.resolve()
    target = tree / "drivers/misc/mi-memory"
    if target.exists():
        raise ValueError("refusing to overwrite an existing mi-memory tree")
    base = {}
    for name, expected in BASE_SHA256.items():
        data = (tree / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"base source differs from pinned tree: {name}")
        base[name] = data.decode("utf-8")
    files = {}
    for name, expected in DONOR_BLOBS.items():
        data = (donor / name).read_bytes()
        if git_blob_id(data) != expected:
            raise ValueError(f"donor Git blob mismatch: {name}")
        files[name] = data.decode("utf-8")

    files["Kconfig"] = replace_exact(files["Kconfig"], '\ttristate "show memory info"', '\tbool "Experimental mi memory info (compile-only)"')
    files["Kconfig"] = replace_exact(files["Kconfig"], "\tdepends on MIHW", "\tdepends on SCSI_UFSHCD && SCSI_UFS_QCOM && PROC_FS")
    files["mi_memory_sysfs.c"] = replace_exact(
        files["mi_memory_sysfs.c"],
        "\tmi_memory = kzalloc(sizeof(struct memory_info), GFP_KERNEL);\n",
        "\tmi_memory = kzalloc(sizeof(struct memory_info), GFP_KERNEL);\n\tif (!mi_memory)\n\t\treturn -ENOMEM;\n",
    )
    # Avoid dereferencing absent HBA/SCSI pointers in the ten donor callbacks.
    # This does not establish that any remaining sysfs/proc handler is safe.
    files["mi_ufs_info.c"] = replace_exact(
        files["mi_ufs_info.c"],
        "\tsend_ufs_hba_data(&hba, &sdev);\n",
        "\tsend_ufs_hba_data(&hba, &sdev);\n\tif (!hba || !sdev)\n\t\treturn -ENODEV;\n",
        10,
    )
    # The target keeps CONFIG_DEBUG_FS=n, so debug-only UFS structures do not
    # exist. Do not enable debugfs or fabricate statistics to satisfy the port.
    # These four diagnostic attributes are deliberately absent in this probe.
    ufs_info = files["mi_ufs_info.c"]
    ufs_info = replace_exact(ufs_info,
        "static ssize_t tag_stats_show(struct device *dev, struct device_attribute *attr, char *buf)\n",
        "#if 0 /* Incompatible debug statistics are excluded from this compile-only probe. */\nstatic ssize_t tag_stats_show(struct device *dev, struct device_attribute *attr, char *buf)\n")
    ufs_info = replace_exact(ufs_info, "static DEVICE_ATTR_RW(req_stats);\n", "static DEVICE_ATTR_RW(req_stats);\n#endif /* incompatible debug statistics */\n")
    ufs_info = replace_exact(ufs_info,
        "\t&dev_attr_tag_stats.attr,\n\t&dev_attr_err_state.attr,\n\t&dev_attr_err_reason.attr,\n\t&dev_attr_req_stats.attr,\n",
        "#if 0 /* Incompatible debug statistics: not provided by this probe. */\n\t&dev_attr_tag_stats.attr,\n\t&dev_attr_err_state.attr,\n\t&dev_attr_err_reason.attr,\n\t&dev_attr_req_stats.attr,\n#endif\n")
    files["mi_ufs_info.c"] = ufs_info
    # These UFS descriptor offsets exist in the pinned donor's ufs.h but not
    # the target header. They are probe constants, not proof of device ABI.
    files["mi_memory_sysfs.h"] = replace_exact(files["mi_memory_sysfs.h"],
        '#include "../../scsi/ufs/ufs.h"\n',
        '#include "../../scsi/ufs/ufs.h"\n'
        '#define DEVICE_DESC_PARAM_UFS_FEAT 0x1F\n'
        '#define DEVICE_DESC_PARAM_FFU_TMT 0x20\n'
        '#define DEVICE_DESC_PARAM_Q_DPTH 0x21\n'
        '#define DEVICE_DESC_PARAM_DEV_VER 0x22\n'
        '#define DEVICE_DESC_PARAM_NUM_SEC_WPA 0x24\n'
        '#define DEVICE_DESC_PARAM_PSA_MAX_DATA 0x25\n'
        '#define DEVICE_DESC_PARAM_PSA_TMT 0x29\n'
        '#define DEVICE_DESC_PARAM_PRDCT_REV 0x2A\n'
        '#define GEOMETRY_DESC_PARAM_DEV_CAP 0x04\n')
    inter = files["mem_interface.c"]
    inter = replace_exact(inter,
        "int ufshcd_read_desc_mi(struct ufs_hba *hba, enum desc_idn desc_id,\n\t\tint desc_index, void *buf, u32 size)\n{\n\tint ret = 0;\n",
        "int ufshcd_read_desc_mi(struct ufs_hba *hba, enum desc_idn desc_id,\n\t\tint desc_index, void *buf, u32 size)\n{\n\tint ret = 0;\n\n\tif (!hba)\n\t\treturn -ENODEV;\n")
    inter = replace_exact(inter, "\tu8 *desc_buf;\n", "\tu8 *desc_buf;\n\n\tif (!hba)\n\t\treturn -ENODEV;\n")
    inter = replace_exact(inter,
        "\tu8 desc_buf[8] = {0};\n\tint ret;\n",
        "\tu8 desc_buf[8] = {0};\n\tint ret;\n\n\tif (!hba)\n\t\treturn -ENODEV;\n")
    files["mem_interface.c"] = inter

    ufs = base["drivers/scsi/ufs/ufshcd.c"]
    # Linkable by built-ins only: do not export these routines to modules.
    ufs = replace_exact(ufs, "static int ufshcd_read_desc_param(", "int ufshcd_read_desc_param(")
    ufs = replace_exact(ufs, "static int ufshcd_read_string_desc(", "int ufshcd_read_string_desc(")
    ufs = replace_exact(ufs,
        "static int ufshcd_slave_configure(struct scsi_device *sdev)\n",
        "#if IS_ENABLED(CONFIG_MI_MEMORY_SYSFS)\nextern void set_ufs_hba_data(struct scsi_device *sdev);\n#endif\n\nstatic int ufshcd_slave_configure(struct scsi_device *sdev)\n")
    ufs = replace_exact(ufs,
        "\tufshcd_crypto_setup_rq_keyslot_manager(hba, q);\n",
        "\tufshcd_crypto_setup_rq_keyslot_manager(hba, q);\n#if IS_ENABLED(CONFIG_MI_MEMORY_SYSFS)\n\t/* Donor uses LUN 2; hardware applicability is NOT established. */\n\tif (sdev->lun == 2)\n\t\tset_ufs_hba_data(sdev);\n#endif\n")
    if "EXPORT_SYMBOL(ufshcd_read_desc_param)" in ufs or "EXPORT_SYMBOL(ufshcd_read_string_desc)" in ufs:
        raise ValueError("probe must not export UFS internals to modules")
    base["drivers/scsi/ufs/ufshcd.c"] = ufs
    if "mi-memory/Kconfig" in base["drivers/misc/Kconfig"] or "mi-memory/" in base["drivers/misc/Makefile"]:
        raise ValueError("existing mi-memory integration found")
    base["drivers/misc/Kconfig"] += '\n# Compile-only Joyeuse experiment.\nsource "drivers/misc/mi-memory/Kconfig"\n'
    base["drivers/misc/Makefile"] += '\n# Compile-only Joyeuse experiment.\nobj-$(CONFIG_MI_MEMORY_SYSFS) += mi-memory/\n'

    target.mkdir(parents=True)
    for name, text in files.items():
        (target / name).write_text(text)
    for name, text in base.items():
        (tree / name).write_text(text)
    print(json.dumps({"probe": "COMPILE_ONLY_DO_NOT_FLASH", "donor_repository": DONOR_REPO,
                      "donor_commit": DONOR_COMMIT, "donor_matches_joyeuse": "NOT_PROVEN",
                      "omitted_unsupported_debug_attributes": ["tag_stats", "err_state", "err_reason", "req_stats"],
                      "warning": "UFS callback, device behavior, lifetime and sysfs safety are unverified"}, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--destination", type=Path, required=True)
    a = sub.add_parser("apply")
    a.add_argument("--tree", type=Path, required=True)
    a.add_argument("--donor", type=Path, required=True)
    args = p.parse_args()
    if args.command == "fetch":
        fetch_donor(args.destination)
    else:
        apply_probe(args.tree, args.donor)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"MI-MEMORY PROBE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
