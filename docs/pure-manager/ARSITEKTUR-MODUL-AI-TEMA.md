# Pure Manager — Arsitektur Distribusi, AI, dan Tema

Keputusan yang sudah dikunci: dua varian (Full & Minimal), AI dengan pilihan agen,
tab kustomisasi tema, dukungan Android TV. Tanggal 2026-10-31.
Dokumen ini menjawab pertanyaan modul dan merinci riset AI.

---

## 1. Jawaban langsung: modul diunduh dari mana?

**Tiga cara mengunduh, dan satu di antaranya harus dihindari.** Ini bedanya
menentukan apakah aplikasi bisa dipasang di luar Play Store atau tidak.

| Cara | Bekerja di luar Play? | Ukuran yang bisa | Kapan dipakai |
|---|---|---|---|
| **A. Dynamic Feature Module + Play Core** | ❌ **Tidak.** Butuh Play Store sebagai penyedia | — | Jangan dipakai |
| **B. `bundletool` + `--local-testing`** | ⚠️ Hanya untuk pengujian, bukan rilis | — | Uji internal saja |
| **C. Unduh berkas biasa dari server sendiri** | ✅ **Ya** | Tak terbatas | **Ini yang dipakai** |
| **D. Sertakan semua di APK Full** | ✅ Ya | 100–200 MB | Varian Full |

**Temuan riset yang menentukan:** Dynamic Feature Module bergantung pada Play Core
dan Play Store sebagai penyedia unduhan. `--local-testing` di `bundletool` hanya
untuk pengujian lokal — modul disimpan di kartu SD lewat perintah ADB, bukan
diunduh pengguna. **Karena Anda di luar Play Store, DFM tidak bisa dipakai.**

### 1.1 Arsitektur modul yang benar untuk Pure Manager

```
APK Minimal (± 12–18 MB)
├── core/        berkas, arsip zip/tar, tema, izin
├── ui/          4 tema + token
└── ModuleManager
     ├─ cek modul terpasang  (versi + sha256)
     ├─ unduh dari GitHub Releases / server sendiri
     ├─ verifikasi SHA-256 + tanda tangan Ed25519
     └─ pasang ke /data/data/net.pure.manager/modules/<id>/
```

**Isi modul** = berkas `.so` native, aset model AI, atau DEX tambahan lewat JAR
yang dimuat `DexClassLoader`. Pola ini sudah terbukti di aplikasi nyata:

- **Native `.so`**: diunduh lalu dimuat dengan `System.load(path)` atau `dlopen()`.
  Ini jalan resmi — bukan akal-akalan. (Riset StackOverflow & dokumentasi NDK
  mengonfirmasi `System.load()` menerima path absolut.)
- **Model AI**: hanya berkas data, paling mudah — tidak ada kode yang dimuat.
- **DEX**: `DexClassLoader` dari berkas `.jar` di penyimpanan aplikasi.

**Yang WAJIB ada di sisi klien** (ini bukan opsional):

1. **SHA-256 per modul**, dicocokkan sebelum dipakai. Tanpa ini, server yang
   dibajak bisa menyuntik kode ke HP pengguna.
2. **Tanda tangan Ed25519 atas manifes modul.** Kunci publik ditanam di APK;
   kunci privat hanya di Build otomatis Anda. Ini mencegah modul palsu.
3. **Fallback jelas**: kalau unduhan gagal atau verifikasi gagal, fitur harus
   berkata "modul belum terpasang — unduh 12 MB" dengan tombol, bukan crash.
4. **Bisa hapus modul** untuk menghemat ruang.
5. **Versi modul harus cocok dengan versi APK.** Modul lama di APK baru = crash
   `UnsatisfiedLinkError`. Simpan `abiVersion` di manifes.

### 1.2 Di mana modul disimpan

Tiga pilihan, dan rekomendasinya:

