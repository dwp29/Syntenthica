#!/usr/bin/env python3
"""Package a minimal, opt-in 2.1 KernelSU WebUI module (no boot scripts)."""
from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "build-kit/ci/module-cyberbrutal"
CONTROL = ROOT / "build-kit/ci/ksun-cyberbrutal/assets/synthetica-control.sh"


def build(output: Path) -> None:
    inputs = {
        "module.prop": MODULE / "module.prop",
        "webroot/index.html": MODULE / "webroot/index.html",
        "webroot/panel.css": MODULE / "webroot/panel.css",
        "webroot/panel.js": MODULE / "webroot/panel.js",
        "bin/synthetica-control.sh": CONTROL,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, source in inputs.items():
            info = zipfile.ZipInfo(name, (2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if name.startswith("bin/") else 0o100644) << 16
            out.writestr(info, source.read_bytes())
    with zipfile.ZipFile(output) as check:
        if check.testzip() is not None:
            raise RuntimeError("Module ZIP CRC verification failed")
        if set(check.namelist()) != set(inputs):
            raise RuntimeError("Unexpected module ZIP contents")
        if check.read("bin/synthetica-control.sh") != CONTROL.read_bytes():
            raise RuntimeError("Module control helper differs from tested Manager helper")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Built {output} ({output.stat().st_size} bytes), SHA-256 {digest}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "release/Synthetica-2.1-Cyberbrutal-WebUI-Module.zip")
