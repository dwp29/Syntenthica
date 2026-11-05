# Synthetica 3.0 — jalur kernel berbasis 2.0

**Status: belum siap flash.** Hasil 3.0 harus lulus build dan pemeriksaan, lalu
kompatibilitas modul dan perilaku perangkat harus diuji terpisah. Pengguna
menyatakan Synthetica 2.0 pernah boot bersama HOS4 di Joyeuse; hash kernel yang
dipakai saat pengujian itu belum terkonfirmasi secara independen.

**Koreksi dokumen lama:** sebuah dokumentasi di arsip mencampurkan nama
Joyeuse dengan POCO F3/Snapdragon 870. Referensi device tree publik menyebut
[Joyeuse sebagai Redmi Note 9 Pro/SM7125](https://github.com/ryzspace/android_device_xiaomi_joyeuse/blob/35c6ad5a217723bbbb06a44d6fb8cc0cd6c67df3/README.md),
sedangkan [Alioth memakai pohon SM8250](https://github.com/xiaomi-sm8250-devs/android_device_xiaomi_alioth/blob/76d3885fb818e0ee229545d5186dc236733afc75/device.mk).
Identitas perangkat pengguna belum diperiksa secara independen; jangan memakai
dokumen lama sebagai dasar flash. Klaim dokumen itu bahwa `super.img` bukan
format LP dan vendor tidak dapat dibaca sebagai ext4 juga tidak sesuai dengan
audit lokal: checksum metadata LP valid dan filesystem vendor dapat dibaca
sebagai ext4. Hal ini tidak membuktikan identitas perangkat atau boot aman.

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
- Installer 2.0 tidak dipakai untuk 3.0. Core AnyKernel dalam ZIP 2.0 dapat
  memanggil `magiskboot dtb ... patch` ketika mendeteksi Magisk; karena itu
  pelestarian DTB dan kebijakan AVB tidak boleh diasumsikan. Integrasi boot
  yang aman masih harus dibuktikan tanpa mengubah ROM atau perangkat.

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

Audit yang sama terhadap sertifikat bundel build **terbaru** 41957764426 juga
mendapat 0 dari 41 tanda tangan terverifikasi dan 0 dari 41 CRC `module_layout`
yang cocok; modul bundel sendiri lolos sebagai kontrol positif. Ini bukan bukti
keyring atau kebijakan enforcement perangkat. Enam modul dari source sendiri
bukan perbaikan otomatis untuk seluruh 41 modul ROM.

Pemetaan nama Kbuild menemukan kandidat untuk 40 dari 41 modul, tetapi nama
bukan bukti kesetaraan. `mi_memory` belum memiliki source yang terbukti cocok:
[donor publik Nexus, commit `d26c193dcd97`](https://github.com/projects-nexus/nexus_kernel_xiaomi_sm8250/tree/d26c193dcd97812a9a565ac40fe5092cc9a18fbf/drivers/misc/mi-memory),
misalnya, menggabungkan `mem_interface.o` ke modul, sedangkan modul arsip
mengimpor simbol interface itu; source 2.0 juga belum menyediakan hook setara
yang terbukti. Source donor juga memanggil `memblock_phys_mem_size`,
`memblock_reserved_size` dan `ufshcd_read_desc_param`: ketiga nama itu muncul
di `System.map` bundel terbaru, tetapi tidak ada sebagai export di
`Module.symvers`. Pada source 2.0 yang dipin, `ufshcd_read_desc_param` bahkan
berdeklarasi `static`, konsisten dengan tipe lokal `t` di `System.map`; donor
menyatakan fungsi itu eksternal. Ini memerlukan pemeriksaan link/modpost jika
source tersebut kelak dibangun sebagai modul; nama di `System.map` bukan export
modul.

Donor juga mengaitkan `set_ufs_hba_data()` pada `ufshcd_slave_configure()`
untuk LUN 2; hook itu tidak ada pada file UFS source 2.0 yang dipin. Pada
konfigurasi 3.0 saat ini `SCSI_UFSHCD=y`, sedangkan donor memakai guard
`IS_ENABLED(CONFIG_MI_MEMORY_SYSFS)` yang juga aktif untuk `=m`. Menyalin hook
tersebut secara langsung dapat menciptakan referensi dari kernel bawaan ke
simbol yang hanya berada dalam modul. Urutan inisialisasi dan umur pointer UFS
juga belum dibuktikan. Donor tidak diport ke build 3.0 saat ini. Sebelumnya
memang pernah ada eksperimen compile-only berbasis 2.0 dengan donor Nexus
sebagai built-in, tetapi empat atribut debug (`tag_stats`, `err_state`,
`err_reason`, `req_stats`) dihilangkan dan tidak ada uji perangkat. Eksperimen
itu sudah dihapus dan tidak membuktikan kesetaraan maupun keselamatan UFS;
jangan menghidupkannya kembali sebagai solusi. Kecocokan ABI, kepercayaan
penandatangan, pengganti driver, dan integrasi ROM harus dibuktikan tanpa bypass.

Pencarian publik tambahan terhadap 157 repository kandidat Miatoll/SM6250/
SM7125/Joyeuse tidak menemukan `drivers/misc/mi-memory/Makefile` maupun
`drivers/misc/mi-memory/mem_interface.c` pada default branch yang diperiksa.
Kontrol positif untuk kedua path pada donor Nexus berhasil. Pencarian ini hanya
memeriksa dua path dan satu branch per repository, **bukan** bukti bahwa semua
source publik tidak ada. Tree resmi Xiaomi
[`curtana-q-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/231fa425e8f42661f74339de63c3ad472de6077d)
dan [`gram-q-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/c5c29fbc28f5d061dd9b50c4e96a59493598efe8)
yang diperiksa juga tidak memiliki path `mi-memory` atau `mem_interface`.
Source resmi [`sweet-r-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/758bb7ef50af360e728662a1ed3b3a1b977a2f13/drivers/misc/mi-memory)
memiliki tiga file parsial untuk perangkat berbeda, tanpa Makefile pada direktori
itu; prototipe fungsi interface-nya berbeda dari donor Nexus. Source itu belum
terbukti identik dengan modul Joyeuse/HOS4 dan bukan dasar port yang aman.

Ada kandidat baca-saja lain dari
[Camellian, commit `a31f6f3c6ad1`](https://github.com/Hadenix/android_kernel_xiaomi_camellian/tree/a31f6f3c6ad1307a7342819c09ddaa6480a5b7c0/drivers/misc/mi-memory):
Kbuild-nya memisahkan `mem_interface.o` sebagai built-in dari modul `mi_memory`,
dan source-nya memakai kelima nama interface yang diimpor modul arsip. Ini
kemiripan struktur dan nama yang lebih dekat, **bukan** bukti CRC, source,
perilaku atau kesetaraan dengan ROM. Source tersebut berbasis perangkat
MediaTek/kernel 4.14.186; ia meneruskan pointer HBA dari `ufshcd_init()` melalui
hook yang belum ada di baseline, dan menyatakan `ufshcd_read_desc_param`
eksternal sedangkan fungsi tersebut `static` pada baseline. Source kandidat juga
mengakses `ufs_stats.tag_stats` dan `req_stats`, yang pada baseline berada di
bawah `CONFIG_DEBUG_FS` yang nonaktif, serta `ufs_stats.err_state` yang tidak
ada pada struct baseline. Urutan dan umur pointer tetap belum terbukti.
Kandidat ini belum diport atau diuji untuk Joyeuse.

Audit privat ulang menemukan 31 record versi pada `mi_memory`: delapan CRC
cocok bundel, 18 berbeda, dan lima nama interface tidak ada di export bundel.
Sebagai pemeriksaan terbatas, `genksyms` host dari source 2.0 yang dipin
membandingkan deklarasi terisolasi Camellian dengan CRC import modul ROM.
Deklarasi `memblock_mem_size_in_gb` menghasilkan CRC yang sama; deklarasi
`ufs_get_string_desc` dan `ufs_read_desc_param`, beserta enum Camellian,
menghasilkan CRC berbeda untuk kondisi yang diuji. Delapan kombinasi kondisi
efektif (`UFSHPB` atau `SCSI_SKHPB`), `UFSFEATURE` dan `UFSTW` diuji untuk
enum descriptor; kontrol `get_random_u32` dan `get_random_u64` cocok dengan `Module.symvers`
bundel. Mengganti enum Camellian dengan enum dari source 2.0 yang dipin
menghasilkan CRC yang sama untuk `ufs_read_desc_param`, tetapi tetap berbeda
untuk `ufs_get_string_desc`. Prototipe yang digunakan diasumsikan seperti
Camellian; implementasi source ROM sebenarnya tidak diketahui.

Pencarian tambahan memeriksa `drivers/scsi/ufs/ufs.h` pada default branch 232
repository kandidat. Sebanyak 190 mengandung enum descriptor yang dapat
diperiksa (enam teks enum unik); 42 path mengembalikan 404. Dengan prototipe
`ufs_get_string_desc` yang diasumsikan tadi dan kondisi enum yang dapat diuji,
tidak ada CRC yang cocok. Ini hanya sampel satu path/branch, bukan pencarian
seluruh source publik. Semua pengujian `genksyms` ini memakai deklarasi
terisolasi, bukan kompilasi source utuh atau pembuktian konfigurasi donor;
kecocokan CRC 32-bit juga bukan bukti identitas source, ABI keseluruhan,
kesetaraan fungsi, atau keselamatan UFS. Tidak ada modul atau image baru.

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
  --boot /tmp/audit-privat/boot-asli.img \
  --dtbo /tmp/audit-privat/dtbo-asli.img \
  --bundle artifacts/synthetica-3.0 \
  --output /tmp/audit-privat/laporan-baru.json
```

`--init`, `--source`, `--boot` dan `--dtbo` opsional. Direktori modul harus
datar dan berisi `modules.load`, `modules.dep`, serta file `.ko` arm64 tanpa
kompresi. Parser hanya mendukung boot header Android v2, FDT v17 dan tabel
DTBO v0; format lain ditolak, bukan ditebak. Output harus berupa file baru di
luar repositori dan semua direktori input; tool menolaknya jika sudah ada dan
membuatnya dengan izin privat. **Jangan commit atau unggah laporan, ROM, maupun
modul ROM.** Hapus salinan privat sementara setelah selesai jika tidak lagi
diperlukan.

Workflow `Synthetica 3.0 - host safety tests (no ROM)` menguji tool dan guard
dengan fixture sintetis serta bundel build publik; ROM dan laporan privat
tidak dikirim ke CI. Tool memeriksa checksum bundel, sertifikat dalam image dan
tanda tangan modul bundel, lalu membandingkan CRC, nama simbol, tanda tangan
dengan sertifikat build tersebut, dependensi, dan perintah `insmod`/`modprobe`
literal pada file `.rc` yang diberikan. Untuk CRC yang berbeda atau export yang
hilang, laporan privat menyebut nama serta tipe di `System.map` dan membedakan
nama yang hanya muncul di sana dari export. Tipe simbol bukan bukti export atau
kecocokan ABI. Kecocokan CRC yang penyedia tercatatnya hanya modul
atau lebih dari satu juga dicatat terpisah; nama penyedia dalam bundel tidak
membuktikan modul itu akan dimuat atau dipercaya. Rincian ini adalah audit,
bukan perubahan pada build atau bukti dependensi tersedia saat runtime.
Parameter callback diperiksa melalui struktur ELF, bukan hanya teks `.modinfo`.
Jika tersedia, `srcversion_comparison` juga membandingkan metadata `srcversion`
modul input dengan modul bundel yang bernama internal sama. `not_comparable`
bukan kecocokan: `not_comparable_reasons` membedakan modul senama yang tidak ada
dari metadata `srcversion` yang tidak tersedia pada input atau bundel. Metadata
dapat ditiru atau tidak lengkap: nilai sama tidak membuktikan source identik,
kompatibilitas ABI, atau perilaku runtime. Versi audit sebelumnya dijalankan
ulang pada 41 modul arsip privat yang sama: satu modul (`gspca_main`) dapat
dibandingkan dan nilainya berbeda; 40 lainnya `not_comparable`, termasuk
`mi_memory`. Rincian alasan yang baru ditambahkan belum dijalankan ulang pada
ROM privat. Hasil ini bukan uji perangkat; laporan dan salinan modul tetap
privat dan tidak disertakan.

Pemindaian source hanya menemukan kandidat Kbuild berdasarkan nama; identitas
source harus diverifikasi terpisah dan kondisi Kbuild tidak dievaluasi
sepenuhnya. Nama simbol yang cocok
**tidak**
membuktikan kode/fungsi identik, dan urutan `modules.load` tidak dengan
sendirinya menjelaskan bagaimana `modprobe` menyelesaikan dependensi. Skrip,
partisi, kondisi properti, keyring, dan jalur pemuatan lain bisa saja tidak
tercakup. Hasil tidak membuktikan modul dapat dimuat atau fitur bekerja.

Jika image boot dan DTBO disediakan, tool memeriksa struktur serta hash bagian
kernel, ramdisk, DTB dan entry DTBO tanpa membuat atau menandatangani image.
`--candidate-boot` opsional membandingkan file v2 lain yang sudah ada dengan
`--boot`, termasuk metadata header dan bagian non-kernel. ID SHA-1 boot lama
bukan tanda tangan; keberadaan atau ketiadaan footer AVB di akhir file juga
**bukan** bukti status AVB. Arsip yang diperiksa tidak memuat `vbmeta.img`,
sehingga descriptor dan kepercayaan bootloader perangkat belum diketahui.
Perbandingan byte tidak membuktikan kompatibilitas boot atau mengizinkan
flashing.

Unpacker AOSP Android 10 commit `5aa0e4241029c80617a8e98b07f7f48ab6b3a3d7`
(selepas penyesuaian pembagian integer untuk Python 3) telah dipakai sebagai
pembanding host untuk tiga bagian boot. Simulasi format sementara juga
memeriksa kernel, ramdisk, DTB dan metadata header; hasilnya tidak disimpan
sebagai produk. Satu kesalahan awal menunjukkan `mkbootimg.py` AOSP tersebut
menerima tanggal patch `YYYY-MM` tetapi diam-diam menyimpan nol; format yang
diparsenya adalah `YYYY-MM-DD`. Pemeriksaan header menangkap selisih ini,
meskipun ID boot SHA-1 tetap cocok. Simulasi yang diperbaiki tidak bertanda
tangan dan tetap **bukan** bukti AVB, kompatibilitas atau izin flash.

Boot fisik, fitur runtime, AVB dan SELinux saat runtime belum diuji. Jangan
flash sampai kompatibilitas, rencana pemulihan, dan uji yang sesuai disiapkan,
dan pengguna menyetujui tindakan perangkat.
