SYNTHETICA LOG COLLECTOR 1.0
Diagnostik Error 1 dan bootloop — BUKAN kernel, BUKAN perbaikan bootloop
======================================================================

Alat ini hanya mengumpulkan log saat dijalankan secara manual. Tidak melakukan
flash kernel, mengubah boot/dtbo/vbmeta/system, mount/decrypt, wipe, reboot atau
upload. Ia menulis folder laporan dan, bila tar/gzip tersedia, arsip .tar.gz
pada penyimpanan yang SUDAH ter-mount dan bisa ditulis, atau /tmp recovery.
Berarti penyimpanan tujuan (misalnya userdata/SD/USB) tetap mengalami penulisan
file laporan. Tool ini tidak menjamin log selalu ada atau recovery kompatibel.

SEBELUM MENCOBA
- Jangan ulangi flash kernel pada perangkat yang belum diketahui kompatibel.
- Jika penulisan boot/readback gagal, JANGAN REBOOT. Gunakan recovery untuk
  memulihkan backup boot yang tepat; dahulukan keselamatan, jangan wipe data.
- 'Error 1' hanya kode gagal umum, bukan penyebab tertentu. Ambil foto SEMUA
  pesan error, versi/jenis recovery, versi ROM/Android, nama model dan codename,
  serta nama dan SHA-256 ZIP kernel yang sebenarnya dicoba.
- Data log mentah dapat memuat serial, alamat jaringan, akun, nama aplikasi,
  atau path/nama file. Tinjau dulu dan kirim secara PRIBADI kepada pihak yang
  dipercaya. Alat tidak menjamin redaksi; jangan unggah ke publik.

SETELAH ERROR 1 DI CUSTOM RECOVERY
1. Tetap di recovery. Sebelum menjalankan ZIP lain, jika tersedia pilih menu
   recovery 'Copy Log'/'Save Log'. Atau, dari komputer yang memiliki adb dan
   terhubung ke recovery:
       adb devices
       adb pull /tmp/recovery.log recovery-sebelum-collector.log
   Recovery berbeda bisa memakai nama/menu lain atau tidak menyediakan adb.
   Simpan/foto log sekarang: menjalankan ZIP kedua dapat menambah atau mengganti
   recovery.log/last_install sehingga error asli mungkin hilang.
2. Pilih Install dan jalankan Synthetica-Log-Collector-1.0.zip. Ini ZIP
   diagnostik yang menulis laporan, bukan ZIP kernel atau modul; jangan gunakan
   installer modul di Manager. Tidak ada reboot otomatis.
   ZIP ini tidak ditandatangani sebagai OTA: stock recovery atau verifikasi
   signature recovery dapat menolaknya. Jangan mematikan verifikasi demi tool ini;
   gunakan Copy Log atau metode adb di bawah jika tersedia.
3. Catat lokasi 'Archive:' atau 'Report folder:' yang ditampilkan. Ambil arsip
   .tar.gz; jika tidak ada, ambil seluruh folder laporan. Laporan disimpan di
   Synthetica-logs pada storage yang sudah mounted/decrypted, jika tersedia.
4. Jika tertulis TEMPORARY /tmp, salin SEBELUM reboot, misalnya:
       adb pull /tmp/Synthetica-logs ./Synthetica-logs
   /tmp hilang saat recovery reboot. Jika adb tidak bisa membaca, gunakan fitur
   file manager/Copy Log recovery atau penyimpanan eksternal yang dimount sendiri.
   Jangan mengandalkan /tmp untuk menyimpan backup boot.

SETELAH BOOTLOOP
Masuk ke recovery secepat mungkin, hindari reboot berulang; catatan pstore/
last_kmsg bisa tidak ada atau tertimpa. Ikuti langkah 1-4 di atas bila aman,
lalu pulihkan backup boot yang TEPAT untuk perangkat/slot/ROM tersebut melalui
prosedur recovery yang sudah diketahui. Jangan wipe data atau ubah vbmeta untuk
memaksa kernel boot. Jika tidak ada backup yang cocok, berhenti dan cari bantuan
pemulihan khusus perangkat, jangan menebak image/slot.

ALTERNATIF ADB TANPA INSTALL ZIP (bila shell recovery tersedia)
Ekstrak collector.sh dari ZIP ini pada komputer lalu jalankan:
    adb push collector.sh /tmp/synthetica-collector.sh
    adb shell sh /tmp/synthetica-collector.sh
Baca lokasi yang dicetak. Jika /tmp, gunakan perintah adb pull di atas sebelum
reboot. Beberapa recovery memblokir shell, tidak memberi izin membaca log, atau
tidak mengaktifkan adb; hasilnya akan tidak lengkap atau tidak bisa berjalan.

ISI LAPORAN
- 01-recovery-current.log dan 04/05-recovery-last.log: log recovery mentah.
- 03-anykernel-prepare.log dan installer-log-*.txt: jika masih tersedia.
- 09-proc-last-kmsg.log, 07-last-kmsg-cache.log dan pstore-*.log: rekaman boot
  sebelumnya bila recovery/kernel menyediakannya; bisa kosong/tidak ada.
- 10-dmesg-recovery.log dan 11-logcat-recovery.log: sesi recovery SEKARANG,
  bukan otomatis log Android yang bootloop; dapat kosong/timeout.
- 12-recovery-context.txt: properti recovery terpilih dan argumen boot terbatas;
  versi Android recovery bisa berbeda dari Android ROM.
- 13-mounted-rom-properties.txt: properti ROM terbatas hanya jika sistem sudah
  ter-mount; bisa berasal dari slot berbeda atau tidak tersedia.
- 14-partition-layout.txt: nama partisi relevan, ukuran/status dan sebagian
  angka header boot jika bisa dibaca. Tidak ada image boot/ramdisk disalin.
- 15-error-lines.txt: potongan kandidat error, bukan kesimpulan penyebab.
- STATUS.tsv: OK, EMPTY, MISSING, UNREADABLE, READ_ERROR, WRITE_ERROR,
  LIMIT_REACHED, TIMED_OUT atau status skip. Log dibatasi; LIMIT_REACHED mungkin
  terpotong.

BATASAN KOMPATIBILITAS
Synthetica 3.0 yang saat ini tersedia memiliki pemeriksaan khusus joyeuse/
miatoll, boot tanpa slot A/B, ukuran/format boot, DTB referensi dan ramdisk.
Android versi lain saja tidak cukup untuk menyimpulkan kompatibilitas. Jangan
menghapus pemeriksaan atau memaksa pemasangan berdasarkan collector ini.
