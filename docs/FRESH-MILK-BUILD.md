# Fresh-Milk / CHEESE-BURGER — Panduan Build

Dua varian, satu tree, satu resep induk (`build_synthetica32_r1.py` yang sudah
lulus 359 tes). Perbedaan varian **hanya** fragment config.

---

## 1. Berkas

| Berkas | Isi |
|---|---|
| `build-kit/scripts/build_fresh_milk.py` | penimpa kunci config + pemeriksaan tambahan |
| `build-kit/ci/fresh-milk/common.config` | 3 simbol bersama |
| `build-kit/ci/fresh-milk/fresh-milk.config` | hanya `LOCALVERSION` |
| `build-kit/ci/fresh-milk/cheese-burger.config` | hanya `LOCALVERSION` |
| `build-kit/ci/fresh-milk/anykernel/anykernel.sh` | installer, teks Inggris |
| `.github/workflows/fresh-milk-kernel.yml` | CI dua varian |
| `tests/test_fresh_milk_variants.py` | 10 tes host |

## 2. Perubahan config

Hanya **tiga** simbol ditambahkan di atas 3.2-r1:

| Simbol | Dari | Ke | Alasan |
|---|---|---|---|
| `CRYPTO_ZSTD` | n | y | opsi kompresor zram ketiga |
| `CRYPTO_LZ4HC` | n | y | kompresi boot image |
| `TMPFS_XATTR` | n | y | syarat Mountify |

**Tidak** ada perubahan lain. Resep menolak build kalau ada config di luar
daftar ini, di luar `LOCALVERSION`.

## 3. Yang sengaja TIDAK diubah

| Hal | Nilai | Alasan |
|---|---|---|
| Toolchain | Neutron clang 24 (dipin) | naik versi mengubah seluruh kode, membatalkan perbandingan ABI |
| SuSFS | v2.3.0 NON-GKI | ABI v2.4.0 belum diverifikasi; ganti nanti, satu variabel |
| Root | KernelSU-Next in-tree | BakaSU = tahap 2, supaya kegagalan boot bisa dilacak |
| Patch | 3.2-r1 + guard MGLRU | tidak ada patch baru |

## 4. Penjaga yang tetap berjalan

Warisan 3.2-r1, tidak dilonggarkan:

1. Semua rekaman `Module.symvers` (**12.236**) dibandingkan dengan 3.1:
   nama, pemilik, jenis ekspor, CRC. Selisih satu = build gagal.
2. `module_layout` CRC harus tetap `0xed5659d1`.
3. `MODULE_FORCE_LOAD` harus tetap mati.
4. Config wajib-cocok dengan `CONFIG_LOCALVERSION` yang dipin.
5. Hash sumber `mm/vmscan.c` sebelum & sesudah patch diperiksa.

Tambahan dari `build_fresh_milk.py`:

6. **20 simbol** wajib tetap `y` (KSU, KSU_SUSFS, NOMOUNT, LRU_GEN, SCHED_TUNE,
   UCLAMP, SELinux, dm-verity, BPF, EROFS, F2FS, …).
7. **3 simbol** wajib tetap mati, masing-masing dengan alasan tertulis.

## 5. Nama rilis

```
4.14.357-openela-Fresh-Milk-14.03      (33 karakter)
4.14.357-openela-CHEESE-BURGER-11.08   (37 karakter)
```

Batas `utsname` 64 karakter. Kapitalisasi **dipertahankan** persis seperti di
`CONFIG_LOCALVERSION` — ini yang dicocokkan BREAKFAST nanti.

## 6. Menjalankan

Lokal (tanpa kompilasi):

```sh
python3 build-kit/scripts/build_fresh_milk.py fresh-milk verify
python3 -m unittest tests.test_fresh_milk_variants -v
```

Kompilasi hanya lewat CI (sandbox tidak punya clang / cross-compiler):

```sh
gh workflow run fresh-milk-kernel.yml --ref arena/96cbd65a-synthentica
```

CI menjalankan **dua varian paralel**, masing-masing:
ambil bukti 3.1 yang dipin → verifikasi Neutron 24 → tes host → siapkan kit →
kompilasi → periksa seluruh ABI → unggah bukti.

## 7. Installer

`anykernel/anykernel.sh`, teks **Inggris saja**, sesuai permintaan:

```
        ____                  _      __  __ _ _ __
       | __ ) _ __ ___  __ _ / _|  |  \/  (_) | | __
       |  _ \| '__/ _ \/ _` | |_   | |\/| | | | |/ /
       | |_) | | |  __/ (_| |  _|  | |  | | | |   <
       |____/|_|  \___|\__,_|_|    |_|  |_|_|_|_|\_\

   4.14.357-openela-Fresh-Milk-14.03

   Installing kernel

  [##.......................] 10%  Checking device
  [########.................] 35%  Writing boot image
  [##################.......] 75%  Finalising
  [#########################] 100%  Finished

   Kernel installed.
   Reboot when ready.
```

Tidak ada doa, tidak ada nama di layar, tidak ada auto-reboot.

Tiga hal yang **dihilangkan** dari installer lama dan akibatnya:

| Dihilangkan | Akibat |
|---|---|
| `do.modules=0` tetap | berkas modul tidak dipasang; modul ROM memakai yang ada |
| backup boot | **tidak ada jalan pulang dari installer ini**; cadangkan manual dulu |
| auto-reboot | user harus reboot sendiri (disengaja) |

## 8. Status klaim

| Tingkat | Status |
|---|---|
| Kompilasi | **belum dijalankan** |
| Statis (ABI, config) | akan diperiksa CI |
| Boot perangkat | **belum** |
| Teruji | **belum** |

Sesuai aturan kerja §1, tidak ada tingkat di atas yang boleh diklaim sebelum
bukti ada.
