# Gate host untuk signature recovery — 3 November 2026

**Status ROM: BELUM SELESAI / HOLD / JANGAN FLASH.** Ini adalah alat dan kontrol host, bukan penandatanganan kandidat, verifikasi trust recovery, atau uji perangkat.

## Yang dibuat dan diuji

`synthetica-project/audit_recovery_signature.py` membaca ZIP dan sertifikat X.509 publik saja. Ia mengharuskan SHA-256 ZIP dan SHA-256 **SubjectPublicKeyInfo** sertifikat dipin secara eksplisit, memeriksa footer/rentang whole-file sebagaimana source AOSP yang ditinjau, lalu memverifikasi signature SHA-256 langsung dengan public key yang diberikan melalui OpenSSL host. Parser ASN.1 dipin di `requirements-recovery-audit.txt`. Input yang tidak didukung ditolak, bukan otomatis dianggap signature tidak sah. Pembacaan dibatasi dan pemeriksaan identitas file dilakukan sebelum dan sesudah; tool tidak mengekstrak atau menjalankan isi paket, tidak membaca private key, dan tidak menulis atau menandatangani ZIP.

[Run 41566434128](https://github.com/dwp29/Syntenthica/actions/runs/41566434128) selesai **sukses untuk kontrol host**, pada commit `38ab9aa711c279fcdc41c422b34a1c8714f6a11b`. Dua belas tes sintetis mencakup RSA, EC P-256, struktur ZIP64 sintetis, data diubah, sertifikat/key yang salah, input unsigned, footer keliru, pin salah, perubahan file saat pemeriksaan, serta format algoritma yang tidak didukung. Kunci fixture dibuat sementara dan dibuang, bukan key produksi.

Run yang sama mengambil `otatools.zip` Android CI build **16644040**, memeriksa SHA-256 `bc85557aa0c59a7d0b48b8175250948d67b2d0f293bd74eb8d5753ba4ad7781f`, mengekstrak hanya SignApk dan library JNI yang diperlukan, lalu membuat dan menandatangani **ZIP sintetis kecil** dengan kunci sementara. Verifier host menerima signature dari SignApk dan menolak salinan sintetis yang diubah. Kesamaan hash tool bukan verifikasi tanda tangan provenance build. Tes SignApk ini bukan uji ZIP64 berukuran nyata 4 GB atau lebih, dan bukan uji ROM atau OrangeFox.

## Batas penting

- Hasil sukses berarti signature cocok dengan **public key yang secara eksplisit dipasok dan dipin**. Ini **tidak** membuktikan key tersebut dipercaya recovery, apalagi jika sumbernya hanya `otacert` di dalam ZIP. Key dan setting recovery yang sebenarnya belum diperiksa.
- Verifier host tidak menjalankan kode OrangeFox pada perangkat dan tidak memvalidasi seluruh ZIP, isi OTA, offset `property-files`, APK/APEX, AVB/vbmeta, rollback atau boot. Pemeriksaan tersebut harus terpisah terhadap artefak final yang sebenarnya.
- Alat mendukung cakupan konservatif: PKCS#7 direct-signature SHA-256 dengan satu signer RSA 2048/4096 atau EC P-256; SHA-1, signed attributes, key/format lain ditolak sebagai **di luar cakupan**. Input yang belum pernah diuji bukan otomatis rusak.
- Kandidat 03 tetap unsigned oleh resep dan memiliki ZIP comment 0 byte; alat ini tidak menciptakan signature untuknya. Tidak ada kandidat 04, key privat pengguna, perubahan image, penonaktifan pemeriksaan atau tindakan pada perangkat.

Sebelum suatu kandidat dapat dinilai layak, masih diperlukan kombinasi framework/vendor/policy yang dibuktikan sesuai, kepercayaan signer dan AVB yang sah, validasi offset pada ZIP final, lalu pengujian recovery/boot dan fungsi pada perangkat. [Pemetaan framework/vendor](PEMETAAN-LANJUTAN-FRAMEWORK-VENDOR-2026-11-03.md); [triage format signing 03](HASIL-SIGNING-REFERENSI-2026-11-03.md).
