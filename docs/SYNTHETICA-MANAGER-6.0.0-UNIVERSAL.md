# Synthetica Manager 6.0.0 — Standalone & Universal Kernel Edition

**Paket:** `net.ember.labs` · **versionCode:** `70000` · **versionName:** `6.0.0` · **UAPI:** `4`
**Lokasi source mandiri:** `synthetica-manager/` (bukan lagi hasil patch pohon upstream)

---

## 1. Jawaban singkat: apakah APK Manager ini bisa dijadikan universal?

**Bisa — tapi dengan batas yang harus jujur dipahami.** Manager 6.0.0 sekarang punya dua
mode kerja:

| Mode | Kernel yang dipakai | Apa yang berfungsi | Apa yang TIDAK berfungsi |
|---|---|---|---|
| **NATIVE** | Synthetica / KernelSU-Next dengan **UAPI v4** dan `libksud.so` bawaan | Semua: modul, superuser, profil root, installer, boot patch, dll. | — |
| **UNIVERSAL ROOT BRIDGE** | Kernel pihak ketiga (stok OEM, Magisk, KernelSU resmi, APatch, lainnya) **selama `su` tersedia** | Control (4 profil daya/termal), Boost, Telemetri hardware/kernel, pemuat modul `.ko`, pembaca `dmesg`/`pstore`/boot audit, tema, backup JSON | Daftar modul KSU, manajemen Superuser KSU, install/patch boot image, SuSFS, hook `ksud` |

Jadi **APK-nya bisa dipasang dan berguna di kernel lain** — tetapi aplikasi **tidak bisa
"menjadi" root** di kernel yang tidak memiliki driver KernelSU. Root tetap harus datang dari
pihak lain (`su` dari Magisk/APatch/KSU resmi). Manager hanya menjadi *front-end root universal*
untuk fitur sysfs/procfs yang tidak butuh driver khusus.

**Batas teknis yang tidak bisa dilanggar:**

- Kernel butuh **driver** (`CONFIG_KSU`) untuk supercall UAPI. Tidak ada cara dari userspace
  untuk menambahkannya; itu harus dibangun ke dalam kernel (`Image`/`boot.img`).
- Penandatanganan APK harus tetap dengan sertifikat asli (`fe833710…`) agar kernel Synthetica
  mengenali Manager sebagai Manager sah. Mengganti sertifikat = kernel menolak.
- Aplikasi **tidak** melakukan *root exploit*; itu akan melanggar desain keamanan dan
  menyebabkan masalah hukum/kepercayaan.

---

## 2. Yang baru di 6.0.0

### 2.1 Source code mandiri
- Pohon Gradle penuh di `synthetica-manager/` — tidak ada lagi `git clone` KernelSU-Next
  saat build, tidak ada patching teks terhadap source upstream.
- Header `uapi/` di-*vendor* ke `app/src/main/cpp/uapi/` (symlink dihapus) sehingga pohon bisa
  di-*clone* dan di-*build* berdiri sendiri.
- Biner `libksud.so` **tidak** di-commit; diinjeksi saat build oleh
  `build-kit/scripts/build_manager_60_standalone.py` dari donor ter-*pin*
  (SHA-256 `c3059657…e4a427`, 5.518.544 byte) dan diverifikasi sebelum dipakai.
- `.gitignore` menolak `*.p12`, `*.jks`, `*.keystore`, `*.pem`, `*.key`, `*.der`, `jniLibs/`.

### 2.2 Universal Root Bridge
- `canActImmediate60()` → `(Natives.isManager && Natives.isFullFeatured()) || rootAvailable()`.
- `probeUniversalRoot60()` → membuka shell root sekali dan memastikan `id -u` = `0`.
- Home menampilkan kartu **"Universal kernel & root bridge"**: `NATIVE` (kernel Synthetica),
  `ACTIVE` (bridge hidup), atau `STANDBY` (belum ada `su`). Hero card menampilkan
  `UNIVERSAL ROOT` + `BRIDGE` saat aktif.
- Semua aksi Control/Boost/Universal memakai allowlist regex; tidak ada argumen bebas dari
  pengguna dan helper dijalankan lewat heredoc literal.

### 2.3 Empat profil daya & termal (`synthetica-control40.sh`)
| Profil | Governor | Batas frekuensi | GPU | `swappiness` |
|---|---|---|---|---|
| `profile_daily` | `schedutil` | 100% maks | level terendah | 60 |
| `profile_gaming` | `performance` | 100% maks | ~40% level | 40 |
| `profile_battery` | `schedutil` | **80% maks** | level terendah | 80 |
| `profile_cooldown` | `schedutil` | **70% maks** | level terendah | 80 |
| `profile_revert` | — | dipulihkan ke nilai asli per-boot | — | — |

