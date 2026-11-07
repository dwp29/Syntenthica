#!/sbin/sh
# Synthetica Log Collector 1.0 -- recovery diagnostics, not a kernel installer.
# Only writes the new report directory/archive on an already-mounted filesystem
# or in /tmp. It does not mount, flash, reboot, change bootloader/AVB or upload.
# Raw diagnostic logs can contain private information; inspect before sharing.

VERSION=1.0
LIMIT=1048576
PSTORE_LIMIT=524288
OUTFD=
if [ "$#" -eq 3 ]; then
  case "$1:$2" in
    *[!0-9:]*|:*|*:) ;;
    *) OUTFD=$2 ;;
  esac
elif [ "$#" -ne 0 ]; then
  echo 'Use: sh collector.sh (or install the diagnostic ZIP in custom recovery).'
  exit 2
fi

# Test fixture mode requires an explicit marker and is never enabled by the ZIP.
# All filesystem inputs and output candidates are redirected below that root.
ROOT=
TEST_MODE=0
if [ -n "${SYNT_COLLECTOR_TEST_ROOT:-}" ]; then
  case "$SYNT_COLLECTOR_TEST_ROOT" in
    /*) ROOT=${SYNT_COLLECTOR_TEST_ROOT%/} ;;
    *) echo 'Invalid test root'; exit 2 ;;
  esac
  [ -n "$ROOT" ] && [ -d "$ROOT" ] && [ -f "$ROOT/.synthetica-collector-fixture" ] || {
    echo 'Invalid test fixture'; exit 2;
  }
  TEST_MODE=1
  PATH="$ROOT/bin:/sbin:/system/bin:/system/xbin:/vendor/bin:/bin:/usr/bin"
else
  PATH=/sbin:/system/bin:/system/xbin:/vendor/bin:/bin:/usr/bin
fi
export PATH
umask 077

app() {
  app_name=$1; shift
  if command -v "$app_name" >/dev/null 2>&1; then
    "$app_name" "$@"
  elif command -v busybox >/dev/null 2>&1; then
    busybox "$app_name" "$@"
  elif command -v toybox >/dev/null 2>&1; then
    toybox "$app_name" "$@"
  else
    return 127
  fi
}

ui() {
  if [ -n "$OUTFD" ] && [ -e "/proc/self/fd/$OUTFD" ]; then
    printf 'ui_print %s\nui_print\n' "$1" > "/proc/self/fd/$OUTFD" 2>/dev/null && return
  fi
  printf '%s\n' "$1"
}

# Select only a filesystem already mounted somewhere other than recovery's
# in-memory root; no attempt is made to mount/decrypt a partition. readlink -f
# resolves the common /sdcard -> /data/media/0 symlink where available.
persistent_mount() (
  pm_path=$(app readlink -f "$1" 2>/dev/null) || pm_path=$1
  [ -n "$pm_path" ] || pm_path=$1
  [ -r "$ROOT/proc/mounts" ] || exit 1
  pm_length=0
  pm_best=
  while IFS=' ' read -r pm_device pm_mount pm_type pm_rest; do
    [ "$pm_mount" != / ] || continue
    case "$pm_path" in "$pm_mount"|"$pm_mount"/*) ;; *) continue ;; esac
    if [ "${#pm_mount}" -gt "$pm_length" ]; then
      pm_length=${#pm_mount}
      pm_best=$pm_type
    fi
  done < "$ROOT/proc/mounts"
  case "$pm_best" in ''|rootfs|ramfs|tmpfs|devtmpfs|overlay) exit 1 ;; *) exit 0 ;; esac
)

stamp=$(app date -u +%Y%m%d-%H%M%S 2>/dev/null)
case "$stamp" in ''|*[!0-9-]*) stamp=no-clock ;; esac
session="$stamp-$$"
OUT=
OUTROOT=
VOLATILE=0
select_output() {
  select_dir=$1
  [ -d "$select_dir" ] || return 1
  select_root="$select_dir/Synthetica-logs"
  [ ! -L "$select_root" ] || return 1
  if [ ! -d "$select_root" ]; then
    app mkdir "$select_root" 2>/dev/null || return 1
  fi
  [ ! -L "$select_root" ] && [ -d "$select_root" ] || return 1
  select_i=0
  while [ "$select_i" -lt 10 ]; do
    select_name="$session-$select_i"
    select_out="$select_root/$select_name"
    if app mkdir "$select_out" 2>/dev/null; then
      if ( printf 'ok\n' > "$select_out/.write-test" ) 2>/dev/null; then
        app rm -f "$select_out/.write-test" 2>/dev/null || :
        app chmod 700 "$select_out" 2>/dev/null || :
        OUT=$select_out
        OUTROOT=$select_root
        SESSION=$select_name
        return 0
      fi
      app rmdir "$select_out" 2>/dev/null || :
    fi
    select_i=$((select_i + 1))
  done
  return 1
}

for target in "$ROOT/sdcard" "$ROOT/data/media/0" "$ROOT/storage/emulated/0" \
              "$ROOT/external_sd" "$ROOT/sdcard1" "$ROOT/storage/sdcard1" \
              "$ROOT/storage/external_SD" "$ROOT/usb-otg" "$ROOT/mnt/usb_otg" \
              "$ROOT/mnt/media_rw/"* "$ROOT/storage/"*; do
  [ -d "$target" ] || continue
  persistent_mount "$target" || continue
  select_output "$target" && break
done
if [ -z "$OUT" ]; then
  VOLATILE=1
  select_output "$ROOT/tmp" || {
    ui 'ERROR: No writable log destination. Use recovery Copy Log or adb pull /tmp/recovery.log.'
    exit 1
  }
fi

STATUS="$OUT/STATUS.tsv"
if ! printf 'source\tstatus\tdetail\n' > "$STATUS"; then
  ui 'ERROR: Cannot write report status; no diagnostics were collected.'
  exit 1
fi
status() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$STATUS"; }

# Existing raw logs are intentionally NOT redacted: redaction cannot guarantee
# privacy and may remove the failure reason. Limit each copy, report absence.
copy_log() (
  cl_source=$1; cl_name=$2; cl_mode=$3; cl_limit=$4
  if [ -L "$cl_source" ]; then status "$cl_name" SKIPPED_SYMLINK "$cl_source"; exit 0; fi
  if [ ! -e "$cl_source" ]; then status "$cl_name" MISSING "$cl_source"; exit 0; fi
  if [ ! -f "$cl_source" ]; then status "$cl_name" NOT_REGULAR "$cl_source"; exit 0; fi
  if [ ! -r "$cl_source" ]; then status "$cl_name" UNREADABLE "$cl_source"; exit 0; fi
  cl_output="$OUT/$cl_name"
  if [ "$cl_mode" = tail ]; then
    app tail -c "$cl_limit" "$cl_source" > "$cl_output" 2>/dev/null
  else
    app head -c "$cl_limit" "$cl_source" > "$cl_output" 2>/dev/null
  fi
  cl_rc=$?
  if [ "$cl_rc" -ne 0 ]; then
    status "$cl_name" READ_ERROR "exit=$cl_rc; $cl_source"; exit 0
  fi
  cl_bytes=$(app wc -c < "$cl_output" 2>/dev/null)
  case "$cl_bytes" in ''|*[!0-9\ ]*) cl_bytes=unknown ;; esac
  cl_bytes=$(printf '%s' "$cl_bytes" | app tr -d ' ' 2>/dev/null)
  if [ ! -s "$cl_output" ]; then
    status "$cl_name" EMPTY "$cl_source"
  elif [ "$cl_bytes" = "$cl_limit" ]; then
    status "$cl_name" LIMIT_REACHED "bytes=$cl_bytes; may be truncated; $cl_source"
  else
    status "$cl_name" OK "bytes=$cl_bytes; $cl_source"
  fi
)

# Capture this before announcing the collector, since recoveries may append to
# or replace the installation log when a second ZIP starts.
copy_log "$ROOT/tmp/recovery.log" 01-recovery-current.log tail "$LIMIT"
ui 'Synthetica Log Collector 1.0 (diagnostics only)'
ui 'No kernel is installed. Raw logs may contain private data.'
ui "Saving report: $OUT"

copy_log "$ROOT/tmp/last_install" 02-last-install-tmp.txt tail "$LIMIT"
copy_log "$ROOT/tmp/anykernel/prepare.log" 03-anykernel-prepare.log tail "$LIMIT"
copy_log "$ROOT/cache/recovery/last_log" 04-recovery-last.log tail "$LIMIT"
copy_log "$ROOT/cache/recovery/last_log.1" 05-recovery-previous.log tail "$LIMIT"
copy_log "$ROOT/cache/recovery/last_install" 06-last-install-cache.txt tail "$LIMIT"
copy_log "$ROOT/cache/recovery/last_kmsg" 07-last-kmsg-cache.log tail "$LIMIT"
copy_log "$ROOT/metadata/recovery/last_log" 08-recovery-metadata.log tail "$LIMIT"
copy_log "$ROOT/proc/last_kmsg" 09-proc-last-kmsg.log head "$LIMIT"

pstore_count=0
if [ -d "$ROOT/sys/fs/pstore" ]; then
  for pstore_file in "$ROOT/sys/fs/pstore/"*; do
    [ -e "$pstore_file" ] || [ -L "$pstore_file" ] || continue
    pstore_name=${pstore_file##*/}
    case "$pstore_name" in ''|*[!a-zA-Z0-9._-]*) status pstore SKIPPED_NAME 'invalid filename'; continue ;; esac
    if [ "$pstore_count" -ge 16 ]; then status pstore LIMIT_REACHED 'more than 16 entries'; break; fi
    pstore_count=$((pstore_count + 1))
    copy_log "$pstore_file" "pstore-$pstore_name.log" head "$PSTORE_LIMIT"
  done
