#!/usr/bin/env python3
"""Package Synthetica 3.2 (all 3.0/3.1 features + cross-ROM unsigned AVB fix)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CORE_SHA = '0544478d92865e2f16aab00676de475af8bbbb0abecea738716f4aea3f484c9b'
MARKER = b'  blockdev --setrw $BLOCK 2>/dev/null;\n'
PATCH = b'''  # Cross-ROM unsigned embedded AVB repair (Project Infinity X 4.1 A17, upgrades, etc.).
  # Non-AVB or signed-AVB boot images (e.g. Lunaris A16) pass through untouched.
  s32_orig_sha=$($BIN/busybox sha256sum "$BOOTIMG" | $BIN/busybox cut -d' ' -f1);
  if [ "$s32_orig_sha" = "d33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f" ]; then
    ui_print "Infinity 4.1: repairing unsigned embedded AVB hash...";
    "$BIN/fix-avb" "$AKHOME/boot-new.img" "$BIN/busybox" || abort "AVB repair failed; boot not written.";
  else
    "$BIN/fix-avb" --if-unsigned "$AKHOME/boot-new.img" "$BIN/busybox" || abort "Unsigned AVB repair failed; boot not written.";
  fi;
'''


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build32 = load('synthetica32_final_build', ROOT / 'build-kit/scripts/build_synthetica32_final.py')
pkg31 = load('synthetica31_for_32_pkg', ROOT / 'build-kit/scripts/package_synthetica31.py')
pkg31.build = build32.s31
pkg31.guard.build = build32.s31.base.rc
pkg31.ENTRY_UI = tuple(
    (old, new.replace('3.1', '3.2').replace('4.14.357-openela-synthetica-3.1', build32.RELEASE))
    for old, new in pkg31.ENTRY_UI
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def readme(image_sha: str, cert_sha: str, helper_sha: str) -> bytes:
    return f'''SYNTHETICA 3.2 (miatoll / Joyeuse)

Kernel 3.2 memuat seluruh fitur Synthetica 3.0 & 3.1 secara utuh:
- Base: Linux 4.14.357-openela (Neutron Clang 18) + baseline optimasi 2.0
- MGLRU (Multi-Gen LRU, LRU_GEN_ENABLED=y) + UCLAMP + WALT/Schedtune
- KernelSU-Next in-tree (Rollercoaster 34000, manual hook) + ksud
- Patch Manager 3.0 (preserve inherited seccomp & post-exec driver-fd)
- Perbaikan installer AVB embedded UNSIGNED lintas-ROM (tools/fix-avb)

Mendukung pemasangan lintas ROM (termasuk Project Infinity X 4.1 Android 17 dan
Lunaris 3.13 Android 16), baik instalasi dari stock boot maupun pembaruan di
atas instalasi Synthetica sebelumnya.

Kernel uname: {build32.RELEASE}
Image.gz SHA-256: {image_sha}
tools/fix-avb SHA-256: {helper_sha}
Sertifikat publik modul SHA-256: {cert_sha}
Sumber kernel: {build32.v3.SOURCE}
'''.encode('utf-8')


def package(result: Path, tested20: Path, baseline30: Path, baseline31: Path,
            source20: Path, helper: Path, expected_helper_sha: str, output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    if helper.is_symlink() or not helper.is_file():
        raise ValueError('helper must be a regular file')
    binary = helper.read_bytes()
    if sha(binary) != expected_helper_sha:
        raise ValueError('helper SHA-256 mismatch')
    if len(binary) > 2_000_000 or binary[:7] != b'\x7fELF\x01\x01\x01' or int.from_bytes(binary[18:20], 'little') != 40:
        raise ValueError('helper must be ARM32 ELF')
    cfg_text = (result / 'generated.config.txt').read_text(encoding='utf-8')
    changes31 = build32.compare_31_config(baseline31, cfg_text)
    files = pkg31.collect(result, tested20, baseline30, source20)
    core = files['tools/ak3-core.sh']
    if sha(core) != CORE_SHA or core.count(MARKER) != 1 or b'fix-avb' in core:
        raise ValueError('unexpected AnyKernel core script')
    files['tools/ak3-core.sh'] = core.replace(MARKER, PATCH + MARKER)
    files['tools/fix-avb'] = binary
    info = json.loads(files['BUILD-INFO.txt'].decode('utf-8'))
    info.update({
        'kind': 'SYNTHETICA_3_2_RELEASE_INSTALLER',
        'version': '3.2',
        'kernel_release': build32.RELEASE,
        'proven_3_1_image_sha256': build32.BASE31_IMAGE_SHA256,
        'proven_3_1_config_sha256': build32.BASE31_CONFIG_SHA256,
        'changes_from_proven_3_1_config': changes31,
        'avb_helper_sha256': expected_helper_sha,
        'avb_patch_scope': 'Repairs unsigned embedded AVB boot hash (stock Infinity 4.1 and re-flashes/other unsigned-AVB ROMs); non-AVB and signed-AVB ROMs untouched.',
        'device_validation_basis': '3.1 kernel + AVB fix verified booting normally on Project Infinity X 4.1 (Android 17) and Lunaris 3.13 (Android 16) with Manager APK working.',
    })
    files['BUILD-INFO.txt'] = (json.dumps(info, indent=2) + '\n').encode('utf-8')
    files['README-FLASH.txt'] = readme(info['image_sha256'], info['module_public_cert_sha256'], expected_helper_sha)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, content in sorted(files.items()):
                zi = zipfile.ZipInfo(name, (2026, 11, 9, 0, 0, 0))
                zi.create_system = 3
                executable = name in (pkg31.legacy.BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                zi.external_attr = (0o100755 if executable else 0o100644) << 16
                z.writestr(zi, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(output) as z:
            if z.testzip() or set(z.namelist()) != set(files) or len(z.namelist()) != len(files):
                raise ValueError('output archive invalid')
            for name in files:
                if z.read(name) != files[name]:
                    raise ValueError('output content mismatch: ' + name)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {
        'path': str(output),
        'bytes': output.stat().st_size,
        'sha256': sha(output.read_bytes()),
        'image_sha256': info['image_sha256'],
        'helper_sha256': expected_helper_sha,
        'kernel_release': build32.RELEASE,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('result', 'tested20', 'baseline30', 'baseline31', 'helper', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--source20', type=Path, default=ROOT / 'release/Synthetica-2.0.zip')
    p.add_argument('--helper-sha256', required=True)
    a = p.parse_args()
    print(json.dumps(package(a.result, a.tested20, a.baseline30, a.baseline31,
                             a.source20, a.helper, a.helper_sha256, a.output), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
