# Ringkasan akhir uji host Syntenthica boot-first

**Tanggal:** 2 November 2026. **Status:** dua tahap uji host yang direncanakan selesai; kandidat kedua tetap **HOLD, belum layak diperlakukan sebagai paket aman untuk flash**. Tidak ada uji perangkat atau bukti boot. Hasil host bukan vonis bahwa ROM pasti gagal maupun pasti berhasil di perangkat.

## Keputusan

Pertahankan sumber, kandidat pertama, kandidat kedua dan backup. Jangan flash atau wipe, jangan ubah image/perangkat dan jangan melemahkan SELinux atau AVB. Modul Magisk/KSU, penggantian kernel/Manager, fitur dan optimasi tetap **hold**. Tindakan pada perangkat atau perubahan di luar persetujuan awal bukan bagian audit ini dan memerlukan persetujuan tersendiri.

Alasan hold adalah gabungan temuan snapshot VINTF yang belum cocok, paket hasil repack tanpa footer tanda tangan whole-file OTA yang terdeteksi, dua offset metadata OTA yang tidak cocok, serta keadaan AVB, rollback, recovery, enkripsi dan boot perangkat yang belum diukur. Ini bukan perintah untuk menonaktifkan pemeriksaan keamanan.

## Tahap 1 — dependensi vendor dan linker

