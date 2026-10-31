#!/sbin/sh
# SYNTHETICA-PULSE log collector (recovery-flashable, read-only).
#
# It does NOT modify any partition. The only writes are inside
# <storage>/synthetica-logs/<timestamp>/ so a bootloop can be diagnosed afterwards.
# Run it while still in recovery, BEFORE rebooting, because /proc/last_kmsg and
# /sys/fs/pstore are only meaningful until the next boot.

# OrangeFox executes update-binary with plain sh and does not define ui_print/abort the way
# AnyKernel3 does. Without this the 2026-10-28 run died on line 51 with "ui_print: command not
# found" and only survived because the shell kept going. Define fallbacks first, always.
command -v ui_print >/dev/null 2>&1 || ui_print() { echo "$@"; }
command -v abort >/dev/null 2>&1 || abort() { echo "$@"; exit 1; }

OUT_ROOT=""
for d in /sdcard /data/media/0 /storage/emulated/0 /tmp; do
  if [ -d "$d" ] && ( : > "$d/.sp_write_test" ) 2>/dev/null; then
    rm -f "$d/.sp_write_test" 2>/dev/null
    OUT_ROOT="$d/synthetica-logs"
    break
  fi
done

# /sdcard often lives under /data; try to bring it up read-write for the log folder only.
if [ -z "$OUT_ROOT" ]; then
  for m in "/dev/block/by-name/userdata /data" "/dev/block/bootdevice/by-name/userdata /data"; do
    set -- $m
    [ -b "$1" ] || continue
    mount -t f2fs -o rw "$1" "$2" 2>/dev/null || mount -t ext4 -o rw "$1" "$2" 2>/dev/null
    for d in /sdcard /data/media/0; do
      if [ -d "$d" ] && ( : > "$d/.sp_write_test" ) 2>/dev/null; then
        rm -f "$d/.sp_write_test" 2>/dev/null
        OUT_ROOT="$d/synthetica-logs"
        break 2
      fi
    done
  done
fi

if [ -z "$OUT_ROOT" ]; then
  ui_print "  ! Tidak ada storage yang bisa ditulis.";
  ui_print "  ! Mount/decrypt data dulu, atau reboot ke system lalu jalankan collector lagi.";
  abort "  Tidak ada tempat menyimpan log.";
fi

STAMP=$(date +%Y%m%d-%H%M%S 2>/dev/null)
[ -n "$STAMP" ] || STAMP=manual
OUT="$OUT_ROOT/$STAMP"
mkdir -p "$OUT" || abort "  Gagal membuat $OUT"

BB=""
for c in /tmp/anykernel/tools/busybox tools/busybox /sbin/busybox /system/bin/busybox; do
  [ -x "$c" ] && BB="$c" && break
done
run_busybox() { [ -n "$BB" ] && "$BB" "$@" 2>/dev/null; }

ui_print "  Mengumpulkan log -> $OUT"

cap() { # cap <relative-name> <command...>
  name="$1"; shift
  "$@" > "$OUT/$name" 2>&1 || true
}

cap 00-uname.txt          sh -c 'uname -a; echo; cat /proc/version'
cap 01-cmdline.txt        cat /proc/cmdline
cap 02-props.txt          sh -c 'getprop 2>/dev/null || echo "getprop tidak tersedia di recovery"'
cap 03-mounts.txt         cat /proc/mounts
cap 04-partitions.txt     sh -c 'ls -l /dev/block/by-name 2>/dev/null; ls -l /dev/block/bootdevice/by-name 2>/dev/null'
cap 05-modules.txt        cat /proc/modules
cap 06-dmesg.txt          dmesg
cap 07-last-kmsg.txt      cat /proc/last_kmsg
cap 08-recovery-log.txt   cat /tmp/recovery.log

