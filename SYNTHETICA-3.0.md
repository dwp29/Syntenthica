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

Build pertama telah selesai dan diverifikasi pada [Actions 41881067516](https://github.com/dwp29/Syntenthica/actions/runs/41881067516).
Hasil dan buktinya ada di `artifacts/synthetica-3.0/`; image SHA-256
`0fbdc5f3b0b5a68c89c18ae1e999e83f783ac22157e63888734f7e9d915b1ea7` adalah
**image mentah yang belum teruji, bukan installer dan tidak boleh di-flash**.

Pemeriksaan langsung terhadap image 2.0 dengan SHA-256
`58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff`
mendapatkan CRC `module_layout` `0x08efcbb0` dari tabel export/CRC yang
direkonstruksi melalui kallsyms (7.337 entri). `Module.symvers` build 3.0
menunjukkan nilai yang sama. Pada audit sebelumnya, 41 modul vendor yang
diperiksa tercatat membutuhkan `0x6968ee15`; modul-modul itu tidak cocok pada
pemeriksaan CRC ini. Salinan backup yang dipakai saat audit tersebut belum dapat
dikonfirmasi lagi, sehingga hasil itu tidak membuktikan keadaan modul yang kini
ada di perangkat. Sertifikat publik build 3.0 juga **tidak identik** dengan
sertifikat yang ditemukan di image 2.0; kepercayaan tanda tangan modul ROM
masih harus diuji dan tidak boleh dibypass.

Boot fisik, fitur runtime, AVB dan SELinux saat runtime belum diuji. Jangan
flash sampai kompatibilitas, rencana pemulihan, dan uji yang sesuai disiapkan,
dan pengguna menyetujui tindakan perangkat.
