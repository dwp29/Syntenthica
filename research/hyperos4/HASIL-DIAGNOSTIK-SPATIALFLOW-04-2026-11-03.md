# Diagnostik build SpatialFlow 04 — 3 November 2026

**HOLD / JANGAN FLASH.** Run [41574640596](https://github.com/dwp29/Syntenthica/actions/runs/41574640596) pada `6d19343` berhenti sebelum mengubah image, membuat ZIP 04, atau membuat draft. Kandidat 03 dan sumbernya tetap terpisah. Kegagalan berasal dari pemeriksa nama paket `Shell.apk`, bukan bukti ROM rusak ataupun bukti ROM aman.

## Sebab yang terverifikasi

Probe baca-saja [41576200655](https://github.com/dwp29/Syntenthica/actions/runs/41576200655) pada `1046720` merekonstruksi kandidat 03 terpin, memverifikasi seluruh `super.img` dan extent system, lalu memeriksa satu APK tanpa mengunggahnya. APK `system:/system/priv-app/Shell/Shell.apk` berukuran 370.060 byte, SHA-256 `174d195cb1c6a55021f088dbad787c173dca92273cb14520589d3439e70fa26a`. Manifest-nya terverifikasi CRC ZIP.

- `aapt dump badging` mengeluarkan nama `com.android.shell`, kemudian exit 1 karena referensi `android:label` platform Android 17 tidak dapat diresolusikan pada host.
- `aapt dump xmltree` dan `aapt2 dump xmltree` masing-masing exit 0 dan membaca atribut package root yang sama, `com.android.shell`. `aapt2 dump badging` juga exit 0.
- Parser tabrakan paket kini tetap gagal tertutup jika kedua pembaca XML gagal/berbeda, nama ambigu, manifest duplikat/CRC rusak, tool crash/timeout, atau nama target sudah ada. Pembaca yang sama tidak dapat dihitung sebagai dua pembaca; hash tool dicatat. Ini hanya pemeriksaan nama paket pada root yang dicakup, bukan bukti APK berfungsi. APEX, target symlink, ODM/vendor, paket dinamis, dan runtime tidak tercakup.
- Hasil lengkap terstruktur: `HASIL-DIAGNOSTIK-SPATIALFLOW-04-2026-11-03.json`. Probe host dan kesamaan nama tidak membuktikan instalasi, AVB, recovery, boot, atau fungsi perangkat.

## Temuan tambahan SpatialFlow sebagai pemutar default

Pada sumber upstream tag v1.8.2 commit `8a40906d074ab95b2bfa32481bfae140dfdfcbed`, filter `android.intent.action.MUSIC_PLAYER` berada pada `.ui.ExternalPlayerActivity`; kode activity itu melakukan `finish()` apabila diluncurkan tanpa URI. Sumber: [manifest](https://github.com/MythicalSHUB/SpatialFlow/blob/8a40906d074ab95b2bfa32481bfae140dfdfcbed/app/src/main/AndroidManifest.xml) dan [activity](https://github.com/MythicalSHUB/SpatialFlow/blob/8a40906d074ab95b2bfa32481bfae140dfdfcbed/app/src/main/java/com/codetrio/spatialflow/ui/ExternalPlayerActivity.kt). Kesesuaian source dengan APK rilis belum diautentikasi, sehingga temuan ini **belum membuktikan** perilaku APK pada perangkat.

`synthetica-project/prepare_spatialflow_music_intent.py` menyiapkan **patch sumber saja**, dengan hash manifest sumber terkunci, untuk memindahkan filter tersebut ke `.MainActivity` tanpa mengubah filter audio eksternal atau simpul manifest lain. Belum dikompilasi, ditandatangani, diinstal, diatur sebagai default, atau diuji; APK rilis upstream tidak diubah. Preferensi Android/HyperOS yang sebenarnya dan pilihan pengguna yang sudah ada tetap memerlukan pengujian dan tidak boleh diklaim selesai.

## Batas yang tetap berlaku

Ekspansi product memerlukan pembuktian layout perangkat, recovery dan AVB. ROM masih unsigned; VINTF/policy belum terbukti kompatibel; hak distribusi ROM dan dependensi SpatialFlow belum tuntas. Tidak ada flash, wipe, perubahan recovery, atau pelemahan verifikasi keamanan yang dilakukan.
