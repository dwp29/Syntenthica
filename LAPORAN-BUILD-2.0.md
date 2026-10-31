# Laporan Build Synthetica 2.0 (UAPI v4 + iOS Liquid Glass GPU Blur)

**Status Kernel & Manager:**
- **Kernel (`Synthetica-2.0.zip`):** Terkonfirmasi **berhasil boot normal** di perangkat fisik Xiaomi Redmi Note 9 Pro (`joyeuse` / `miatoll`) dengan identitas `4.14.357-openela-Synthetica-2.0` dan driver `ksun-legacy-susfs-v2 (34000-4)` (UAPI v4). Seluruh modul boot (`/data/adb/modules`: `OverlayFS 1.3.1`, `Zygisk Next 1.5.2`, `service.d`, `post-fs-data.d`) berjalan normal saat boot melalui `/data/adb/ksud`.
- **Manager APK (`Synthetica-2.0.apk` — Revisi UAPI v4 + iOS Liquid Glass):** Dikompilasi ulang dari `KernelSU-Next @ ea51427ff700f73909e7e8c8717cc3241322ee1e` (**UAPI v4 murni**, cocok 100% dengan kernel `34000-4` dan `libksud.so`), tema **iOS Liquid Glass dengan GPU Blur nyata** (`RenderEffect` / `GraphicsLayer` `BlurEffect`), tata letak menu identik 1:1 dengan Manager 1.16 (`Rollercoaster` → rebrand penuh ke **`Synthetica`**), *splash screen* 3D Liquid Glass baru, ikon peluncur 3D Liquid Glass baru, tanpa notifikasi *update nag* upstream `KernelSU-Next`, dan ditandatangani lokal memakai kunci privat yang sama (`secretkey/synthetica-2.0.p12`, sertifikat `0x565` / `fe833710...`) sehingga **cukup di-install langsung (in-place update) tanpa perlu flash ulang kernel**.

---

## 1. Akar Masalah Modul Tidak Muncul di APK Sebelumnya (Padahal Aktif Saat Boot)

1. **Mengapa modul tetap berjalan saat boot:** Eksekusi modul (`OverlayFS`, `Zygisk Next`, `post-fs-data.d`, `service.d`) ditangani langsung oleh daemon **`/data/adb/ksud`** bersama driver kernel **`ksun-legacy-susfs-v2 (34000-4)`** saat inisialisasi sistem Android — **tidak bergantung** pada aplikasi Manager.
2. **Mengapa modul sempat tidak tampil di UI Manager sebelumnya:** Commit `KernelSU-Next` yang lebih baru (`31946acd`) telah menaikkan protokol komunikasi JNI `KERNEL_SU_UAPI_VERSION` ke **v6**, sedangkan kernel `4.14.357-openela-Synthetica-2.0` (`34000-4`) menggunakan **UAPI v4**. Fungsi `Natives.isFullFeatured()` memeriksa kecocokan persis `kernelUAPIVersion (4) == managerUAPIVersion`; ketika tidak sama (`4 != 6`), Manager masuk ke mode terbatas dan menyembunyikan tab `Superuser` serta `Module`.
3. **Solusi Permanen di Build Ini:** Manager APK dibangun ulang dari commit upstream UAPI v4 (`ea51427ff700f73909e7e8c8717cc3241322ee1e`). Disassembly simbol JNI `Java_com_rifsxd_ksunext_Natives_getManagerUAPIVersion` di dalam `lib/arm64-v8a/libkernelsu.so` terverifikasi menghasilkan instruksi AArch64 `mov w0, #4; ret` (`0x52800080`, `0xd65f03c0`), sejajar 100% dengan kernel (`UAPI = 4`) dan `lib/arm64-v8a/libksud.so` (`UAPI = 4`).

---

## 2. Pembaruan UI/UX Manager APK (`Synthetica-2.0.apk`)

1. **Real GPU Blur iOS Liquid Glass (Light, Dark & AMOLED):**
   - Arsitektur `GraphicsLayer` dua lapis (*sibling* `wallpaperLayer` + `contentLayer`, bebas *cyclic layer recursion*) dengan blur GPU nyata (`BlurEffect` di Android 12+ / `RenderEffect`) pada kartu (`IosHeroCard`, `IosGroup`, `IosTile`, kartu `Module` & `SuperUser`), `GlassTopBar`, serta *floating* `GlassBottomBar` dengan indikator pil kaca geser (*sliding glass pill*).
   - `MaterialTheme.colorScheme.background = Color.Transparent` agar gradien bola cahaya hidup (`GlassBackground`) terlihat menembus seluruh halaman, sementara `ModalBottomSheet` memakai permukaan kaca kedap yang terbaca jelas.
