# Synthetica 3.2 — Audit Fitur, Rilis Lintas-ROM, dan Panduan Pengembangan

## 1. Audit Kelengkapan Fitur Synthetica 3.0 -> 3.1 -> 3.2

Seluruh fitur kernel **Synthetica 3.0** (`4.14.357-openela-synthetica-3.0`) telah terkonfirmasi **100% masuk** di `Synthetica-3.1-AVB-Fix-TEST.zip` maupun di rilis final **`Synthetica-3.2.zip`** (`4.14.357-openela-synthetica-3.2`).

### Pohon Sumber & Toolchain
- **Kernel Tree**: `Saamitk/kernel_xiaomi_sm6250-switchoff` @ `c1e6f795b557b7bf92220c91f05a42b456de7a74` (`4.14.357-openela`)
- **KernelSU-Next**: `KernelSU-Next/KernelSU-Next` @ `d86ff76cd7f8efab5fb7ebfd6ab7ef6b3b3b9f50` (Rollercoaster `34000`, manual hook)
- **Toolchain**: Neutron Clang 18.0.0 (`06092026`, SHA-256 `531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30`)

### 8 Patch Inti (Identik 3.0 = 3.1 = 3.2)
1. `0001-mglru-4.14.patch` — Backport Multi-Gen LRU (MGLRU) untuk Linux 4.14
2. `0002-uclamp-walt-stune.patch` — Integrasi Utilization Clamping (UCLAMP) dengan WALT & Schedtune
3. `0003-uclamp-correctness.patch` — Perbaikan akurasi bucket/agregasi UCLAMP
4. `0004-mglru-anon-file.patch` — Perbaikan aging anonymous/file page MGLRU
5. `0005-mglru-pagewalk-caf.patch` — Kompatibilitas pagewalk MGLRU pada tree CAF SM6250
6. `0006-neutron-enum-cast.patch` — Perbaikan kompilasi enum cast di bawah Clang 18
7. `0001-ksu-manager-preserve-seccomp.patch` — Preservasi flag seccomp proses Manager
8. `0001-manager-fd-after-exec.patch` — Pengiriman fd komunikasi Manager pasca-`execve` (`ksu_install_manager_exec_fd`)

