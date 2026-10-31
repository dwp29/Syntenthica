#!/bin/bash
# =============================================================================
#  build-rollercoaster.sh — builder 3 build Rollercoaster 0.0.1
#
#  Pakai:  bash build-rollercoaster.sh <tree> <profile> [jobs]
#     profile: chronicle | lite | critical
#
#  Profil:
#     chronicle = KernelSU-Next · harian · hiding/integrity lengkap
#     lite      = NonKSU · harian · baterai + tanpa jejak root
#     critical  = KernelSU-Next · gaming · FPS tinggi
#
#  Output: output/Rollercoaster-<Profil>-<versi>.zip
# =============================================================================
set -euo pipefail

TREE="$(cd "${1:?usage: build-rollercoaster.sh <tree> <profile> [jobs]}" && pwd)"
PROFILE="${2:?profile: chronicle|lite|critical}"
JOBS="${3:-2}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(cd "$SELF/.." && pwd)"

KVER="$(grep -E '^version=' "$SELF/VERSION" | cut -d= -f2)"
case "$PROFILE" in
  chronicle) NAME="Rollercoaster-Chronicle"; KSU="yes"; DESC="KernelSU-Next - daily - integrity/hiding" ;;
  synthetica) NAME="Rollercoaster-Chronicle"; KSU="yes"; DESC="KernelSU-Next - daily tuned (Synthetica 2.0)" ;;
  lite)      NAME="Rollercoaster-Lite";      KSU="no";  DESC="NonKSU - daily - battery - no root traces" ;;
  critical)  NAME="Rollercoaster-Critical";  KSU="yes"; DESC="KernelSU-Next - gaming - high FPS" ;;
  port)      NAME="Rollercoaster-Port";      KSU="yes"; DESC="KernelSU-Next - ROM port miatoll (peaceSU/HyperOS4/ColorOS16)" ;;
  portn)     NAME="Rollercoaster-PortN";     KSU="yes"; DESC="KernelSU-Next - ROM port berbasis vendor/kernel Nezuko (modul ROM boleh dimuat)" ;;
  *) echo "profil tidak dikenal: $PROFILE"; exit 1 ;;
esac
# NOMOUNT hanya untuk build non-port (port butuh mount nyata untuk metamodule/Zygisk)
NOMOUNT="yes"; case "$PROFILE" in port|portn) NOMOUNT="no" ;; esac

# --- SYNTHETICA-PULSE: identity override (ADDITIVE, see ci/rollercoaster/README.md) ----------
# Nothing changes when neither variable is set: NAME and KVER keep the values from VERSION and the
# profile case above. Only the release string (and therefore vermagic) is affected - no config,
# no patch, no source file is touched by this.
NAME="${SP_BUILD_NAME:-$NAME}"
KVER="${SP_BUILD_KVER:-$KVER}"

LOCALVER="-${NAME}-${KVER}"
case "$PROFILE" in port|portn) LOCALVER="-${NAME}-${KVER}-perf" ;; esac
OUT="$TREE/out-$PROFILE"
DEFCONFIG="arch/arm64/configs/vendor/xiaomi/miatoll_rollercoaster_defconfig"
OUTDIR="${OUTDIR:-$WS/output}"
ZIP="$OUTDIR/${NAME}-${KVER}.zip"

export PATH="/usr/lib/llvm-18/bin:/usr/lib/ccache:/usr/bin:/bin:$PATH"
export ARCH=arm64 LC_ALL=C
export KBUILD_BUILD_USER="graziemille"
export KBUILD_BUILD_HOST="rollercoaster-build"
export KBUILD_BUILD_TIMESTAMP="$(date -u '+%a %b %d %H:%M:%S UTC %Y')"

MO=(
  O="$OUT" ARCH=arm64
  CC=clang CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu-
  LD=ld.lld AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump
  READELF=llvm-readelf STRIP=llvm-strip SIZE=llvm-size
  HOSTCC=clang HOSTCXX=clang++ HOSTLD=ld.lld HOSTAR=llvm-ar
  LLVM=1 LLVM_IAS=1
  KCFLAGS="-Wno-error=implicit-int -Wno-error=strict-prototypes"
)
# --- sertifikat Manager Rollercoaster (eksklusif) ---------------------------
# KernelSU-Next hanya mengakui Manager bila sertifikat APK-nya persis sama
# dengan yang ditanam saat build (kernel/manager/apk_sign.c).
# Nilai diambil dari output/manager-ui/rollercoaster.jks (SHA-256 sertifikat DER).
KSU_MANAGER_CERT_SIZE="${KSU_MANAGER_CERT_SIZE:-0x597}"
KSU_MANAGER_CERT_HASH="${KSU_MANAGER_CERT_HASH:-c2ed2ed91cc0cd68a4c3a1cb3f7acd2e549a995c2599cf86226e0e6d1db40b07}"
KSU_MANAGER_PKG="${KSU_MANAGER_PKG:-com.rifsxd.ksunext}"

