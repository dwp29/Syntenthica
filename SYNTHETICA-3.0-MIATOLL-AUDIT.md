# Audit kompatibilitas Synthetica 3.0 — miatoll

**Status: diagnosis dan kandidat pengembangan; bukan perbaikan bootloop yang
sudah terbukti dan bukan izin untuk flash kandidat pengembangan.** Kernel ZIP
3.0 dan semua gerbang pemeriksaan boot yang substantif belum diubah. Hash DTB
baru belum disetujui. Asisten tidak melakukan flashing atau pengujian langsung
pada perangkat fisik. Pengguna menunjukkan screenshot perangkat yang sudah masuk
Android dan menampilkan banner yang cocok dengan build 3.0; identitas byte image
terpasang dan kompatibilitas ROM lain belum diverifikasi secara independen.

## Yang diketahui dan yang belum

- Dua arsip log yang diperiksa sebelumnya adalah sesi yang sama, bukan dua
  pengujian terpisah. Pada joyeuse/Lunaris 3.13 Android 16, installer 3.0
  menampilkan `boot DTB is not the known Lunaris 3.13 reference` lalu
  `The boot partition was not written`. Ini penolakan sebelum penulisan,
  **bukan** bukti penyebab bootloop. Hash DTB aktual belum terekam.
- Perangkat kedua dilaporkan joyeuse dengan Infinity Project 4.1 Android 17 dan
  mengalami Error 1 saat instalasi. Pesan lengkap, tanggal build, log recovery
  dan hash DTB aktual belum tersedia. Jangan menganggap penyebabnya sama.
- Codename fisik keluarga miatoll mencakup `joyeuse`, `curtana`, `excalibur`
  dan `gram`; `miatoll` juga dapat menjadi properti ROM/recovery yang terpadu.
  Nama atau properti saja tidak membuktikan hardware, ROM, DTB, atau ABI aman.
- Paket lama tidak menetapkan batas versi Android 16/17. Itu bukan bukti bahwa
  kernel cocok dengan semua Android 16 atau 17.

## Laporan boot menggunakan installer kernel lain

Pengguna melaporkan ada joyeuse/Lunaris 3.13 yang berhasil boot setelah
`Image.gz` Synthetica 3.0 dipindah ke ZIP kernel lain. Screenshot menunjukkan
Android 16 GMS-Community sudah berjalan pada joyeuse dan menampilkan banner
`4.14.357-openela-synthetica-3.0`, Neutron 24, serta waktu build
`Sat Nov 07 08:09:14 UTC 2026`. Banner lengkap tersebut cocok dengan banner
tertanam pada `Image.gz` ZIP 3.0 yang dipin. Screenshot lain menunjukkan
`Image.gz` ada di ZIP 3.0 asal; screenshot tidak memperlihatkan hasil edit
ZIP lain, langkah flashing, hash image yang terpasang, atau nomor versi ROM
Lunaris. Versi ROM dan cara pemasangan adalah laporan pengguna.

Ini bukti positif bahwa kombinasi yang ditunjukkan dapat masuk Android dengan
kernel yang melaporkan banner build 3.0; bukan pembuktian hash image yang
terpasang, stabilitas, semua fitur atau kompatibilitas setiap miatoll/ROM.
Pengguna menyatakan perangkat tersebut **berbeda** dari perangkat pada log
penolakan DTB. Pengguna juga melaporkan empat pengguna mengalami Error 1, satu
berhasil boot, dan satu lagi berhasil dengan memindah image; rincian instalasi
keberhasilan pertama serta log keempat kegagalan belum tersedia. Angka ini
adalah laporan pengguna, bukan hasil verifikasi independen, dan Error 1 tidak
membuktikan seluruh kegagalan terjadi pada guard yang sama.

