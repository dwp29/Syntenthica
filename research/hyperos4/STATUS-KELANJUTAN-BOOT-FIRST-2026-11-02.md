# Status kelanjutan Syntenthica boot-first

**Diperbarui:** 2 November 2026. **Status:** audit host baca-saja; belum ada uji perangkat atau persetujuan flash kandidat.

## Keputusan dan batas pengguna

Pengguna menyatakan recovery dan backup aman dan OrangeFox R12.0_2 beta FBEv2 miatoll pernah berhasil dipakai flash. Keterangan ini diterima; jangan meminta konfirmasi ulang. Keberhasilan sebelumnya bukan uji kandidat baru.

Persetujuan terbatas pada satu file identitas non-eksekusi pada kandidat pertama, tiga pemeriksaan hasil installer pada kandidat kedua yang terpisah, dan pengujian host. Tidak ada persetujuan untuk flash, wipe, format data, pergantian recovery, perubahan firmware/image lain atau pelemahan keamanan. Semua modul Magisk/KSU tetap **hold**; fitur dan optimasi menunggu bukti boot dasar.

## Temuan terkini

- Audit updater terisolasi sebelumnya lulus **17 skenario lokal**, dan [run 41434731862](https://github.com/dwp29/Syntenthica/actions/runs/41434731862) lulus **7 skenario** pada host. Guard berhenti pada kegagalan yang diuji, tetapi tidak memulihkan penulisan sebelumnya atau parsial. Ini bukan OrangeFox, partisi nyata atau bukti boot.
- [Run 41449702558](https://github.com/dwp29/Syntenthica/actions/runs/41449702558) menyelesaikan inventaris VINTF kandidat kedua dengan hash ZIP dan empat extent cocok sebelum/sesudah. Ada **67 XML** pada empat partisi yang dibaca; **37 tes host** lulus. Tidak ada input image diubah atau diunggah.
- Manifest vendor utama bertarget **FCM 4**; matriks framework berlabel yang terlihat adalah **7, 8, 202404, 202504 dan 202604**, tanpa label 4 pada lokasi yang dibaca. Ada matriks tanpa label di system dan product. Ini petunjuk yang memerlukan pemeriksaan formal, **bukan** vonis gagal atau lulus kompatibilitas; pembacaan ODM/APEX/SKU runtime belum lengkap.
- Matriks system tanpa label memuat entri NFC AIDL dan HIDL. Deklarasi NFC HIDL terlihat di vendor; nama/format NFC AIDL tidak ditemukan dalam manifest vendor yang diinventarisasi. Ini bukan bukti NFC atau boot gagal dan bukan pembandingan penuh versi/instance. Lihat [audit VINTF](https://drive.google.com/file/d/1DBQXcWxIPLmgImM99t-MEcXgJ4WoxQLd/view).
- Boot warisan sumber memuat parameter SELinux permissive; analisis init statis menemukan jalur yang dapat memintanya. Ini risiko warisan, bukan perubahan pada kandidat atau bukti status runtime. ZIP tidak memuat vbmeta; AVB eksternal dan penegakannya belum diketahui. [Ringkasan audit AVB/SELinux](https://drive.google.com/file/d/14FqxFcc3wu6TXqeN5k8QMQOaw4Zmirhf/view).
- **Koreksi penyimpanan:** JSON rincian analisis init sempat ada lokal tetapi tidak bertahan saat lingkungan kerja dipulihkan. Provider konektor telah memblokir unggahannya; jangan mengirim ulang atau mengubah kontennya untuk melewati filter. Ringkasan tetap ada di Drive.
- Kandidat hasil repack belum ditandatangani oleh resep; offset metadata OTA masih tidak cocok. `dtbo.img` 24 MiB tidak dipotong; ukuran fisik unit pengguna belum diukur. Batas FAT32 untuk satu file lebih kecil daripada ZIP utuh; tidak ada saran memformat media.

## Artefak dipertahankan

- **Sumber:** ZIP asli SHA-256 `454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63`. Salinan temporary di `/tmp` tidak dijamin bertahan.
- **Kandidat pertama:** 4.713.790.032 byte, SHA-256 `300df7c2a3c0e3125a9d356b381dd97d5bd6e79ef9366ee8dfbdcdec607728b8`; [draf terpisah](https://github.com/dwp29/Syntenthica/releases/tag/untagged-f7309bc26809ec3a0054) memiliki tiga bagian.
- **Kandidat kedua:** 4.713.790.039 byte, SHA-256 `395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372`; [draf terpisah](https://github.com/dwp29/Syntenthica/releases/tag/untagged-7c217f15dd422f58a0f1) memiliki tiga bagian dan dua laporan. [Run 41426885968](https://github.com/dwp29/Syntenthica/actions/runs/41426885968) sebelumnya mengunduh ulang dan memverifikasi lima aset. Run build 41425089108 berstatus **failure** administratif setelah unggah; jangan menyebutnya success.
- Kedua draf belum dipublikasikan dan hanya dapat diakses akun yang berwenang. [Folder laporan Drive](https://drive.google.com/drive/folders/13zpabyxNpb3BagsvYtC9-J8cXNzZoKyu) tidak berisi ZIP utuh. Unggahan Drive kandidat lama yang pernah diperiksa baru enam dari 50 bagian. Jangan mencampur bagian antar-kandidat atau sumber transfer; potongan mentah sendiri bukan ZIP siap flash.

## Lanjutkan dengan aman

Pertahankan sumber, kandidat dan backup. Siapkan pemeriksaan VINTF formal dengan alat yang dapat diaudit, sumber SKU/ODM/APEX yang jelas dan batas evidensi yang eksplisit; lanjutkan audit baca-saja AVB, rollback, enkripsi, recovery dan hambatan boot. Tindakan pada perangkat atau perubahan di luar persetujuan awal memerlukan keputusan dan persetujuan spesifik terpisah.
