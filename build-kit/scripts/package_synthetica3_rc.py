#!/usr/bin/env python3
"""Create a guarded Joyeuse 3.0-rc1 recovery test ZIP from verified build evidence.

The new image, Manager seccomp change and camera are not tested on a device.
This does not bypass module signatures, AVB or install userspace/ksud.
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
SCRIPTS = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer'
BASE = ROOT / 'release/Synthetica-2.0.zip'
BASE_SHA256 = 'b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
ENTRY_SHA256 = 'd6fa389a46945be0c050cd462bcfc46123004242728011c4bce7d2cbd2d0bbe3'
PREPARE_SHA256 = '0a6eedd69f2d2432b57bcaf64d7bd291b6466b59ad0658a6ed5ba403228a7ad4'
REFERENCE_DTB_SHA256 = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
BASE_FILES = ('LICENSE', 'META-INF/com/google/android/update-binary',
              'META-INF/com/google/android/updater-script', 'tools/busybox', 'tools/magiskboot')


def load_guard():
    spec = importlib.util.spec_from_file_location('synthetica3_rc_package_guard',
                                                  ROOT / 'build-kit/scripts/build_synthetica3_rc.py')
    if spec is None or spec.loader is None:
        raise ValueError('build guard could not be loaded')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_guard()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_zip_unique(z: zipfile.ZipFile, name: str, max_size: int) -> bytes:
    matches = [x for x in z.infolist() if x.filename == name]
    if len(matches) != 1 or matches[0].file_size > max_size:
        raise ValueError('missing, duplicate or oversized ZIP member: ' + name)
    return z.read(matches[0])


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise ValueError('unexpected installer template: ' + old.decode('ascii', 'replace')[:80])
    return data.replace(old, new, 1)


def readme(image_sha: str, public_cert_sha: str) -> str:
    return f'''SY N T H E T I C A  3.0-rc1  -  ZIP UJI COBA
Neutron / MGLRU aktif secara default
================================================

INI ZIP FLASHABLE UNTUK UJI COBA, BUKAN RILIS STABIL.
Synthetica 2.0 eksperimen dilaporkan boot oleh pengguna di joyeuse/Lunaris 3.13,
tetapi image 3.0-rc1 ini BARU dan BELUM DIUJI di perangkat. Root, Manager,
SECCOMP, kompatibilitas ROM/modul dan kepercayaan AVB belum terbukti.

Pengguna melaporkan kamera 0.6x freeze pada build sebelumnya. Kandidat ini
TIDAK berisi perbaikan kamera; masalah bisa tetap terjadi. SECCOMP dipertahankan
hanya untuk proses Manager bila filter diwariskan dari ROM. Perilaku aplikasi
yang diizinkan root dan proses setelah eskalasi root tidak diubah. Apakah
Manager, root, dan filter benar-benar bekerja perlu diuji di perangkat.

Sebelum mencoba: pastikan bootloader terbuka, recovery dapat diakses, dan salinan
boot yang TEPAT dari perangkat saat ini tersimpan terpisah. Pastikan Anda tahu
cara memulihkannya. Installer tidak membuat backup otomatis. Bootloop, hilangnya
root atau fungsi perangkat, panas dan gangguan lain tetap mungkin terjadi.

Installer hanya menulis partisi boot setelah pemeriksaan perangkat/format/DTB,
serta membaca ulang hasil. Ramdisk, DTB, second, recovery DTBO dan metadata AVB
diperiksa agar tetap sama. Signature boot lama mungkin tidak lagi valid karena
kernel berubah. Installer tidak mengubah vbmeta, dtbo, vendor, system, userdata,
ksud, atau modul, dan tidak menonaktifkan verifikasi. Sertifikat modul build ini
berbeda dari build sebelumnya; kepercayaan modul ROM belum diverifikasi.

Pemasangan dibatalkan jika device bukan joyeuse/miatoll, slot A/B terdeteksi,
bootloader tidak dapat dipastikan terbuka, boot bukan 128 MiB/header v2/page
4096, DTB berbeda dari referensi Lunaris, ramdisk Magisk/tidak didukung, atau
pemeriksaan repack gagal. DTB yang cocok bukan bukti ROM atau modul kompatibel.

Tidak ada reboot otomatis. Bila penulisan/pembacaan ulang gagal: JANGAN REBOOT;
pulihkan boot backup yang tepat dari recovery. Jika bootloop, pulihkan backup
yang sama. Jangan wipe data atau mengubah vbmeta untuk memaksa boot.

Image.gz SHA-256: {image_sha}
Sertifikat modul publik SHA-256: {public_cert_sha}
Toolchain: Neutron clang 24.0.0git. CONFIG_LRU_GEN_ENABLED=y di image.
Sumber kernel: https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/tree/c1e6f795b557b7bf92220c91f05a42b456de7a74
Resep dan patch: https://github.com/dwp29/Syntenthica/tree/arena/96cbd65a-syntenthica
'''


def collect(result: Path, tested_config: Path) -> dict[str, bytes]:
    build.check_inputs()
    if result.is_symlink() or not result.is_dir():
        raise ValueError('compile evidence must be an existing non-symlink directory')
    status_raw = (result / 'STATUS.json').read_bytes()
    if len(status_raw) > 200_000:
        raise ValueError('oversized build status')
    status = json.loads(status_raw)
    image = (result / 'Image.gz.DO-NOT-FLASH').read_bytes()
    config = (result / 'generated.config.txt').read_bytes()
    if not (8_000_000 < len(image) <= 25_000_000 and len(config) <= 1_000_000):
        raise ValueError('unexpected image or config size')
    image_sha = sha(image)
    if (status.get('kind') != 'SYNTHETICA_3_RC1_COMPILED_ONLY_DO_NOT_FLASH'
            or status.get('release') != build.EXPECTED_RELEASE
            or status.get('image_sha256') != image_sha
            or status.get('config_sha256') != sha(config)
            or status.get('base_source') != build.s2x.v3.SOURCE
            or status.get('manager_seccomp_patch_sha256') != build.PATCH_SHA256
            or status.get('tested_2_0_experiment_image_sha256') != build.TESTED_IMAGE_SHA256
            or status.get('tested_2_0_experiment_config_sha256') != build.TESTED_CONFIG_SHA256
            or status.get('compiler', {}).get('kind') != 'neutron'
            or status.get('compiler', {}).get('neutron_archive_sha256') != build.s2x.NEUTRON_SHA
            or status.get('mglru', {}).get('variant') != 'on'
            or status.get('mglru', {}).get('enabled_by_default') is not True
            or status.get('mglru', {}).get('runtime_tested') is not False
            or status.get('installer_created') is not False
            or status.get('private_key_exported') is not False
            or status.get('manager', {}).get('package') != 'net.ember.labs'
            or status.get('manager', {}).get('cert_sha256') != build.s2x.MANAGER_CERT_SHA):
        raise ValueError('unexpected 3.0-rc1 compile evidence')
    public_cert_sha = status.get('module_public_cert_sha256')
    if (not isinstance(public_cert_sha, str) or len(public_cert_sha) != 64
            or sha((result / 'module-signing-public-cert.x509').read_bytes()) != public_cert_sha):
        raise ValueError('module public certificate evidence mismatch')
    build.compare_tested_config(tested_config, config.decode('utf-8'))
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as f:
        raw = f.read(build.s2x.v3.MAX_RAW_IMAGE + 1)
    if len(raw) > build.s2x.v3.MAX_RAW_IMAGE:
        raise ValueError('uncompressed kernel exceeds size limit')
    if ('Linux version ' + build.EXPECTED_RELEASE + ' ').encode() not in raw:
        raise ValueError('unexpected kernel release')
    build.s2x.v3.verify_embedded_config(raw, config)
    for literal in (b'KernelSU', b'net.ember.labs', build.s2x.MANAGER_CERT_SHA.encode('ascii')):
        if literal not in raw:
            raise ValueError('expected KernelSU/Manager identity missing in image')

    raw_base = BASE.read_bytes()
    if sha(raw_base) != BASE_SHA256:
        raise ValueError('reference AnyKernel ZIP digest changed')
    with zipfile.ZipFile(io.BytesIO(raw_base)) as z:
        files = {name: read_zip_unique(z, name, 4_000_000) for name in BASE_FILES}
    name = 'META-INF/com/google/android/update-binary'
    backend = files[name]
    start, end = backend.find(b'debugging() {\n'), backend.find(b'\ncleanup() {\n')
    if start < 0 or end < start or backend.count(b'debugging() {\n') != 1:
        raise ValueError('unexpected AnyKernel debug function')
    files[name] = backend[:start] + b'debugging() { :; } # no persistent debug archive\n' + backend[end:]
    entry = (SCRIPTS / 'anykernel.sh').read_bytes()
    prepare = (SCRIPTS / 'prepare-boot.sh').read_bytes()
    if sha(entry) != ENTRY_SHA256 or sha(prepare) != PREPARE_SHA256:
        raise ValueError('tested installer template changed')
    entry = replace_once(entry, build.TESTED_IMAGE_SHA256.encode(), image_sha.encode())
    entry = replace_once(entry, b'kernel.string=Synthetica 2.0 Experimental - Neutron - MGLRU ON',
                         b'kernel.string=Synthetica 3.0-rc1 - Neutron - MGLRU ON')
    entry = replace_once(entry, b"'Synthetica 2.0 EXPERIMENTAL - Neutron / MGLRU ON'",
                         b"'Synthetica 3.0-rc1 TEST - Neutron / MGLRU ON'")
    if entry.count(REFERENCE_DTB_SHA256.encode()) != 1:
        raise ValueError('reference DTB guard is missing or ambiguous')
    metadata = {
        'kind': 'SYNTHETICA_3_RC1_RECOVERY_TEST_INSTALLER_NOT_DEVICE_TESTED',
        'release': build.EXPECTED_RELEASE,
        'target': 'joyeuse/miatoll; runtime boot structure and reference DTB guarded',
        'compiler': status['compiler']['clang_version'].splitlines()[0],
        'image_sha256': image_sha,
        'config_sha256': sha(config),
        'manager_seccomp_patch_sha256': build.PATCH_SHA256,
        'reference_experiment_image_sha256': build.TESTED_IMAGE_SHA256,
        'reference_experiment_config_sha256': build.TESTED_CONFIG_SHA256,
        'module_public_cert_sha256': public_cert_sha,
        'previous_experiment_module_public_cert_sha256': build.TESTED_CERT_SHA256,
        'reference_dtb_sha256': REFERENCE_DTB_SHA256,
        'compile_status_sha256': sha(status_raw),
        'physical_boot_test_this_image': 'NOT RUN',
        'manager_root_seccomp_this_image': 'NOT TESTED',
        'camera_0_6x': 'USER REPORTED FREEZE ON PREVIOUS EXPERIMENT; NO CAMERA FIX INCLUDED',
        'rom_module_abi_and_signatures': 'NOT VERIFIED; fresh module signing certificate',
        'avb_boot_trust': 'NOT VERIFIED; existing signature may not validate modified boot',
        'writes': ['boot partition only, after runtime checks'],
        'does_not_write': ['vbmeta', 'dtbo', 'vendor', 'system', 'userdata', 'ksud', 'modules'],
        'auto_backup': False,
    }
    files.update({'Image.gz': image, 'anykernel.sh': entry, 'tools/prepare-boot.sh': prepare,
                  'README-FLASH.txt': readme(image_sha, public_cert_sha).encode('utf-8'),
                  'BUILD-INFO.json': (json.dumps(metadata, indent=2) + '\n').encode('utf-8')})
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
            if sha(z.read('Image.gz')) != sha(files['Image.gz']):
                raise ValueError('created ZIP contains an unexpected kernel')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    report = {'path': str(output), 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes()),
              'image_sha256': sha(files['Image.gz']), 'kind': '3.0-rc1 recovery test; NOT device tested'}
    print(json.dumps(report, indent=2))
    return report


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
        print('3.0-rc1 packaging refused: ' + str(exc), file=sys.stderr)
        sys.exit(1)