Kernel wadah yang ditunjuk adalah
[Not-Kinesis-KSU-Miatoll-20261030-1718.zip](https://t.me/whisperersdump/778?single).
Posting tersebut mencantumkan ukuran 16,9 MB dan SHA-1
`ec8cc69400fd1f922e261b73e72d666e021912ba`. Ini metadata penerbit, bukan
verifikasi lokal atau bukti autentisitas. Hingga pencatatan ini isi ZIP Telegram
belum diperoleh/diperiksa; jangan menganggap ZIP lain atau source mirip sebagai
identik dengan paket tersebut.

Jika memakai installer lain, guard DTB di installer Synthetica tidak otomatis
ikut dipakai; tanpa ZIP dan log installer lain kita belum tahu apakah
DTB/DTBO, ramdisk, AVB, modul, atau partisi lain dipertahankan atau diubah.
Jangan menyimpulkan bahwa DTB sebelum dan sesudahnya identik atau meniru
pemindahan image untuk perangkat lain sebagai solusi universal.

Untuk investigasi baca-saja, minta ZIP asli dari posting tersebut dan, bila
ada, ZIP hasil modifikasi serta pesan/log recovery dari pengguna yang gagal.
Periksa ZIP sebagai input tidak tepercaya tanpa menjalankan skripnya. Hash
DTB saat ini dan data sebelum perubahan, bila tersedia, membantu tetapi hash
semata tidak membuktikan kompatibilitas/kepercayaan AVB.

## Error 1: klasifikasi berdasarkan pesan, bukan tebakan

| Tahap | Contoh yang dapat menyebabkan kegagalan | Penulisan boot |
|---|---|---|
| Sebelum skrip berjalan | ZIP tidak utuh, format update-binary, pemeriksaan signature recovery, BusyBox tidak dapat dieksekusi | Skrip belum menulis boot; pastikan dari log yang sesuai |
| Pengenalan/lingkungan | properti device tidak cocok/tidak tersedia, indikasi slot, bootloader terkunci/tidak diketahui, partisi boot tidak ada, ukuran berbeda, read-only, ruang `/tmp` tidak cukup | Guard membatalkan sebelum penulisan |
| Pemeriksaan boot | header bukan v2/page 4096/header 1660, AVB footer/metadata hilang atau tak didukung, DTB berbeda, ramdisk Magisk/tidak terbaca, gzip/hash kernel salah | Prepare membatalkan sebelum penulisan |
| Repack | komponen non-kernel berubah, header/metadata AVB berbeda, output atau partisi berubah saat persiapan | Guard membatalkan sebelum penulisan |
| Write/readback | penulisan gagal atau bytes hasil berbeda | **Boot mungkin sudah berubah**; jangan reboot, pulihkan backup boot yang tepat dari recovery |

Daftar tersebut adalah kemungkinan jalur kode, bukan klaim bahwa semuanya
terjadi pada Infinity. Sebelum menjalankan ZIP lain, simpan dulu `/tmp/recovery.log`
atau log yang ditawarkan recovery untuk sesi Infinity: recovery dapat menimpa
log instalasi sebelumnya. Jika ADB recovery tersedia, contoh baca-saja:

```
adb pull /tmp/recovery.log recovery-infinity-sesudah-error.log
```

Tinjau/redaksi akun, nomor seri, IMEI, path privat dan identitas lain sebelum
membagikan log. Jika sudah tertimpa, laporkan itu; jangan memaksa flashing ulang
hanya untuk menghasilkan log.

## Risiko bootloop/fitur hilang setelah write berhasil

1. **AVB:** metadata yang sama byte-for-byte tidak membuktikan hash/signature
   boot baru valid setelah kernel diganti. Status bootloader/recovery juga tidak
   membuktikan perilaku trust semua perangkat. Tidak ada perubahan `vbmeta`,
   penonaktifan verity, atau pemaksaan boot dalam kandidat.
2. **Modul vendor:** image 3.0 yang dipin berisi `CONFIG_MODVERSIONS=y`,
   `CONFIG_MODULE_SIG=y` dan `CONFIG_MODULE_SIG_FORCE=y`. Evidence build tersebut
   mencatat CRC `module_layout` `0xed5659d1` dan sertifikat modul publik SHA-256
   `fccecddc68e8828ff42c59be08f3aca01baf1f07e9caf8369ce69e8fad4bd062`.
   ZIP installer tidak memuat `.ko`; modul dari build lain/ROM belum tentu lolos
   vermagic, CRC, dependency, signature/keyring atau urutan loading. Kegagalan
   modul penting dapat memengaruhi boot atau fitur; tidak ada bukti bahwa ini
   penyebab laporan pengguna. Jangan menonaktifkan pemeriksaan signature/ABI.
3. **DTB/DTBO, driver dan vendor userspace:** hash DTB saja tidak menjamin
   kecocokan DTBO, driver sensor, kamera, storage, modem, init, SELinux atau
   setiap varian fisik. Tidak ada image DTBO yang dipasang oleh kandidat.
4. **Ramdisk/root:** ramdisk Magisk atau format yang tidak didukung sengaja
   ditolak; KernelSU Manager/root dan modul userspace belum terbukti pada ROM
   Infinity. Jangan menumpuk penyedia root/patch tanpa analisis.
5. **Regresi runtime:** MGLRU, Uclamp, suspend/charging, thermal, kamera dan
   perbedaan userspace tetap memerlukan uji nyata. Risiko itu bukan diagnosis
   tanpa log boot/crash yang relevan. Log recovery saat ini bukan log panic
   kernel setelah bootloop.

Bila write/readback gagal atau bootloop, kembali ke recovery dan pulihkan
**backup boot yang berasal dari perangkat dan kondisi ROM yang tepat**. Jangan
wipe data, mengganti slot, mengubah `vbmeta`, atau mem-flash image acak.

## Perubahan kode yang disiapkan

`build-kit/scripts/package_synthetica3_compat.py` hanya menerima ZIP asal
SHA-256 `16b32f57381005c08cbee0ec684397dc91acc77f5b2ccbb4ef7f4b99a9a791e6`,
lalu membuat dua artefak terpisah:

- **Boot Audit** tidak berisi kernel/installer flash. Ia hanya membaca partisi
  boot unslotted dan menghitung hash seluruh bagian DTB v2 yang dibatasi header,
  menampilkan dua bagian hash pada layar, serta menghapus salinan DTB sementara
  di `/tmp`. Tidak memasang partisi atau mengunggah data. Jika terhenti mendadak,
  file sementara dapat tersisa sampai dibersihkan/recovery direstart. ZIP
  unsigned ini belum diuji pada recovery fisik. Audit bukan pemeriksaan FDT,
  validitas AVB, modul, atau keselamatan boot. Simpan log kegagalan sebelumnya
  sebelum menjalankan audit.
- **3.0 Compat development candidate — JANGAN FLASH.** Pengakuan nama menambah
  empat codename fisik dan mempertahankan `miatoll`; petunjuk A/B dicek juga
  dari properti slot kedua, `ro.build.ab_update`, command line dan nama boot
  berslot yang lazim. Hasil kosong tetap bukan bukti universal bahwa device
  tidak berslot. Pada penolakan DTB, hash aktual ditampilkan tanpa menyetujuinya.
  `setup_env`/`restore_env` AnyKernel tidak dijalankan: backend lama dapat
  mencoba me-mount partisi lewat fstab dengan flag default (tidak membuktikan
  ada data yang tertulis). Kandidat memakai properti recovery yang sudah ada;
  jika tidak tersedia, identifikasi bisa gagal aman.

Image.gz, MagiskBoot, BusyBox dan `prepare-boot.sh` kandidat identik dengan ZIP
3.0 asal. **Satu-satunya hash DTB yang diterima tetap**
`6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239`.
Dengan demikian penolakan Lunaris yang dilaporkan belum teratasi; hash berbeda
bukan bukti bahwa kernel akan atau tidak akan boot. Tidak ada dukungan ROM
baru yang diumumkan. Backup otomatis belum ada.

## Validasi sintetis dan identitas artefak

- [Actions 42389526170](https://github.com/dwp29/Syntenthica/actions/runs/42389526170)
  berhasil menjalankan pengujian host, jalur ekstraksi ZIP, BusyBox dan MagiskBoot
  ARM melalui QEMU, guard repack, serta dua pengujian boot sintetis berbasis loop.
  Hash DTB audit
  cocok dengan keluaran MagiskBoot untuk fixture tunggal dan gabungan; penolakan
  DTB berbeda pada loop tidak mengubah boot fixture. Jalur tulis positif diuji
  hanya setelah hash fixture sintetis dimasukkan ke salinan sementara skrip.
- ZIP Boot Audit yang identik dengan CI berukuran 867.544 byte dan SHA-256
  `50ce02a4789b8fb760fc2bfac681e5486b8b411be8949c57026e69958a1a00a3`.
  Tidak ada kernel di dalamnya. Kandidat pengembangan tetap tidak boleh di-flash.
- Uji host keseluruhan menjalankan 268 tes dengan 38 dilewati saat tool/env
  opsional tidak tersedia. Pengujian sintetis/loop bukan uji recovery atau boot
  perangkat, dan tidak menguji ABI, kepercayaan AVB, root atau ROM aktual.

## Audit modul offline

`build-kit/scripts/audit_synthetica3_compat_modules.py` dapat membandingkan
salinan privat `.ko` ROM yang sudah diekstrak terhadap image, `Module.symvers`,
`System.map`, konfigurasi dan sertifikat publik **build 3.0 yang tepat**.
Status/evidence terikat ke hash ZIP asal, input hanya dibaca, laporan baru
harus di luar repositori/input dan dibuat mode `0600`; tidak ada modul dimuat.
File terkompresi dan symlink dilaporkan dilewati. Jangan commit/unggah ROM,
modul, laporan privat atau informasi perangkat mentah ke CI.

Contoh pengembang jika evidence dan salinan privat memang tersedia:

```
python3 build-kit/scripts/audit_synthetica3_compat_modules.py \
  --modules /tmp/audit-privat/modul-rom \
  --original /path/privat/synthetica-3.0.zip \
  --evidence /path/privat/evidence-3.0 \
  --report /tmp/laporan-modul-3.0.json
```

Output membandingkan vermagic, CRC record, simbol, dan signature terhadap
sertifikat build; ia tidak membuktikan module keyring runtime, apakah file
tersebut dimuat, identitas ROM terpasang, atau bootabilitas.

## Gerbang berikutnya

1. Simpan dan kirim pesan/log recovery Infinity yang tepat, nama serta tanggal
   build ROM. Simpan log Lunaris jika ada sesi kegagalan berbeda.
2. Jalankan hanya Boot Audit setelah log disimpan; kirim dua baris hash untuk
   **masing-masing perangkat** beserta pesan hasil/header/ukuran. Jika format
   tidak didukung, kirim alasan STOPPED, jangan memaksa.
3. Bandingkan DTB/DTBO, build ROM, ramdisk dan modul secara offline; identifikasi
   backup boot dan kebijakan AVB yang benar. Hash baru tidak otomatis diizinkan.
4. Baru susun kandidat per konfigurasi yang buktinya memadai; tetap butuh tes
   recovery/perangkat, root, jaringan, kamera, suspend dan beban. Tidak ada
   jaminan boot atau kompatibilitas universal.