if [ "$KSU" = "yes" ]; then
  MO+=(KSU_VERSION_OVERRIDE=34000 KSU_VERSION_TAG_OVERRIDE=ksun-legacy-susfs-v2)
  MO+=(KSU_NEXT_MANAGER_SIZE="$KSU_MANAGER_CERT_SIZE")
  MO+=(KSU_NEXT_MANAGER_HASH="$KSU_MANAGER_CERT_HASH")
  MO+=(KSU_MANAGER_PACKAGE="$KSU_MANAGER_PKG")
fi

cd "$TREE"
echo "=============================================================="
echo " $NAME $KVER  (profil: $PROFILE, jobs: $JOBS)"
echo "=============================================================="

# --- patch wajib (idempotent, berbasis penanda) ------------------------------
# Penanda diperiksa lebih dulu supaya build tidak bergantung pada pembacaan
# berkas patch saat runtime (pernah gagal ENOENT di sandbox).
apply_patch() { # <patch> <berkas-penanda> <penanda> <present|absent> <deskripsi>
  local pf="$1" mf="$2" mk="$3" want="$4" desc="$5" state="absent"
  grep -q "$mk" "$mf" 2>/dev/null && state="present"
  if [ "$state" = "$want" ]; then echo "[patch] $desc: sudah terpasang"; return 0; fi
  if [ -r "$pf" ] && git apply --check "$pf" 2>/dev/null; then
    git apply "$pf"; echo "[patch] $desc: diterapkan"; return 0
  fi
  echo "[patch] GAGAL: $desc belum terpasang dan patch tidak bisa dipakai"; return 1
}
# --- sertifikat Manager: batas panjang sertifikat di KernelSU-Next -------------
# KernelSU-Next membatasi sertifikat 1024 byte. Sertifikat RSA 4096 kita 1431 byte
# (0x597). Tanpa kenaikan batas ini, seluruh pemeriksaan sha256 menjadi kode mati
# dan Manager TIDAK PERNAH dikenali (gejala: menu Manager mati / "bukan Manager").
APK_SIGN_C="$TREE/drivers/kernelsu/manager/apk_sign.c"
if [ -f "$APK_SIGN_C" ]; then
  if grep -q "#define CERT_MAX_LENGTH 1024" "$APK_SIGN_C"; then
    sed -i 's/#define CERT_MAX_LENGTH 1024/#define CERT_MAX_LENGTH 2048/' "$APK_SIGN_C"
    echo "[patch] sertifikat Manager: batas 1024 -> 2048 byte (wajib untuk RSA 4096 kita)"
  else
    echo "[patch] sertifikat Manager: batas sertifikat sudah >= 2048 byte"
  fi
fi

# --- blok tanda tangan v3 / v3.1 tidak boleh membatalkan verifikasi v2 --------
# KernelSU-Next menolak APK bila menemukan blok v3/v3.1 ("Unexpected v3 signature
# scheme found!"). Akibatnya APK yang ditandatangani alat modern (v2+v3) tidak
# pernah dikenali sebagai Manager: uname menampilkan m0, Manager "No root",
# padahal su berjalan. Identitas tetap ditentukan sertifikat blok v2.
if [ -f "$APK_SIGN_C" ]; then
  if grep -q "v2 verified - accepted (Rollercoaster)" "$APK_SIGN_C"; then
    echo "[patch] toleransi blok v3: sudah terpasang"
  else
    if git apply --check "$SELF/patches/apk-sign-accept-v3.patch" 2>/dev/null; then
      git apply "$SELF/patches/apk-sign-accept-v3.patch"
      echo "[patch] toleransi blok v3: diterapkan"
    else
      # tree versi lain: penolakan dilakukan lewat daftar id blok
      sed -i 's/id != 0x42726577u/id != 0x42726577u \&\& id != 0xf05368c0u \&\& id != 0x1b93ad61u/' "$APK_SIGN_C"
      echo "[patch] toleransi blok v3: diterapkan lewat jalur id blok"
    fi
  fi
  # verifikasi: tidak boleh ada lagi penolakan v3 yang aktif
  if grep -q "Unexpected v3 signature scheme found" "$APK_SIGN_C"; then
    echo "[patch] GAGAL: penolakan v3 masih ada di $APK_SIGN_C"; exit 1
  fi
  if ! grep -q "v2 verified - accepted (Rollercoaster)" "$APK_SIGN_C" \
     && ! grep -q "id != 0xf05368c0u" "$APK_SIGN_C"; then
    echo "[patch] GAGAL: toleransi v3 tidak terpasang"; exit 1
  fi
  echo "  OK   apk_sign: blok v3 diterima, verifikasi v2 tetap wajib"
