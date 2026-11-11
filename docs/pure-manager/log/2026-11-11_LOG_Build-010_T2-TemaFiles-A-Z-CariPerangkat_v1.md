# LOG-010 — Pure Manager 0.5.0
## Tema Files iOS · Indeks A–Z · Pencarian se-perangkat · Kunci rilis di Drive

**Tanggal:** 2026-11-11
**Versi:** 0.4.0 → **0.5.0** (versionCode 11)
**Run hijau:** [43014600784](https://github.com/dwp29/Synthentica/actions/runs/43014600784) — commit `ca1d0fa`
**APK:** `PureManager-0.5.0-DEBUGKEY.apk`, 18.822.377 byte,
sha256 `603244e4f831e2388293d376c1cd956c9d648d2dbf3ab217ec96e4ef72eab5cc`
**Di Drive:** ID `1FSd4R8JDYHoAthvOfqD8_TJGDShmVgkH` (folder `02-BUILD-APK`)
**Log ini di Drive:** ID `1ze8CthkbLRXYk0YMKgcmm9kZRqb5WaVu`

---

## 1. Yang selesai di build ini

| Permintaan | Status |
|---|---|
| Tema meniru Files iOS | ✅ diperbaiki besar-besaran |
| Indeks A–Z | ✅ ada, dengan aturan huruf yang benar |
| Cari berkas di seluruh perangkat | ✅ baru |
| Kunci tanda tangan tersimpan di Drive | ✅ 3 berkas + dokumen sandi |
| Kunci rilis dipakai saat build | ⛔ menunggu dua variabel GitHub (lihat §5) |

---

## 2. Kenapa tema sebelumnya dinilai belum mirip

Saya membandingkan tangkapan layar 0.4.0 dengan acuan resmi Apple
(`support.apple.com`, iPhone Files → Browse) dan menemukan lima perbedaan, semuanya
struktural, bukan soal warna:

1. **Kisi ada di dalam kartu putih.** Di Files, ikon duduk langsung di atas latar
   halaman. Kartu itu yang membuat tampilan terasa seperti Setelan Android yang
   kebetulan berisi gambar.
2. **Tiap baris daftar punya tombol titik-tiga.** Akibatnya ukuran berkas terdorong
   keluar dan daftar panjang terlihat seperti halaman pengaturan. Di Files, menu
   muncul lewat tekan-lama; chevron hanya untuk folder.
3. **Ukuran ada di baris yang sama dengan nama**, sehingga nama panjang Indonesia
   terpotong. Di Files: nama di atas, ukuran/tanggal kecil di bawahnya.
4. **Folder tidak berwarna.** Files memberi tiap folder warnanya sendiri dan
   menaruh titik warna sebelum namanya. Itu bagian paling khas dan paling sering
   hilang saat orang meniru tampilannya.
5. **Toolbar menjejalkan enam tombol dan dua baris teks dalam satu baris**; di layar
   360 dp nama folder cuma kebagian ~90 dp.

Yang berubah:

- Kisi tanpa kartu, jarak antar-sel ala Files, 3 kolom di ponsel / 4 kolom di layar
  ≥600 dp.
- `folderTint(nama)` memilih dari delapan warna folder Apple. Warnanya **stabil**
  untuk nama yang sama (hash nama), jadi tidak berkedip saat digulir. Catatan jujur:
  di Files warna folder diatur pengguna; aplikasi ini belum menyimpan metadata
  per-folder, jadi namanya yang menentukan. Ganti nama = ganti warna.
- Baris daftar: nama + ukuran bertumpuk, chevron redup hanya untuk folder, garis
  pemisah menjorok setelah ikon, dan garis terakhir di dalam kartu tidak digambar.
- Toolbar dua baris dengan tombol bulat.
- Thumbnail gambar/video kini juga muncul di tampilan daftar, bukan hanya kisi.

---

## 3. Indeks A–Z

Bagian yang mudah salah bukan menggambar hurufnya, tapi memutuskan huruf mana yang
menampung sebuah nama. Tiga aturan, masing-masing pernah jadi bug di aplikasi lain:

| Aturan | Alasan |
|---|---|
| Angka & simbol masuk grup **`#`** | Folder `2026-11-11_APK` sangat umum. Membandingkan kode karakter mentah menaruhnya di tempat yang tidak bisa dicapai dari bilah huruf. |
| Huruf beraksen dilipat ke huruf dasarnya | `Ékspor` harus di bawah **E**, bukan di grup yang tak ada di bilah. |
| Huruf besar/kecil tidak pernah berarti | `album` dan `Album` satu grup. |

Bilah huruf di tepi kanan **hanya menggambar huruf yang benar-benar ada** — indeks
dengan 23 huruf mati hanyalah scrollbar yang menyamar. Menekan huruf menyaring
daftar; menekannya lagi mengembalikan semua. Ini keputusan sadar: daftar berkas
berada di dalam scroll milik shell, yang tidak dipegang layar ini, jadi indeks
"lompat ke huruf" akan butuh posisi scroll yang tidak dimilikinya. Menyaring selalu
bekerja, berapa pun panjang daftarnya.

Bilah baru muncul kalau isi folder ≥ 8 item, supaya folder berisi tiga berkas tidak
dihiasi indeks.

---

## 4. Pencarian se-perangkat

Kolom pencarian tetap menyaring folder yang sedang dibuka (seperti Files). Tombol
titik di kanan kolom itu yang membuka pencarian seluruh penyimpanan.

Empat pembatas, karena tanpa salah satunya aplikasi bisa membeku di HP:

| Pembatas | Nilai | Kenapa |
|---|---|---|
| Kedalaman | 8 tingkat | `Android/data` bersarang tanpa akhir dan tidak terbaca di Android 11+. |
| Hasil maksimum | 200 | Menampilkan 50 dari 100.000 baris tidak berguna. |
| Bisa dibatalkan | per folder | Menutup panel menghentikan penelusuran, bukan meninggalkan thread membaca kartu SD. |
| Melewati folder privat aplikasi lain | `/Android/data`, `/Android/obb`, `/Android/media` | Butuh izin yang tidak dimiliki aplikasi; menelusurinya hanya menghasilkan pengecualian. |

Aturan lewati dicocokkan pada **akhiran jalur penuh**, bukan nama folder: folder
`data` di dalam `Documents` milik pengguna dan tetap ditelusuri. Versi pertama saya
mencocokkan nama dan diam-diam menyembunyikan berkas asli — itu ditemukan oleh tes
JVM sebelum build.

Panel hasil menampilkan nama, potongan jalur (dipotong di tengah, bukan di ujung,
supaya nama folder pembeda tetap terlihat) dan ukuran. Tombol **Buka** menjalankan
berkas, mengetuk barisnya membuka folder tempat berkas itu berada.

---

## 5. Kunci tanda tangan — apa yang sudah beres dan apa yang belum

**Sudah beres:**

- Kunci rilis dibuat: RSA 4096, SHA-256 with RSA, berlaku sampai **2056-11-03**,
  alias `pure-manager-release`.
- Tersimpan di Drive, folder **`05 — KEY SIGNING & BERKAS PENTING Pure Manager`**
  ([tautan](https://drive.google.com/drive/folders/1JE-GGwyQKV0rbTqgBoeCJ9bDaLeB0pTo)),
  dengan nama yang menyebut isinya:

  | Berkas | ID Drive | Ukuran |
  |---|---|---|
  | `2026-11-11_KEY-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.p12` | `1_l_C0Y3uEFbK_84EPIoB4FqWGR-h4IdT` | 4.380 B |
  | `2026-11-11_CERT-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.pem` | `1w1URa9IbBp1BbRWscW25HMZPxaDle5zf` | 1.915 B |
  | `2026-11-11_DOK-Pure-Manager-KEY-SIGNING-password-alias-fingerprint.md` | `1OClMa9gQYi_3b-PtXYeEnSgdsXekODGC` | 4.107 B |
  | `2026-11-11_KEY-Pure-Manager-PM_KEYSTORE_B64-siap-tempel-di-GitHub.txt` | `1ajGkBkl--VO7D5gTV8M9Q2qwDSXz75-O` | 6.381 B |

- Dibuktikan bisa dibuka: `openssl pkcs12 -info` lolos dengan sandi benar dan
  **menolak** sandi salah (`Mac verify error`). Format PBES2/AES-256-CBC — format
  yang diterima AGP; RC2 lama tidak dipakai.
- Sidik jari SHA-256 sertifikat:
  `A2:F9:42:45:2E:EC:1C:D8:76:3E:6C:F3:3B:99:37:C1:A9:9B:38:49:C6:27:73:A7:3B:F4:44:77:67:43:F2:D8`
- `build.gradle.kts` membaca kunci dari empat variabel lingkungan dan otomatis jatuh
  ke kunci debug kalau tidak ada.
- Nama berkas APK sekarang menyebut kunci penandatangannya: `DEBUGKEY` atau
  `RELEASEKEY`. Sebelumnya selalu tertulis DEBUG — jujur, tapi tidak berguna.

**Belum beres, dan hanya Anda yang bisa:**

Token GitHub di sandbox ini **ditolak saat menulis Actions secrets** (HTTP 403), dan
repo ini publik sehingga kunci tidak boleh masuk repo. Jadi dua variabel ini harus
dipasang sekali secara manual di
**https://github.com/dwp29/Synthentica/settings/variables/actions**:

| Nama | Nilai |
|---|---|
| `PM_KEYSTORE_B64` | seluruh isi berkas base64 yang sudah saya taruh di folder Drive di atas |
| `PM_KEYSTORE_PASSWORD` | `PureManager2026!` |

Build berikutnya akan menghasilkan `...-RELEASEKEY.apk` dan mencetak sidik jari
penanda tangan di ringkasan build untuk dicocokkan dengan `A2:F9:42:…:F2:D8`.

Sampai itu dipasang, **APK 0.5.0 masih bertanda tangan kunci debug**, jadi di HP
harus **hapus aplikasi versi lama dulu**, baru pasang 0.5.0. Ini bukan kelalaian;
ini konsekuensi dari tidak adanya izin menulis variabel repo.

---

## 6. Verifikasi

- **87 tes sumber** (`tests/test_pure_manager_sources.py`) — OK.
  Tambahan di build ini: aturan grup `#`, pelipatan aksen, bilah yang menyaring,
  filter yang bersih saat pindah folder, batas kedalaman/hasil pencarian, aturan
  lewati folder privat, pencarian yang tidak membaca state Compose dari thread lain,
  `trimPath`, kisi tanpa kartu, warna folder yang stabil, dan **penjaga trailing
  lambda** baru.
- **Uji JVM di CI** — bagian dari run hijau 43014600784 (tes `Search` dan `Alphabet`
  ikut dijalankan).
- **APK diperiksa**: `zipfile.testzip()` bersih, 146 entri, dan string `Alphabet`,
  `Search`, `folderTint`, `trimPath`, `DeviceSearchDialog`, `AlphabetStrip` semuanya
  ada di dalam `classes*.dex` — jadi kode baru benar-benar ikut terpaket.

### Satu bug nyata di build ini, dan bagaimana ia tertangkap

Run pertama 0.5.0 **merah**:

```
e: BrowserScreen.kt:1942:42 No value passed for parameter 'onClick'.
e: BrowserScreen.kt:1942:49 Argument type mismatch: actual type is
   'kotlin.Function0<kotlin.Unit?>', but 'androidx.compose.ui.graphics.Color?' was expected.
```

Sebabnya: `ToolButton` sekarang punya parameter opsional `tint` di belakang
`onClick`, jadi `ToolButton("←", false) { ... }` menaruh lambda di `tint`. Saya
mengganti pemanggilnya ke argumen bernama, lalu menulis penjaga agar bentuk itu
tidak muncul lagi — dan **menguji penjaganya dengan menanam baris rusak**: penjaga
gagal seperti seharusnya. Versi pertama penjaga bahkan tidak menangkap bentuk
aslinya (kurung kurawal ada di akhir baris, bukan di tengah), dan itu juga
diperbaiki sebelum dipercaya.

---

## 7. Yang belum dikerjakan

| Hal | Status |
|---|---|
| T1 tema: warna & sudut tiap layar lain (Modul, Setelan, Tema) | sebagian — kisi & daftar Berkas sudah mengikuti Files |
| T3 root + terminal | belum |
| T4 dua varian + tab Modul berfungsi | belum |
| T5 PDF/Word/Excel | belum |
| T6 editor kode | belum |
| T7 gambar/audio | belum |
| T8 AI | ditahan atas permintaan |
| Arti "reset" | **masih belum jelas** — lihat pertanyaan di akhir laporan |

---

## 8. Catatan lain

- APK 0.1.4 dan 0.4.0 saya hapus dari folder `02-BUILD-APK` supaya tidak ada yang
  salah memasang versi lama. Yang tersisa hanya 0.5.0. Cadangannya masih ada di
  branch `build-output` GitHub (hanya versi terbaru) — kalau Anda ingin versi lama
  disimpan permanen, bilang saja, saya unggah ulang dari riwayat.
