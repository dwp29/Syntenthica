# Synthetica 3.0-rc1: kandidat uji untuk joyeuse

**Status: kandidat, bukan rilis stabil.** Dokumen ini menjelaskan jalur baru
berbasis Synthetica 2.0 eksperimen yang dilaporkan boot oleh pengguna, bukan
build 3.0 lama yang dijelaskan di `SYNTHETICA-3.0.md`. Image 3.0-rc1 baru perlu
lulus build dan pengujian sintetis sebelum dibuat ZIP uji; hasil pada perangkat
belum ada. Jangan menganggap berkas bukti kompilasi sebagai ZIP flashable.

## Dasar dan batas bukti

Pengguna melaporkan eksperimen Neutron 2.0 boot pada joyeuse/Lunaris AOSP GMS
3.13 Android 16, terdeteksi di KernelSU Manager, dan fitur umumnya berfungsi.
Pengguna juga melaporkan `/sys/kernel/mm/lru_gen/enabled` bernilai `1`: MGLRU
aktif saat laporan tersebut dibuat. Ini adalah laporan untuk image eksperimen
sebelumnya, bukan pengujian image 3.0-rc1 yang baru.

Kamera **0.6× freeze** menurut pengguna, juga pernah terjadi pada beberapa
kernel lain. Tidak ada perubahan driver/HAL kamera atau klaim perbaikan kamera
pada kandidat ini. Nama dan versi aplikasi kamera, perilaku pada kernel bawaan
ROM, serta log saat freeze dibutuhkan sebelum menentukan penyebabnya.

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
Manager yang dipin mencari FD tersebut di `/proc/self/fd`. Patch 3.0-rc1 hanya
menghapus pematian filter pada cabang **Manager**; injeksi FD, pemeriksaan
identitas, serta jalur root tetap tidak diubah. Patch mempertahankan filter jika
ROM benar-benar memasangnya; patch tidak membuat filter jika belum ada, dan
tidak memalsukan tampilan Manager.

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
