# Saran: File Manager Android dengan Root + Fitur MT Manager

Status: **dokumen saran, belum ada kode.** Tanggal: 2026-10-31.
Ditulis setelah pelajaran dari proyek Manager 6.1 (lihat `docs/` lain di repo ini).

Keputusan yang sudah dikunci oleh Anda (2026-10-31):

| Hal | Keputusan | Akibatnya |
|---|---|---|
| Distribusi | **Di luar Play Store** (APK langsung) | `MANAGE_EXTERNAL_STORAGE` bebas dipakai tanpa peninjauan manual; fitur yang ditolak Play bukan penghalang |
| Root | **KernelSU atau Magisk**, keduanya harus jalan | Wajib `libsu`; tidak boleh ada asumsi khusus satu implementasi |
| Tanpa root | **Harus berfungsi normal** | Root adalah lapisan opsional di atas aplikasi yang sudah utuh, bukan syarat |

Tiga keputusan ini saling menguatkan dan menyederhanakan banyak hal — lihat §11.

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

## 10. Yang masih perlu Anda jawab

Dari lima pertanyaan sebelumnya, dua sudah terjawab (§ header). Tiga tersisa:

1. **Target Android minimum.** Saran: **Android 11 (API 30)**, karena di situlah model
   storage modern berlaku. Di bawah itu Anda harus memelihara dua jalur kode sekaligus
   tanpa manfaat nyata.
2. **Prioritas pertama:** file manager sehari-hari, atau alat bedah APK? Kalau Anda
   memilih bedah APK lebih dulu, saya sarankan menolak pilihan itu — lihat §7.
3. **Satu orang atau ada tim?** Ini menentukan apakah tahap 5 realistis atau sebaiknya
   tidak dijanjikan sama sekali.

---

## 11. Konsekuensi dari keputusan Anda

Bagian ini yang berubah karena jawaban Anda: **di luar Play**, **KSU atau Magisk**,
**jalan tanpa root**.

### 11.1 Di luar Play Store — ini melonggarkan banyak hal

- **`MANAGE_EXTERNAL_STORAGE` tidak perlu ditinjau siapa pun.** Ini izin yang di Play
  ditolak untuk banyak aplikasi. Di luar Play, Anda tetap wajib mengarahkan pengguna
  ke layar setelan "Semua akses file", tapi tidak ada risiko penolakan.
- **Fitur yang ditolak Play jadi mungkin** — misalnya akses penuh `Android/data`.
  Kalau nanti Anda tetap ingin masuk Play, fitur-fitur itu harus jadi build terpisah.
- **Anda bertanggung jawab penuh atas pembaruan sendiri.** Tidak ada Play yang
  memaksa update. Konsekuensi: **jangan pernah ganti keystore**. Kalau kunci hilang,
  semua pengguna harus uninstall — persis yang baru terjadi. Ini alasan nomor satu
  untuk menyimpan kunci di tiga tempat sejak hari pertama.
- **Tanda tangan APK Anda adalah identitas Anda.** Tidak ada Play App Signing yang
  menyelamatkan. Pelajaran dari Manager 6.1 berlaku mutlak di sini.

### 11.2 KSU atau Magisk — `libsu` wajib, dan ada satu jebakan

`libsu` dari topjohnwu menangani keduanya dengan cara yang sama: memanggil `su`,
membaca hasil, shell bersama. Yang perlu Anda sadari:

| Hal | Magisk | KernelSU |
|---|---|---|
| Deteksi versi | `su -v` mengembalikan nomor versi | `su -v` juga ada, tapi formatnya lain |
| Manajer aplikasi | `magisk --list` | `ksud` lewat shell |
| Mount `/system` rw | `magisk --mount-master` | Perilaku berbeda, tergantung mode |
| Modul | `/data/adb/modules` | `/data/adb/modules` (sama) |

**Jebakan yang sudah menggigit di Manager 6.1:** `su --mount-master` dijalankan lebih
dulu daripada `su` polos, dan hasilnya root tampak tidak terdeteksi. **Selalu coba
`su` polos lebih dulu**, baru jatuh ke varian khusus kalau perlu. Ini sudah tercatat
di repo ini sebagai perbaikan `fix(root): su polos harus jalan lebih dulu`.

