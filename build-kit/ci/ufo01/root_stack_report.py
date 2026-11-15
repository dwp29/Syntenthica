#!/usr/bin/env python3
"""Answer "is this feature really in the kernel" from System.map.

Why not Image.gz
----------------
The Image holds string literals, and whether a particular literal survives the
compiler and linker depends on inlining, on which branch folded, and on whether the
string was merged with an identical one elsewhere. Three rounds of grepping produced
three different answers from the same code:

  * `lru_gen` present, but as a vmstat key. Looks like proof, is not.
  * `lru_gen_full` absent. Looks like disproof, is not -- the literal can be folded.
  * `susfs` present 142 times, but SuSFS was still not demonstrably reachable from
    any syscall path, because a name in `.rodata` does not say who calls it.

System.map has none of those failure modes. A symbol appears there if and only if
the linker kept the function or object, and the address tells you whether it lives in
.text (code) or .rodata/.data. A feature that was compiled but never wired in shows up
as a set of symbols that nothing in the call graph references -- which this script
can flag by looking for the entry point the rest of the kernel is supposed to call.

Usage:
    root_stack_report.py System.map [--verbose]
"""
from __future__ import annotations

import pathlib
import re
import sys

# Each entry: label, a regex over symbol names, and the symbols that must be present
# for the feature to be wired in rather than merely compiled.
#
# The "required" list is the difference between this and a `grep`. For MGLRU, having
# lru_gen_* functions is necessary but not sufficient: the kernel has to call
# lru_gen_enabled() and lru_gen_add_folio() from the reclaim path, and those are
# either in the symbol table or they are not.
FEATURES: list[tuple[str, str, list[str], str]] = [
    ("MGLRU",
     r"^lru_gen|_lru_gen_",
     ["lru_gen_enabled", "lru_gen_add_folio", "lru_gen_del_folio", "lru_gen_seq_show"],
     "multi-generational LRU: the reclaim path must be able to call into it"),
    ("UCLAMP",
     r"[Uu]clamp",
     ["uclamp_eff_get", "uclamp_update_active", "uclamp_rq_inc"],
     "task and CPU performance clamps; the scheduler must reach the update path"),
    ("WALT",
     r"^(walt|sched_walt|update_|walt_)|_walt_",
     ["walt_update_task_ravg", "walt_rotate_work_func"],
     "window-assisted load tracking: the tick must feed the window"),
    ("KernelSU",
     r"^(ksu_|kernelsu)|ksu_driver",
     ["ksu_driver", "ksu_handle_execveat", "ksu_handle_faccessat"],
     "KernelSU-Next hooks; the driver struct alone is not enough"),
    ("SuSFS",
     r"susfs",
     ["susfs_init", "susfs_is_current_proc_umounted"],
     "SuSFS 2.3.0; init plus the query the VFS path calls"),
    ("NoMount",
     r"nomount",
     ["nomount_umount", "nomount_init"],
     "NoMount umount interception"),
]


def parse(path: pathlib.Path) -> dict[str, tuple[str, str]]:
    """name -> (type letter, address)."""
    syms: dict[str, tuple[str, str]] = {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            syms[parts[2]] = (parts[1], parts[0])
    return syms


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = pathlib.Path(argv[1])
    verbose = "--verbose" in argv
    if not path.exists():
        print(f"{path} tidak ada. Build ini tidak menerbitkan System.map.", file=sys.stderr)
        return 2

    syms = parse(path)
    print(f"{path.name}: {len(syms):,} simbol")
    print()

    failed = 0
    for label, pattern, required, why in FEATURES:
        found = sorted(s for s in syms if re.search(pattern, s))
        missing = [r for r in required if r not in syms]

        if not found:
            verdict = "TIDAK DIKOMPILASI"
            failed += 1
        elif len(missing) == len(required):
            verdict = "DIKOMPILASI, TIDAK TERSAMBUNG"
            failed += 1
        elif missing:
            verdict = "SEBAGIAN TERSAMBUNG"
            failed += 1
        else:
            verdict = "TERSAMBUNG"

        print(f"{label:10} {verdict:26} {len(found):3} simbol")
        print(f"           {why}")
        if verbose:
            for s in found[:12]:
                kind, addr = syms[s]
                print(f"             {addr} {kind} {s}")
            if len(found) > 12:
                print(f"             ... dan {len(found) - 12} lagi")
        if missing:
            print(f"           tidak ada: {', '.join(missing)}")
        print()

    if failed:
        print(f"{failed} fitur tidak terbukti tersambung. Ini bacaan dari tabel simbol,")
        print("bukan dari string di Image.")
        return 1
    print("semua fitur dikompilasi DAN titik masuknya ada di tabel simbol.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