[Run 41466512890](https://github.com/dwp29/Syntenthica/actions/runs/41466512890) membaca `DT_NEEDED` dari **194 executable vendor ARM/AArch64** yang terlihat sebagai file reguler dengan interpreter yang dikenali: seluruh 194 terbaca, tanpa kesalahan parser atau nama dependency yang ditolak. Ada symlink vendor yang tidak diikuti; static executable tanpa `PT_INTERP` dan lokasi lain bukan cakupan perbandingan ini.

Dibandingkan hanya dengan nama dan header dasar ELF pada direktori `lib`/`lib64` langsung di system, system_ext, vendor dan product:

| Kategori pasangan nama library + bitness | Jumlah | Arti yang dibenarkan |
|---|---:|---|
| Nama dan header ARM/AArch64 `ET_DYN` yang sesuai terlihat | 344 | Hanya kecocokan nama dan header dasar; **bukan** bukti versi simbol atau ABI cocok. |
| Hanya nama symlink terlihat | 6 | Target symlink tidak diikuti dalam perbandingan ini, termasuk nama `libc.so`, `libdl.so`, `libm.so` untuk 32/64-bit. |
| Tidak terlihat di direktori terpilih | 36 | Bukan bukti library hilang: APEX aktif, ODM, subdirektori vendor dan namespace linker tidak diselesaikan. |

Header ELF terpisah menunjukkan 11 executable ARM 32-bit dan 183 AArch64 64-bit dengan interpreter yang dikenali, serta satu ARM 32-bit tanpa `PT_INTERP`. Pada [run 41463290011](https://github.com/dwp29/Syntenthica/actions/runs/41463290011), payload EROFS runtime APEX diperiksa sebagai data dengan tool host AOSP terisolasi: file linker ARM 32-bit dan AArch64 64-bit sama-sama ada **di dalam paket**. Ini tidak membuktikan paket aktif, kernel mendukung 32-bit, simbol library cocok atau service berjalan. Tanda tangan APEX belum diverifikasi.

## Tahap 2 — integritas paket dan batas keamanan

- ZIP kandidat kedua berukuran **4.713.790.039 byte**, SHA-256 `395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372`, tetap sama sebelum/sesudah. `super.img` dibaca sampai EOF dengan CRC dan SHA-256 cocok; empat salinan extent dan identitas 67 XML cocok sebelum/sesudah. Pemeriksaan menjaga hanya metadata, bukan image ROM.
- `boot.img` dan `dtbo.img` dibaca sampai EOF, CRC ZIP dan SHA-256 masing-masing cocok baseline: `57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d` dan `9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2`.
- Tidak terlihat footer AVB kanonis pada akhir kedua image, dan tidak ada entri `vbmeta*.img` dalam ZIP. Ini **tidak** menyingkirkan vbmeta/deskriptor terpisah yang sudah berada pada perangkat dan bukan bukti AVB dinonaktifkan.
- Komentar ZIP panjangnya 0 sehingga footer tanda tangan whole-file OTA standar tidak terlihat. `otacert` di dalam arsip bukan bukti ZIP hasil repack ditandatangani atau diterima recovery. Offset yang dinyatakan untuk `metadata` dan `metadata.pb` keduanya tidak cocok dengan lokasi aktual.
- Ukuran partisi fisik unit pengguna, status AVB/enforcement, rollback index, firmware, FBE/dekripsi, kebijakan verifikasi OrangeFox dan penerimaan ZIP64 belum diukur. Ponsel tidak diakses.

## Pemeriksaan VINTF dan batas lainnya

Tool host `checkvintf` AOSP dari build `16644040` telah lulus kontrol sintetis kompatibel, inkompatibel dan XML rusak. Untuk dua skenario snapshot parsial kandidat, tool mengembalikan **exit 65 / INCOMPATIBLE**; diagnostiknya menyebut tidak menemukan matriks tepat FCM **4** dan sepolicy manifest **30.0** tidak memenuhi matriks framework yang disediakan. Skenario first API 30 adalah hipotetis. Ini temuan pada input terbatas, bukan bukti boot gagal pada perangkat: ODM aktual, SKU, APEX aktif, properti boot dan kernel runtime tidak tercakup penuh.

Field lain `plat_sepolicy_vers.txt` vendor bernilai **31.0** dan file mapping `31.0.cil` terlihat pada tiga partisi. Field ini berbeda dari sepolicy **30.0** pada manifest VINTF. Tiga pasangan isi digest policy platform/vendor yang dibaca berbeda; pemilihan serta pemuatan policy sebenarnya belum diketahui. Cmdline boot warisan memuat permintaan SELinux permissive, tetapi status runtime belum diuji dan tidak ada perubahan untuk melemahkan keamanan.

Installer guard berhenti pada kegagalan yang diuji di host dengan target palsu; ia tidak membatalkan penulisan sebelumnya dan tidak membuktikan perilaku OrangeFox pada perangkat. Kamera, audio, radio, Bluetooth, NFC, fingerprint, kernel/modul dan Manager belum terbukti berfungsi hanya dari deklarasi atau header.

## Validasi dan penyimpanan

- **76 tes regresi host lulus lokal** pada sepuluh kelompok; workflow akhir selesai sukses. Tiga kontrol checkvintf dan dua kontrol EROFS juga memperoleh hasil yang diharapkan sebelum kandidat dibaca. Status sukses workflow berarti audit selesai, bukan kandidat lulus kompatibilitas.
- Tool resmi host dipin oleh hash dari `otatools.zip` Android CI build `16644040`; digest cocok dengan subject pernyataan build yang pernah diperiksa, tetapi tanda tangan pernyataan belum diverifikasi. Pada run pemeriksaan akhir ini tidak ada executable ROM yang dijalankan; pada audit updater sebelumnya binary updater diuji secara terisolasi dengan target palsu.
- Metadata lengkap audit akhir: `HASIL-AUDIT-AKHIR-HOST-RUN-41466512890-2026-11-02.json`, SHA-256 `0f2ca520007b37cd3f0bc7c00b51ff21e02de7b1d434049d5063ccaa1f782ca5`. Rincian VINTF/SELinux: `AUDIT-CHECKVINTF-PARSIAL-SELINUX-2026-11-02.md`; rincian ELF/APEX: `AUDIT-ELF-VENDOR-LINKER-2026-11-02.md`.
- JSON detail init yang pernah diblokir provider tidak dikirim ulang, dimodifikasi untuk menghindari filter, atau dialihkan ke layanan lain.
