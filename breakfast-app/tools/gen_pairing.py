#!/usr/bin/env python3
"""Generate the pairing table Kotlin source from tools/pairing.json.

Generating instead of hand-writing means the APK cannot ship a table that
disagrees with the file the release pipeline checks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HEADER = """package app.breakfast.manager.data

// GENERATED FILE - do not edit. Source: breakfast-app/tools/pairing.json
// Regenerate with: python3 breakfast-app/tools/gen_pairing.py

internal object PairingGenerated {
    val KERNELS: List<KernelPairing.Kernel> = listOf(
"""

FOOTER = """    )
}
"""


def render(payload: dict) -> str:
    rows = []
    for kernel in payload["kernels"]:
        release = json.dumps(kernel["release"])
        variant = json.dumps(kernel["variant"])
        profile = json.dumps(kernel["profile"])
        status = json.dumps(kernel["status"])
        rows.append(
            "        KernelPairing.Kernel(\n"
            f"            release = {release},\n"
            f"            variant = {variant},\n"
            f"            profile = {profile},\n"
            f"            kernelUapi = {int(kernel['kernel_uapi'])},\n"
            f"            capabilitiesVerified = {str(kernel.get('capabilities_verified', False)).lower()},\n"
            f"            status = {status},\n"
            "        ),\n"
        )
    return HEADER + "".join(rows) + FOOTER


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("breakfast-app/tools/pairing.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("breakfast-app/app/src/main/java/app/breakfast/manager/data/PairingGenerated.kt"),
    )
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise SystemExit("unsupported pairing schema")
    if not payload.get("kernels"):
        raise SystemExit("pairing table is empty")

    releases = [k["release"] for k in payload["kernels"]]
    if len(set(releases)) != len(releases):
        raise SystemExit("duplicate release in pairing table")
    for kernel in payload["kernels"]:
        if len(kernel["release"]) > 64:
            raise SystemExit(f"release exceeds utsname length: {kernel['release']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(payload), encoding="utf-8")
    print(f"wrote {args.output} ({len(payload['kernels'])} kernels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