2. **Tata Letak Menu Identik Manager 1.16 (Rebrand Penuh ke `Synthetica`):**
   - **Floating Bottom Bar 4-Tab:** `Home`, `Root apps` / `Aplikasi root`, `Modules` / `Modul`, `Settings` / `Pengaturan`.
   - **Beranda (`Home`):** Header `Synthetica` dengan emblem kaca, kartu hero status `Synthetica 2.0`, kisi pintasan 2×2 (`Modules`, `Root apps`, `Install kernel`, `Settings`), grup `Status` (`Kernel`, `Manager`, `Root access`, `Hiding / SuSFS`, + rincian `Metamodule`, `Zygisk`, `SELinux`, `Android`, `ABI` yang dapat dibuka), dan `Quick tools` (`Synthetica Boost`, `Metamodule`). Pengecekan update GitHub upstream (`v3.4.2`) dinonaktifkan.
   - **Pengaturan (`Settings`):** Grup kartu kaca iOS: (1) Kernel/Root (`Umount modules`, `SU Compat`, `Kernel umount`, `SU Log`, `ADB Root`, `SELinux Hide`, `AVC Spoof` — tanpa toggle SELinux permissive global), (2) Alat (`Synthetica Boost`, `Metamodule`, `SU Log`, `App Profile Template`, `Backup & Restore`), (3) Aplikasi (`Customization`, `Biometric App Lock`, `Developer`, `Export Log` → `Synthetica_bugreport_*.tar.gz`, `About`).
   - **Halaman `Synthetica Boost` & `About`:** Optimasi jaringan TCP/Wi-Fi (`synthetica-boost.sh`) & penguat gain audio `tinymix` (`synthetica-sound.sh`) dengan pembersihan otomatis skrip lama, serta halaman `About` berlapis kaca buram beridentitas `Synthetica 2.0`.
3. **Splash Screen & Ikon Peluncur 3D Liquid Glass Baru:**
   - **Splash Screen (`SyntheticaGlassSplash`):** Latar kaca hidup dengan pendaran berlapis, pedestal *squircle* kaca 3D berefek kilau diagonal (*specular sheen*) + emblem kristal `Synthetica` beranimasi pegas halus, tipografi `Synthetica` & kapsul `2.0 · LIQUID GLASS`.
   - **Launcher Icon (`build-kit/ci/branding/`):** Ikon adaptif (`foreground` + `background` + `monochrome` Android 13+) dan *legacy* di seluruh kepadatan (`mdpi` s/d `xxxhdpi`) bergaya 3D iOS Liquid Glass.

---

## 3. Hasil Akhir & Checksum SHA-256 (`release/`)

| Nama Berkas | Ukuran (Byte) | SHA-256 | Keterangan |
|---|---:|---|---|
| **`Synthetica-2.0.apk`** | `9161501` | `7bded761808c560fa5511acf32d3ce728adedce663002820815d00176526b567` | Manager APK UAPI v4 (`ea51427ff7`), `net.ember.labs`, label **Synthetica**, iOS Liquid Glass GPU Blur, menu 1.16, splash & ikon baru, v2+v3 signed (`0x565` / `fe833710...`) |
| **`Synthetica-2.0.zip`** | `21567245` | `b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c` | Paket flashable recovery AnyKernel3 (`4.14.357-openela-Synthetica-2.0` + `ksud` UAPI v4) — **tidak perlu di-flash ulang** bila sudah terpasang |
| **`Synthetica-2.0-LOG.zip`** | `861633` | `0832820bc4646a1069dd4b2ef96ce17a6cc5cc522080a9e668c730d644fd15c0` | Paket pengumpul log *read-only* untuk recovery (`<storage>/synthetica-logs/<waktu>/`) |
| **`BUILD-FULL.log`** | *(lihat `release/SHA256SUMS.txt`)* | *(lihat `release/SHA256SUMS.txt`)* | Log gabungan lengkap Langkah 1 (APK UAPI v4 + Liquid Glass) + Verifikasi Sertifikat + Langkah 2 (Kernel) + Langkah 3 (Packaging) |

---

## 4. Bukti Verifikasi Kriptografis & Keamanan Kunci

- **Skema Tanda Tangan APK:** APK Signature Scheme v2 (`true`) & v3 (`true`)
- **Sertifikat Penanda Tangan (`Signer #1`):**
  - DN: `C=ID, O=Synthetica, CN=Synthetica Manager`
  - Ukuran DER: **`1381` byte (`0x565`)**
  - SHA-256 Sertifikat: **`fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`** (identik 100% dengan `KSU_NEXT_MANAGER_HASH` di dalam kernel `Synthetica-2.0.zip`)
- **Verifikasi Biner Native di dalam APK:**
  - `lib/arm64-v8a/libkernelsu.so` (`13896` B, SHA-256 `a819a333955cce739f9bb14504736cd91be00ef2e5381963f8fe4975df8f38a8`): `getManagerUAPIVersion` → `mov w0, #4; ret` (**UAPI = 4**)
  - `lib/arm64-v8a/libksud.so` (`5518544` B, SHA-256 `c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427`): **UAPI = 4**
- **Keamanan Kunci Privat:** `secretkey/synthetica-2.0.p12` hanya diekstrak sementara di `/tmp` untuk penandatanganan lokal dan telah di-*shred* serta dihapus permanen (`0` kunci privat di repositori Git, CI, maupun artefak rilis).
