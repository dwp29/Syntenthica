#!/system/bin/sh
# Synthetica — Kernel Compatibility Check (read-only).
#
# Menjawab satu pertanyaan: kalau Synthetica Manager 6.0.0 tidak bisa root di
# kernel ini, LAPISAN MANA yang gagal?
#
#   Lapisan 1  Driver KSU ada di kernel?      (tidak ada -> mustahil root via KSU)
#   Lapisan 2  su benar-benar memberi UID 0?  (kalau ya, Universal Root Bridge HIDUP)
#   Lapisan 3  Manager Synthetica dikenali?   (kalau tidak -> fitur KSU tertutup)
#
# Skrip ini TIDAK mengubah apa pun. Tidak ada tulis ke sysfs/procfs, tidak
# memuat modul, tidak memasang apa pun. Aman dijalankan di perangkat apa pun.
#
# Pakai:
#   adb shell 'sh /data/local/tmp/synthetica-compat-check.sh'
#   atau dari Termux: sh synthetica-compat-check.sh
#   atau lewat root:  su -c 'sh synthetica-compat-check.sh'

set -f
PKG=${SYNTH_PKG:-net.ember.labs}

say() { printf '%s\n' "$*"; }
rule() { printf '%s\n' '------------------------------------------------------------'; }
head2() { rule; printf '== %s\n' "$*"; rule; }

YES=0
NO=0
UNKNOWN=0
ok()   { printf '  [OK]    %s\n' "$*"; YES=$((YES+1)); }
bad()  { printf '  [GAGAL] %s\n' "$*"; NO=$((NO+1)); }
warn() { printf '  [??]    %s\n' "$*"; UNKNOWN=$((UNKNOWN+1)); }

# Setiap pemeriksaan hanya membaca. Semua path dibatasi ke root yang wajar.
read1() { [ -r "$1" ] && head -n 1 "$1" 2>/dev/null | tr -d '\r'; }

# ---------------------------------------------------------------- 0. identitas
head2 "0. Perangkat & kernel"
UNAME_R=$(uname -r 2>/dev/null)
UNAME_M=$(uname -m 2>/dev/null)
say "  uname -r        : ${UNAME_R:-?}"
say "  arsitektur      : ${UNAME_M:-?}"
say "  Android         : $(getprop ro.build.version.release 2>/dev/null) (SDK $(getprop ro.build.version.sdk 2>/dev/null))"
say "  perangkat       : $(getprop ro.product.device 2>/dev/null) / $(getprop ro.product.model 2>/dev/null)"
say "  build kernel    : $(read1 /proc/version)"

# Kernel 5.1x = GKI 2.0. BakaSU mendukung 3.4+ tapi hook manual.
case "$UNAME_R" in
    5.1?.*|6.*) say "  kategori        : GKI 2.0 (>= 5.10)" ;;
    5.*)        say "  kategori        : GKI 1.0 (5.4-5.9)" ;;
    4.*|3.*)    say "  kategori        : non-GKI lama (< 5.0) — butuh hook manual" ;;
    *)          say "  kategori        : tidak dikenali" ;;
esac

# ------------------------------------------------------- 1. driver KSU di kernel
head2 "1. Driver KSU di kernel"
DRIVER=0
if [ -r /proc/modules ] && grep -q '^kernelsu ' /proc/modules 2>/dev/null; then
    ok "modul 'kernelsu' tercantum di /proc/modules (mode LKM)"
    DRIVER=1
fi
if ls -l /proc/self/fd 2>/dev/null | grep -q 'ksu_driver'; then
    ok "fd driver '[ksu_driver]' sudah terbuka (driver aktif)"
    DRIVER=1
fi
for D in /data/adb/ksu /data/adb/ksud /data/adb/modules/kernelsu; do
    [ -e "$D" ] && say "  ada            : $D"
done
if [ "$DRIVER" -eq 0 ]; then
    if [ -e /data/adb/ksu ] || [ -e /data/adb/ksud ]; then
        warn "direktori KSU ada, tapi driver tidak terlihat di process ini"
        say "                    (normal bila su belum diberikan ke shell ini)"
    else
        bad "tidak ada jejak driver KSU — kernel ini kemungkinan tanpa KSU"
    fi
fi

# ------------------------------------------------------------ 2. su & UID 0
head2 "2. su benar-benar memberi root?"
UID_NOW=$(id -u 2>/dev/null)
say "  id -u sekarang  : ${UID_NOW:-?}"
SU_PATH=$(command -v su 2>/dev/null)
if [ -n "$SU_PATH" ]; then
    ok "binary su ditemukan: $SU_PATH"
else
    warn "binary su tidak ada di PATH shell ini"
fi

ROOT_WORKS=0
if [ "$UID_NOW" = "0" ]; then
    ok "shell ini SUDAH root (UID 0)"
    ROOT_WORKS=1
