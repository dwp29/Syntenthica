#!/sbin/sh
# Synthetica Boot Audit 1.0. Read-only boot-v2 diagnostics, not an installer.
# Only the DTB section is copied temporarily into a private /tmp directory.

OUTFD=${2-}
ZIPFILE=${3-}
case "$OUTFD" in ''|*[!0-9]*) echo 'Invalid recovery output descriptor' >&2; exit 1;; esac
[ -e "/proc/self/fd/$OUTFD" ] || { echo 'Recovery output descriptor unavailable' >&2; exit 1; }
ui() { printf 'ui_print %s\nui_print\n' "$1" >> "/proc/self/fd/$OUTFD"; }
stop() { ui "AUDIT STOPPED: $*"; ui 'Read only; no partition was written.'; exit 1; }

ui 'Synthetica Boot Audit 1.0 - READ ONLY'
ui 'No kernel installation or partition write.'
umask 077
WORK_BASE=/tmp
WORK="$WORK_BASE/synthetica-boot-audit-$$"
mkdir "$WORK" 2>/dev/null || stop 'Cannot create a private temporary directory.'
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

# Prefer the same BusyBox distributed with Synthetica 3.0. If the recovery has
# no unzip utility, its own BusyBox may still be able to perform the audit.
BB="$WORK/busybox"
if command -v unzip >/dev/null 2>&1 && [ -f "$ZIPFILE" ]; then
  unzip -p "$ZIPFILE" tools/busybox > "$BB" 2>/dev/null || stop 'Cannot extract the bundled BusyBox.'
  chmod 700 "$BB" || stop 'Cannot prepare the bundled BusyBox.'
elif command -v busybox >/dev/null 2>&1; then
  BB=$(command -v busybox)
else
  stop 'Recovery needs unzip or BusyBox to run this audit.'
fi
"$BB" true >/dev/null 2>&1 || stop 'BusyBox cannot execute in this recovery.'

prop() { getprop "$1" 2>/dev/null || true; }
showprop() {
  value=$(prop "$1")
  case "$value" in
    '') value='(empty)' ;;
    *[!A-Za-z0-9._-]*) value='(unexpected characters)' ;;
  esac
  ui "$1: $value"
}
for key in ro.product.device ro.build.product ro.product.vendor.device ro.vendor.product.device \
           ro.boot.slot_suffix ro.boot.slot ro.build.ab_update ro.boot.flash.locked \
           ro.boot.verifiedbootstate ro.boot.vbmeta.device_state; do
  showprop "$key"
done
ui 'Recovery properties can differ from the installed ROM.'

# Do not guess an A/B slot even though the diagnostic only reads.
for key in ro.boot.slot_suffix ro.boot.slot; do
  value=$(prop "$key")
  case "$value" in ''|normal) :;; *) stop 'A/B or unknown slot property; no boot selected.';; esac
done
value=$(prop ro.build.ab_update)
case "$value" in ''|false|0) :;; *) stop 'A/B or unknown update property; no boot selected.';; esac
CMDLINE=/proc/cmdline
for arg in $(cat "$CMDLINE" 2>/dev/null); do
  case "$arg" in
    androidboot.slot=|androidboot.slot=normal|androidboot.slot_suffix=|androidboot.slot_suffix=normal) :;;
    androidboot.slot=*|androidboot.slot_suffix=*) stop 'A/B slot in kernel command line; no boot selected.';;
  esac
done
PRIMARY=/dev/block/bootdevice/by-name
SECONDARY=/dev/block/by-name
for dir in "$PRIMARY" "$SECONDARY"; do
  for part in "$dir/boot_a" "$dir/boot_b"; do
    [ ! -e "$part" ] && [ ! -L "$part" ] || stop 'Slotted boot names found; no boot selected.'
  done
done
BLOCK="$PRIMARY/boot"
if [ ! -b "$BLOCK" ]; then
  BLOCK="$SECONDARY/boot"
  [ -b "$BLOCK" ] || stop 'Unslotted boot block device not found.'
fi
ui "Reading boot: $BLOCK"
partsize=$("$BB" blockdev --getsize64 "$BLOCK" 2>/dev/null) || stop 'Cannot determine boot partition size.'
case "$partsize" in ''|*[!0-9]*) stop 'Invalid boot partition size.';; esac
[ "$partsize" -ge 16777216 ] && [ "$partsize" -le 268435456 ] || stop 'Boot size outside audit limits.'
ui "Boot partition bytes: $partsize"
magic=$("$BB" dd if="$BLOCK" bs=8 count=1 2>/dev/null) || stop 'Cannot read boot header.'
[ "$magic" = 'ANDROID!' ] || stop 'Not an Android boot image.'

