# Synthetica-Project

Rebuild terpisah untuk joyeuse dari port HyperOS 4 asli diza. Folder ini **bukan** kelanjutan source atau output ROM Rollercoaster. Pada tahap sekarang ini baru fondasi audit, **bukan ROM atau ZIP flashable**. Unggahan ulang pengguna telah diverifikasi sebagai ZIP yang sama dengan referensi publik; delapan entri file ZIP lulus pembacaan CRC, tetapi kompatibilitas dan fungsi perangkat belum semuanya dibuktikan.

## Prinsip

1. Gunakan basis asli yang identitasnya terverifikasi; pisahkan pernyataan pengguna, metadata penyedia dan hash yang kita hitung. Semua fitur dan aplikasi bawaan menjadi prioritas untuk tetap utuh tanpa modifikasi.
2. Pertahankan boot, ramdisk, DTB, DTBO, system, vendor, product dan konfigurasi asli sebagai baseline. Jangan otomatis mengganti kernel dengan Synthetica lama, karena ABI/modul/perangkat dan perbedaan string versi belum selesai diaudit.
3. Jangan ubah layout, fstab, AVB, enkripsi, firmware, instalasi recovery atau integritas otomatis. Tidak ada kredensial, keybox, file pengguna, atau blob ROM di repositori.
4. Setiap perubahan yang diusulkan harus memiliki asal, hash input/output, alasan, dependensi, pengujian host dan rencana rollback. Uji host atau build CI tidak membuktikan boot atau fungsi fisik.
5. Kamera, audio, locale, telephony, KernelSU/Manager dan spoofing dievaluasi terpisah; aplikasi kamera manual dan keberhasilan flash asli dilaporkan pengguna, bukan hasil uji kami.

## Alur yang sudah tersedia

- `research/hyperos4/verify_archive.py`: read-only, ukuran/SHA dan central directory. `--inspect-core` opsional menghitung hash dan memeriksa CRC ZIP hanya pada `boot.img`, `dtbo.img` dan `super.img` setelah hash ZIP cocok. Tidak mengekstrak, menjalankan installer, atau mengakses perangkat.
- `tests/test_hyperos4_preflight.py`: tes host sintetis untuk input, ZIP64, urutan part, CRC, ukuran, mutasi dan path berbahaya. Tidak berisi ROM atau data pengguna.
- `.github/workflows/synthetica-project-baseline.yml`: satu run terpicu hanya bila workflow ini diubah pada branch sesi; mencoba mengunduh ZIP publik ke runner sementara, memverifikasi, lalu menerbitkan **metadata** hasil, bukan image. Ketersediaan sumber belum dijamin.
- `original-baseline.lock.json`: hash ZIP, semua entri, dan empat partisi logis yang dihitung dari ROM asli; file ini hanya metadata.
- `verify_preservation.py`: pemeriksaan read-only ZIP kandidat terhadap lock; hanya ZIP yang identik byte-per-byte keluar dengan status sukses. Repack dengan isi sama, perubahan isi, serta input invalid tidak otomatis diluluskan. Tidak menjalankan installer dan tidak membuktikan fungsi perangkat.
- `tests/test_rom_preservation.py`: uji sintetis untuk deteksi perubahan, repack, CRC rusak, input tidak aman dan mutasi saat pemeriksaan; bukan pengujian ROM di perangkat.
- `research/hyperos4/AUDIT-AWAL-SUPER-VENDOR-2026-11-02.md` dan laporan persiapan build terbaru: status bukti, batas dan rencana.
- `research/hyperos4/lp_metadata.py`: parser LP terbatas yang sudah dites dengan data sintetis dan dipakai untuk audit read-only ROM asli; tes sintetis tersedia di CI, tetapi parser belum terintegrasi ke verifier dan bukan pengganti `lpdump`/liblp.

## Gate berikutnya

1. Verifikasi ZIP lengkap dan kecocokan boot/DTBO dengan berkas yang pengguna berikan. Hitung hash `super.img` dan audit metadata `liblp`, partisi logis, file system dan ukuran sebenarnya.
2. Inventaris sistem/vendor: versi yang benar, VINTF, ABI dan `.ko`, ramdisk/fstab, akses recovery, kamera, audio, radio dan SELinux. Jangan mengasumsikan nilai yang belum diperiksa.
3. Putuskan kernel/Manager berdasarkan source dan konfigurasi aktual, UAPI, identitas sertifikat, DTB dan ABI. Pilihan fitur opt-in dan tidak menyertakan komponen spoofing yang pernah ditolak.
4. Sebelum build yang mengubah komponen, tetapkan daftar perubahan spesifik dan minta persetujuan terinformasi; siapkan proses yang dapat diulang, bandingkan output dengan basis dan sediakan rencana rollback. Salinan ZIP asli yang identik bukan build Synthetica baru.
5. Belum ada recipe build ROM Synthetica di folder ini. Hasil host/CI tidak sama dengan uji perangkat. Uji perangkat, bila diperlukan, memerlukan persetujuan pengguna; tidak perlu mengklaim perangkat stabil hanya karena build selesai.
