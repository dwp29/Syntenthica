#!/bin/bash
# UFO-0.2: build pada 4.14.357 dengan seluruh fitur Synthetica 3.2.
#
# Kenapa pohon ini:
#   - 4.14.357 membawa perbaikan kernel nyata: kgsl use-after-free, KCAL,
#     penghapusan /system/addon.d dari UID tak berhak.
#   - Pohon Saamitk/kernel_xiaomi_sm6250-switchoff SUDAH membawa SuSFS v2.3.0,
#     KernelSU-Next, dan NoMount v2.0.0. Jadi yang perlu ditanam hanya MGLRU dan
#     UCLAMP, lewat enam patch asli Synthetica yang menempel bersih.
#
# Manager: nilai bawaan pohon, yaitu sertifikat manager KernelSU-Next resmi.
#   Kernel ini TIDAK dipatok ke APK apa pun. Sebelumnya sempat dipatok ke
#   sertifikat Pure Manager, dan itu keliru -- Pure Manager adalah file explorer,
#   bukan manager KernelSU, jadi memasang sertifikatnya tidak memberinya
#   kemampuan mengelola izin root. Manager resmi KernelSU-Next dipakai apa adanya.
#
# Catatan ukuran sertifikat: manager KernelSU-Next resmi jauh di bawah batas yang
# dipakai check_block(), jadi tidak perlu mengubah batas. Kalau suatu saat manager
# yang dipakai lebih besar dari CERT_MAX_LENGTH, apply_synthetica357.sh sudah
# menaikkannya ke 4096 dan verify_manager_bound.py akan menolak build bila batas
# itu tidak benar-benar ada di image.

set -euo pipefail

TREE="${1:?usage: build_ufo02.sh <kernel-tree>}"
WORK="${2:-out}"
JOBS="${JOBS:-$(nproc)}"

# Hash sertifikat APK Pure Manager 0.10.0 (RELEASEKEY).
# Diperiksa ulang oleh verify_manager.sh; jangan ditulis tanpa bukti.
# Manager: pakai milik KernelSU-Next, bukan APK kita.
#
# Sebelumnya kernel ini dipatok ke sertifikat Pure Manager 0.10.0. Itu keliru:
# Pure Manager adalah file explorer, bukan manager KernelSU. Memasang sertifikatnya
# di kernel tidak membuatnya mengelola izin root -- ia hanya mendapat perlakuan
# manager (tidak di-umount modulnya) dan bisa menjalankan su. Yang benar adalah
# membiarkan nilai bawaan pohon ini, yaitu sertifikat manager KernelSU-Next resmi.
#
# Nilai bawaan sengaja TIDAK ditulis ulang di sini. Menuliskannya berarti build
# tetap bisa diam-diam berbeda dari pohon bila upstream mengubahnya. Baris di
# bawah hanya memastikan nilainya kosong, sehingga Kbuild memakai bawaannya.
KSU_MGR=""

echo "-- make olddefconfig"
# shellcheck disable=SC2086
make O="$WORK" ARCH=arm64 $MAKEARGS $KSU_MGR olddefconfig

echo "-- pastikan fitur yang diminta benar-benar menyala di config final"
python3 - "$WORK/.config" <<'PY'
import pathlib
import sys

cfg = pathlib.Path(sys.argv[1]).read_text().splitlines()
rows = {}
for l in cfg:
    l = l.strip()
    if l.startswith("CONFIG_") and "=" in l:
        k, _, v = l.partition("=")
        rows[k] = v
    elif l.startswith("# ") and "is not set" in l:
        rows[l.split()[1]] = "n"

required = {
    "CONFIG_LRU_GEN": "y",
    "CONFIG_LRU_GEN_ENABLED": "y",
    "CONFIG_UCLAMP_TASK": "y",
    "CONFIG_UCLAMP_TASK_GROUP": "y",
    "CONFIG_SCHED_WALT": "y",
    "CONFIG_SCHED_TUNE": "y",
    "CONFIG_KSU": "y",
    "CONFIG_KSU_MANUAL_HOOK": "y",
    "CONFIG_KSU_SUSFS": "y",
    "CONFIG_NOMOUNT": "y",
}
bad = []
for k, want in required.items():
    got = rows.get(k, "TIDAK ADA")
    mark = "OK " if got == want else "GAGAL"
    if got != want:
        bad.append(f"{k}={got} (butuh {want})")
    print(f"{mark} {k}={got}")

if bad:
    print("\nCONFIG FINAL TIDAK SESUAI:")
    for b in bad:
        print("  ", b)
    sys.exit(1)
print("\nconfig final: semua fitur menyala")
PY

echo "-- compile"
# shellcheck disable=SC2086
make -j"$JOBS" O="$WORK" ARCH=arm64 $MAKEARGS $KSU_MGR Image.gz

ls -l "$WORK/arch/arm64/boot/Image.gz"
