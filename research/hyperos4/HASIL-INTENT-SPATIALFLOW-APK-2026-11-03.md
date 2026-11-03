# SpatialFlow: audit intent APK rilis dan rancangan default — 3 November 2026

**Status: HOLD; bukan perubahan ROM atau bukti fungsi perangkat.** Kandidat 04 masih memuat APK rilis yang tidak dimodifikasi dan belum menjadikan SpatialFlow pemutar default.

## Yang benar-benar diperiksa

[Run 41579580603](https://github.com/dwp29/Syntenthica/actions/runs/41579580603), commit `7e374c3660b27cb93e55fe9475624bb039be497b`, men-download ulang APK arm64 v1.8.2 yang dipatok SHA-256 `a3c5349073f9819764f185022867a9d47c58347d9c34573423e6397f33f9233d`. Dua pembaca manifest, `aapt` dan `aapt2`, sepakat: **filter `android.intent.action.MUSIC_PLAYER` / `DEFAULT` tanpa data menunjuk `com.codetrio.spatialflow.ui.ExternalPlayerActivity` yang diekspor**. Manifest APK berukuran 27.016 byte, SHA-256 `b7f1292d815583b696219f827fa25a2b457f5612ca0c6ce96f7ab469bd0b206f`. Hasil mesin: `HASIL-INTENT-SPATIALFLOW-RUN-41579580603-2026-11-03.json`.

Ini menguatkan kesesuaian **arah filter manifest** dengan tag sumber; tidak membuktikan bahwa kode binary sama dengan sumber. Sumber `ExternalPlayerActivity` yang ditinjau sebelumnya menutup bila tidak menerima URI, tetapi apakah binary rilis berperilaku sama memerlukan pengujian. Panggilan audio lain atau `ACTION_VIEW` tidak otomatis diwakili oleh `MUSIC_PLAYER`.

Dua run awal `41579392118` dan `41579445296` serta run diagnostik `41579513403` berakhir **incomplete / neutral** karena parser awal belum menormalisasi namespace URL pada output `aapt2`. Format tersebut diperbaiki, ditambah tes kontrol dan dua pembaca barulah sepakat pada run sukses. Tidak ada ketidaksepakatan itu yang diabaikan.

## Persiapan sumber untuk kandidat masa depan

- `prepare_spatialflow_music_intent.py` memindahkan filter tersebut ke `MainActivity` pada **manifest sumber**, bukan APK rilis. Input dan output dipatok dan tidak ada node lain yang diubah; output SHA-256 `7b550c685db1106722cb9224619454910c46baa2caef1424a6db75fd7374b8c7`.
- `prepare_spatialflow_preference.py` sekarang menyiapkan **prototipe** preferensi `MUSIC_PLAYER` saja, hanya bila manifest input sesuai hasil patch dan filter tunggal berada pada `MainActivity` yang diekspor. Output SHA-256 `691406616a72b6acebe22fcf48353f23bf7b895511823126c17347d0d9a3c674`. Prototipe tidak dikemas atau diterapkan; jangan gunakan dengan APK 04, karena APK itu masih menunjuk activity yang berbeda.
- Acuan desain terbatas: [AOSP Android 15 `Settings.java` pada commit `4e43ad12`](https://github.com/aosp-mirror/platform_frameworks_base/blob/4e43ad12e1b211f15152e9c5b16b0fe88e6b93f3/services/core/java/com/android/server/pm/Settings.java) membaca `etc/preferred-apps` saat `createNewUser`, memeriksa resolver dan aplikasi sistem; [PreferredComponent](https://github.com/aosp-mirror/platform_frameworks_base/blob/4e43ad12e1b211f15152e9c5b16b0fe88e6b93f3/services/core/java/com/android/server/pm/PreferredComponent.java) dan [IntentFilter](https://github.com/aosp-mirror/platform_frameworks_base/blob/4e43ad12e1b211f15152e9c5b16b0fe88e6b93f3/core/java/android/content/IntentFilter.java) menggambarkan bentuk XML. Ini **bukan** bukti implementasi Xiaomi Android 17 sama, tidak menjamin preferensi berlaku untuk pengguna yang sudah ada, dan tidak mencakup semua resolusi audio.

## Gate

Sebelum konfigurasi dapat dipertimbangkan: bangun dan verifikasi APK sumber yang dipatch, tangani lisensi/source-to-binary dan penandatanganan/update, buktikan kompatibilitas package manager versi ROM, resolusi first boot dan pengguna lama, serta jalankan uji playback nyata. Jangan menghapus app bawaan atau mengubah data pengguna untuk memaksakan preferensi. Kandidat tetap **JANGAN FLASH / JANGAN PUBLIKASIKAN** sampai blocker recovery, AVB, boot dan lisensi ditangani.
