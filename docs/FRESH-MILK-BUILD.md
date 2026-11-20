# Fresh-Milk / CHEESE-BURGER — Panduan Build

Dua varian, satu tree, satu resep induk (`build_synthetica32_r1.py`).
Perbedaan varian **hanya identitas rilis**. Tidak ada kode, patch, toolchain,
SuSFS, atau root yang berbeda.

> **Catatan 2026-10:** tree ini sekarang juga membangun kedua varian di **stack
> BakaSU** (root alternatif, manual hook tanpa SuSFS). Bukti build, empat
> perbaikan yang dibutuhkan, dan jebakan untuk pengembangan ada di **§9**.

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

---

## 9. Stack BakaSU (root alternatif pada tree 4.14)

Selain KernelSU-Next, tree ini dapat dibangun dengan **BakaSU** sebagai root
stack. Kedua varian (`fresh-milk`, `cheese-burger`) sekarang membangun di stack
ini. Catatan ini untuk pengembangan kelak: apa yang berbeda, apa yang sudah
diperbaiki, dan jebakan yang sudah dipastikan.

### 9.1 Cara stack dipilih

- `build-kit/scripts/build_fresh_milk.py` menandai tiap varian dengan
  `root_stack: 'bakasu'` di tabel `VARIANTS`.
- `apply_variant()` memasang **`SP_ROOT_STACK`** di environment (di `main()`,
  bukan di fungsi yang dipanggil tes langsung, agar tidak bocor ke tes lain).
- Resep 3.2-r1 memeriksa `SP_ROOT_STACK == 'bakasu'` untuk memicu integrasi
  BakaSU. **Jangan** kunci pada `BAKASU_ARCHIVE` di tahap `finish`: variabel itu
  hanya ada di langkah prepare/compile, sedangkan langkah finish hanya membawa
  `FM_VARIANT`.
- `BAKASU_ARCHIVE` tetap dipakai di `prepare_tree()` (tahap compile) karena di
  situ archive memang sudah diekstrak.

### 9.2 Layout tree BakaSU

- `drivers/kernelsu` adalah **symlink** ke `../BakaSU/kernel` (dibuat oleh
  `bakasu_root.py::apply_tree_patch`).
- `BakaSU/kernel/Kbuild` ditambal menambahkan
  `ccflags-y += -I$(src)/../compat-4.14`; `compat-4.14/linux/` membawa
  `hex.h`, `minmax.h`, `pgtable.h`, `unaligned.h` (header pasca-4.14 yang
  tidak ada di tree ini).
- Directory `KernelSU-Next/` **tetap ada** di tree (patch seccomp/setuid-hook
  dari resep warisan diterapkan ke sana). Yang **tidak** ada:
  `ksu_install_manager_exec_fd`, `KernelSU-Next/kernel/supercall/`, dan flag
  build manager `-fno-builtin-strncmp`.

### 9.3 Empat perbaikan yang dibutuhkan (semua sudah masuk CI)

1. **`generated/compile.h`** — BakaSU `init.c` menyertakan
   `<generated/compile.h>`. Berkas ini dihasilkan oleh aturan `init/Makefile`
   sebagai prasyarat `init/version.o`, **bukan** oleh `prepare`. KernelSU-Next
   tidak menyertakannya, jadi `drivers/kernelsu/` dulu dibangun sebelum `init/`
   tanpa masalah. Pada BakaSU, `build-rollercoaster.sh` sekarang membangun
   `init/version.o` **sebelum** `drivers/kernelsu/`.
2. **Gerbang export ABI** — `compare_31_exports` membandingkan
   `(crc, owner, kind)`. BakaSU menggeser layout tautan, jadi **8193 alamat
   simbol bergeser** meski ABI (nama/owner/tipe) sama persis (`missing=0
   added=0`). `build_fresh_milk.py` membandingkan ABI (nama/owner/tipe) dan
   mengizinkan delta crc di stack BakaSU; stack KernelSU-Next tetap menggunakan
   gerbang ketat asli.
3. **Verifikasi finish yang hanya berlaku KernelSU-Next** — rantai finish
   (`3.2-r1 → 3.0-root → 3.0-rc1 → 2.0-experiment`) menjalankan pemeriksaan
   sumber/objek yang ditulis untuk root KernelSU-Next. Pada stack BakaSU,
   semuanya dilewati saat `SP_ROOT_STACK=bakasu` dan dicatat sebagai tidak
   berlaku di status:
   - `build_synthetica3_root.finish`: `verify_root_source`, `verify_exec_objects`
   - `build_synthetica3_rc.finish`: `verify_hook_object` (dan `verify_source`)
   - `build_synthetica2_experimental.finish`: `verify_manager_object`, serta pin
     hash sertifikat Manager di dalam image (BakaSU mengenali Manager lewat
     indeks signature APK, bukan literal hash)
   Pemeriksaan yang berlaku umum (config, image, cert, modul, ABI) tetap
   berjalan di kedua stack.
