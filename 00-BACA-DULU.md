# Synthetica 2.0 — PAKET SOURCE LENGKAP (build di tempat lain)

Semua yang dibutuhkan untuk membangun **Synthetica 2.0** sendiri, dalam satu paket:
source kernel utuh, source manager, tema glass, builder, installer, **dan keystore
tanda tangan** — supaya APK dan kernel yang kamu hasilkan pasti cocok (tidak "no root").

Urutan build WAJIB: **1) APK dulu, 2) kernel kemudian** (kernel menanam sertifikat APK).

## Isi

| Folder/berkas | Isi |
|---|---|
| `kernel-tree/` | Source kernel UTUH `Saamitk/kernel_xiaomi_sm6250-switchoff` @ `c1e6f795` (basis 1.16 terbukti) |
| `manager-source/` | Source KernelSU-Next @ `31946acd` (yang ditema ulang) |
| `build-kit/ci/ksun-overlay/` | Tema **glassmorphism iOS** (Color/Theme/Type/Shapes/Glass.kt) |
| `build-kit/ci/branding/` | Ikon kaca baru + splash |
| `build-kit/ci/rollercoaster/` | Builder asli + profil (`chronicle`, **`synthetica`** = daily 2.0) + patch + `ksud` |
| `build-kit/ci/release/` | Installer AnyKernel3 (Inggris ringkas, Bismillah/Alhamdulillah, install log, tanpa backup boot) |
| `build-kit/scripts/` | `build_manager_source.py`, `build_chronicle_base.py`, `package_release.py`, dll |
| `build-kit/workflows/build-2.0.yml` | Workflow GitHub (kalau nanti mau build di CI lagi) |
| `secretkey/` | **Keystore `synthetica-2.0.p12` + sertifikat + `MANAGER-IDENTITY.json`** — simpan sendiri, jangan sebar |
| `reference-1.16/` | `STATUS.json` + `generated.config.txt` build 1.16 yang terbukti (pembanding) |
| `BUILD-SEMUA.sh` | Satu perintah: APK → kernel → zip flashable |
| `BUILD-HOWTO.md` | Penjelasan langkah + kebutuhan mesin |

## Identitas pasangan (sudah dikunci di paket ini)

- Paket APK: `net.ember.labs`, nama aplikasi: **Synthetica**
- Sertifikat: 1381 byte (`0x565`), sha256 `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`
- `uname`: `4.14.357-openela-Synthetica-2.0`
- Hasil flash: `Synthetica-2.0.zip` — APK: `Synthetica-2.0.apk`

## Yang TIDAK ada di paket (harus disiapkan di mesin build)

- **Android SDK** (platform 36, build-tools 36.1.0, NDK 29, cmake) + **JDK 21** — untuk APK.
  Unduh dari Google (di sandbox Arena host itu diblokir, makanya paket ini dibuat).
- **clang/LLVM 18 + gcc-aarch64** — untuk kernel. Host Ubuntu 24.04, RAM ≥ 8 GB, disk ± 20 GB.
- Gradle & dependensi Maven akan diunduh otomatis saat build APK pertama.

## Status kejujuran

Kode ini sama persis dengan commit `f55a104` di repo. Di GitHub, build-nya **belum pernah
jalan** (runner terkunci billing akun), jadi statusnya tetap `COMPILED_ONLY_UNVERIFIED`
sampai ada yang build + flash + boot. Paket installer sudah diuji lokal (CRC, isi zip,
teks installer). Zip keluaran builder kernel TIDAK boleh di-flash; yang di-flash hanya
`Synthetica-2.0.zip` hasil `package_release.py`.
