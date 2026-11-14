#!/usr/bin/env python3
"""Check what actually ended up inside Image.gz, not what the config claimed.

A kernel can build with CONFIG_LRU_GEN=y and still not carry MGLRU, if a patch half
applied. These are the strings that only exist when the code is really there.
"""
import gzip
import re
import sys

CHECKS = [
    ("MGLRU",          rb"lru_gen",                     "mm/vmscan MGLRU"),
    ("UCLAMP",         rb"uclamp",                      "sched uclamp"),
    ("WALT",           rb"walt_",                       "window assisted load tracking"),
    ("KernelSU",       rb"ksu_driver",                  "KernelSU core present"),
    ("SuSFS",          rb"susfs",                       "SUSFS v2"),
    ("NoMount",        rb"nomount",                     "NoMount"),
]
# Absent-by-design is worth reporting too: it means a config did NOT take effect.
MUST_NOT = [
    ("Kinesis stock KSU", rb"drivers/staging/kernelsu"),
]

raw = gzip.open(sys.argv[1], "rb").read()  # decompressed: strings only exist here
if not raw.startswith(b"\x1f\x8b") and len(raw) < 1_000_000:
    sys.exit("not a kernel image")
print(f"ukuran setelah dibuka: {len(raw):,} byte")
ver = re.search(rb"Linux version ([0-9][^\x00 ]+)", raw)
print(f"versi: {ver.group(1).decode() if ver else 'TIDAK DITEMUKAN'}")
print()

bad = 0
for label, needle, note in CHECKS:
    n = len(re.findall(needle, raw, re.I))
    mark = "ADA" if n else "HILANG"
    if not n:
        bad += 1
    print(f"  {label:18} {mark:7} ({n} kemunculan) -- {note}")
for label, needle in MUST_NOT:
    n = len(re.findall(needle, raw))
    print(f"  {label:18} {'ADA' if n else 'tidak ada':7} ({n})")
print()
if bad:
    print(f"{bad} fitur HILANG dari Image.")
    sys.exit(1)
print("semua fitur yang diminta ada di dalam Image.")
