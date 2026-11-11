# Saran: File Manager Android dengan Root + Fitur MT Manager

Status: **dokumen saran, belum ada kode.** Tanggal: 2026-10-31.
Ditulis setelah pelajaran dari proyek Manager 6.1 (lihat `docs/` lain di repo ini).

---

## 0. Ringkasan jujur di depan

Yang Anda minta itu **bukan satu aplikasi**, tapi sekitar **lima aplikasi** yang digabung:
file manager, editor arsip, APK editor/reverse-engineering suite, klien jaringan,
dan design system. MT Manager mencapai itu setelah belasan tahun dan tim kecil.
Itu bukan alasan untuk tidak mencoba — tapi kalau semuanya dikerjakan sekaligus,
hasilnya akan seperti Manager 6.1 sebelumnya: banyak fitur, tidak ada yang benar-benar selesai.

Saran utama saya: **tentukan dulu satu hal yang bukan fitur**, yaitu cara aplikasi
ini berbicara dengan root. Salah memilih di sini membuat semua fitur lain di atasnya rapuh,
dan itulah yang baru saja terjadi.

---

## 1. Keputusan paling penting: bagaimana app bicara ke root

Ini akar masalah "root gak terdeteksi" di proyek sebelumnya.

| Pendekatan | Cara kerja | Kelebihan | Kekurangan |
|---|---|---|---|
| **A. Klien `libsu`** (rekomendasi) | App memanggil `su` yang sudah ada di perangkat (Magisk/KernelSU/APatch) lewat shell bersama | Tidak peduli root mana yang dipakai; tidak perlu kernel cocok; tidak ada urusan sertifikat | Pengguna wajib sudah root; tidak bisa mengatur kebijakan root sendiri |
| B. Bundel KernelSU sendiri | App = manager + kernel module | Kontrol penuh | Wajib kernel cocok, sertifikat dipaku, satu versi salah = semua mati |
| C. Tulis `su` sendiri | Implementasi daemon sendiri | Otonom | Sangat berbahaya, mudah jadi celah keamanan, tak sepadan |

**Rekomendasi: A.** File manager yang baik adalah **warga negara** dari ekosistem root,
bukan penguasa ekosistem root. Dengan `libsu`:

- Satu shell root dipakai bersama, jadi operasi massal cepat (tidak spawn `su` per berkas).
- Deteksi root cukup: `su -v` berhasil atau tidak. Tidak ada sertifikat, tidak ada pinning.
- Kalau pengguna pindah dari Magisk ke KernelSU, aplikasi tetap jalan.

Pelajaran dari Manager 6.1: aplikasi mati bukan karena kodenya salah, tapi karena
**identitas tanda tangannya** tidak diterima kernel. Jangan ulangi pola itu di sini.

---

## 2. Storage modern: yang benar dan yang mitos

Android 11+ (dan wajib target Android 16 sejak 31 Agustus 2026 kalau lewat Play):

- **`MANAGE_EXTERNAL_STORAGE` wajib** untuk file manager yang jujur. Ini bukan runtime
  permission — pengguna harus menyalakannya di layar setelan khusus. Google Play
  **meninjau manual** dan mengizinkannya untuk kategori file manager. Kalau app
  disebar di luar Play (seperti MT Manager), ini tidak jadi masalah.
- **Jangan andalkan `requestLegacyExternalStorage`** — sudah mati sejak API 30.
- **`Android/data/` milik app lain tetap tidak bisa diakses** walau punya all-files access
  di Android 11+. Ini batasan sistem. Rencanakan UI-nya supaya folder itu tampil
  tapi ditandai "butuh akses khusus", bukan error misterius.
- **Akses root melewati semua batasan di atas** — itu justru alasan fitur root penting:
  dengan root, `Android/data` bisa dibaca. Tapi ini harus eksplisit "mode root", bukan default.

---

## 3. Arsitektur tema — jangan modelkan sebagai daftar tema

Ini kesalahan desain yang paling sering terjadi dan paling mahal untuk diperbaiki nanti.

Permintaan Anda: tema iOS, Pixel, Windows, Cyberpunk, dark, night, AMOLED.

Perhatikan: **dark / night / AMOLED bukan tema**, itu **mode**. Kalau ketujuhnya
dijadikan satu daftar datar, Anda akan dapat 7 × 7 kombinasi yang tidak konsisten.

Modelkan sebagai **tiga sumbu ortogonal**:

```
Tema (bahasa visual)   ×   Mode (terang/gelap)   ×   Aksen
iOS                        Light                   (per tema)
Pixel                      Dark
Windows                    AMOLED
Cyberpunk
```

Yang membedakan tema bukan hanya warna, tapi **bentuk dan ritme**:

| Tema | Sudut | Elevasi | Tipografi | Ikon | Kepadatan |
|---|---|---|---|---|---|
| iOS | 12–20 dp | bayangan lembut, blur | SF-like (Inter) | rounded, garis 1.5 | sedang |
| Pixel | penuh (pill) | tonal, tanpa bayangan | Roboto/Google Sans | Material Symbols | lega |
| Windows | 4 dp (bukan 0) | datar, border 1px | Segoe-like (Selawik) | Fluent | padat |
| Cyberpunk | 2 dp | glow, bukan bayangan | mono + display | garis neon | padat |

