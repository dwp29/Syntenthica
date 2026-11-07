# Synthetica 3.0 — kandidat perbaikan root Manager

**Kandidat uji, bukan rilis stabil.** Pengguna melaporkan 3.0-rc1 boot tetapi
Manager 2.1.2 menampilkan `Failed to grant root`. Perubahan di sini menargetkan
satu kemungkinan penyebab; belum ada bukti bahwa itu penyebab di perangkat,
dan image ini belum diuji secara fisik. `uname -r` yang diharapkan adalah
`4.14.357-openela-synthetica-3.0`; nama ZIP adalah `synthetica-3.0.zip`.

## Kandidat dan bukti pengujian

- [Unduh synthetica-3.0.zip](https://drive.google.com/file/d/1tKKHqM3gclN-0ZnT7b6_Wrxtxj-sjvNd/view?usp=drivesdk)
  — 15.719.303 byte; SHA-256 ZIP
  `16b32f57381005c08cbee0ec684397dc91acc77f5b2ccbb4ef7f4b99a9a791e6`.
- SHA-256 `Image.gz`:
  `92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb`.
- Sertifikat modul publik SHA-256:
  `fccecddc68e8828ff42c59be08f3aca01baf1f07e9caf8369ce69e8fad4bd062`.
- [Run build 42354153045](https://github.com/dwp29/Syntenthica/actions/runs/42354153045)
  berhasil mengompilasi kernel, memeriksa konfigurasi, source, object, identity
  dan modul, serta mengemas ZIP. **Run keseluruhan gagal** karena tes sintetis
  pertama timeout setelah 75 detik; penyebab timeout belum diketahui.
- [Run terisolasi 42355147656](https://github.com/dwp29/Syntenthica/actions/runs/42355147656)
  memverifikasi SHA ZIP yang sama, kemudian lulus lima tes repack/penolakan
  ARM/QEMU dan tes writer sebenarnya pada boot sintetis berbasis loop. Tidak
  ada perangkat fisik yang diuji. Host suite lokal: 177 tes, 17 dilewati;
  pengujian packaging kandidat nyata juga lulus secara terpisah.

## Root dan SECCOMP

Pada source kernel yang dipin, fd driver Manager memakai `O_CLOEXEC`. Source
Manager/ksud yang dipin menjalankan helper `libksud.so debug su` di proses
baru; helper memindai fd driver dan, jika tidak ada, mencoba syscall `reboot`
khusus KernelSU. Filter SECCOMP Android tertentu dapat memblokir syscall itu.
Kombinasi ini menjelaskan kemungkinan kegagalan setelah patch rc1 yang
mempertahankan filter, tetapi filter ROM, hash APK terpasang, output helper,
dan penyebab kegagalan sebenarnya **belum diverifikasi**.

Patch `build-kit/ci/synthetica3-root/0001-manager-fd-after-exec.patch` memasang
fd driver **biasa**, bukan fd su-session, setelah `exec` berhasil dan hanya
untuk UID Manager yang dikenali saat path berakhir `/libksud.so`. Fd baru tetap
`O_CLOEXEC` dan otorisasi ioctl tetap berlaku. Patch tidak mengubah aturan BPF,
mematikan SECCOMP Manager, mematikan SELinux, atau memperluas daftar root.
Seperti sebelumnya, root-profile tetap dapat mematikan filter setelah
eskalasi root; kandidat ini bukan perubahan SECCOMP global. Hasil aktual tetap
bergantung pada identitas Manager, kebijakan ROM, dan jalur executable nyata.

Source legacy juga memiliki urutan pemasangan fd su-session sebelum pemeriksaan
`su` dan sebelum `exec`, walaupun fd itu `O_CLOEXEC`. Masalah terpisah ini
tidak diklaim sebagai penyebab screenshot dan tidak diubah di kandidat ini;
membuat fd su-session inheritable tanpa audit lebih lanjut bisa membocorkan
kapabilitas ioctl.

Tes host menjalankan fungsi patch sesungguhnya dengan stub identitas/fd,
memeriksa penolakan UID/path dan kegagalan alokasi, serta menjalankan `exec`,
`FD_CLOEXEC` dan filter BPF SECCOMP nyata di Linux host dengan driver palsu.
Tes itu **bukan** pengujian ioctl KernelSU, root, Android, atau kernel perangkat.

## Installer dan keselamatan

Installer menampilkan logo teks, tahapan singkat dan progress. Penolakan,
peringatan belum diverifikasinya AVB/modul, serta instruksi **jangan reboot**
jika write/readback gagal tetap ditampilkan. Pemeriksaan device, slot,
bootloader, partisi, hash, DTB, ramdisk, repack, AVB bytes dan readback tetap
ada. Pemeriksaan bytes AVB **bukan** verifikasi validitas signature.

Sebelum flash: pastikan perangkat/ROM yang ditargetkan cocok, bootloader
terbuka, recovery dapat diakses, dan **backup boot yang tepat** tersimpan
terpisah serta diketahui cara restore-nya. Tidak ada backup atau reboot otomatis.
Jika gagal saat menulis atau verifikasi, jangan reboot; pulihkan boot dari
recovery. Jika bootloop, pulihkan boot yang sama. Tidak perlu wipe data dan
jangan ubah vbmeta untuk memaksa boot. Kepercayaan AVB dan modul ROM tetap
belum diverifikasi; sertifikat modul build baru berbeda dari build lama.

Kamera 0.6× sebelumnya dilaporkan freeze; kandidat ini tidak berisi perubahan
atau klaim perbaikan kamera. Installer hanya menulis boot, bukan vbmeta, dtbo,
vendor, system, userdata, ksud atau modul.

## Kunci Manager

`release/MANAGER.json` mencatat kunci lokal lama sebagai
`secretkey/synthetica-2.0.p12`, alias `synthetica`, dan mencatat salinan itu
sudah dimusnahkan. Direktori tersebut disebut dalam dokumen paket source lama,
tetapi tidak ada dalam checkout saat ini. Arsip sumber 2.1 yang tersedia di
Drive mungkin memiliki salinan; isi arsip belum diperiksa. Periksa arsip secara
privat. Jangan mengunggah private key atau password ke chat/GitHub; sertifikat
publik tidak bisa merekonstruksi private key.

## Reproduksi

- Builder: `build-kit/scripts/build_synthetica3_root.py`; mewarisi input/guard
  rc1, source/kernel/toolchain yang dipin, dan membandingkan konfigurasi
  eksperimen yang dilaporkan boot, hanya mengizinkan perubahan `LOCALVERSION`.
- Packager: `build-kit/scripts/package_synthetica3_root.py`; memakai payload
  `prepare-boot.sh` yang dipin dan memeriksa image serta bukti kompilasi.
- Workflow: `.github/workflows/synthetica3-root.yml`. Hasil sintetik atau
  kompilasi saja bukan bukti boot, root, recovery, modul, kamera atau AVB di
  perangkat. Rincian identitas kandidat harus diperiksa dari hasil run spesifik.
