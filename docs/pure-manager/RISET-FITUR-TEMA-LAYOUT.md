# Riset Pure Manager — Fitur, Tema, Layout

Status: **riset, belum ada kode aplikasi.** Tanggal 2026-10-31.
Proyek baru. Tidak memakai ulang kode atau kunci dari Manager 6.1.

Gambar: `mockup-tema-layout.png`, `mockup-matriks-mode.png` (folder yang sama).

---

## 1. Ringkasan temuan

Riset ini menjawab satu pertanyaan: **apa yang belum ada di file manager Android,
dan apakah permintaan Anda (edit gambar, AI, edit suara) bisa dijalankan serius
di dalam satu aplikasi?**

Tiga kesimpulan utama:

1. **Celah terbesar bukan fitur, tapi integrasi.** Semua pesaing punya file manager,
   beberapa punya editor media, tapi hampir tidak ada yang menyatukan keduanya
   secara rapi. MiXplorer punya segalanya tapi UI-nya padat dan usang (dikeluhkan
   pengguna sendiri di forum). Solid Explorer rapi tapi kaku dan berbayar.
   **Inilah posisi Pure Manager: kekuatan MiXplorer dengan keindahan Solid Explorer,
   ditambah edit media dan AI yang tidak dimiliki keduanya.**

2. **AI bukan fitur tambahan, tapi lapisan lintas fitur.** Nilainya bukan "ada AI",
   tapi: pencarian semantik, penamaan otomatis, deteksi duplikat, OCR, dan
   pengelompokan cerdas. Semuanya harus jalan **on-device** karena Anda di luar
   Play dan pengguna file manager sangat sensitif soal privasi.

3. **Permintaan "semua fitur" bertabrakan dengan satu hal:** ukuran APK dan
   kerapuhan. Setiap fitur berat (FFmpeg, model AI, Smali) menambah puluhan MB dan
   menambah permukaan kerusakan. Jawabannya bukan menolak, tapi **modul terpisah**
   yang diunduh saat dibutuhkan — lihat §6.

---

## 2. Lanskap pesaing (riset 2026)

| Aplikasi | Kekuatan | Kelemahan yang dikeluhkan | Yang bisa diambil |
|---|---|---|---|
| **MiXplorer** | Plugin, 19+ cloud, arsip lengkap, sangat bisa dikustom | UI padat, kurva belajar curam, sebaran di luar Play | Sistem plugin, kedalaman format |
| **Solid Explorer** | Desain M3 paling rapi, dual-pane, vault AES-256 | Berbayar ($2.99 dual-pane), kaku | Kualitas visual, vault |
| **X-plore** | Dual-pane gratis, tree-view, Android TV, disk map | UI terasa usang, ada iklan | Tree-view, disk map, dukungan TV |
| **FX File Explorer** | Privasi, tanpa koleksi data, pembersih | Pembaruan jarang | Posisi privasi |
| **MT Manager** | APK editor (DEX/ARSC/XML), tanda tangan on-device | Tidak di Play, fitur berisiko hukum | Hanya bagian teknis yang sah |
| **Files by Google** | Sederhana, andal, gratis | Sangat dasar | Kategori otomatis |

**Kesimpulan kompetitif:** tidak ada satu pun yang punya **edit gambar + edit suara +
AI on-device di dalam file manager**. Itu ruang kosong yang bisa diisi.

---

## 3. Fitur yang BELUM ada, dan layak dibuat

Diurutkan dari yang paling membedakan.

### 3.1 Lapisan AI (pembeda utama)

| Fitur | Cara kerja | Biaya realistis |
|---|---|---|
| **Pencarian semantik** | "cari struk bulan lalu" — bukan cocok nama | Embedding on-device, indeks lokal |
| **Penamaan otomatis** | `IMG_4321.jpg` → `Struk-Tokopedia-2026-10.jpg` | OCR (ML Kit) + model kecil |
| **Deteksi duplikat isi** | Hash + kemiripan persepsi untuk gambar | pHash, tanpa AI mahal |
| **OCR massal** | Semua gambar & PDF jadi bisa dicari | ML Kit, 20–50 MB, 100–300 ms/gambar |
| **Ringkasan dokumen** | PDF 30 halaman → 5 poin | Model kecil atau cloud opsional |
| **Klasifikasi otomatis** | Struk / KTP / faktur / tangkapan layar | Model klasifikasi ringan |
| **Pembersih pintar** | Saran hapus: buram, duplikat, layar mati | Heuristik + model kecil |

