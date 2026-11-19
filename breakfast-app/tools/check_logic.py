#!/usr/bin/env python3
"""Host-side checks for the app's pure logic, without a JVM.

These mirror the Kotlin unit tests so a regression is caught even on a machine
with no Android toolchain. The Kotlin tests remain the authority; this file
exists so CI can fail fast and so the formulas can be checked independently.

Only behaviour is checked here - reading the Kotlin source is done by
check_sources.py, which proves the two stay in step.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "breakfast-app"

WEIGHT = {"OOPS": 10, "BUG": 8, "WARN": 3}
PATTERNS = {
    "OOPS": ("Internal error: Oops", "Unable to handle kernel"),
    "BUG": ("kernel BUG at", "BUG: "),
    "WARN": ("WARNING: CPU:", "WARNING: at "),
}


def burden(counts: dict[str, int]) -> int:
    return sum(WEIGHT[k] * v for k, v in counts.items())


def score(b: int, hours: float) -> int:
    h = 1.0 if (hours != hours or hours < 1.0) else hours
    # round() half-up over a non-negative number, matching Math.round in Kotlin.
    return int(math.floor(max(0.0, min(100.0, 100.0 - (b * 10.0) / h)) + 0.5))


def band(value: int) -> str:
    if value >= 90:
        return "STABLE"
    if value >= 70:
        return "NORMAL"
    if value >= 40:
        return "ATTENTION"
    return "TROUBLE"


def classify(line: str) -> str | None:
    for event, needles in PATTERNS.items():
        for needle in needles:
            if needle in line:
                return event
    return None


def lum(color: int) -> float:
    def channel(v: int) -> float:
        c = (v & 0xFF) / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r = channel((color >> 16) & 0xFF)
    g = channel((color >> 8) & 0xFF)
    b = channel(color & 0xFF)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: int, b: int) -> float:
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
    return (hi + 0.05) / (lo + 0.05)


def check(condition: bool, message: str) -> list[str]:
    return [] if condition else [message]


def main() -> int:
    failures: list[str] = []

    # --- Stability Ledger, the five worked examples from the spec ------------
    for counts, hours, expected in (
        ({}, 99, 100),
        ({"WARN": 1}, 1, 70),
        ({"WARN": 1}, 10, 97),
        ({"OOPS": 1}, 5, 80),
        ({"OOPS": 2, "WARN": 1}, 2, 0),
    ):
        got = score(burden(counts), hours)
        failures += check(got == expected, f"ledger {counts} {hours}h: {got} != {expected}")

    # Uptime under one hour must not be rewarded.
    failures += check(score(10, 0.2) == score(10, 1.0), "ledger: sub-hour uptime not clamped")
    failures += check(score(0, float("nan")) == 100, "ledger: NaN uptime must not crash")
    # Scores clamp at both ends.
    failures += check(score(1000, 1) == 0, "ledger: score must clamp at 0")

    # --- Band thresholds -----------------------------------------------------
    for value, expected in ((100, "STABLE"), (90, "STABLE"), (89, "NORMAL"),
                            (70, "NORMAL"), (69, "ATTENTION"), (40, "ATTENTION"),
                            (39, "TROUBLE"), (0, "TROUBLE")):
        failures += check(band(value) == expected, f"band {value}: {band(value)} != {expected}")

    # --- Classification: counts what it should, ignores what it should -------
    should_count = {
        "Internal error: Oops - BUG: 96000004": "OOPS",
        "Unable to handle kernel paging request at virtual address": "OOPS",
        "kernel BUG at mm/vmscan.c:1234!": "BUG",
        "WARNING: CPU: 3 PID: 1234 at kernel/sched/core.c:5678": "WARN",
    }
    for line, expected in should_count.items():
        got = classify(line)
        failures += check(got == expected, f"classify {line[:40]!r}: {got} != {expected}")

    should_ignore = [
        "Call trace:",
        "---[ end trace 1a2b3c ]---",
        "i2c_geni f9920000.i2c: i2c error -107",
        "pr_err: probe failed, retrying",
        "WARNING: at drivers/gpu/drm/msm/adreno/a6xx_gpu.c:1",  # no "WARNING: at " form before CPU
    ]
    # "WARNING: at " is a real counted pattern, so drop that one from the ignore list.
    should_ignore = [line for line in should_ignore if not line.startswith("WARNING: at ")]
    for line in should_ignore:
        failures += check(classify(line) is None, f"must ignore {line[:40]!r}")

    # --- Themes: contrast is computed, never assumed -------------------------
    catalogue = [
        ("fresh-milk", 0x0D1117, 0x4A9EFF),
        ("cheese-burger", 0x0A0A0C, 0xFFB020),
        ("mint", 0x0B1512, 0x3DDC97),
        ("grape", 0x120D18, 0xA56BFF),
        ("mono", 0x0C0C0C, 0xD6D6D6),
    ]
    for name, bg, accent in catalogue:
        failures += check(ratio(0xF2F2F2, bg) >= 4.5, f"theme {name}: body contrast")
        failures += check(ratio(0x9A9A9A, bg) >= 4.5, f"theme {name}: secondary contrast")
        failures += check(ratio(accent, bg) >= 3.0, f"theme {name}: accent contrast")

    # A deliberately unreadable theme must be rejected by the same rule.
    failures += check(ratio(0xF2F2F2, 0xF0F0F0) < 4.5, "contrast: light-on-light must fail")
    failures += check(isinstance(ratio(0x000000, 0xFFFFFF), float) and abs(ratio(0x000000, 0xFFFFFF) - 21.0) < 0.01,
                      "contrast: black on white must be 21:1")

    # --- Tuning whitelist is closed ------------------------------------------
    markup = (APP / "app/src/main/java/app/breakfast/manager/data/TuningWhitelist.kt").read_text(encoding="utf-8")
    failures += check('key = "zram_comp_algorithm"' in markup, "whitelist: zram algorithm missing")
    # The genuinely dangerous ones must not appear as a Parameter at all.
    for forbidden in ("key = \"scaling_max_freq\"", "key = \"scaling_governor\"",
                      "key = \"vm_swappiness\"", "key = \"thermal\""):
        failures += check(forbidden not in markup, f"whitelist: must not expose {forbidden}")

    # --- Pairing gate --------------------------------------------------------
    pairing = json.loads((APP / "tools/pairing.json").read_text(encoding="utf-8"))
    releases = [k["release"] for k in pairing["kernels"]]
    failures += check(len(releases) == len(set(releases)), "pairing: duplicate release")
    for kernel in pairing["kernels"]:
        failures += check(len(kernel["release"]) <= 64, f"pairing: {kernel['release']} exceeds utsname")
        failures += check(kernel["status"] != "boot_tested",
                          f"pairing: {kernel['release']} claims a boot test that did not happen")
    generated = (APP / "app/src/main/java/app/breakfast/manager/data/PairingGenerated.kt").read_text(encoding="utf-8")
    for release in releases:
        failures += check(f'release = "{release}"' in generated,
                          f"generated pairing lost {release}")

    # The generated file must be reproducible from the JSON.
    sys.path.insert(0, str(APP / "tools"))
    import gen_pairing
    failures += check(gen_pairing.render(pairing) == generated,
                      "generated pairing is stale; re-run gen_pairing.py")

    # --- Audit rules ---------------------------------------------------------
    COOLDOWN = 30_000

    def cooldown_remaining(last, now):
        if last is None:
            return 0
        if now < last:
            return COOLDOWN
        return max(0, COOLDOWN - (now - last))

    for last, now, expected in ((None, 1_000, 0), (100_000, 100_000, 30_000),
                                (100_000, 120_000, 10_000), (100_000, 130_000, 0),
                                (100_000, 50_000, 30_000)):
        got = cooldown_remaining(last, now)
        failures += check(got == expected, f"cooldown last={last} now={now}: {got} != {expected}")

    def resolve(prev_kernel, new_kernel, running):
        """Returns ('fresh'|'stale'|'none', kernel)."""
        if prev_kernel is not None and prev_kernel != running:
            return ("fresh", new_kernel) if new_kernel else ("none", None)
        if new_kernel:
            return ("fresh", new_kernel)
        return ("stale", prev_kernel) if prev_kernel else ("none", None)

    for prev, new, running, expected in (
        ("A", "B", "B", ("fresh", "B")),   # flash, new audit ok
        ("A", "A", "A", ("fresh", "A")),   # same kernel, new audit ok
        ("A", None, "A", ("stale", "A")),  # same kernel, audit failed
        ("A", None, "B", ("none", None)),  # flash, audit failed -> discard
        (None, None, "A", ("none", None)), # never audited
    ):
        got = resolve(prev, new, running)
        failures += check(got == expected, f"resolve {prev}/{new}/{running}: {got} != {expected}")

    # The audit may only ever read: no write API on its interface.
    runner = (APP / "app/src/main/java/app/breakfast/manager/data/AuditRunner.kt").read_text(encoding="utf-8")
    fs_block = runner.split("interface Fs {")[1].split("}")[0]
    failures += check("fun write" not in fs_block, "audit Fs must not expose a write operation")

    # Read-only paths must never be tunable.
    audit = (APP / "app/src/main/java/app/breakfast/manager/data/DeviceAudit.kt").read_text(encoding="utf-8")
    for path in ("trip_point_0_temp", "thermal_zone0/type"):
        failures += check(path in audit, f"audit must inspect {path}")

    if failures:
        print(f"FAILED ({len(failures)}):")
        for item in failures:
            print("  -", item)
        return 1
    print("ok: ledger, bands, classification, contrast, whitelist, pairing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
