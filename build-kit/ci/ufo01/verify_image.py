#!/usr/bin/env python3
"""What an Image can and cannot prove.

Two rounds of this project were wasted on a question this script got wrong.

Round 1 read the gzip bytes and reported SuSFS present and everything else missing.
After that was fixed, round 2 read the decompressed image and reported all six
features present -- but the numbers were absurd (2, 3, 3, 142) and nobody looked at
what those numbers meant. Here is what they meant:

  `lru_gen` (2 hits)   one is a vmstat counter key, one is an error message from
                       init_lru_gen. Neither is evidence the code runs. The debugfs
                       node name `lru_gen_full` is not in the image at all, which
                       might mean the initcall was dropped or might mean the linker
                       folded the literal. Strings cannot tell those apart.
  `uclamp` (3 hits)    actually good: `uclamp.min` and `uclamp.max` are sysfs
                       attribute names, so the sched group registered them.
  `walt_` (3 hits)     `walt_stats.nr_big_tasks` is a tracepoint field, which only
                       exists when CONFIG_SCHED_WALT emits it.

So the honest thing for this script to do is report the strong ones, name the weak
ones as weak, and refuse to guess about the rest. The authoritative answer for
"is this function in the kernel" is System.map, which the build now publishes, and
`root_stack_report.py`, which reads it.

Exit code is 0 unless a STRONG marker is missing. That is a deliberate retreat from
the previous behaviour: it failed the build on the absence of a string that cannot
prove anything, which is how a real missing feature could hide behind a noisy check.
"""
from __future__ import annotations

import gzip
import re
import sys

# Only marker that survive the linker AND only appear when the code is reachable.
STRONG: list[tuple[str, bytes, str]] = [
    ("UCLAMP", rb"uclamp\.min\x00", "sysfs attribute registered by CONFIG_UCLAMP_TASK_GROUP"),
    ("UCLAMP", rb"uclamp\.max\x00", "its pair; both must be present"),
    ("WALT", rb"walt_stats\.nr_big_tasks", "tracepoint field emitted only by CONFIG_SCHED_WALT"),
    ("KernelSU", rb"ksu_driver", "the KSU driver struct, not a borrowed symbol"),
]

# Reported, never judged. A hit here says a name exists, nothing more.
WEAK: list[tuple[str, bytes]] = [
    ("MGLRU", rb"lru_gen"),
    ("UCLAMP", rb"uclamp"),
    ("WALT", rb"walt_"),
    ("KernelSU", rb"ksu_"),
    ("SuSFS", rb"susfs"),
    ("NoMount", rb"nomount"),
]

MUST_NOT: list[tuple[str, bytes]] = [
    ("Kinesis stock KSU", rb"drivers/staging/kernelsu"),
]


def main(path: str) -> int:
    with gzip.open(path, "rb") as f:
        raw = f.read()

    if not raw.startswith(b"\x00\x80\x86\x14") and b"ARMd" not in raw[0x30:0x40]:
        print("bukan Image arm64 yang sah", file=sys.stderr)
        return 2

    print(f"ukuran setelah dibuka: {len(raw):,} byte")
    ver = re.search(rb"Linux version ([0-9][^\x00 ]+)", raw)
    print(f"versi: {ver.group(1).decode() if ver else 'TIDAK DITEMUKAN'}")
    print()

    missing = []
    print("KUAT (gagal bila hilang):")
    for label, pattern, note in STRONG:
        n = len(re.findall(pattern, raw))
        print(f"  {label:10} {'ADA' if n else 'HILANG':6} ({n:3})  {note}")
        if not n:
            missing.append(label)
    print()

    print("LEMAH (tidak dinilai; hanya menunjukkan nama ada):")
    for label, pattern in WEAK:
        n = len(re.findall(pattern, raw))
        print(f"  {label:10} {n:4} kemunculan")
    print()

    for label, pattern in MUST_NOT:
        n = len(re.findall(pattern, raw))
        print(f"  {label:18} {'ADA' if n else 'tidak ada':10} ({n})")
    print()

    print("Untuk MGLRU, SuSFS dan NoMount, Image tidak bisa menjawab. Yang menjawab")
    print("adalah System.map (diterbitkan build ini) lewat root_stack_report.py:")
    print("symbol yang ada = fungsi benar-benar ditautkan; yang tidak ada = tidak.")
    print()

    if missing:
        print(f"HILANG: {', '.join(sorted(set(missing)))} -- ini penanda kuat, bukan tebakan.")
        return 1
    print("semua penanda KUAT ada.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
