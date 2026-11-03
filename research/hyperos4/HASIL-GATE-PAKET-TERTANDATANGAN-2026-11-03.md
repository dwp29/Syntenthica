# Gate paket OTA tertandatangani — 3 November 2026

**Status ROM: HOLD / JANGAN FLASH.** Pekerjaan ini menambah pemeriksaan host; tidak ada kandidat 04, image baru, signing produksi, flash, wipe, perubahan recovery atau uji perangkat.

## Mengapa gate gabungan diperlukan

Kandidat 03 sudah memiliki offset OTA yang cocok pada ZIP **yang belum ditandatangani**, tetapi penandatangan dapat menyusun ulang anggota ZIP. Karena itu signature yang valid tidak membuktikan offset yang sebelumnya benar masih menunjuk ke byte yang benar pada file akhir.

`synthetica-project/audit_signed_ota.py` memeriksa, pada ZIP final yang sama:

1. Signature whole-file terhadap **sertifikat publik dan SHA-256 SPKI yang dipasok secara independen**, serta SHA-256 ZIP signed yang dipin. Sertifikat tertanam tidak digunakan untuk menetapkan trust.
2. ZIP referensi pra-signing juga harus sesuai pin SHA-256 yang dipasok. Nama anggota reguler harus sama; seluruh anggota selain dua metadata dan `otacert` dibandingkan **byte tak terkompresi** sampai EOF dan CRC diperiksa. Ini mencakup `super.img`, `boot.img`, `dtbo.img`, updater dan script.
3. `metadata` dan `metadata.pb` harus konsisten, field selain properti tetap semantik sama, dan setiap offset/ukuran `property-files` harus cocok dengan local header, penyimpanan `STORED`, ukuran, dan pembacaan byte langsung di **ZIP signed**.
4. Public key `otacert` dalam ZIP signed harus cocok dengan pin signer yang diberikan. Ini adalah pemeriksaan konsistensi, **bukan** bukti bahwa recovery mempercayai key tersebut. ZIP duplikat, nama/path berbahaya, symlink dan format di luar cakupan ditolak.

Alat hanya membaca dan mengalirkan ZIP; ia tidak membutuhkan private key dan tidak menandatangani atau menjalankan isi ZIP. Harus disediakan sertifikat publik, pin ZIP referensi, pin ZIP final dan pin public key yang asal serta kepercayaannya ditentukan secara terpisah. Pembacaan ulang file final secara penuh memang disengaja untuk mengikat pemeriksaan signature dan isi pada identitas byte yang sama.

## Hasil kontrol

[Run 41568878053](https://github.com/dwp29/Syntenthica/actions/runs/41568878053), commit `67a39a90cb7b2934131ce269f2cc6dfd746b408b`, selesai sukses. Workflow **mengharuskan sedikitnya 55 tes sintetis/regresi dan dua tes interop SignApk benar-benar berjalan tanpa skip**:

- Pada ZIP **sintetis kecil**, SignApk AOSP membuat signature yang diterima verifier terhadap public key sementara, tetapi menyusun ulang layout sehingga offset yang berasal dari ZIP pra-signing tidak lagi benar. Gate gabungan menolak paket tersebut walaupun signature valid.
- Kontrol kedua menyesuaikan properti dengan layout awal SignApk lalu menandatangani kembali **hanya fixture sintetis**, dan gate memeriksa ulang ZIP final: signature, offset dan isi yang dibandingkan cocok. Ini demonstrasi kontrol, bukan resep signing atau bukti bahwa operasi dua putaran akan aman untuk ROM nyata.
- Kontrol lain menolak metadata stale, isi image berubah, tambahan anggota, key atau pin salah, `otacert` berbeda, perubahan selama audit, property-file terkompresi, field non-property berubah dan ZIP dengan nama duplikat/tidak aman. Ada ZIP64 **sintetis kecil**, bukan uji ZIP64 nyata lebih dari 4 GB.
- Audit signature host kini juga menolak FIFO tanpa menunggu penulis, diuji dengan timeout. SignApk/JNI diambil dari `otatools.zip` Android CI build 16644040 yang dipin SHA-256 `bc85557aa0c59a7d0b48b8175250948d67b2d0f293bd74eb8d5753ba4ad7781f`; pin hash bukan bukti tanda tangan provenance.

Regresi lokal mengumpulkan **336 tes**, dengan **4 skip**: dua interop SignApk yang terpisah lulus di CI di atas, dan dua kontrol opsional edify/QEMU yang tidak memiliki dependensi lokal. Hasil run dan langkahnya tersimpan dalam `HASIL-GATE-PAKET-TERTANDATANGAN-RUN-41568878053-2026-11-03.json`. Pengunduhan log mentah GitHub ke lingkungan ini gagal `EOF`; kesimpulan run/step diperoleh melalui metadata API dan workflow pada commit tersebut secara eksplisit menggagalkan kedua tes interop jika salah satunya skip.

## Batas dan keputusan

- Gate **belum dijalankan pada ZIP ROM signed yang nyata**. Kandidat 03 sendiri masih memiliki komentar ZIP 0 byte dan tidak ditandatangani resep; verifikasi ulang offset pada sebuah ZIP final belum terjadi karena ZIP final signed belum ada.
- Perbandingan anggota tidak menjamin kesamaan metadata ZIP, mode, timestamp, direktori, compressed stream, seluruh struktur ZIP, perilaku installer, penerimaan ZIP64 oleh recovery, atau kompatibilitas perangkat. Pemeriksaan-pemeriksaan itu tetap terpisah.
- Sertifikat publik yang lolos tidak otomatis dipercaya oleh recovery pengguna. AVB/vbmeta, rollback, SELinux runtime, VINTF/HAL/ABI, enkripsi, boot dan fungsi perangkat tetap belum dibuktikan. Jangan menonaktifkan verifikasi atau meminta/mengunggah private key pengguna.
- [Catatan resmi OrangeFox R12.0_2 FBEv2](https://orangefox.download/release/69ea75f54a1c3a7b3f7c103d) secara eksplisit menyatakan **jangan gunakan dengan MIUI atau HyperOS**. Pengguna memang melaporkan pernah berhasil mem-flash port yang sama dengan varian tersebut; pengalaman itu diterima, tetapi bukan uji kandidat baru atau bukti dekripsi/restore aman. Tidak ada anjuran mengganti recovery secara otomatis.

[Referensi metadata Madrid terpisah](HASIL-REFERENSI-MADRID-2026-11-03.md) dan [status boot-first](STATUS-KELANJUTAN-BOOT-FIRST-2026-11-02.md) menjelaskan blocker lainnya.
