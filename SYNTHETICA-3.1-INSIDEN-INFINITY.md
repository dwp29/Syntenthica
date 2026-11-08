# Laporan gagal boot — Synthetica 3.1 / Project Infinity 4.1

## Status

Menurut pelapor, perangkat **joyeuse** dengan Project Infinity 4.1 / Android 17 tertahan di **logo Redmi/Mi, sebelum animasi ROM**, setelah installer Synthetica 3.1 melaporkan selesai. Sistem sebelumnya memakai KernelSU/KernelSU Next; versi dan kondisi root setelah pemulihan belum diketahui. Perangkat dilaporkan **sudah dapat boot kembali**, dan ada cadangan boot yang menurut pelapor cocok untuk perangkat/ROM. Belum diketahui apakah cadangan itu digunakan untuk pemulihan. Identitas file, hasil dan kondisi perangkat ini belum diverifikasi secara independen.

**Tanggal/build lengkap ROM, nama/hash ZIP yang benar-benar dipasang dan log kejadian belum tersedia untuk diperiksa.** Tertahan di logo dapat terjadi pada beberapa tahap, termasuk kernel awal atau init, sehingga gejala ini saja tidak menetapkan penyebab. Laporan ini bukan bukti bahwa seluruh ROM Android 17 atau seluruh keluarga miatoll tidak kompatibel. Tunda percobaan 3.1 pada kombinasi tersebut sampai ada bukti dan jalur pemulihan yang sesuai.

Sebelumnya ada laporan *lain yang tercatat* mengenai joyeuse, Infinity Project 4.1 Android 17 dan Error 1 ketika memasang **3.0**. Belum diketahui apakah perangkat atau penyebabnya sama; Error 1 saat instalasi tidak identik dengan kegagalan boot setelah installer selesai. Jangan menggabungkan kedua laporan tanpa konfirmasi.

## Dahulukan pemulihan yang aman

- Jangan ulangi flash hanya untuk memperoleh log, jangan wipe/format data, jangan menonaktifkan AVB/vbmeta, dan jangan menebak image atau slot. Jangan menjalankan installer lama di komputer atau pada perangkat untuk pengujian.
- Jika masih berada di recovery setelah penulisan boot gagal, jangan reboot sebelum jalur pemulihan dipastikan. Jika perangkat bootloop, hentikan percobaan reboot berulang dan, **bila dapat diakses dengan aman**, masuk ke recovery yang sudah ada. Prioritaskan pemulihan perangkat daripada melengkapi log.
- Cadangan boot dari perangkat, ROM/build, keadaan root, dan slot yang tepat mungkin dapat digunakan untuk pemulihan melalui prosedur yang sesuai perangkat. Verifikasi hal tersebut terlebih dahulu; bila cadangan yang cocok tidak ada atau slot/partisi tidak jelas, cari panduan pemulihan spesifik perangkat dan jangan menebak.
- Installer 3.1 juga dapat mengganti `/data/adb/ksud` **sebelum** menulis boot jika `/data/adb` tersedia. Memulihkan boot saja tidak otomatis mengembalikan file itu. Jangan mengambil `ksud` dari perangkat atau versi lain secara acak.

## Pengumpulan bukti, tanpa flash

Mintalah informasi yang tersedia; jangan meminta serial, IMEI, kredensial, kunci, atau image mentah untuk dipublikasikan.

1. Model dan codename fisik, tanggal/build lengkap Project Infinity, versi firmware/vendor jika diketahui, recovery dan versinya. Info ROM yang dibaca dari recovery dapat berbeda dari ROM yang terpasang.
2. Sebelum kejadian apakah ROM tersebut sudah berhasil boot, kernel apa yang digunakan, bagaimana 3.1 dipasang, nama ZIP dan SHA-256, apakah ZIP dimodifikasi/dipindah ke installer lain, serta urutan ZIP/root yang digunakan.
3. Installer dilaporkan selesai dan boot tertahan di logo Redmi/Mi sebelum animasi. Jika masih ada foto/log atau rincian lain, simpan **seluruh** pesan. Bagaimana perangkat dipulihkan?
4. Cadangan boot yang cocok dilaporkan tersedia dan KernelSU digunakan sebelumnya. Versi KernelSU, modul userspace, dan apakah root masih berfungsi setelah pemulihan belum diketahui. Jangan mengubahnya hanya untuk diagnosis.
5. Belum ada log kejadian yang tersedia untuk diperiksa. Bila ternyata tersimpan, simpan log installer/recovery dan `pstore` atau `last_kmsg` dari boot yang gagal. Setelah pemulihan log lama mungkin sudah tidak ada atau tertimpa; log recovery saat ini bukan otomatis log panic Android. Jangan reboot/flash ulang untuk membuat log.

Jika recovery saat ini mendukung ADB dan file dapat dibaca, contoh **baca/salin saja** dari komputer (tidak mem-flash atau me-mount partisi):

```text
adb pull /tmp/recovery.log recovery-saat-ini.log
adb pull /proc/last_kmsg last-kmsg.txt
adb pull /sys/fs/pstore pstore-infinity
```