fi
[ "$pstore_count" -gt 0 ] || status pstore UNAVAILABLE_OR_EMPTY 'not mounted, unsupported, unreadable or no retained records'

# Known legacy installer logs only; not an inventory of the user's storage.
install_count=0
for install_dir in "$ROOT/sdcard/Synthetica" "$ROOT/data/media/0/Synthetica" \
                   "$ROOT/external_sd/Synthetica" "$ROOT/sdcard1/Synthetica"; do
  [ -d "$install_dir" ] || continue
  set --
  for install_file in "$install_dir"/install-log-*.txt; do
    [ -f "$install_file" ] || [ -L "$install_file" ] || continue
    set -- "$@" "$install_file"
    [ "$#" -le 5 ] || shift
  done
  for install_file do
    [ "$install_count" -lt 5 ] || break
    install_count=$((install_count + 1))
    copy_log "$install_file" "installer-log-$install_count.txt" tail "$PSTORE_LIMIT"
  done
done
[ "$install_count" -gt 0 ] || status installer-log MISSING 'no known legacy install logs found'

# Collect bounded command output only when an actual timeout implementation is
# available. This avoids waiting indefinitely for a missing recovery logd.
capture_command() (
  cc_name=$1; shift
  if ! app timeout 1 sh -c 'exit 0' >/dev/null 2>&1; then
    status "$cc_name" SKIPPED_NO_TIMEOUT 'command not run'; exit 0
  fi
  cc_executable=$1
  if command -v "$cc_executable" >/dev/null 2>&1; then
    :
  elif [ "$cc_executable" = dmesg ] && command -v busybox >/dev/null 2>&1; then
    shift; set -- busybox dmesg "$@"
  elif [ "$cc_executable" = dmesg ] && command -v toybox >/dev/null 2>&1; then
    shift; set -- toybox dmesg "$@"
  else
    status "$cc_name" MISSING_COMMAND "$cc_executable"; exit 0
  fi
  cc_rcfile="$OUT/.command-rc-$cc_name"
  (
    app timeout 8 "$@" 2>&1
    printf '%s\n' "$?" > "$cc_rcfile"
  ) | app tail -c "$LIMIT" > "$OUT/$cc_name"
  cc_tail_rc=$?
  cc_rc=$(app cat "$cc_rcfile" 2>/dev/null)
  app rm -f "$cc_rcfile" 2>/dev/null || :
  if [ "$cc_tail_rc" -ne 0 ] || [ -z "$cc_rc" ]; then
    status "$cc_name" CAPTURE_ERROR "tail=$cc_tail_rc; command=$cc_rc"
  elif [ "$cc_rc" = 124 ] || [ "$cc_rc" = 143 ]; then
    status "$cc_name" TIMED_OUT "exit=$cc_rc"
  elif [ "$cc_rc" != 0 ]; then
    status "$cc_name" COMMAND_FAILED "exit=$cc_rc; see file"
  elif [ ! -s "$OUT/$cc_name" ]; then
    status "$cc_name" EMPTY 'command succeeded but returned no data'
  else
    cc_bytes=$(app wc -c < "$OUT/$cc_name" 2>/dev/null | app tr -d ' ')
    if [ "$cc_bytes" = "$LIMIT" ]; then
      status "$cc_name" LIMIT_REACHED "bytes=$cc_bytes; may be truncated"
    else
      status "$cc_name" OK "bytes=$cc_bytes"
    fi
  fi
)
capture_command 10-dmesg-recovery.log dmesg
capture_command 11-logcat-recovery.log logcat -d -v threadtime -b all

