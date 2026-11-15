# Synthetica Manager 6.5.1 — yang bisa dipasang

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
| Berkas | `Synthetica-Manager-6.5.1-standalone-INSTALLABLE-DEBUG-SIGNED.apk` |
| Ukuran | 9 199 787 byte |
| SHA-256 | `45671c386d672ad78937854468986734e6b4ff0e2e580e2156b470701b38d621` |
| Paket | `net.ember.labs.standalone` |
| versi | 6.5.1 / 75100 |
| Sertifikat | 1364 byte, SHA-256 `ef0eb4e04f7321b0fa6a25ce651b10b3de9474ecad83908e10fb4088739db1bf` |
| Tanda tangan | v2 + v3 (v1 mati) |
| Drive | id `11vNJOvgwQhoUWAHTUATh253YQIc2a4I8` |
| CI | run `43722714274` |

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