# pstore survives a crash: copy everything under /sys/fs/pstore
if [ -d /sys/fs/pstore ]; then
  mkdir -p "$OUT/09-pstore"
  for f in /sys/fs/pstore/*; do
    [ -f "$f" ] || continue
    cp "$f" "$OUT/09-pstore/$(basename "$f")" 2>/dev/null
  done
  ls -l /sys/fs/pstore > "$OUT/09-pstore-listing.txt" 2>&1 || true
fi

# recovery may keep the previous logs under /cache/recovery
mkdir -p "$OUT/10-cache-recovery"
for f in /cache/recovery/last_log /cache/recovery/last_kmsg /cache/recovery/last_install; do
  [ -f "$f" ] && cp "$f" "$OUT/10-cache-recovery/$(basename "$f")" 2>/dev/null
done

# read-only fingerprints of the partitions that matter for restoring
: > "$OUT/11-partition-hashes.txt"
for p in boot dtbo vbmeta; do
  dev="/dev/block/bootdevice/by-name/$p"
  [ -b "$dev" ] || dev="/dev/block/by-name/$p"
  [ -b "$dev" ] || continue
  if [ -n "$BB" ]; then
    # stat without -L reports the length of the /dev/block/bootdevice/by-name symlink
    # target string (16 bytes) - that is what the 2026-10-28 log showed as "bytes=16".
    # Hash the device content and count the bytes actually read instead.
    sum=$("$BB" sha256sum "$dev" 2>/dev/null | "$BB" cut -d' ' -f1)
    read_bytes=$("$BB" wc -c < "$dev" 2>/dev/null)
    echo "$p $dev hashed_bytes=${read_bytes:-unknown} sha256=$sum" >> "$OUT/11-partition-hashes.txt"
  else
    echo "$p $dev (busybox tidak tersedia, hash dilewati)" >> "$OUT/11-partition-hashes.txt"
  fi
done

# existing backups made by the installer
mkdir -p "$OUT/12-backup-listing"
BK="$(dirname "$OUT_ROOT")/synthetica-pulse-backups"
ls -l "$BK" > "$OUT/12-backup-listing/listing.txt" 2>&1 || true
# BACKUP-INFO.txt holds the sha256 of the partition BEFORE any write. Without it nobody can tell
# whether the kernel that is installed now is the tested one or the restored backup.
for f in "$BK"/BACKUP-INFO.txt "$BK"/*/BACKUP-INFO.txt; do
  [ -f "$f" ] && cp "$f" "$OUT/12-backup-listing/$(basename "$(dirname "$f")")-BACKUP-INFO.txt" 2>/dev/null
done

# Which kernel is actually inside the boot partition right now?
# The kernel payload inside a boot image is gzip-compressed, so the version string is NOT visible in
# a plain read - the 2026-10-29 log shows 13-installed-kernel.txt empty for exactly that reason.
# So: parse the boot image header, cut the kernel segment, gunzip it, then look for "openela-<n>".
BOOT_IMG="${TMPDIR:-/tmp}/sp-boot.img"
: > "$OUT/13-installed-kernel.txt"
for p in boot; do
  dev="/dev/block/bootdevice/by-name/$p"
  [ -b "$dev" ] || dev="/dev/block/by-name/$p"
  [ -b "$dev" ] || continue
  echo "== $p ($dev) ==" >> "$OUT/13-installed-kernel.txt"

  # header page: magic "ANDROID!", kernel_size @8, page_size @36, header_version @40
  dd if="$dev" of="$BOOT_IMG" bs=4096 count=1 2>/dev/null
  magic=$(od -An -c -j 0 -N 8 "$BOOT_IMG" 2>/dev/null | tr -d ' \n')
  ksize=$(od -An -tu4 -j 8 -N 4 "$BOOT_IMG" 2>/dev/null | tr -d ' ')
  psize=$(od -An -tu4 -j 36 -N 4 "$BOOT_IMG" 2>/dev/null | tr -d ' ')
  hver=$(od -An -tu4 -j 40 -N 4 "$BOOT_IMG" 2>/dev/null | tr -d ' ')
  echo "magic=$magic kernel_size=${ksize:-?} page_size=${psize:-?} header_version=${hver:-?}" \
    >> "$OUT/13-installed-kernel.txt"
  case "$psize" in ''|0|*[!0-9]*) psize=2048 ;; esac
  case "$ksize" in ''|0|*[!0-9]*) ksize=0 ;; esac

  if [ "$ksize" -gt 0 ]; then
    blocks=$(( (ksize + psize - 1) / psize ))
    dd if="$dev" bs="$psize" skip=1 count="$blocks" 2>/dev/null > "$BOOT_IMG.payload"
    # gzip payload (our zip ships Image.gz): try to decompress, then grep; if it is not gzip,
    # grep the raw bytes too so an uncompressed Image still gives an answer.
    if command -v gzip >/dev/null 2>&1; then
      gzip -dc "$BOOT_IMG.payload" 2>/dev/null | tr -c "[:print:]" "\n" \
        | grep -a -E "openela-[0-9]" | sort -u | head -10 >> "$OUT/13-installed-kernel.txt"
    elif [ -n "$BB" ]; then
      "$BB" gzip -dc "$BOOT_IMG.payload" 2>/dev/null | "$BB" tr -c "[:print:]" "\n" \
        | "$BB" grep -a -E "openela-[0-9]" | "$BB" sort -u | "$BB" head -10 \
        >> "$OUT/13-installed-kernel.txt"
    fi
    tr -c "[:print:]" "\n" < "$BOOT_IMG.payload" \
      | grep -a -E "openela-[0-9]" | sort -u | head -10 >> "$OUT/13-installed-kernel.txt"
    rm -f "$BOOT_IMG.payload"
  fi
  rm -f "$BOOT_IMG"
