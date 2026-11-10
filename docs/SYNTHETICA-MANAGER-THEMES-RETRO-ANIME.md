# Synthetica Manager — tema Retro Arcade, Anime Wibu, dan Gothic Crimson

Tiga tema baru yang ditambahkan di atas Manager 6.0.0 yang sudah rilis. Ketiganya
**presentasi saja**: tidak menyentuh backend root, KernelSU, modul, atau
pengaturan. Semua layar, data, dan tombol tetap sama; yang berubah hanya warna,
tipografi, bentuk, banner, splash, dan gerak.

> Status jujur: kode ini **sudah dikompilasi**. `:app:assembleRelease` berhasil
> di CI (run 42845619299, commit `ca0506d`) dan APK-nya diperiksa ulang: 6 lapisan
> banner, 7 emblem, 4 lisensi font, serta id `retro_arcade` / `anime_wibu` /
> `gothic_crimson` ada di DEX. Yang **belum** dibuktikan adalah tampilannya di
> perangkat; lihat "Yang belum dibuktikan" di bawah.
>
> Dua putaran CI sebelumnya gagal karena kesalahan yang tidak terlihat oleh test:
> `ThemedHero.kt` kehilangan baris `package`, `CutCornerShape` dipakai tanpa
> import, dua `when` di `IosSwitch` tidak exhaustive, dan `R` tidak diimpor.
> Keempatnya sekarang dijaga test (lihat bagian gerbang).

## Cara memilih

Settings → Appearance → Design, lalu pilih **Retro Arcade**, **Anime Wibu**,
atau **Gothic Crimson**. Pilihan tersimpan di preferensi `manager_visual_style`
dengan id `retro_arcade`, `anime_wibu`, dan `gothic_crimson`, ikut terekspor/terimpor lewat konfigurasi JSON yang sudah ada,
dan tidak mengubah id tema lama (`pixel`, `cyberpunk`, `ios_glass`, `neon`),
sehingga pengaturan lama tetap terbaca.

## Bentuk ketiga tema

Ketiganya memakai satu komponen banner bersama (`IllustratedBannerHero`), tetapi
dengan ilustrasi, geometri, tipografi, dan palet yang berbeda. Ini bukan varian
warna dari satu sama lain.

| | Retro Arcade | Anime Wibu | Gothic Crimson |
| --- | --- | --- | --- |
| Ilustrasi | Taman hiburan 16-bit: coaster, kastil, bianglala, anak berjaket | Malam sakura: bulan, pagoda, torii, lentera, gadis berjaket | Bulan darah di atas kastil gotik, ksatria bermahkota duri, gagak |
| Palet | Biru langit + kuning, merah, hijau rumput | Indigo-violet + sakura pink, emas lentera | Hitam + merah darah, baja, tulang |
| Judul banner | VT323 | Zen Maru Gothic | Serif heraldik |
| Label | Press Start 2P (8-bit) | Zen Maru Gothic | Serif |
| Bentuk panel | Radius 14 dp, tepi keras | Radius 28 dp, pil | Potongan bilah 26 dp |
| Dock | Hampir selebar layar, kapital | Sempit dan mengambang | Sedang, kapital |
| Banner | 214 dp | 218 dp, denyut halus | 222 dp |
| Splash | `INSERT COIN` / `PRESS START` | Stiker berdenyut + `マネージャー` | Bulan naik + emblem menyala |

## Banner bergerak

Setiap banner terdiri dari **dua lapisan** dari ilustrasi yang sama:

- `theme_banner_<tema>_far.jpg` — latar tanpa tokoh, digeser perlahan
  (parallax 10–14 dp bolak-balik mengikuti fase tema);
- `theme_banner_<tema>.jpg` — ilustrasi penuh dengan tokoh, di-*breathing zoom*
  halus (1,02–1,035×).

Lapisan jauh dibuat dengan memotong bagian kanan ilustrasi lalu diskalakan ulang
ke 16:9, karena dipakai dengan `ContentScale.Crop`. Test menjaga agar kedua
lapisan tetap 16:9 dan tidak identik.

Di atas ilustrasi, tiga hal tetap **data hidup**, bukan bagian gambar: pil status
(`Rooted`/`Not rooted`), `modePill` (`NATIVE`/`BUILT-IN`), dan strip bawah berisi
baris kernel serta `UAPI v4 · 6.0.0`. Ada gradien gelap 62% di bagian bawah dan
panel semi-opak untuk strip data supaya teks tetap terbaca di atas piksel terang
(ini persis masalah yang terlihat pada mock: teks putih di atas langit biru).

## Aset

| Berkas | Isi | Ukuran |
| --- | --- | --- |
| `theme_banner_retro.jpg` / `_far` | 1200×675 | 114 KB / 80 KB |
| `theme_banner_gothic.jpg` / `_far` | 1200×675 | 178 KB / 134 KB |
| `theme_banner_anime.jpg` / `_far` | 1200×675 | 197 KB / 158 KB |
| `ic_emblem_retro.png` | atom piksel | 22 KB |
| `ic_emblem_gothic.png` | pentagram duri | 62 KB |
| `ic_emblem_anime.png` | atom glass ungu | 50 KB |