Setiap penulisan sysfs disimpan dulu ke snapshot per-`boot_id`, ditulis, dibaca ulang, dan
diverifikasi. Jika pembacaan balik tidak cocok, nilai lama dipulihkan otomatis.

### 2.4 Telemetri, `.ko` loader, dan pembaca log (`synthetica-universal60.sh`)
- `telemetry` — semua policy cpufreq (`policy0`, `policy6`, tri-cluster), GPU KGSL, suhu
  baterai, memori/swap/ZRAM, MGLRU, TCP congestion, qdisc, dan scheduler I/O.
  **Terbukti read-only** di unit test (hash seluruh sysfs tidak berubah).
- `kmod_status` — status tiap modul: `LOADED`, `UNLOADED`, dan apakah file `.ko` tersedia
  atau `BUILT_IN_OR_NOT_FOUND`.
- `kmod_load:<modul>` / `kmod_unload:<modul>` — `ntfs`, `wireguard`, `zsmalloc`,
  `lz4_compress`, `zstd_compress`; mencari di `/data/adb/modules/synthetica_extra/vendor/lib/modules`
  lalu `/vendor/lib/modules`; menolak jika bukan root.
- `diag_dmesg` (80 baris terakhir), `diag_pstore` (maks 40 baris per file, deteksi "clean"),
  `diag_boot` (`uname -a`, SELinux, properti Verified Boot/slot, `/proc/cmdline`).
- Output dibatasi 300 baris × 600 karakter di sisi Kotlin agar UI tidak macet.

### 2.5 Kustomisasi lanjutan & backup/restore JSON
- Kecepatan animasi: **Normal 1.0×**, **Turbo 1.8×**, **Eco/Gentle 0.5×** — langsung mengubah
  durasi animasi `rememberStylePhase()`.
- **Export JSON ke clipboard** dan **Import JSON dari clipboard**
  (skema `synthetica-manager-6.0.0`, berisi tema, mode gelap, aksen, kilau, motion, kecepatan
  animasi). Import memakai validasi per kunci dan tidak pernah menulis di luar `SharedPreferences`.
- 46 string `manager60_*` tersedia lengkap dalam **Inggris** dan **Indonesia**
  (unit test memastikan tidak ada string yang hilang atau tak terpakai).

---

## 3. Identitas teknis yang dipertahankan

| Item | Nilai |
|---|---|
| Package ID | `net.ember.labs` |
| versionCode / versionName | `70000` / `6.0.0` |
| Sertifikat publik (harus sama) | `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140` |
| `libksud.so` (arm64-v8a) | SHA-256 `c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427` |
| JNI `libkernelsu.so` | identik dengan baseline 2.0 kecuali ELF build ID; `getManagerUAPIVersion` mengembalikan `4` |
| `libadbroot.so` | identik dengan baseline 2.0 kecuali ELF build ID |
| `META-INF/.../update-binary` + `updater-script` | byte-identik dengan baseline 2.0 |
| ABI | hanya `arm64-v8a` |

---

## 4. Cara membangun sendiri (reproducible)

```bash
# 1. Statis saja (tanpa SDK/NDK)
python3 build-kit/scripts/build_manager_60_standalone.py --verify-only

# 2. Build penuh (butuh JDK 21, Android SDK 36, NDK 29, CMake 3.22)
ANDROID_SDK_ROOT=/path/to/sdk \
python3 build-kit/scripts/build_manager_60_standalone.py \
  --workdir /tmp/manager60 \
  --output artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk
```

Pohon `synthetica-manager/` juga bisa dibuka langsung di Android Studio (Gradle wrapper 9.2.0,
AGP 8.13.1, Kotlin 2.2.0). Untuk build lokal dengan kunci sendiri:

```bash
cd synthetica-manager && ./gradlew :app:assembleRelease
```

> Catatan: build Gradle langsung akan menghasilkan APK **tanpa** `libksud.so` (karena
> `jniLibs/` di-ignore). Gunakan skrip Python di atas untuk APK yang lengkap.

### Penandatanganan dengan kunci asli

```bash
python3 build-kit/scripts/sign_manager_60_locally.py \
  --apk artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk \
  --expected-sha256 <SHA-256 hasil build> \
  --keystore /path/di/luar/repo/synthetica-2.0.p12 \
  --alias synthetica \
  --out Synthetica-Manager-6.0.0-Universal-SIGNED.apk \
  --build-tools $ANDROID_SDK_ROOT/build-tools/36.1.0
```

