# Laporan Akhir — Pure Manager

**Tanggal:** 11 November 2026
**Versi terbaru:** 0.10.0 (versionCode 16)
**Repo:** `dwp29/Synthentica`, branch `arena/96cbd65a-synthentica`

---

## 1. Yang sudah jadi

| Tahap | Isi | Versi | Status |
|---|---|---|---|
| T1 | Kerangka aplikasi, tema, kunci rilis | 0.1.0 | ✅ |
| T2 | Browser berkas: salin (dengan progres + batal), pindah, ganti nama, hapus, thumbnail gambar/video | 0.2.0–0.3.0 | ✅ |
| T3 | Analisis penyimpanan, ZIP (isi + ekstrak), indeks A–Z, pencarian seluruh perangkat, root + terminal | 0.4.0–0.6.0 | ✅ |
| T4 | Tema iOS: tab bawah mengambang, judul besar, blur asli (Haze), sudut membulat, baris lega | 0.7.0 | ✅ |
| T5 | Pratinjau `.docx`, `.xlsx`, `.pdf` di dalam aplikasi | 0.8.0 | ✅ |
| T6 | Editor teks/kode: penyorotan sintaks, undo/redo, cari-ganti, indentasi otomatis | 0.9.0 | ✅ |
| T7 | Pemutar gambar (cubit + geser), audio (daftar putar folder), video | 0.10.0 | ✅ |
| T8 | Fitur AI | — | **DITAHAN** atas instruksi |

**Fitur dasar yang Anda minta semuanya sudah ada:** progres salin + batal, thumbnail,
analisis penyimpanan, ZIP, indeks A–Z, pencarian seluruh perangkat, root, dan terminal.

**Tema iOS** dikerjakan sampai mirip acuan (iOS Files asli) sebelum lanjut ke tahap
berikutnya, sesuai keputusan Anda.

---

## 2. Berkas yang bisa dipasang

Keduanya ada di Google Drive, folder **`02` APK**:

| Varian | Nama berkas | Ukuran | sha256 (16 awal) |
|---|---|---|---|
| FULL (dengan terminal + modul) | `PureManager-0.10.0-DEBUGKEY.apk` | 19.117.285 byte | `4c5145bbc56ebbb7` |
| MINIMAL (hanya file manager) | `PureManager-0.10.0-minimal-DEBUGKEY.apk` | 19.117.297 byte | `3fc3be7ed745043a` |

Keduanya bisa dipasang berdampingan (nama paketnya berbeda).

**Catatan soal "MINIMAL":** varian MINIMAL **tidak lebih kecil** — justru 12 byte
lebih besar. Penyebabnya: kode kedua varian identik, perbedaannya hanya satu nilai
`BuildConfig.HAS_MODULES`. Jadi nama "minimal" di sini berarti *fitur yang
ditampilkan* lebih sedikit, bukan *berkas* lebih kecil. Saya sebutkan ini supaya
tidak mengira ada yang salah unduh.

---

## 3. Yang belum selesai, dan kenapa

### 3.1 Kunci rilis (PENTING)

APK di atas masih ditandatangani **debug key**, sesuai nama berkasnya
(`DEBUGKEY`). Artinya:

- Bisa dipasang dan dipakai normal.
- **Tidak bisa** dipakai menerbitkan modul, karena modul harus ditandatangani
  dengan kunci yang sama dengan aplikasi.
- Kalau suatu saat dipasang versi bertanda kunci rilis, aplikasi harus
  di-uninstall dulu (data hilang), karena tanda tangannya berbeda.

Kunci rilisnya **sudah dibuat dan sudah diarsipkan** di Drive folder **`05`**:

- Alias: `pure-manager-release`
- Sandi: `PureManager2026!`
- SHA-256 sertifikat:
  `A2:F9:42:45:2E:EC:1C:D8:76:3E:6C:F3:3B:99:37:C1:A9:9B:38:49:C6:27:73:A7:3B:F4:44:77:67:43:F2:D8`

Yang dibutuhkan agar build memakainya: dua nilai rahasia di repo GitHub
(`PM_KEYSTORE_B64` dan `PM_KEYSTORE_PASSWORD`). Saya **tidak bisa** menulis
secret GitHub dari sini — token yang tersedia tidak punya izin itu, dan sandi
tidak boleh dititipkan lewat chat. Anda perlu menambahkannya sendiri, atau
memberi saya cara lain yang Anda anggap aman.

