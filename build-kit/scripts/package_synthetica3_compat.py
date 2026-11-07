#!/usr/bin/env python3
"""Build a read-only boot audit and an unvalidated 3.0 installer development candidate.

The inputs are pinned to the already published 3.0 ZIP. No DTB allowlist entry,
kernel image, MagiskBoot binary or boot-preparation guard is changed. The test
installer is NOT a claim of physical-device or ROM compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build-kit/ci/synthetica3-compat'
ORIGINAL_SHA256 = '16b32f57381005c08cbee0ec684397dc91acc77f5b2ccbb4ef7f4b99a9a791e6'
REFERENCE_DTB = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
IMAGE_SHA256 = '92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb'
BINARY = 'META-INF/com/google/android/update-binary'
UPDATER = 'META-INF/com/google/android/updater-script'
EXPECTED = frozenset((
    'BUILD-INFO.json', 'Image.gz', 'LICENSE', BINARY, UPDATER, 'README-FLASH.txt',
    'anykernel.sh', 'banner', 'tools/busybox', 'tools/magiskboot', 'tools/prepare-boot.sh',
))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: bytes, old: bytes, new: bytes) -> bytes:
    if text.count(old) != 1:
        raise ValueError('expected exactly one original installer fragment: ' + repr(old[:80]))
    return text.replace(old, new, 1)


def original_files(path: Path) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError('original ZIP must be an existing regular, non-symlink file')
    if path.stat().st_size != 15_719_303:
        raise ValueError('original 3.0 ZIP size mismatch')
    raw = path.read_bytes()
    if len(raw) != 15_719_303 or sha(raw) != ORIGINAL_SHA256:
        raise ValueError('original 3.0 ZIP hash mismatch')
    # Inspect the very bytes just hashed, not a second open of a mutable path.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or frozenset(names) != EXPECTED or archive.testzip():
            raise ValueError('original ZIP entries or CRC mismatch')
        if any(archive.getinfo(name).file_size > 20_000_000 for name in names):
            raise ValueError('unexpectedly large original ZIP entry')
        files = {name: archive.read(name) for name in names}
    info = json.loads(files['BUILD-INFO.json'])
    if (sha(files['Image.gz']) != IMAGE_SHA256 or info.get('image_sha256') != IMAGE_SHA256
            or info.get('reference_dtb_sha256') != REFERENCE_DTB):
        raise ValueError('original kernel or DTB identity mismatch')
    return files


def compat_entry(entry: bytes) -> bytes:
    entry = replace_once(entry, b'device.name1=joyeuse\ndevice.name2=miatoll\n',
                         b'device.name1=joyeuse\ndevice.name2=curtana\ndevice.name3=excalibur\n'
                         b'device.name4=gram\ndevice.name5=miatoll\n')
    entry = replace_once(entry, b'kernel.string=3.0\n', b'kernel.string=3.0 COMPAT TEST\n')
    entry = replace_once(entry, b'''# Do not guess which slot to overwrite on an A/B device.
slot=$(prop ro.boot.slot_suffix)
[ -z "$slot" ] || [ "$slot" = normal ] || fail "A/B slot detected; this package only targets an unslotted boot partition"
''', b'''# Check several independent A/B indications. Missing values alone cannot
# prove a device is unslotted. Never select or overwrite a guessed slot.
for key in ro.boot.slot_suffix ro.boot.slot; do
  slot=$(prop "$key")
  case "$slot" in ''|normal) :;; *) fail 'A/B slot detected or unknown slot; no boot selected';; esac
done
ab=$(prop ro.build.ab_update)
case "$ab" in ''|false|0) :;; *) fail 'A/B or unknown update property; no boot selected';; esac
for arg in $(cat /proc/cmdline 2>/dev/null); do
  case "$arg" in
    androidboot.slot=|androidboot.slot=normal|androidboot.slot_suffix=|androidboot.slot_suffix=normal) :;;
    androidboot.slot=*|androidboot.slot_suffix=*) fail 'A/B slot in kernel command line; no boot selected';;
  esac
done
for dir in /dev/block/bootdevice/by-name /dev/block/by-name; do
  for part in "$dir/boot_a" "$dir/boot_b"; do
    [ ! -e "$part" ] && [ ! -L "$part" ] || fail 'Slotted boot names detected; no boot selected'
  done
done
''')
    entry = replace_once(entry, b'''  [ -z "$reason" ] || ui_print "$reason"
  fail 'Boot checks failed. The boot partition was not written.'
''', b'''  if [ -n "$reason" ]; then
    ui_print "$reason"
  else
    ui_print 'Preparation failed unexpectedly; save recovery.log.'
  fi
  # Report a fingerprint only after the original strict DTB rejection. This
  # is not an allowlist and the boot partition is never written on failure.
  case "$reason" in
    *'boot DTB is not the known Lunaris 3.13 reference'*)
      if [ -f "$AKHOME/boot-check/orig/dtb" ]; then
        actual=$("$BB" sha256sum "$AKHOME/boot-check/orig/dtb" | "$BB" cut -d ' ' -f 1)
        case "$actual" in
          ''|*[!0-9a-f]*) :;;
          *) if [ "${#actual}" -eq 64 ]; then
               ui_print "DTB SHA256 1/2: $(printf '%s' "$actual" | "$BB" cut -c 1-32)" \\
                        "DTB SHA256 2/2: $(printf '%s' "$actual" | "$BB" cut -c 33-64)" \\
                        'Different hash is not a compatibility verdict.'
             fi;;
        esac
      fi;;
  esac
  fail 'Boot checks failed. The boot partition was not written.'
''')
    entry = replace_once(entry, b"fail 'Unable to read full boot partition'",
                         b"fail 'Unable to read boot; check recovery permissions and /tmp space'")
    return entry


def compat_backend(backend: bytes) -> bytes:
    # The original AnyKernel setup_env mounts several partitions and may mount
    # fstab entries with default (possibly writable) flags. This kernel-only
    # candidate requires no mounts: use the recovery's existing getprop instead.
    # If the recovery cannot supply identifying properties, do_devicecheck
    # fails closed; no fallback to guessed properties is introduced.
    backend = replace_once(backend, b'''  debugging;
  restore_env;
  if [ ! -f anykernel.sh''', b'''  debugging;
  # No setup_env was run, so do not unmount or restore recovery mounts.
  if [ ! -f anykernel.sh''')
    backend = replace_once(backend, b'''setup_env;

do_devicecheck;''', b'''# No setup_env: do not mount partitions or change the recovery environment.
do_devicecheck;''')
    backend = replace_once(backend, b'''debugging;
ui_print " ";
restore_env;

if [ "$(file_getprop anykernel.sh do.cleanup)" == 1 ]; then''', b'''debugging;
ui_print " ";
# No setup_env was run; leave all existing recovery mounts untouched.
if [ "$(file_getprop anykernel.sh do.cleanup)" == 1 ]; then''')
    return backend


def compat_files(files: dict[str, bytes]) -> dict[str, bytes]:
    out = dict(files)
    out['anykernel.sh'] = compat_entry(out['anykernel.sh'])
    out[BINARY] = compat_backend(out[BINARY])
    old = json.loads(out['BUILD-INFO.json'])
    old.update({
        'kind': 'SYNTHETICA_3_0_COMPAT_DEVELOPMENT_NOT_DEVICE_VALIDATED',
        'target': 'miatoll property family; DTB and all existing boot guards still apply',
        'base_zip_sha256': ORIGINAL_SHA256,
        'changes': ['explicit miatoll device codenames', 'additional A/B indications',
                    'DTB fingerprint on strict rejection', 'no installer-initiated mounts'],
        'known_dtb_policy': 'unchanged: the sole existing reference hash; no new ROM approved',
        'avb_boot_trust': 'NOT VERIFIED; existing signature may not validate modified boot',
        'rom_module_abi_and_signatures': 'NOT VERIFIED',
        'physical_boot_test_this_installer': 'NOT RUN',
    })
    out['BUILD-INFO.json'] = (json.dumps(old, indent=2) + '\n').encode()
    out['README-FLASH.txt'] = (SOURCE / 'README-COMPAT-TEST.txt').read_bytes()
    return out


def audit_files(files: dict[str, bytes]) -> dict[str, bytes]:
    script = (SOURCE / 'boot-audit.sh').read_bytes()
    if not script.startswith(b'#!/sbin/sh\n') or REFERENCE_DTB.encode() not in script:
        raise ValueError('boot audit source incomplete')
    return {
        BINARY: script,
        UPDATER: b'# Synthetica Boot Audit: diagnostic update-binary, not a kernel.\n',
        'boot-audit.sh': script,
        'README-ID.txt': (SOURCE / 'README-BOOT-AUDIT.txt').read_bytes(),
        'tools/busybox': files['tools/busybox'],
        'LICENSE': files['LICENSE'],
    }


def package(files: dict[str, bytes], output: Path, executable: set[str]) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            created = True
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100755 if name in executable else 0o100644) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(files) or archive.testzip():
                raise ValueError('output ZIP failed integrity or entry checks')
            for name in names:
                mode = 0o100755 if name in executable else 0o100644
                if archive.read(name) != files[name] or archive.getinfo(name).external_attr >> 16 != mode:
                    raise ValueError('output ZIP differs from verified input: ' + name)
        return {'name': output.name, 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes())}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True, type=Path, help='pinned Synthetica 3.0 ZIP')
    parser.add_argument('--audit-output', required=True, type=Path, help='new read-only diagnostic ZIP')
    parser.add_argument('--compat-output', required=True, type=Path, help='new unvalidated development ZIP')
    args = parser.parse_args()
    original = original_files(args.original)
    audit = package(audit_files(original), args.audit_output, {BINARY, 'boot-audit.sh', 'tools/busybox'})
    try:
        compat = package(compat_files(original), args.compat_output,
                         {BINARY, 'anykernel.sh', 'tools/busybox', 'tools/magiskboot', 'tools/prepare-boot.sh'})
    except BaseException:
        args.audit_output.unlink(missing_ok=True)
        raise
    print(json.dumps({'audit': audit, 'unvalidated_installer': compat}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print('Packaging refused: ' + str(exc), file=sys.stderr)
        sys.exit(1)
