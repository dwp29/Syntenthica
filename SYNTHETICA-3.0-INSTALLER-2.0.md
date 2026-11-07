# Synthetica 3.0 — installer 2.0 (kandidat uji)

## Unduh

- [ZIP Synthetica-3.0-Installer-2.0-TEST](https://drive.google.com/file/d/1ajXzVFVyYl32_Uu8IoPFKi7GesFjV3B-/view?usp=drivesdk)
- [Berkas SHA-256](https://drive.google.com/file/d/1Eul3qoWeyE4BYomFS0sR3jt0I0qt-Z7a/view?usp=drivesdk)
- Ukuran: 21.529.406 byte. SHA-256 ZIP:
  `1c41c6d71ea4c0e52692b71512b3c79b580977ed8a8d67cc2b00a1670b689136`

## Apa yang dibuat

Paket ini memakai **Image.gz 3.0 yang sudah dikompilasi sebelumnya** (SHA-256
`92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb`) dan
installer dari ZIP rilis 2.0 (SHA-256
`b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c`).
Kernel tidak dikompilasi ulang. Installer, backend, alat dan `ksud` tetap dari
2.0; perubahan skrip hanya pada label versi dan uname. Dokumen di dalam paket
diperbarui agar menyebut isi dan risikonya dengan benar.

Paket mengenali properti `miatoll`, `curtana`, `excalibur`, `gram` dan
`joyeuse`, seperti 2.0. Paket tidak membawa DTB, DTBO atau `.ko`. Tidak ada
pemeriksaan hash DTB, slot/unlock, ramdisk dan readback pascatulis setara
installer 3.0 asli. `IS_SLOT_DEVICE=0` bukan bukti perangkat tidak memiliki
slot. Tidak ada perubahan kernel yang menjamin modul ROM atau memperbaiki
kamera 0.6x.

## Pengujian dan batasnya

[Build dan tes CI](https://github.com/dwp29/Syntenthica/actions/runs/42394590026)
lulus dan menghasilkan SHA-256 ZIP yang sama seperti file di Drive. Tes paket
memeriksa hash input, isi, mode, CRC dan identitas lima device; tes ARM/QEMU
menjalankan entry dan core AnyKernel pada **boot sintetis dengan path dan
operasi sistem di-mock**, termasuk dua DTB sintetis berbeda dan kondisi `/data`
tersedia/terkunci. Ini bukan uji update-binary di recovery fisik dan bukan
bukti boot, root, kepercayaan AVB, atau kompatibilitas modul/ROM.

## Sebelum mencoba

Pastikan bootloader terbuka, perangkat/ROM/slot sesuai, recovery dapat dipakai,
dan simpan backup **boot yang tepat** beserta cara restore. Installer tidak
membuat backup otomatis. Backup juga `/data/adb/ksud` yang sudah ada jika
perlu: sama seperti 2.0, installer dapat menggantinya **sebelum** menulis boot,
bahkan jika proses boot kemudian gagal. Jika data terkunci, instalasi `ksud`
dilewati. AnyKernel dapat mem-patch DTB/AVB pada kondisi tertentu seperti
Magisk; validitas signature belum diverifikasi. Jangan wipe data atau ubah
vbmeta untuk memaksa boot. Bila gagal saat menulis, jangan reboot sebelum
memulihkan boot yang tepat melalui recovery.

Builder: `build-kit/scripts/package_synthetica3_installer20.py`. ZIP sumber 3.0
asli dan 2.0 diperiksa hash-nya sebelum dikemas; tidak ada skrip installer yang
dijalankan pada ponsel oleh builder.