# Only fixed, non-unique property keys: never enumerate getprop or copy raw
# cmdline. Recovery properties may describe the recovery, not the installed ROM.
{
  printf 'Collector version: %s\n' "$VERSION"
  printf 'UTC timestamp: %s\n' "$stamp"
  printf 'Fixture test mode: %s\n' "$TEST_MODE"
  printf 'Kernel in CURRENT recovery session: '
  app uname -r 2>/dev/null || printf 'unavailable\n'
  printf '\nThese properties are from the current recovery and may NOT describe the installed ROM.\n'
  if command -v getprop >/dev/null 2>&1; then
    property_count=0
    for property in ro.product.device ro.product.vendor.device ro.product.system.device \
      ro.product.brand ro.product.manufacturer ro.product.model ro.hardware \
      ro.build.display.id ro.build.fingerprint ro.build.version.release ro.build.version.sdk \
      ro.build.version.security_patch ro.build.ab_update ro.boot.slot ro.boot.slot_suffix \
      ro.boot.flash.locked ro.boot.verifiedbootstate ro.boot.vbmeta.device_state \
      ro.boot.veritymode ro.boot.hardware ro.boot.bootreason ro.bootmode ro.boot.mode \
      ro.recovery.version ro.twrp.version ro.orangefox.version ro.crypto.state; do
      value=$(getprop "$property" 2>/dev/null)
      if [ -n "$value" ]; then
        property_count=$((property_count + 1))
        printf '%s=%s\n' "$property" "$value"
      fi
    done
    if [ "$property_count" -eq 0 ]; then
      printf 'No selected properties were available.\n'
      status recovery-properties EMPTY 'getprop returned no selected values'
    else
      status recovery-properties OK "returned=$property_count"
    fi
  else
    printf 'getprop unavailable\n'
    status recovery-properties MISSING_COMMAND 'getprop'
  fi
  printf '\nSelected non-unique boot arguments from the current recovery only:\n'
  if [ -r "$ROOT/proc/cmdline" ]; then
    for argument in $(app cat "$ROOT/proc/cmdline" 2>/dev/null); do
      case "$argument" in androidboot.slot=*|androidboot.slot_suffix=*|androidboot.hardware=*|\
        androidboot.verifiedbootstate=*|androidboot.flash.locked=*|androidboot.bootreason=*)
        printf '%s\n' "$argument" ;;
      esac
    done
  else
    printf 'unavailable\n'
  fi
} > "$OUT/12-recovery-context.txt" 2>&1
status 12-recovery-context.txt OK 'allowlisted recovery properties and boot arguments'

