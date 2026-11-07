#!/sbin/sh
# Synthetica 2.0 EXPERIMENTAL boot-v2 preparation. Never writes a partition.
# Called by anykernel.sh with fixed, package-specific SHA-256s.
set -eu

fail() { echo "PREPARE FAILED: $*" >&2; exit 1; }
[ "$#" -eq 6 ] || fail "incorrect arguments"
original=$1
kernel=$2
candidate=$3
work=$4
expected_kernel=$5
expected_dtb=$6
: "${BB:?BusyBox path required}"
: "${MAGISKBOOT:?MagiskBoot path required}"
[ -f "$original" ] && [ -f "$kernel" ] || fail "input file missing"
[ ! -e "$work" ] && [ ! -e "$candidate" ] || fail "work or output already exists"

size() { "$BB" stat -c %s "$1"; }
hash() { "$BB" sha256sum "$1" | "$BB" cut -d ' ' -f 1; }
slice() { "$BB" dd if="$1" of="$4" bs=1048576 skip="$2" count="$3" iflag=skip_bytes,count_bytes 2>/dev/null; }
word_le() { "$BB" od -An -t u4 -j "$2" -N 4 "$1" | "$BB" tr -d ' \n'; }
# Footer offsets are big-endian u64; reject values above 32 bits before arithmetic.
word_be64() {
  set -- $("$BB" od -An -t u1 -j "$2" -N 8 "$1")
  [ "$#" -eq 8 ] && [ "$1" -eq 0 ] && [ "$2" -eq 0 ] && [ "$3" -eq 0 ] && [ "$4" -eq 0 ] || fail "invalid AVB 64-bit field"
  echo $(( $5 * 16777216 + $6 * 65536 + $7 * 256 + $8 ))
}
footer_meta() {
  f=$1
  n=$(size "$f")
  [ "$n" -ge 64 ] || fail "image too small for AVB footer"
  tailoff=$((n - 64))
  slice "$f" "$tailoff" 4 "$work/avb-magic"
  [ "$(cat "$work/avb-magic")" = AVBf ] || fail "missing AVB footer"
  metaoff=$(word_be64 "$f" "$((tailoff + 20))")
  metalen=$(word_be64 "$f" "$((tailoff + 28))")
  [ "$metalen" -ge 256 ] && [ "$metalen" -le 4194304 ] && [ "$metaoff" -le "$tailoff" ] && [ "$metalen" -le "$((tailoff - metaoff))" ] || fail "invalid AVB metadata range"
  slice "$f" "$metaoff" "$metalen" "$2"
  [ "$(size "$2")" -eq "$metalen" ] || fail "short AVB metadata read"
  slice "$2" 0 4 "$work/avb-header-magic"
  [ "$(cat "$work/avb-header-magic")" = AVB0 ] || fail "invalid AVB metadata header"
}

orig_size=$(size "$original")
[ "$orig_size" -ge 16777216 ] && [ "$orig_size" -le 268435456 ] || fail "unexpected boot partition size"
[ "$(hash "$kernel")" = "$expected_kernel" ] || fail "kernel SHA-256 mismatch"
"$BB" gzip -t "$kernel" || fail "kernel gzip integrity check failed"
mkdir "$work" "$work/orig" "$work/new" "$work/ramdisk-check"
slice "$original" 0 8 "$work/boot-magic"
[ "$(cat "$work/boot-magic")" = 'ANDROID!' ] || fail "not an Android boot image"
[ "$(word_le "$original" 40)" = 2 ] || fail "only Android boot header v2 is supported"
[ "$(word_le "$original" 36)" = 4096 ] || fail "unexpected boot page size"
[ "$(word_le "$original" 1644)" = 1660 ] || fail "unexpected boot v2 header size"
footer_meta "$original" "$work/old-vbmeta"

(cd "$work/orig" && "$MAGISKBOOT" unpack -n "$original") || fail "cannot unpack original boot"
[ -f "$work/orig/kernel" ] && [ -f "$work/orig/ramdisk.cpio" ] && [ -f "$work/orig/dtb" ] || fail "required boot components missing"
[ "$(hash "$work/orig/dtb")" = "$expected_dtb" ] || fail "boot DTB is not the known Lunaris 3.13 reference"

# Avoid silently applying a legacy Magisk kernel patch or breaking a Magisk ramdisk.
# KSU userspace and all ramdisk bytes are left alone. Non-stock/unknown cpio fails closed.
rd="$work/ramdisk-check/ramdisk.cpio"
if ! "$MAGISKBOOT" decompress "$work/orig/ramdisk.cpio" "$rd"; then
  slice "$work/orig/ramdisk.cpio" 0 6 "$work/ramdisk-magic"
  case "$(cat "$work/ramdisk-magic")" in
    070701|070702) cp "$work/orig/ramdisk.cpio" "$rd";;
    *) fail "cannot read ramdisk for Magisk check";;
  esac
fi
[ -s "$rd" ] || fail "empty ramdisk"
if ! "$MAGISKBOOT" cpio "$rd" test; then
  fail "Magisk or unsupported ramdisk detected; no boot image written"
fi

cp "$kernel" "$work/orig/kernel"
(cd "$work/orig" && PATCHVBMETAFLAG=false "$MAGISKBOOT" repack -n "$original" "$candidate") || fail "cannot repack boot"
[ -f "$candidate" ] || fail "repacked boot missing"
[ "$(size "$candidate")" -eq "$orig_size" ] || fail "AVB boot output is not the original partition size"
footer_meta "$candidate" "$work/new-vbmeta"
"$BB" cmp -s "$work/old-vbmeta" "$work/new-vbmeta" || fail "embedded AVB metadata changed"
(cd "$work/new" && "$MAGISKBOOT" unpack -n "$candidate") || fail "cannot unpack repacked boot"
"$BB" cmp -s "$kernel" "$work/new/kernel" || fail "repacked kernel differs from verified image"
for f in ramdisk.cpio dtb second extra recovery_dtbo kernel_dtb; do
  if [ -e "$work/orig/$f" ] || [ -e "$work/new/$f" ]; then
    [ -f "$work/orig/$f" ] && [ -f "$work/new/$f" ] || fail "$f presence changed"
    "$BB" cmp -s "$work/orig/$f" "$work/new/$f" || fail "$f changed during repacking"
  fi
done
# Compare every defined v2 header byte except kernel size, legacy boot ID, and
# recovery_dtbo_offset, which may legitimately change when the kernel changes.
for region in '0 8' '12 564' '608 1028' '1644 16'; do
  set -- $region
  slice "$original" "$1" "$2" "$work/header-old"
  slice "$candidate" "$1" "$2" "$work/header-new"
  [ "$(size "$work/header-old")" -eq "$2" ] && [ "$(size "$work/header-new")" -eq "$2" ] || fail "short header read"
  "$BB" cmp -s "$work/header-old" "$work/header-new" || fail "boot header changed unexpectedly"
done

echo 'Prepared boot: exact kernel, non-kernel components, stable header and embedded AVB bytes checked.'
echo 'AVB SIGNATURE, ROM MODULES, KERNEL BOOT AND ROOT ARE NOT VERIFIED.'
