# Lanjutan audit kandidat 04, GMS, Leica dan AxSandbox — 3 November 2026

## Keputusan

**HOLD / JANGAN FLASH / JANGAN PUBLIKASIKAN.** [Kandidat SpatialFlow 04](https://github.com/dwp29/Syntenthica/releases/edit/432276369) tetap draft dan ZIP-nya belum ditandatangani. Belum ada verifikasi recovery, external vbmeta/AVB pada perangkat, boot, instalasi, fungsi audio atau hardware. Kandidat 03 dan sumber tidak ditimpa; tidak ada perangkat atau data pengguna yang disentuh.

Laporan ini memperbarui, bukan menghapus, [hasil signature sebelumnya](HASIL-SIGNATURE-LEICA-GOOGLE-AXSANDBOX-2026-11-03.md) dan [hasil build 04](BUILD-SPATIALFLOW-04-HOLD-2026-11-03.md). Kesimpulan di sini adalah hasil host yang terikat pada input dan run tertentu, bukan persetujuan untuk menggunakan ROM.

## Pembacaan langsung product kandidat 04

[Audit 41583357398](https://github.com/dwp29/Syntenthica/actions/runs/41583357398), check `125743577026`, merekonstruksi tiga part di runner, memverifikasi ZIP, membaca `super` dan dua extent logical `product` secara read-only, lalu membaca dua file ext4 tanpa mount. Hasil lengkap: `HASIL-PRODUCT-SPATIALFLOW-04-RUN-41583357398-2026-11-03.json`.

| Yang dibaca langsung dari 04 | SHA-256 | Pembandingan |
|---|---|---|
| ZIP kandidat, 4.748.586.175 byte | `7aa84e14e1b4e30aa0a70e222c8d9550b4d533c8016aa1f002d17fe460d96df8` | Tiga part dan digest kandidat dipin |
| `super`, 8.589.934.592 byte | `bc7b59d0824bddb63ffa2d1a49b7f1030b3363cbfe7caa7e6fa55ad1839e5f54` | CRC anggota ZIP dibaca hingga EOF |
| `product`, 3.925.241.856 byte | `e8504d1b387ac0dfeca063097ba88efe9b00a6874aad89a9d6443a3cfae50aad` | Dua extent diekstrak sesuai metadata |
| `product:/apex/com.google.android.gmssystem.prodvic.apex`, 155.066.368 byte | `fdf44ee609c5290e749f8cf1ed81b144155fe0530be90eca4c2a806ff51873fd` | Hash dan ukuran sama dengan APEX yang diaudit pada 03 |
| `product:/app/SpatialFlow/SpatialFlow.apk`, 45.521.038 byte | `a3c5349073f9819764f185022867a9d47c58347d9c34573423e6397f33f9233d` | Hash dan ukuran sama dengan APK rilis yang dipin |

Input dan status draft tetap tidak berubah pada akhir run. Artinya APEX GMS di product 04 memiliki ukuran dan SHA-256 yang sama dengan referensi 03; pemeriksaan signature di bagian berikut **dijalankan pada salinan dari 03**, dengan kaitan ke 04 melalui kecocokan ukuran dan hash itu, bukan melalui boot atau aktivasi di 04. Kehadiran SpatialFlow juga bukan bukti bahwa ia pemutar default atau audio berfungsi; patch intent/preferensi sebelumnya tetap prototipe terpisah dan tidak dikemas dalam APK 04.

## Signature GMS: konsistensi kriptografis, bukan trust perangkat

- [Audit APK GMS dalam APEX dari 03, run 41582635035](https://github.com/dwp29/Syntenthica/actions/runs/41582635035), check `125741363798`: satu APK `com.google.android.gms`, 227.669.823 byte, SHA-256 `05de4f30a39a0db182f50bca1adf82ed2a8c05c09463e1ccddbe9ae95b9301e3`. `apksigner` exit 0, v3 benar, satu sertifikat `5f2391277b1dbd489000467e4c2fa6af802430080457dce2f618992e9dfb5402`; kontrol positif/negatif lulus dan APK sementara dihapus.
- [Audit ulang APEX dari 03, run 41583865006](https://github.com/dwp29/Syntenthica/actions/runs/41583865006), check `125745273839`: signature outer v3 lulus dengan sertifikat `35ef2d4ae5166e5079a1b12cc8f8987786110844533a57785dc512684ab757a4`. Signature AVB dan hashtree payload lulus terhadap kunci yang **tertanam dalam APEX yang sama**, SHA-256 `c1224cd9cfc4d12e32f52500e678eef607ccaefc2319f44ff34177be98beddbd`. Hasil mentah dan kontrol ada pada JSON masing-masing run.

Field `payload_avb_structure.signature_or_hashtree_verified=false` pada hasil APEX merupakan pembacaan struktur **sebelum** tahap verifikasi. Hasil verifikasi kriptografi terpisah ada pada `payload_avb_verification.payload_signature_and_hashtree_verified_with_embedded_key=true`. Dua field ini tidak saling bertentangan.

Pemeriksaan tersebut **tidak** mengautentikasi penerbit sebagai Google, membuktikan sertifikat/kunci dipercaya perangkat, menguji external vbmeta, membuktikan aktivasi GMS atau fungsi Play Store. Kecocokan fingerprint yang diindeks pihak ketiga pada versi GMS lain juga bukan bukti asal resmi untuk file ini. Jangan menafsirkan sertifikat yang tidak cocok dengan daftar test key sebagai otomatis tepercaya.

## Leica: ditemukan sertifikat public AOSP testkey

[Probe terbaru 41583864961](https://github.com/dwp29/Syntenthica/actions/runs/41583864961), check `125744762339`, merekonstruksi prebuilt Leica dari dua Git blob yang dipin; dua reader setuju tentang package `com.android.camera` dan versi `Universal-5.0-Beta7.3`; seluruh 11.643 entri APK diperiksa CRC. APK 127.878.632 byte memiliki SHA-256 `54dc2f389b74a1799c6b238699fa4a8b5cca829d93f5064da3f55457900e1792`.

`apksigner` berhasil memverifikasi v3, tetapi sertifikatnya `a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc` **identik dengan sertifikat development AOSP `testkey` yang publik**. [Pembandingan referensi independen 41583865053](https://github.com/dwp29/Syntenthica/actions/runs/41583865053), check `125744710799`, mengambil hanya sertifikat X.509 publik dari commit sumber AOSP yang dipin dan membandingkan SHA-256 DER. Hasil gate untuk prebuilt tersebut `REJECT_PUBLIC_TESTKEY`. Tidak ada private key yang diminta, diambil atau dipakai.

Ini menyangkut **APK prebuilt yang direkonstruksi**, bukan bukti bahwa ROM dasar/perangkat memakai testkey. Blueprint upstream meminta platform signing pada build final; platform key final atau otoritas penandatangan belum diverifikasi. Signature yang valid tidak membuktikan penerbit, lisensi, kompatibilitas sensor/HAL atau keamanan. APK, 86 library native terkait dan hak distribusinya belum diverifikasi untuk integrasi; tidak ada yang dipasang ke 04.

Preflight builder SpatialFlow kini menolak sembilan fingerprint sertifikat development AOSP publik yang dikurasi (`testkey`, `platform`, `shared`, `media`, `networkstack`, `bluetooth`, `nfc`, `sdk_sandbox`, `cts_uicc_2021`); probe Leica melaporkan gate penolakan bila cocok. Sembilan sertifikat publik diverifikasi ulang pada run referensi di atas. **Daftar ini tidak lengkap dan bukan allowlist**: sertifikat yang tidak cocok tetap `NOT_ASSESSED`, bukan terbukti tepercaya. Guard ini tidak mengubah 04 yang sudah dibuat dan bukan audit seluruh sistem penandatanganan ROM.

[AOSP menjelaskan risiko test key publik untuk rilis](https://source.android.com/docs/core/ota/sign_builds); [sertifikat referensi dan README](https://github.com/aosp-mirror/platform_build/tree/3d9c9aacdb6ca0b745b3048dad88d0db4680d50e/target/product/security) dipin, tetapi tanda tangan commit sumber itu sendiri tidak diverifikasi. Nama `platform` pada sertifikat development AOSP tidak mengidentifikasikan platform key perangkat pengguna.

## AxSandbox tetap karantina prototipe

[Run 41582635095](https://github.com/dwp29/Syntenthica/actions/runs/41582635095), check `125740781739`, mereproduksi patch fail-closed pada file sumber yang dipin. Import, restore, delete dan migrasi legacy sengaja dinonaktifkan; perubahan ini **membuat vault tidak fungsional**, bukan memperbaiki seluruh vault. Output sumber SHA-256 `2b1108eaa8df623a598e081b4fa1326affe480d6ac0adc62b1ef2a36e6b896d6`; patch SHA-256 `7e9b9d2443dfa65180625ef3c6c640e3e2ef048788c4718a84db5a5edd88a66a`.

Prototipe belum di-compile, di-sign, dikemas, diinstal atau diuji pada perangkat. Provider, cache/media bridge, autentikasi, kriptografi dan concurrency belum diaudit menyeluruh. Pengembangan fungsional membutuhkan desain transaksi, pengujian gagal-I/O dan crash menggunakan data sintetis, serta pemeriksaan dependensi framework/platform signing.

## Pengujian dan gate tersisa

Regresi lokal pada commit kode `6f24ca9`: **481 tes dijalankan: 477 lulus dan 4 skipped**; ini adalah tes host, bukan tes Android. JSON hasil run yang dirujuk disimpan di direktori laporan ini. Audit VINTF/SELinux/policy dan ABI, kecocokan partisi/vendor, recovery dengan verifikasi signature utuh, trust external AVB/vbmeta, hak distribusi, boot dan pengujian hardware/fungsi pada perangkat yang sesuai tetap blocker. Jangan melemahkan pemeriksaan signature untuk melewati blocker.
