# AnyKernel3 Ramdisk Mod Script
# osm0sis @ xda-developers
# BREAKFAST - Fresh-Milk / CHEESE-BURGER: kernel + KernelSU-Next userspace (ksud)

## AnyKernel setup
# begin properties
properties() { '
kernel.string=Fresh-Milk / CHEESE-BURGER for miatoll - Linux 4.14.357
kernel.compiler=Neutron clang 24
kernel.made=@Pure_Saturday
kernel.version=Fresh-Milk-14.03 / CHEESE-BURGER-11.08
message.word=Breakfast
do.devicecheck=1
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=0
device.name1=miatoll
device.name2=curtana
device.name3=excalibur
device.name4=gram
device.name5=joyeuse
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties

# shell variables
block=/dev/block/bootdevice/by-name/boot;
is_slot_device=0;
ramdisk_compression=auto;
patch_vbmeta_flag=auto;

# The packager rewrites this line from the build's own CONFIG_LOCALVERSION, so
# the string shown below the banner always matches the image being flashed.
SP_RELEASE="4.14.357-openela-Fresh-Milk-14.03";


## AnyKernel methods (DO NOT CHANGE)
# import patching functions/variables - see for reference
. tools/ak3-core.sh;


## AnyKernel file attributes
# set permissions/ownership for included ramdisk files
set_perm_recursive 0 0 755 644 $ramdisk/*;
set_perm_recursive 0 0 750 750 $ramdisk/init* $ramdisk/sbin;


## installer text -------------------------------------------------------------
# English only. The kernel name is the one large element; everything else is a
# single short line. No banner art, no prayer, no auto reboot.

sp_bar() {
  # $1 = percent, $2 = what is happening
  _pct="$1"; _fill=$((_pct / 4)); _empty=$((25 - _fill))
  _bar=""
  while [ "$_fill" -gt 0 ]; do _bar="${_bar}#"; _fill=$((_fill - 1)); done
  while [ "$_empty" -gt 0 ]; do _bar="${_bar}."; _empty=$((_empty - 1)); done
  ui_print "  [${_bar}] ${_pct}%  $2"
}

# Pick a writable place for the install log. tmpfs/ramfs are skipped because a
# log there disappears on reboot and would look like a failed write.
sp_log_root() {
  for _d in /sdcard /data/media/0 /storage/emulated/0 /cache; do
    [ -d "$_d" ] || continue
    _fs="$(stat -f -c %T "$_d" 2>/dev/null)"
    case "$_fs" in tmpfs|ramfs|rootfs|"") continue ;; esac
    if ( : > "$_d/.fm_probe" ) 2>/dev/null; then
      rm -f "$_d/.fm_probe" 2>/dev/null
      echo "$_d"; return 0
    fi
  done
  return 1
}

stamp="$(date +%Y%m%d-%H%M%S 2>/dev/null)"; [ -n "$stamp" ] || stamp=manual
LOG_FILE=""
if _root="$(sp_log_root)"; then
  mkdir -p "$_root/Breakfast" 2>/dev/null
  LOG_FILE="$_root/Breakfast/install-$stamp.txt"
fi
log_line() {
  [ -n "$LOG_FILE" ] || return 0
  echo "$1" >> "$LOG_FILE" 2>/dev/null
}

ui_print " "
ui_print "   $SP_RELEASE"
ui_print " "
ui_print "   Installing kernel"
ui_print " "

log_line "Fresh-Milk / CHEESE-BURGER - installation log"
log_line "started=$stamp"
log_line "release=$SP_RELEASE"
log_line "block=$block"

sp_bar 10 "Checking device"
if [ -f Image.gz ] && [ -x tools/busybox ]; then
  log_line "image_sha256=$(tools/busybox sha256sum Image.gz 2>/dev/null | tools/busybox cut -d' ' -f1)"
  log_line "image_bytes=$(tools/busybox stat -c %s Image.gz 2>/dev/null)"
fi

## AnyKernel boot install
# No automatic boot backup is taken on this variant.
sp_bar 35 "Writing boot image"
log_line "write=started"
dump_boot;
write_boot;
log_line "write=done"
## end boot install

sp_bar 75 "Finalising"

# --- KernelSU-Next userspace (ksud) -------------------------------------------
# Silent when it succeeds. Messages appear only for something the user must act
# on: encrypted /data at flash time.
if [ -f ./ksud ]; then
  mount -o rw,remount /data 2>/dev/null
  if [ -d /data/adb ]; then
    cp -f ./ksud /data/adb/ksud
    chown 0:0 /data/adb/ksud 2>/dev/null
    chmod 0755 /data/adb/ksud 2>/dev/null
    mkdir -p /data/adb/ksu/bin /data/adb/ksu/log /data/adb/ksu/cache 2>/dev/null
    mkdir -p /data/adb/modules /data/adb/modules_update 2>/dev/null
    chcon u:object_r:ksu_file:s0 /data/adb/ksud 2>/dev/null
    if [ "$(stat -c %s /data/adb/ksud 2>/dev/null)" != "$(stat -c %s ./ksud 2>/dev/null)" ]; then
      ui_print "   Warning: /data/adb/ksud did not write (is /data read-only?)"
      log_line "ksud=copy_mismatch"
    else
      log_line "ksud=installed"
    fi
  else
    ui_print "   Warning: /data is not unlocked, so ksud was not installed."
    ui_print "   Decrypt data in recovery (enter your PIN), then flash this zip again."
    log_line "ksud=skipped_data_locked"
  fi
fi

sp_bar 100 "Finished"
log_line "result=success"
log_line "auto_reboot=no"
[ -n "$LOG_FILE" ] && log_line "log=$LOG_FILE"

ui_print " "
ui_print "   Kernel installed."
ui_print "   Reboot when ready."
[ -n "$LOG_FILE" ] && ui_print "   Log: $LOG_FILE"
ui_print " "
# ------------------------------------------------------------------------------
