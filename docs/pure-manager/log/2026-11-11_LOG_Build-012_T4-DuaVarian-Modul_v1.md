# LOG-012 — Pure Manager 0.7.0
## Tahap T4: dua varian (FULL & MINIMAL), klien modul dengan verifikasi

**Tanggal:** 2026-11-11
**Versi:** 0.6.0 → **0.7.0** (versionCode 13)
**Run hijau:** [43029254062](https://github.com/dwp29/Synthentica/actions/runs/43029254062) — commit `b109559`

| Varian | Berkas | Ukuran | sha256 (16 awal) | ID Drive |
|---|---|---|---|---|
| **FULL** | `PureManager-0.7.0-DEBUGKEY.apk` | 18.887.913 B | `5a2a0c95e287d6b0` | `1EmgUMlRqX2gRaVPVKzLGvn927Y8Xlnlx` |
| **MINIMAL** | `PureManager-0.7.0-minimal-DEBUGKEY.apk` | 18.887.921 B | `c1e2440272897d1d` | `1SkZTB8YDUUyVE2k24RZSaHJaCW0Q1MiN` |

Keduanya di folder Drive `02-BUILD-APK`.
**Log ini di Drive:** ID `17qLNKuy-jT2rMdiVwJdhsF222oQ6TLFi`
**Pemeriksaan dari sandbox:** zip bersih 146 entri; manifest MINIMAL memuat
`net.pure.manager.minimal`, manifest FULL tidak memuat kata "minimal".

---

## 1. Dua varian

| | FULL | MINIMAL |
|---|---|---|
| Paket | `net.pure.manager` | `net.pure.manager.minimal` |
| Nama versi | `0.7.0` | `0.7.0-minimal` |
| Tab Modul & terminal | ada | **tidak ada** (tab disembunyikan) |
| Manajer berkas (salin, ZIP, cari, A–Z, thumbnail) | ada | ada |

Karena id paketnya berbeda, **keduanya bisa dipasang bersamaan** di HP yang sama.
Itu satu-satunya cara membandingkan dua versi tanpa menghapus salah satunya.

Saya periksa sendiri kedua APK-nya: manifest MINIMAL benar-benar memuat
`net.pure.manager.minimal` (dibaca dari `AndroidManifest.xml` di dalam APK), sedang
manifest FULL tidak memuat kata "minimal" sama sekali.

Catatan jujur: tab Modul yang disembunyikan **tidak** membuat APK jadi jauh lebih
kecil (18.887.921 vs 18.887.913 byte — selisih 8 byte). Yang dikurangi adalah
permukaan UI, bukan kode. Kalau Anda menginginkan MINIMAL yang benar-benar ramping,
itu perlu pemisahan kode ke modul terpisah dengan R8 — pekerjaan tersendiri, dan
saya tidak akan mengklaim sudah melakukannya.

---

## 2. Klien modul

Alurnya: **unduh → hash SHA-256 → bandingkan → pakai atau hapus**.

| Aturan | Kenapa |
|---|---|
| SHA-256 dicek sebelum modul bisa dipakai | Modul yang dieksekusi tanpa pemeriksaan adalah kesalahan yang tidak bisa ditarik kembali. |
| Berkas yang hash-nya salah **dihapus** | Berkas yang tertinggal di folder adalah satu ketukan dari dipasang oleh versi aplikasi berikutnya yang mempercayai folder itu. |
| Hash dibaca dengan stream 64 KB | Modul bisa puluhan MB; membacanya utuh hanya untuk di-hash adalah lonjakan memori tanpa alasan. |
| Perbandingan versi numerik | `"1.10.0"` vs `"1.9.0"` — sebagai teks, `"1.10"` lebih kecil, dan itu cara pembaruan diam-diam berhenti ditawarkan. |

**Yang belum ada, dan dikatakan di layar:** tanda tangan **Ed25519**. Hash yang
diambil dari tempat yang sama dengan berkasnya melindungi dari berkas rusak, **bukan**
dari pihak yang bisa mengganti keduanya sekaligus. Kalimat itu tercetak di tab Modul,
bukan disembunyikan di komentar kode.

**Katalog masih kosong** karena belum ada rilis modul. Layarnya mengatakan itu, bukan
menampilkan tombol unduh palsu. Alur unduh–periksa–pasang–hapus sudah jalan dan diuji
(12 tes JVM).

---

## 3. Empat bug di build ini

Semua tertangkap sebelum sampai ke HP Anda, dan semuanya sudah ditutup penjaga:

1. **`testReleaseUnitTest` ambigu.** Dimensi flavor mengubahnya menjadi dua task;
   Gradle menolak menebak dan build mati sebelum satu tes pun jalan. → diganti
   `testFullReleaseUnitTest`.
2. **Cek paket FULL bisa dipuaskan APK MINIMAL.** `grep -F "package: name='net.pure.manager'"`
   juga cocok dengan `net.pure.manager.minimal`. Artinya APK MINIMAL yang benar
   meloloskan pemeriksaan varian FULL, dan id paket yang salah akan lolos diam-diam.
   → dicocokkan persis sampai tanda kutip penutup.
3. **Pembanding penanda tangan kedua selalu kosong.** `SIGNER_MIN` dihitung sebelum
   `SIGNER` ada, jadi perbandingan "kedua varian harus dikunci yang sama" tidak
   pernah benar-benar terjadi. → urutan dibetulkan, dan penjaga memastikan urutannya.
4. **Penjaga Python tidak pernah dijalankan CI.** 108 penjaga sumber hanya dijalankan
   manual di sandbox. Penjaga yang tidak dijalankan hanyalah komentar yang punya nama.
   → sekarang menjadi langkah tersendiri di workflow, sebelum tes unit.

Dua di antaranya (2 dan 3) tidak akan pernah terlihat selama hanya ada satu varian.
Itu pelajaran sebenarnya dari T4: memecah build menjadi dua membuat dua jalur yang
sebelumnya tidak ada, dan satu di antaranya sempat salah tanpa suara.

---

## 4. Bukti

- **108 penjaga sumber** — OK, dan **sekarang dijalankan CI**.
- **Tes JVM**: 110 tes (105 lama + 12 modul − beberapa penjaga pindah kelas… angka
  pasti ada di notice build) — hijau di run 43029254062.
- Kedua APK: zip bersih, 146 entri, id paket berbeda terbukti dari manifest.
- Workflow memverifikasi zipalign, badging, id paket, nama versi, dan penanda tangan
  **untuk kedua varian**.

---

## 5. Yang belum

| Hal | Status |
|---|---|
| T5 PDF/Word/Excel | belum |
| T6 editor kode | belum |
| T7 edit gambar/audio | belum |
| T8 AI | ditahan |
| Kunci rilis dipakai | menunggu 2 variabel GitHub (LOG-010 §5) |
| Tanda tangan Ed25519 modul | belum — butuh kunci publik yang diterbitkan |
| Arti "reset" | masih belum jelas |