fi

apply_patch "$SELF/patches/aw8624-drop-timed_output.patch" \
            drivers/misc/aw8624_haptic/aw8624.h "timed_output" absent \
            "aw8624-drop-timed_output" || exit 1
# Tree dipakai bergantian antar profil: kembalikan module.c dulu supaya patch
# vermagic (khusus port) tidak menempel ke build non-port.
case "$PROFILE" in
  chronicle|critical|lite|synthetica)
    if grep -q "diterima (Rollercoaster-Port)" "$TREE/kernel/module.c" 2>/dev/null; then
      git checkout -- kernel/module.c 2>/dev/null && echo "[patch] vermagic port dikembalikan (bukan build port)"
    fi ;;
esac
case "$PROFILE" in port|portn)
  apply_patch "$SELF/patches/port-allow-foreign-vermagic.patch" \
              kernel/module.c "diterima (Rollercoaster-Port)" present \
              "port-allow-foreign-vermagic" || exit 1
  ;;
esac

# --- susun defconfig ---------------------------------------------------------
# PENTING: basis = defconfig lengkap milik tree (bukan cuma blok kita), kalau
# tidak olddefconfig akan mematikan hampir semua driver dan kernel tidak boot.
BASE_DEFCONFIG="arch/arm64/configs/vendor/xiaomi/miatoll_defconfig"
if git cat-file -e "HEAD:$BASE_DEFCONFIG" 2>/dev/null; then
    git show "HEAD:$BASE_DEFCONFIG" > "$DEFCONFIG"
else
    cp "$BASE_DEFCONFIG" "$DEFCONFIG"
fi
cat "$SELF/profiles/00-common.config" "$SELF/profiles/$PROFILE.config" >> "$DEFCONFIG"
printf '\nCONFIG_LOCALVERSION="%s"\n' "$LOCALVER" >> "$DEFCONFIG"

make "${MO[@]}" vendor/xiaomi/miatoll_rollercoaster_defconfig >/dev/null
make "${MO[@]}" olddefconfig >/dev/null

# --- audit: gagal cepat kalau ada yang tidak tercapai ------------------------
fail=0
chk() { # chk <SYMBOL> <y|n>
  local sym="$1" want="$2" line
  line="$(grep -E "^(CONFIG_${sym}=|# CONFIG_${sym} is not set)" "$OUT/.config" 2>/dev/null | head -1 || true)"
  case "$want" in
    y) grep -qx "CONFIG_${sym}=y" "$OUT/.config" || { echo "  FAIL $sym harus y"; fail=1; return; } ;;
    n) # simbol yang tidak ada sama sekali (karena induknya off) juga dianggap n
       if grep -q "^CONFIG_${sym}=" "$OUT/.config"; then echo "  FAIL $sym masih aktif"; fail=1; return; fi ;;
  esac
  printf "  OK   %-32s %s\n" "$sym" "$line"
}
echo "--- audit config ---"
chk BPF_EVENTS y; chk RD_LZ4 y; chk EROFS_FS y; chk DM_DEFAULT_KEY y
chk DEBUG_LIST n; chk BUG_ON_DATA_CORRUPTION n; chk DEBUG_INFO n
chk CRYPTO_LZ4 y; chk FRONTSWAP y; chk DEFAULT_BBR y; chk DEFAULT_FQ_CODEL y
if [ "$KSU" = "yes" ]; then
  chk KSU y; chk KSU_MANUAL_HOOK y; chk KSU_SUSFS y; chk KSU_SUSFS_SUS_PATH y
  chk KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG y; chk KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS y
  if [ "$NOMOUNT" = "yes" ]; then chk NOMOUNT y; else chk NOMOUNT n; fi