# Mounted build.prop files can help identify the installed ROM. Do not mount
# anything to obtain them. Keep only fixed software/device metadata keys.
{
  printf 'Only already-mounted build.prop files are inspected; missing is normal.\n'
  printf 'These files can describe a different slot or stale mount.\n\n'
  rom_files=0
  for propfile in "$ROOT/system/build.prop" "$ROOT/system/system/build.prop" \
                  "$ROOT/system_root/system/build.prop" "$ROOT/vendor/build.prop" \
                  "$ROOT/product/build.prop" "$ROOT/system_ext/build.prop"; do
    if [ -L "$propfile" ]; then printf '%s: symlink skipped\n' "$propfile"; continue; fi
    prop_dir=${propfile%/*}
    if [ -f "$propfile" ] && [ -r "$propfile" ] && persistent_mount "$prop_dir"; then
      rom_files=$((rom_files + 1))
      printf '\n== %s ==\n' "$propfile"
      app grep -E '^(ro\.product\.(device|vendor\.device|system\.device|brand|manufacturer|model)|ro\.(build|system\.build|vendor\.build)\.(fingerprint|display\.id|version\.release|version\.sdk|version\.security_patch))=' "$propfile" 2>/dev/null | app head -c 65536 || :
    fi
  done
} > "$OUT/13-mounted-rom-properties.txt" 2>&1
if [ "$rom_files" -eq 0 ]; then
  status 13-mounted-rom-properties.txt UNAVAILABLE 'no readable build.prop in an already-mounted system'
else
  status 13-mounted-rom-properties.txt OK "files=$rom_files; allowlisted keys only"
fi

# Parse only numeric boot header fields. The raw header, cmdline, ramdisk, kernel
# and partition image are never written to the report. Vendor boot uses a
# different header and is only identified, not interpreted.
u32le() (
  words=$(app od -An -t u1 -j "$2" -N 4 "$1" 2>/dev/null) || exit 1
  set -- $words
  [ "$#" -eq 4 ] || exit 1
  for number do case "$number" in ''|*[!0-9]*) exit 1 ;; esac; done
  printf '%s' "$(( $1 + $2 * 256 + $3 * 65536 + $4 * 16777216 ))"
)
boot_header() (
  header_path=$1
  magic=$(app od -An -t x1 -N 8 "$header_path" 2>/dev/null | app tr -d ' \n')
  case "$magic" in
    414e44524f494421)
      hv=$(u32le "$header_path" 40) || hv=unknown
      kernel_size=$(u32le "$header_path" 8) || kernel_size=unknown
      ramdisk_size=$(u32le "$header_path" 12) || ramdisk_size=unknown
      printf '  magic=ANDROID! header_version=%s kernel_bytes=%s ramdisk_bytes=%s\n' "$hv" "$kernel_size" "$ramdisk_size"
      case "$hv" in
        0|1|2)
          page=$(u32le "$header_path" 36) || page=unknown
          printf '  legacy_page_bytes=%s\n' "$page"
          if [ "$hv" = 1 ] || [ "$hv" = 2 ]; then
            hs=$(u32le "$header_path" 1644) || hs=unknown
            printf '  legacy_header_bytes=%s\n' "$hs"
          fi ;;
        *) printf '  page/header-size layout not interpreted for this version.\n' ;;
      esac ;;
    564e4452424f4f54) printf '  magic=VNDRBOOT; vendor boot header not interpreted\n' ;;
    '') printf '  header unavailable or unreadable\n' ;;
    *) printf '  header is not a recognized Android boot image\n' ;;
  esac
)
{
  printf 'Selected by-name entries. Sizes/header fields are read only. No image is copied.\n'
  printf 'A slot or matching format alone does not establish kernel compatibility.\n'
  found=0
  for byname in "$ROOT/dev/block/bootdevice/by-name" "$ROOT/dev/block/by-name" \
                "$ROOT/dev/block/platform/"*/by-name "$ROOT/dev/block/platform/"*/*/by-name; do
    [ -d "$byname" ] || continue
    for partition in boot boot_a boot_b init_boot init_boot_a init_boot_b \
      vendor_boot vendor_boot_a vendor_boot_b recovery recovery_a recovery_b \
      dtbo dtbo_a dtbo_b vbmeta vbmeta_a vbmeta_b super; do
      block="$byname/$partition"
      [ -e "$block" ] || [ -L "$block" ] || continue
      found=$((found + 1))
      printf '\n%s\n' "$block"
      link=$(app readlink "$block" 2>/dev/null) && printf '  link=%s\n' "$link"
      if [ -b "$block" ] || { [ "$TEST_MODE" = 1 ] && [ -f "$block" ]; }; then
        if [ "$TEST_MODE" = 1 ] && [ -f "$block" ]; then
          partsize=$(app stat -c %s "$block" 2>/dev/null) || partsize=unknown
          readonly=fixture
        else
          partsize=$(app blockdev --getsize64 "$block" 2>/dev/null) || partsize=unknown
          readonly=$(app blockdev --getro "$block" 2>/dev/null) || readonly=unknown
        fi
        printf '  size_bytes=%s readonly=%s\n' "${partsize:-unknown}" "${readonly:-unknown}"
        case "$partition" in boot|boot_a|boot_b|init_boot|init_boot_a|init_boot_b|vendor_boot|vendor_boot_a|vendor_boot_b)
          boot_header "$block" ;;
        esac
      else
        printf '  entry is missing, inaccessible, or not a block device\n'
      fi
    done
  done
  [ "$found" -gt 0 ] || printf '\nNo selected by-name entries found or accessible.\n'
} > "$OUT/14-partition-layout.txt" 2>&1
if [ "$found" -eq 0 ]; then
  status 14-partition-layout.txt UNAVAILABLE 'no selected by-name entries found'
else
  status 14-partition-layout.txt OK "entries=$found; selected header fields only"
fi

{
  printf 'Candidate lines from captured recovery/installer logs, NOT a diagnosis.\n'
  printf 'A later collector operation can replace last_install. Inspect raw logs too.\n\n'
  for hint_file in "$OUT/01-recovery-current.log" "$OUT/03-anykernel-prepare.log" \
                   "$OUT/04-recovery-last.log" "$OUT/05-recovery-previous.log" \
                   "$OUT/installer-log-"*.txt; do
    [ -f "$hint_file" ] || continue
    printf '== %s ==\n' "${hint_file##*/}"
    app grep -iE 'error|failed|failure|abort|assert|denied|unsupported|device|slot|dtb|ramdisk|signature|verify|not found|cannot|unable|zip|boot' "$hint_file" 2>/dev/null | app tail -n 120
    printf '\n'
  done
} > "$OUT/15-error-lines.txt" 2>&1
status 15-error-lines.txt OK 'selected lines, may include private information'

