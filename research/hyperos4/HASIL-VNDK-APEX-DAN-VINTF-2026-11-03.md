# Hasil lanjutan VNDK 30, APEX dan VINTF — joyeuse

**Tanggal:** 3 November 2026. **Status: kandidat 03 tetap HOLD / JANGAN FLASH.** Ini pemeriksaan host, bukan bukti kandidat boot pada ponsel. Tidak ada perubahan image, policy, perangkat, atau pengaturan keamanan pada pemeriksaan ini.

## Hasil yang mengubah arah pencarian

Kandidat ternyata **sudah memiliki** `/system_ext/apex/com.android.vndk.v30.apex`. Karena super image kandidat 02 dan 03 identik, pengamatan read-only atas extent 02 juga berlaku untuk isi super 03. Nama dan ukuran paket: **114.769.920 byte**, SHA-256 `bd9fd612ddf6e42431ee0ebd680bd306505bc5abc1cf5afef5b0ba09af0089b3`. Properti yang dibaca dari vendor menyatakan `ro.vndk.version=30`; ini tidak membuktikan nilai runtime pada perangkat.

- Manifest APEX luar dan dalam identik byte-per-byte dan menyebut `com.android.vndk.v30`, versi paket `1`. Payload adalah ext4; 286 file dengan nama library dan header ELF dasar yang sesuai ARM 32-bit ditemukan di `/lib`, serta 286 yang sesuai AArch64 64-bit di `/lib64`.
- Dari **386 pasangan bitness/nama dependency langsung** pada 194 executable vendor yang diparsing, **127 pasangan** memiliki nama dan header ELF dasar yang cocok di dua root APEX ini. Angka ini bukan penilaian semua dependency: pasangan lain dapat berasal dari vendor, system, APEX lain, symlink, atau lokasi yang tidak diperiksa. Kecocokan nama/header **bukan bukti kompatibilitas simbol, versi ABI, resolusi namespace, atau fungsi runtime**.
- Kunci publik dalam footer vbmeta payload identik dengan `apex_pubkey` paket. Pada [run 41554835306](https://github.com/dwp29/Syntenthica/actions/runs/41554835306), verifier AOSP terisolasi berhasil memeriksa **tanda tangan vbmeta payload dan hashtree SHA-256 menggunakan kunci yang tertanam**. Empat kontrol sintetis lulus: payload sah diterima; payload rusak, tanda tangan rusak, dan payload tanpa tanda tangan ditolak.
- Verifikasi tersebut membuktikan **konsistensi internal terhadap kunci yang dibawa paket**, bukan siapa penandatangannya atau bahwa kuncinya dipercaya perangkat. Tanda tangan APK/APEX luar, rantai AVB/vbmeta perangkat, aktivasi APEX, anti-rollback, linker dan boot **belum diverifikasi**. Tidak ada kunci privat atau output policy yang dikemas.

Jadi, mencari dan menyisipkan donor VNDK 30 bukan langkah pertama: paket yang perlu diteliti sudah ada. Keberadaannya tetap bukan bukti bahwa ia kompatibel dan aktif saat boot.

## Uji hipotesis VINTF — salinan sementara saja

[Run 41490124807](https://github.com/dwp29/Syntenthica/actions/runs/41490124807), kemudian diulang oleh run 41554835306, memeriksa snapshot parsial dengan `checkvintf` AOSP. Seluruh salinan XML dipulihkan dan hash input/kandidat tetap cocok.

| Snapshot | Hasil dan batas |
|---|---|
| Asli | Exit **65 / INCOMPATIBLE**; dilaporkan sepolicy vendor `30.0` tidak memenuhi matriks, dan matriks target FCM 4 tidak ditemukan. |
| VINTF sepolicy `30.0 → 31.0` saja | Exit **65 / INCOMPATIBLE**; diagnostik sepolicy tersebut tidak lagi muncul, tetapi VNDK 30 yang diminta device tidak didukung oleh deklarasi framework yang terbaca (`34`), dan matriks tepat FCM 4 tetap tidak ditemukan. |
| Sejumlah dua hipotesis sekaligus: sepolicy `31.0` dan deklarasi framework VNDK `30` | Exit **70 / tool_error_or_incomplete_input**; diagnostik spesifik sepolicy dan VNDK di atas tidak muncul pada run ini, tetapi tool tetap melaporkan matriks tepat FCM 4 tidak ditemukan. **Ini bukan COMPATIBLE maupun bukti kedua perubahan benar.** |

FCM 4 ada sebagai sumber lama AOSP, tetapi [AOSP kemudian menghapus matriks Android Q](https://github.com/aosp-mirror-neo/platform_hardware_interfaces/commit/7ad5797272c40c2b83b0df5a57a0f248a210091b) setelah device downstream beralih ke target FCM yang lebih baru. Berkas XML sumber [dibangun bersama konfigurasi kernel](https://github.com/aosp-mirror-neo/platform_hardware_interfaces/blob/b0d52ce9546a9d42da12bf24a6deecb1b5fa4c79/compatibility_matrices/Android.bp); menyalinnya atau memalsukan angka target tidak membuktikan framework modern mendukung HAL/kernel lama. Tidak ada FCM atau deklarasi ini yang dimasukkan ke image.

Snapshot belum memuat seluruh ODM/SKU/APEX dan keadaan kernel; hasilnya tidak dapat menetapkan apakah ROM sebenarnya gagal atau berhasil boot.

## Policy dan tindakan berikut

Mode strict `secilc` pada run sebelumnya keluar **255** dengan **290 catatan kegagalan** `neverallow`; mode pembanding `-N` AOSP keluar `0` dengan melewati assertion **waktu kompilasi**, bukan mematikan enforcement. Mode itu tidak membuktikan enforcement, jalur init atau boot pada ROM ini. Rincian dan batas: [laporan policy sebelumnya](https://drive.google.com/file/d/1wD7zLHkQHHjLx9QkCTsXGCGO6AZcDWvf/view).

Langkah substantif adalah membuktikan kombinasi framework/vendor/policy dan implementasi HAL untuk joyeuse, termasuk dukungan FCM yang sah dan kompatibilitas ABI/namespace; cocokkan juga trust APEX luar, recovery, AVB/vbmeta dan rollback. **Source tree/build manifest port asli** atau log boot yang sudah ada dari port asal dapat membantu menentukan kombinasi sebenarnya, tanpa meminta flash kandidat. Kunci privat tidak boleh dikirim ke chat atau dikomit ke repositori. Belum ada dasar membuat kandidat 04 dengan angka deklarasi saja atau menambahkan donor yang tidak diketahui asalnya.

## Bukti dan sumber

- Hasil inventaris awal: `HASIL-VNDK-RUN-41488406818-2026-11-02.json`; isi APEX dan dua hipotesis: `HASIL-APEX-VNDK-RUN-41490124807-2026-11-03.json`.
- Verifikasi internal AVB, kontrol sintetis dan snapshot: `HASIL-AVB-APEX-RUN-41554835306-2026-11-03.json`, [check 125652494568](https://github.com/dwp29/Syntenthica/runs/125652494568).
- AOSP mendefinisikan modul [VNDK v30 untuk system_ext](https://github.com/aosp-mirror-neo/platform_packages_modules_vndk/blob/18c78f8c11a1487e9dfa7a87612b839edefd1ccf/apex/Android.bp), dan [mendokumentasikan snapshot VNDK](https://source.android.com/docs/core/architecture/vndk/snapshot-generate). Ini referensi umum, bukan bukti bahwa image HyperOS berasal dari source itu.
- Source device Lineage untuk miatoll dan blob referensi stock joyeuse bukan bukti donor tersebut cocok dengan framework HyperOS kandidat. Tidak ada binary GSI/community yang diunduh atau disisipkan pada pekerjaan ini.

**Kesimpulan:** pekerjaan host telah maju, tetapi ROM belum selesai dan kandidat 03 tetap **HOLD / JANGAN FLASH**. Tidak ada klaim sukses boot, perangkat tidak disentuh, dan kandidat lama serta sumber dipertahankan.
