#!/usr/bin/env python3
"""Package the verified 3.1 rebuild with the user-tested 2.0 installer flow.

Only presentation/progress in the 2.0 scripts is changed; kernel writing,
device checks, mount/ksud behavior, warnings, error exits and logging remain.
The 3.1 kernel is newly compiled and has not been boot tested on a device.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('cannot load build or packaging helper')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('synthetica31_package_build', ROOT / 'build-kit/scripts/build_synthetica31.py')
legacy = load('synthetica31_package_legacy20', ROOT / 'build-kit/scripts/package_synthetica3_installer20.py')
guard = load('synthetica31_package_rc_guard', ROOT / 'build-kit/scripts/package_synthetica3_rc.py')
# Reuse the root/rc evidence validation with a private 3.1-configured copy.
guard.build = build.base.rc

BANNER = r''' _____   ___  _ _____ _  _ ___ _____ ___ ___   _
/ __\ \ / / \| |_   _| || | __|_   _|_ _/ __| /_\
\__ \\ V /| .` | | | | __ | _|  | |  | | (__ / _ \
|___/ |_| |_|\_| |_| |_||_|___| |_| |___\___/_/ \_\
'''.encode('ascii')

# Paired replacements make it possible to verify that every other byte of the
# original entry/backend, including error paths and partition writes, is intact.
ENTRY_UI = (
    ('SP_VERSION="2.0"', 'SP_VERSION="3.1"'),
    ('SP_UNAME="4.14.357-openela-Synthetica-2.0"', f'SP_UNAME="{build.RELEASE}"'),
    ('kernel.string=Synthetica by graziemille - Linux 4.14.357-openela', 'kernel.string=Synthetica 3.1'),
    ('IS_SLOT_DEVICE=0;\nRAMDISK_COMPRESSION=auto;',
     'IS_SLOT_DEVICE=0;\nNO_BLOCK_DISPLAY=1; # hide only redundant block-path UI\nRAMDISK_COMPRESSION=auto;'),
    ('''ui_print " ";
ui_print "  بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ";
ui_print " ";
ui_print "  Synthetica $SP_VERSION";
ui_print "  Kernel : $SP_UNAME";
ui_print "  Root   : $SP_ROOT_LINE";
ui_print " ";''', '''# UI progress only; all installation logic and file logging below are unchanged.
sp_progress() { echo "set_progress $1" >> "/proc/self/fd/$OUTFD"; }
sp_progress 0.20;'''),
    ('[ -n "$LOG_FILE" ] && ui_print "  Log    : $LOG_FILE";\nui_print " ";\n',
     '# The log file remains available when storage is writable.\n'),
    ('ui_print "  Installing ksud...";', 'ui_print "[2/3] Installing ksud...";'),
    ('ui_print "  ! ksud failed (data read-only?)";', 'ui_print "WARNING: ksud failed (data read-only?)";'),
    ('ui_print "  ksud OK";', 'ui_print "ksud: OK";'),
    ('ui_print "  ! /data is locked - ksud NOT installed. Unlock data, then flash again.";',
     'ui_print "WARNING: /data locked; ksud skipped.";'),
    ('''ui_print "  Writing kernel...";
log_line "write=started"
dump_boot;
write_boot;''', '''ui_print "[3/3] Preparing boot...";
sp_progress 0.45;
log_line "write=started"
dump_boot;
ui_print "[3/3] Writing boot...";
sp_progress 0.75;
write_boot;
sp_progress 1.0;'''),
    ('''ui_print " ";
ui_print "  الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ";
ui_print " ";
ui_print "  Done. Kernel installed.";
[ -n "$LOG_FILE" ] && ui_print "  Installation log: $LOG_FILE";
ui_print "  No auto-reboot. Reboot when you are ready.";
ui_print " ";''', '''ui_print "Done. No automatic reboot.";'''),
)
BACKEND_UI = (
    ('show_progress 1.34 25;', 'show_progress 1.0 0;'),
    ('unzip -o "$ZIPFILE";', 'unzip -qo "$ZIPFILE";'),
    ('ui_print "Checking device...";', 'ui_print "[1/3] Checking device...";'),
    ('ui_print "$testname" " ";', 'ui_print "Device: $testname";'),
    ('ui_print " " "AnyKernel3 by osm0sis @ xda-developers" " ";\n', ''),
    ('grep -oE \'AK_BASE.*\' META-INF/com/google/android/updater-script >&2;\n', ''),
    ('ui_print "Installing...";\n', ''),
    ('ui_print " " "Done!";\n', ''),
)


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'expected one original installer fragment: {old[:80]!r}')
    return text.replace(old, new, 1)


def ui_changes(data: bytes, changes: tuple[tuple[str, str], ...]) -> bytes:
    text = data.decode('utf-8')
    for old, new in changes:
        text = replace_once(text, old, new)
    return text.encode('utf-8')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_result(result: Path, tested20: Path, baseline30: Path) -> tuple[bytes, dict[str, object]]:
    if result.is_symlink() or not result.is_dir():
        raise ValueError('compile result must be an existing non-symlink directory')
    build.base.check_inputs()
    status = json.loads((result / 'STATUS.json').read_text(encoding='utf-8'))
    obj = status.get('manager_exec_fd_objects', {})
    if (status.get('kind') != build.STATUS_KIND or status.get('release') != build.RELEASE
            or status.get('baseline_3_0_image_sha256') != build.BASE30_IMAGE_SHA256
            or status.get('baseline_3_0_config_sha256') != build.BASE30_CONFIG_SHA256
            or status.get('manager_exec_fd_patch_sha256') != build.base.PATCH_SHA256
            or obj.get('symbol') != 'ksu_install_manager_exec_fd'
            or any(not isinstance(obj.get(k), str) or len(obj[k]) != 64
                   for k in ('fs_exec_sha256', 'ksu_supercall_sha256'))):
        raise ValueError('3.1 build, baseline or Manager patch evidence mismatch')
    config = (result / 'generated.config.txt').read_bytes()
    changes = build.compare_30_config(baseline30, config.decode('utf-8'))
    if status.get('changes_from_original_3_0_config') != changes:
        raise ValueError('3.1 config comparison in build status differs')
    checked = guard.collect(result, tested20, expected_kind=build.STATUS_KIND)
    image = checked['Image.gz']
    certificate = (result / 'module-signing-public-cert.x509').read_bytes()
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as f:
        raw = f.read(build.base.rc.s2x.v3.MAX_RAW_IMAGE + 1)
    if len(raw) > build.base.rc.s2x.v3.MAX_RAW_IMAGE or raw.count(certificate) != 1:
        raise ValueError('embedded module certificate mismatch')
    for name, key in (('Module.symvers', 'module_symvers_sha256'), ('System.map', 'system_map_sha256')):
        if sha((result / name).read_bytes()) != status.get(key):
            raise ValueError('build evidence digest mismatch: ' + name)
    crc = build.base.rc.s2x.modules.symvers_records((result / 'Module.symvers').read_text())['module_layout']
    if status.get('module_layout_crc') != f'0x{crc:08x}':
        raise ValueError('module_layout evidence mismatch')
    return image, status


def readme(image_sha: str, cert_sha: str) -> bytes:
    return f'''SY N T H E T I C A  3.1

Kernel 3.1 dikompilasi ulang dari resep/source 3.0, dengan konfigurasi yang sama
kecuali LOCALVERSION. Installer mengikuti alur rilis 2.0 yang sebelumnya
dilaporkan berhasil boot; logo dan teks progress TWRP diringkas.

PENTING: laporan boot pengguna berlaku untuk paket 3.0 sebelumnya, bukan image
3.1 yang baru ini. Boot, root, modul ROM, AVB dan kamera belum diuji secara
fisik pada image 3.1. Sertifikat penandatanganan modul baru berbeda dari build
sebelumnya; kecocokan dan kepercayaan modul ROM belum terbukti.

Sebelum flash: pastikan bootloader terbuka, varian/slot/recovery dan ROM sesuai,
dan simpan backup BOOT yang tepat serta cara memulihkannya. Installer 2.0 tidak
membuat backup. Backup juga /data/adb/ksud jika ada: installer bisa menggantinya
sebelum penulisan boot, termasuk ketika flash kemudian gagal. Jika data terkunci,
ksud dilewati. Tidak ada modul, DTB atau DTBO bawaan di paket.

Alur 2.0 tidak memiliki guard slot/unlock, hash DTB dan readback setara installer
3.0 asli. IS_SLOT_DEVICE=0 bukan bukti perangkat tidak memiliki slot. AnyKernel
bisa mem-patch DTB/AVB dalam kondisi tertentu seperti Magisk; signature boot
belum diverifikasi. Jangan wipe data atau ubah vbmeta untuk memaksa boot.
Jika terjadi kesalahan saat penulisan, jangan reboot; pulihkan boot dari recovery.

Kernel uname: {build.RELEASE}
Image.gz SHA-256: {image_sha}
Sertifikat publik modul SHA-256: {cert_sha}
Sumber kernel: {build.base.rc.s2x.v3.SOURCE}
'''.encode('utf-8')


def collect(result: Path, tested20: Path, baseline30: Path, source20: Path) -> dict[str, bytes]:
    image, status = verify_result(result, tested20, baseline30)
    files = legacy.read_archive(source20, legacy.SOURCE20_SHA, 21_567_245, legacy.SOURCE20_MEMBERS)
    if sha(files['ksud']) != legacy.KSUD_SHA:
        raise ValueError('2.0 ksud identity mismatch')
    files['Image.gz'] = image
    files['anykernel.sh'] = ui_changes(files['anykernel.sh'], ENTRY_UI)
    files[legacy.BINARY] = ui_changes(files[legacy.BINARY], BACKEND_UI)
    files['banner'] = BANNER
    files['README-FLASH.txt'] = readme(sha(image), status['module_public_cert_sha256'])
    metadata = {
        'kind': 'SYNTHETICA_3_1_NEW_KERNEL_NOT_DEVICE_TESTED',
        'version': '3.1', 'kernel_release': build.RELEASE,
        'image_sha256': sha(image), 'config_sha256': status['config_sha256'],
        'source_2_0_zip_sha256': legacy.SOURCE20_SHA,
        'tested_previous_3_0_image_sha256': build.BASE30_IMAGE_SHA256,
        'previous_3_0_boot': 'User reports a previously Error 1-affected user now boots; exact installed bytes and ROM not independently verified.',
        'physical_boot_test_this_3_1_image': 'NOT RUN',
        'installer': '2.0 release workflow; only text, progress, quiet unzip and labels changed',
        'ksud_2_0_sha256': legacy.KSUD_SHA,
        'boot_backup_automatic': False,
        'module_public_cert_sha256': status['module_public_cert_sha256'],
        'module_layout_crc': status['module_layout_crc'],
        'rom_module_abi_and_trust': 'NOT VERIFIED',
        'avb_boot_trust': 'NOT VERIFIED',
    }
    files['BUILD-INFO.txt'] = (json.dumps(metadata, indent=2) + '\n').encode('utf-8')
    return files


def package(result: Path, tested20: Path, baseline30: Path, source20: Path, output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    files = collect(result, tested20, baseline30, source20)
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            created = True
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2026, 11, 8, 0, 0, 0))
                info.create_system = 3
                executable = name in (legacy.BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                info.external_attr = (0o100755 if executable else 0o100644) << 16
                z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or set(names) != set(files) or z.testzip():
                raise ValueError('output ZIP failed entry or CRC check')
            for name in names:
                executable = name in (legacy.BINARY, 'anykernel.sh', 'ksud') or name.startswith('tools/')
                if z.read(name) != files[name] or z.getinfo(name).external_attr >> 16 != (0o100755 if executable else 0o100644):
                    raise ValueError('output entry/mode mismatch: ' + name)
        return {'path': str(output), 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes()),
                'image_sha256': sha(files['Image.gz']), 'kernel_release': build.RELEASE,
                'physical_boot_test_this_image': False}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--tested20', required=True, type=Path)
    parser.add_argument('--baseline30', required=True, type=Path)
    parser.add_argument('--source20', type=Path, default=ROOT / 'release/Synthetica-2.0.zip')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.result, args.tested20, args.baseline30, args.source20, args.output), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f'Synthetica 3.1 packaging refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
