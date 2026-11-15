# 2026-11-15 — Pure Manager: tampilan baru (ikon garis + Inter)

## Apa yang diubah

**1. Ikon.** Semua ikon di layar sebelumnya adalah karakter Unicode yang dicetak
sebagai teks: `\u25A4` untuk folder, `\u2699` untuk setelan, `\u2295` untuk folder
baru. Karakter seperti itu ikut garis dasar teks dan memakai glyph apa pun yang
kebetulan dimiliki font perangkat — akibatnya muncul kotak kosong di tempat ikon
arsip, dan amplop di tempat roda gigi. Itu sebab utamanya terlihat "jelek".

Penggantinya: **45 ikon garis** di grid 24×24, digambar langsung di proyek
(`ui/PureIcons.kt`), stroke 1,7 dengan ujung membulat — satu keluarga bentuk, tanpa
dependensi baru.

**2. Font.** Tema iOS memakai `FontFamily.SansSerif` = Roboto. Roboto bukan huruf yang
dirancang untuk tata letak ini: x-height-nya lebih besar dan angkanya lebih lebar,
sehingga baris seukuran iOS terlihat padat. Sekarang **Inter** dipasang di
`res/font` dengan 4 bobot (400/500/600/700), subset Latin, 66 KB per bobot, lisensi
SIL OFL dan teks lisensinya ikut di `assets/`.

**3. Menu aksi** (tekan lama berkas) sekarang punya ikon: buka, bagikan, edit,
arsip, ganti nama, salin, pindahkan, info, hapus.

**4. Layar media**: tombol putar/jeda/mundur/maju/berikut sebelumnya juga karakter
(`⏮ ⏸ ▶ ⏭`, `−10`, `+10`) — sekarang ikon tergambar.

**5. Indeks A–Z, kolom cari, tombol toolbar, tab bar, panel setelan** semuanya ikon.

## Bukti build

| | |
|---|---|
| CI run | `43671936214` (sukses, semua langkah) |
| Commit | `acdea8b` |
| APK FULL | `PureManager-0.10.0-RELEASEKEY.apk` — 19.362.927 byte |
| sha256 FULL | `9a745056714cf0b59fc9311e6497a627450ddb4b2c457b5181fddd08d1d3afaa` |
| APK MINIMAL | `PureManager-0.10.0-minimal-RELEASEKEY.apk` — 19.362.943 byte |
| sha256 MINIMAL | `3415a0306cf5ede2d7266acad36c14040d340178414121ec2c2fa029df6e2d42` |
| Tanda tangan | RELEASEKEY (kunci rilis) |
| Isi APK diperiksa | 4 font Inter (`res/BR.ttf`, `res/U4.ttf`, `res/XE.ttf`, `res/fS.ttf`), `assets/INTER-OFL-LICENSE.txt` |

## Tiga bug CI yang ditemukan sambil mengerjakan ini

Ketiganya membuat build "diam" atau "merah" tanpa sebab yang jelas:

1. **Filter branch salah satu huruf.** Workflow menulis
   `arena/96cbd65a-synthentica`; branch sesi `arena/96cbd65a-synthentica`. Push tidak
   memicu apa pun, tanpa pesan.
2. **Checkout dipatok ke nama branch itu.** Jadi setiap run menguji commit lama dan
   melaporkan enam galat yang sudah diperbaiki. Sekarang checkout memakai commit
   pemicu; tidak ada nama yang bisa salah ketik.
3. **`res/font/` hanya menerima `.xml/.ttf/.ttc/.otf`.** Teks lisensi OFL di folder itu
   menggagalkan resource merger. Sekarang di `assets/`.

Dua guard baru di `tests/test_pure_manager_sources.py` mencegah pengulangan: aturan
ekstensi direktori `res/`, dan aturan bahwa lambda ekor tidak boleh tertelan
parameter opsional. Keduanya sudah diuji dengan memasukkan kembali bug-nya.

## Belum

- **Belum dipasang di HP.** Yang terbukti baru "berhasil dikompilasi dan ditandatangani",
  bukan "terlihat bagus di layar Anda". Penilaian tampilan tetap milik Anda.
- Tema Pixel / Windows / Cyberpunk belum dirombak; ikon baru berlaku untuk semuanya,
  tetapi Inter baru dipakai tema iOS.
