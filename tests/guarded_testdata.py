"""Small synthetic fixtures; these are not Android ROMs or device images."""
import hashlib
import random
import zipfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_script() -> bytes:
    script = b'''assert(getprop("ro.product.device") == "joyeuse" || getprop("ro.build.product") == "joyeuse" || abort("wrong device"));
show_progress(0.2, 10);
package_extract_file("super.img", "/dev/block/bootdevice/by-name/super");
package_extract_file("boot.img", "/dev/block/bootdevice/by-name/boot");
package_extract_file("dtbo.img", "/dev/block/bootdevice/by-name/dtbo");
ui_print("Flashing completed");
set_progress(1.0);
'''
    return script + b"#" + b"x" * (1545 - len(script) - 2) + b"\n"


def manually_guard(script: bytes) -> bytes:
    for part in ("super", "boot", "dtbo"):
        line = f'package_extract_file("{part}.img", "/dev/block/bootdevice/by-name/{part}");'.encode()
        assert script.count(line) == 1
        script = script.replace(line, b"assert(" + line[:-1] + b");", 1)
    return script


def tiny_archive(path: Path) -> dict:
    script = synthetic_script()
    rng = random.Random(1337)
    contents = {
        "META-INF/": None,
        "META-INF/com/": None,
        "META-INF/com/google/": None,
        "META-INF/com/google/android/": None,
        "META-INF/com/google/android/updater-script": script,
        "META-INF/com/google/android/update-binary": rng.randbytes(4096),
        "META-INF/com/android/": None,
        "META-INF/com/android/metadata": b"not-a-real-ota-metadata\n",
        "META-INF/com/android/metadata.pb": b"synthetic protobuf bytes",
        "boot.img": rng.randbytes(8192),
        "dtbo.img": rng.randbytes(2048),
        "super.img": rng.randbytes(131072),
    }
    expected = {}
    with zipfile.ZipFile(path, "x", allowZip64=True) as z:
        z.comment = b"synthetic; no ROM or partitions here"
        for name, data in contents.items():
            info = zipfile.ZipInfo(name, (2026, 11, 2, 4, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = 1
            info.external_attr = (0o40755 if data is None else 0o100644) << 16
            z.writestr(info, data if data is not None else b"")
            expected[name] = ({"name": name, "directory": True} if data is None else
                              {"name": name, "bytes": len(data), "sha256": digest(data)})
    return expected