| Lokasi | Bisa diunduh | Bisa dieksekusi | Catatan |
|---|---|---|---|
| `getExternalFilesDir()` | ✅ | ✅ | Bisa dibaca PC lewat USB; terhapus saat uninstall |
| `filesDir` (internal) | ✅ | ✅ | **Paling aman**, tidak bisa diintip aplikasi lain |
| `/sdcard/PureManager/modules` | ✅ | ⚠️ | Terlihat pengguna; rawan diutak-atik |

**Rekomendasi: `filesDir/modules/`.** Tidak perlu izin tambahan di Android 10+,
dan tidak bisa dimodifikasi aplikasi lain tanpa root.

### 1.3 Rencana distribusi modul

```
GitHub Releases (repo publik atau privat dengan token)
  └── modules/
       ├── manifest.json          ← daftar modul + sha256 + tanda tangan
       ├── ffmpeg-arm64-v8a.zip   ← ± 22 MB
       ├── ocr-models.zip         ← ± 4 MB
       ├── embedding-model.zip    ← ± 60 MB
       └── whisper-tiny.zip       ← ± 75 MB
```

`manifest.json` ditandatangani; aplikasi memverifikasi tanda tangan sebelum
percaya isinya. Ini yang membedakan modul aman dari modul sembarangan.

**Catatan lisensi:** modul FFmpeg berlisensi **GPL**. Kalau diunduh terpisah
dan tidak dibundel, APK utama Anda tidak terkena GPL. Kalau dibundel di varian
Full, **seluruh APK Full jadi wajib GPL** dan sumbernya harus tersedia.
Ini bukan tafsir saya — itu syarat lisensi GPL. Saya akan tulis peringatannya
di dalam aplikasi.

---

## 2. Dua varian: Full dan Minimal

| | **Full** | **Minimal** |
|---|---|---|
| Ukuran pasang | ± 150 MB (satu ABI) | ± 15 MB |
| Fitur langsung jalan | Semua | Inti + tema |
| Modul | Sudah di dalam | Diunduh saat dipakai |
| Cocok untuk | Yang mau sekali pasang | Storage kecil, data terbatas |
| Lisensi | **Wajib GPL** (karena FFmpeg) | Apache-2.0 + modul terpisah |
| Pembaruan | Lebih berat (150 MB) | Ringan |

Keduanya memakai **kunci tanda tangan yang sama** dan **`applicationId` yang sama**
supaya bisa saling menggantikan tanpa uninstall — dengan catatan versi harus
sama atau lebih tinggi.

Kalau ingin benar-benar terpisah (bisa dipasang berdampingan), pakai
`applicationIdSuffix` berbeda, tapi konsekuensinya data tidak berbagi.

---

## 3. Fitur AI — dan temuan yang membatalkan asumsi

### 3.1 Masalah: Gemini Nano kemungkinan besar TIDAK ada di HP Anda

Dari riset Oktober 2026, daftar perangkat Gemini Nano:

| Versi Nano | Perangkat |
|---|---|
| nano-v4 | Pixel 11, Galaxy Z Fold8 / Flip8 |
| nano-v3 | Pixel 9 & 10, Galaxy S26, OnePlus 15, OPPO Find X9, vivo X300 |
| nano-v2 | OnePlus 13, Xiaomi 15, Galaxy Z Fold7, Honor Magic 7, realme GT 7 Pro |

**Dan syarat yang paling sering terlewat: `bootloader` harus terkunci.**
Perangkat dengan bootloader terbuka — yaitu **semua HP yang di-root** —
tidak didukung ML Kit GenAI sama sekali.

Artinya: **pengguna file manager dengan root, hampir pasti tidak bisa memakai
Gemini Nano.** Ini bukan detail kecil; ini membalik seluruh rencana AI.

Selain itu, batasnya juga nyata: input maksimal 4.000 token, output maksimal
255 token, kuota per aplikasi dari AICore, dan hanya jalan saat aplikasi di
depan.