# Parse little-endian 32-bit fields bytewise. The bound prevents arithmetic
# overflow on 32-bit recovery shells and limits all reads to this partition.
u32() {
  set -- $("$BB" od -An -t u1 -j "$1" -N 4 "$BLOCK" 2>/dev/null)
  [ "$#" -eq 4 ] || return 1
  [ "$4" -le 16 ] || return 1
  n=$(( $1 + $2 * 256 + $3 * 65536 + $4 * 16777216 ))
  [ "$n" -le 268435456 ] || return 1
  printf '%s\n' "$n"
}
version=$(u32 40) || stop 'Cannot read header version.'
page=$(u32 36) || stop 'Cannot read page size.'
headersize=$(u32 1644) || stop 'Cannot read header size.'
[ "$version" = 2 ] && [ "$page" = 4096 ] && [ "$headersize" = 1660 ] || stop 'Only boot-v2, page 4096, header 1660 is audited.'
kernel=$(u32 8) || stop 'Invalid kernel size.'
ramdisk=$(u32 16) || stop 'Invalid ramdisk size.'
second=$(u32 24) || stop 'Invalid second size.'
recovery=$(u32 1632) || stop 'Invalid recovery DTBO size.'
recoveryoff=$(u32 1636) || stop 'Invalid recovery DTBO offset.'
recoveryoffhi=$(u32 1640) || stop 'Invalid recovery DTBO high offset.'
dtb=$(u32 1648) || stop 'Invalid boot DTB size.'
[ "$kernel" -gt 0 ] && [ "$ramdisk" -gt 0 ] || stop 'Kernel or ramdisk section is empty.'
[ "$dtb" -gt 0 ] && [ "$dtb" -le 16777216 ] || stop 'DTB missing or exceeds audit limit.'
[ "$recoveryoffhi" = 0 ] || stop 'Recovery DTBO offset exceeds audit limit.'
align() { printf '%s\n' "$(( ($1 + page - 1) / page * page ))"; }
pos=$((page + $(align "$kernel") + $(align "$ramdisk") + $(align "$second")))
[ "$pos" -le "$partsize" ] || stop 'Boot sections exceed partition size.'
if [ "$recovery" -gt 0 ]; then
  [ "$recoveryoff" -eq "$pos" ] || stop 'Unexpected recovery DTBO offset.'
else
  [ "$recoveryoff" -eq 0 ] || stop 'Unexpected empty recovery DTBO offset.'
fi
pos=$((pos + $(align "$recovery")))
[ "$pos" -le "$partsize" ] && [ "$(align "$dtb")" -le "$((partsize - pos))" ] || stop 'DTB section exceeds partition size.'
ui "Boot header: v2, page $page, header $headersize"
ui "Kernel bytes: $kernel; ramdisk bytes: $ramdisk"
ui "DTB bytes: $dtb; offset: $pos"

# A bounded temporary DTB file makes a short read detectable; it is never
# copied to shared storage or sent anywhere. Do not hash an incomplete read.
"$BB" dd if="$BLOCK" of="$WORK/dtb.bin" bs=1048576 skip="$pos" count="$dtb" iflag=skip_bytes,count_bytes 2>/dev/null || stop 'Could not read the DTB section.'
actual=$("$BB" wc -c < "$WORK/dtb.bin" | "$BB" tr -d ' \n')
[ "$actual" = "$dtb" ] || stop 'Short DTB read; no hash reported.'
sum=$("$BB" sha256sum "$WORK/dtb.bin" 2>/dev/null) || stop 'Cannot hash the DTB section.'
set -- $sum
hash=${1-}
[ "${#hash}" -eq 64 ] || stop 'Invalid DTB hash output.'
case "$hash" in *[!0-9a-f]*) stop 'Invalid DTB hash output.';; esac
rm -f "$WORK/dtb.bin"
first=$(printf '%s' "$hash" | "$BB" cut -c 1-32)
last=$(printf '%s' "$hash" | "$BB" cut -c 33-64)
ui "DTB SHA256 1/2: $first"
ui "DTB SHA256 2/2: $last"
if [ "$hash" = 6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239 ]; then
  ui '3.0 reference DTB: MATCH'
else
  ui '3.0 reference DTB: DIFFERENT (not a compatibility verdict)'
fi
ui 'Hash is not proof of AVB trust, module ABI or boot safety.'
ui 'Audit complete. No partition was written.'
exit 0
