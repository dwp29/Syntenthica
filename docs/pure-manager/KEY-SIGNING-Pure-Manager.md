# KEY SIGNING — Pure Manager

**Dibuat:** 2026-11-11
**Berlaku untuk:** semua APK Pure Manager (`net.pure.manager`) mulai versi 0.5.0
**Jangan pernah dihapus, diganti nama, atau diunggah ulang sebagai berkas baru.**

---

## 1. Berkas di folder ini

| Berkas | Isi |
|---|---|
| `2026-11-11_KEY-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.p12` | keystore PKCS#12, berisi kunci privat + sertifikat |
| `2026-11-11_CERT-Pure-Manager-Signing-Release-RSA4096-A2F942452EEC.pem` | sertifikat publik saja (aman dibagikan) |
| dokumen ini | kata sandi dan cara memakainya |

## 2. Kata sandi dan alias

```
storePassword : PureManager2026!
keyPassword   : PureManager2026!
keyAlias      : pure-manager-release
format        : PKCS#12 (PBES2 / AES-256, MAC SHA-256)
```

Perintah memeriksa tanpa mengekstrak apa pun:

```
openssl pkcs12 -info -in <BERKAS>.p12 -passin "pass:PureManager2026!" -noout
```

Kata sandi ini **bukan** rahasia yang kuat — berkasnya ada di Drive Anda, bukan di
internet. Yang penting: jangan unggah keystore ini ke repo (repo-nya publik) dan
jangan kirim kata sandi di tempat umum.

## 3. Identitas kunci

| | |
|---|---|
| Jenis | RSA **4096** bit |
| Algoritma tanda tangan | SHA-256 with RSA |
| Subjek | `CN = Pure Manager, O = Pure Manager, C = ID` |
| Berlaku | 11 Nov 2026 — 3 Nov 2056 |
| SHA-256 sidik jari | `A2:F9:42:45:2E:EC:1C:D8:76:3E:6C:F3:3B:99:37:C1:A9:9B:38:49:C6:27:73:A7:3B:F4:44:77:67:43:F2:D8` |
| SHA-1 sidik jari | `CC:64:B0:74:FE:62:14:E9:10:13:E4:47:50:0C:4D:23:88:F4:73:64` |
| SHA-256 berkas `.p12` | `ba9be8a2879f8f2961872d4a4f7963e81643d8fab254105c44ef60a4fbe9b3f3` |
| SHA-256 berkas `.pem` | `8915ec91b9e857657c16f02978183764f4a7511434c5e419cef784fb6dc2ff53` |

Sidik jari `A2:F9:42:…:F2:D8` inilah yang nanti muncul di `apksigner verify`
pada setiap APK yang ditandatangani kunci ini. Kalau berbeda, yang dipasang bukan
build dari kunci ini.

## 4. Kenapa ini penting

Semua APK sampai 0.4.0 ditandatangani dengan kunci debug yang **dibuat baru di
setiap runner**. Akibatnya:

- APK tidak bisa diperbarui di atas versi lama tanpa menghapus aplikasi dulu.
- Membuka kunci kunci itu di masa depan tidak mungkin — tidak ada yang menyimpannya.
- Modul bertanda tangan (tahap 4) tidak akan pernah bisa memverifikasi aplikasi
  induknya, karena induknya berganti kunci setiap build.

Kunci ini menutup ketiganya.

## 5. Cara memakai di build

`pure-manager/app/build.gradle.kts` membaca empat variabel lingkungan:

```
PM_KEYSTORE_PATH      : jalur ke berkas .p12
PM_KEYSTORE_PASSWORD  : PureManager2026!
PM_KEY_ALIAS          : pure-manager-release
PM_KEY_PASSWORD       : (kosongkan; memakai PM_KEYSTORE_PASSWORD)
```

Kalau keempatnya kosong, build tetap jalan dan menghasilkan APK **DEBUGKEY** —
nama berkasnya menyebut itu, jadi tidak ada yang tertukar.

Workflow CI mencoba mengambil kunci lebih dulu. Dua jalur yang tersedia:

1. **Variabel repo** `PM_KEYSTORE_FILE_ID` (file id Drive) + `PM_KEYSTORE_PASSWORD`.
   Hanya bekerja kalau runner punya akses Google; dengan token GitHub tidak.
2. **Variabel repo** `PM_KEYSTORE_B64` (keystore base64) + `PM_KEYSTORE_PASSWORD`.
   Ini yang selalu bekerja: tidak butuh akses Drive, hanya satu variabel teks.

Membuat isi `PM_KEYSTORE_B64`:

```
base64 -w0 <BERKAS>.p12
```

Menaruhnya di GitHub: **Settings → Secrets and variables → Actions → Variables →
New repository variable**. Nama: `PM_KEYSTORE_B64`. Isi: hasil perintah di atas.

## 6. Kalau kunci ini hilang

Tidak ada cara memulihkannya. Yang terjadi: APK berikutnya memakai kunci baru, dan
pengguna harus menghapus aplikasi lalu memasang ulang. Karena itu:

- Salinan cadangan: simpan satu lagi di luar Drive (flashdisk, atau akun lain).
- Jangan pernah menjalankan `keytool -genkeypair` untuk menggantinya.

## 7. Berkas penting lain

| Berkas | Di mana |
|---|---|
| APK tiap versi | folder `02-BUILD-APK` |
| Log tiap build | folder `04-HOLD-BAHASAN-AI-DITAHAN` |
| Sumber kode | `https://github.com/dwp29/Synthentica`, branch `arena/96cbd65a-synthentica` |
| APK publik terakhir | branch `build-output` di repo yang sama |

## 8. Versi siap tempel

Folder yang sama berisi
`2026-11-11_KEY-Pure-Manager-PM_KEYSTORE_B64-siap-tempel-di-GitHub.txt`:
isi `.p12` dalam base64, sudah dibungkus petunjuk singkat. Berkas itu **berisi
kunci privat** — perlakukan sama seperti `.p12`.

## 9. Langkah yang masih menunggu Anda

Saya tidak punya izin menulis variabel/secrets di GitHub (token di sandbox ini
ditolak, HTTP 403), jadi dua variabel ini harus dipasang sekali secara manual:

**https://github.com/dwp29/Synthentica/settings/variables/actions**

| Nama | Nilai |
|---|---|
| `PM_KEYSTORE_B64` | seluruh isi berkas base64 di atas |
| `PM_KEYSTORE_PASSWORD` | `PureManager2026!` |

Setelah itu, build berikutnya menghasilkan
`PureManager-<versi>-RELEASEKEY.apk` dan mencetak sidik jari penanda tangan di
notice build, sehingga bisa dicocokkan dengan `A2:F9:42:45:…:F2:D8`.

Sampai dua variabel itu ada, build tetap jalan dan menghasilkan `DEBUGKEY`. Itu
disengaja: APK yang bisa dipasang lebih berguna daripada build merah.