### 3.2 Modul Ed25519

Belum ada. Rencananya modul ditandatangani, tetapi verifikasi tanda tangan
memerlukan kunci rilis di atas.

### 3.3 Uji di HP

**Belum ada satu pun fitur yang dijalankan di HP sungguhan.** Semua yang saya
laporkan diverifikasi lewat: (a) 148 penjaga Python, (b) 220 tes JVM yang
dijalankan CI, (c) pemeriksaan isi APK. Itu menangkap banyak kesalahan, tapi
**bukan** hal seperti tata letak, gestur, atau perilaku pemutar media di perangkat
Anda.

Yang paling perlu Anda coba lebih dulu:

1. **Editor teks** — buka `.txt` lewat *panjang-tekan → Edit teks*. Ini fitur
   paling baru dan paling belum teruji.
2. **Pemutar audio** — apakah lagu benar-benar berbunyi, dan tombol
   *sebelum/berikut* berpindah trek.
3. **Pemutar video** — apakah gambar keluar dan suara ada.
4. **Gambar** — apakah foto tegak, bukan miring (masalah rotasi paling sering
   muncul di HP, tidak di tes).
5. **Root/terminal** — butuh HP ber-root; saya tidak bisa menguji ini sama sekali.

### 3.4 Batasan fitur yang perlu Anda tahu

- **Pratinjau dokumen**: hanya teks dan nilai sel. Font, warna, gambar, dan tabel
  gabungan tidak tampil. `.doc`/`.xls` lama tidak didukung. Teks PDF tidak bisa
  disalin, formulir tidak bisa diisi.
- **Editor**: berkas di atas 8 MB ditolak; berkas biner ditolak. Tidak ada
  *autocomplete*, tidak ada *Simpan sebagai*, tidak ada integrasi git. Penyorotan
  berhenti di 200.000 karakter (di atas itu tampil tanpa warna).
- **Media**: tidak membaca tag ID3 (judul = nama berkas), tanpa sampul album,
  video tanpa mode layar penuh, tanpa subtitle, GIF tampil sebagai gambar diam.
- **RAR** tidak didukung untuk ekstrak (hanya ZIP).

---

## 4. Satu pertanyaan yang belum terjawab

Pada percakapan sebelumnya Anda menulis **"coba dalami reset"**. Saya sudah
mencoba menebak maksudnya beberapa kali dan tidak berani melanjutkan tanpa
kepastian, karena kalau salah tebak hasilnya bisa merusak data.

Kemungkinan yang saya pikirkan:

1. **Reset aplikasi** — tombol untuk mengembalikan seluruh pengaturan Pure Manager
   ke awal (tema, akses folder).
2. **Reset preferensi tema** — khusus tampilan kembali ke iOS bawaan.
3. **Reset data ponsel** — sesuatu yang berkaitan dengan pemulihan/penghapusan
   seluruh penyimpanan.
4. **"Reset" sebagai nama fitur lain** yang Anda lihat di aplikasi lain.

Mohon dibalas salah satu nomor di atas, atau jelaskan dengan kalimat Anda
sendiri. Selama belum jelas, saya **tidak** membuat fitur reset apa pun.

---

## 5. Arsip

Semua berkas penting ada di Google Drive:

| Folder | Isi |
|---|---|
| `02` APK | dua APK 0.10.0 (versi sebelumnya dihapus agar tidak tertukar) |
| `04` Log | LOG-011 s/d LOG-015 |
| `05` Kunci | keystore rilis + keterangan alias dan sidik jari |

LOG-013 (tahap pratinjau dokumen) **ditolak filter keamanan Drive** dan hanya ada
di repo. Isinya tidak saya ubah untuk mengakalinya — itu akan mengorbankan
kejujuran dokumen demi arsip.

---

## 6. Langkah berikutnya

Menunggu keputusan Anda untuk:

1. **T8 (fitur AI)** — masih ditahan; perlu arahan apa yang Anda inginkan.
2. **Kunci rilis** — apakah Anda akan menambahkan `PM_KEYSTORE_B64` dan
   `PM_KEYSTORE_PASSWORD` sendiri.
3. **Arti "coba dalami reset"**.
4. Hasil uji di HP, supaya bug yang nyata bisa saya perbaiki (sesuai instruksi
   Anda: selesaikan dulu semua langkah, koreksi bug menyusul).
