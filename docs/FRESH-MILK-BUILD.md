# Fresh-Milk / CHEESE-BURGER — Panduan Build

Dua varian, satu tree, satu resep induk (`build_synthetica32_r1.py`).
Perbedaan varian **hanya identitas rilis**. Tidak ada kode, patch, toolchain,
SuSFS, atau root yang berbeda.

---

## 1. Bukti kompilasi (nyata, bukan klaim)

CI `fresh-milk-kernel.yml` run **44580909494**: kedua varian **sukses**, termasuk pemaketan.

| | Fresh-Milk | CHEESE-BURGER |
|---|---|---|
| profil | `synthetica` (harian) | `critical` (gaming) |
| LOCALVERSION terbangun | `"-Fresh-Milk-14.03"` | `"-CHEESE-BURGER-11.08"` |
| config berubah dari 3.1 | `LOCALVERSION` saja | 10 simbol (lihat §4) |
| ekspor dibandingkan | 12.236 | 12.236 |
| selisih ABI | **0** | **0** |
| `module_layout` CRC | `0xed5659d1` | `0xed5659d1` |
| modul ikut dibangun | 6 | 6 |
| `image_sha256` | `9c21fc83…b99912f0` | `bc178e66…3f133847` |
| ZIP | `Fresh-Milk-14.03.zip` | `CHEESE-BURGER-11.08.zip` |
| ukuran ZIP | 15.718.511 B | 15.719.382 B |
| `sha256` ZIP | `e2bb21e2…32815f51` | `4e0a847c…5fcce7bc` |

Yang **belum** dibuktikan: boot di perangkat, dan kecocokan dengan modul ROM
tertentu. Jangan menyebut lebih dari ini.

## 2. Dari mana nama kernel berasal

Ini sumber kesalahan pertama yang butuh tiga iterasi CI untuk ketahuan:
`CONFIG_LOCALVERSION` **tidak** dibaca dari berkas fragment config.

`ci/rollercoaster/build-rollercoaster.sh` membentuknya dari dua variabel:

```sh
NAME="${SP_BUILD_NAME:-$NAME}"
KVER="${SP_BUILD_KVER:-$KVER}"
LOCALVER="-${NAME}-${KVER}"
printf '\nCONFIG_LOCALVERSION="%s"\n' "$LOCALVER" >> "$DEFCONFIG"
```

Jadi kalau `SP_BUILD_NAME=fresh-milk` (huruf kecil), kernel akan bernama
`fresh-milk` — bukan `Fresh-Milk`. Karena itu:

- tabel varian menyimpan `name` dan `kver` berkapitalisasi benar;
- workflow mengirimkannya sebagai `SP_BUILD_NAME` / `SP_BUILD_KVER`;
- `apply_variant()` **menolak jalan** kalau environment tidak cocok;
- CI punya asersi yang gagal kalau `LOCALVERSION` hasil build tidak sama
  dengan identitas varian.

## 3. Perubahan config

**Fresh-Milk** mengubah **nol** simbol config. Hanya `CONFIG_LOCALVERSION`.

**CHEESE-BURGER** menjalankan profil `critical.config` milik kit. Efek nyatanya
di atas 3.1 hanya 10 simbol, dan seluruhnya berasal dari berkas profil itu
sendiri — bukan daftar yang dikarang:

| Simbol | 3.1 | Gaming | Sebab |
|---|---|---|---|
| `HZ` / `HZ_300` | 100 / n | 300 / y | respons input lebih cepat |
| `HZ_100` | y | n | eksklusif dengan `HZ_300` (Kconfig) |
| `CPU_FREQ_DEFAULT_GOV_PERFORMANCE` | n | y | default governor performa |
| `CPU_FREQ_DEFAULT_GOV_SCHEDUTIL` | y | n | tergantikan pilihan di atas |
| `DEFAULT_IOSCHED` | `"cfq"` | `"deadline"` | profil memilih deadline |
| `DEFAULT_DEADLINE` / `DEFAULT_CFQ` | n / — | y / n | pasangan pilihan scheduler |
| `WQ_POWER_EFFICIENT_DEFAULT` | y | n | profil tidak menyatakannya |
| `LOCALVERSION` | `synthetica-3.1` | `CHEESE-BURGER` | identitas |

Tiga simbol yang sempat direncanakan ditambahkan ternyata **sudah aktif** di
baseline 2.0, jadi dipindah menjadi penjaga `MUST_STAY_ON`:

```
CONFIG_CRYPTO_ZSTD=y
CONFIG_CRYPTO_LZ4HC=y
CONFIG_TMPFS_XATTR=y
```

### Dua jebakan yang ditemukan lewat CI

1. `critical.config` **tidak memuat MGLRU/UCLAMP/WALT**. Blok fitur itu hanya
   ditambahkan `prepare()` ke `synthetica.config`. Tanpa perbaikan, varian
   gaming akan kehilangan fitur wajib 3.2. Solusinya: blok yang sama disalin
   apa adanya dari `synthetica.config` ke profil gaming saat `prepare`.
