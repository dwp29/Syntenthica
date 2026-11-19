# Aturan Kerja — Pembuatan Kernel Synthetica

Dokumen ini mengikat. Semua pekerjaan kernel di repositori ini tunduk pada aturan
di bawah. Aturan lahir dari kesalahan nyata yang sudah terjadi, bukan dari teori.

Terakhir diperbarui: 2026-10-31.

---

## 1. Klaim harus setara bukti

Ada empat tingkat bukti yang **tidak boleh dicampur**:

| Tingkat | Arti | Boleh diklaim sebagai |
|---|---|---|
| **Kompilasi** | Build CI lulus, artefak ada, sha256 cocok | "sudah dikompilasi" |
| **Statis** | Config, vermagic, CRC, signature, ekspor diperiksa | "lulus pemeriksaan statis" |
| **Boot** | Image benar-benar boot di perangkat | "terbukti boot" |
| **Operasional** | Root, kamera, thermal, baterai, suspend diuji | "teruji di perangkat" |

**Aturan:** jangan pernah menyebut tingkat yang lebih tinggi dari bukti yang ada.
"Sudah dikompilasi" bukan "sudah jalan". "Terbukti boot" bukan "semua fitur bekerja".

Saat ini:

- **3.1** — tingkat **operasional**. Terbukti boot dan Manager berjalan di
  Project Infinity X 4.1 (Android 17) dan Lunaris 3.13 (Android 16), dengan
  perbaikan AVB embedded unsigned.
- **3.2-r1** — tingkat **statis**. Kompilasi lulus, 359 tes lokal lulus, seluruh
  12.236 rekaman ekspor cocok dengan 3.1. **Belum pernah boot.**

---

## 2. Baca dokumen yang benar sebelum menyimpulkan

Repositori ini pernah punya **tiga** dokumen yang saling bertentangan tentang
"Synthetica 3.2". Membaca yang salah menghasilkan kesimpulan yang salah.

| Dokumen | Status | Isi |
|---|---|---|
| `SYNTHETICA-3.2.md` | **DITARIK** | Kembali ke basis 2.0, Clang 18, tanpa MGLRU/UCLAMP |
| `SYNTHETICA-3.2-r1.md` | kandidat dev | Dari resep 3.1, semua fitur dipertahankan |
| `artifacts/synthetica-3.2/STATUS.json` | historis | Detail build yang ditarik |

**Aturan:** sebelum membahas fitur atau versi, baca `SYNTHETICA-3.2-r1.md` dan
`artifacts/synthetica-3.2/STATUS.json`. Dokumen bertanda **DITARIK** tidak boleh
dipakai sebagai dasar rencana.

---

## 3. Versi diverifikasi dari source, bukan dari ringkasan

Ringkasan dokumen bisa usang. Angka versi **wajib** dibaca dari berkas sumber.

| Hal | Sumber kebenaran |
|---|---|
| Versi SuSFS | `include/linux/susfs.h` → `SUSFS_VERSION` |
| Versi kernel | `Makefile` → `VERSION`/`PATCHLEVEL`/`SUBLEVEL`/`EXTRAVERSION` |
| Nama rilis | defconfig → `CONFIG_LOCALVERSION` |
| Toolchain | `artifacts/*/STATUS.json` → `compiler.clang_version` |
| Config aktif | `generated.config.txt` hasil build, **bukan** defconfig mentah |

**Kesalahan yang pernah terjadi:** menyebut "Clang 18" karena membaca
`SYNTHETICA-3.2.md` (ditarik), padahal 3.1 dan 3.2-r1 memakai **Neutron Clang 24**.

**Kesalahan lain:** menyebut SuSFS "v1.5.9" karena membaca patch proyek **pure-noz**
di `build-kit/ci/patches/`. Itu proyek berbeda. Synthetica memakai **v2.3.0 NON-GKI**.

---

## 4. Jangan mencampur proyek

| Proyek | SuSFS | Root | Lokasi |
|---|---|---|---|
| **pure-noz-0.1** | v1.5.9 (patch eksternal) | KernelSU-Next UAPI 4 | `release/pure-noz-0.1/` |
| **Synthetica** | v2.3.0 in-tree | KernelSU-Next in-tree | `build-kit/ci/synthetica2-experimental/` |
| **Fresh-Milk / CHEESE-BURGER** | v2.4.0 (target) | BakaSU UAPI 6 | *belum ada* |

**Aturan:** patch, config, atau versi dari satu proyek tidak boleh dipinjam ke
proyek lain tanpa verifikasi ulang. Nama berkas yang mirip bukan bukti kesamaan.

---

## 5. Base dan resep yang dipakai

**Base source (dipin):**

```
Saamitk/kernel_xiaomi_sm6250-switchoff
commit c1e6f795b557b7bf92220c91f05a42b456de7a74
archive_sha256 a68c9e306a3e14de92a258b185531a2562e3631f616a74b7882fc2667ac10ec0
```

**Resep:** `build-kit/scripts/build_synthetica32_r1.py` — turunan resep 3.1 yang
sudah terbukti boot, ditambah dua patch MGLRU defensif.