app cat > "$OUT/README.txt" <<'TXT'
Synthetica Log Collector 1.0 -- diagnostik, BUKAN installer kernel

STATUS.tsv menunjukkan log yang berhasil, kosong, tidak ada, tidak bisa dibaca,
melebihi batas, atau timeout. Log recovery adalah sesi sekarang; pstore dan
last_kmsg hanya berisi boot sebelumnya jika perangkat/recovery menyediakannya.
Tidak ada log crash bukan bukti bahwa tidak terjadi crash. last_install dapat
tergantikan oleh operasi collector ini. 15-error-lines.txt bukan diagnosis.

PRIVASI: log mentah bisa memuat serial, path/nama file, nama aplikasi, alamat
jaringan, akun, atau informasi sensitif lain. Jangan bagikan secara publik.
Tinjau dan kirim hanya secara pribadi kepada pihak yang dipercaya. Collector
memilih beberapa properti, tetapi TIDAK menjamin redaksi log mentah.

Hanya direktori/laporan ini yang ditulis ke penyimpanan yang sudah tersedia;
tidak ada flash, mount, perubahan vbmeta, reboot, penghapusan data atau upload.
Laporan di /tmp bersifat sementara dan hilang saat reboot: salin via adb dahulu.
Nilai recovery mungkin berbeda dari ROM terpasang. Error 1 adalah kode umum,
bukan penyebab pasti, dan data ini tidak membuktikan kernel kompatibel.
TXT