done
echo "(kosong = tidak ada string openela-* yang bisa dibaca dari payload boot)" \
  >> "$OUT/13-installed-kernel.txt"

# Did the write actually land? Compare the live boot hash with every recorded pre-flash hash.
{
  bdev="/dev/block/bootdevice/by-name/boot"
  [ -b "$bdev" ] || bdev="/dev/block/by-name/boot"
  live=$( ( [ -n "$BB" ] && "$BB" sha256sum "$bdev" ) 2>/dev/null | awk '{print $1}' )
  echo "live_boot_sha256=$live"
  for f in "$BK"/BACKUP-INFO.txt "$BK"/*/BACKUP-INFO.txt; do
    [ -f "$f" ] || continue
    echo "--- $f"
    grep -E "backup_file|release|created|sha256|live_sha256|bytes" "$f" 2>/dev/null
  done
  echo
  echo "Baca: live_boot_sha256 sama dengan sha256 backup terbaru = kernel TIDAK berubah"
  echo "      (flash tidak berefek / sudah di-rollback). Beda = partisi boot memang ditulis."
} > "$OUT/15-boot-compare.txt" 2>&1 || true

# Is pstore even usable on this device? On 2026-10-28 and again on 2026-10-29 the ramoops region
# came up with a broken header, which is why every crash dump was lost. Record the state.
{
  echo "== /sys/fs/pstore =="
  ls -l /sys/fs/pstore 2>&1
  echo
  echo "== dmesg: ramoops / persistent_ram / pstore =="
  dmesg 2>/dev/null | grep -iE "ramoops|persistent_ram|pstore" | tail -20
  echo
  echo "Baris 'uncorrectable error in header' = RAM reserved untuk crash dump sudah rusak;"
  echo "tidak ada dump panic yang bisa disimpan sampai region itu bersih."
} > "$OUT/16-pstore-health.txt" 2>&1 || true

# What did the user actually install? The zip folder names say it.
{
  echo "== SYNTHETICA-PULSE folders/files on storage =="
  ls -ld /sdcard/Download/SYNTHETICA-PULSE-* 2>/dev/null
  ls -l /sdcard/Download/SYNTHETICA-PULSE-*/*.zip 2>/dev/null
} > "$OUT/14-installed-zip.txt" 2>&1 || true

cat > "$OUT/README.txt" <<'TXT'
SYNTHETICA-PULSE log collector output
=====================================
Isi: uname/version, cmdline, properties, mounts, partitions, modules, dmesg,
/proc/last_kmsg, /tmp/recovery.log, pstore, /cache/recovery/*, hash boot/dtbo/vbmeta,
dan daftar backup boot yang ada.

Yang paling berguna untuk diagnosis bootloop:
- 09-pstore/ dan 07-last-kmsg.txt  -> jejak crash dari boot yang gagal
- 13-installed-kernel.txt           -> kernel APA yang benar-benar ada di partisi boot sekarang
- 15-boot-compare.txt               -> apakah flash benar-benar mengubah isi boot
- 16-pstore-health.txt              -> apakah RAM crash-dump masih bisa dipakai
- 14-installed-zip.txt              -> zip mana yang terakhir dipasang
- 12-backup-listing/                -> BACKUP-INFO.txt: sha256 boot sebelum ditulis
- 06-dmesg.txt                      -> log kernel sesi recovery ini
- 08-recovery-log.txt               -> apa yang dilakukan recovery
- 11-partition-hashes.txt           -> bukti isi boot/dtbo saat ini

Tidak ada data pribadi yang dikumpulkan: tidak ada /data, tidak ada akun, tidak ada IMEI.
Kirim folder ini ke pengembang setelah memeriksa sendiri isinya.
TXT

if [ -n "$BB" ]; then
  ( cd "$OUT_ROOT" && "$BB" tar -czf "$OUT_ROOT/synthetica-logs-$STAMP.tar.gz" "$STAMP" 2>/dev/null )
  ui_print "  Arsip: $OUT_ROOT/synthetica-logs-$STAMP.tar.gz"
fi

ui_print "  Selesai. Folder: $OUT"
ui_print "  Tidak ada partisi yang diubah."
ui_print "  Jangan reboot dulu kalau ingin /proc/last_kmsg tetap terbaca."
exit 0