Skrip akan: memvalidasi badging `net.ember.labs / 70000 / 6.0.0`, menjalankan
`zipalign -c -p 4` dan `-c -P 16 4`, menjalankan `tests/verify_synthetica60_apk.py`,
memastikan APK input memang **belum** tertandatangani, memverifikasi sertifikat, menandatangani
dengan `apksigner` (v2+v3), lalu memastikan **payload non-tanda tangan tidak berubah**.

---

## 5. Pengujian yang dijalankan

| Lapis | Cakupan | Status |
|---|---|---|
| Unit host (27 test) | Pohon mandiri, versi, tanpa rahasia, allowlist aksi, bridge `su`, animasi + JSON, 46 string en/id, 4 profil | Lulus |
| Shell helper (fake `/sys`, `/proc`) | `telemetry` read-only, `kmod_status/load/unload`, `diag_*`, `profile_battery` 80%, `profile_cooldown` 70%, `profile_revert` | Lulus |
| Signing gate (5 test) | Sertifikat asli saja, v2+v3, payload identik, tanpa password di argumen | Lulus |
| Statis APK | Identitas, permission set = 2.0, UAPI 4, `libksud` ter-*pin*, alignment 4B/16KB, unsigned | Lulus |
| Suite repo penuh | 511 test | Lulus (126 skip karena prasyarat host) |

**Tidak** diuji: instalasi di ponsel fisik, `su` sungguhan, pemuatan modul `.ko` nyata,
dan perilaku boot. Klaim di dokumen ini hanya sebatas pengujian di atas.

---

## 6. Kompatibilitas Device Check

Layar **Device Check** adalah pengamatan, bukan atestasi. Pada kernel pihak ketiga ia akan
melaporkan `rootAccessible = true` (dari `su`) tetapi SuSFS, modul KSU, dan Zygisk KSU akan
`Tidak tersedia` — itu **wajar**, bukan kerusakan.

---

## 7. Perubahan setelah rilis 6.0.0 pertama (belum masuk APK bertanda tangan)

Tiga perubahan di bawah ini ada di source `main` tetapi **belum** ada di APK
`Synthetica-Manager-6.0.0-Universal-SIGNED.apk` yang sudah diunggah. APK baru
butuh build CI + tanda tangan ulang.

### 7.1 Urutan shell root dibetulkan

| Sebelum | Sesudah |
|---|---|
| `libksud.so debug su -g \|\| su --mount-master \|\| sh` | `su --mount-master \|\| su \|\| libksud.so debug su --global-mnt \|\| sh` |

Alasan: `libksud.so` selalu ada di dalam APK, jadi kalau ia dicoba lebih dulu ia
menutupi `su` milik kernel pihak ketiga. Pada kernel SELAIN Synthetica perintah
itu gagal, lalu rantai jatuh ke `sh` — shell **biasa**, bukan root.

### 7.2 Deteksi root tidak lagi memakai exit code

`probeUniversalRoot60()` dulu menilai `result.isSuccess` dari seluruh rantai
`... || sh`. Karena `sh` hampir selalu berhasil, hasilnya `true` meski UID-nya
2000. Helper lalu berjalan tanpa hak root dan gagal diam-diam.

Sekarang probe memakai status shell libsu (`shell.isRoot`, diisi setelah `id`
mengembalikan `uid=0`) plus konfirmasi `id -u` == `0`.

### 7.3 Halaman About: pembuat, source, lisensi, donasi