2. `critical.config` juga **tidak menyebut** `F2FS_STAT_FS`, sehingga nilainya
   kembali ke `=y` dari `00-common`. Statistik f2fs adalah beban profiling di
   hot path — justru yang paling tidak diinginkan build gaming. Profil gaming
   kini menyatakan `# CONFIG_F2FS_STAT_FS is not set` secara eksplisit.

## 4. Penjaga yang berjalan

Warisan 3.2-r1, tidak dilonggarkan:

1. 12.236 rekaman `Module.symvers` dibandingkan dengan 3.1: nama, pemilik,
   jenis ekspor, CRC. Selisih satu = build gagal.
2. `module_layout` harus tetap `0xed5659d1`.
3. `MODULE_FORCE_LOAD` harus tetap mati.
4. Config wajib cocok dengan `CONFIG_LOCALVERSION` yang dipin.
5. Hash `mm/vmscan.c` sebelum & sesudah patch MGLRU diperiksa.

Tambahan `build_fresh_milk.py`:

6. **23 simbol** wajib tetap `y`.
7. **3 simbol** wajib tetap mati, masing-masing beralasan tertulis.
8. Identitas env diperiksa sebelum kompilasi dimulai.
9. Set config yang boleh berubah **diturunkan dari berkas profil kit**, bukan
   diketik tangan. Daftar tulisan tangan pasti menyimpang begitu profilnya
   berubah.
10. Simbol di `MUST_STAY_OFF` tidak boleh muncul di set yang boleh berubah.
11. Guard bawaan yang menuntut *default governor* schedutil diganti dengan
    versi yang tetap mewajibkan governor schedutil **terkompilasi** — hanya
    pilihan default-nya yang diserahkan ke profil. Untuk Fresh-Milk, guard
    aslinya dipakai apa adanya.

## 5. Nama rilis

```
4.14.357-openela-Fresh-Milk-14.03      (33 karakter)
4.14.357-openela-CHEESE-BURGER-11.08   (36 karakter)
```

Batas `utsname` 64. Kapitalisasi **dipertahankan** persis — ini yang akan
dicocokkan BREAKFAST.

## 6. Menjalankan

Lokal, tanpa kompilasi:

```sh
python3 build-kit/scripts/build_fresh_milk.py fresh-milk verify
python3 -m unittest tests.test_fresh_milk_variants -v
```

Kompilasi hanya lewat CI (sandbox tidak punya clang / cross-compiler):

```sh
gh workflow run fresh-milk-kernel.yml --ref arena/96cbd65a-synthentica
```

## 7. Installer

Ada di `build-kit/ci/rollercoaster/anykernel/anykernel.sh` — **bukan** di
`ci/fresh-milk/`. Alasan: kalau kit kelak memaketkan zip, sumbernya adalah
`ci/rollercoaster/anykernel`, jadi installer di folder lain tidak akan pernah
ikut.

**Status: sudah dipaketkan.** Resep 3.2-r1 memang berhenti di "Image and
matching modules only". Pemaketan ditambahkan sebagai tahap tersendiri,
`build-kit/scripts/package_fresh_milk.py`, tanpa mengubah resep itu.

Pemaket memakai ulang bagian yang membuat zip bisa dipercaya, semuanya dipin
dengan digest:

| Bagian | Sumber |
|---|---|
| kerangka AnyKernel (busybox, magiskboot, update-binary) | `release/Synthetica-2.0.zip`, sha `b1a0be5c…` |
| skrip installer | `ci/synthetica2-experimental/test-installer/anykernel.sh`, sha `d6fa389a…` |
| penyiap boot | `prepare-boot.sh`, sha `0a6eedd6…` |

Dan menolak bukti build yang tidak cocok: rilis, digest image, digest config,
sumber, toolchain, flag MGLRU, identitas manager, serta flag
`installer_created`/`private_key_exported`. ZIP tidak pernah memuat kunci
privat maupun arsip debug.

Installer menanam **digest image yang tepat** dan hanya mau menulis image itu.

Teks Inggris saja, nama kernel sebagai satu-satunya elemen besar:

```
   4.14.357-openela-Fresh-Milk-14.03
    Installing kernel
  [##.......................] 10%  Checking device
  [########.................] 35%  Writing boot image
  [##################.......] 75%  Finalising
  [#########################] 100%  Finished
   Kernel installed.
   Reboot when ready.
```

Pemasangan `ksud` tetap ada dan senyap saat berhasil; pesan hanya muncul
kalau `/data` masih terenkripsi.

| Perilaku | Nilai |
|---|---|
| doa / teks Indonesia / Arab | tidak ada |
| nama pembuat di layar | tidak ada |
| auto-reboot | tidak ada |
| cadangan boot | **tidak ada** |
| log | `/sdcard/Breakfast/install-<waktu>.txt` bila bisa ditulis |

## 8. Status klaim

| Tingkat | Status |
|---|---|
| Kompilasi | **lulus** (run 44580909494) |
| Statis (ABI, config) | **lulus**, 0 selisih |
| Paket flashable | **lulus** — ZIP + installer + penjaga digest |
| Boot perangkat | **belum** |
| Teruji | **belum** |

Sesuai `docs/KERNEL-WORK-RULES.md` §1, tidak ada tingkat di atas yang boleh
diklaim sebelum buktinya ada.
