# Laporan Build Synthetica 2.0

**Status Kejujuran:** `COMPILED_ONLY_UNVERIFIED`  
**Catatan Penting:** Build berhasil dikompilasi dan diverifikasi secara kriptografis/struktural, namun **uji flash dan boot fisik di perangkat Xiaomi joyeuse (`miatoll`) BELUM dilakukan**. Hijau di build/CI **bukan** bukti kernel bisa boot; klaim *bootloop fix proven* tidak dibuat (`bootloop_fix_proven: false`, `physical_boot_root_tests: "NOT_RUN"`).

---

## 1. Verifikasi Paket Sumber (Google Drive)

Sumber tunggal dari folder Google Drive `Synthetica-2.0-SOURCE` (`1-vAkrPrUlwL5dqRY0IpV_1DDcLBf275C`):

| Bagian | Ukuran (Byte) | SHA-256 Terukur | Status vs `MANIFEST-GABUNGAN.txt` |
|---|---:|---|---|
| `Synthetica-2.0-SOURCE.zip.001` | `75497472` | `76f495a42d4e643a2c84bb3b2d3edb86380dcbecaf2ddbfb5df6ebe2a49335ee` | COCOK |
| `Synthetica-2.0-SOURCE.zip.002` | `75497472` | `1ac52b0c1215870ae9089bc88648a81d0e65315097db0c58aa3beade1d6dfaff` | COCOK |
| `Synthetica-2.0-SOURCE.zip.003` | `75497472` | `29c93c99535726780d59af325e19a6c7ca3278252721c09f95652f1febccef4a` | COCOK |
| `Synthetica-2.0-SOURCE.zip.004` | `59764666` | `34527e6dd7fc3a77c6fe3b26644a7cf0f8b50fd83618e7e498413e9013296d9c` | COCOK |
| **Hasil Gabungan (`Synthetica-2.0-SOURCE.zip`)** | **`286257082`** | **`45ade99e68f7a68f600639fb25ef78a9a225db37a12e26cf219d4b594be2a17a`** | **COCOK PERSIS** |

Keamanan kunci privat (`secretkey/synthetica-2.0.p12` & `secretkey/MANAGER-IDENTITY.json`):
- Hanya disimpan di direktori lokal sementara di luar repositori Git.
- **Tidak pernah** di-commit, **tidak pernah** di-upload ke GitHub/Secrets/Drive, dan **tidak pernah** ditampilkan isinya di log publik.
- Penandatanganan APK (`apksigner` dari `build-tools;36.1.0`) dilakukan secara lokal memakai `secretkey/synthetica-2.0.p12` (alias `synthetica`).

---

## 2. Lingkungan Mesin & Toolchain Build

- **OS & Mesin Kompilasi:** Ubuntu 24.04.5 LTS (`Noble Numbat`), 4 vCPU (`JOBS=4`), RAM 15 GiB, disk bebas > 80 GB
- **JDK & Android SDK (Langkah 1 - APK):**
  - OpenJDK Temurin 21 (`21.0.13` di kompilasi Gradle; `21.0.8` lokal untuk penandatanganan `apksigner`)
  - `platforms;android-36`, `build-tools;36.1.0`, `ndk;29.0.14206865`, `cmake;3.22.1` (`ANDROID_SDK_ROOT` diset)
