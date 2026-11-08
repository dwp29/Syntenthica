# Laporan gagal boot — Synthetica 3.1 / Project Infinity 4.1

## Status

Menurut pelapor, perangkat **joyeuse** dengan Project Infinity X **4.1 GAPPS, 21.10.2026 / Android 17** tertahan di **logo Redmi/Mi, sebelum animasi ROM**, setelah installer Synthetica 3.1 melaporkan selesai. Perangkat dilaporkan **sudah dapat boot kembali dan KernelSU masih berfungsi**; varian/versi KernelSU belum diketahui. Ada cadangan boot yang menurut pelapor cocok untuk perangkat/ROM, tetapi belum diketahui apakah cadangan itu digunakan untuk pemulihan. Identitas file, hasil dan kondisi perangkat ini belum diverifikasi secara independen.

**Nama/hash ZIP ROM dan kernel yang benar-benar dipasang, serta log kejadian, belum tersedia untuk diperiksa.** Tertahan di logo dapat terjadi pada beberapa tahap, termasuk kernel awal atau init, sehingga gejala ini saja tidak menetapkan penyebab. Root yang berfungsi setelah pemulihan juga tidak membuktikan penyebab kegagalan atau bahwa installer tidak mengubah `ksud`. Laporan ini bukan bukti bahwa seluruh ROM Android 17 atau seluruh keluarga miatoll tidak kompatibel. Tunda percobaan 3.1 pada kombinasi tersebut sampai ada bukti dan jalur pemulihan yang sesuai.

Sebelumnya ada laporan *lain yang tercatat* mengenai joyeuse, Infinity Project 4.1 Android 17 dan Error 1 ketika memasang **3.0**. Belum diketahui apakah perangkat atau penyebabnya sama; Error 1 saat instalasi tidak identik dengan kegagalan boot setelah installer selesai. Jangan menggabungkan kedua laporan tanpa konfirmasi.

## Identitas ROM dari tautan pelapor

[Posting Telegram](https://t.me/RN9ProUpdate/7313) menyebut **Project Infinity X 4.1 Official, miatoll, Android 17**, tanggal build `02/10/2026` dan catatan umum bahwa masalah custom kernel diperbaiki. Namun, [metadata perangkat resmi yang diubah pada 21 Oktober](https://github.com/ProjectInfinity-X/official_devices/commit/fc200fc5c766d9768564d8b0a47b322eca795945) mencatat **4.1** sebagai dua file berikut; di perubahan yang sama, `02.10.2026` merupakan tanggal pada nama ZIP **4.0**. Perbedaan ini bisa merupakan kekeliruan pada salah satu keterangan, tetapi identitas ROM terpasang belum dapat dipastikan dari tautan saja.

| Varian yang tercatat resmi | Nama file | Ukuran byte | MD5 menurut metadata proyek |
|---|---|---:|---|
| GAPPS | `Project_Infinity-X-4.1-miatoll-21.10.2026-GAPPS-OFFICIAL.zip` | 2641732377 | `6b3d41aea18311e663266489adf54307` |
| VANILLA | `Project_Infinity-X-4.1-miatoll-21.10.2026-VANILLA-OFFICIAL.zip` | 1869490649 | `0aa6b44bcee30e4f5d348ec48cc4f1ea` |

[Halaman unduhan proyek](https://projectinfinity-x.com/downloads/miatoll) juga menampilkan dua varian 4.1 tersebut dan changelog `Fixed Some Issues Regarding Custom Kernels`, tanpa rincian perbaikan atau klaim kompatibilitas Synthetica 3.1. Ini petunjuk investigasi, **bukan** bukti penyebab atau solusi untuk kasus ini. Pelapor memilih **4.1 GAPPS, 21.10.2026**, tetapi nama/hash ZIP ROM dan checksum kernel 3.1 yang benar-benar dipasang belum diverifikasi. MD5 di atas adalah metadata penerbit, bukan pembuktian keaslian atau bahwa file terpasang identik; tidak ada ZIP ROM yang diunduh atau dianalisis pada tahap ini.

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
4. Cadangan boot yang cocok dilaporkan tersedia dan KernelSU masih berfungsi setelah pemulihan. Versi/varian KernelSU, modul userspace, dan apakah cadangan boot digunakan untuk pemulihan belum diketahui. Jangan mengubahnya hanya untuk diagnosis.
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

- Perbandingan bukti build publik 3.0 dan 3.1 yang tepat menunjukkan `Module.symvers` **identik byte demi byte** (12.236 baris, SHA-256 `1ce7153529b53f3f4bf361ea2e061ec575e712cd47cc5a0f10a854cf91d19ac3`) dan `System.map` juga identik (SHA-256 `d505b872733137313fd040dc9b5fb8363fbeea973ebb79f3eebcaef26de84d7b`). Konfigurasi build berbeda hanya pada `LOCALVERSION`; hash compiler dan linker yang dicatat sama. Ini **tidak** membuktikan dua image identik atau ROM dapat boot: image dan sertifikat penandatanganan modul berbeda, dan kesamaan simbol/CRC bukan bukti kompatibilitas atau keyring runtime.
- Konfigurasi 3.1 yang diperiksa memiliki `CONFIG_MODVERSIONS=y` dan `CONFIG_MODULE_SIG_FORCE=y`. ZIP tidak menyertakan modul `.ko`. Modul ROM yang diperlukan **mungkin** gagal karena ABI, versi, dependensi, atau signature/keyring. Tanpa modul ROM, log dan bukti keyring runtime, ini hipotesis, bukan penyebab yang terbukti.
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

Pengujian host tersedia pada `tests/test_synthetica31_rom_modules.py` dan workflow `.github/workflows/synthetica31-rom-audit.yml`. [CI 42480474040](https://github.com/dwp29/Syntenthica/actions/runs/42480474040) lulus 42 tes host, termasuk perbandingan evidence 3.0/3.1 yang dipin dan fixture lama/sintetis, **bukan** modul pengguna, pengujian load, atau boot fisik.
