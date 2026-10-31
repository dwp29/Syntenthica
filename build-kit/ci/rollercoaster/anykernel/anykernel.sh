# AnyKernel3 Ramdisk Mod Script
# osm0sis @ xda-developers
# Rollercoaster — satu zip: kernel + userspace root (ksud)

## AnyKernel setup
# begin properties
properties() { '
kernel.string=Rollercoaster by graziemille
kernel.compiler=clang 18 (AOSP LLVM)
kernel.made=graziemille
kernel.version=Rollercoaster
message.word=Rollercoaster
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
'; } # end properties

# shell variables
block=/dev/block/bootdevice/by-name/boot;
is_slot_device=0;
ramdisk_compression=auto;
patch_vbmeta_flag=auto;


## AnyKernel methods (DO NOT CHANGE)
# import patching functions/variables - see for reference
. tools/ak3-core.sh;


## AnyKernel file attributes
# set permissions/ownership for included ramdisk files
set_perm_recursive 0 0 755 644 $ramdisk/*;
set_perm_recursive 0 0 750 750 $ramdisk/init* $ramdisk/sbin;


## AnyKernel boot install
# Catatan: tidak ada pencadangan boot otomatis. Boot lama TIDAK disalin ke /sdcard.
dump_boot;
write_boot;
## end boot install


# --- Rollercoaster: pasang userspace KernelSU (ksud) ---------------------------
# Senyap saat berhasil (tanpa baris progres). Pesan hanya muncul kalau ada
# masalah yang harus ditindaklanjuti.
if [ -f ./ksud ]; then
  mkdir -p /data 2>/dev/null
  mount -o rw /data 2>/dev/null
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null
  mount -o rw,remount /data 2>/dev/null

  if [ -d /data/adb ]; then
    cp -f ./ksud /data/adb/ksud
    chown 0:0 /data/adb/ksud 2>/dev/null
    chmod 0755 /data/adb/ksud 2>/dev/null
    mkdir -p /data/adb/ksu/bin /data/adb/ksu/log /data/adb/ksu/cache 2>/dev/null
    mkdir -p /data/adb/modules /data/adb/modules_update 2>/dev/null
    chcon u:object_r:ksu_file:s0 /data/adb/ksud 2>/dev/null
    if [ "$(stat -c %s /data/adb/ksud 2>/dev/null)" != "$(stat -c %s ./ksud 2>/dev/null)" ]; then
      ui_print "  ! /data/adb/ksud gagal ditulis (data read-only?)"
    fi
  else
    ui_print "  ! /data belum terbuka — ksud TIDAK dipasang."
    ui_print "  ! Decrypt data di recovery (masukkan PIN), lalu flash zip ini sekali lagi."
  fi
fi

ui_print "  Rollercoaster: kernel + root terpasang."
# ------------------------------------------------------------------------------
