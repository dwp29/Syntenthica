### AnyKernel3 — Fresh-Milk / CHEESE-BURGER
## SP_RELEASE is rewritten by the packager from the build's LOCALVERSION.
## Installer text is English only, by request: large kernel name, plain progress.
## No auto reboot. No boot backup on this variant (see README).
SP_RELEASE="4.14.357-openela-Fresh-Milk-14.03"

### AnyKernel setup
properties() { '
kernel.string=Fresh-Milk for miatoll - Linux 4.14.357-openela
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

### AnyKernel install
boot_attributes() {
set_perm_recursive 0 0 755 644 $RAMDISK/*;
set_perm_recursive 0 0 750 750 $RAMDISK/init* $RAMDISK/sbin;
} # end attributes

BLOCK=/dev/block/bootdevice/by-name/boot;
IS_SLOT_DEVICE=0;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching (DO NOT REMOVE)
. tools/ak3-core.sh;

# --- plain progress output -----------------------------------------------------
# The kernel name is the only large element. Everything else is one short line.
sp_bar() {
  # $1 percent 0..100
  _pct=$1; _fill=$((_pct / 4)); _empty=$((25 - _fill))
  _bar=""; while [ $_fill -gt 0 ]; do _bar="${_bar}#"; _fill=$((_fill - 1)); done
  while [ $_empty -gt 0 ]; do _bar="${_bar}."; _empty=$((_empty - 1)); done
  ui_print "  [${_bar}] ${_pct}%  $2";
}

sp_fstype() {
  _dir="$1"; _best=""; _type=""
  while read -r _dev _mnt _fs _rest; do
    case "$_dir/" in
      "$_mnt"/*|"$_mnt"/)
        if [ ${#_mnt} -ge ${#_best} ]; then _best="$_mnt"; _type="$_fs"; fi
        ;;
    esac
  done < /proc/mounts
  echo "$_type"
}

sp_pick_log_root() {
  for _d in /sdcard /data/media/0 /storage/emulated/0 /cache /cache/recovery; do
    [ -d "$_d" ] || continue
    case "$(sp_fstype "$_d")" in tmpfs|ramfs|rootfs|"") continue ;; esac
    if ( : > "$_d/.fm_write_test" ) 2>/dev/null; then
      rm -f "$_d/.fm_write_test" 2>/dev/null
      echo "$_d"; return 0
    fi
  done
  return 1
}

stamp=$(date +%Y%m%d-%H%M%S 2>/dev/null); [ -n "$stamp" ] || stamp=manual
log_root=$(sp_pick_log_root) || log_root=""
LOG_FILE=""
if [ -n "$log_root" ]; then
  mkdir -p "$log_root/Breakfast" 2>/dev/null
  LOG_FILE="$log_root/Breakfast/install-$stamp.txt"
fi

log_line() {
  [ -n "$LOG_FILE" ] || return 0
  echo "$1" >> "$LOG_FILE" 2>/dev/null
}

# --- banner --------------------------------------------------------------------
ui_print " ";
ui_print " ";
ui_print "        ____                  _      __  __ _ _ _       ";
ui_print "       | __ ) _ __ ___  __ _ / _|  |  \\/  (_) | | __   ";
ui_print "       |  _ \\| '__/ _ \\/ _\` | |_   | |\\/| | | | |/ /   ";
ui_print "       | |_) | | |  __/ (_| |  _|  | |  | | | |   <    ";
ui_print "       |____/|_|  \\___|\\__,_|_|    |_|  |_|_|_|_|\\_\\   ";
ui_print " ";
ui_print "   $SP_RELEASE";
ui_print " ";
ui_print "   Installing kernel";
ui_print " ";

log_line "Fresh-Milk / CHEESE-BURGER - installation log"
log_line "started=$stamp"
log_line "release=$SP_RELEASE"
log_line "block=$BLOCK"

sp_bar 10 "Checking device"
if [ -f Image.gz ] && [ -x tools/busybox ]; then
  log_line "image_sha256=$(tools/busybox sha256sum Image.gz 2>/dev/null | tools/busybox cut -d' ' -f1)"
  log_line "image_bytes=$(tools/busybox stat -c %s Image.gz 2>/dev/null)"
fi

sp_bar 35 "Writing boot image"
log_line "write=started"
dump_boot;
write_boot;
log_line "write=done"

sp_bar 75 "Finalising"
sp_bar 100 "Finished"

log_line "result=success"
log_line "auto_reboot=no"
[ -n "$LOG_FILE" ] && log_line "log=$LOG_FILE"

ui_print " ";
ui_print "   Kernel installed.";
ui_print "   Reboot when ready.";
[ -n "$LOG_FILE" ] && ui_print "   Log: $LOG_FILE";
ui_print " ";
