#!/usr/bin/env python3
"""Fail the build when the JVM unit tests did not actually run or did not pass.

Gradle can report success while running zero tests; asserting on the XML report
is the only way to know the suite was really executed.
"""
from __future__ import annotations

import glob
import sys
import xml.etree.ElementTree as ET

RESULTS = "app/build/test-results/testDebugUnitTest/*.xml"


def main() -> int:
    files = glob.glob(RESULTS)
    if not files:
        print(f"no unit test results under {RESULTS}")
        return 1

    total = failures = errors = skipped = 0
    for path in files:
        root = ET.parse(path).getroot()
        total += int(root.get("tests", 0))
        failures += int(root.get("failures", 0))
        errors += int(root.get("errors", 0))
        skipped += int(root.get("skipped", 0))

    print(f"tests={total} failures={failures} errors={errors} skipped={skipped}")
    if total == 0:
        print("zero tests ran")
        return 1
    if failures or errors:
        print("unit tests failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
