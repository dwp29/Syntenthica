#!/usr/bin/env python3
"""Prove each requested feature is reachable from code the kernel actually runs.

Why this file exists, and why the two before it were wrong
----------------------------------------------------------
"Is feature X in the kernel" was answered three times, wrongly each time:

  Round 1  grep Image.gz            -> "MGLRU ADA (2)". One of the two hits was a
                                       vmstat counter key. The other was an error
                                       message printed by the init function. Neither
                                       says anything about whether MGLRU runs.
  Round 2  grep decompressed Image  -> "lru_gen_full HILANG, so the initcall was
                                       dropped". Wrong: the linker folded that
                                       literal. Absence of a string is not absence of
                                       a feature.
  Round 3  grep System.map for a    -> "MGLRU not wired". Wrong: the symbol list was
           hand-invented list           invented from memory of kernel 6.x, where the
                                       helper is lru_gen_add_folio. This tree's MGLRU
                                       works on struct page and its helper is
                                       lru_gen_eviction.

The lesson is the same every time: a name is not a call.

What this script checks instead
-------------------------------
Three kinds of evidence, strongest first, all read from the built artefacts:

  CALL     A BL instruction inside a named caller resolves to the feature's
           function. This is the compiler saying "this code runs that code".
           Proven by disassembly, not by a string or a symbol name.

  POINTER  A named struct in .data contains the address of the feature's function.
           Used for features that the kernel invokes through an operations table,
           where there is no BL to find -- NoMount installs nm_dir_lookup into
           nm_dir_iops and the VFS calls through the pointer.

  DATA     An ADRP+ADD pair inside a named consumer resolves exactly to the
           feature's data symbol. Used where the feature is entirely inlined and
           therefore has no function symbol at all -- UCLAMP compiles to reads of
           uclamp_default pasted into the scheduler.

A feature is PROVEN only if at least one chain succeeds end to end. "Found symbols
but no caller" is reported as NOT PROVEN, which is different from ABSENT (not
compiled at all) and different again from UNKNOWN (inputs cannot answer). Only
ABSENT and NOT PROVEN fail the build; UNKNOWN fails it too, because an unanswerable
question must never be recorded as a pass.

Usage:
    prove_features.py Image.gz System.map
    prove_features.py --self-test

Caller names were re-read from the 4.14.357 source; the 4.14.344 names were not
assumed to carry over, because they do not (wake-side WALT is a helper here).
"""
from __future__ import annotations

import gzip
import pathlib
import struct
import sys

ARM64_TEXT_OFFSET = 0x800


# --------------------------------------------------------------------------- table
#
# (feature, chain, note)
#   chain = [(kind, caller_or_struct, target, what_it_shows), ...]
#
# Every caller and target here was read out of the source tree, not remembered.
# Where the first name I guessed did not exist, the source told me the real one;
# the fact that a name is *wrong* is exactly what round 3 got caught on, so the
# checks below are validated against a real build before they are trusted.

CHAINS: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("MGLRU", [
        ("CALL", "shrink_page_list", "lru_gen_eviction",
         "reclaim path accounts for generations"),
        ("CALL", "shrink_active_list", "lru_gen_eviction",
         "second reclaim entry point (optional)"),
    ]),
    ("UCLAMP", [
        ("CALL", "__schedule", "uclamp_rq_inc_id",
         "the scheduler applies the clamp on every context switch"),
        ("DATA", "sched_init", "uclamp_default",
         "the per-cpu clamp arrays are initialised at boot"),
    ]),
    ("WALT", [
        ("CALL", "__schedule", "update_task_ravg",
         "the switch path records the window"),
        # 4.14.357 moved the wake-side accounting into a helper of its own; the
        # caller is not try_to_wake_up in this tree. Read from source, not assumed.
        ("CALL", "walt_try_to_wake_up", "update_task_ravg",
         "the wake path records the window"),
    ]),
    ("KernelSU", [
        ("CALL", "do_execveat_common", "ksu_handle_execveat",
         "exec is intercepted before the new program runs"),
    ]),
    ("SuSFS", [
        ("CALL", "link_path_walk", "susfs_is_inode_sus_path",
         "path resolution asks whether an inode is hidden"),
    ]),
    ("NoMount", [
        ("POINTER", "nm_dir_iops", "nm_dir_lookup",
         "the directory operations table points at the NoMount lookup"),
        ("POINTER", "nm_dir_fops", "nm_dir_iterate_dir",
         "and the file operations table at the directory iterator"),
    ]),
]

# Which chains are enough on their own. The second MGLRU and the second UCLAMP
# entries are corroboration on some build trees, not requirements: a kernel may
# legitimately call the feature from only one of them.
REQUIRED = {
    "MGLRU": 1,
    "UCLAMP": 1,
    "WALT": 2,     # both the switch and the wake path; one alone would be suspicious
    "KernelSU": 1,
    "SuSFS": 1,
    "NoMount": 1,
}


