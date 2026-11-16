# Synthetica Manager 6.5.1 — yang bisa dipasang

> **BERKASNYA SUDAH ADA (16 Nov).** Build `1c36b34`, run `43789901198`.
> `Synthetica-Manager-6.5.1-standalone-DEBUG-SIGNED.apk`, 8 978 323 byte,
> sha256 `ae483f7741869d53e56ffb0cf5b05cf023d2fedebf8e059c2ff2bd879947d46a`.
>
> **Google Drive:** https://drive.google.com/file/d/1rtQAzxns-mBJOZVgSt4yHbsyz1rtQOBU/view
> (id `1rtQAzxns-mBJOZVgSt4yHbsyz1rtQOBU`, MD5 `d65cfd351ff4fbe97d66d5e049b20635`,
> sudah dicocokkan dengan berkas lokal byte-per-byte).
>
> Ambil dengan git, bukan artefak CI (artefak selalu gagal diunduh dari sandbox):
>
> ```
> git clone --depth 1 --branch build-output https://github.com/dwp29/Syntenthica.git
> ```
>
> Diperiksa dari berkasnya sendiri: `retro_arcade`, `RETRO_ARCADE`,
> `ic_emblem_retro`, `theme_banner_retro`, `anime_wibu`, `gothic_crimson`
> semuanya **tidak ada** di DEX maupun resources; `ToolsScreen`, `DownloadScreen`,
> `ios_nav_download` ada; blok tanda tangan memuat v2 (`0x7109871a`) dan v3
> (`0xf05368c0`); sertifikat `CN=Synthetica Manager Standalone (debug key)`.
>
> Apa yang **tidak** berubah: kuncinya tetap kunci debug sekali pakai dari CI,
> bukan `fe833710`. Paketnya `net.ember.labs.standalone`, jadi terpasang **di
> samping** 6.0.0, bukan menimpanya. Belum diuji di perangkat.

## Kenapa 6.5.0 tidak bisa dipasang

Dua sebab, dan saya hanya menyebut satu.

1. **Tidak ditandatangani.** Sudah saya sampaikan.
2. **Tidak akan pernah bisa memperbarui 6.0.0**, bahkan kalau ditandatangani. Android
   mewajibkan sertifikat sama untuk sebuah pembaruan, dan kunci `fe833710…` (yang
   menandatangani 6.0.0) **tidak pernah ada di repo ini**.

## Jawaban: identitas kedua

6.5.1 memakai paket **`net.ember.labs.standalone`**, ditandatangani kunci RSA-4096 baru yang
dibuat di dalam CI setiap kali build dan tidak disimpan di mana pun. Karena nama paketnya
berbeda, Android memasangnya **di samping** Manager 6.0.0, bukan menimpanya.

Yang **tidak** berubah: identitas `net.ember.labs` milik Anda, APK 6.0.0 yang sudah
terpasang, dan pin kernel `fe833710…`. Tidak ada yang dibuat tidak valid.

| | |
|---|---|
| Berkas | `Synthetica-Manager-6.5.1-standalone-DEBUG-SIGNED.apk` |
| Ukuran | 8 978 323 byte |
| SHA-256 | `ae483f7741869d53e56ffb0cf5b05cf023d2fedebf8e059c2ff2bd879947d46a` |
| Paket | `net.ember.labs.standalone` |
| versi | 6.5.1 / 75100 |
| Sertifikat | `CN=Synthetica Manager Standalone (debug key)`, SHA-256 `0E:97:82:41:…:1D:AC` |
| Tanda tangan | v2 + v3 (v1 mati) |
| Sumber | cabang `build-output`, run `43789901198`, commit `1c36b34` |

> Versi yang dulu ada di Drive (id `11vNJOvg…`, 9 199 787 byte) berasal dari commit
> `8be5d18` dan **masih memuat Retro Arcade**. Berkas itu sudah tidak dipakai; yang
> berlaku adalah 8 978 323 byte di atas.

Diverifikasi dari berkasnya sendiri, bukan dari log: blok APK Signing berisi v2
(`0x7109871a`) dan v3 (`0xf05368c0`), paket dan versi di manifest benar, `anime_wibu` dan
`gothic_crimson` tidak ada di DEX, kunci `wallpaper_*` ada.

## Konsekuensi yang harus Anda tahu

- **Root/kernel tidak akan mengenalinya sebagai manager resmi.** Driver KernelSU mencocokkan
  sertifikat APK dengan pin di kernel. Sertifikat 6.5.1 (`ef0eb4e0…`) bukan `fe833710…`,
  jadi kernel akan memperlakukannya seperti aplikasi biasa: fitur yang butuh UAPI v4 natif
  tidak jalan. Mode *Universal Root Bridge* lewat `su` tetap bisa, seperti aplikasi pihak
  ketiga mana pun.
- Kalau Anda meng-uninstall 6.0.0, Anda **tidak bisa memasangnya kembali** — APK-nya ada di
  Drive, tetapi tidak ada yang bisa mengembalikan kemampuan "manager resmi" tanpa kunci itu.
- **Kunci debug ini bukan kunci rilis.** Jangan pakai untuk distribusi. Ia ada hanya karena
  kunci asli hilang.

## Kalau kunci asli ditemukan

Satu perintah, dan 6.5.x menjadi pembaruan sungguhan atas 6.0.0:

```
apksigner sign --ks synthetica-2.0.p12 --ks-key-alias synthetica \
  --out Synthetica-Manager-6.5.1-SIGNED.apk \
  Manager-6.5.1-standalone-UNSIGNED.apk
```

dengan aplikasi dibangun memakai `SYNTHETICA_APP_ID=net.ember.labs`. Jangan pakai kunci 6.1
(`5cc7e1a7…`, sudah Anda minta dihapus): menandatangani dengan kunci itu sama saja membuat
identitas ketiga yang juga tidak dikenali kernel.

## Yang belum terbukti

APK ini **belum pernah dipasang dan dijalankan di perangkat**. Yang terbukti: ia memverifikasi
tanda tangan v2+v3, identitasnya benar, isinya sesuai maksud, dan selaras 4-byte + 16 KiB.
Apakah ia benar-benar menginstal dan tampil sesuai harapan hanya bisa dijawab di ponsel.