### 3.2 Arsitektur yang benar: rantai empat lapis

Berdasarkan temuan di atas, desainnya harus **berlapis dengan fallback otomatis**:

```
AiRouter (memilih otomatis, bisa ditimpa pengguna)
│
├── 1. On-device lokal            ← FONDASI, selalu ada
│     LiteRT / ONNX dengan model yang diunduh sebagai modul
│     Jalan di HP apa pun, termasuk yang di-root
│
├── 2. Gemini Nano (ML Kit GenAI) ← bonus kalau perangkat mendukung
│     Cek GenerativeModel.checkStatus() saat runtime
│     Status: available / downloadable / downloading / unavailable
│
├── 3. Cloud BYOK                 ← paling pintar, butuh kunci pengguna
│     Gemini API / Groq / OpenRouter
│
└── 4. Tanpa AI                   ← selalu berfungsi
      OCR ML Kit, hash duplikat, penamaan berbasis aturan
```

**Aturan mutlak: lapis 1 dan 4 tidak boleh butuh jaringan dan tidak boleh
bergantung pada perangkat flagship.** Kalau semua AI gagal, aplikasi tetap
menjadi file manager yang utuh.

### 3.3 Soal "layanan AI gratis" — ini yang harus jujur

Anda meminta: *"jika tidak ada, alihkan ke layanan AI gratis."* Saya riset
penyedia gratisnya, dan hasilnya **tidak bisa dipakai sebagai default aplikasi**:

| Penyedia | Kuota gratis | Masalah untuk aplikasi |
|---|---|---|
| Groq | 30 RPM, **1.000/hari** per model, 200K token/hari | Kuota **per organisasi**, bukan per pengguna |
| OpenRouter `:free` | 20 RPM, **50/hari** (1.000 setelah beli $10) | Provider gratis **boleh mencatat prompt** |
| Gemini API | Kuota per model, tampil di AI Studio | **Prompt gratis dipakai memperbaiki produk Google** |

**Kesimpulan yang harus disampaikan ke pengguna:** kuota gratis itu per akun
*developer* — yaitu akun Anda, bukan akun tiap pengguna. Kalau Anda menanam
satu kunci API di aplikasi, 1.000 pengguna akan berbagi 1.000 permintaan/hari,
dan kunci itu bisa dicuri dari APK. Itu bukan solusi, itu bug.

**Jadi desainnya:**

- **Mode gratis untuk pengguna** = lapis 1 (on-device). Ini benar-benar gratis,
  tanpa batas, tanpa jaringan, tanpa kunci.
- **Cloud = BYOK** (bawa kunci sendiri). Pengguna memasukkan kunci API-nya
  sendiri; kuota gratis miliknya sendiri. Aplikasi hanya menyediakan antarmuka
  dan penyimpanan kunci yang aman (EncryptedSharedPreferences / Keystore).
- **Tidak ada kunci API yang ditanam di APK.** Kalau ada, aplikasi ini akan
  jadi sasaran penyalahgunaan dan biaya Anda meledak.

Ini bagian di mana saya harus menolak permintaan literal, karena menerapkannya
akan merugikan Anda sendiri.

### 3.4 Alur tekan-lama yang Anda minta

```
Pengguna tekan lama berkas gambar
        │
        ▼
┌──────────────────────────────────────┐
│  Banner-Arcade.png                   │
│  Apa yang ingin dilakukan?           │
├──────────────────────────────────────┤
│  ✂ Edit gambar          [LOKAL]      │  ← selalu ada
│  🏷 Beri nama otomatis  [LOKAL]      │  ← OCR + model kecil
│  🔍 Cari yang mirip     [LOKAL]      │  ← embedding
│  ✦ Tanya AI             [NANO/BYOK]  │  ← hanya kalau tersedia
└──────────────────────────────────────┘
```

