# Status awal — Synthetica-Project / HyperOS 4 joyeuse

**Tanggal:** 2 November 2026 (WIB)

**Tahap:** audit sumber asli dan persiapan rebuild; belum ada ROM baru, flash, format, atau uji perangkat.

## Keputusan proyek

Synthetica-Project dimulai ulang dari port HyperOS asli diza untuk joyeuse, **bukan** meneruskan output Rollercoaster. Pengguna mengonfirmasi bahwa `Hos4.0.zip` berasal dari port asli tersebut. Ini konfirmasi asal oleh pengguna, belum perbandingan kriptografis terhadap ZIP lengkap. Kernel dan Manager Synthetica lama boleh menjadi sumber fitur, tetapi tidak akan ditukar atau dibundel otomatis sebelum kompatibilitas terbukti.

## Yang tersedia dan belum tersedia

- `Hos4.0.zip` di folder ini: 20.165.720 byte; SHA-256 lokal sama dengan Drive, `9ec126b8081abc9ce19d494e8617eed8a6f0367c013506c2d92c0fadf2d68245`.
- ZIP itu memuat `META-INF`, `boot.img` dan `dtbo.img`, semuanya di bawah folder `Hos4.0/`; **tidak ada `super.img`**, dan susunan tersebut bukan ZIP recovery lengkap yang siap dipasang.
- Boot: 134.217.728 byte, SHA-256 `57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d`. DTBO: 25.165.824 byte, SHA-256 `9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2`. CRC kedua image cocok dengan ZIP saat dibaca. Hash tidak membuktikan bootability atau keaslian penulis.
- ZIP lengkap yang dirujuk publik: metadata menyebut 4.512.854.711 byte dan SHA-256 `454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63`. Ini **metadata penyedia**, belum hash file yang kami hitung. `super.img`, sistem, vendor, kamera, audio, VINTF dan modul belum tersedia untuk pemeriksaan lokal.

## Temuan teknis penting

1. Kernel asli melaporkan banner `5.15.245-Nezuko_Kimochii`, **tetapi** image yang sama mengandung string internal `4.14.369-Nezuko-Ganteng`. Salah satu kandidat source Nezuko juga menyatakan 4.14.369; ini indikasi yang perlu dicocokkan, bukan bukti commit atau versi dasar secara pasti. Synthetica lama melaporkan `4.14.357`; jangan menentukan perbedaan mayor hanya dari banner atau langsung mengganti kernel.
2. IKCONFIG image identik dengan `stock_defconfig` pada kandidat source, tetapi source kandidat secara eksplisit memasukkan file stock itu sebagai IKCONFIG. Karena itu IKCONFIG **bukan bukti konfigurasi build efektif** dan kecocokan byte tidak membuktikan asal commit. ABI, `.ko`, device tree, tanda tangan modul dan konfigurasi build tetap harus diperiksa.
3. Ada string terkait KernelSU dan pemilihan manager di kernel asli. Versi UAPI, sertifikat yang diterima, status runtime dan kecocokan Manager Synthetica 2.1.2 belum terbukti.
4. Ramdisk mencantumkan logical ext4 pada `system`, `system_ext`, `product`, `vendor` dan F2FS `/data`; pengaturan ini saja tidak membuktikan kompatibilitas FBE/dekripsi recovery. Cmdline mencantumkan `androidboot.selinux=permissive`; status SELinux aktual belum diuji.
5. Empat entri FDT pada DTBO memiliki batas yang terbaca; ini belum membuktikan pilihan device-tree oleh perangkat. Installer mengizinkan `joyeuse` dan mendeklarasikan penulisan `super`, `boot`, `dtbo`; script maupun binary-nya tidak dijalankan.
6. Metadata OTA menyebut SDK 35 dan fingerprint Android 12 yang saling tidak konsisten dan juga berbeda dengan target Android 17 dalam proyek referensi. Versi ROM sebenarnya perlu diperiksa dari sistem/framework; jangan menganggap metadata itu bukti final.

## Rencana aman dan status

- Pertahankan `boot.img` dan `dtbo.img` asli sebagai baseline; tetapkan manifest asal, perubahan bertahap dan rollback sebelum mengubah apa pun.
- Pemeriksaan runner GitHub disiapkan untuk mencoba mengambil ZIP publik lengkap, memverifikasi ukuran/hash, lalu mengalirkan tiga image untuk hash/CRC tanpa menjalankan installer. Hanya metadata diagnostik yang boleh disimpan; image ROM tidak di-commit atau diunggah sebagai artefak. Hasil runner belum boleh dianggap sukses sampai run selesai.
- Setelah `super.img` tersedia, audit metadata dynamic partition, sistem/vendor, ABI modul, SELinux, kamera, audio, telephony dan dependensi; baru tentukan adaptasi kernel dan Manager. Tidak ada jaminan kompatibilitas atau keberhasilan fisik tanpa pengujian.
- Pengguna pernah berhasil memasang port yang sama dengan OrangeFox R12.0_2 FBEv2, serta melaporkan build Rollercoaster lain masuk fastboot setelah flash. Kedua pengalaman dihormati; penyebab fastboot dan identitas persis artefak yang gagal belum terbukti. Tidak ada permintaan untuk mengulang flash atau mengganti recovery.
- Pengguna menyampaikan GCam/Leica/MIUI Camera dapat dipasang manual oleh banyak orang; pilihan versi dan semua fungsi masih memerlukan verifikasi.

Riset rinci tersimpan pada `LAPORAN-RISET-HYPEROS4-JOYEUSE.md`. Tidak ada data pribadi, keybox, image ROM atau kredensial yang dibutuhkan dalam laporan.
