# Log kerja UFO-0.1 — dari laporan palsu ke bukti yang bisa diperiksa

Berkas ini mencatat apa yang saya kerjakan, apa yang saya salah, dan apa yang masih
terbuka. Disusun karena tiga laporan sebelumnya ke owner ternyata keliru, dan
kekeliruan itu tidak boleh hilang dari catatan.

## Keadaan akhir

| Hal | Keadaan |
|---|---|
| Build UFO-0.1 terakhir | run `43676566211`, commit `facd6c6`, hijau 13/13 |
| Gerbang fitur | membaca instruksi mesin (`prove_features.py`), keenam fitur lulus |
| Zip flash | `3f1bd045…`, 21.123.226 byte, 26 berkas |
| Bukti mentah | branch `ufo-evidence` dan `ufo-release` |
| Boot/performa/drain/panas/deep sleep | **belum diuji sama sekali** |

## Urutan kerja

1. **Pelajaran dari APK.** Owner menegur karena pekerjaan lari ke APK. Kembali ke
   kernel, dan tidak menyentuh tampilan lagi.
2. **Bukti pertama, salah.** `verify_image.py` generasi pertama hanya mencari string
   di `Image.gz`, melaporkan "semua fitur ada". Dua hit `lru_gen` ternyata kunci
   counter vmstat dan pesan error.
3. **Bukti kedua, salah ke arah sebaliknya.** Image dibuka, `lru_gen_full` dicari,
   tidak ada, lalu saya simpulkan initcall MGLRU dibuang. Yang sebenarnya terjadi:
   linker membuang literal itu. Hilangnya string tidak membuktikan apa-apa.
4. **Bukti ketiga, salah lagi.** `System.map` dibaca dengan daftar simbol yang saya
   karang dari ingatan kernel 6.x (`lru_gen_add_folio`). Pohon 4.14 ini memakai
   `lru_gen_eviction`. Semua fitur dilaporkan "tidak tersambung".
5. **Berhenti menebak dari nama.** `prove_features.py` mem-(1) mendekode `BL`,
   `ADRP`, `ADD` dari Image, (2) mencocokkan alamat dengan `System.map`, (3)
   memeriksa apakah fungsi kernel yang benar-benar berjalan memanggil kode fitur.
6. **Self-test menemukan dua bug di alat itu sendiri** sebelum dipakai pada kernel:
   salah hitung jumlah kata (semua pemindaian `ADRP` kosong) dan pembacaan struct di
   alamat yang salah. Keduanya akan melaporkan kernel sehat sebagai rusak.
7. **Uji negatif.** Dengan Image yang sengaja dirusak, gerbang mengembalikan 1 dan
   menyebut keenam fitur gagal. Gerbangnya bukan hiasan.
8. **Build hijau.** `43676566211`. `PROOF.txt` dari runner menunjukkan keenam fitur
   punya rantai bukti utuh.
9. **Arsip Drive dirapikan** (lihat `MANIFEST-RAPIKAN-ARSIP-v4`): zip usang
   diarsipkan, log kernel dipisah dari log perangkat lain, indeks v3 diganti v4.

## Kesalahan yang perlu diingat

- **Nama bukan panggilan.** Tiga kali berturut-turut saya menyimpulkan dari nama.
- **Hijau bukan berfungsi.** Build hijau berarti kompilasi selesai, bukan menyala.
- **`CONFIG_X=y` bukan bukti.** Itu hanya permintaan yang diterima Kconfig.
- **Mengedit YAML berdasarkan indeks baris berbahaya.** Satu penyuntingan saya
  menukar nama langkah dengan isi langkah lain, dan berkasnya masih lolos sebagai
  YAML yang sah. Yang menangkapnya hanya perbandingan nama langkah satu per satu.
  Sejak itu setiap penyuntingan workflow diverifikasi dengan mem-parse ulang dan
  mencetak nama tiap langkah.

## Yang belum dikerjakan

1. **`CONFIG_KSU_SUSFS_TRY_UMOUNT` dan `SUS_MEMFD` mati.** Tidak pernah ada di
   `miatoll_defconfig`. Dampak: umount paksa tidak ditangani SuSFS, memfd tidak
   disamarkan. Bisa dinyalakan, belum dilakukan.
2. **Bukti SuSFS masih satu titik.** `PROOF.txt` membuktikan
   `susfs_is_inode_sus_path` dipanggil dari `link_path_walk`. `SUS_KSTAT`,
   `OPEN_REDIRECT`, `SPOOF_UNAME`, `SUS_MAP` ada di config dan punya simbol, tapi
   belum punya rantai bukti masing-masing.
3. **Tidak ada pengukuran.** Ini lubang terbesar. Tanpa flash dan angka, klaim
   "performa, stabil, tanpa drain, tanpa panas, deep sleep" tidak punya dasar.

## Berkas yang berkaitan

- `build-kit/ci/ufo01/prove_features.py` — gerbang bukti, dengan self-test.
- `build-kit/ci/ufo01/verify_image.py` — penanda kuat di Image (bukan gerbang).
- `build-kit/ci/ufo01/root_stack_report.py` — laporan simbol, dipakai sebagai
  pembanding; tidak lagi menentukan lulus/gagal.
- `docs/2026-11-15_UFO-0.1-BUKTI-FITUR.md` — laporan bukti untuk owner.
- `.github/workflows/ufo-01-build.yml` — build, bukti, gerbang, publikasi zip.
