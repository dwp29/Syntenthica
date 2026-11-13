# ARSIP LENGKAP PROJECT KERNEL & MANAGER
Disusun 13 November 2026. Semua berkas project dari awal sampai akhir dikumpulkan
di folder ini. Indeks ini menyebut **folder**, bukan berkas satu per satu, karena
tiap folder sudah bernomor dan berkas di dalamnya sudah diberi nama detail.

## 01 — KERNEL SEMUA VERSI
| Sub-folder | Isi |
|---|---|
| `01-KERNEL-Synthetica-1.0-sampai-4.0-Arsip-Versi-Lama` | Synthetica 2.0 (Neutron/MGLRU TEST, HASIL-BUILD, LiquidGlass), 2.1 Cyberbrutal, 3.0 rc1/Neon, 4.0 arsip riset |
| `02-KERNEL-DAN-BUKTI-BUILD-Synthetica-2.0-sampai-4.0` | Synthetica 3.0/3.1/3.2/3.2-r1/4.0 (ZIP + sha256), DevKit + signed modules, Synthetica-3.2.zip |
| `03-KERNEL-Rollercoaster-Arsip-26OKT2026-dan-Roll-3.3` | ROLLERCOASTER-ARSIP PART1 (dokumen+kode) & PART2 (kernel), Rollercoaster-Chronicle/Critical 1.2.0, Roll.3.3 |
| `04-KERNEL-Project-HOS-4.0-Synthetica-2.0` | synthetica-2.0-kernel-hos4.zip + panduan pasang |
| `05-SOURCE-KIT-Synthetica-3.0-Pengembangan-PRIVAT` | Source kit 3.0 dipecah .001–.004 (~368 MB) |

## 02 — APK MANAGER SEMUA VERSI
| Sub-folder | Isi |
|---|---|
| `01-APK-Manager-2.0-sampai-3.0-Rilis-Siap-Pakai` | Synthetica-2.0.apk, 2.1/2.1.2 Cyberbrutal, 3.0 Installer 2.0 |
| `02-APK-Manager-2.x-sampai-5.0-Arsip` | Manager 3.0/3.1.0 Neon, 4.0.0 Pixel, 5.0 & 5.0.1 MultiTema (+sha256) |
| `03-APK-Manager-6.0.0-Universal-SIGNED-R2` | Manager 6.0.0 Universal SIGNED R2 + sha256 |
| `04-APK-Manager-6.1-Themes-SIGNED` | Manager 6.1 Themes SIGNED |
| `05-APK-PREVIEW-Neon-3.0-BUKAN-MANAGER.apk` | preview tampilan, bukan Manager |

## 03 — SOURCE KIT DAN BUILD
| Berkas | Isi |
|---|---|
| `2026-11-13_SOURCE-KIT-Synthetica-Rollercoaster-UFO-46-berkas.zip` | builder Rollercoaster + 7 profil config (termasuk `synthetica.config`), 8 patch inti Synthetica (MGLRU 116 KB, UCLAMP 58 KB, KSU seccomp, fd pasca-exec), resep build 3.2 final + pemaket, catatan MD 3.0–4.0 |

## 04 — DOKUMEN MD DAN CATATAN
| Sub-folder | Isi |
|---|---|
| `01-DOKUMEN-MD-Synthetica-dan-Kernel` | SYNTHETICA-3.2-RELEASE-AND-DEV-GUIDE.md dan dokumen proyek lain |
| `00-BACA-DULU-SYNTHETICA-PANDUAN-AWAL.txt` | panduan awal |

## 05 — KEY SIGNING  (JANGAN DISEBAR)
| Berkas | Isi |
|---|---|
| `2026-11-11_KEY-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.p12` | keystore rilis Pure Manager (PKCS12, 4380 B) |
| `2026-11-11_CERT-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.pem` | sertifikat publik |
| `2026-11-11_DOK-Pure-Manager-KEY-SIGNING-password-alias-fingerprint.md` | sandi, alias, fingerprint |
| `2026-11-11_KEY-Pure-Manager-PM_KEYSTORE_B64-siap-tempel-di-GitHub.txt` | base64 untuk variabel repo |
| `2026-11-11_KEY-Synthetica-Manager-6.1-Themes-keystore.p12` | keystore Manager 6.1 Themes |

Sertifikat Pure Manager release key:
`A2:F9:42:45:2E:EC:1C:D8:76:3E:6C:F3:3B:99:37:C1:A9:9B:38:49:C6:27:73:A7:3B:F4:44:77:67:43:F2:D8`
**Peringatan:** keystore ini juga tersalin di repo GitHub publik `dwp29/Synthentica`
folder `ci-stage/` (dipakai sekali untuk menandatangani APK 0.10.0). Anggap kunci
ini hangus untuk rilis publik; ganti sebelum aplikasi dibagikan ke selain owner.

## 06 — ALAT DIAGNOSTIK
| Sub-folder | Isi |
|---|---|
| `01-ALAT-Synthetica-Log-Collector-dan-Boot-Audit` | Log Collector 1.0, ADB Log PC test |
| `02-Kernel-dan-Diagnostik-Lama` | Boot Audit 1.0 + diagnostik 2.0 |

## 07 — LOG DAN BUKTI KOMPILASI
| Berkas | Isi |
|---|---|
| `2026-11-12_BOOTLOG-joyeuse-OneUI8-bootloop-Recovery-Log.zip` | log recovery bootloop joyeuse + analisis |
| `2026-11-10_CI-ARTEFAK-Manager-6.0-run-42750759962-unsigned.zip` | artefak CI unsigned |

## 09 — TAMPILAN DAN TEMA MANAGER
`09-TAMPILAN-DAN-TEMA-MANAGER`: riset UI/UX, deck desain lengkap (PDF),
visualisasi semua halaman, mockup matriks mode & tema layout, prototipe tema (HTML),
layar asli Manager 5.0.1, arsitektur modul AI/tema, riset fitur tema-layout.

## 08 — PURE MANAGER (APK DAN LOG)
APK 0.10.0 FULL & MINIMAL bertanda **kunci rilis** (`RELEASEKEY`), LOG-001…016,
laporan akhir, riset desain, dan salinan folder key signing.

## Hasil pemeriksaan akhir (13 Nov 2026)
- Akar Drive hanya berisi **satu** folder project: `SYNTHETICA-KERNEL-ARSIP-LENGKAP-2026-11-13`.
- Folder lama `SYNTHETICA` sudah kosong lalu dipindah ke Trash (bukan dihapus permanen).
- Tidak ada lagi berkas project yang tersisa di akar Drive.
- 83 berkas project yang sebelumnya tersebar di 12 lokasi kini berada dalam satu induk.

## Status pekerjaan UFO-0.1 (belum selesai)
- Identitas sudah ditetapkan: `SP_BUILD_NAME=UFO`, `SP_BUILD_KVER=0.1` → uname `4.14.370-UFO-0.1`.
- **Penghambat:** source `4.14.370` tidak tersedia publik. Yang bisa dijangkau hanya
  `Saamitk/kernel_xiaomi_sm6250-switchoff` (branch `a`) dan
  `Saamitk/kernel_xiaomi_SM6250_SKYNET`, keduanya **4.14.357**.
- Yang sudah terbukti (CI run `43427832932`): di pohon 4.14.357, patch
  `0001-mglru-4.14.patch` dan `0002-uclamp-walt-stune.patch` menempel **bersih**.
- Belum diuji: patch 0003–0008 (uji berhenti di patch ketiga karena kesalahan skrip probe).
