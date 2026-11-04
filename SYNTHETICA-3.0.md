# Synthetica 3.0 — jalur kernel berbasis 2.0

**Status: belum siap flash.** Hasil 3.0 harus lulus build dan pemeriksaan, lalu
kompatibilitas modul dan perilaku perangkat harus diuji terpisah. Pengguna
menyatakan Synthetica 2.0 pernah boot bersama HOS4 di Joyeuse; hash kernel yang
dipakai saat pengujian itu belum terkonfirmasi secara independen.

## Basis dan perubahan

- Source, resep, profil, identitas Manager dan konfigurasi build 2.0 tetap
  dipakai. Input penting diperiksa hash-nya sebelum build.
- Perubahan konfigurasi yang diizinkan hanya `LOCALVERSION` menjadi 3.0.
  `MODVERSIONS`, pemeriksaan tanda tangan modul, SELinux dan fitur lain tidak
  dimatikan. Semua opsi konfigurasi dibandingkan, bukan sekadar beberapa opsi.
- Dalam salinan source sementara, aturan IKCONFIG diperbaiki agar image
  memasukkan konfigurasi build aktual, bukan `stock_defconfig` lama. Hasil
  embedded config diverifikasi byte demi byte. Builder dan pin 2.0 asli tidak
  diedit.
- Tidak ada profil port, bypass vermagic, perubahan ROM, instalasi, atau
  SpatialFlow dalam jalur build ini.

## Build dan batas verifikasi

Workflow `Synthetica 3.0 - kernel berbasis 2.0 (belum siap flash)` menjalankan
unit test, membangun image dari source publik yang dipin, dan hanya mengunggah
image bertanda **DO-NOT-FLASH** beserta konfigurasi, `Module.symvers`,
`System.map`, sertifikat modul **publik** dan status. Kunci privat tidak
termasuk. Workflow tidak membuat ZIP installer atau mengubah perangkat.

Kecocokan konfigurasi dan identitas Manager di biner tidak membuktikan root
atau semua fitur berfungsi. Versi kernel berubah; kecocokan ABI, vermagic dan
kepercayaan tanda tangan modul vendor HOS4 belum terbukti. Build dapat memakai
sertifikat modul baru yang tidak otomatis mempercayai modul ROM atau 2.0.
Boot fisik, AVB dan SELinux saat runtime juga belum diuji. Jangan flash sampai
semua pemeriksaan dan rencana pemulihan yang sesuai telah disiapkan dan
pengguna menyetujui tindakan perangkat.
