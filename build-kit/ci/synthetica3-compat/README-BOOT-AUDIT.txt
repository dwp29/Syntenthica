SY N T H E T I C A — BOOT AUDIT 1.0 (HANYA MEMBACA)

Ini BUKAN kernel dan TIDAK memasang atau menulis partisi. Tujuannya menampilkan
identitas bagian DTB pada boot yang sedang terpasang, agar penolakan installer
3.0 dapat diselidiki. ZIP ini unsigned dan belum diuji pada recovery/perangkat
fisik; recovery bawaan atau pemeriksaan tanda tangan dapat menolaknya.

Cara memakai:
1. Cocokkan SHA-256 ZIP dengan file checksum pendamping. Siapkan backup boot
   yang tepat dan recovery yang dapat dipakai; audit ini bukan pengganti backup.
2. Di TWRP/OrangeFox pilih Install dan pilih ZIP Boot Audit (BUKAN ZIP kernel).
   Audit membaca boot tanpa slot, tetapi tidak mengubahnya. Tidak ada reboot
   otomatis dan tidak ada akses internet dari skrip ini.
3. Foto atau salin kedua baris `DTB SHA256 1/2` dan `DTB SHA256 2/2`,
   `Boot header`, ukuran boot serta pesan hasil/STOPPED. Sertakan codename,
   nama dan tanggal build ROM. Jika Error 1 lain terjadi, kirim juga pesan
   persis dan recovery log sesegera mungkin: audit ini dapat mengganti log
   recovery sebelumnya. Jangan kirim IMEI, nomor seri, akun, atau kunci.
4. Jika audit berhenti karena slot, ukuran, header, kemampuan BusyBox, atau
   pembacaan, kirim pesan STOPPED; jangan mengakalinya atau mengubah slot.

Audit hanya mendukung header boot v2, page 4096, header 1660, dan DTB terpisah.
Ia menghitung SHA-256 dari seluruh bagian DTB yang panjangnya tercantum pada
header; tidak memeriksa validitas struktur FDT atau kompatibilitas hardware.
MATCH/DIFFERENT hanya perbandingan dengan satu referensi installer lama. Bahkan
MATCH tidak membuktikan kernel akan boot, signature AVB valid, modul ROM cocok,
atau aman untuk flash. DIFFERENT tidak otomatis berarti DTB rusak/tidak cocok.

Properti yang tampil berasal dari recovery dan dapat berbeda dari ROM yang
terpasang. Audit tidak menyimpan full boot atau ramdisk. Sebagian DTB disalin
sementara ke direktori privat /tmp untuk cek panjang dan hash, lalu dihapus
saat skrip selesai; jika proses terhenti mendadak, file sementara dapat tetap
ada sampai dibersihkan/recovery direstart. Tidak ada laporan yang diunggah;
hasil layar dapat ikut tercatat dalam log recovery. Periksa isi log sebelum
membagikannya. Tidak ada mount otomatis, pengubahan vbmeta, atau wipe data.
