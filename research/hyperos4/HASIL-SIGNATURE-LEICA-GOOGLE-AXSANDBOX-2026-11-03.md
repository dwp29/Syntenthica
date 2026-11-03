# Hasil pemeriksaan signature dan karantina sumber — 3 November 2026

## Keputusan

**HOLD / JANGAN FLASH / JANGAN PUBLIKASIKAN.** [Kandidat SpatialFlow 04](https://github.com/dwp29/Syntenthica/releases/edit/432276369) masih unsigned dan belum diuji di recovery, AVB perangkat, saat boot, pada perangkat, maupun audio. Pemeriksaan di bawah bersifat statis pada host; bukan izin memakai hasil pada perangkat pengguna. Kandidat 03 dan sumber tidak ditimpa; perangkat dan data pengguna tidak disentuh.

## APEX Google pada kandidat 03

[Run 41581542764](https://github.com/dwp29/Syntenthica/actions/runs/41581542764), check `125737850762`, dengan parser yang sudah diperbaiki: dua pemeriksaan host **berhasil** pada `product:/apex/com.google.android.gmssystem.prodvic.apex` (SHA-256 `fdf44ee609c5290e749f8cf1ed81b144155fe0530be90eca4c2a806ff51873fd`).

1. `apksigner` memverifikasi signature outer v3 dan melaporkan satu sertifikat SHA-256 `35ef2d4ae5166e5079a1b12cc8f8987786110844533a57785dc512684ab757a4`.
2. Verifikasi AVB signature dan hashtree payload terhadap kunci yang **tertanam di APEX yang sama** berhasil. SHA-256 kunci tersebut `c1224cd9cfc4d12e32f52500e678eef607ccaefc2319f44ff34177be98beddbd`. Kontrol AVB sintetis valid lulus; payload rusak, signature rusak dan payload unsigned ditolak. Field struktur yang menyatakan signature belum diverifikasi adalah observasi header awal; verifikasi kriptografis ada pada field `payload_avb_verification` terpisah.

Keduanya membuktikan **self-consistency**, bukan identitas Google, rantai kepercayaan perangkat, validitas external vbmeta, aktivasi APEX atau boot. Signature APK GMS di dalam APEX belum diperiksa di run ini. Hasil mentah: `HASIL-SIGNATURE-APEX-GOOGLE-RUN-41581542764-2026-11-03.json`. Run sebelumnya `41580902002` inkonklusif pada outer karena parser tidak mengenali format modern `V3.0 Signer:`; itu **bukan bukti signature rusak**. Parser kini memiliki kontrol format lama, modern, source-stamp dan ambiguitas.

## Kandidat sumber kamera Leica

[Run 41581542726](https://github.com/dwp29/Syntenthica/actions/runs/41581542726), check `125737382559`, merekonstruksi APK dari dua Git blob pin dan memeriksa hash, CRC seluruh 11.643 entri serta manifest dengan dua reader. APK SHA-256 `54dc2f389b74a1799c6b238699fa4a8b5cca829d93f5064da3f55457900e1792`, package `com.android.camera`, versi `Universal-5.0-Beta7.3`, min SDK 29, target 33. `apksigner` exit 0 melaporkan v3 dan satu sertifikat SHA-256 `a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc`. Rincian ada di `HASIL-KAMERA-LEICA-RUN-41581542726-2026-11-03.json`.

Ini tidak membuktikan bahwa sertifikat adalah platform key perangkat atau bahwa APK dapat dipasang dan berfungsi. Sumber meminta platform signing, privileged apps dan override kamera; lisensi/hak distribusi, 86 pustaka native terpisah, HAL, sensor dan kesesuaian HyperOS belum diverifikasi. APK dan pustaka belum diintegrasikan, dipasang atau diterbitkan.

## AxSandbox: karantina sumber, bukan vault fungsional

Pada [FileVaultManager.kt sumber pin](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/src/com/android/axion/sandbox/io/FileVaultManager.kt), pemeriksaan statis mengidentifikasi beberapa risiko tambahan:

- Import dapat menghapus asli setelah menulis tanpa bukti baca-kembali dan durabilitas; migrasi menghapus metadata pada exception.
- Restore membuka target dengan `FileOutputStream`, yang dapat menimpa file yang sudah ada, dan pada exception memanggil `targetFile.delete()`; implementasi juga menghapus vault setelah copy tanpa bukti durabilitas. Ini risiko statis, bukan klaim kerusakan yang sudah terjadi.
- Daftar vault menghapus metadata jika file bin tidak ditemukan, tanpa membuktikan bahwa absensi itu permanen.

Sebagai **prototipe sumber saja**, `prepare_axsandbox_vault_quarantine.py` menerima hanya file sumber SHA-256 `1883370ab8b947990c65f06b6d317990d068dc521e629e9e452ec89931d43ab5` dan menghasilkan patch `synthetica-project/patches/axsandbox/FileVaultManager-QUARANTINE-ONLY.patch`. Prototipe sengaja menonaktifkan import, restore, delete, dan migrasi legacy, serta mencegah penghapusan otomatis metadata ketika file hilang. **Vault tidak fungsional.** [Run 41581834637](https://github.com/dwp29/Syntenthica/actions/runs/41581834637), check `125738245388`, memverifikasi pin, reproduksi patch dan kontrol host; output sumber SHA-256 `2b1108eaa8df623a598e081b4fa1326affe480d6ac0adc62b1ef2a36e6b896d6`.

Karantina **bukan perbaikan penuh**, tidak di-compile Android, di-sign, dikemas, diinstal atau diuji perangkat. Cache/MediaStore bridge, provider lain, autentikasi, kriptografi dan race belum diaudit. UI dapat melaporkan kegagalan secara tidak tepat; jangan pakai prototipe ini sebagai ROM atau untuk data pengguna. Implementasi fungsional membutuhkan desain transaksi dan uji gagal-I/O, keystore, ruang habis, crash/power loss, restore non-overwrite, rollback dan keamanan menggunakan data sintetis. Dependensi framework/UID, platform signing, permission, kompatibilitas, dan lisensi tetap blocker.

## Pengujian dan langkah lanjut

Regresi host: **455 tes lulus, 4 skipped**. Ini bukan tes Android/device. Hasil kandidat 04 tetap tidak berubah. Sebelum keputusan perangkat, bukti yang masih diperlukan meliputi VINTF/policy dan ABI kompatibel, signature serta AVB eksternal yang benar-benar dipercaya, recovery dan instalasi dengan verifikasi utuh, boot serta pengujian fungsi pada perangkat yang sesuai dan hanya dengan backup/izin yang jelas.