**Realitas teknis (penting):** Gemini Nano hanya ada di flagship tertentu, foreground-only,
dan berkuota. **Jangan jadikan itu fondasi.** Arsitektur yang benar: satu antarmuka
`AiEngine` dengan tiga implementasi — on-device lokal (LiteRT/ONNX), Gemini Nano kalau
tersedia, dan cloud opsional (kunci milik pengguna). Kalau satu tidak ada, turun ke
yang lain, jangan gagal.

### 3.2 Edit gambar

Yang belum ada di file manager mana pun secara serius:

| Fitur | Catatan |
|---|---|
| Crop, rotate, flip, straighten | Dasar, wajib |
| Kecerahan, kontras, saturasi, suhu | Non-destruktif, bisa dibatalkan |
| Filter & preset | 20–40 preset siap pakai |
| Hapus background | Bisa on-device; ini fitur "wow" |
| Batch resize & convert | HEIC/AVIF/WebP — pembeda besar |
| Edit EXIF | Termasuk **hapus GPS** (privasi) |
| Watermark & teks | Untuk pengguna yang jual foto |
| RAW/DNG | Hanya baca + develop dasar |
| Histogram & color picker | Untuk yang serius |
| **Non-destruktif + undo riwayat** | Ini yang membedakan dari app edit biasa |

**Jangan bikin editor setara Lightroom.** Yang menang adalah **edit cepat tepat di
tempat** (in-place), karena itulah gunanya file manager.

### 3.3 Edit suara

| Fitur | Catatan |
|---|---|
| Waveform interaktif | Wajib; ini yang membuat trimming terasa |
| Trim, split, merge | Operasi inti |
| Fade in/out | Kecil tapi sangat diminta |
| Ubah volume / normalisasi | Normalisasi loudness (EBU R128) |
| Konversi format | MP3/WAV/AAC/FLAC/OGG/M4A |
| Ubah bitrate | Untuk memperkecil |
| Denoise sederhana | Bukan studio-grade; cukup untuk rekaman |
| Ekstrak audio dari video | Sangat sering dipakai |
| Edit tag ID3 | Judul, artis, album, cover |
| Rekam suara | Pelengkap |

**Realitas teknis:** FFmpeg adalah satu-satunya jalan untuk format lengkap, tapi
**build FFmpeg penuh berlisensi GPL** dan menambah 15–30 MB per ABI. Pilihan:

- **Rekomendasi:** pakai `MediaCodec`/`MediaMuxer` untuk operasi umum (trim, merge,
  konversi dasar) — **tanpa GPL**, APK kecil. FFmpeg hanya untuk kasus langka,
  sebagai modul terpisah yang diunduh.
- Anggaran ukuran harus dijaga; lihat §6.

### 3.4 Fitur yang belum ada di mana pun, dan murah dibuat

- **Recycle bin** dengan pemulihan — sangat jarang di file manager Android
- **Riwayat operasi** yang bisa dibatalkan (undo untuk move/rename massal)
- **Mode dual-pane seret antar-cloud** (X-plore punya, sedikit yang lain)
- **Peta penyimpanan** interaktif (treemap), bukan sekadar daftar
- **Aturan otomatis**: "semua `.apk` di Download → pindah ke folder APK"
- **Penanda folder favorit dengan warna**
- **Bandingkan dua folder** (untuk backup)
- **Cari berdasarkan isi** berkas teks, bukan hanya nama

---

## 4. Riset tema

### 4.1 Temuan dari Material 3 Expressive (2025–2026)

