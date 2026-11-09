#!/usr/bin/env python3
"""Build a guarded ROM-specific experimental ZIP using the original 3.1 kernel.

The unchanged ROM boot is an exact SHA-pinned input. Only its kernel and the
unsigned embedded hash descriptor are changed. This is not a proven boot fix;
there is no module deployment and no external AVB validation. Never uploads the
input or output image. Writes only new files, not partitions.
"""
import argparse
import gzip
import io
import json
from pathlib import Path
import zipfile

import audit_synthetica3_boot as audit
import audit_boot_avb_hash as avb
import build_synthetica31_control_boot as repack
import package_synthetica31_control_boot as package
import build_synthetica3 as v3

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = '67c804f049c9bb00977c067e06bc663f75a8b7782b4f47bd2626b3fd5a36a847'
IMAGE = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
CONFIG = '4b53a2cb030e9aa55ff798a3ee5c773c0eb50e56cd36430d2874adcb56fa236d'
KIND = 'SYNTHETICA_3_1_REBUILT_KERNEL_NOT_DEVICE_VALIDATED'
RELEASE = '4.14.357-openela-synthetica-3.1'

README = '''SY N T H E T I C A 3.1 AVB-TEST — ZIP UJI EKSPERIMENTAL

Untuk Joyeuse dan ROM Infinity X 4.1 GAPPS 21.10.2026, bukan Android 16.
Kernel ini adalah kernel 3.1 yang sama seperti pada percobaan sebelumnya.
Perubahan: boot disiapkan dari boot ROM resmi yang cocok dengan image Anda,
ramdisk dan DTB dipertahankan, hash AVB unsigned embedded dihitung ulang.
Offline hash dan struktur cocok. Ini BUKAN perbaikan bootloop yang terbukti:
boot fisik, AVB eksternal, root, dan kompatibilitas modul ROM belum diuji.
Modul ROM tidak diganti; ketidakcocokan ABI/signature modul masih ada.

Syarat: bootloader terbuka; OrangeFox dan backup boot tepat yang dapat dipulihkan
siap; simpan backup di luar perangkat. Pastikan ROM target sudah terpasang.
ZIP tidak membuat backup. Installer menolak jika seluruh boot saat ini tidak
identik dengan referensi, termasuk boot yang telah dimodifikasi/patched. Jangan
mengganti boot hanya untuk memaksa lolos. Jangan flash di ROM Android 16.

Installer hanya menulis boot setelah pengecekan hash, lalu memverifikasi hasil
pembacaan ulang. Tidak menulis ksud, vendor, modul, system, dtbo atau vbmeta;
tidak reboot otomatis. Jika penulisan/readback gagal, JANGAN REBOOT dan pulihkan
backup boot yang tepat dari recovery. Jika bootloop, kembali ke recovery dan
pulihkan backup boot yang tepat. Jangan wipe/format data atau nonaktifkan AVB.

Hash boot referensi: {reference}
Hash boot kandidat: {candidate}
Hash kernel: {kernel}
'''

def original_kernel(evidence: Path) -> bytes:
    raw = repack.regular(evidence, 30_000_000)
    if repack.sha(raw) != EVIDENCE:
        raise ValueError('wrong original 3.1 evidence')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        expected = {'Image.gz.DO-NOT-FLASH','STATUS.json','generated.config.txt',
                    'module-signing-public-cert.x509','Module.symvers','System.map'}
        if len(names) != len(expected) or set(names) != expected or z.testzip():
            raise ValueError('invalid evidence members')
        if any(i.file_size > 25_000_000 for i in z.infolist()):
            raise ValueError('oversized evidence member')
        image = z.read('Image.gz.DO-NOT-FLASH')
        config = z.read('generated.config.txt')
        status = json.loads(z.read('STATUS.json'))
    if repack.sha(image) != IMAGE or repack.sha(config) != CONFIG:
        raise ValueError('kernel or config identity mismatch')
    if status.get('kind') != KIND or status.get('image_sha256') != IMAGE:
        raise ValueError('wrong build identity')
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as gz:
        kernel = gz.read(v3.MAX_RAW_IMAGE + 1)
    if len(kernel) > v3.MAX_RAW_IMAGE or kernel[0x38:0x3c] != b'ARMd':
        raise ValueError('invalid ARM64 image')
    if b'Linux version ' + RELEASE.encode() + b' ' not in kernel:
        raise ValueError('incorrect kernel release')
    v3.verify_embedded_config(kernel, config)
    return image


def create(reference: Path, evidence: Path, candidate: Path, output: Path):
    if output.exists() or output.is_symlink() or candidate.exists() or candidate.is_symlink():
        raise ValueError('refusing existing output')
    # A private module object is configured for this run, with all existing
    # structural/embedded-hash guards intact; the 3.1-control1 files are unchanged.
    repack.EVIDENCE, repack.IMAGE, repack.CONFIG = EVIDENCE, IMAGE, CONFIG
    repack.get_kernel = original_kernel
    result = repack.construct(reference, evidence, candidate)
    package.CANDIDATE = result['candidate_sha256']
    package.TEMPLATE = ROOT / 'build-kit/ci/s31-avbtest-installer/update-binary'
    package.README = README
    try:
        out = package.package(reference, candidate, output)
        # Independently re-read the ZIP payload, boot structure and AVB digest.
        with zipfile.ZipFile(output) as z:
            embedded = z.read('boot.img')
            entry = z.read(package.BINARY)
        if repack.sha(embedded) != result['candidate_sha256']:
            raise ValueError('packaged boot mismatch')
        if b'3.1-control1' in entry or b'3.1-AVB-test' not in entry:
            raise ValueError('installer label mismatch')
        avb_result = avb.inspect(candidate)
        compared = audit.compare_boot(audit.inspect_boot(reference), audit.inspect_boot(candidate), IMAGE)
        if not avb_result['embedded_boot_hash']['digest_matches'] or not all(compared['non_kernel_sections_match'].values()):
            raise ValueError('independent verification failed')
        return {**out, 'reference_sha256': repack.REFERENCE, 'kernel_sha256': IMAGE,
                'embedded_unsigned_avb_hash': 'MATCH', 'ramdisk_and_dtb_preserved': True,
                'device_boot': 'NOT TESTED', 'rom_module_loadability': 'NOT VERIFIED'}
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference','evidence','candidate','output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(create(a.reference, a.evidence, a.candidate, a.output), indent=2))

if __name__ == '__main__':
    main()