**Yang harus diuji, bukan diasumsikan:** satu perangkat Magisk dan satu perangkat
KernelSU, minimal. Kalau hanya diuji di satu, Anda tidak akan tahu bedanya sampai
pengguna melapor.

### 11.3 Jalan tanpa root — ini yang mengubah arsitektur

Karena aplikasi harus berguna **tanpa root**, root tidak boleh jadi fondasi.
Root adalah **lapisan tambahan**. Konsekuensi desainnya konkret:

**a. Lapisan akses berkas harus punya dua implementasi di balik satu antarmuka.**

```
FileOps (antarmuka)
├── SafeFileOps     -> MediaStore + SAF, untuk mode tanpa root
└── RootFileOps     -> shell root via libsu, untuk mode root
```

UI tidak boleh tahu mana yang aktif. Kalau ada `if (isRoot)` yang berserakan di
tampilan, Anda akan menulis ulang semuanya saat menambah implementasi ketiga
(misalnya: shizuku/ADB).

**b. Dua mode ini punya batasan berbeda — tampilkan, jangan sembunyikan.**

| Operasi | Tanpa root | Dengan root |
|---|---|---|
| Baca/tulis storage utama | Ya (all-files access) | Ya |
| `Android/data` aplikasi lain | **Tidak** | Ya |
| `/system`, `/vendor`, `/data` | Tidak | Ya |
| `chmod` / `chown` | Sebagian (milik sendiri) | Ya |
| Mount rw | Tidak | Ya |
| Jalankan skrip shell | Tidak | Ya |

Saran UI: tampilkan badge kecil "butuh root" pada aksi yang tidak tersedia, dan
saat ditekan beri penjelasan — **bukan** tombol mati tanpa alasan. Pengguna harus
paham kenapa, karena ini yang membedakan aplikasi bagus dari aplikasi membingungkan.

**c. Turunkan kelas, jangan gagal.** Kalau root dicabut di tengah sesi (pengguna
mencabut izin), aplikasi harus otomatis turun ke `SafeFileOps` dan tetap jalan,
bukan crash. Ini skenario nyata: orang mencabut root saat aplikasi terbuka.

**d. Arsip, thumbnail, cari, tema, editor teks — semuanya jalan tanpa root.**
Justru ini bagian terbesar aplikasi. Kalau tahap 1 dikerjakan benar, aplikasi sudah
layak dipakai sebelum root disentuh sama sekali.

### 11.4 Yang berubah dari urutan pengerjaan

Tahap 2 di §7 (root) sekarang menjadi **tambahan**, bukan fondasi. Urutannya bisa
dibalik: bangun dulu seluruh pengalaman tanpa root, lalu tambahkan root sebagai
lapisan. Ini lebih aman karena:

- Anda punya aplikasi yang bisa diuji di perangkat apa pun, termasuk yang belum root.
- Bug root tidak memblokir fitur lain.
- Kalau dukungan root bermasalah di satu OEM, aplikasi tetap berguna.

Satu penyesuaian: **antarmuka `FileOps` harus dibuat sejak tahap 1**, walau baru
implementasi `SafeFileOps` yang ada. Menambahkan abstraksi itu belakangan berarti
membongkar seluruh UI — itu kesalahan yang mahal dan mudah dihindari.

### 11.5 Distribusi tanpa Play: yang harus disiapkan

- **Kanal pembaruan sendiri.** Cek versi ke GitHub Releases (atau server Anda), beri
  tahu pengguna kalau ada versi baru. Tanpa ini, pengguna akan tertinggal di versi lama.
- **Dua ABI atau universal.** `arm64-v8a` menutup hampir semua HP modern, tapi
  `armeabi-v7a` masih dipakai perangkat lama. Native lib untuk arsip/7z membuat
  ukuran APK naik — pertimbangkan ABI split.
- **Peringatan sideload.** Pengguna harus menyalakan "instal dari sumber tidak dikenal".
  Jelaskan di README, jangan biarkan mereka menebak.
- **Kunci tanda tangan disimpan di tiga tempat** (lokal terenkripsi, penyimpanan
  offline, dan satu salinan terpisah) — beserta sidik jari SHA-256 di dokumen.
  Ini bukan formalitas; ini yang mencegah bencana yang sudah terjadi sekali.
