SY N T H E T I C A  2.0  -  EKSPERIMEN UJI COBA
Neutron / MGLRU aktif secara default
================================================

INI ZIP FLASHABLE EKSPERIMENTAL, BUKAN RILIS STABIL.
Belum pernah diuji boot pada Joyeuse atau ROM Lunaris 3.13. Risiko bootloop,
hilangnya root/fungsi perangkat, tidak bisa deep sleep, panas, atau gangguan
pengisian daya tetap ada. Kompatibilitas seluruh modul ROM dan kepercayaan AVB
belum terbukti. Tidak ada garansi perangkat akan boot atau Manager akan bekerja.

Sebelum mencoba: pastikan bootloader benar-benar terbuka, recovery dapat diakses,
dan salinan boot yang TEPAT dari perangkat saat ini tersimpan terpisah serta
Anda tahu cara memulihkannya. Jangan gunakan jika tidak siap memulihkan boot.
Tidak ada backup boot otomatis dalam installer ini.

Cara kerja
----------
Dipasang dari custom recovery yang mendukung ZIP AnyKernel3. Installer membaca
boot yang sedang ada, dan hanya setelah pemeriksaan lulus akan mengganti kernel
pada partisi boot. Installer berusaha mempertahankan isi ramdisk, DTB, second,
recovery DTBO dan metadata AVB byte-per-byte; memeriksa ulang hasil repack;
dan membandingkan hasil baca-tulis. Tidak menulis vbmeta, dtbo, vendor, system,
userdata, ksud, ataupun modul. Signature boot lama dapat menjadi tidak valid
karena kernel berubah; installer tidak menonaktifkan verifikasi.

Pengaman membatalkan sebelum menulis bila device bukan joyeuse/miatoll, slot A/B
terdeteksi, bootloader tidak dapat dipastikan terbuka, boot bukan 128 MiB/header
v2/page 4096, DTB berbeda dari referensi Lunaris, ramdisk terdeteksi Magisk atau
tidak didukung, atau ada perbedaan komponen setelah repack. DTB yang cocok tidak
membuktikan ROM yang terpasang atau kompatibilitas modul. Beberapa recovery bisa
tidak menyediakan informasi yang diperlukan; dalam kasus itu pemasangan batal.

Setelah percobaan
-----------------
Tidak ada reboot otomatis. Jika tulisan/readback gagal, JANGAN REBOOT; pulihkan
boot backup yang tepat dari recovery. Jika bootloop, kembali ke recovery dan
pulihkan backup yang sama. Jangan wipe data atau mengubah vbmeta untuk memaksa
boot. KernelSU-Next disertakan pada kernel, tetapi installer tidak memasang atau
mengganti ksud; root dan pairing Manager tidak dijamin.

Image.gz SHA-256:
3a9f39f8f7ea79c9251a896050dfeb60395f1194a064f91a85a8fe8ae38adaea
Toolchain: Neutron clang 24.0.0git. CONFIG_LRU_GEN_ENABLED=y di image hasil build.
