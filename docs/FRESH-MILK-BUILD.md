# Fresh-Milk / CHEESE-BURGER — Panduan Build

Dua varian, satu tree, satu resep induk (`build_synthetica32_r1.py`).
Perbedaan varian **hanya identitas rilis**. Tidak ada kode, patch, toolchain,
SuSFS, atau root yang berbeda.

---

## 1. Bukti kompilasi (nyata, bukan klaim)

CI `fresh-milk-kernel.yml` run **44546020859**: kedua varian **sukses**.

| | Fresh-Milk | CHEESE-BURGER |
|---|---|---|
| LOCALVERSION terbangun | `"-Fresh-Milk-14.03"` | `"-CHEESE-BURGER-11.08"` |
| config berubah dari 3.1 | `LOCALVERSION` saja | `LOCALVERSION` saja |
| ekspor dibandingkan | 12.236 | 12.236 |
| selisih ABI | **0** | **0** |
| `module_layout` CRC | `0xed5659d1` | `0xed5659d1` |
| modul ikut dibangun | 6 | 6 |
| `image_sha256` | `630ed4d7…6067db` | `92120cf4…7cffb7e` |

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

## 3. Perubahan config: tidak ada

Tiga simbol yang sempat direncanakan ditambahkan ternyata **sudah aktif** di
baseline 2.0:

```
CONFIG_CRYPTO_ZSTD=y
CONFIG_CRYPTO_LZ4HC=y
CONFIG_TMPFS_XATTR=y
```

Karena itu ketiganya dipindah dari daftar "perubahan yang diizinkan" menjadi
penjaga `MUST_STAY_ON`. Mendaftarkannya sebagai perubahan justru membuat
penjaga selisih-tepat gagal — dan memang begitulah cara kerjanya.

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
`ci/fresh-milk/`. Alasan: paket flashable dibangun dari
`ci/rollercoaster/anykernel`, jadi installer di folder lain tidak pernah ikut
ke dalam zip.

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
| Kompilasi | **lulus** (run 44546020859) |
| Statis (ABI, config) | **lulus**, 0 selisih |
| Paket flashable | **belum** dibuat pada varian ini |
| Boot perangkat | **belum** |
| Teruji | **belum** |

Sesuai `docs/KERNEL-WORK-RULES.md` §1, tidak ada tingkat di atas yang boleh
diklaim sebelum buktinya ada.