# ------------------------------------------------------------------------ parsing
def parse_map(path: pathlib.Path) -> dict[str, int]:
    syms: dict[str, int] = {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                syms[parts[2]] = int(parts[0], 16)
            except ValueError:
                pass
    return syms


def read_image(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def find_symbol(syms: dict[str, int], name: str) -> tuple[str, int] | None:
    """Exact, then the compiler's own suffix (foo.llvm.1234, foo.constprop.0)."""
    if name in syms:
        return name, syms[name]
    # Clang appends its own suffixes: shrink_page_list.llvm.12208889867182419374
    for cand, addr in syms.items():
        if cand.startswith(name + "."):
            return cand, addr
    return None


def function_size(syms: dict[str, int], addr: int) -> int:
    after = [v for v in syms.values() if v > addr]
    return (min(after) - addr) if after else 0x2000


# --------------------------------------------------------------------- decoders
def bl_targets(image: bytes, syms: dict[str, int], start: int, size: int) -> list[tuple[int, int]]:
    """(pc, target) for every BL in the function."""
    base = start - syms["_stext"] + ARM64_TEXT_OFFSET
    out: list[tuple[int, int]] = []
    if base < 0 or base + size > len(image):
        return out
    for i in range(0, size - 3, 4):
        word = struct.unpack_from("<I", image, base + i)[0]
        if (word >> 26) != 0b100101:
            continue
        imm = word & 0x03FFFFFF
        if imm & 0x02000000:
            imm -= 0x04000000
        out.append((start + i, start + i + (imm << 2)))
    return out


def data_refs(image: bytes, syms: dict[str, int], start: int, size: int, target: int) -> list[int]:
    """Program counters of ADRP+ADD pairs inside the function that resolve to target."""
    base = start - syms["_stext"] + ARM64_TEXT_OFFSET
    out: list[int] = []
    if base < 0 or base + size > len(image):
        return out
    # Words available. size//4, not (size-8)//4: the previous version silently
    # shortened a 3-word window to 1 word and every ADRP check returned nothing.
    # The self-test caught it; on the real build it would have looked like
    # "UCLAMP not wired", the exact false negative this file exists to stop.
    n = max(0, size // 4)
    if n < 2:
        return out
    words = struct.unpack_from("<%dI" % n, image, base)
    for i in range(n - 1):
        w0 = words[i]
        if (w0 & 0x9F000000) != 0x90000000:  # ADRP
            continue
        rd = w0 & 0x1F
        imm = (((w0 >> 5) & 0x7FFFF) << 2) | ((w0 >> 29) & 0x3)
        if imm & 0x100000:
            imm -= 0x200000
        pc = start + i * 4
        page = (pc & ~0xFFF) + (imm << 12)
        if page != (target & ~0xFFF):
            continue
        for j in range(i + 1, min(i + 4, n)):
            w1 = words[j]
            if (w1 & 0xFF800000) != 0x91000000:  # ADD immediate, 64-bit
                continue
            if (w1 & 0x1F) != rd or ((w1 >> 5) & 0x1F) != rd:
                continue
            imm12 = (w1 >> 10) & 0xFFF
            if (w1 >> 22) & 0x3 == 1:
                imm12 <<= 12
            if page + imm12 == target:
                out.append(pc)
            break
    return out


def struct_holds(image: bytes, syms: dict[str, int], struct_va: int, value: int,
                 span: int = 0x100) -> int | None:
    """Offset inside [struct_va, struct_va+span) whose 8-byte word equals value."""
    base = struct_va - syms["_stext"] + ARM64_TEXT_OFFSET
    if base < 0:
        return None
    # A table placed near the end of the image must still be scannable: clamp to what
    # exists instead of refusing. Refusing would report "no pointer" for a struct the
    # linker happened to put last, which reads as "feature not wired".
    span = min(span, len(image) - base)
    for off in range(0, span - 7, 8):
        if struct.unpack_from("<Q", image, base + off)[0] == value:
            return off
    return None


# ------------------------------------------------------------------------- checks
def check(image: bytes, syms: dict[str, int], kind: str, caller: str, target: str):
    """Returns (ok, detail) or (None, reason) when the inputs cannot answer."""
    c = find_symbol(syms, caller)
    t = find_symbol(syms, target)
    if c is None:
        return None, f"{caller} tidak ada di System.map"
    if t is None:
        return None, f"{target} tidak ada di System.map"
    c_name, c_addr = c
    t_name, t_addr = t

    if kind == "CALL":
        for pc, tgt in bl_targets(image, syms, c_addr, function_size(syms, c_addr)):
            if tgt == t_addr:
                return True, f"BL di {c_name}+{pc - c_addr:#x} menuju {t_name}"
        return False, f"tidak ada BL ke {t_name} di dalam {c_name}"

    if kind == "DATA":
        refs = data_refs(image, syms, c_addr, function_size(syms, c_addr), t_addr)
        if refs:
            return True, f"{c_name}+{refs[0] - c_addr:#x} memuat alamat {t_name}"
        return False, f"{c_name} tidak memuat alamat {t_name}"

    if kind == "POINTER":
        off = struct_holds(image, syms, c_addr, t_addr)
        if off is not None:
            return True, f"{c_name}+{off:#x} berisi pointer ke {t_name}"
        return False, f"{c_name} tidak berisi pointer ke {t_name}"

    return None, f"jenis bukti tidak dikenal: {kind}"


def run(image_path: pathlib.Path, map_path: pathlib.Path) -> int:
    image = read_image(image_path)
    syms = parse_map(map_path)
    if "_stext" not in syms:
        print("System.map tidak punya _stext; bukan map kernel", file=sys.stderr)
        return 2

    print(f"Image  : {len(image):,} byte")
    print(f"Simbol : {len(syms):,}")
    print()

    failures: list[str] = []
    unknowns: list[str] = []

    for feature, chain in CHAINS:
        proven: list[str] = []
        unproven: list[str] = []
        unknown: list[str] = []

        for kind, caller, target, what in chain:
            ok, detail = check(image, syms, kind, caller, target)
            if ok is True:
                proven.append(f"{what}\n             {detail}")
            elif ok is False:
                unproven.append(f"{what}\n             {detail}")
            else:
                unknown.append(f"{what}\n             {detail}")

        need = REQUIRED[feature]
        if len(proven) >= need:
            verdict = "TERBUKTI"
        elif unknown and not proven:
            verdict = "TIDAK BISA DIJAWAB"
            unknowns.append(feature)
        elif proven:
            verdict = "TERBUKTI SEBAGIAN"
            failures.append(feature)
        else:
            verdict = "TIDAK TERSAMBUNG"
            failures.append(feature)

        print(f"{feature:10} {verdict}")
        for p in proven:
            print(f"           OK   {p}")
        for u in unproven:
            print(f"           --   {u}")
        for u in unknown:
            print(f"           ??   {u}")
        print()

    if unknowns:
        print(f"TIDAK BISA DIJAWAB: {', '.join(unknowns)}")
        print("Input tidak cukup untuk menjawab. Ini bukan lulus.")
        return 2
    if failures:
        print(f"GAGAL: {', '.join(failures)} tidak punya rantai bukti yang utuh.")
        print("Fitur bisa saja terkompilasi tapi tidak dipanggil dari mana pun.")
        return 1
    print("Semua fitur punya rantai bukti utuh dari kode yang dijalankan kernel.")
    return 0


def self_test() -> int:
    """The decoders are the whole argument; if they are wrong the proof is noise.

    Two bugs in this file were found by nothing but this function: a wrong word
    count that made every ADRP scan return an empty list, and a struct read at the
    wrong address. Both would have reported "feature not wired" for a good kernel.
    """
    pad = ARM64_TEXT_OFFSET
    syms = {"_stext": 0x1000}

    # BL from 0x1000 to 0x1010: imm26 = 4, target = 0x1000 + 4*4
    bl = struct.pack("<I", 0x94000004)

    # ADRP x1, page 0x2000 from pc 0x1004 (one page ahead), ADD x1, x1, #0x100
    imm = 1
    adrp = 0x90000000 | ((imm & 0x3) << 29) | (((imm >> 2) & 0x7FFFF) << 5) | 1
    add = 0x91000000 | (0x100 << 10) | (1 << 5) | 1

    code = bl + struct.pack("<I", adrp) + struct.pack("<I", add)
    fake = b"\x00" * pad + code

    got_bl = bl_targets(fake, syms, 0x1000, 0xC)
    ok_bl = got_bl == [(0x1000, 0x1010)]

    refs = data_refs(fake, syms, 0x1000, 0xC, 0x2000 + 0x100)
    ok_adrp = refs == [0x1004]

    # POINTER: a fake operations struct holding a function address
    struct_va = 0x3000
    struct_off = struct_va - 0x1000 + pad
    blob = bytearray(fake)
    if len(blob) < struct_off + 0x20:
        blob.extend(b"\x00" * (struct_off + 0x20 - len(blob)))
    struct.pack_into("<Q", blob, struct_off + 0x10, 0xABCD)
    ok_ptr = struct_holds(bytes(blob), syms, struct_va, 0xABCD) == 0x10

    print("self-test BL     :", "ok" if ok_bl else f"GAGAL ({got_bl})")
    print("self-test ADRP   :", "ok" if ok_adrp else f"GAGAL ({refs})")
    print("self-test POINTER:", "ok" if ok_ptr else "GAGAL")
    return 0 if (ok_bl and ok_adrp and ok_ptr) else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if len(argv) < 3:
        print(__doc__)
        return 2
    return run(pathlib.Path(argv[1]), pathlib.Path(argv[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
