#!/usr/bin/env python3
"""Package a guarded Synthetica 3.0 recovery candidate, not a stable release."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('cannot load packaging guard')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('synthetica3_root_packaging_build', ROOT / 'build-kit/scripts/build_synthetica3_root.py')
base = load('synthetica3_root_packaging_base', ROOT / 'build-kit/scripts/package_synthetica3_rc.py')
# Reuse all rc1 input/image/config/identity/archive verification, but compare to
# this candidate's exact release and status kind. It is a private imported copy.
base.build = build.rc

BANNER = r''' _____   ___  _ _____ _  _ ___ _____ ___ ___   _
/ __\ \ / / \| |_   _| || | __|_   _|_ _/ __| /_\
\__ \\ V /| .` | | | | __ | _|  | |  | | (__ / _ \
|___/ |_| |_|\_| |_| |_||_|___| |_| |___\___/_/ \_\
'''.encode('ascii')


def concise_entry(entry: bytes) -> bytes:
    """Only change UI/progress and logging in the already pinned writer template."""
    replace = base.replace_once
    entry = replace(entry, b'kernel.string=Synthetica 3.0-rc1 - Neutron - MGLRU ON',
                    b'kernel.string=3.0')
    entry = replace(entry, b'''fail() { ui_print ' ' "ERROR: $*" 'No reboot will be performed.'; exit 1; }
prop()''', b'''fail() { ui_print ' ' "ERROR: $*" 'No reboot will be performed.'; exit 1; }
set_progress() { echo "set_progress $1" >> "/proc/self/fd/$OUTFD"; }
prop()''')
    entry = replace(entry, b'''ui_print ' ' 'Synthetica 3.0-rc1 TEST - Neutron / MGLRU ON' \\
  'WARNING: no physical boot, ROM module or root test has been performed.' \\
  'A bootloop is possible. Keep the current boot backup and recovery available.' ' '
''', b'''ui_print 'Backup boot and recovery required.' 'Checking boot...'
set_progress 0.05
''')
    entry = replace(entry, b"ui_print 'Reading current boot image. Nothing is written yet...'",
                    b"ui_print 'Reading boot...'\nset_progress 0.15")
    entry = replace(entry, b"ui_print 'Checking kernel hash, boot format, reference DTB, ramdisk and preserved components...'",
                    b"ui_print 'Preparing boot...'\nset_progress 0.25")
    # MagiskBoot is noisy on success. On failure, retain the actual guard reason.
    entry = replace(entry, b'''  6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239; then
  fail 'Boot checks failed. The boot partition was not written.'
fi''', b'''  6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239 > "$AKHOME/prepare.log" 2>&1; then
  reason=$("$BB" grep -F 'PREPARE FAILED:' "$AKHOME/prepare.log" | "$BB" tail -n 1)
  [ -z "$reason" ] || ui_print "$reason"
  fail 'Boot checks failed. The boot partition was not written.'
fi
set_progress 0.70''')
    entry = replace(entry, b"ui_print 'WARNING: AVB signature and ROM modules are NOT verified.' 'Writing boot partition...'",
                    b"ui_print 'AVB and modules unverified.' 'Writing boot...'\nset_progress 0.75")
    entry = replace(entry, b'if ! "$BB" dd if="$candidate" of="$BLOCK" bs=1048576 conv=fsync; then',
                    b'if ! "$BB" dd if="$candidate" of="$BLOCK" bs=1048576 conv=fsync 2>/dev/null; then')
    entry = replace(entry, b'''if ! "$BB" cmp -s -n "$partsize" "$candidate" "$BLOCK"; then''',
                    b'''ui_print 'Verifying write...'
set_progress 0.90
if ! "$BB" cmp -s -n "$partsize" "$candidate" "$BLOCK"; then''')
    entry = replace(entry, b'''ui_print 'Boot write and byte readback completed.' \\
  'No automatic reboot. Boot, root and ROM module compatibility remain untested.' \\
  'If the phone does not boot, return to recovery and restore your exact boot backup.'
''', b'''set_progress 1.0
ui_print 'Boot write and byte readback completed.'
''')
    return entry


def concise_backend(backend: bytes) -> bytes:
    """Keep AnyKernel checks/cleanup; remove redundant successful UI only."""
    replace = base.replace_once
    backend = replace(backend, b'show_progress 1.34 25;', b'show_progress 1.0 0;')
    backend = replace(backend, b'unzip -o "$ZIPFILE";', b'unzip -qo "$ZIPFILE";')
    backend = replace(backend, b'        ui_print "$testname" " ";\n', b'')
    backend = replace(backend, b'ui_print " " "AnyKernel3 by osm0sis @ xda-developers" " ";\n', b'')
    backend = replace(backend, b'grep -oE \'AK_BASE.*\' META-INF/com/google/android/updater-script >&2;\n', b'')
    backend = replace(backend, b'ui_print "Installing...";\n', b'')
    backend = replace(backend, b'ui_print " " "Done!";\n', b'')
    return backend


def readme(image_sha: str, cert_sha: str) -> str:
    return f'''SY N T H E T I C A  3.0 — KANDIDAT UJI RECOVERY

BUKAN RILIS STABIL. Image ini belum diuji pada perangkat. Perubahan root
Manager menargetkan kemungkinan descriptor terhapus saat helper dijalankan;
penyebab di ponsel ini dan keberhasilannya belum terbukti. SECCOMP Manager tidak
dimatikan dan otorisasi KernelSU tidak dilemahkan. Setelah eskalasi root,
perilaku root-profile dan SECCOMP tetap mengikuti kernel sebelumnya.

Sebelum mencoba: pastikan bootloader terbuka, recovery bisa dipakai, dan
simpan backup boot yang TEPAT untuk kondisi perangkat sekarang di tempat
terpisah. Installer tidak membuat backup otomatis. Pastikan cara memulihkan
backup jika bootloop. Jangan wipe data atau ubah vbmeta untuk memaksa boot.

Installer memeriksa device joyeuse/miatoll, tidak ada slot A/B, bootloader,
ukuran partisi boot, format boot-v2, hash kernel, DTB referensi dan ramdisk.
Isi non-kernel, header yang stabil dan bytes AVB dibandingkan setelah repack;
boot ditulis hanya setelah lolos pemeriksaan, lalu hasilnya dibaca ulang.
TIDAK ADA REBOOT OTOMATIS. Jika penulisan atau readback gagal: JANGAN REBOOT;
pulihkan boot backup yang tepat melalui recovery.

Bytes AVB yang sama tidak membuktikan signature boot masih valid. Kepercayaan
AVB, modul ROM dan kompatibilitas perangkat tidak diverifikasi; sertifikat
modul baru berbeda dari build sebelumnya. Tidak ada vbmeta, dtbo, vendor,
system, userdata, ksud atau modul yang ditulis. Kamera 0.6x sebelumnya
dilaporkan freeze; kandidat ini tidak berisi perbaikan kamera.

uname -r: {build.EXPECTED_RELEASE}
Image.gz SHA-256: {image_sha}
Sertifikat modul publik SHA-256: {cert_sha}
Sumber: https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/tree/c1e6f795b557b7bf92220c91f05a42b456de7a74
Resep dan patch: https://github.com/dwp29/Syntenthica/tree/arena/96cbd65a-syntenthica
'''


def collect(result: Path, tested_config: Path) -> dict[str, bytes]:
    build.check_inputs()
    # Refuse evidence lacking the second patch and statically verified object.
    if result.is_symlink() or not result.is_dir():
        raise ValueError('compile evidence must be an existing non-symlink directory')
    raw = (result / 'STATUS.json').read_bytes()
    if len(raw) > 200_000:
        raise ValueError('oversized build status')
    status = json.loads(raw)
    obj = status.get('manager_exec_fd_objects', {})
    if (status.get('kind') != build.STATUS_KIND
            or status.get('manager_exec_fd_patch_sha256') != build.PATCH_SHA256
            or obj.get('symbol') != 'ksu_install_manager_exec_fd'
            or any(not isinstance(obj.get(k), str) or len(obj[k]) != 64
                   for k in ('fs_exec_sha256', 'ksu_supercall_sha256'))):
        raise ValueError('Manager helper patch/object evidence missing')
    files = base.collect(result, tested_config, expected_kind=build.STATUS_KIND)
    files['anykernel.sh'] = concise_entry(files['anykernel.sh'])
    binary = 'META-INF/com/google/android/update-binary'
    files[binary] = concise_backend(files[binary])
    files['banner'] = BANNER
    image_sha = base.sha(files['Image.gz'])
    cert_sha = status['module_public_cert_sha256']
    files['README-FLASH.txt'] = readme(image_sha, cert_sha).encode('utf-8')
    meta = json.loads(files['BUILD-INFO.json'])
    meta.update({
        'kind': 'SYNTHETICA_3_0_RECOVERY_TEST_INSTALLER_NOT_DEVICE_TESTED',
        'release': build.EXPECTED_RELEASE,
        'manager_exec_fd_patch_sha256': build.PATCH_SHA256,
        'manager_root_seccomp_this_image': 'NOT TESTED ON DEVICE; fix addresses an unconfirmed hypothesis',
        'manager_helper_scope': 'Recognized Manager UID, libksud.so after successful exec; normal CLOEXEC fd and existing ioctl checks',
    })
    files['BUILD-INFO.json'] = (json.dumps(meta, indent=2) + '\n').encode('utf-8')
    return files


def package(result: Path, tested_config: Path, output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    files = collect(result, tested_config)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if name in ('anykernel.sh', 'tools/prepare-boot.sh', 'tools/busybox',
                                          'tools/magiskboot', 'META-INF/com/google/android/update-binary') else 0o644
                info.external_attr = (0o100000 | mode) << 16
                z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None or len(z.namelist()) != len(files) or set(z.namelist()) != set(files):
                raise ValueError('created ZIP failed integrity verification')
            if base.sha(z.read('Image.gz')) != base.sha(files['Image.gz']):
                raise ValueError('created ZIP contains an unexpected kernel')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    info = {'path': str(output), 'bytes': output.stat().st_size,
            'sha256': base.sha(output.read_bytes()), 'image_sha256': base.sha(files['Image.gz']),
            'kind': '3.0 recovery candidate; NOT device tested'}
    print(json.dumps(info, indent=2))
    return info


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result', required=True, type=Path)
    p.add_argument('--tested-config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    package(args.result, args.tested_config, args.output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print('3.0 candidate packaging refused: ' + str(exc), file=sys.stderr)
        sys.exit(1)
