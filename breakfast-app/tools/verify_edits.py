#!/usr/bin/env python3
"""Fails loudly when an intended change is not actually present in the source.

Written after an edit silently did nothing: a replace() that matched nothing left
LAB showing four counts while the audit had five, and the mismatch reached a real
device. Every claim in a commit message is checked here instead of remembered.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SRC = APP / "app/src/main/java/app/breakfast/manager"

CHECKS = [
    # (file, required substring, why)
    ("ui/screens/LabScreen.kt", "report.countsLine()", "LAB must print five counts"),
    ("ui/screens/LabScreen.kt", "report.countsLegend()", "legend must match the counts"),
    ("ui/screens/LabScreen.kt", "readings.thermalZones", "LAB must show every thermal zone"),
    ("ui/PulseData.kt", "THRESHOLD_MARKERS", "throttle limits must not be read as sensors"),
    ("ui/PulseData.kt", "thermalZoneName = hottest?.name", "the ring must name its zone"),
    ("ui/screens/PulseScreen.kt", "caption = readings.thermalZoneName", "ring caption must be the zone"),
    ("ui/components/Components.kt", "valueText: String", "ring must accept an explicit value"),
    ("data/DeviceAudit.kt", "fun countsLine()", "counts must be generated, not typed twice"),
]

failures = []
for rel, needle, why in CHECKS:
    text = (SRC / rel).read_text(encoding="utf-8")
    if needle not in text:
        failures.append(f"{rel}: missing {needle!r} ({why})")

# The five counts must always total the nodes, in code and in the test copy.
audit = (SRC / "data/DeviceAudit.kt").read_text(encoding="utf-8")
if "counted(): Int = supported + readOnly + unreadable + unknown + absent" not in audit:
    failures.append("DeviceAudit.counted() must sum all five buckets")

if failures:
    print("VERIFY-EDITS FAILED:")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print(f"ok: {len(CHECKS)} perubahan terverifikasi ada di sumber")