Status tiap agen **ditampilkan apa adanya**: `LOKAL`, `NANO`, `BYOK`, atau
`TIDAK TERSEDIA` beserta alasannya. Tidak ada agen yang disembunyikan tanpa
penjelasan — itu prinsip yang sama dengan badge "butuh root".

---

## 4. Tab Kustomisasi Tema (permintaan Anda)

Tab tersendiri, bukan tersebar di Setelan. Isinya:

| Bagian | Pilihan |
|---|---|
| **Tema** | iOS · Pixel · Windows · Cyberpunk (+ impor tema) |
| **Mode** | Light · Dark · AMOLED · **Ikuti jadwal** (matahari) |
| **Aksen** | 12 warna siap + color picker bebas |
| **Font** | Inter · Roboto · Selawik · JetBrains Mono · font pengguna (`.ttf`) |
| **Layout** | Kepadatan (lega/normal/padat) · bentuk baris (kartu/tabel) |
| **Ikon** | 4 set ikon sesuai tema |
| **Animasi** | Penuh · Redam · **Mati** (hormati setelan sistem) |
| **Sudut** | Slider radius global |
| **Pratinjau langsung** | Perubahan terlihat seketika, tanpa keluar tab |

**Prinsip teknis:** semua ini adalah *token*, bukan kode bercabang. Kalau
pengguna memilih font `.ttf` sendiri, aplikasi memuatnya lewat
`ResourcesCompat.getFont()` — tidak perlu restart.

**Yang saya tolak:** tema yang diunduh dari internet sebagai APK terpisah.
Itu vektor serangan (kode asing di dalam aplikasi Anda) tanpa manfaat nyata;
cukup berkas JSON token yang ditandatangani.

---

## 5. Prototipe visual — bisa dilihat di HP

Dua jalur, karena yang PNG tidak bisa Anda buka nyaman di browser HP:

| Berkas | Cara pakai |
|---|---|
| `prototipe-tema.html` | **Buka di browser HP.** Ketuk untuk ganti tema/mode/aksen. Tekan lama berkas untuk melihat menu AI. |
| `mockup-tema-layout.png` | Gambar statis empat tema |
| `mockup-matriks-mode.png` | Matriks tema × mode |

Prototipe HTML memakai token yang **sama** dengan yang akan dipakai aplikasi:
`--bg`, `--surface`, `--accent`, `--radius`, `--row`, `--font`, dan `--nav`.
Model navigasi ikut berubah — tab bar, navigation bar M3, rail kiri, atau baris
perintah — bukan hanya warnanya.

---

## 6. Yang berubah dari rencana sebelumnya

| Sebelumnya | Sekarang | Alasan |
|---|---|---|
| Dynamic Feature Module | Unduh berkas + verifikasi tanda tangan | DFM butuh Play Store |
| Gemini Nano sebagai opsi utama AI | Pilihan ke-2 dari 4 | Butuh flagship **dan** bootloader terkunci |
| "AI gratis cloud" sebagai fallback | BYOK, atau tetap lokal | Kuota gratis milik developer, bukan pengguna |
| Satu APK | Full + Minimal, kunci sama | Permintaan Anda; dan lisensi GPL memisahkan keduanya |
| Tema di Setelan | **Tab Kustomisasi sendiri** | Permintaan Anda |

---

## 7. Pertanyaan yang masih perlu jawaban

1. **Server modul**: GitHub Releases (gratis, publik) atau server Anda sendiri?
   GitHub Releases cukup, tapi repo jadi publik — modul FFmpeg GPL memang harus
   tersedia publik, jadi ini tidak masalah.
2. **Kunci tanda tangan**: satu kunci untuk Full dan Minimal (bisa saling ganti),
   atau dua kunci terpisah (bisa dipasang berdampingan)? Saya sarankan **satu**.
3. **Model AI lokal mana yang dibundel sebagai modul pertama?**
   Saya sarankan **OCR (4 MB)** dulu — paling kecil, paling langsung berguna,
   dan tidak butuh GPU.