Ini standar desain Android sekarang. Yang relevan untuk kita:

- **Dua skema gerak:** *Expressive* (pegas, ada overshoot) dan *Standard* (redam tinggi).
  **Aturan mutlak: jangan pernah pasang bounce pada opacity/warna.** Hanya posisi,
  ukuran, bentuk yang boleh memantul. Warna dan alpha harus redam kritis.
- **Token spasial vs efek** dipisah. Ini persis yang saya sarankan di dokumen
  sebelumnya: `motionSpec` per tema, bukan angka mentah di tiap komponen.
- **Hormati "reduce motion"** — kalau skala animasi sistem = 0, semua transisi
  harus instan. Ini sering dilupakan dan membuat aplikasi terasa rusak bagi
  pengguna yang mengaktifkannya.
- **Maksimal 1–2 "hero moment" per alur.** Jangan setiap layar beranimasi.
- **Kontras:** teks 4.5:1, non-teks 3:1. Target sentuh minimal 48dp.

### 4.2 Empat tema, empat model layout

Lihat `mockup-tema-layout.png`. Yang saya rancang bukan empat warna, tapi
**empat cara menyusun informasi**:

| Tema | Model navigasi | Baris berkas | Ikon | Kepadatan |
|---|---|---|---|---|
| **iOS** | Tab bar bawah, judul besar, field cari | Kartu terpisah, radius 12–16 | Squircle terisi | Lega (54dp) |
| **Pixel** | Navigation bar + pill indikator | Kartu tonal, radius 20 | Material Symbols | Lega (62dp) |
| **Windows** | **Rail kiri** + tabel berkolom | Baris tabel, garis 1px | Fluent, kotak | **Padat (34dp)** |
| **Cyberpunk** | **Baris perintah bawah** (F1–F4) | Grid mono, border menyala | Glyph monospace | **Padat (30dp)** |

Keputusan penting: **Windows dan Cyberpunk memakai model navigasi berbeda**, bukan
hanya warna berbeda. Windows meniru Explorer (rail + kolom), Cyberpunk meniru
terminal (baris perintah). Kalau hanya warnanya yang beda, tema terasa seperti
skin murah.

### 4.3 Tema × Mode — tiga sumbu

Lihat `mockup-matriks-mode.png`. Yang perlu ditegaskan:

- **AMOLED bukan "hitam lebih pekat".** Di atas hitam murni, elevasi tonal tidak
  terlihat sama sekali. Jadi AMOLED **mematikan bayangan** dan memindahkan
  pemisahan ke **garis tepi** dan **kontras**. Kalau tidak, semua kartu menyatu.
- **Light mode pada Cyberpunk** tetap harus terasa Cyberpunk — karena itu
  memakai latar ungu pucat dengan aksen neon gelap, bukan sekadar membalik warna.
- **Windows Light** memakai abu-abu netral (`#F3F3F3`), bukan putih — itu yang
  membuatnya terasa seperti Explorer, bukan seperti iOS.

### 4.4 Tipografi per tema

| Tema | Font | Alasan |
|---|---|---|
| iOS | Inter | Netral, metrik mirip SF, lisensi OFL |
| Pixel | Roboto / Google Sans Flex | Asli Android |
| Windows | **Selawik** | Pengganti metrik Segoe UI, lisensi OFL — jangan pakai Segoe asli |
| Cyberpunk | JetBrains Mono / IBM Plex Mono | Mono, OFL |
| Default | Inter | Bisa diubah pengguna |

Semua font di atas **boleh dibundel** (OFL). Segoe UI dan SF Pro **tidak boleh** —
itu alasan mockup ini memakai DejaVu sebagai pengganti sementara.

---

## 5. Arsitektur yang muncul dari riset ini

### 5.1 Modul, bukan monolit

```
pure-manager/
├── core/          berkas, arsip, izin, operasi massal
├── ui/            tema, token, komponen
├── media-image/   editor gambar
├── media-audio/   editor suara
├── ai/            antarmuka AiEngine + implementasi
├── root/          libsu, opsional
├── network/       SMB/FTP/SFTP/HTTP
└── apk-tools/     AXR/ARSC/DEX (nanti)
```