### Konfigurasi Kernel & Simbol ABI
- Satu-satunya perubahan `.config` dari 3.0 (`253a89a3...`) ke 3.1 (`4b53a2cb...`) ke 3.2 (`72be9099...`) adalah `CONFIG_LOCALVERSION="-synthetica-3.2"`.
- `Module.symvers` (`1ce7153529b53f3f4bf361ea2e061ec575e712cd47cc5a0f10a854cf91d19ac3`) **100% identik** antara 3.0, 3.1, dan 3.2 (12.236 simbol diekspor, `module_layout` CRC `0xed5659d1`).
- Fitur aktif:
  - **MGLRU**: `CONFIG_LRU_GEN=y`, `CONFIG_LRU_GEN_ENABLED=y`, `CONFIG_NR_LRU_GENS=7`, `CONFIG_TIERS_PER_GEN=4`
  - **UCLAMP + WALT**: `CONFIG_UCLAMP_TASK=y`, `CONFIG_UCLAMP_TASK_GROUP=y`, `CONFIG_UCLAMP_BUCKETS_COUNT=5`, `CONFIG_SCHED_WALT=y`
  - **Memori & Jaringan**: `CONFIG_ZRAM=y`, `CONFIG_CRYPTO_LZ4=y`, `CONFIG_CRYPTO_ZSTD=y`, `CONFIG_TCP_CONG_BBR=y`
  - **Root & Keamanan**: `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `CONFIG_MODULES=y`, `CONFIG_MODVERSIONS=y`, `CONFIG_MODULE_SIG=y`, `CONFIG_MODULE_SIG_FORCE=y`, `CONFIG_MODULE_SIG_SHA512=y`
  - **Identitas Manager**: `net.ember.labs` (`expected_size=996`, `expected_sha256=fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`)

---

## 2. Perbaikan Installer Lintas-ROM di Synthetica 3.2

- **Akar Masalah Bootloop di Project Infinity X 4.1 (A17)**:
  Boot image `Project Infinity X 4.1` memiliki footer `AVBf` + struktur `AVB0` tanpa tanda tangan kriptografis (`algorithm_type = 0 / NONE`). Saat AnyKernel3 (`magiskboot repack`) mengganti `Image.gz`, ukuran image di footer `AVBf` diperbarui tetapi `image_size` dan digest SHA-256 di dalam Hash Descriptor `AVB0` tetap berisi nilai kernel lama, sehingga ditolak bootloader saat verifikasi AVB.
- **Solusi Lintas-ROM (`tools/fix-avb --if-unsigned`)**:
  - Jika `boot.img` asal adalah stock `Project Infinity X 4.1` (`d33c01c2...`), installer menampilkan log eksplisit dan memperbaiki `image_size` serta digest SHA-256 pada descriptor `AVB0`.
  - Untuk ROM lain (termasuk re-flash/upgrade di atas `boot.img` yang sudah terpasang Synthetica atau varian ROM A17 lain), `tools/fix-avb --if-unsigned` secara otomatis memperbaiki descriptor **hanya jika** memiliki footer `AVBf` + `AVB0` unsigned (`algorithm_type == 0`).
  - Untuk ROM tanpa footer `AVBf` atau dengan AVB bertanda tangan penuh (seperti **Lunaris AOSP 3.13 A16**), `tools/fix-avb --if-unsigned` keluar dengan kode `0` tanpa menyentuh byte apa pun (`O_RDONLY`).
- **Teruji di Perangkat Fisik (`miatoll`)**:
  - **Project Infinity X 4.1 (Android 17)** — Boot normal, root & Manager APK aktif.
  - **Lunaris AOSP 3.13 (Android 16)** — Boot normal, root & Manager APK aktif.

---

## 3. Identitas Artefak Synthetica 3.2

| Komponen | Nilai / Path | SHA-256 |
|---|---|---|
| **Paket Recovery Flashable** | `Synthetica-3.2.zip` (`21,754,839` byte) | `a8e5d1eb09a0558c69de841fcf64987689e0e694bcec6f45fc43421f4edc52fb` |
| **Kernel Image (`Image.gz`)** | `4.14.357-openela-synthetica-3.2` (`14,533,460` byte) | `7ebbe4b263adad8cb780025fab7dc8f7faf9de2e671eaafa14c6081a9d40813e` |
| **Kernel `.config`** | `artifacts/synthetica-3.2/generated.config.txt` | `72be909960649924ad36eb21ed45efe0f8c064d8c668d940aea2b0c027e44430` |
| **`Module.symvers`** | `artifacts/synthetica-3.2/Module.symvers.txt` | `1ce7153529b53f3f4bf361ea2e061ec575e712cd47cc5a0f10a854cf91d19ac3` |
| **`System.map`** | `artifacts/synthetica-3.2/System.map.txt` | `d505b872733137313fd040dc9b5fb8363fbeea973ebb79f3eebcaef26de84d7b` |
| **Sertifikat Publik Modul** | `artifacts/synthetica-3.2/kernel-module-public-cert.x509` | `8d32632bc1ee4c3103142436be0b1ef1a163aeb75ab3b4d655b9b346b6f8edb3` |
| **Helper ARM32 Statis** | `tools/fix-avb` (`463,980` byte) | `656c2cb4c3d9aa189cbc325e4c928dc002c03b93ddd777b688248d95734e2706` |
| **Daemon Root (`ksud`)** | `ksud` (`5,518,552` byte) | `52ba3da465459bfbac98dd25c53f8d31f93ee5a8ee89d84f67a28fe0d18cdef2` |
| **Bukti Kompilasi CI** | Git blob `289351e7832eaa4ca1acde0ea2b1a837b1e3391b` (run `42617952429`) | `0ef3f1fd1ab47bb91e594837d2b9c1a50673fcd4fd0db57f149b482e4f8c3ba4` |

---

## 4. Struktur Berkas untuk Pengembangan ke Depan

1. **Recipe & Pemaket 3.2**:
   - `build-kit/scripts/build_synthetica32_final.py` — Recipe kompilasi kernel + 6 modul `.ko` bertanda tangan same-build + verifikasi invarian `.config` dan `Module.symvers`.
   - `build-kit/scripts/package_synthetica32_final.py` — Pemaket deterministik `Synthetica-3.2.zip` dengan integrasi `tools/fix-avb --if-unsigned`.
   - `build-kit/ci/s31-avb-fix/fix_avb.c` — Source C helper perbaikan descriptor AVB0 unsigned lintas-ROM.
2. **Bukti Build & DevKit 3.2**:
   - `build-kit/ci/synthetica32-final-build-evidence.json` — Manifest hash terverifikasi dari run CI `42617952429`.
   - `artifacts/synthetica-3.2/` — Berisi `STATUS.json`, `generated.config.txt`, `Module.symvers.txt`, `System.map.txt`, `kernel-module-public-cert.x509`, `signed-modules/*.ko`, dan `SHA256SUMS.txt`.
3. **Pengujian Otomatis & CI**:
   - `tests/test_synthetica31_avb_fix.py` — Uji unit helper `fix-avb` (mode default & `--if-unsigned`, penolakan signed/corrupt AVB, symlink guard).
   - `tests/test_synthetica32_final_qemu.py` — Uji integrasi ARM QEMU lintas-ROM (synthetic boot, fresh flash Project Infinity X 4.1, dan re-flash/upgrade langsung).
   - `.github/workflows/synthetica32-final.yml` — Workflow kompilasi penuh kernel + modul + helper.
   - `.github/workflows/synthetica32-package.yml` — Workflow verifikasi cepat bukti kompilasi, pemaketan deterministik, dan pengujian ARM QEMU.
4. **Cadangan Synthetica 4.0 (SUSFS v2.0.0)**:
   - Tetap terisolasi dan aman di `build-kit/ci/synthetica40/`, `build-kit/ci/s40-susfs-abi/`, `build-kit/scripts/build_synthetica40.py`, serta folder Google Drive Backup 4.0 (`1lbfYSfVN7ZZ7q5BiqIzD03BLRRJQ28-D`).
