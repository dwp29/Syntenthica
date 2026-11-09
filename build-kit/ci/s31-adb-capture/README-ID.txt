SYNTHETICA 3.1 — PENGAMBIL LOG VIA PC, BUKAN KERNEL / INSTALLER

Baca juga laporan: SYNTHETICA-3.1-INSIDEN-INFINITY.md di repositori.
Alat ini HANYA membaca lewat adb get-state, adb shell ls, dan adb exec-out cat;
tidak memasang kernel, me-reboot, me-mount, mengubah AVB, atau menghapus data
pada ponsel. Alat menulis file log di PC. Jangan jalankan sebagai ZIP recovery.
Belum diuji di OrangeFox atau perangkat fisik; hasil bergantung ADB/izin recovery.

PERSIAPAN
1. PC dengan Python 3.9+ dan Android Platform Tools adb dalam PATH. Kabel USB.
   Di Windows gunakan 'python' atau 'py -3'; di macOS/Linux gunakan 'python3'.
2. Siapkan recovery yang dapat diakses dan cadangan boot yang cocok dengan
   device, ROM/build, keadaan root dan slot yang benar serta cara memulihkannya.
   Backup Android 16 belum tentu cocok untuk ROM Android 17. Kernel 3.1 sudah
   dilaporkan gagal boot pada Infinity 4.1; jangan ulang flash hanya demi log.
3. Uji komunikasi di recovery yang saat ini normal: adb devices. Bila unauthorized,
   offline, lebih dari satu perangkat, atau recovery tidak mendukung ADB, selesaikan
   akses yang aman dahulu. Jangan mematikan keamanan atau menebak partisi/slot.
4. Jalankan 'install' ke folder baru untuk uji alat TANPA flash. Log yang diambil
   hanya log recovery saat itu, bukan bukti insiden. 'STATUS.json' menyatakan
   captured, empty, truncated, command_failed, timeout atau adb_unavailable.

PADA PC — CONTOH WINDOWS (di folder tempat capture.py diekstrak)
  adb devices
  py -3 capture.py --stage install --out log-install

Pada Linux/macOS ganti 'py -3' dengan 'python3'. Bila executable adb tidak ada
pada PATH, tambahkan --adb dengan path lengkap yang sesuai. Folder --out harus
baru; alat tidak menimpa folder sebelumnya. Hindari output pada folder publik.

Jika kelak tes kernel disepakati setelah ROM dan jalur pemulihan terverifikasi:
- Simpan foto semua pesan installer. Segera simpan log instalasi DARI SESI
  RECOVERY YANG SAMA sebelum reboot atau menjalankan ZIP lain, pakai perintah di
  atas dengan folder baru. Bila penulisan boot gagal, JANGAN reboot; prioritaskan
  pemulihan yang tepat.
- Jika boot gagal dan aman kembali ke recovery yang sudah tersedia, salin pstore
  secepatnya, sebelum reboot lebih lanjut, dari PC:
  py -3 capture.py --stage boot --out log-boot-gagal
  Pada Linux/macOS: python3 capture.py --stage boot --out log-boot-gagal
- Jika perangkat dapat boot kembali, jangan menganggap log dari boot baru sebagai
  log kegagalan sebelumnya. Recovery atau reboot bisa menimpa bukti lama.

Tahap boot mengambil file bernama aman dari /sys/fs/pstore terlebih dahulu,
kemudian /proc/last_kmsg dan /tmp/recovery.log. Kedua tahap juga mencari file
install-log-*.txt dari direktori installer yang diketahui (maksimum 20 file).
Direktori bisa saling alias dan log dapat berasal dari sesi lama; cocokkan tanggal
dan isi, jangan anggap otomatis log yang benar. Setiap file dibatasi 8 MiB dan
pstore dibatasi 128 nama; data terpotong dilaporkan. Pstore bisa tidak tersedia,
kosong, tidak dapat dibaca, atau tidak menyimpan hang. Sebagian recovery tidak
mendukung exec-out meski ADB tersedia. ADB timeout juga dicatat. Tinjau STATUS.json;
exit sukses hanya berarti adb melaporkan device atau recovery, BUKAN jaminan
log berhasil.
Jika alat gagal, bila tersedia coba secara manual di PC:
  adb pull /sys/fs/pstore pstore-manual
  adb pull /proc/last_kmsg last-kmsg-manual.txt
  adb pull /tmp/recovery.log recovery-manual.log
Jangan me-mount atau mengubah partisi hanya untuk memperoleh log.

PRIVASI: semua log bisa memuat serial, akun, alamat, aplikasi, token atau nama
file. Tidak ada redaksi otomatis. Simpan folder lokal secara privat dan tinjau
sebelum mengirim privat; jangan unggah ke repositori publik. Permission 700/600
dicoba di OS yang mendukung tetapi bukan jaminan privasi, khususnya Windows.
Tidak ada unggahan otomatis. Jangan mengirim password, kunci atau IMEI.
