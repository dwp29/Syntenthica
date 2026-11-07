#!/sbin/sh
# Synthetica 2.0 EXPERIMENTAL. This is not a validated production release.
properties() { '
kernel.string=Synthetica 2.0 Experimental - Neutron - MGLRU ON
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=1
device.name1=joyeuse
device.name2=miatoll
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; }

ui_print() {
  until [ ! "$1" ]; do
    echo "ui_print $1
ui_print" >> "/proc/self/fd/$OUTFD"
    shift
  done
}
fail() { ui_print ' ' "ERROR: $*" 'No reboot will be performed.'; exit 1; }
prop() { getprop "$1" 2>/dev/null || true; }

ui_print ' ' 'Synthetica 2.0 EXPERIMENTAL - Neutron / MGLRU ON' \
  'WARNING: no physical boot, ROM module or root test has been performed.' \
  'A bootloop is possible. Keep the current boot backup and recovery available.' ' '

# Do not guess which slot to overwrite on an A/B device.
slot=$(prop ro.boot.slot_suffix)
[ -z "$slot" ] || [ "$slot" = normal ] || fail "A/B slot detected; this package only targets an unslotted boot partition"
locked=$(prop ro.boot.flash.locked)
state=$(prop ro.boot.verifiedbootstate)
device_state=$(prop ro.boot.vbmeta.device_state)
[ "$locked" != 1 ] && [ "$device_state" != locked ] || fail 'Bootloader reports locked'
[ "$locked" = 0 ] || [ "$state" = orange ] || [ "$device_state" = unlocked ] || fail 'Cannot confirm unlocked bootloader from recovery'

BLOCK=/dev/block/bootdevice/by-name/boot
BB="$AKHOME/tools/busybox"
MAGISKBOOT="$AKHOME/tools/magiskboot"
export BB MAGISKBOOT
[ -b "$BLOCK" ] || fail 'Expected boot block device does not exist'
partsize=$("$BB" blockdev --getsize64 "$BLOCK") || fail 'Cannot determine boot partition size'
[ "$partsize" = 134217728 ] || fail 'Boot partition size differs from the published Joyeuse/miatoll reference'
readonly=$("$BB" blockdev --getro "$BLOCK") || fail 'Cannot determine whether boot partition is writable'
[ "$readonly" = 0 ] || fail 'Boot partition is read-only'

ui_print 'Reading current boot image. Nothing is written yet...'
original="$AKHOME/current-boot.img"
candidate="$AKHOME/new-boot.img"
"$BB" dd if="$BLOCK" of="$original" bs=1048576 2>/dev/null || fail 'Unable to read full boot partition'
[ "$("$BB" stat -c %s "$original")" = "$partsize" ] || fail 'Short boot partition read'

ui_print 'Checking kernel hash, boot format, reference DTB, ramdisk and preserved components...'
if ! ash "$AKHOME/tools/prepare-boot.sh" "$original" "$AKHOME/Image.gz" "$candidate" "$AKHOME/boot-check" \
  3a9f39f8f7ea79c9251a896050dfeb60395f1194a064f91a85a8fe8ae38adaea \
  6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239; then
  fail 'Boot checks failed. The boot partition was not written.'
fi
[ "$("$BB" stat -c %s "$candidate")" = "$partsize" ] || fail 'Repacked boot has unexpected size'
"$BB" cmp -s "$original" "$BLOCK" || fail 'Boot changed during preparation; no write performed'
ui_print 'WARNING: AVB signature and ROM modules are NOT verified.' 'Writing boot partition...'
if ! "$BB" dd if="$candidate" of="$BLOCK" bs=1048576 conv=fsync; then
  ui_print 'WRITE FAILED. DO NOT REBOOT. RESTORE YOUR EXACT BOOT BACKUP FROM RECOVERY.'
  exit 1
fi
if ! "$BB" cmp -s -n "$partsize" "$candidate" "$BLOCK"; then
  ui_print 'BOOT READBACK MISMATCH. DO NOT REBOOT. RESTORE YOUR EXACT BOOT BACKUP FROM RECOVERY.'
  exit 1
fi
ui_print 'Boot write and byte readback completed.' \
  'No automatic reboot. Boot, root and ROM module compatibility remain untested.' \
  'If the phone does not boot, return to recovery and restore your exact boot backup.'