else
  chk KSU n; chk KSU_SUSFS n; chk NOMOUNT n
fi
case "$PROFILE" in
  critical) chk HZ_300 y; chk CPU_BOOST y ;;
  lite)     chk CPU_BOOST n; chk CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y ;;
  chronicle) chk CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y ;;
  synthetica) chk CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y; chk MQ_IOSCHED_DEADLINE y ;;
  port)     chk CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y; chk PREEMPT y
            chk MODVERSIONS n; chk MODULE_UNLOAD y; chk MODULE_FORCE_LOAD y ;;
  portn)    chk CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y; chk PREEMPT y
            chk MODVERSIONS n; chk MODULE_UNLOAD y; chk MODULE_FORCE_LOAD y
            chk MODULE_SIG n; chk PSTORE y; chk PSTORE_CONSOLE y
            chk PSTORE_PMSG y; chk PSTORE_RAM y
            chk KSU_SUSFS_SUS_PATH y; chk KSU_SUSFS_SUS_MOUNT y
            chk KSU_SUSFS_SUS_KSTAT y; chk KSU_SUSFS_SUS_MAP y
            chk KSU_SUSFS_SPOOF_UNAME y; chk KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG y
            chk KSU_SUSFS_OPEN_REDIRECT y; chk KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS y
            chk F2FS_FS_COMPRESSION y; chk IOSCHED_BFQ y ;;
esac
# khusus port: pastikan uname berakhir -perf dan patch vermagic benar-benar masuk
case "$PROFILE" in port|portn)
  case "$LOCALVER" in *-perf) echo "  OK   LOCALVERSION berakhiran -perf" ;;
    *) echo "  FAIL LOCALVERSION tidak berakhiran -perf"; fail=1 ;; esac
  grep -q "diterima (Rollercoaster-Port)" "$TREE/kernel/module.c" \
    && echo "  OK   patch vermagic lintas-rilis aktif" \
    || { echo "  FAIL patch vermagic tidak ada"; fail=1; }
  ;;
esac
# --- audit sertifikat Manager (hanya build ber-KSU) ---
# KernelSU-Next membaca nilai ini dari variabel make KSU_NEXT_MANAGER_*;
# verifikasi byte-nya dilakukan setelah build (lihat ROLLERCOASTER-CERT-VERIFY).
if [ "$KSU" = "yes" ]; then
  echo "  OK   manager-cert                  size=$KSU_MANAGER_CERT_SIZE hash=${KSU_MANAGER_CERT_HASH:0:16}..."
fi
grep -E '^CONFIG_LOCALVERSION=' "$OUT/.config"
[ "$fail" = 0 ] || { echo "AUDIT GAGAL — build dihentikan"; exit 1; }

# --- prebuild ---------------------------------------------------------------
echo "--- prebuild ---"
make -j"$JOBS" "${MO[@]}" security/selinux/ >/dev/null
make -j"$JOBS" "${MO[@]}" fs/erofs/ lib/zstd/ >/dev/null
[ "$KSU" = "yes" ] && make -j"$JOBS" "${MO[@]}" drivers/kernelsu/ fs/susfs.o >/dev/null

# --- build -----------------------------------------------------------------
echo "--- FULL BUILD $(date -u) ---"
make -j"$JOBS" "${MO[@]}" Image.gz
ls -la "$OUT/arch/arm64/boot/Image.gz"

# --- kemas AnyKernel3 ------------------------------------------------------
echo "--- kemas AnyKernel3 ---"
WORK="$OUT/ak3pkg"; rm -rf "$WORK"; mkdir -p "$WORK"
cp -a "$TREE/AnyKernel3/." "$WORK/"
find "$WORK" -name .gitignore -delete
# skrip flash milik kita (tanpa backup otomatis, tanpa baris progres berisik)
cp -f "$SELF/anykernel/anykernel.sh" "$WORK/anykernel.sh"
# payload userspace KernelSU — hanya untuk build ber-root (Lite tanpa KSU)
if [ "$KSU" = "yes" ]; then
  KS="$SELF/anykernel/ksud"
  [ -s "$KS" ] || { echo "GAGAL: $KS tidak ada"; exit 1; }
  cp -f "$KS" "$WORK/ksud"; chmod 0755 "$WORK/ksud"
