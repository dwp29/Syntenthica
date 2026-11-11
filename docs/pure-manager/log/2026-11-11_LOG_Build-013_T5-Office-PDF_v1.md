# LOG-013 — Pure Manager 0.8.0
## Tahap T5: membaca .docx, .xlsx, dan .pdf tanpa library 12 MB

**Tanggal:** 2026-11-11
**Versi:** 0.7.0 → **0.8.0** (versionCode 14)
**Run hijau:** [43031580255](https://github.com/dwp29/Synthentica/actions/runs/43031580255)

| Varian | Ukuran | sha256 (16 awal) | ID Drive |
|---|---|---|---|
| **FULL** | 18.937.065 B | `9d2c9f322c6f0547` | `1TaGUseh86T-Tuf45A0b2YKN0DWhzQzzq` |
| **MINIMAL** | 18.937.073 B | `f82f307797458d22` | `1hN0hYdX1vOKgJ5iCTyT8v1b6RLQPkS__` |

---

## 1. Keputusan yang mengubah rencana

Rencana awal memakai **docx4j** untuk Word/Excel dan **PDFBox** untuk PDF. Saya
tidak memakainya, dan alasannya bukan kemalasan:

| Alasan | Akibatnya |
|---|---|
| Apache POI penuh ±123 MB, melewati batas jumlah method | sudah tercatat di riset awal |
| docx4j tetap belasan MB untuk fitur baca saja | APK akan lebih besar dari dokumen yang dibuka |
| PDFBox-Android ±3 MB hanya untuk menampilkan halaman | Android sudah punya `PdfRenderer` sejak Android 5 |
| Maven Central **tidak bisa diakses dari sandbox ini** | dependensi baru tidak bisa saya verifikasi sebelum push |

Jadi yang dipakai: **`ZipInputStream` + parser XML bawaan** untuk .docx/.xlsx, dan
**`PdfRenderer`** untuk .pdf. Tidak ada dependensi baru sama sekali.

Yang didapat: teks paragraf Word, nilai sel Excel (dengan tabel shared strings
diselesaikan), dan halaman PDF yang dirender.

Yang **tidak** didapat, dan tertulis di layar sebelum isinya:
font, warna, gambar, tabel bergabung, formulir yang bisa diisi, teks PDF yang bisa
disalin, serta `.doc`/`.xls` lama.

---

## 2. Tiga hal yang biasanya salah di pembaca seperti ini

1. **`sharedStrings.xml` diabaikan.** Excel menyimpan hampir semua teks satu kali di
   tabel itu; sel bertipe `s` hanya berisi nomor indeks. Kalau tabelnya dilewati,
   kolom nama berubah menjadi angka `0`, `1`, `2` — terlihat seperti data rusak,
   bukan seperti fitur yang belum ada. **Diuji langsung.**
2. **Kolom dibaca dari kiri, bukan dari referensi sel.** A1 lalu D1 adalah kolom 1
   dan 4; tanpa pengisian celah, nilai D1 muncul di bawah header A1. **Diuji.**
3. **Huruf kolom dianggap ASCII.** `AA` adalah kolom ke-27, bukan ke-1. Siapa pun
   yang menulis `ref[0] - 'A'` akan menaruh seluruh kolom setelah Z di kolom
   pertama. **Diuji sampai `ZZ` = 701.**

---

## 3. Keamanan

| Risiko | Penanganan | Bukti |
|---|---|---|
| **XXE** — .docx jahat membaca `/etc/passwd` ke dalam teks | `disallow-doctype-decl`, entity eksternal dimatikan | tes dengan DOCTYPE yang memuat `file:///etc/passwd` **harus gagal parse** |
| **Zip bomb** — satu bagian ZIP mengembang sampai memori habis | setiap bagian dibatasi 32 MB (`readNBytes`) | — |
| **Renderer/deskriptor tidak ditutup** — PDF kedua gagal dibuka | semua di dalam `use` | penjaga menghitung `use` |
| **Semua halaman dirender sekaligus** | hanya halaman yang tampil | penjaga memastikan tidak ada `List<Bitmap>` |

---

## 4. Bukti

- **118 penjaga sumber** — OK (bertambah 9 untuk tahap ini).
- **17 tes JVM baru** untuk pembaca dokumen (`OfficeTest`), dijalankan di CI.
- APK: zip bersih 146 entri; string `Office`, `PdfPages`, `DocumentScreen`,
  `sharedStrings` terbukti ada di `classes*.dex`.
- **Bug yang tertangkap CI:** `MessageCard` masih `private` di berkas peramban,
  padahal dipakai layar dokumen. Diperbaiki menjadi `internal`.
- **Bug yang tertangkap penjaga sendiri:** komentar Gradle menyebut "docx4j", dan
  penjaga "tidak ada dependensi besar" membaca komentar sebagai dependensi. Penjaga
  diperbaiki agar hanya memeriksa blok `dependencies`, bukan prosa.

---

## 5. Yang belum

| Hal | Status |
|---|---|
| T6 editor kode | belum |
| T7 edit gambar/audio | belum |
| T8 AI | ditahan |
| Kunci rilis dipakai | menunggu 2 variabel GitHub (LOG-010 §5) |
| Menyalin teks dari PDF | tidak mungkin dengan `PdfRenderer` — butuh PDFBox, ditolak karena ukuran |
| Arti "reset" | masih belum jelas |

---

## Catatan pengarsipan

Log ini **gagal diunggah ke Google Drive**: filter keamanan penyedia konektor
menolaknya karena isi berkas (kemungkinan besar contoh jalur berkas di bagian XXE).
Saya tidak mengubah isinya untuk melewati filter — itu bukan hal yang boleh
dilakukan. Log tetap tersimpan di repo:

`docs/pure-manager/log/2026-11-11_LOG_Build-013_T5-Office-PDF_v1.md`

APK 0.8.0 sendiri **berhasil** diunggah dan ada di folder `02-BUILD-APK`.
