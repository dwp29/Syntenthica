# Synthetica 3.2-r1 — revisi berbasis 3.1

> **JANGAN FLASH.** Ini kandidat pengembangan, bukan boot image lengkap atau
> installer recovery. Kompatibilitas dengan ROM Android 17, boot fisik, AVB,
> modul ROM, root/Manager dan perangkat keras belum dibuktikan. Revisi ini
> tidak boleh dianggap sebagai perbaikan pasti untuk gagal boot.

## Apa yang berubah

Kandidat ini dibangun dari resep dan patch **3.1**, bukan eksperimen rollback
2.0 di [halaman lama 3.2](SYNTHETICA-3.2.md). Konfigurasi 3.1 dipertahankan,
termasuk MGLRU yang default aktif, UCLAMP, WALT, KernelSU/SUSFS, SELinux,
seccomp, verifikasi modul dan dm-verity. Perbaikan source jalur Manager dan
seccomp 3.1 juga tetap diterapkan. Keberadaannya di source bukan bukti bahwa
root atau fitur-fitur tersebut bekerja pada perangkat ini.

Patch tambahan kecil pada MGLRU:

1. Nilai sysfs `spread` negatif ditolak; `0` dan nilai valid lain tetap tersedia.
2. Jika thread `kswapd` gagal dibuat, buffer walker MGLRU dibebaskan dan
   penunjuknya dikosongkan. Perilaku fatal `BUG_ON` saat kegagalan awal boot
   tidak dihilangkan.

Keduanya merupakan pengamanan defensif pada kondisi tertentu; belum ada bukti
bahwa keduanya adalah penyebab atau perbaikan kegagalan boot Android 17.
Tidak ada kesimpulan baru tentang penyebab insiden sebelumnya.

Identitas release hasil build adalah
`4.14.357-openela-synthetica-3.2-r1`, berbeda dari eksperimen 3.2 terdahulu.
Jangan mencampur kernel atau modul dari kedua build. Nama release 3.2-r1 juga
berbeda dari 3.1: walaupun seluruh CRC ekspor diperiksa terhadap 3.1, modul
3.1 tidak otomatis cocok atau dipercaya. Kunci penandatanganan modul baru
untuk build baru; kecocokan signer modul ROM dan runtime keyring belum diuji.

## Hasil kompilasi

[Build CI 3.2-r1](https://github.com/dwp29/Syntenthica/actions/runs/42507696077)
**lulus** pada commit `955fa867f2f2a22fda90e51e694e7ea3eddeaa7e` dan
menghasilkan image baru, bukan sekadar mengganti nama 3.1. SHA-256 `Image.gz`:
`e3502ae4e00c729e83efe4997dac3e202f5320be34a440974471cdc6727ec03a`.

- [Unduh arsip bukti kompilasi — JANGAN FLASH](https://drive.google.com/file/d/1Q4hM1ZoWO1vrweYFNuki70NVI4RVEe2X/view?usp=drivesdk)
- [Unduh checksum SHA-256](https://drive.google.com/file/d/100oQXF5n4mNzuUyUfcB5dRKmwb6uhUNN/view?usp=drivesdk)
- Ukuran arsip: **15.997.940 byte**. SHA-256 arsip:
  `c8ad9e1d5848242e2570990dc4350bad065d5a9bc35f38d3f2116b8671d1a38f`.

Arsip hanya memuat image kernel terkompresi, config, simbol, bukti dan enam
modul bertanda tangan dari build yang sama. Tidak ada installer, boot image
lengkap atau private key. File Drive berada di folder diagnostik privat dan
hak aksesnya diperiksa: hanya pemilik. Keberhasilan kompilasi tidak menjamin
bahwa 3.2-r1 dapat boot pada perangkat atau ROM apa pun.

## Pemeriksaan

- Build menggunakan source dan toolchain yang dipin seperti 3.1, serta
  menerapkan seluruh patch 3.1 sebelum patch pengaman tambahan.
- Config hasil build dibandingkan dengan config 3.1 yang dipin; satu-satunya
  perubahan yang diizinkan adalah `LOCALVERSION`. Fitur dan pemeriksaan
  keamanan bawaan 3.1 tetap wajib lulus.
- Seluruh **12.236** rekaman ekspor dibandingkan dengan `Module.symvers` 3.1:
  nama, pemilik, jenis ekspor dan CRC. Ini perbandingan antar-build, bukan
  audit terhadap modul ROM target.
- Enam modul dari build yang sama diperiksa secara statis terhadap config,
  vermagic, CRC dan sertifikat publik yang tertanam di kernel. Ini bukan uji
  pemuatan modul, dan tidak menetapkan kepercayaan terhadap modul ROM.
- Tes host mengompilasi fungsi MGLRU asli yang diekstrak dari source yang
  dipatch untuk memeriksa batas `spread` serta jalur sukses/gagal `kswapd`
  dengan dependensi yang dimock. Tes ini bukan boot atau simulasi Android.

Pembandingan config, seluruh ekspor dan enam modul tersebut lulus di CI build.
Arsip transfer juga diperiksa ulang secara offline menggunakan
`build-kit/scripts/verify_synthetica32_r1_evidence.py`, termasuk integritas ZIP,
config tertanam, identitas Manager dan signature enam modul. Script itu membaca
arsip dan referensi 3.1 secara lokal; ia tidak mengakses atau menulis perangkat.

Untuk mengulang pemeriksaan offline dari checkout repositori, siapkan referensi
3.1 asli dan jalankan:

```sh
gh api -H 'Accept: application/vnd.github.raw+json' \
  repos/dwp29/Syntenthica/git/blobs/0f815b773d39a8f0b392a7d190be9ca1ad702ead > /tmp/s31-evidence.zip
echo '67c804f049c9bb00977c067e06bc663f75a8b7782b4f47bd2626b3fd5a36a847  /tmp/s31-evidence.zip' | sha256sum -c -
unzip -p /tmp/s31-evidence.zip generated.config.txt > /tmp/s31.config
unzip -p /tmp/s31-evidence.zip Module.symvers > /tmp/s31.symvers
python3 build-kit/scripts/verify_synthetica32_r1_evidence.py \
  --evidence /path/to/Synthetica-3.2-r1-DO-NOT-FLASH-Bukti-Kompilasi.zip \
  --config31 /tmp/s31.config --symvers31 /tmp/s31.symvers
```

Ini hanya memverifikasi bukti kompilasi yang dipin, bukan kompatibilitas ROM,
AVB, boot, root, kamera, atau keberhasilan memuat modul pada perangkat nyata.