if [ ! -s "$OUT/README.txt" ] || ! printf 'report\tCOMPLETE\tcollector finished\n' >> "$STATUS" 2>/dev/null; then
  ui 'ERROR: Report storage is full or unwritable; inspect the partial report before reboot.'
  exit 1
fi
ARCHIVE="$OUTROOT/$SESSION.tar.gz"
if [ -e "$ARCHIVE" ] || [ -L "$ARCHIVE" ]; then
  ui 'Archive name already exists; it was not overwritten. Send the report folder.'
elif app tar -czf "$ARCHIVE" -C "$OUTROOT" "$SESSION" >/dev/null 2>&1; then
  ui "Archive: $ARCHIVE"
else
  # Remove only a partial archive from this attempted creation, never a symlink.
  [ ! -L "$ARCHIVE" ] && app rm -f "$ARCHIVE" 2>/dev/null || :
  ui 'Archive unavailable; send the report folder instead.'
fi
ui "Report folder: $OUT"
if [ "$VOLATILE" = 1 ]; then
  ui 'TEMPORARY /tmp: adb pull the report BEFORE reboot; it will be lost.'
else
  ui 'Storage must remain mounted/decrypted to retrieve the report.'
fi
ui 'Review sensitive logs before sharing privately. No automatic reboot.'
exit 0
