# Synthetica 3.1 — kernel kompilasi ulang dengan installer 2.0

## Unduh

- [ZIP Synthetica-3.1-Installer-2.0-TEST](https://drive.google.com/file/d/1bUcr4Xyurv4mbF-iBKcR04GL4B2p0Izv/view?usp=drivesdk)
- [Berkas checksum SHA-256](https://drive.google.com/file/d/1dSwRUvRjst6uPRykeP09M-DNpIg0J7kl/view?usp=drivesdk)
- Ukuran ZIP: **25.423.751 byte**. SHA-256:
  `1ffe861ceaa2775e4f75bc9f7ecd4b7c56cf9c146f1690eb941c8dd2e5200d4a`

Kedua file berada di folder Drive pribadi yang sama dengan paket sebelumnya.
Hak akses ZIP diperiksa: hanya pemilik, tidak dibagikan publik. Rilis lama
tetap tersedia dan tidak diubah.

## Apa yang dibuat

Ini **kernel baru yang benar-benar dikompilasi ulang**, bukan 3.0 yang hanya
diganti label. `uname -r` hasil build adalah
`4.14.357-openela-synthetica-3.1` dan SHA-256 `Image.gz` adalah
`650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287`.
Source, patch fitur, Neutron toolchain dan resep mengikuti build 3.0; konfigurasi
yang dihasilkan dibandingkan dengan konfigurasi 3.0 yang tepat dan perbedaan
satu-satunya adalah `LOCALVERSION`.

Installer memakai core AnyKernel, alat dan `ksud` asli dari ZIP 2.0, termasuk
pemeriksaan properti dan alur tulis yang sama. Perubahan hanya label, logo ASCII
besar, progress dan teks TWRP yang lebih ringkas; peringatan data terkunci,
ksud gagal dan error core tetap ada; proses pencatatan log tidak dihilangkan.
Nilai `do.devicecheck=1` dan
pengenalan properti `miatoll`, `curtana`, `excalibur`, `gram`, `joyeuse` tetap
seperti 2.0; pengenalan properti **bukan** bukti perangkat atau ROM pasti aman.
ZIP tidak membawa DTB, DTBO atau modul `.ko`.

Sertifikat modul publik baru memiliki SHA-256
`6d8ab0c34f5052d098c801841d34976a75ef9c3fed53e3630376dc2b0f93b72e`, berbeda
dari 3.0. CRC `module_layout` sama dengan 3.0 (`0xed5659d1`), tetapi itu saja
**tidak membuktikan** bahwa modul ROM kompatibel atau dipercaya kernel ini.

## Pengujian dan batasnya

- [Build kernel 3.1](https://github.com/dwp29/Syntenthica/actions/runs/42399880621)
  lulus kompilasi serta pemeriksaan source, config tertanam, release, Manager
  dan sampel modul bertanda tangan dari build yang sama.
- [Build dan tes ZIP final](https://github.com/dwp29/Syntenthica/actions/runs/42400941300)
  lulus. ZIP yang dihasilkan CI memiliki SHA-256 yang sama dengan file Drive.
  Empat tes ARM/QEMU menggunakan **image 3.1 yang sebenarnya** pada boot
  sintetis dengan path diarahkan ke file sementara dan operasi sistem di-mock:
  data tersedia, data terkunci, gagal salin ksud, dan boot tidak valid.
- [Tes UI dan installer 2.0](https://github.com/dwp29/Syntenthica/actions/runs/42400941140)
  juga lulus. Ini bukan menjalankan `update-binary` pada TWRP fisik.
- Pengguna melaporkan paket 3.0 + installer 2.0 sebelumnya sudah boot pada
  seseorang yang sebelumnya mendapat Error 1. Itu **bukan** pengujian untuk
  image 3.1 baru ini dan bukan bukti kompatibilitas semua ROM.

**Boot fisik 3.1, root, Manager, AVB, kamera dan kepercayaan/kompatibilitas
modul ROM belum diuji atau dipastikan.** Karena itu paket diberi nama `TEST`.

## Sebelum mencoba

Pastikan bootloader terbuka, perangkat/ROM/slot sesuai dan recovery dapat
digunakan. Simpan backup **boot yang tepat** serta cara memulihkannya; installer
2.0 tidak membuat backup otomatis. Jika ada `/data/adb/ksud`, backup juga file
tersebut: installer dapat menggantinya **sebelum** menulis boot, termasuk jika
flash kemudian gagal. Jika data terkunci, `ksud` dilewati dan muncul peringatan.

Alur 2.0 tidak memiliki guard slot/unlock, hash DTB dan readback pascatulis
setara installer 3.0 asli. `IS_SLOT_DEVICE=0` bukan bukti tidak ada slot.
Dalam beberapa kondisi seperti Magisk, AnyKernel dapat mem-patch DTB/AVB;
validitas signature boot belum diverifikasi. Jangan wipe data atau mengubah
vbmeta untuk memaksa boot. Bila gagal saat penulisan, jangan reboot sebelum
memulihkan backup boot yang tepat dari recovery.

Bila penyimpanan tersedia untuk ditulis, log instalasi disimpan di
`Synthetica/install-log-*.txt`. Recovery dapat menimpa `/tmp/recovery.log` saat
ZIP lain di-flash; simpan terlebih dahulu jika diperlukan.

Resep: `build-kit/scripts/build_synthetica31.py`; packager:
`build-kit/scripts/package_synthetica31.py`; identitas bukti build publik:
`build-kit/ci/synthetica31-build-evidence.json`.