- **Toolchain Kernel (Langkah 2 - Kernel):**
  - `Ubuntu clang version 18.1.3 (1ubuntu1)`
  - `Ubuntu LLD 18.1.3 (compatible with GNU linkers)`
  - `aarch64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
  - `arm-linux-gnueabi-gcc (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0`
  - Paket pendukung lengkap: `llvm-18 bc flex bison libssl-dev libelf-dev device-tree-compiler cpio lz4 xz-utils`

---

## 3. Hasil Akhir (3 Berkas Utama + Log Build)

Berkas tersedia di `out/` (sesuai skrip) serta disalin ke `release/` (agar tetap tersimpan di workspace viewer Arena & cabang Git `arena/96cbd65a-syntenthica`):

| Nama Berkas | Ukuran (Byte) | SHA-256 | Keterangan |
|---|---:|---|---|
| **`Synthetica-2.0.apk`** | `8637527` | `fef90c01a5620ba7251b85c07c62542339dad335baeb81f93b610262aed78d9d` | Manager APK (`net.ember.labs`, label **Synthetica**, tema glassmorphism iOS, `libksud.so` + `libkernelsu.so`, v2+v3 signed dengan `secretkey/synthetica-2.0.p12`) |
| **`Synthetica-2.0.zip`** | `21567245` | `b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c` | Paket flashable recovery AnyKernel3 (`Image.gz` + `ksud` + `anykernel.sh`, tanpa backup boot, tanpa auto-reboot, menulis install log) |
| **`Synthetica-2.0-LOG.zip`** | `861633` | `0832820bc4646a1069dd4b2ef96ce17a6cc5cc522080a9e668c730d644fd15c0` | Paket pengumpul log *read-only* untuk recovery (`<storage>/synthetica-logs/<waktu>/`) |
| **`BUILD-FULL.log`** | *(lihat `release/SHA256SUMS.txt`)* | *(lihat `release/SHA256SUMS.txt`)* | Log gabungan lengkap Langkah 1 (APK) + Verifikasi Sertifikat + Langkah 2 (Kernel) + Langkah 3 (Packaging) |

Artefak antara kernel (`artifacts/`):
- `artifacts/Image.gz`: `14570501` byte, SHA-256 `58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff`
- `artifacts/generated.config.txt`: SHA-256 `248af9218b5ed9dd82202956d99991f97428c3010565a810eac3c9e6f71ff33b`

---

## 4. Bukti Verifikasi Wajib

1. **Urutan Kerja:**
   - **Langkah 1 (APK dulu):** `KernelSU-Next @ 31946acd2f529b2b24e5e4f0267cfacb5d13498c` + overlay glass UI + injeksi `lib/arm64-v8a/libksud.so` (`5518552` B) + ditandatangani `secretkey/synthetica-2.0.p12` → menghasilkan `MANAGER.json` (`0x565` / `1381` B / `fe833710...`).
   - **Langkah 2 (Kernel):** `Saamitk/kernel_xiaomi_sm6250-switchoff @ c1e6f795b557b7bf92220c91f05a42b456de7a74` (pin SHA-256 `a68c9e306a3e14de92a258b185531a2562e3631f616a74b7882fc2667ac10ec0` `VERIFIED`), profil `synthetica`, menanam sertifikat APK dari Langkah 1 (`KSU_NEXT_MANAGER_SIZE=0x565`, `KSU_NEXT_MANAGER_HASH=fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`, `KSU_MANAGER_PACKAGE=net.ember.labs` — string hash & paket terverifikasi tertanam di dalam biner `Image.gz`).
   - **Langkah 3 (Paket Flashable):** `osm0sis/AnyKernel3 @ 41f04bdb4ee30a44e429c2c1131d5e8bb32b15f1` → `Synthetica-2.0.zip` & `Synthetica-2.0-LOG.zip` (CRC semua entri OK).

2. **String Versi Kernel (`artifacts/Image.gz`):**
   ```text
   Linux version 4.14.357-openela-Synthetica-2.0 (graziemille@rollercoaster-build) (Ubuntu clang version 18.1.3 (1ubuntu1), Ubuntu LLD 18.1.3) #1 SMP PREEMPT Sat Oct 31 09:27:40 UTC 2026
   ```

3. **Sertifikat Penanda Tangan APK (`out/Synthetica-2.0.apk`):**
   - Skema tanda tangan: APK Signature Scheme v2 (`true`) & v3 (`true`)
   - Ukuran DER sertifikat X.509: **`1381` byte (`0x565`)**
   - SHA-256 sertifikat: **`fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`**
   - Paket aplikasi: `net.ember.labs` | Label aplikasi: `Synthetica`

4. **Isi `anykernel.sh` di dalam `out/Synthetica-2.0.zip`:**
   - Memuat pembuka Arab: `بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ`
   - Memuat penutup sukses Arab: `الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ`
   - **Tidak memuat** perintah backup partisi boot (`boot_backup=disabled`).
   - Menulis log instalasi ke `<storage>/Synthetica/install-log-<waktu>.txt`.
   - Tanpa auto-reboot (`auto_reboot=no`), tanpa penulisan vbmeta/firmware/DTBO/bootloader.

5. **Audit Konfigurasi Kernel vs Referensi 1.16 (`reference-1.16/generated.config.txt`):**
   - Seluruh perubahan terhadap basis 1.16 murni level `.config`:
     - `CONFIG_LOCALVERSION="-Synthetica-2.0"`
     - `CONFIG_MQ_IOSCHED_DEADLINE=y` & `CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y`
     - `CONFIG_WQ_POWER_EFFICIENT_DEFAULT=y`
     - `# CONFIG_F2FS_STAT_FS is not set`
   - Tetap terjaga: `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `CONFIG_KSU_SUSFS=y`, `CONFIG_NOMOUNT=y`, `CONFIG_MODULE_SIG_FORCE=y`, tanpa overclock, tanpa ubahan thermal, tanpa SELinux permissive global.