- Pembuat: **Pure_Saturday**, Telegram [@Pure_Saturday](https://t.me/Pure_Saturday).
- Source lengkap: <https://github.com/dwp29/Syntenthica>, dengan penawaran source
  eksplisit di [`synthetica-manager/SOURCE-OFFER.md`](../synthetica-manager/SOURCE-OFFER.md).
- Lisensi: `GPL-3.0-only`, teks penuh di [`synthetica-manager/LICENSE`](../synthetica-manager/LICENSE),
  atribusi pihak ketiga di [`synthetica-manager/NOTICE`](../synthetica-manager/NOTICE).
- Donasi: **slot placeholder** (`AppCredit60.DONATE_URL = ""`). Baris tampil
  nonaktif dengan label `SOON`; tidak ada dompet atau tautan karangan.

### 7.4 Status verifikasi

`tests/test_synthetica60_standalone.py` + `tests/test_synthetica60_signing.py`
lulus (35 test), termasuk penjaga regresi:
- locale tidak boleh tertukar antara `values/` dan `values-in-rID/`;
- `su` harus dicoba sebelum `libksud.so`;
- probe root harus memakai `shell.isRoot`, bukan exit code;
- slot donasi harus tetap placeholder nonaktif;
- `detectRootChannel()` harus `suspend` + `Dispatchers.IO` (pernah hilang dan
  membuat probe jalan di main thread).

Seluruh suite repo juga dijalankan ulang dari pohon yang sekarang: **515 test,
0 gagal** (126 skip karena prasyarat host), termasuk gate statis 6.0.0
(`[verify] net.ember.labs 6.0.0 (70000); UAPI 4; standalone tree OK`).

### 7.5 Kompilasi: terbukti di CI

Kompilasi Kotlin **berhasil** di GitHub Actions. Riwayat lengkapnya penting
supaya tidak ada yang mengulang jalan buntu yang sama:

| Run | Commit | Hasil |
|---|---|---|
| `42747467198` | `e83d3a4` | `startup_failure` — 0 job |
| `42747877219` | `8bd4de8` | gagal `aapt2`: `strings_manager50.xml:19` (apostrof mentah `kernel's`) |
| `42749580793` | `410200b` | gagal Kotlin: `unresolved reference: build` di `KsuCli.kt:160` |
| `42750759962` | `8106db7` | **sukses** — langkah 6 (compile) dan 7 (verify) lulus |

Dua kegagalan itu bukan masalah lingkungan, melainkan bug di pohon ini, dan
keduanya sekarang dijaga regresi:

- apostrof mentah di `strings.xml` membuat `aapt2` mati. Dijaga oleh
  `test_strings_are_valid_aapt_input`.
- deklarasi top-level ganda (`createRootShellBuilder` di baris 73 **dan** 143)
  menghasilkan pesan menyesatkan `unresolved reference: build` di titik
  pemanggilan. Dijaga oleh `test_no_duplicate_top_level_declarations`.

Keduanya sudah dibuktikan **gagal saat bug disuntikkan kembali**, jadi
penjaganya bukan test kosong.

Pelajaran operasional: workflow di branch non-default bisa gagal dijadwalkan
(`startup_failure`) bila menarik reusable workflow lewat `uses:` lintas-branch.
Jalan yang berhasil adalah menyalin langkah build secara utuh ke workflow di
`main` (`manager60-run.yml`, `workflow_dispatch` saja). Jangan mengubah nama
berkas workflow: workflow yang di-rename tidak terdaftar dan tidak bisa
di-rerun.

### 7.6 APK final

Artifact CI (unsigned) ditandatangani di luar CI dengan kunci Synthetica asli.

| Properti | Nilai |
|---|---|
| Berkas | `Synthetica-Manager-6.0.0-Universal-SIGNED.apk` |
| Ukuran | `8.990.470` byte |
| SHA-256 | `666b24b6d4e7835a5b03b7e5e40f77676820f827d0130aad2d96a120a4dd9cac` |
| Skema tanda tangan | v2 `true`, v3 `true`, v1 `false` |
| Sertifikat (SHA-256) | `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140` |
| Package / versi | `net.ember.labs` / `6.0.0` (`70000`), label `Synthetica` |
| Native code | `arm64-v8a` |

Artifact unsigned dari CI: `8.927.711` byte, SHA-256
`7f3333b6efbc9c6ee9e61d7514cdd64783b776b51eac16af9880874bc11bd5c8`.
Perbandingan isi ZIP: 642 entri sebelum dan sesudah, **tidak ada satu pun entri
payload yang berubah**; satu-satunya tambahan adalah `META-INF/MANIFEST.MF`,
`SYNTHETI.SF`, dan `SYNTHETI.RSA`.

Verifikasi isi APK final:

- `apksigner verify --verbose --print-certs` → `Verifies`, v2 dan v3 `true`.
- `tests/verify_synthetica60_apk.py` → semua gate lulus, termasuk halaman About.
- Rantai root di DEX: literal `su --mount-master || `, `su || `, ` || sh`,
  ` debug su`, dan ` --global-mnt` semuanya ditemukan. Pencarian frasa gabungan
  gagal hanya karena R8 memecah string menjadi literal per-bagian.
- `RootChannel` tidak ditemukan sebagai literal karena R8 me-rename nama kelas
  di build release; ini normal, bukan regresi.
- URL donasi karangan tidak ditemukan di DEX.

**Yang tetap belum diverifikasi:** instalasi di perangkat Android, root `su`
sungguhan, pemuatan modul nyata, dan perilaku boot. APK ini lolos kompilasi,
tanda tangan, dan pemeriksaan isi — bukan uji perangkat.
