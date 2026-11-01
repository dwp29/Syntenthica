# Synthetica-Project

Rebuild terpisah untuk joyeuse dari port HyperOS 4 asli diza. Folder ini **bukan** kelanjutan source atau output ROM Rollercoaster. Pada tahap sekarang ini baru fondasi audit, **bukan ROM atau ZIP flashable**.

## Prinsip

1. Gunakan basis asli yang identitasnya terverifikasi; pisahkan pernyataan pengguna, metadata penyedia dan hash yang kita hitung.
2. Pertahankan boot, ramdisk, DTB dan DTBO asli sebagai baseline. Jangan otomatis mengganti kernel dengan Synthetica lama, karena ABI/modul/perangkat dan perbedaan string versi belum selesai diaudit.
3. Jangan ubah layout, fstab, AVB, enkripsi, firmware, instalasi recovery atau integritas otomatis. Tidak ada kredensial, keybox, file pengguna, atau blob ROM di repositori.
4. Setiap perubahan yang diusulkan harus memiliki asal, hash input/output, alasan, dependensi, pengujian host dan rencana rollback. Uji host atau build CI tidak membuktikan boot atau fungsi fisik.
5. Kamera, audio, locale, telephony, KernelSU/Manager dan spoofing dievaluasi terpisah; aplikasi kamera manual dan keberhasilan flash asli dilaporkan pengguna, bukan hasil uji kami.

## Alur yang sudah tersedia

- `research/hyperos4/verify_archive.py`: read-only, ukuran/SHA dan central directory. `--inspect-core` opsional menghitung hash dan memeriksa CRC ZIP hanya pada `boot.img`, `dtbo.img` dan `super.img` setelah hash ZIP cocok. Tidak mengekstrak, menjalankan installer, atau mengakses perangkat.
- `tests/test_hyperos4_preflight.py`: tes host sintetis untuk input, ZIP64, urutan part, CRC, ukuran, mutasi dan path berbahaya. Tidak berisi ROM atau data pengguna.
- `.github/workflows/synthetica-project-baseline.yml`: satu run terpicu hanya bila workflow ini diubah pada branch sesi; mencoba mengunduh ZIP publik ke runner sementara, memverifikasi, lalu menerbitkan **metadata** hasil, bukan image. Ketersediaan sumber belum dijamin.
- `research/hyperos4/STATUS-DATA-AWAL-2026-11-02.md` dan `LAPORAN-RISET-HYPEROS4-JOYEUSE.md`: status bukti, batas dan rencana.

## Gate berikutnya

1. Verifikasi ZIP lengkap dan kecocokan boot/DTBO dengan berkas yang pengguna berikan. Hitung hash `super.img` dan audit metadata `liblp`, partisi logis, file system dan ukuran sebenarnya.
2. Inventaris sistem/vendor: versi yang benar, VINTF, ABI dan `.ko`, ramdisk/fstab, akses recovery, kamera, audio, radio dan SELinux. Jangan mengasumsikan nilai yang belum diperiksa.
3. Putuskan kernel/Manager berdasarkan source dan konfigurasi aktual, UAPI, identitas sertifikat, DTB dan ABI. Pilihan fitur opt-in dan tidak menyertakan komponen spoofing yang pernah ditolak.
4. Hanya sesudah gate di atas, bangun perubahan minimal yang dapat diulang, bandingkan output dengan basis dan siapkan verifikasi/rollback. Uji perangkat memerlukan persetujuan pengguna dan dibedakan dari uji host.