4. **`SP_PROFILE` di langkah prepare** — `resolve_hook_choice()` berjalan di
   `prepare()` dan menulis ulang profil yang akan dibangun. Langkah prepare
   dulu hanya membawa `FM_VARIANT`, sehingga `SP_PROFILE` jatuh ke default
   `synthetica`. Varian lain (cheese-burger → `critical`) tidak pernah
   ditesolusi: SuSFS tetap on dan manual hook dropped, lalu compile gagal di
   gerbang retained-feature. Workflow sekarang mengirim `SP_PROFILE` dari
   matrix ke env langkah prepare.

### 9.4 Resolusi hook choice

BakaSU menempatkan tracepoint / manual hook / SuSFS dalam satu `choice` Kconfig.
Pada 4.14 hanya **manual hook** yang valid. `resolve_hook_choice()`:

- mematikan seluruh keluarga `CONFIG_KSU_SUSFS*` dan
  `CONFIG_KSU_TRACEPOINT_HOOK` (`=y` → `# ... is not set`);
- menambahkan `CONFIG_KSU_MANUAL_HOOK=y`;
- hanya menyentuh `00-common.config` dan `<profil>.config` (tidak semua profil).

Tanpa ini, `olddefconfig` memilih SuSFS dan mengalahkan manual hook — inilah
sebabnya SuSFS **harus** distrip dari profil **sebelum** build.

### 9.5 Bukti build (run CI 44726068179, kedua varian sukses)

| | Fresh-Milk-14.03B | CHEESE-BURGER-11.08B |
|---|---|---|
| profil | `synthetica` | `critical` |
| `image_sha256` | `ddb75b68…08abe58` | `309d1bc1…0a7d0be6` |
| ZIP | `Fresh-Milk-14.03B.zip` (19.761.514 B) | `CHEESE-BURGER-11.08B.zip` (19.764.420 B) |
| `sha256` ZIP | `03d740ee…5452c07525` | `bdd1bbe2…0d30af69a36d` |

Delta config = tepat `BAKASU_CONFIG_DELTA` (KSU hook/identitas + simbol
`KSU_SUSFS*` + `LOCALVERSION`), plus delta profil gaming untuk cheese-burger.

### 9.6 Catatan untuk pengembangan kelak

- **Jangan** menambal `apk_sign.c` BakaSU dengan patch KernelSU-Next; BakaSU
  menolak blok v3 di APK (v1+v2 cukup).
- **Jangan** mem-build BakaSU sebelum hook dipasang.
- Pin `build-rollercoaster.sh` (digest di `PINNED_INPUTS`) **harus** diperbarui
  setiap kali skrip itu berubah — ada tes yang mengecek digest ini.
- Perubahan ke `build-rollercoaster.sh` / `build_synthetica3.py` /
  `build-fresh-milk.py` memicu workflow (jalur `paths` sudah mencakupnya).
  Commit kosong **tidak** memicu (filter `paths` butuh perubahan berkas nyata).
- `gh run rerun` tidak tersedia untuk job; untuk memicu ulang, buat commit
  berkas nyata atau gunakan `workflow_dispatch`.
- Sandbox **tidak bisa** mengunduh aset rilis / artifact CI (host
  `release-assets.githubusercontent.com` dan blob hasil produksi diblokir).
  Download ZIP dilakukan dari tautan rilis di luar sandbox.
- **Jebakan installer (perbaikan `083b795`):** `ak3-core.sh` (dari skeleton
  `Synthetica-2.0.zip`) membaca partisi target dari **`$BLOCK` (uppercase)** di
  `setup_ak`/`write_boot`. `anykernel.sh` rollercoaster harus set
  **`BLOCK=` (uppercase)**. Kalau pakai lowercase `block=`, `$BLOCK` kosong →
  `setup_ak` masuk branch `*` → `parttype` kosong → `target` kosong → abort
  **`Unable to determine  partition`** (spasi ganda = `$BLOCK` kosong) →
  recovery `Updater process ended with ERROR: 1`, ZIP gagal flash. Packager
  (`package_fresh_milk.py`) kini menjaga nama ini via `require()` dan test
  `test_installer_block_var_matches_ak3_core`.
- Build hanya bisa dikompilasi lewat CI (sandbox tidak punya clang/cross-
  compiler aarch64). Reproduksi config lokal dengan `make olddefconfig` + gcc
  host masih mungkin untuk mengecek gerbang config.

### 9.7 Status klaim (stack BakaSU)

| Tingkat | Status |
|---|---|
| Kompilasi | **lulus** (run 44726068179) |
| Statis (ABI, config) | **lulus**, ABI 0 selisih, crc bergeser seperti yang diizinkan |
| Paket flashable | **lulus** — ZIP + installer + penjaga digest |
| Boot perangkat | **belum** |
| Teruji | **belum** |

Kernel ini menggunakan **manual hook tanpa SuSFS**; Manager APK bertanda tangan
**ephemeral**. Bukti fisik boot dan kecocokan modul ROM tetap belum ada.
