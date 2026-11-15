### UFO-0.1 build

commit: facd6c64093a4e07f7a212b2c3bd69fdf163d412

#### error pertama
```
2662:-- KSU_NEXT: fallthrough in compiler_attributes.h not found
```

#### ekor log (60 baris)
```
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/utils/src/wlan_utility.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/spectral/core/spectral_offload.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/spectral/core/spectral_common.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/spectral/dispatcher/src/wlan_spectral_ucfg_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/spectral/dispatcher/src/wlan_spectral_utils_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/spectral/dispatcher/src/wlan_spectral_tgt_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/os_if/linux/spectral/src/wlan_cfg80211_spectral.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/os_if/linux/spectral/src/os_if_spectral_netlink.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/spectral/target_if_spectral_netlink.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/spectral/target_if_spectral_phyerr.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/spectral/target_if_spectral.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/spectral/target_if_spectral_sim.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/gpio/dispatcher/src/wlan_gpio_tgt_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/gpio/dispatcher/src/wlan_gpio_ucfg_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/gpio/core/src/wlan_gpio_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/os_if/linux/gpio/src/wlan_cfg80211_gpio.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/gpio/target_if_gpio.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/green_ap/core/src/wlan_green_ap_main.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/green_ap/dispatcher/src/wlan_green_ap_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/green_ap/dispatcher/src/wlan_green_ap_ucfg_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/target_if/green_ap/src/target_if_green_ap.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/crypto/src/wlan_crypto_global_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/crypto/src/wlan_crypto_ucfg_api.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/crypto/src/wlan_crypto_main.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/crypto/src/wlan_crypto_obj_mgr.o
  CC      drivers/staging/qcacld-3.0/../qca-wifi-host-cmn/umac/cmn_services/crypto/src/wlan_crypto_param_handling.o
  AR      drivers/staging/qcacld-3.0/wlan.o
  AR      drivers/staging/qcacld-3.0/built-in.o
  AR      drivers/staging/built-in.o
  AR      drivers/built-in.o
  GEN     .version
  CC      init/main.o
  CHK     include/generated/compile.h
  CC      init/do_mounts.o
  CC      init/do_mounts_rd.o
  UPD     include/generated/compile.h
  CC      init/do_mounts_initrd.o
  CC      init/do_mounts_dm.o
  CC      init/noinitramfs.o
  CC      init/initramfs.o
  CC      init/init_task.o
  CC      init/version.o
  AR      init/mounts.o
  AR      init/built-in.o
  AR      built-in.o
  LTO     vmlinux.o
  MODPOST vmlinux.o
  KSYM    .tmp_kallsyms1.o
  KSYM    .tmp_kallsyms2.o
  LD      vmlinux
  SORTEX  vmlinux
  SYSMAP  System.map
find: ‘arch/arm64/boot/dts/’: No such file or directory
find: ‘arch/arm64/boot/dts/’: No such file or directory
  OBJCOPY arch/arm64/boot/Image
find: ‘arch/arm64/boot/dts/’: No such file or directory
find: ‘arch/arm64/boot/dts/’: No such file or directory
  GZIP    arch/arm64/boot/Image.gz
make[1]: Leaving directory '/home/runner/work/_temp/ufo/out'
exit=0
```

#### audit
```
       Manager must match the vendored KernelSU-Next (this fork ships root as a metamodule for legacy kernels).
       susfs4ksu module must provide the v2.x 'ksu_susfs' helper; v1.5.x 'susfs4ksu.sh' is incompatible.
       NoMount's 'nm' CLI + profiles ship as a KSU/APatch metamodule; rules live in the kernel keyring, not in /dev.

AUDIT PASSED (0 errors, 1 warning(s))
```

#### hasil
```
-rw-r--r-- 1 runner runner 15895043 Nov 15 04:40 /home/runner/work/_temp/ufo/out/arch/arm64/boot/Image.gz
6da3b7477074abefe848438887cd1175c2b3a5253f9cef93c59759841e75e547  /home/runner/work/_temp/ufo/out/arch/arm64/boot/Image.gz
versi tertanam: 4.14.344-openela-UFO-0.1
ukuran setelah dibuka: 39,184,400 byte
versi: 4.14.344-openela-UFO-0.1

KUAT (gagal bila hilang):
  UCLAMP     ADA    (  1)  sysfs attribute registered by CONFIG_UCLAMP_TASK_GROUP
  UCLAMP     ADA    (  1)  its pair; both must be present
  WALT       ADA    (  1)  tracepoint field emitted only by CONFIG_SCHED_WALT
  KernelSU   ADA    (  1)  the KSU driver struct, not a borrowed symbol

LEMAH (tidak dinilai; hanya menunjukkan nama ada):
  MGLRU         2 kemunculan
  UCLAMP        3 kemunculan
  WALT          3 kemunculan
  KernelSU    158 kemunculan
  SuSFS       117 kemunculan
  NoMount       2 kemunculan

  Kinesis stock KSU  tidak ada  (0)

Untuk MGLRU, SuSFS dan NoMount, Image tidak bisa menjawab. Yang menjawab
adalah System.map (diterbitkan build ini) lewat root_stack_report.py:
symbol yang ada = fungsi benar-benar ditautkan; yang tidak ada = tidak.

semua penanda KUAT ada.
```

#### zip siap flash
```

#### zip siap flash
```
3f1bd045aa1e12dd42b354f881d1d4da688d08dddb34d87653d264ff45505610  /home/runner/work/_temp/UFO-0.1-miatoll-4.14.344.zip
26 berkas
  anykernel.sh
  Image.gz
```
Belum di-flash siapa pun.

catatan perakitan:
```
