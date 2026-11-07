SY N T H E T I C A  3.0 COMPAT — KANDIDAT PENGEMBANGAN

JANGAN FLASH: belum divalidasi pada recovery atau perangkat fisik. Berkas ini
hanya untuk audit kode dan pengujian sintetis; bukan rilis, bukan perbaikan
bootloop, dan bukan bukti dukungan ROM/perangkat. Tidak ada flash yang dilakukan
oleh pengembang pada ponsel pengguna.

Perubahan dibanding ZIP 3.0 asal: mengenali nama joyeuse, curtana, excalibur,
gram dan miatoll; memeriksa petunjuk slot tambahan; menampilkan hash DTB saat
penolakan; serta tidak menjalankan langkah mount AnyKernel. Properti perangkat
recovery saja tidak membuktikan identitas fisik atau kompatibilitas kernel.

Kernel Image.gz dan prepare-boot.sh tidak berubah. HANYA satu hash DTB asal
3.0 yang diterima. Karena hash DTB perangkat pada laporan Lunaris belum ada,
penolakan yang dilaporkan kemungkinan tetap terjadi. Penyebab Error 1 pada
Infinity belum diketahui. Jangan menghapus pemeriksaan atau menambah hash baru
semata-mata karena DTB tersebut terpasang pada perangkat.

Sebelum ada kandidat yang layak diuji: identifikasi boot/ROM aktual, audit ABI
dan penandatangan modul yang dibutuhkan, periksa kepercayaan AVB, dan pastikan
recovery/backup boot yang TEPAT dapat dipulihkan. Bytes metadata AVB yang sama
bukan bukti signature boot baru valid. A/B, bootloader, partition, ukuran,
hash kernel, format boot, ramdisk, pemeriksaan repack, integritas tulis dan
readback tetap diperlukan. Installer tetap tidak membuat backup otomatis.
Kamera, root, jaringan, suspend dan stabilitas belum divalidasi.
