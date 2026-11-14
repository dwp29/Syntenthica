# AnyKernel3 Ramdisk Mod Script
# osm0sis @ xda-developers
# UFO-0.1 — Linux 4.14.344 + KernelSU-Next + SuSFS v2.3.0 + NoMount
#
# Basis: Kinesis (clarencelol/kernel_xiaomi_sm6250 @ kinesis-v29) yang dipasangi
# seluruh fitur Synthetica 3.2: MGLRU, UCLAMP, WALT, KSU seccomp & fd-after-exec.
#
# PENTING:
#   - Paket ini TIDAK mengganti DTB. DTB disusun dari sumber Kinesis untuk miatoll;
#     DTB milik ROM Anda dipertahankan apa adanya.
#   - cmdline dipertahankan apa adanya; hanya sisa eksperimen 1.3.0
#     (memmap=..., ram.mem_address=...) yang dibuang kalau ada.
#   - /data/adb/ksud yang sudah ada TIDAK ditimpa.

## AnyKernel setup
properties() { '
kernel.string=UFO-0.1 - Linux 4.14.344 + KernelSU-Next + SuSFS + NoMount - miatoll
kernel.compiler=clang 18 (AOSP LLVM)
kernel.made=graziemille
kernel.version=UFO-0.1
message.word=UFO-0.1
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
. tools/ak3-core.sh;


## AnyKernel file attributes
set_perm_recursive 0 0 755 644 $ramdisk/*;
set_perm_recursive 0 0 750 750 $ramdisk/init* $ramdisk/sbin;


## AnyKernel boot install
dump_boot;

ui_print " "
ui_print "  UFO-0.1"
ui_print "  Linux 4.14.344 + KernelSU-Next + SuSFS + NoMount"
ui_print "  Basis Kinesis + MGLRU + UCLAMP + WALT"
ui_print " "

# --- cadangan senyap --------------------------------------------------------
DIAG=/sdcard/UFO-diag
mkdir -p $DIAG 2>/dev/null
cp -f $split_img/boot.img $DIAG/boot-sebelum-UFO-0.1.img 2>/dev/null
ui_print "  cadangan boot lama: /sdcard/UFO-diag/"

# Catat identitas kernel yang sedang dipasang, supaya kalau gagal boot
# setidaknya ada berkas yang bisa dibaca.
{
  echo "paket=UFO-0.1"
  echo "kernel=4.14.344-openela-UFO-0.1"
  echo "tanggal=$(date 2>/dev/null)"
  echo "device=$(getprop ro.product.device 2>/dev/null)"
} > $DIAG/identitas-UFO-0.1.txt 2>/dev/null

# --- cmdline: pertahankan milik ROM, buang sisa 1.3.0 -----------------------
if [ -f "$split_img/cmdline.txt" ]; then
  OLD_CMD=$(cat "$split_img/cmdline.txt" 2>/dev/null)
else
  OLD_CMD=$(grep '^cmdline=' "$split_img/header" 2>/dev/null | cut -d= -f2-)
fi
echo "$OLD_CMD" > $DIAG/cmdline-sebelum-UFO-0.1.txt 2>/dev/null

case "$OLD_CMD" in
  *memmap=*|*ram.mem_address=*)
    NEW_CMD=$(echo "$OLD_CMD" | sed -e 's/memmap=[^ ]*//g' -e 's/ram\.mem_address=[^ ]*//g' -e 's/  */ /g' -e 's/^ *//' -e 's/ *$//')
    echo "$NEW_CMD" > $split_img/cmdline.txt
    ui_print "  cmdline: token 1.3.0 dibuang (${#NEW_CMD} byte)"
    ;;
  "")
    ui_print "  cmdline: kosong, dibiarkan"
    ;;
  *)
    ui_print "  cmdline: dipakai apa adanya (${#OLD_CMD} byte)"
    ;;
esac

# --- DTB: tidak pernah diganti -------------------------------------------------
# Roll 3.3 menanam DTB ROM 3.0.304.0 kalau sha256-nya cocok. UFO-0.1 tidak membawa
# DTB sama sekali: DTB bawaan boot image Anda dipertahankan. Ini menghilangkan satu
# penyebab bootloop yang tidak perlu.
ui_print "  DTB: dipertahankan (paket ini tidak membawa DTB)"

ui_print "  Memasang kernel..."
write_boot;
ui_print "  Selesai. Reboot system."


# --- ksud: jangan timpa yang sudah ada --------------------------------------
if [ -f ./ksud ]; then
  mount -o rw /data 2>/dev/null
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t f2fs -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/by-name/userdata /data 2>/dev/null
  [ -d /data/adb ] || mount -t ext4 -o rw /dev/block/bootdevice/by-name/userdata /data 2>/dev/null
  if [ -d /data/adb ] && [ ! -f /data/adb/ksud ]; then
    cp -f ./ksud /data/adb/ksud
    chown 0:0 /data/adb/ksud 2>/dev/null
    chmod 0755 /data/adb/ksud 2>/dev/null
    mkdir -p /data/adb/ksu/bin /data/adb/ksu/log /data/adb/ksu/cache /data/adb/modules /data/adb/modules_update 2>/dev/null
    ui_print "  KernelSU: ksud dipasang (belum ada sebelumnya)"
  fi
fi
