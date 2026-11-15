#!/bin/bash
# UFO-0.2: build pada 4.14.357 dengan seluruh fitur Synthetica 3.2.
#
# Kenapa pohon ini, bukan Kinesis 4.14.344:
#   - 4.14.357 membawa perbaikan kernel yang nyata: kgsl use-after-free, KCAL,
#     hidung /system/addon.d dari UID tak berhak.
#   - Pohon Saamitk/kernel_xiaomi_sm6250-switchoff SUDAH membawa SuSFS v2.3.0,
#     KernelSU-Next, dan NoMount v2.0.0. Jadi yang perlu ditanam hanya MGLRU dan
#     UCLAMP, lewat enam patch asli Synthetica yang menempel bersih.
#
# Kenapa manager memakai hash sendiri:
#   is_manager_apk() TIDAK mencocokkan nama paket (kecuali KSU_MANAGER_PACKAGE
#   di-set saat build). Ia membandingkan panjang sertifikat v2 dan sha256-nya:
#       EXPECTED_MANAGER_SIZE / EXPECTED_MANAGER_HASH
#   Default pohon ini 0x3e6 (998 byte) / 79e59011..., yaitu sertifikat manager
#   KernelSU-Next resmi. APK Pure Manager kita ditandatangani kunci kita sendiri:
#       1373 byte (0x55d), sha256 a2f94245...43f2d8
#   Tanpa override, kernel akan menganggap APK kita bukan manager, dan semua
#   supercall ditolak. Jadi dua variabel itu WAJIB diisi dari APK yang dipakai.
set -euo pipefail

TREE="${1:?usage: build_ufo02.sh <kernel-tree>}"
WORK="${2:-out}"
JOBS="${JOBS:-$(nproc)}"

# Hash sertifikat APK Pure Manager 0.10.0 (RELEASEKEY).
# Diperiksa ulang oleh verify_manager.sh; jangan ditulis tanpa bukti.
MGR_SIZE="0x55d"
MGR_HASH="a2f942452eec1cd8763e6cf33b9937c1a99b3849c62773a73bf444776743f2d8"

cd "$TREE"
mkdir -p "$WORK"
cp arch/arm64/configs/vendor/xiaomi/miatoll_defconfig "$WORK/.config"

export ARCH=arm64
export CROSS_COMPILE_ARM32=arm-linux-gnueabi-
MAKEARGS="CC=clang CROSS_COMPILE=aarch64-linux-gnu- LD=ld.lld AR=llvm-ar"
MAKEARGS="$MAKEARGS NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump"
MAKEARGS="$MAKEARGS STRIP=llvm-strip CLANG_TRIPLE=aarch64-linux-gnu-"

# Kbuild reads these two from the make line / environment and turns them into
# -DEXPECTED_MANAGER_SIZE / -DEXPECTED_MANAGER_HASH.
KSU_MGR="KSU_NEXT_MANAGER_SIZE=$MGR_SIZE KSU_NEXT_MANAGER_HASH=$MGR_HASH"

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
