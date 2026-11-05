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
unit test dan membangun image dari source publik yang dipin. Workflow telah
diperbarui untuk membangun serta menandatangani dalam build yang sama enam
modul yang sudah dipilih `=m` pada konfigurasi 2.0: `tcp_bic`, `tcp_westwood`,
`tcp_htcp`, `gspca_main`, `rmnet_perf`, dan `rmnet_shs`. Tidak ada perubahan
opsi Kconfig untuk menambah modul itu.

Sebelum mengunggah hasil baru, pemeriksaan statis mensyaratkan ELF arm64,
nama dan vermagic tepat, dependensi terbundel, seluruh CRC `__versions`
sesuai `Module.symvers`, serta tanda tangan PKCS#7 yang diverifikasi terhadap
sertifikat publik yang tertanam dalam image build yang sama. Kunci privat
tidak diekspor. Uji sintetis juga memeriksa perubahan isi, CRC salah,
sertifikat salah dan modul hilang. Pemeriksaan ini tidak memuat modul pada
perangkat. Modul dari satu build **tidak boleh dipasangkan** dengan image
build lain yang menggunakan sertifikat berbeda.

Workflow tidak membuat ZIP installer, mengubah ROM, atau mengubah perangkat.
Kecocokan konfigurasi, identitas Manager dan enam modul build sendiri tidak
membuktikan root, seluruh fitur, atau kompatibilitas modul vendor HOS4.

Build pertama telah selesai dan diverifikasi pada [Actions 41881067516](https://github.com/dwp29/Syntenthica/actions/runs/41881067516).
Hasilnya saat ini ada di `artifacts/synthetica-3.0/`; image SHA-256
`0fbdc5f3b0b5a68c89c18ae1e999e83f783ac22157e63888734f7e9d915b1ea7` adalah
**image mentah yang belum teruji, bukan installer dan tidak boleh di-flash**.
Build pertama ini belum menyertakan enam modul; workflow yang diperbarui
harus menghasilkan dan memverifikasi image dan modul baru bersama-sama.

Pemeriksaan langsung terhadap image 2.0 dengan SHA-256
`58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff`
mendapatkan CRC `module_layout` `0x08efcbb0` dari tabel export/CRC yang
direkonstruksi melalui kallsyms (7.337 entri). `Module.symvers` build pertama
3.0 menunjukkan nilai yang sama.

Audit baca-saja terhadap arsip ROM `H0S4diza.zip` dengan SHA-256
`454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63`
memeriksa 41 modul yang tercantum dalam `modules.load` vendor. Seluruhnya
memiliki CRC `module_layout` `0x6968ee15`, berbeda dari image 2.0 dan build
pertama 3.0; tanda tangan tidak satu pun terverifikasi menggunakan masing-masing
sertifikat publik spesifik kedua build tersebut. Ini membuktikan ketidakcocokan
statis dengan kombinasi yang diperiksa, bukan bahwa seluruh modul pasti
berjalan atau wajib dipakai pada perangkat. Keyring perangkat tidak diperiksa,
dan audit ini tidak memastikan ROM yang saat ini terpasang identik dengan arsip
tersebut. Laporan pengguna bahwa 2.0 pernah boot tetap merupakan keterangan
pengguna, bukan pengujian fitur independen. Arsip ROM privat tidak disertakan.

Enam modul dari source sendiri bukan perbaikan otomatis untuk seluruh 41 modul
ROM. Kepercayaan tanda tangan, pengganti driver, dan integrasi ROM harus
dibuktikan tanpa bypass.

Boot fisik, fitur runtime, AVB dan SELinux saat runtime belum diuji. Jangan
flash sampai kompatibilitas, rencana pemulihan, dan uji yang sesuai disiapkan,
dan pengguna menyetujui tindakan perangkat.
