# Log Build 008 — Pure Manager 0.3.1 · Buka, bagikan, lokasi, kembali

Tanggal: **2026-11-11**
Tahap: **T2** (menutup keluhan "fitur dasar tidak ada")
Status: **✅ APK siap uji** — run `42995207026` hijau, **38/38 tes JVM lolos**

| | |
|---|---|
| Berkas | `2026-11-11_APK_Pure-Manager-v0.3.1_Buka-Bagikan-Lokasi_DebugKey.apk` |
| Ukuran | **18.707.689 byte** |
| SHA256 | `70c860e06cebe79ca8919ffc0c9e6fd003801197822bb39785a81a4291aa5842` |
| Tanda tangan | v2 ✅ |
| Drive | `17wybc1y_S2dPklh5TQJcE8Z06IrIQCg-` |
| GitHub | https://github.com/dwp29/Synthentica/raw/build-output/PureManager-0.3.1-DEBUGKEY.apk |
| Drive (folder 02) | https://drive.google.com/file/d/17wybc1y_S2dPklh5TQJcE8Z06IrIQCg-/view |

---

## 1. Apa yang salah sebelum ini, diakui

Build 0.3.0 **tidak pernah sampai ke HP**. Kodenya tidak bisa dikompilasi:

- `verticalScroll` dan `rememberScrollState` dipakai tetapi tidak pernah diimpor.
- Toggle pilihan menugaskan `selectionMode`, yang di dalam `ScreenBody` adalah
  parameter `val`.

Yang penting bukan dua kesalahan itu, tetapi **cara saya memperbaikinya salah
dua kali**. Versi pertama tes penjaga mencari penanda akhir blok yang tidak
pernah ada, sehingga asersinya tidak pernah jalan. Versi kedua mencari pola
penugasan di jendela teks yang tidak memuat penugasan apa pun. Keduanya
**lolos pada kode yang rusak** — tes yang hijau tanpa memeriksa apa pun.

Versi ketiga membaca nama parameter setiap fungsi dan memindai seluruh badan
fungsi. Saya jalankan tes itu terhadap kode yang rusak, dan hasilnya merah
dengan pesan yang tepat. Tes baru hanya boleh dipercaya setelah begitu.

## 2. Empat fitur dasar yang sekarang ada

| Fitur | Sebelumnya | Sekarang |
|---|---|---|
| Membuka berkas | toast "menyusul (tahap 5)" | diserahkan ke aplikasi yang terdaftar untuk jenisnya |
| Menu tahan-lama | ganti nama, salin, pindah, info, hapus | **+ Buka dengan…, Bagikan** |
| Pindah lokasi | tidak ada | lembar **Lokasi**: Internal, kartu SD, folder pilihan |
| Tombol kembali | langsung menutup aplikasi | naik satu folder; saat memilih, membatalkan pilihan |

Tiga hal di balik tabel itu, yang tidak terlihat tetapi terasa:

1. **Folder SAF tadinya jalan buntu.** Folder yang pernah ditambahkan disimpan
   lalu tidak ditampilkan di mana pun. Menambah folder adalah pintu satu arah:
   setelah berpindah folder, satu-satunya cara kembali adalah menambahkannya
   lagi. Lembar **Lokasi** menutup itu.
2. **Tombol naik di folder SAF tidak melakukan apa pun.** Ia mengembalikan
   jalurnya sendiri, jadi terlihat responsif dan diam. Sekarang ia memotong id
   dokumen dan menyusun ulang URI induk.
3. **Membuka berkas tidak boleh bertanya dulu "ada aplikasinya?"** Sejak
   Android 11, jawaban pertanyaan itu disaring dan sering salah: berkas yang
   jelas punya pembuka dilaporkan tidak punya. Sekarang dicoba, lalu kegagalannya
   yang dilaporkan — dalam bahasa Indonesia, bukan nama exception.

## 3. Tiga bug yang ditemukan tes JVM, bukan oleh mata

| Bug | Akibat kalau lolos |
|---|---|
| `parentOf("/storage/emulated/0")` → `/storage/emulated` | tombol naik berjalan ke luar penyimpanan pengguna, ke folder kosong yang tidak bisa dibedakan dari folder rusak |
| `copy(folder, folder)` | rekursi sampai disk penuh (ditemukan lebih awal, tetap dijaga) |
| `validateName` memeriksa spasi setelah `trim()` | nama berakhiran spasi lolos, lalu gagal saat dibuat |

Bug pertama **baru tertangkap di CI**, bukan di sandbox: 38 tes lolos, satu gagal,
dan pesan gagalnya menyebut nama berkas dan nama parameter. Itu fungsi tes yang
sebenarnya — bukan upacara.

## 4. Dua kegagalan CI yang bukan kesalahan kode

| Run | Gejala | Sebab |
|---|---|---|
| `42993726608` | 38/38 tes lolos, build merah | langkah verifikasi mencari `versionName='0.3.0'` yang ditulis tangan di sembilan tempat |
| `42994597044` | APK benar, 38/38 hijau, gagal saat publikasi | versi diekspor sebagai `PM_VERSION`, dibaca sebagai `VERSION`; `set -u` menghentikannya |

Keduanya sudah ditutup dengan **satu sumber versi** yang dibaca dari
`build.gradle.kts`, dan dua tes penjaga yang gagal kalau versi atau nama artefak
ditulis ulang dengan tangan.

## 5. Tes

- **JVM: 38** (naik dari 17) — termasuk 20 tes untuk `Support`, satu kelas baru
  berisi keputusan yang tadinya tidak bisa diuji sama sekali.
- **Penjaga sumber Python: 63** — termasuk penjaga bahwa tesnya sendiri tidak
  boleh lolos pada kode rusak.

## 6. Masih terbuka

| Hal | Status |
|---|---|
| Tema iOS / glass / blur sesuai foto | **belum sesuai** — belum disentuh di build ini |
| Indeks/sorotan bagian (A–Z) seperti iOS | belum ada |
| Thumbnail gambar | belum ada |
| Progres salin + batal | belum ada; salin besar masih terasa macet |
| "Coba dalami reset" | **belum saya kerjakan — perlu penjelasan** |

Soal yang terakhir: saya tidak tahu apa yang harus di-reset. Ada tiga kemungkinan
dan saya tidak mau menebak:

1. **Reset aplikasi** (hapus data, mulai dari awal) — tombol di Setelan.
2. **Reset tema** ke bawaan — kalau tema diutak-atik lalu tidak bisa kembali.
3. Bukan reset, melainkan **riset** — salah tulis.

Kalau yang dimaksud (1) atau (2), keduanya pekerjaan kecil dan bisa masuk build
berikutnya. Kalau (3), saya perlu tahu riset tentang apa.

## 7. Cara memasang

1. Unduh APK dari tautan GitHub atau Drive di atas.
2. Pasang di atas 0.2.1 (kunci tangannya sama, jadi langsung menimpa).
3. Saat pertama dibuka, izinkan **Semua berkas**, atau tambah satu folder lewat
   **⊕**.

Kalau ada yang aneh, sebutkan langkahnya — layar apa, tombol apa, dan apa yang
diharapkan. Itu lebih cepat saya perbaiki daripada tangkapan layar saja.
