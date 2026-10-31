#!/usr/bin/env python3
"""Pack the SYNTHETICA NEXT module that puts the tuning panel inside the KernelSU manager.

The manager we ship (KernelSU-Next) renders `webroot/index.html` as a page inside the app and runs
it as root, so this module is what turns "game mode" into a switch inside the manager instead of a
terminal command. Layout:

    module.prop
    games.txt                     list of packages for auto mode (commented out by default)
    bin/synthetica-tune.sh        the tuner, copied from tools/
    webroot/index.html|panel.css|panel.js

Nothing here runs at boot on its own: the panel calls the tuner, and the tuner only writes live
/sys and /proc values. Removing the module removes everything.
"""
from pathlib import Path
import hashlib
import json
import os
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "module"
TUNER = ROOT / "tools" / "synthetica-tune.sh"
OUT = ROOT / "artifacts"
VERSION = os.environ.get("SP_RELEASE_VERSION", "1.19")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert MODULE.exists(), f"missing module dir: {MODULE}"
    assert TUNER.exists(), f"missing tuner: {TUNER}"
    assert (MODULE / "module.prop").exists(), "module.prop missing"
    assert (MODULE / "webroot" / "index.html").exists(), "webroot/index.html missing"

    prop = (MODULE / "module.prop").read_text()
    prop = prop.replace("version=1.0.0", f"version={VERSION}")
    entries = {
        "module.prop": prop.encode(),
        "games.txt": (MODULE / "games.txt").read_bytes(),
        "bin/synthetica-tune.sh": TUNER.read_bytes(),
    }
    for f in sorted((MODULE / "webroot").iterdir()):
        if f.is_file():
            entries[f"webroot/{f.name}"] = f.read_bytes()

    name = f"SYNTHETICA-NEXT-module-{VERSION}.zip"
    target = OUT / name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path, blob in entries.items():
            info = zipfile.ZipInfo(path)
            info.external_attr = 0o644 << 16
            if path.endswith(".sh"):
                info.external_attr = 0o755 << 16
            z.writestr(info, blob)

    record = {
        "kind": f"KernelSU module {VERSION}: panel + tuner",
        "zip": {"name": name, "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
        "entries": {k: len(v) for k, v in entries.items()},
        "install": ("KernelSU manager -> Modules -> Install from storage -> pick this zip -> reboot "
                    "is not required; open the module page to reach the panel"),
        "remove": "Modules -> SYNTHETICA NEXT -> Remove (nothing was written to the boot image)",
    }
    (OUT / "MODULE.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    print(f"DONE: {target} ({target.stat().st_size} B)")


if __name__ == "__main__":
    main()
