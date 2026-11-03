# Kandidat 04 SpatialFlow — hasil host, 3 November 2026

**HOLD / JANGAN FLASH / JANGAN PUBLIKASIKAN.** Kandidat terpisah sudah dibuat dan diverifikasi pada host, tetapi **belum ditandatangani, belum diuji recovery/AVB/boot, dan tidak disetujui untuk flash**. Tidak ada perangkat, recovery atau data pengguna yang disentuh.

## Identitas dan penyimpanan

- [Run build dan transfer 41576967077](https://github.com/dwp29/Syntenthica/actions/runs/41576967077), resep `69e1972941cba9da90a939af8029da9e03ab2de2`, status `HOST_VERIFIED_DEVICE_UNTESTED_HOLD_DO_NOT_FLASH`.
- Basis: kandidat 03 yang terverifikasi, diturunkan dari ZIP asli diza; SHA-256 `bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425`. Kandidat 03 dan sumber tidak ditimpa.
- ZIP hasil: `synthetica-feature-20261103-04-spatialflow.zip`, **4.748.586.175 byte**, SHA-256 `7aa84e14e1b4e30aa0a70e222c8d9550b4d533c8016aa1f002d17fe460d96df8`.
- Draft GitHub [432276369](https://github.com/dwp29/Syntenthica/releases/edit/432276369) tetap **draft/prerelease**, target metadata dipatok ke commit build, tidak diterbitkan. Tiga potongan adalah bagian mentah dari satu ZIP, **bukan ZIP flashable terpisah**. Tiap potongan diunduh ulang secara independen dan SHA-256 gabungannya diperiksa oleh workflow.

| Bagian | Asset ID | Ukuran (byte) | SHA-256 |
|---|---:|---:|---|
| 001 | 704274886 | 1.610.612.736 | `43bf226564c032384e07d6e2624b1be2113a7507a047081117e4e015cd1e2385` |
| 002 | 704277071 | 1.610.612.736 | `30d99f3a41acf977311f66e59c721c80c207c1028ca49ddc9c241647737b747c` |
| 003 | 704281287 | 1.527.360.703 | `6a2e6e710ce44694f3a552ea296dc9601fc5cb093f1bdfe399a3859285039c86` |

Laporan build asset `704286815` SHA-256 `93b8ead16e22911d90418c65b2cc52e2e4683244f6c92389603a4738347bc477`; manifest asset `704286879` SHA-256 `1254356192bd836dcfd1193039c2b28673114eeb62bd0ddbae53381c0c7580b7`. Rekonstruksi JSON dari hasil check-run cocok dengan hash metadata kedua asset; unduhan langsung lokal terkendala EOF. Ini **bukan** unduh ulang mandiri kedua asset kecil tersebut.

## Perubahan dan pemeriksaan yang benar-benar lulus

- Menambahkan APK SpatialFlow v1.8.2 `com.codetrio.spatialflow` sebagai aplikasi biasa pada product, SHA-256 `a3c5349073f9819764f185022867a9d47c58347d9c34573423e6397f33f9233d`; signature APK diperiksa pada host tetapi sertifikat pembuat belum diautentikasi dan hubungan source/binary belum dibuktikan. Permission deklarasi termasuk mikrofon, telepon, overlay, akses internet dan permintaan instalasi; ini bukan pernyataan bahwa semua permission telah diberikan.
- Product diperbesar **32 MiB** menjadi 3.925.241.856 byte menggunakan extent logis kedua; keempat salinan metadata dua slot cocok dan `lpdump` pihak ketiga yang dijalankan terisolasi menyetujui layout. Asal-usul source-to-binary `lpdump` belum diautentikasi; ukuran/layout perangkat fisik belum diukur.
- `e2fsck -n` selesai exit 0. Audit membandingkan 2.195 path dan inode lama yang dapat dijangkau, termasuk hash 1.718 file biasa, serta atribut yang ditampilkan; hanya direktori dan APK SpatialFlow ditambahkan. Tidak membandingkan ruang tak teralokasi.
- Baca-ulang seluruh 8 GiB `super` menunjukkan byte di luar metadata dan dua extent product identik; logical `system`, `system_ext`, `vendor`, `boot.img`, `dtbo.img` dan data terkompresi anggota ZIP lain dipertahankan dari kandidat 03. CRC anggota dan `unzip -t` lulus; metadata OTA tetap konsisten. Ini bukan verifikasi boot atau signature whole-file.
- Scan manifest 250 APK di enam root app/priv-app tidak menemukan tabrakan package SpatialFlow. APEX, symlink, ODM/vendor, paket dinamis, dan perilaku package manager tidak tercakup.

## Batas dan pekerjaan tersisa

SpatialFlow **belum diatur sebagai pemutar default**, belum diuji instalasi atau audio/4 GB RAM. Perbaikan sumber untuk intent `MUSIC_PLAYER` masih patch saja dan tidak termasuk dalam APK ini. Play Store dan Google Services Framework ditemukan secara statis di root yang discan; `com.google.android.gms` tidak ditemukan pada root tersebut, sehingga keberadaan di tempat lain dan fungsi Play Services **belum diketahui**. Lihat `HASIL-INVENTARIS-APLIKASI-RUN-41577314268-2026-11-03.json`.

Sebelum pemakaian: kompatibilitas VINTF/SELinux/vendor, external vbmeta/AVB, signature ZIP dan trust recovery, boot, hardware dan izin distribusi harus diselesaikan dan diuji. AxSandbox, spoofing, Leica, Dolby, Theme Manager, KernelSU, biometrik, NFC, DNS/adblock dan fitur lain belum dapat diklaim berfungsi. Lihat laporan lisensi dan gate AxSandbox terpisah.