Banner disimpan sebagai JPEG progresif 1200 px (bukan PNG) karena fotorealistik
dan akan membengkak 5–10× sebagai PNG; emblem tetap PNG berpalet 256 warna agar
transparan dan tajam.

## Font dan lisensi

Keempat famili berlisensi **SIL Open Font License 1.1** dan diambil dari
[google/fonts](https://github.com/google/fonts):

| Berkas | Famili | Ukuran asli | Subset di APK |
| --- | --- | --- | --- |
| `retro_vt323.ttf` | VT323 | 153 KB | 31 KB |
| `retro_pressstart.ttf` | Press Start 2P | 118 KB | 10 KB |
| `anime_zenmaru.ttf` | Zen Maru Gothic Black | 3,7 MB | 67 KB |
| `anime_rampart.ttf` | Rampart One | 3,7 MB | 177 KB |

Gothic Crimson sengaja **tidak** menambah berkas font: ia memakai serif bawaan
platform. Fraktur asli akan lebih setia pada referensi, tetapi membutuhkan
subset dan lisensi sendiri untuk keuntungan visual yang kecil; serif menjaga
nuansa heraldik tanpa menambah ±200 KB.

Subset dibuat dengan `fonttools` memakai `--text` berisi Latin + tanda baca yang
dipakai tema + kana/kanji yang muncul di string tema, `--layout-features=*`,
`--no-hinting`, `--desubroutinize`. Totalnya turun dari ±7,5 MB menjadi ±285 KB.
Konsekuensinya: **karakter di luar subset akan tampil sebagai tofu**, jadi string
baru untuk kedua tema harus memakai huruf yang sudah ada di subset (test menjaga
batas ukuran berkas, bukan cakupan glyph).

Teks lisensi lengkap ikut dibundel di `app/src/main/assets/font-licenses/` dan
dicatat di `NOTICE`. Font tidak dijual terpisah, tidak di-rename, dan tidak
di-modifikasi di luar subsetting (yang diizinkan OFL).

## Emblem

`ic_emblem_retro.png` dan `ic_emblem_anime.png` dibuat untuk tema ini, berlatarb
transparan, 512×512, dipangkas dan dipusatkan seperti emblem lama.

## Gerbang yang menjaga

`tests/test_synthetica61_retro_anime.py` (16 test) memeriksa:

1. enum punya tujuh gaya dan id lama tidak berubah;
2. setiap titik dispatch (`VisualStyles`, `ThemedHero`, `Glass`,
   `AppearanceControls`) punya cabang untuk ketiga tema baru;
3. setiap `when` yang menyebut salah satu anggota `ManagerStyle` bersifat
   exhaustive. Versi pertama test ini hanya mengenali `when (style)`, dan justru
   itu sebabnya dua `when` yang tidak exhaustive lolos sampai CI. Versi sekarang
   memindai subjek apa pun dan menuntut ketujuh cabang — diuji dengan menghapus
   satu cabang dan memastikan test gagal;
4. setiap berkas tema mendeklarasikan `package` dan mengimpor `R`. Keduanya
   sempat hilang dan memakan satu putaran CI penuh (58 error, 53 di antaranya
   efek berantai dari baris `package` yang hilang);
5. lapisan banner ada, berjumlah dua per tema (near + far), keduanya 16:9, saling
   berbeda, di bawah batas ukuran, dan benar-benar dipakai di source;
6. data hidup (status, mode, baris kernel) tetap dirender di atas ilustrasi;
7. font dan emblem ada, dipakai, dan di bawah batas ukuran;
8. pemilih tema dan string (termasuk terjemahan Indonesia) memuat ketiga tema;
9. gerbang standalone `verify_tree()` masih menerima pohon, dan tidak ada bahan
   penandatanganan yang ikut masuk.

`tests/verify_synthetica60_apk.py` mengulang pemeriksaan itu **pada APK**, bukan
pada source: 7 emblem, 6 lapisan banner, dan ketiga id gaya harus ada di DEX.
Semuanya lolos pada APK hasil run 42845619299. Gate ini juga diuji balik dengan
APK yang sengaja dirusak, dan memang menolak.

## Yang belum dibuktikan

- **Belum diuji di perangkat.** Kompilasi sudah terbukti, tampilan belum. Belum
  ada tangkapan layar, belum ada bukti animasi berjalan di layar sungguhan, dan
  belum ada angka frame rate pada perangkat 4.14. Yang paling perlu dilihat
  pertama: keterbacaan judul di atas langit biru terang milik tema retro.
- **Cakupan glyph subset terbatas** pada daftar karakter di atas.
- **Belum ditandatangani.** APK yang dihasilkan CI sengaja *unsigned*; penandatanganan
  memakai sertifikat Synthetica asli di luar sandbox.