elif [ -n "$SU_PATH" ]; then
    # Coba sekali, dengan timeout supaya tidak menggantung bila prompt tidak muncul.
    TRY=$( (echo 'id -u'; ) | timeout 8 su 2>/dev/null | tail -n 1 | tr -d '\r' )
    case "$TRY" in
        0) ok "su berhasil memberi UID 0"; ROOT_WORKS=1 ;;
        '') bad "su tidak menjawab dalam 8 detik (prompt tidak muncul / ditolak)" ;;
        *)  bad "su menjawab UID '$TRY', bukan 0 (permintaan belum disetujui)" ;;
    esac
fi
if [ "$ROOT_WORKS" -eq 0 ]; then
    say ""
    say "  PENTING: di kernel KernelSU/BakaSU/SukiSU/APatch, permintaan root untuk"
    say "  paket '$PKG' HARUS disetujui dari manager BAWAAN kernel itu"
    say "  (mis. BakaSU Manager). Synthetica Manager tidak bisa menyetujui dirinya sendiri."
    say "  Di Magisk, cukup buka Magisk -> Superuser -> izinkan Synthetica."
fi

# ------------------------------------------------ 3. pengenalan manager & UAPI
head2 "3. Apakah kernel mengenali Synthetica Manager?"
KSUD=""
for C in /data/adb/ksud /data/adb/ksu/bin/ksud; do
    [ -x "$C" ] && KSUD=$C && break
done
if [ -n "$KSUD" ]; then
    say "  ksud            : $KSUD"
    say "  ksud version    : $("$KSUD" --version 2>&1 | head -n 2 | tr '\n' ' ')"
    V=$("$KSUD" debug version 2>/dev/null | head -n 1)
    [ -n "$V" ] && say "  driver version  : $V"
else
    warn "ksud tidak ditemukan di /data/adb (mungkin bukan KSU-family, atau butuh root)"
fi

# Siapa yang terpasang sebagai manager KSU di perangkat ini?
say ""
say "  Paket manager yang terpasang:"
FOUND_MGR=0
for P in com.sukisu.ultra me.bakasu.manager io.github.vvb2060.kernelsu \
         com.rifsxd.ksunext com.topjohnwu.magisk me.weishu.kernelsu \
         com.rifsxd.ksunext.spoofed; do
    if pm list packages 2>/dev/null | grep -qx "package:$P"; then
        say "    - $P"
        FOUND_MGR=1
    fi
done
[ "$FOUND_MGR" -eq 0 ] && say "    (tidak ada manager KSU/Magisk yang terdeteksi)"
if pm list packages 2>/dev/null | grep -qx "package:$PKG"; then
    ok "Synthetica Manager ($PKG) terpasang"
else
    warn "Synthetica Manager ($PKG) TIDAK terpasang"
fi

say ""
say "  Kenapa ini penting:"
say "  Kernel KSU memverifikasi manager lewat HASH SHA-256 sertifikat APK yang"
say "  dikompilasi ke dalam kernel (EXPECTED_MANAGER_HASH) + nama paket"
say "  (KSU_MANAGER_PACKAGE). Nilai default di KernelSU-Next adalah sertifikat"
say "  mereka sendiri:"
say "      KSU_NEXT_MANAGER_SIZE = 0x3e6"
say "      KSU_NEXT_MANAGER_HASH = 79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7"
say "  Synthetica memakai sertifikat LAIN:"
say "      fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140 (1381 byte / 0x565)"
say "  Jadi kernel pihak ketiga TIDAK akan mengenali APK ini sebagai manager,"
say "  kecuali kernel itu dibangun dengan hash kita."

# ------------------------------------------------------- 4. fitur KernelSU kita
head2 "4. Jejak fitur Synthetica di kernel"
for F in /sys/kernel/susfs /data/adb/ksu/feature /sys/fs/pstore; do
    [ -e "$F" ] && say "  ada            : $F"
done

# ------------------------------------------------------------- ringkasan verdict
head2 "RINGKASAN"
say "  OK=$YES  GAGAL=$NO  TIDAK_PASTI=$UNKNOWN"
say ""
if [ "$ROOT_WORKS" -eq 1 ]; then
    say "  VERDICT: Universal Root Bridge BISA HIDUP di kernel ini."
    say "           Control / Boost / Telemetri / .ko Loader / Log Viewer"
    say "           akan berfungsi lewat su."
    say "           Modul-KSU, Superuser-KSU, install boot, SuSFS: TIDAK."
elif [ "$DRIVER" -eq 1 ]; then
    say "  VERDICT: Driver KSU ADA, tetapi shell ini belum mendapat root."
    say "           Setujui permintaan root untuk Synthetica di manager kernel"
    say "           (BakaSU Manager / manager KSU bawaan), lalu jalankan ulang."
else
    say "  VERDICT: Tidak ada root yang bisa dipakai. Root TIDAK mungkin dari"
    say "           userspace — harus dari kernel (KSU-family) atau Magisk/APatch."
fi
say ""
say "Catatan: skrip ini hanya membaca. Tidak ada perubahan sistem."
exit 0
