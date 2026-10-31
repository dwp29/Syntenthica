### AnyKernel3 — Synthetica (graziemille)
## SP_VERSION / SP_ROOT_LINE / SP_UNAME are rewritten by ci/package_release.py from STATUS.json.
## No boot backup (removed in 2.0 by request), no modules, no ramdisk edits, no auto reboot.
## The installer writes an installation log to storage (Synthetica/install-log-*.txt).
SP_VERSION="2.0"
SP_ROOT_LINE="KernelSU-Next (built-in)"
SP_UNAME="4.14.357-openela-Synthetica-2.0"

### AnyKernel setup
properties() { '
kernel.string=Synthetica by graziemille - Linux 4.14.357-openela
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

# --- installation log ---------------------------------------------------------
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
    if ( : > "$_d/.synthetica_write_test" ) 2>/dev/null; then
      rm -f "$_d/.synthetica_write_test" 2>/dev/null
      echo "$_d"; return 0
    fi
  done
  return 1
}

stamp=$(date +%Y%m%d-%H%M%S 2>/dev/null); [ -n "$stamp" ] || stamp=manual
log_root=$(sp_pick_log_root) || log_root=""
LOG_FILE=""
if [ -n "$log_root" ]; then
  mkdir -p "$log_root/Synthetica" 2>/dev/null
  LOG_FILE="$log_root/Synthetica/install-log-$stamp.txt"
fi

log_line() {
  [ -n "$LOG_FILE" ] || return 0
  echo "$1" >> "$LOG_FILE" 2>/dev/null
}

ui_print " ";
ui_print "  بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ";
ui_print " ";
ui_print "  Synthetica $SP_VERSION";
ui_print "  Kernel : $SP_UNAME";
ui_print "  Root   : $SP_ROOT_LINE";
ui_print " ";

log_line "Synthetica $SP_VERSION - kernel installation log"
log_line "started=$stamp"
log_line "kernel=$SP_UNAME"
log_line "root=$SP_ROOT_LINE"
log_line "block=$BLOCK"
if [ -x tools/busybox ] && [ -f Image.gz ]; then
  log_line "image_sha256=$(tools/busybox sha256sum Image.gz 2>/dev/null | tools/busybox cut -d' ' -f1)"
  log_line "image_bytes=$(tools/busybox stat -c %s Image.gz 2>/dev/null)"
fi
log_line "boot_backup=disabled"
[ -n "$LOG_FILE" ] && ui_print "  Log    : $LOG_FILE";
ui_print " ";

# --- Root userspace: ksud ------------------------------------------------------
if [ -f ./ksud ]; then
  ui_print "  Installing ksud...";
  mkdir -p /data 2>/dev/null;
  mount -o rw /data 2>/dev/null;
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/by-name/userdata /data 2>/dev/null;
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null;
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/by-name/userdata /data 2>/dev/null;
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null;
  mount -o rw,remount /data 2>/dev/null;
  if [ -d /data/adb ]; then
    cp -f ./ksud /data/adb/ksud;
    chown 0:0 /data/adb/ksud 2>/dev/null;
    chmod 0755 /data/adb/ksud 2>/dev/null;
    mkdir -p /data/adb/ksu/bin /data/adb/ksu/log /data/adb/ksu/cache 2>/dev/null;
    mkdir -p /data/adb/modules /data/adb/modules_update 2>/dev/null;
    chcon u:object_r:ksu_file:s0 /data/adb/ksud 2>/dev/null;
    if [ "$(stat -c %s /data/adb/ksud 2>/dev/null)" != "$(stat -c %s ./ksud 2>/dev/null)" ]; then
      ui_print "  ! ksud failed (data read-only?)";
      log_line "ksud=failed";
    else
      ui_print "  ksud OK";
      log_line "ksud=installed";
    fi
  else
    ui_print "  ! /data is locked - ksud NOT installed. Unlock data, then flash again.";
    log_line "ksud=skipped-data-locked";
  fi
fi

# --- Install -------------------------------------------------------------------
ui_print "  Writing kernel...";
log_line "write=started"
dump_boot;
write_boot;
log_line "write=done"
log_line "result=success"
log_line "auto_reboot=no"

ui_print " ";
ui_print "  الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ";
ui_print " ";
ui_print "  Done. Kernel installed.";
[ -n "$LOG_FILE" ] && ui_print "  Installation log: $LOG_FILE";
ui_print "  No auto-reboot. Reboot when you are ready.";
ui_print " ";
