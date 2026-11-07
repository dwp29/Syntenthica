# Synthetica 3.0-rc1: kandidat uji untuk joyeuse

**Status: kandidat uji, bukan rilis stabil.** Dokumen ini menjelaskan jalur baru
berbasis Synthetica 2.0 eksperimen yang dilaporkan boot oleh pengguna, bukan
build 3.0 lama yang dijelaskan di `SYNTHETICA-3.0.md`. ZIP recovery di bawah
sudah dibuat dan diuji secara sintetis, tetapi **belum diuji pada perangkat**.
Jangan menganggap berkas bukti kompilasi sebagai ZIP flashable.

## ZIP kandidat dan hasil tes

- [Unduh Synthetica-3.0-rc1-Neutron-MGLRU-on-TEST.zip](https://drive.google.com/file/d/1-541dKUnmYJy8RtrfWfXpTYNtC_LxAEf/view?usp=drivesdk)
  — 15.720.062 byte.
- SHA-256 ZIP: `811b72694f1ee3c9264c6d077c28e386d3aec8e67a6b5c4cec6d352c1c33929b`.
- SHA-256 `Image.gz` di dalam ZIP: `c83b7a8ac326f189d2dc3ec49da7758ceeb31b1db61952e30032b2a1b9ac83a2`.
- Kernel release: `4.14.357-openela-Synthetica-3.0-rc1`.
- [Run build dan packaging 42342404613](https://github.com/dwp29/Syntenthica/actions/runs/42342404613)
  berhasil mengompilasi, memvalidasi bukti, dan mengemas kandidat ini, tetapi
  **run secara keseluruhan gagal** karena tes ARM/QEMU pertama timeout. Penyebab
  hang tersebut tidak berhasil dipastikan.
- [Run diagnostik terpisah 42343549394](https://github.com/dwp29/Syntenthica/actions/runs/42343549394)
  menguji **ZIP dengan SHA yang sama**: lima tes repack/penolakan dan tes skrip
  writer sebenarnya pada boot sintetis berbasis loop berhasil. Tes yang sama juga
  lulus di lingkungan lokal sintetis. Tidak satu pun menguji perangkat, recovery
  nyata, root, SECCOMP saat runtime, kamera, modul ROM, atau keabsahan AVB.

## Sebelum mencoba

1. Paket ini hanya kandidat untuk joyeuse/Lunaris yang sama, dengan bootloader
   terbuka, boot tanpa slot, format boot-v2 dan recovery yang kompatibel.
   Pemeriksaan installer dapat menolak perangkat/boot yang tidak sesuai.
2. Backup **boot yang sedang terpasang persis** melalui recovery dan simpan
   backup di tempat aman. Pastikan recovery dan cara restore benar-benar dapat
   diakses sebelum flashing; bootloop atau AVB gagal tetap mungkin terjadi.
3. Cocokkan SHA-256 ZIP, lalu flash ZIP utuh melalui recovery. Installer tidak
   membuat backup otomatis. Jika tampil kegagalan tulis/readback, **jangan
   reboot** dan pulihkan backup boot dari recovery. Jika bootloop, kembali ke
   recovery dan pulihkan backup yang sama.
4. Setelah boot, cocokkan `uname -r` dengan kernel release di atas, periksa
   Manager dan `su`, lalu ulangi tes SECCOMP dan kamera. Tampilan Manager belum
   dapat dijamin berubah karena patch hanya mempertahankan filter jika ROM
   memang memasangnya.

## Dasar dan batas bukti

Pengguna melaporkan eksperimen Neutron 2.0 boot pada joyeuse/Lunaris AOSP GMS
3.13 Android 16, terdeteksi di KernelSU Manager, dan fitur umumnya berfungsi.
Pengguna juga melaporkan `/sys/kernel/mm/lru_gen/enabled` bernilai `1`: MGLRU
aktif saat laporan tersebut dibuat. Ini adalah laporan untuk image eksperimen
sebelumnya, bukan pengujian image 3.0-rc1 yang baru.

Kamera **0.6× freeze** menurut pengguna, juga pernah terjadi pada beberapa
kernel lain. Tidak ada perubahan driver/HAL kamera atau klaim perbaikan kamera
pada kandidat ini. Secara statis config eksperimen memuat `SPECTRA_CAMERA=y`;
Makefile source memasukkan komponen sensor, CCI dan request manager ke jalur
itu. Installer mempertahankan DTB boot yang ada, bukan memasang DTB baru. Pada
perbandingan referensi yang terbatas, `cam_sensor_dev.c` identik dengan
LineageOS `lineage-22.2@803b55865869df8558ef07f51bfb8182d95d08ed`, sedangkan
`cam_sensor_core.c` berbeda pada pemeriksaan null dan komentar copyright saja.
LineageOS bukan bukti source/ROM yang sedang terpasang dan perbandingan ini
tidak menentukan penyebab freeze. Nama dan versi aplikasi kamera, perilaku pada
kernel bawaan ROM, serta log saat freeze dibutuhkan untuk diagnosis.

Konfigurasi kandidat diaudit agar sama dengan konfigurasi Neutron MGLRU-on yang
dilaporkan boot, **kecuali `LOCALVERSION`**. Ini mempertahankan MGLRU default-on,
Uclamp, WALT/STune, thermal, KernelSU-Next, verity, MODVERSIONS dan penegakan
signature modul. Perubahan kode yang disengaja adalah patch Manager di bawah;
penamaan `3.0-rc1` membedakan image baru dan build 3.0 lama, serta menandakan
bahwa pengujian perangkat dan kamera belum lengkap.

## SECCOMP: temuan dan cakupan patch

Kernel config sebelumnya memuat `CONFIG_SECCOMP=y` dan `CONFIG_SECCOMP_FILTER=y`.
Tampilan Manager membaca `PR_GET_SECCOMP` pada thread pemanggil, bukan status
global semua proses. Nilai `0` berarti tidak ada filter pada thread itu, nilai
`2` berarti filter aktif, dan kesalahan pembacaan bukan bukti status global.

Pada source KernelSU-Next yang dipin, `ksu_handle_setresuid()` untuk kernel di
bawah 5.10 memang memanggil `disable_seccomp(current)` pada cabang UID Manager.
Dalam cabang yang sama, driver FD Manager dijadwalkan melalui task work; kode JNI
Manager yang dipin mencari FD tersebut di `/proc/self/fd`. Pada referensi AOSP
Android 16 [`frameworks/base@99b01a65`](https://github.com/aosp-mirror/platform_frameworks_base/blob/99b01a65cc4c104933788b3143285ab6bae65827/core/jni/com_android_internal_os_Zygote.cpp),
filter aplikasi dipasang sebelum `setresuid` bila security enforcement aktif.
Pada referensi [`bionic@09a271af`](https://github.com/aosp-mirror/platform_bionic/blob/09a271af557444c9a6b3f3146d6d474156fd6cdb/libc/SECCOMP_BLOCKLIST_APP.TXT),
`reboot` diblokir, sedangkan `ioctl`/`execve` tidak ada dalam blocklist yang
diperiksa. Ini mendukung jalur FD, tetapi tidak membuktikan policy ROM atau
keseluruhan perilaku Manager yang terpasang.

Patch 3.0-rc1 hanya menghapus pematian filter pada cabang **Manager**; injeksi
FD, pemeriksaan identitas, serta jalur root tetap tidak diubah. Patch
mempertahankan filter jika ROM benar-benar memasangnya; patch tidak membuat
filter jika belum ada, dan tidak memalsukan tampilan Manager.

**Ini bukan perbaikan SECCOMP global.** Cabang untuk beberapa aplikasi yang
sudah diizinkan root pada kernel 4.14 masih dapat mematikan filter saat
`setresuid`; `escape_with_root_profile()` juga tetap mematikannya saat eskalasi
root. Jalur tersebut sengaja tidak diubah karena kompatibilitas supercall/reboot
KernelSU belum dapat diuji di sini. Aplikasi biasa tidak otomatis menjadi tidak
terfilter hanya karena tampilan Manager menunjukkan `Disabled`, tetapi kondisi
per-thread aktual harus diukur di perangkat. Manager, pemberian root, dan
SECCOMP setelah patch tetap membutuhkan tes nyata; tes host menggunakan stub
bukan pengujian BPF atau Android.

## Reproduksi dan keamanan build

- Source: `Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795b557b7bf92220c91f05a42b456de7a74`.
- Feature patches dan toolchain sama dengan jalur `synthetica2-experimental`:
  Neutron clang/LLD 24 (`06092026`), dengan SHA archive dipin oleh script.
- Patch baru: `build-kit/ci/synthetica3-rc/0001-ksu-manager-preserve-seccomp.patch`.
- Guard build: `build-kit/scripts/build_synthetica3_rc.py`; membandingkan hasil
  dengan config eksperimen yang dipin dan menolak perubahan selain versi.
- Guard packaging: `build-kit/scripts/package_synthetica3_rc.py`; memakai skrip
  installer yang sama dengan pengujian sebelumnya, mengganti pin image dan
  label, serta tidak menyertakan key privat, ksud atau modul.
- Workflow: `.github/workflows/synthetica3-rc1.yml`. Tes meliputi regresi host,
  build, bukti konfigurasi/identitas, repack ARM/QEMU dan boot sintetis pada loop
  device jika tersedia. Itu **bukan** tes boot fisik, recovery nyata, pairing
  root, perilaku seccomp, kamera, kepercayaan modul ROM, atau validitas AVB.

Setiap kompilasi membuat sertifikat signing modul baru. Meskipun konfigurasi dan
ABI diperiksa, modul yang dibangun/ditandatangani untuk image lama belum tentu
dipercayai oleh image baru. Jangan mematikan signature atau MODVERSIONS untuk
memaksakan modul. Installer tidak menulis partisi selain boot, tidak mengubah
`vbmeta`, `dtbo`, `/data/adb/ksud` atau modul, dan tidak membuat backup otomatis;
signature AVB lama pada boot yang diubah mungkin tidak valid. Pemulihan hanya
dengan backup boot yang tepat dan recovery yang dapat diakses.

## Bukti perangkat yang diminta

1. Sebutkan nama/versi aplikasi kamera dan apakah 0.6× bekerja pada kernel
   bawaan ROM yang sama (jika sudah diketahui; tidak perlu menghapus data).
2. Reproduksi freeze, lalu kumpulkan log sesegera mungkin melalui terminal
   dengan root. Log dapat memuat nama aplikasi, identitas, pesan atau data
   pribadi: **tinjau dan sensor dahulu sebelum mengirim**.

   ```sh
   su -c 'logcat -b all -d -v threadtime -t 3000 > /sdcard/Synthetica-camera-logcat.txt; dmesg | tail -n 2000 > /sdcard/Synthetica-camera-dmesg.txt'
   ```

3. Untuk mengukur SECCOMP, buka Manager dan Pengaturan terlebih dahulu, lalu
   jalankan perintah baca-saja ini. Ia membaca status setiap thread proses
   Manager dan aplikasi Pengaturan yang masih berjalan; nama proses/PID mungkin
   muncul dalam hasil. Jika tidak ada keluaran untuk satu aplikasi, prosesnya
   mungkin tidak sedang berjalan. Sensor data yang tidak ingin dibagikan.

   ```sh
   su -c 'for app in net.ember.labs com.android.settings; do echo "== $app =="; for p in $(pidof "$app"); do for s in /proc/"$p"/task/*/status; do [ -r "$s" ] && grep -E "^(Name|Pid|Seccomp):" "$s"; done; done; done'
   ```

   Jalankan sebelum dan sesudah percobaan kandidat jika memungkinkan. Nilai
   `Seccomp: 2` menunjukkan mode filter, bukan jaminan kualitas seluruh kebijakan
   filter atau keamanan root. Pengujian root perlu mencakup Manager dan `su`,
   serta memeriksa aplikasi berizin root tanpa mengungkap data pribadi.