**Aturan:** base mentah `c1e6f79` **bukan** Synthetica. Yang membuat kernel bisa
boot adalah **resep + patch + config fragment** di atasnya. Membangun dari base
mentah tanpa resep menghasilkan kernel yang berbeda.

---

## 6. Toolchain dipin, tidak dinaikkan tanpa alasan

```
Neutron clang version 24.0.0git
llvm_commit f42c87ba2c70219b1f4ad1f031a5b6a1ea6603fb
archive     neutron-clang-06092026.tar.zst
archive_sha256 531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30
```

**Aturan:** toolchain **tidak** dinaikkan sebagai bagian dari pekerjaan fitur.
Menaikkan toolchain mengubah kode yang dihasilkan di seluruh kernel dan
membatalkan perbandingan ABI. Kalau toolchain harus naik, itu pekerjaan tersendiri
dengan pengujian tersendiri.

Neutron 24 sudah lebih baru dari Clang 18. Arah "upgrade" bukan ke atas.

---

## 7. ABI dijaga, dan dibuktikan dengan angka

Build 3.1 yang terbukti boot punya:

```
exported_symbol_count   12236
module_layout_crc       0xed5659d1
```

**Aturan:** setiap build baru wajib membandingkan **seluruh** rekaman
`Module.symvers` terhadap baseline 3.1: nama, pemilik, jenis ekspor, dan CRC.
Bukan sampel, bukan sebagian. Perbedaan jumlah ekspor adalah **cacat**, bukan
variasi.

Modul ROM lama **tidak otomatis** cocok dengan build baru. Setiap kompilasi
menghasilkan sertifikat penandatangan modul baru, dan kepercayaan keyring ROM
belum diuji.

---

## 8. Config yang dimatikan punya alasan — baca komentarnya

Contoh nyata dari defconfig 3.2:

```
# CONFIG_KSU_SUSFS_TRY_UMOUNT is not set
#   The SuSFS v2.3.0-for-4.14 port ships no susfs_try_umount()/susfs_add_try_umount()
#   ... with this symbol enabled the KernelSU-Next fork would call missing functions
```

**Aturan:** sebelum menyalakan config yang mati, baca komentar di sekitarnya.
Kalau komentar menyebut alasan teknis, alasan itu harus **dibantah dengan bukti**
sebelum config dinyalakan. Menyalakan config karena "terlihat belum masuk" adalah
cara paling cepat membuat build gagal.

---

## 9. Dua varian = satu tree, dua fragment

Varian kernel **tidak** boleh menjadi fork terpisah. Semua varian berbagi source
dan patch yang sama; perbedaan hanya di fragment config.

**Aturan:**

- Patch inti berlaku untuk semua varian.
- Perbedaan varian dinyatakan sebagai fragment config, bukan `#ifdef` di source.
- Setiap varian punya `CONFIG_LOCALVERSION` sendiri.
- Nama rilis maksimum **64 karakter** (`__NEW_UTS_LEN`). Hitung sebelum menetapkan.

Varian yang direncanakan:

| Nama | Fokus | LOCALVERSION | Panjang |
|---|---|---|---|
| Fresh-Milk | stabilitas | `4.14.357-openela-Fresh-Milk-14.03` | 33 |
| CHEESE-BURGER | performa gaming | `4.14.357-openela-CHEESE-BURGER-11.08` | 37 |

---

## 10. Artefak bersih

**Aturan:**

- Tidak ada private key di artefak mana pun. `private_key_exported` wajib `false`.
- Artefak berisi image, config, `Module.symvers`, `System.map`, modul, sertifikat
  publik, dan checksum. **Bukan** boot image lengkap, DTB, DTBO, atau installer,
  kecuali memang itu yang sedang dibangun.
- Setiap artefak disertai sha256 dan dicatat di `STATUS.json`.
- Arsip bukti kompilasi **bukan** arsip flashable dan harus ditandai jelas.

---

## 11. Kejujuran tentang yang belum diuji

`STATUS.json` wajib memuat kolom eksplisit untuk hal yang belum diuji, dengan
nilai `NOT RUN` / `NOT VERIFIED` — bukan dikosongkan atau dihilangkan.

Contoh yang sudah dipakai dan harus dipertahankan:

```json
"physical_boot_root_thermal_battery_suspend_charging_tests": "NOT RUN"
"rom_vendor_module_abi_and_trust": "NOT VERIFIED"
```

**Aturan:** nilai `NOT RUN` adalah informasi, bukan aib. Menghapusnya adalah
kebohongan.

---

## 12. Urutan kerja wajib

1. Baca `SYNTHETICA-3.2-r1.md` + `STATUS.json`.
2. Verifikasi versi dari source (aturan 3).
3. Tetapkan base dan resep (aturan 5).
4. Tulis rencana perubahan config; baca komentar config terkait (aturan 8).
5. Bangun; bandingkan seluruh ekspor terhadap baseline (aturan 7).
6. Jalankan tes statis.
7. Catat status jujur di `STATUS.json` (aturan 11).
8. Boot **hanya** kalau ada perangkat dan izin eksplisit.
9. Naikkan tingkat klaim **hanya** setelah bukti tingkat itu ada (aturan 1).