Implementasinya: satu **set token** (`colorScheme`, `shapes`, `typography`, `elevation`,
`motionSpec`) yang di-inject. Komponen UI **tidak boleh** tahu tema mana yang aktif —
kalau ada `if (theme == IOS)` di dalam composable, arsitekturnya sudah gagal.

Ini juga yang membuat "animated" jadi masuk akal: animasi adalah bagian dari token
(`motionSpec`), bukan efek tempelan. iOS = pegas halus, Pixel = cepat dan langsung,
Cyberpunk = glitch/scanline yang memang disengaja.

**AMOLED** khususnya bukan "hitam lebih pekat": harus mematikan elevasi tonal,
karena di atas hitam murni bayangan tidak terlihat — pakai border atau perbedaan
kontras, bukan `surfaceVariant` yang mendekati hitam.

---

## 4. Peta fitur MT Manager, dipilah menurut realistis-tidaknya

Riset ke fitur MT Manager yang sebenarnya (v2.15–2.26):

### Tingkat 1 — fondasi, wajib ada sebelum apa pun
- Dual-pane, tab, bookmark, riwayat
- Copy / move / rename / delete / batch, dengan **progress + batal**
- Salin lintas penyimpanan (internal ↔ SD ↔ OTG) tanpa kehabisan memori
- Cari nama + isi (isi butuh indeks atau streaming, bukan load semua)
- Izin & pemilik berkas, ubah mode `chmod`/`chown`
- Arsip: **ZIP baca/tulis di tempat**, TAR/TAR.GZ baca/tulis, **RAR/7z baca**
  (menulis RAR tidak mungkin secara legal — formatnya tertutup)
- Editor teks (encoding UTF-8/UTF-16/GBK, besar berkas puluhan MB)
- Hex editor (jangan load seluruh berkas ke RAM — pakai jendela)
- Thumbnail: gambar, video, PDF, ikon APK, pratinjau font

### Tingkat 2 — pembeda, dan di sinilah nilainya
- APK dibuka seperti folder (edit ZIP di tempat), lalu zipalign + tanda tangan sendiri
- Editor AXML (binary XML) dan `resources.arsc`
- Editor DEX / Smali
- Diff teks dan diff DEX
- Klien **FTP / FTPS / SFTP / SMB / WebDAV**
- Server HTTP di HP supaya PC bisa mengunduh lewat Wi-Fi

### Tingkat 3 — panjang, dan sebagian bermasalah secara etika
Fitur yang di MT Manager dipakai untuk membongkar aplikasi orang lain:
"signature killer", "remove signature verification", anti-split, clone APK dengan
nama paket lain, auto-translate APK.

**Saran saya: jangan masukkan ini di rilis pertama, dan pikirkan ulang apakah perlu sama sekali.**
Alasannya bukan hanya hukum (di banyak yurisdiksi ini membantu pelanggaran hak cipta),
tapi juga praktis: fitur-fitur inilah yang paling sering rusak tiap Android naik versi,
dan reputasi aplikasi Anda akan dinilai dari situ. Kalau tetap ingin, pisahkan sebagai
modul terpisah yang diunduh terpisah, dengan peringatan jelas.

---

## 5. Klarifikasi teknis yang perlu Anda tahu sekarang

**MTP tidak bisa dibuat oleh aplikasi.** MTP adalah protokol di mana **PC melihat HP**.
Itu dijalankan oleh sistem Android, bukan oleh app pihak ketiga. Yang bisa Anda buat:

- HP sebagai **klien** SMB/FTP/SFTP ke PC atau NAS (ini yang berguna)
- HP sebagai **server** HTTP/FTP supaya PC menarik berkas dari HP
- USB: lewat SAF atau `UsbManager` (AOA), bukan MTP

Jadi kalau ada yang menjanjikan "app dengan fitur MTP", yang dimaksud biasanya
salah satu dari tiga hal di atas.

**RAR tulis = tidak mungkin.** Baca bisa (`junrar` atau `unrar` native), tulis tidak.

**7z tulis** bisa lewat `sevenzipjbinding`, tapi menambah ~2 MB native lib per ABI.
Pertimbangkan: ZIP/TAR tulis, 7z/RAR baca saja untuk versi pertama.

---

## 6. Fondasi teknis yang saya sarankan

| Kebutuhan | Pilihan | Catatan |
|---|---|---|
| UI | **Jetpack Compose** + Material 3 | Token tema mudah di-inject, animasi ekspresif |
| Root | **libsu** (Magisk) | Lihat §1 — ini keputusan nomor satu |
| Arsip | `commons-compress` + `junrar` + `sevenzipjbinding` | ZIP baca/tulis, RAR baca |
| Thumbnail | **Coil 3** + loader kustom | Cache disk + memori, batalkan saat scroll |
| Teks besar | `RandomAccessFile` + jendela baris | Jangan pernah `readText()` untuk berkas > 10 MB |
| Hex | baca per 4–8 KB | Sama |
| Smali/DEX | `smali/baksmali` (dexlib2) | Ini library yang sama yang dipakai APKTool |
| ARSC | `arsc-lib` / `apk-parser` | Riset dulu kualitasnya; ARSC tulis itu rumit |
| Font | bundel 3–4 font saja | Windows→Selawik (lisensi OFL), iOS→Inter, Cyberpunk→mono |
| Gambar | WebP + AVIF untuk aset | APK lebih kecil |

