# LOG Build-015 — Tahap 7: Gambar & audio (0.10.0)

- **Tanggal:** 11 November 2026
- **Versi:** 0.10.0 (versionCode 16)
- **Run hijau:** `43042980292` — SUCCESS
- **Status:** T7 selesai. T8 (AI) masih **ditahan**.

## Yang diminta

Tahap 7 pada rencana: aplikasi bisa menampilkan gambar dan memutar audio sendiri,
tanpa menyerahkan berkas ke aplikasi lain.

## Keputusan: tidak memakai ExoPlayer

ExoPlayer (media3) sekitar 1,5 MB plus peninjauan lisensi, untuk hal yang
`MediaPlayer` dan `VideoView` sudah lakukan di HP owner. Yang tidak diberikan
platform adalah **aritmetika di sekitar pemutar** — dan itu justru bagian yang
sering salah. Jadi pemutar tetap milik platform, dan aturannya ditulis sendiri
sebagai fungsi biasa di `media/Timeline.kt`.

Berkas yang dipakai:

| Berkas | Isi |
|---|---|
| `media/Timeline.kt` | `formatClock`, `shownPosition`, `progressFraction`, `nextIndex`, `previousIndex`, `previousRestartsInsteadOfGoingBack`, `MediaKind`, `ZoomState`, `clampZoom`, `doubleTapZoomState` |
| `media/Players.kt` | `AudioPlayer` (MediaPlayer + ticker posisi), `titleOf`, `playlistPosition` |
| `ui/MediaScreen.kt` | `ImageViewer`, `AudioScreen`, `VideoScreen`, `decodeSampled` |
| `tools/media_logic_check.py` | Port Python, dijalankan penjaga |
| `test/.../MediaTest.kt` | 40 tes JVM |

Tidak ada dependensi baru.

## Bug yang ditemukan sebelum CI

1. **`clampZoom` memaku geseran ke nol.** Versi pertama menulis `maxX = 0f`, yang
   benar saat skala 1 dan **mematikan geseran di semua skala lain**: gambar bisa
   dizoom tapi tidak bisa digeser sama sekali. Penggeseran sekarang dibatasi pada
   setengah luapan: `viewport * (skala - 1) / 2`.
2. **Nol negatif.** `coerceIn(-0f, 0f)` mengembalikan `-0.0f`, dan
   `Float.equals` — yang dipakai `assertEquals` JUnit — menganggap `-0.0f` bukan
   `0.0f`. Gambar yang terpusat sempurna gagal tes kesetaraannya sendiri, dan
   pembagian dengan offset itu nanti menghasilkan `-Infinity`. Ditambah `+ 0f`.
3. **`nextIndex` memakai `%`, bukan `floorMod`.** Seed negatif menghasilkan indeks
   negatif, dan indeks negatif ke dalam daftar putar adalah crash.

## Bug yang ditemukan CI

1. **`private data class` di tengah fungsi.** Deklarasi `MediaTarget` jatuh di
   antara dua pernyataan `BrowserScreen`, sehingga Kotlin membacanya sebagai
   **local class** — dan local class tidak boleh membawa `private`. Pesan
   kompilernya menunjuk ke modifier, bukan ke posisi, jadi perbaikan pertama saya
   mengubah tempat yang salah. Sekarang ada penjaga yang gagal bila sebuah
   deklarasi bersemodifier ditulis menjorok di dalam blok.
2. **`context` terhapus dari `VideoScreen`** saat saya membersihkan impor yang
   tidak terpakai — `VideoView(context)` membutuhkannya.
3. **`onLongPress` ikut terhapus** saat saya memindahkan blok deklarasi; sudah
   dipulihkan dan diverifikasi penjaga.
4. **Nol negatif** di atas baru muncul di CI, karena port Python tidak bisa
   membedakan `-0.0` dari `0.0` dengan `==`. Port sekarang memeriksa **tanda**
   dengan `math.copysign`.

## Verifikasi

- **148 penjaga Python OK** (135 sebelumnya + 13 kelas `MediaPlayers`).
- **220 tes JVM**, semuanya hijau.
- APK diperiksa: 146 entri zip; penanda `AudioPlayer`, `VideoScreen`,
  `ImageViewer`, `EditorScreen`, `clampZoom` ada di dex.

## Hasil

| Varian | Berkas | Byte | sha256 (16 awal) | Drive |
|---|---|---|---|---|
| FULL | `PureManager-0.10.0-DEBUGKEY.apk` | 19.117.285 | `4c5145bbc56ebbb7` | `1f4aIThHhFgI-8NLHaSmin4yK5ULyIkFq` |
| MINIMAL | `PureManager-0.10.0-minimal-DEBUGKEY.apk` | 19.117.297 | `3fc3be7ed745043a` | `1O7wwzVSKmeMBugre7YgZQftjtyrMj9Ay` |

## Keterbatasan yang harus dikatakan

- **Tidak ada lirik, tag ID3, atau sampul album.** Judul = nama berkas. Tidak ada
  pustaka pembaca tag, dan menambahkannya bukan keputusan tahap ini.
- **Video tidak punya tombol layar penuh**; video mengisi lebar layar dan itu
  batasnya.
- **Subtitle tidak didukung.**
- **Format yang tidak didukung dekoder Android tidak bisa diputar** (mis. MKV
  dengan kodek tertentu). Pesannya menyebut kode galat, bukan diam.
- **GIF tidak dianimasikan** — ditampilkan sebagai gambar diam.
- **Belum diuji di HP.** Belum ada yang memutar satu berkas pun di perangkat
  sungguhan; itu menunggu owner.

## Pengarsipan

Kedua APK dan log ini diunggah ke Drive. APK 0.9.0 dihapus supaya folder `02`
hanya berisi versi terbaru.

> Koreksi: dua ID Drive di tabel ini sempat ditulis sebagai tebakan sebelum
> unggahan selesai, lalu diganti dengan ID yang sebenarnya dari jawaban Drive.
