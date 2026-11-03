# Pemeriksaan awal lisensi SpatialFlow v1.8.2 — 3 November 2026

**Belum layak dinyatakan aman untuk distribusi komunitas.** Ini inventaris teknis, bukan pendapat hukum, bukan bukti seluruh komponen terdapat dalam APK rilis, dan bukan izin mendistribusikan ROM dasar.

## Ketidaksesuaian pada repositori aplikasi

Pada commit `8a40906d074ab95b2bfa32481bfae140dfdfcbed`:

- Berkas [`LICENSE`](https://github.com/MythicalSHUB/SpatialFlow/blob/8a40906d074ab95b2bfa32481bfae140dfdfcbed/LICENSE) adalah teks **Apache-2.0** (Git blob `07339d19cf854d41e719f6450d3e6a8c0a1786a2`, SHA-256 `33617bbae1e7124616a8cb439f6966006069128a7898776655dfa76395ed35c9`).
- [`README.md`](https://github.com/MythicalSHUB/SpatialFlow/blob/8a40906d074ab95b2bfa32481bfae140dfdfcbed/README.md) menyatakan **MIT** dan menunjuk berkas `LICENSE` yang ternyata berisi Apache-2.0 (SHA-256 README `ca4300590cd85cfa452710246c88e3e4c7012e4a98188dd9e33717c9b2793efa`). Tidak dapat disimpulkan otomatis apakah keduanya memang ditawarkan atau salah satu adalah kekeliruan; klarifikasi pemegang hak diperlukan sebelum penerbitan.

## Dependensi yang perlu ditelusuri

- [`app/build.gradle`](https://github.com/MythicalSHUB/SpatialFlow/blob/8a40906d074ab95b2bfa32481bfae140dfdfcbed/app/build.gradle) mendeklarasikan `implementation libs.newpipeextractor`; katalog versi menunjuk `com.github.TeamNewPipe:NewPipeExtractor:v0.26.1`. [Tag upstream](https://github.com/TeamNewPipe/NewPipeExtractor/tree/18757880f64620568381bab1bf87104ede940d1c) memiliki berkas lisensi GPL-3.0. Keterkaitan deklarasi sumber dengan isi APK rilis, lisensi yang berlaku terhadap hasil gabungan, dan pemenuhan kewajiban distribusinya belum diverifikasi.
- Pohon sumber menyertakan `app/libs/ffmpeg-kit-audio-6.0-2.LTS.aar` (Git blob `a0a8173cfc01edb800e6715492cabf63aad42395`). [Dokumentasi FFmpegKit](https://github.com/arthenica/ffmpeg-kit/blob/97760a31349439243487a99adbcde09e9dabe458/README.md) menyatakan bundle umumnya LGPL-3.0 dan varian yang mengaktifkan GPL menjadi GPL-3.0. Nama berkas saja tidak mengautentikasi binary, konfigurasi build, versi seluruh library, atau pemenuhan source/notices.
- `app/build.gradle` mengecualikan sejumlah `META-INF/LICENSE*`, `NOTICE*`, dan `DEPENDENCIES` dari packaging. Ini bukan bukti otomatis pelanggaran: pemberitahuan dapat disediakan di tempat lain. Namun sumber, lisensi dan pemberitahuan semua dependensi hasil build tetap harus diinventarisasi serta tersedia sesuai ketentuan yang berlaku.
- Tag sumber tidak bertanda tangan dan hubungan source-to-binary untuk APK rilis `a3c5349073f9819764f185022867a9d47c58347d9c34573423e6397f33f9233d` belum diautentikasi. Tanda tangan APK yang valid hanya membuktikan konsistensi paket terhadap sertifikatnya, bukan kewenangan distribusi.

## Gate

Sebelum distribusi: klarifikasi ketentuan SpatialFlow yang bertentangan, inventarisasi dependensi dan source/notices yang benar, evaluasi kewajiban komponen GPL/LGPL dan hak atas ROM, Google apps, serta komponen proprietari lain. Sampai itu dan pengujian perangkat selesai, semua kandidat tetap **draft pribadi / HOLD / JANGAN FLASH**, bukan rilis komunitas.