fi
cp "$OUT/arch/arm64/boot/Image.gz" "$WORK/Image.gz"
sed -i "s|^kernel.string=.*|kernel.string=$NAME $KVER by graziemille - Linux 4.14.357-openela - miatoll|" "$WORK/anykernel.sh"
[ "$PROFILE" = "port" ] && sed -i "s|^kernel.string=.*|kernel.string=$NAME $KVER (compat: peaceSU / HyperOS4 / ColorOS16) by graziemille|" "$WORK/anykernel.sh"
sed -i "s|^kernel.compiler=.*|kernel.compiler=clang 18.1.8 + ld.lld (LLVM_IAS) - tanpa gcc|"              "$WORK/anykernel.sh"
sed -i "s|^kernel.made=.*|kernel.made=graziemille|"                                                   "$WORK/anykernel.sh"
sed -i "s|^kernel.version=.*|kernel.version=$NAME-$KVER|"                                             "$WORK/anykernel.sh"
sed -i "s|^message.word=.*|message.word=$NAME $KVER|"                                                 "$WORK/anykernel.sh"

# --- verifikasi paket sebelum dikemas ---------------------------------------
grep -q "Mencadangkan boot" "$WORK/anykernel.sh" && { echo "GAGAL: backup otomatis masih ada"; exit 1; }
[ -s "$WORK/Image.gz" ] || { echo "GAGAL: Image.gz tidak ada di paket"; exit 1; }
if [ "$KSU" = "yes" ]; then [ -s "$WORK/ksud" ] || { echo "GAGAL: ksud tidak ada di paket"; exit 1; }
else [ -e "$WORK/ksud" ] && { echo "GAGAL: Lite tidak boleh membawa ksud"; exit 1; }; fi
grep -q "^kernel.version=$NAME-$KVER" "$WORK/anykernel.sh" || { echo "GAGAL: kernel.version tidak sesuai"; exit 1; }
echo "  OK   paket: Image.gz + ksud + anykernel.sh (tanpa backup otomatis)"

mkdir -p "$OUTDIR"
( cd "$WORK" && zip -r9 "$ZIP" . -x '*.git*' >/dev/null )

# --- varian permissive (khusus PortN) --------------------------------------
# Hanya beda satu baris: androidboot.selinux=permissive lewat patch_cmdline().
# Dipakai bila ROM port menuntut Permissiver. Image-nya sama persis.
if [ "$PROFILE" = "portn" ]; then
  PERMW="$OUT/ak3perm"; rm -rf "$PERMW"; cp -a "$WORK" "$PERMW"
  python3 - "$PERMW/anykernel.sh" <<'EOP'
import sys
p = sys.argv[1]; s = open(p).read()
anchor = "dump_boot;"
assert anchor in s, "dump_boot tidak ditemukan"
s = s.replace(anchor,
    '# Rollercoaster-PortN: SELinux permissive untuk port yang menuntut Permissiver.\n'
    'patch_cmdline "androidboot.selinux" "androidboot.selinux=permissive"\n\n' + anchor, 1)
open(p, 'w').write(s)
EOP
  ZIPPERM="$OUTDIR/${NAME}-${KVER}-permissive.zip"
  rm -f "$ZIPPERM"
  ( cd "$PERMW" && zip -r9 "$ZIPPERM" . -x '*.git*' >/dev/null )
  if ! unzip -p "$ZIPPERM" anykernel.sh | grep -q 'androidboot.selinux=permissive'; then
    echo "GAGAL: zip permissive tidak memuat patch_cmdline"; exit 1
  fi
  if unzip -p "$ZIP" anykernel.sh | grep -q 'androidboot.selinux=permissive'; then
    echo "GAGAL: zip enforcing ikut memuat permissive"; exit 1
  fi
  ( cd "$OUTDIR" && sha256sum "${NAME}-${KVER}-permissive.zip" > "${NAME}-${KVER}-permissive.zip.sha256" )
  echo "  OK   varian permissive: $ZIPPERM"
fi
( cd "$OUTDIR" && sha256sum "${NAME}-${KVER}.zip" > "${NAME}-${KVER}.zip.sha256" )
echo "=============================================================="
echo " SELESAI: $ZIP"
echo " $(cat "$OUTDIR/${NAME}-${KVER}.zip.sha256")"
unzip -l "$ZIP" | tail -2
echo "=============================================================="