File/path dapat tidak ada atau tidak dapat diakses; jangan memaksa akses dengan mengubah partisi. `/tmp/recovery.log` dapat berasal dari sesi recovery terbaru, bukan sesi flash yang gagal, dan hilang saat recovery reboot. `pstore`/`last_kmsg` mungkin kosong atau bukan boot yang dimaksud. Tinjau dan redaksi data pribadi sebelum mengirim log secara privat. Jangan unggah log mentah ke repositori publik.

## Fakta statis yang perlu dibedakan dari diagnosis

Pemeriksaan dilakukan **offline**, bukan pada perangkat pengguna. Bukti build CI 3.1 dan konfigurasi ditarik dari Git blob publik dan diverifikasi hash; ZIP 3.1 direkonstruksi dari input yang dipin dan SHA-256-nya cocok dengan rilis yang terdokumentasi, `1ffe861ceaa2775e4f75bc9f7ecd4b7c56cf9c146f1690eb941c8dd2e5200d4a`. Belum diketahui apakah itulah file yang digunakan pelapor.

- Konfigurasi 3.1 yang diperiksa memiliki `CONFIG_MODVERSIONS=y` dan `CONFIG_MODULE_SIG_FORCE=y`. Sertifikat modul build 3.1 berbeda dari 3.0; ZIP tidak menyertakan modul `.ko`. Modul ROM yang diperlukan **mungkin** gagal karena ABI, versi, dependensi, atau signature/keyring. Tanpa modul ROM, log dan bukti keyring runtime, ini hipotesis, bukan penyebab yang terbukti.
- Paket resmi 3.1 menggunakan core AnyKernel 2.0 dan menyetel `IS_SLOT_DEVICE=0`, tanpa memastikan perangkat tidak memiliki slot; tidak ada verifikasi readback setara installer 3.0 asli. Jalur penulisan umum mengisi partisi boot dengan nol sebelum menulis image baru: kegagalan/terputus dapat meninggalkan boot rusak. Paket tidak membuat backup boot otomatis. `Done` bukan bukti bahwa image benar atau dapat boot.
- Paket tidak membawa DTB/DTBO, tetapi cabang Magisk di core installer dapat mem-patch DTB; efek yang benar-benar terjadi bergantung pada kondisi perangkat. Perbedaan DTB/DTBO, ramdisk, AVB, firmware/vendor, root userspace, atau regresi kernel juga perlu dipertimbangkan hanya sesuai bukti. Tidak satu pun telah ditetapkan sebagai penyebab kasus ini.
- CI build dan pengujian QEMU sebelumnya menggunakan image nyata tetapi boot/perangkat sintetis; itu bukan uji boot fisik, kompatibilitas modul ROM, atau jaminan pemulihan. Pemeriksaan paket offline pada insiden ini lulus delapan tes; itu tidak mereproduksi kegagalan boot.

Jangan menghapus pemeriksaan keamanan, mematikan verifikasi modul/AVB, atau merilis "fix" berdasarkan salah satu hipotesis saja.

## Alat audit modul offline untuk 3.1

`build-kit/scripts/audit_synthetica31_rom_modules.py` dapat membandingkan `.ko` yang sudah diekstrak dari **build ROM yang tepat** dengan image, konfigurasi, `Module.symvers`, `System.map`, dan sertifikat modul build 3.1 yang dipin. Alat ini tidak mengakses ponsel, tidak menjalankan modul, tidak membuat boot image dan tidak mengubah input. Ia menulis laporan baru mode `600` di luar repositori/input, serta memakai direktori sementara privat untuk pemeriksaan signature. File sementara dapat tertinggal jika proses dihentikan secara paksa.

Contoh di **komputer**, setelah menyediakan direktori privat berisi modul ROM yang sudah diekstrak (bukan menjalankan perintah ini pada ponsel):

```sh
mkdir -m 700 /tmp/s31-audit-private
gh api -H 'Accept: application/vnd.github.raw+json' \
  repos/dwp29/Syntenthica/git/blobs/0f815b773d39a8f0b392a7d190be9ca1ad702ead \
  > /tmp/s31-audit-private/evidence31.zip
python3 build-kit/scripts/audit_synthetica31_rom_modules.py \
  --modules /tmp/s31-audit-private/modul-rom \
  --evidence /tmp/s31-audit-private/evidence31.zip \
  --report /tmp/s31-audit-private/laporan.json
```

Arsip evidence harus cocok SHA-256 dan Git blob yang dipin; tidak perlu mengekstrak atau menjalankan image kernel di dalamnya. Hanya `.ko` reguler tak terkompresi yang diperiksa; symlink dan file berakhiran `.ko.*` seperti `.ko.gz`, `.ko.xz`, `.ko.zst` atau `.ko.lz4` dilewati dan dicatat. Hasil mencakup signature terhadap **satu sertifikat build**, CRC simbol, `module_layout`, dan perbandingan vermagic; hasil tersebut tidak membuktikan keyring runtime, modul mana yang dimuat, asal ROM terpasang, maupun penyebab kegagalan boot. ROM aktual dan log kasus ini belum dianalisis.

Pengujian host tersedia pada `tests/test_synthetica31_rom_modules.py` dan workflow `.github/workflows/synthetica31-rom-audit.yml`. [CI 42479268803](https://github.com/dwp29/Syntenthica/actions/runs/42479268803) lulus 41 tes host yang mencakup evidence 3.1 dan fixture lama/sintetis, **bukan** modul pengguna, pengujian load, atau boot fisik.