### 5.2 Batas ukuran APK — ini yang menentukan segalanya

| Komponen | Ukuran | Keputusan |
|---|---|---|
| UI + core | ~8 MB | Wajib, di APK utama |
| 4 font | ~600 KB | Di APK utama |
| ML Kit OCR | +3–4 MB (model terunduh) | Opsional saat pemasangan |
| Whisper-tiny | ~75 MB | **Modul unduh**, jangan dibundel |
| FFmpeg penuh | 15–30 MB/ABI | **Modul unduh**, GPL dipisah |
| Model embedding | 50–200 MB | **Modul unduh**, pilih oleh pengguna |
| Smali/DEX | ~2 MB | APK utama |

**Target: APK utama di bawah 20 MB.** Semua yang berat jadi modul. Ini juga
menjawab masalah lisensi: FFmpeg GPL di modul terpisah yang diunduh terpisah
tidak mencemari lisensi APK utama.

### 5.3 AI: antarmuka dulu, model belakangan

```
AiEngine
├── LocalEngine    (LiteRT / ONNX, model dipilih pengguna)
├── NanoEngine     (Gemini Nano via ML Kit, kalau perangkat mendukung)
└── CloudEngine    (API key milik pengguna, opsional, mati secara default)
```

Aturan: **tidak ada satu fitur pun yang bergantung pada AI.** Kalau semua mesin AI
tidak tersedia, aplikasi tetap berfungsi penuh sebagai file manager. AI adalah
lapisan di atas, bukan fondasi.

---

## 6. Yang saya sarankan TIDAK dibuat

| Fitur | Alasan |
|---|---|
| Signature killer / bypass verifikasi | Membantu pelanggaran hak cipta; rusak tiap update Android |
| Tulis RAR | Format tertutup |
| MTP | Tidak bisa dibuat aplikasi; itu protokol sistem |
| Editor video penuh | Itu aplikasi terpisah; cukup trim + ekstrak audio |
| Editor gambar setara Lightroom | Kalah bersaing, dan bukan inti file manager |
| Cloud SDK komersial (Drive/Dropbox) | Menambah 5–10 MB per provider; lebih baik lewat SAF/WebDAV |
| Gemini Nano sebagai fondasi AI | Hanya flagship, foreground-only, berkuota |

---

## 7. Prioritas berdasarkan riset

Urutan ini berbeda dari dokumen sebelumnya, karena riset mengubah penilaian.

**P0 — Fondasi yang tidak terlihat tapi menentukan**
`FileOps` (Safe + Root), token tema, operasi berkas dengan undo, arsip.
Tanpa ini semua fitur lain akan dibongkar ulang.

**P1 — Pembeda yang murah**
Recycle bin, undo, pencarian isi, peta penyimpanan, aturan otomatis, 4 tema.
Ini yang membuat orang berpindah dari MiXplorer.

**P2 — Media**
Editor gambar (in-place, non-destruktif), editor suara (MediaCodec dulu).
Ini yang tidak dimiliki pesaing mana pun.

**P3 — AI**
Mulai dari yang murah dan pasti berguna: **OCR + duplikat + penamaan**.
Jangan mulai dari chatbot.

**P4 — Jaringan dan bedah APK**
Terakhir, karena paling rapuh.

---

## 8. Pertanyaan terbuka untuk Anda

1. **Ukuran APK utama di bawah 20 MB** — setuju? Kalau tidak, fitur berat harus
   dibundel dan APK jadi 80–150 MB.
2. **AI on-device atau cloud?** On-device = privat tapi terbatas perangkat.
   Cloud = pintar tapi berkas keluar dari HP.
3. **Cyberpunk dengan baris perintah bawah** (seperti mockup) atau tetap tab
   biasa dengan warna neon saja? Yang pertama lebih berani.
4. **Dukungan Android TV?** X-plore punya, dan itu celah yang belum terisi
   oleh pesaing premium.
