# Audit VINTF boot-first: system dan vendor

**Tanggal:** 2 November 2026. **Status:** inventaris baca-saja di host; belum ada uji perangkat dan belum ada kesimpulan kompatibilitas atau bukti boot.

**Pembaruan:** setelah inventaris ini, [audit checkvintf parsial](https://drive.google.com/file/d/1XIVMCiRAzKnQ0sMFtW40aNY6FTefGm5t/view) selesai pada [run 41456952143](https://github.com/dwp29/Syntenthica/actions/runs/41456952143). Tool melaporkan `INCOMPATIBLE` untuk dua skenario snapshot parsial, termasuk diagnostik FCM 4 dan sepolicy 30.0. Ini bukan vonis pada perangkat atau bukti gagal boot; keberhasilan workflow berarti pemeriksaan selesai, bukan kandidat lolos.

## Ringkasan

Audit atas kandidat kedua menemukan bahwa manifest vendor utama menyatakan **target FCM 4**, sedangkan matriks framework yang berlabel tingkat dan terlihat pada empat partisi yang diperiksa menyatakan **7, 8, 202404, 202504 dan 202604**. Tidak terlihat matriks berlabel eksplisit 4 di lokasi yang dibaca. Ini **petunjuk yang perlu diselidiki, bukan bukti bahwa ROM pasti gagal boot**.

Ada dua matriks framework tanpa label tingkat: satu di system dan satu di product. Source AOSP yang diperiksa dapat menggabungkan matriks tanpa label pada tingkat target perangkat dan memasukkan informasi dari tingkat lebih tinggi sebagai opsional. Implementasi serta sumber input runtime ROM ini belum dibuktikan sama dengan source referensi tersebut. Pemeriksaan `checkvintf` host parsial kemudian dijalankan; hasil dan batasannya dicatat pada pembaruan di atas. [1](https://source.android.com/docs/core/architecture/vintf/match-rules) [2](https://android.googlesource.com/platform/system/libvintf/+/a1ff1e5a0835fd2cfe4c904efc6da5274b8824c1/CompatibilityMatrix.cpp)

## Identitas dan cara pemeriksaan

- [Run GitHub 41449702558](https://github.com/dwp29/Syntenthica/actions/runs/41449702558) **berhasil** pada salinan sementara kandidat kedua, yang disusun dari tiga bagian draf terpisah. Ukuran dan SHA-256 setiap bagian serta ZIP gabungan diperiksa; SHA-256 ZIP sebelum dan sesudah tetap `395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372`.
- Isi `super.img` dibaca sampai akhir dalam dua lintasan; CRC ZIP dan SHA-256 `3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673` cocok pada keduanya. Metadata logical-partition dan hash empat salinan extent yang diperiksa cocok sebelum dan sesudah pembacaan.
- `vendor`, `system_ext` dan `product` cocok dengan hash extent sumber yang sudah terkunci. Extent `system` adalah versi kandidat dengan file identitas yang telah disetujui; hash-nya cocok dengan kandidat pertama. Salinan extent sementara dibaca tanpa mount, dan tidak ada image input yang diubah atau diunggah.
- **67 berkas XML** pada direktori VINTF yang terlihat diinventarisasi: 19 system, 11 system_ext, 2 product dan 35 vendor. Lokasi `/odm/etc/vintf` di dalam salinan vendor tidak ditemukan atau tidak dapat dibaca; ini **bukan** pernyataan bahwa semua sumber ODM runtime telah diperiksa.
- Sebanyak **37 tes host** pada tiga kelompok lulus dalam run yang sama, termasuk uji filesystem dan ZIP sintetis. Sebelumnya [run 41449006892](https://github.com/dwp29/Syntenthica/actions/runs/41449006892) juga menyelesaikan inventaris baca-saja. Hasil terstruktur hanya memuat metadata deklarasi dan hash, bukan image atau isi XML mentah.

## Temuan terpilih

| Pengamatan statis | Arti dan batas |
|---|---|
| Manifest vendor utama bertarget FCM 4 | Hash manifest cocok dengan hasil audit sumber sebelumnya. Tingkat ini bukan versi Android runtime yang terukur. |
| Matriks berlabel di system: 7, 8, 202404, 202504, 202604 | Tidak ditemukan label 4 dalam direktori empat partisi yang dibaca. Pemilihan file, properti SKU, ODM, APEX dan implementasi aktual dapat memengaruhi hasil. |
| Matriks tanpa label ada di system dan product | Jangan menyimpulkan kegagalan hanya dari tidak adanya file berlabel 4; penggabungan matriks harus diuji dengan implementasi VINTF yang sesuai. |
| Matriks system tanpa label memuat entri NFC AIDL dan NFC HIDL | Nama dan format NFC HIDL terlihat pada manifest vendor utama; deklarasi NFC AIDL tidak terlihat pada berkas manifest vendor yang diinventarisasi. Ini **bukan** bukti NFC atau boot gagal: sumber runtime lain dan aturan pencocokan lengkap belum diperiksa. |
| Entri radio HIDL pada matriks juga memiliki nama dan format yang terlihat di manifest vendor | Pencarian ini hanya membandingkan nama dan format, bukan versi, semua instance, status layanan, atau kesesuaian formal. |
| Manifest/fragmen vendor memuat deklarasi contoh audio HIDL 6.0, camera provider HIDL 2.4, health HIDL 2.1, fingerprint HIDL 2.1 serta power AIDL | Deklarasi atau keberadaan file tidak membuktikan layanan, sensor, kamera, audio atau fitur lain berfungsi. |

## Hal yang belum dibuktikan

Pemeriksaan ini tidak menggabungkan seluruh persyaratan HAL secara formal, tidak memeriksa seluruh sumber APEX/ODM atau override SKU runtime, dan tidak menguji ABI library, kernel, AVB, rollback, enkripsi, penerimaan ZIP oleh OrangeFox, atau boot. Hasil inventaris tidak menjelaskan dengan pasti penyebab fastboot pada artefak lain yang sebelumnya dicoba pengguna.

Pengguna menyatakan recovery dan backup aman dan recovery pernah berhasil dipakai flash; keterangan itu diterima. Sumber, kedua kandidat dan backup tetap dipertahankan. Tidak dilakukan flash, wipe, format, penggantian recovery/firmware, perubahan image atau pelemahan keamanan. Semua modul Magisk/KSU tetap **hold**, dan fitur/optimasi menunggu bukti boot dasar.

## Penyimpanan dan langkah aman berikutnya

Rincian hasil inventaris: `HASIL-INVENTARIS-VINTF-KANDIDAT-02-2026-11-02.json`; hasil inventaris awal: `HASIL-INVENTARIS-VINTF-RUN-41449006892-2026-11-02.json`. Keduanya hanya data hasil pemeriksaan, bukan paket ROM.

Koreksi penyimpanan sesi sebelumnya: JSON rincian analisis init SELinux sempat tersedia lokal tetapi tidak bertahan saat lingkungan kerja dipulihkan. Provider konektor telah memblokir pengunggahannya; jangan mengirim ulang atau mengubah kontennya untuk melewati filter. [Ringkasan audit AVB/SELinux tetap tersedia di Drive](https://drive.google.com/file/d/14FqxFcc3wu6TXqeN5k8QMQOaw4Zmirhf/view).

Langkah berikutnya adalah menindaklanjuti hasil checkvintf parsial tanpa menganggap sumber runtime yang hilang telah diketahui, lalu menilai AVB, enkripsi serta hambatan boot lainnya. Tindakan pada perangkat atau perubahan di luar persetujuan awal tetap memerlukan keputusan spesifik terpisah.
