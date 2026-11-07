# Synthetica Manager 3.0.0 — Cyberpunk Neon

## Ringkasan dan batas penting

Manager asli telah dibangun ulang dari source KernelSU-Next UAPI v4 dengan tema
neon. **APK Manager masih unsigned: tidak dapat dipasang sebelum ditandatangani
secara lokal dengan kunci Manager asli.** Repositori hanya memiliki sertifikat
publik, bukan private key-nya. Kunci itu tidak dapat dibuat kembali dari APK atau
sertifikat publik. Jangan menghapus Manager yang sekarang untuk mencoba paket
ini dan jangan mengirim password atau private key ke chat/repo.

- Package Manager: `net.ember.labs`; versionName `3.0.0`; versionCode `40000`.
- Sertifikat publik Manager yang dipin oleh build kernel Synthetica 2.0/3.0-rc1:
  SHA-256 `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`.
  Instalasi update juga memerlukan penandatangan yang diterima Android untuk APK
  yang **benar-benar** sedang terpasang; identitas di perangkat belum diverifikasi.
- [Unduh Manager 3.0.0 NEON — UNSIGNED](https://drive.google.com/file/d/1Lloc10XNWJLnKtYUofPaeTXIqfu0mvEu/view?usp=drivesdk)
  — 9.027.930 byte. SHA-256:
  `a6d0c1ff11130a56d66ae040786ca4060b29b55992643997b64fadebbb88ebea`.
- [Unduh APK PREVIEW — BUKAN MANAGER ROOT](https://drive.google.com/file/d/1ghGdJ31aFQMtL8f62RyKUGrEPkiBRbkA/view?usp=drivesdk)
  — 16.432.467 byte. SHA-256:
  `aab692aea781154d68a8cfaedeb7236674f6e033a979b6aa5420b81757993e48`.
  Preview punya package `net.ember.labs.neonpreview` dan tanda tangan debug
  terpisah, sehingga tidak memperbarui atau menggantikan Manager sebenarnya.
  Isinya hanya data contoh dan kontrol tampilan; ia tidak memiliki backend KSU,
  `ksud`, perintah root atau izin jaringan. Build preview lain bisa memiliki
  kunci debug berbeda dan mungkin memerlukan penghapusan *preview*, bukan Manager.

## Apa yang berubah

- Background grid bercahaya, panel/corner cyberpunk, tombol dan ikon baru,
  dashboard dengan kelompok akses cepat, serta dock empat tab dengan tab aktif
  bercahaya. Rute dan kontrol root/fitur yang ada dipertahankan.
- Logo baru, tema gelap/AMOLED, empat aksen (sian, merah muda, ungu, lime),
  indikator dan transisi. Animasi glow dan scan line dinyalakan secara default;
  bisa dimatikan di **Setelan → Personalisasi → Animasi neon**, dan mengikuti
  pengaturan animasi sistem. Animasi navigasi/transisi Android yang lain tetap
  mengikuti sistem. Accent dan pilihan animasi tersimpan di preferensi aplikasi.
- Status SECCOMP dibaca dengan `PR_GET_SECCOMP` pada **utas UI Manager**; angka
  filter/disabled bukan klaim tentang semua proses. Error ditampilkan sebagai
  tidak tersedia, bukan dipalsukan sebagai aktif. Ini tidak mengubah kebijakan
  keamanan dan bukan tes BPF.
- Tampilan versi menggunakan metadata APK; nama kernel yang aktif tetap dibaca
  dari perangkat dan tidak dipalsukan sebagai “Synthetica 3.0”.

## Verifikasi yang dilakukan

- [CI build Manager 42347623437](https://github.com/dwp29/Syntenthica/actions/runs/42347623437)
  berhasil dan menghasilkan **bytes dengan SHA-256 di atas**. Metadata package,
  versionName/code, alignment, dan kesamaan daftar permission dengan Manager 2.0
  diverifikasi. Run sebelumnya gagal karena penanda diagnostik debug dihapus oleh
  optimizer R8; kriteria yang tidak valid itu diperbaiki dan build diulang.
  File di Drive telah dicek ulang menggunakan SHA-256 dan ukurannya.
- Pintu statis memeriksa JNI mengembalikan UAPI 4, JNI dan `adbroot` identik
  dengan rujukan 2.0 setelah meniadakan ELF build ID, `libksud.so` identik,
  serta `main.jar` dan skrip update bawaan identik. Perbandingan source untuk
  fitur aplikasi menunjukkan perubahan hanya pada UI/resource/versi/branding.
- [CI preview 42347623465](https://github.com/dwp29/Syntenthica/actions/runs/42347623465)
  berhasil membangun dan memeriksa APK preview terpisah. [CI emulator 42348509076](https://github.com/dwp29/Syntenthica/actions/runs/42348509076)
  menjalankan preview itu pada Android API 35: navigasi ke Setelan berhasil;
  screenshot diperiksa untuk keterbacaan label aksen. Pilihan merah muda dan animasi dimatikan
  tersimpan setelah proses preview dihentikan dan dibuka ulang. Tes ini hanya
  menyentuh preview, bukan Manager atau akses root.
- Tes host repositori terakhir menjalankan 163 tes: 152 lulus, 11 di-skip
  (integrasi signing/QEMU dan fixture kandidat/kernel tertentu tidak disediakan
  dalam run host itu). [CI signing 42348375416](https://github.com/dwp29/Syntenthica/actions/runs/42348375416)
  secara terpisah menguji penolakan kunci yang salah dan mekanisme signing dengan
  kunci sementara; ini **bukan** kunci Manager asli.
- Belum ada pengujian Manager baru yang ditandatangani, proses update Android,
  komunikasi dengan kernel, `su`, modul, atau pengujian di HP pengguna. Hasil
  statis/preview tidak membuktikan fungsi root berjalan.

## Jika kunci asli masih dimiliki

Jalankan hanya pada komputer yang menyimpan private keystore asli. Tool berikut
meminta password secara interaktif, tidak menerima password sebagai argumen,
memeriksa hash unsigned, metadata, UAPI, dan sertifikat sebelum/sesudah signing,
serta menolak file output yang sudah ada. Ini tidak memasang APK otomatis.

```sh
python3 build-kit/scripts/sign_neon_manager_locally.py \
  --apk /path/Synthetica-Manager-3.0.0-Neon-UNSIGNED.apk \
  --expected-sha256 a6d0c1ff11130a56d66ae040786ca4060b29b55992643997b64fadebbb88ebea \
  --keystore /path/keystore-asli.p12 \
  --alias ALIAS_KUNCI_ASLI \
  --build-tools "$ANDROID_SDK_ROOT/build-tools/36.1.0" \
  --out /path/Synthetica-Manager-3.0.0-Neon-SIGNED.apk
```

Butuh JDK `keytool` dan Android SDK build-tools. Jika private key asli sudah
hilang, APK tidak dapat di-update dengan identitas itu. Solusi identitas baru
memerlukan proses terpisah dan persetujuan eksplisit: penandatangan baru,
perubahan kernel agar mempercayainya, serta kemungkinan perlu menghapus Manager
lama dan kehilangan data/akses; tidak dilakukan otomatis di sini.

## Source dan reproduksi

Source dan lisensi: `KernelSU-Next/KernelSU-Next@ea51427ff700f73909e7e8c8717cc3241322ee1e`
(GPL-3.0); overlay di `build-kit/ci/ksun-neon/`, builder di
`build-kit/scripts/build_manager_30_neon.py`, dan preview terisolasi di
`build-kit/ci/neon-preview/`. CI membutuhkan JDK 21, Android SDK 36, NDK 29 dan
CMake 3.22.1. Tidak ada private key di dalam APK unsigned maupun repositori.

### Mengulang uji CI

Build Manager dan preview masing-masing menyediakan `workflow_dispatch`. Setelah
menjalankan build, catat run ID dan SHA-256 APK dari hasil CI. Jalankan workflow
`synthetica30-preview-emulator.yml` untuk menguji preview, atau
`synthetica30-neon-signing-tests.yml` untuk tes signing dengan **kunci sementara**,
dengan memasukkan run ID dan SHA-256 yang sesuai. Artifact build Actions disimpan
14 hari; jalankan build baru jika artifact telah kedaluwarsa. Emulator memerlukan
KVM; workflow akan gagal jika akselerasi tidak tersedia, bukan menganggap tes
berhasil. Kedua workflow ini tidak menggunakan kunci Manager asli.
