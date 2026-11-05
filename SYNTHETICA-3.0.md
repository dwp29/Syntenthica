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

Build kernel dan keenam modul berhasil pada [Actions 41957764426](https://github.com/dwp29/Syntenthica/actions/runs/41957764426).
Satu bundel hasil build yang sama ada di `artifacts/synthetica-3.0/`; image
SHA-256 `60ca6baee91ef0b41f6898ebaaf2ea776f3ff3d626ce4f29c32df69ec902159b`
adalah **image mentah yang belum teruji, bukan installer dan tidak boleh
di-flash**. Tanda tangan dan seluruh CRC versi enam modul diperiksa kembali
terhadap image, sertifikat publik dan `Module.symvers` bundel itu; seluruh
`SHA256SUMS.txt` juga diperiksa ulang secara lokal. Kunci privat tidak ada.

Pada [run pengumpulan 41958942643](https://github.com/dwp29/Syntenthica/actions/runs/41958942643),
pengambilan dan verifikasi independen berhasil, tetapi langkah penyimpanan
akhir dilaporkan gagal meskipun commit hasil `b9215a1` sudah muncul di branch.
Isi commit tersebut kemudian diverifikasi kembali secara lokal; kegagalan
run pengumpulan tidak dianggap sebagai run sukses.

Build pertama [41881067516](https://github.com/dwp29/Syntenthica/actions/runs/41881067516)
tidak menyertakan modul. Run lanjutan [41953079538](https://github.com/dwp29/Syntenthica/actions/runs/41953079538)
mengompilasi kernel dan modul tetapi tidak mengunggah hasil karena parser
semula menolak teks non-ASCII pada metadata deskriptif. Parser diperbaiki dan
diuji sebelum build terakhir; identitas, CRC dan tanda tangan tetap ketat.

Pemeriksaan langsung terhadap image 2.0 dengan SHA-256
`58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff`
mendapatkan CRC `module_layout` `0x08efcbb0` dari tabel export/CRC yang
direkonstruksi melalui kallsyms. `Module.symvers` build terbaru 3.0 menunjukkan
nilai yang sama. Pemeriksaan lanjutan membandingkan seluruh 12.227 export
bawaan 2.0 (7.337 biasa dan 4.890 GPL) dengan export `vmlinux` build terbaru
3.0: tidak ada nama export yang hilang atau CRC yang berbeda. Ekstraksi nama
dan jenis simbol menggunakan `vmlinux-to-elf` 1.4.0 juga menghasilkan 136.727
entri 2.0 yang semuanya ada pada `System.map` 3.0 terbaru; System.map memiliki
18 entri metadata/absolut tambahan. Ini bukti statis kesamaan nama dan CRC,
bukan bukti kesamaan kode, kepercayaan penandatangan, boot atau semua fitur.

Audit baca-saja terhadap arsip ROM `H0S4diza.zip` dengan SHA-256
`454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63`
memeriksa 41 modul yang tercantum dalam `modules.load` vendor. Seluruhnya
memiliki CRC `module_layout` `0x6968ee15`, berbeda dari image 2.0 serta build
pertama dan terbaru 3.0. Tanda tangan tidak satu pun terverifikasi menggunakan
masing-masing sertifikat publik spesifik image 2.0 dan build **pertama** 3.0.
Karena setiap build dapat memakai sertifikat berbeda, hasil itu tidak boleh
digeneralisasi ke image lain. Ini membuktikan ketidakcocokan statis dengan
kombinasi yang diperiksa, bukan bahwa seluruh modul pasti berjalan atau wajib
dipakai pada perangkat. Keyring perangkat tidak diperiksa,
dan audit ini tidak memastikan ROM yang saat ini terpasang identik dengan arsip
tersebut. Laporan pengguna bahwa 2.0 pernah boot tetap merupakan keterangan
pengguna, bukan pengujian fitur independen. Arsip ROM privat tidak disertakan.

Enam modul dari source sendiri bukan perbaikan otomatis untuk seluruh 41 modul
ROM. Kepercayaan tanda tangan, pengganti driver, dan integrasi ROM harus
dibuktikan tanpa bypass.

## Audit vendor offline dan privat

`build-kit/scripts/audit_synthetica3_vendor.py` membandingkan salinan hasil
setiap build dengan **salinan ekstraksi lokal** direktori modul vendor. Tool
ini hanya membaca input, tidak memerlukan perangkat atau mount, dan tidak
memuat modul. Contoh (gunakan direktori privat yang sudah ada):

```sh
python3 build-kit/scripts/audit_synthetica3_vendor.py \
  --modules /tmp/audit-privat/vendor-modules \
  --init /tmp/audit-privat/vendor-init \
  --source /tmp/audit-privat/source-kernel-terverifikasi \
  --bundle artifacts/synthetica-3.0 \
  --output /tmp/audit-privat/laporan-baru.json
```

`--init` dan `--source` opsional. Direktori modul harus datar dan berisi
`modules.load`, `modules.dep`, serta file `.ko` arm64 tanpa kompresi. Output
harus berupa file baru di luar repositori dan semua direktori input; tool
menolaknya jika sudah ada dan membuatnya dengan izin privat. **Jangan commit
atau unggah laporan, ROM, maupun modul ROM.** Hapus salinan privat sementara
setelah selesai jika tidak lagi diperlukan.

Tool memeriksa checksum bundel, sertifikat dalam image dan tanda tangan modul
bundel, lalu membandingkan CRC, nama simbol, tanda tangan dengan sertifikat
build tersebut, dependensi, dan perintah `insmod`/`modprobe` literal pada
file `.rc` yang diberikan. Parameter callback diperiksa melalui struktur ELF,
bukan hanya teks `.modinfo`. Pemindaian source hanya menemukan kandidat
Kbuild berdasarkan nama; identitas source harus diverifikasi terpisah dan
kondisi Kbuild tidak dievaluasi sepenuhnya. Nama simbol yang cocok **tidak**
membuktikan kode/fungsi identik, dan urutan `modules.load` tidak dengan
sendirinya menjelaskan bagaimana `modprobe` menyelesaikan dependensi. Skrip,
partisi, kondisi properti, keyring, dan jalur pemuatan lain bisa saja tidak
tercakup. Hasil tidak membuktikan modul dapat dimuat atau fitur bekerja.

Boot fisik, fitur runtime, AVB dan SELinux saat runtime belum diuji. Jangan
flash sampai kompatibilitas, rencana pemulihan, dan uji yang sesuai disiapkan,
dan pengguna menyetujui tindakan perangkat.