**Jangan mulai dari nol kalau tidak perlu.** Untuk mesin berkas (bukan UI),
ada proyek open source matang: *Material Files* (GPL-3.0), *Amaze* (GPL-3.0).
Kalau memakai, Anda **wajib** merilis sumber dengan lisensi sama. Kalau Anda ingin
kode tertutup, tulis mesin berkas sendiri — itu pekerjaan besar tapi bisa.

---

## 7. Yang paling menentukan berhasil-tidaknya: urutan pengerjaan

Saran saya, dalam 5 tahap. Setiap tahap harus **bisa dipakai sehari-hari** sebelum lanjut.

**Tahap 1 — "file manager yang tidak memalukan" (target realistis: 4–6 minggu)**
Dual-pane, navigasi, copy/move/delete dengan progress, arsip ZIP/TAR, thumbnail,
cari nama, tema iOS + Pixel + mode gelap. Tanpa root.

**Tahap 2 — "root yang benar" (2–4 minggu)**
Integrasi `libsu`, jelajah `/system`, mount rw, chmod/chown, jelajah `Android/data`.
Uji di **minimal 3 perangkat** dengan root berbeda (Magisk, KernelSU, APatch).

**Tahap 3 — "editor" (6–10 minggu)**
Teks, hex, editor ZIP di tempat, tanda tangan APK + zipalign.

**Tahap 4 — "jaringan" (3–5 minggu)**
SMB, SFTP, FTP, server HTTP.

**Tahap 5 — "bedah APK" (paling lama, tidak ada estimasi jujur)**
AXML, ARSC, DEX/Smali. Ini setara membangun ulang APKTool di dalam HP.

Total realistis untuk satu orang: **1–1,5 tahun** sampai semua tingkat 2 stabil.

---

## 8. Jebakan yang sudah terbukti menggigit di proyek Anda

Ini bukan teori — semuanya sudah terjadi di Manager 6.1:

1. **Jangan pernah regenerasi keystore.** Tentukan `applicationId` dan keystore
   **sekali di awal**, lalu simpan di 3 tempat dan catat sidik jari SHA-256-nya
   di dokumen. Kehilangan kunci = pengguna wajib uninstall, dan itu merusak kepercayaan.

2. **Jangan simpan apa pun hanya di `/tmp`.** Semua hasil build harus punya rumah
   yang tahan reset, dan diverifikasi dengan hash — bukan dengan ingatan.

3. **Uji di perangkat fisik sejak tahap 1.** Manager 6.1 lulus semua test statis
   tapi tidak pernah dirender di HP. Test yang tidak pernah dijalankan di perangkat
   nyata bukan bukti.

4. **Satu fitur, satu bukti.** "Sudah dibuat" dan "sudah terbukti bekerja" adalah
   dua hal berbeda. Tulis matriks fitur dengan kolom: *belum / dibuat / diuji di
   emulator / diuji di perangkat*.

5. **Root butuh matriksuji perangkat.** Satu HP bukan bukti. Root berbeda-beda
   perilakunya di tiap OEM (Xiaomi, Samsung, Pixel sangat berbeda soal `/system` rw).

---

## 9. Rekomendasi akhir

Kalau saya yang memutuskan:

1. **Mulai dari file manager yang solid + root via `libsu`**, bukan dari fitur MT Manager.
   MT Manager hebat karena fondasi file manager-nya sudah sempurna sebelum ada
   editor DEX.
2. **Tema sebagai token, bukan if-else.** Itu kekuatan yang sudah terbukti di
   proyek sebelumnya, dan sekarang bisa dibuat benar.
3. **Tunda fitur "bedah APK" sampai tahap 5.** Jangan biarkan fitur itu menarik
   Anda mengerjakan yang sulit lebih dulu.
4. **Putuskan sekarang:** aplikasi ini untuk Play Store atau di luar Play?
   Jawaban itu mengubah desain permission, distribusi, dan fitur mana yang boleh ada.
5. **Tulis dulu satu halaman "apa yang TIDAK akan dibuat di v1"**. Proyek gagal
   karena lingkup, bukan karena kurang fitur.

---

## 10. Pertanyaan yang perlu Anda jawab sebelum mulai

1. Root apa yang dipakai di HP Anda sekarang — Magisk, KernelSU, atau APatch?
2. Aplikasi ini akan masuk Play Store, atau disebar sebagai APK langsung?
3. Prioritas pertama: **file manager sehari-hari** atau **alat bedah APK**?
4. Target perangkat minimum (Android 11? 13?) — menentukan banyak keputusan storage.
5. Anda mengerjakan sendiri atau ada orang lain? Ini menentukan apakah tahap 5 realistis.
