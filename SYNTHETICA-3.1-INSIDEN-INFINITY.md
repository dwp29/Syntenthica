# Laporan gagal boot — Synthetica 3.1 / Project Infinity 4.1

## Status

Menurut pelapor, perangkat **joyeuse** dengan Project Infinity X **4.1 GAPPS, 21.10.2026 / Android 17** tertahan di **logo Redmi/Mi, sebelum animasi ROM**, setelah installer Synthetica 3.1 melaporkan selesai. Perangkat dilaporkan **sudah dapat boot kembali dan KernelSU masih berfungsi**; varian/versi KernelSU belum diketahui. Ada cadangan boot yang menurut pelapor cocok untuk perangkat/ROM, tetapi belum diketahui apakah cadangan itu digunakan untuk pemulihan. Identitas file, hasil dan kondisi perangkat ini belum diverifikasi secara independen.

**Nama/hash ZIP ROM dan log kejadian belum tersedia untuk diperiksa.** Pelapor menyatakan SHA-256 ZIP kernel 3.1 yang dipakai cocok dengan rilis terdokumentasi, tetapi file yang dipasang belum diperiksa secara independen. Tertahan di logo dapat terjadi pada beberapa tahap, termasuk kernel awal atau init, sehingga gejala ini saja tidak menetapkan penyebab. Root yang berfungsi setelah pemulihan juga tidak membuktikan penyebab kegagalan atau bahwa installer tidak mengubah `ksud`. Laporan ini bukan bukti bahwa seluruh ROM Android 17 atau seluruh keluarga miatoll tidak kompatibel. Tunda percobaan 3.1 pada kombinasi tersebut sampai ada bukti dan jalur pemulihan yang sesuai.

**Koreksi pelapor:** Synthetica 3.0 belum pernah berhasil boot pada ROM Infinity 4.1. Belum jelas apakah 3.0 pernah dicoba pada ROM tersebut; tidak ada pembanding boot 3.0 yang berhasil pada ROM ini. Sebelumnya ada laporan yang tercatat mengenai joyeuse, Infinity Project 4.1 Android 17 dan Error 1 ketika memasang **3.0**. Belum diketahui apakah perangkat atau penyebabnya sama; Error 1 saat instalasi tidak identik dengan kegagalan boot setelah installer selesai. Jangan menggabungkan kedua laporan tanpa konfirmasi.

## Identitas ROM dari tautan pelapor

[Posting Telegram](https://t.me/RN9ProUpdate/7313) menyebut **Project Infinity X 4.1 Official, miatoll, Android 17**, tanggal build `02/10/2026` dan catatan umum bahwa masalah custom kernel diperbaiki. Namun, [metadata perangkat resmi yang diubah pada 21 Oktober](https://github.com/ProjectInfinity-X/official_devices/commit/fc200fc5c766d9768564d8b0a47b322eca795945) mencatat **4.1** sebagai dua file berikut; di perubahan yang sama, `02.10.2026` merupakan tanggal pada nama ZIP **4.0**. Perbedaan ini bisa merupakan kekeliruan pada salah satu keterangan, tetapi identitas ROM terpasang belum dapat dipastikan dari tautan saja.

| Varian yang tercatat resmi | Nama file | Ukuran byte | MD5 menurut metadata proyek |
|---|---|---:|---|
| GAPPS | `Project_Infinity-X-4.1-miatoll-21.10.2026-GAPPS-OFFICIAL.zip` | 2641732377 | `6b3d41aea18311e663266489adf54307` |
| VANILLA | `Project_Infinity-X-4.1-miatoll-21.10.2026-VANILLA-OFFICIAL.zip` | 1869490649 | `0aa6b44bcee30e4f5d348ec48cc4f1ea` |

[Halaman unduhan proyek](https://projectinfinity-x.com/downloads/miatoll) juga menampilkan dua varian 4.1 tersebut dan changelog `Fixed Some Issues Regarding Custom Kernels`, tanpa rincian perbaikan atau klaim kompatibilitas Synthetica 3.1. Ini petunjuk investigasi, **bukan** bukti penyebab atau solusi untuk kasus ini. Pelapor memilih **4.1 GAPPS, 21.10.2026** dan menyatakan checksum ZIP kernel 3.1 cocok; nama/hash ZIP ROM dan file yang dipasang belum diverifikasi secara independen. MD5 di atas adalah metadata penerbit, bukan pembuktian keaslian atau bahwa file terpasang identik; tidak ada ZIP ROM yang diunduh atau dianalisis pada tahap ini.

## Dahulukan pemulihan yang aman

- Jangan ulangi flash hanya untuk memperoleh log, jangan wipe/format data, jangan menonaktifkan AVB/vbmeta, dan jangan menebak image atau slot. Jangan menjalankan installer lama di komputer atau pada perangkat untuk pengujian.
- Jika masih berada di recovery setelah penulisan boot gagal, jangan reboot sebelum jalur pemulihan dipastikan. Jika perangkat bootloop, hentikan percobaan reboot berulang dan, **bila dapat diakses dengan aman**, masuk ke recovery yang sudah ada. Prioritaskan pemulihan perangkat daripada melengkapi log.
- Cadangan boot dari perangkat, ROM/build, keadaan root, dan slot yang tepat mungkin dapat digunakan untuk pemulihan melalui prosedur yang sesuai perangkat. Verifikasi hal tersebut terlebih dahulu; bila cadangan yang cocok tidak ada atau slot/partisi tidak jelas, cari panduan pemulihan spesifik perangkat dan jangan menebak.
- Installer 3.1 juga dapat mengganti `/data/adb/ksud` **sebelum** menulis boot jika `/data/adb` tersedia. Memulihkan boot saja tidak otomatis mengembalikan file itu. Jangan mengambil `ksud` dari perangkat atau versi lain secara acak.

## Pengumpulan bukti, tanpa flash

Mintalah informasi yang tersedia; jangan meminta serial, IMEI, kredensial, kunci, atau image mentah untuk dipublikasikan.

1. Model dan codename fisik, tanggal/build lengkap Project Infinity, versi firmware/vendor jika diketahui, recovery dan versinya. Info ROM yang dibaca dari recovery dapat berbeda dari ROM yang terpasang.
2. Sebelum kejadian apakah ROM tersebut sudah berhasil boot, kernel apa yang digunakan, bagaimana 3.1 dipasang, apakah ZIP dimodifikasi/dipindah ke installer lain, serta urutan ZIP/root yang digunakan. Pelapor menyatakan SHA-256 ZIP 3.1 cocok dengan rilis; file belum diverifikasi independen.
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

## Pengambilan log lewat PC (uji awal tanpa flash)

[`capture.py`](build-kit/ci/s31-adb-capture/capture.py) adalah alat terpisah
untuk PC, **bukan installer kernel**, dengan petunjuk di
[`README-ID.txt`](build-kit/ci/s31-adb-capture/README-ID.txt). Ia menggunakan
ADB untuk membaca log recovery, log installer yang ada, dan pada tahap boot
mengambil pstore terlebih dahulu serta `last_kmsg`. Hasil hanya ditulis di folder
baru pada PC; log perlu ditinjau privat. Pstore dapat kosong/tertindih; recovery
log bukan otomatis log boot gagal. Batas ukuran, kegagalan, timeout dan output
kosong tercatat di `STATUS.json`. Alat tidak flash, reboot, mount atau mengubah
partisi. Tes menggunakan ADB palsu; **belum diuji pada OrangeFox atau perangkat
fisik** dan tidak menjamin log dapat dikumpulkan. Uji awal tidak memerlukan flash.
[CI host Ubuntu dan Windows 42561394722](https://github.com/dwp29/Syntenthica/actions/runs/42561394722)
lulus dengan ADB palsu, bukan recovery sebenarnya. [ZIP alat PC diagnostik](https://drive.google.com/file/d/1ukWt9Wi44TqHt4zZ0Ehd1ExmunfdU2rV/view?usp=drivesdk)
(SHA-256 `561c46fdcc758505ab8643f608ae17ad6ea5c72617d02b67812fa37f64d442f0`)
hanya berisi skrip Python dan panduan; **bukan file kernel untuk di-flash**.

Konfigurasi 3.1 pada bukti build ber-SHA terverifikasi mengaktifkan `PSTORE`,
`PSTORE_CONSOLE`, `PSTORE_PMSG`, dan `PSTORE_RAM`; ini bukan bukti perangkat,
DTB, recovery atau boot gagal benar-benar menyimpan record yang dapat dibaca.

## Pemeriksaan image yang diberikan pengguna

Pengguna menyediakan `Infinity4.1-boot.img` melalui ZIP. SHA-256 ZIP
`6dc75bcdfc1ba403f927fa7ce6b4a7c1b8d71dda11a887658ba52a0601853e35` cocok
dengan metadata Drive; arsip teruji dan hanya berisi satu `boot.img`. Setelah
ekstraksi offline, image berukuran 134.217.728 byte dengan SHA-256
`d33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f`,
cocok dengan metadata file image terpisah di Drive. Kecocokan ini hanya
mengaitkan kedua unggahan, **bukan membuktikan asal atau keaslian ROM**. Belum
ada konfirmasi apakah image berasal dari ZIP ROM atau backup perangkat, atau
apakah pernah dipatch root.

Pemeriksaan offline `audit_synthetica3_boot.inspect_boot` menemukan header
Android boot v2, page 4096, kernel ARM64 tidak terkompresi sepanjang 48.535.576
byte, ramdisk berformat awal LZ4 legacy dan satu DTB yang lolos pemeriksaan
struktur. Legacy boot ID cocok dan footer AVB ditemukan, **tanpa verifikasi
signature atau trust AVB**. Kernel berisi string versi
`4.14.357-openela-perf-ge84700282bb0`, build 21 Oktober 2026, serta embedded
config yang dapat diekstrak. Nama file dan string tersebut tidak membuktikan
image berasal dari ROM target yang belum diinspeksi.

Config image itu dan config bukti 3.1 sama-sama mengaktifkan
`CONFIG_MODVERSIONS`, `CONFIG_MODULE_SIG` dan `CONFIG_MODULE_SIG_FORCE`.
Config 3.1 mengaktifkan `CONFIG_LRU_GEN`, `CONFIG_LRU_GEN_ENABLED`,
`CONFIG_UCLAMP_TASK`, `CONFIG_KSU`, `CONFIG_KSU_SUSFS` dan `CONFIG_NOMOUNT`;
simbol tersebut tidak ditemukan dalam config image pengguna. Ketidakhadiran
simbol dapat berarti perbedaan source/Kconfig, bukan sekadar opsi dinonaktifkan.
Sebanyak 383 entri berbeda termasuk simbol yang hanya ada pada salah satu
config; perbandingan ini bukan bukti perbedaan fungsi runtime atau penyebab
bootloop. Modul ROM, kecocokan CRC dan kepercayaan keyring belum diverifikasi.
Ramdisk juga berhasil didekompresi dan struktur CPIO diperiksa secara offline:
terdapat sembilan entri sebelum trailer, tanpa file `.ko` atau `modules.load`.
Nama-nama entri tidak menunjukkan Magisk, KernelSU atau APatch; hal ini **tidak
membuktikan image tidak dipatch**. `fstab.qcom` mencantumkan antara lain ext4
untuk `/system` dan `/vendor`, serta f2fs untuk `/data`; ini bukan bukti
partisi aktual sudah terpasang atau kompatibel. Ketiadaan modul di ramdisk
bukan bukti bahwa ROM tidak menggunakan modul di partisi lain. Pencarian commit
`e84700282bb0` pada repositori source yang dipin 3.1 tidak menemukannya; ini
belum mengidentifikasi source image atau membuktikan keduanya tidak terkait.

Image pengguna tidak dimasukkan ke repositori dan tidak ditulis ke perangkat.
Belum ada kandidat perbaikan baru yang siap diuji.

## Fakta statis yang perlu dibedakan dari diagnosis

Pemeriksaan dilakukan **offline**, bukan pada perangkat pengguna. Bukti build CI 3.1 dan konfigurasi ditarik dari Git blob publik dan diverifikasi hash; ZIP 3.1 direkonstruksi dari input yang dipin dan SHA-256-nya cocok dengan rilis yang terdokumentasi, `1ffe861ceaa2775e4f75bc9f7ecd4b7c56cf9c146f1690eb941c8dd2e5200d4a`. Pelapor menyatakan checksum ZIP yang digunakan cocok, tetapi file itu sendiri belum diperiksa secara independen.

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

## Kandidat kontrol 3.1-control1 (hasil kompilasi)

Kandidat ini menggunakan resep dan patch source 3.1, bukan rollback 2.0.
Perubahan yang diizinkan dari config 3.1 hanya suffix release dan
`CONFIG_LRU_GEN_ENABLED` dari `y` ke `n`: MGLRU tetap dikompilasi tetapi
nonaktif secara default. UCLAMP, KernelSU, SUSFS, NoMount dan pemeriksaan
keamanan tetap diwajibkan oleh guard konfigurasi. Ini eksperimen terkontrol,
**bukan diagnosis atau perbaikan bootloop yang terbukti**. Config image yang
diberikan tidak mengandung simbol MGLRU, tetapi itu saja tidak menetapkan bahwa
MGLRU menyebabkan masalah.

`build-kit/scripts/build_synthetica31_control.py` menyiapkan tree terisolasi,
memeriksa config aktual terhadap evidence 3.1 terpin dan meminta seluruh
12.236 ekspor tetap cocok; toolchain, source, Manager dan modul satu build
juga diperiksa oleh guard turunan. Workflow
`.github/workflows/synthetica31-control-kernel.yml` menghasilkan bukti
kompilasi saja, bukan installer. [CI 42563877678](https://github.com/dwp29/Syntenthica/actions/runs/42563877678)
lulus pada commit `590c51c2970638934fec36c7eecf5b145e907715`. Lima tes lokal
melewati config referensi sebenarnya; CI memverifikasi config, patch, toolchain,
six same-build modules dan seluruh 12.236 ekspor terhadap 3.1. Hasilnya cocok
untuk seluruh ekspor, termasuk `module_layout=0xed5659d1`; ini bukan audit modul
ROM. Transfer evidence Git blob `32b910e3de03358bf29cd00dc2c5a1f2880c656c`
ber-SHA-256 `8b01dde5c65234654634d5dc9cbc97a071ba3dc0f5c3061bb3ec02c9ab15867c`
telah diunduh dan diperiksa: integritas ZIP, sembilan hash manifest, dan config
tertanam dalam image cocok. `Image.gz` baru SHA-256
`bb0f98da58541cdc7eb8131d60860d006e35efc56a8ca1b33ebe3cc7d003e226`.

Kernel baru menggunakan sertifikat modul baru dan identitas release baru;
ABI dan kepercayaan modul ROM, AVB dan boot fisik masih belum diketahui.
Bukti kompilasi bukan boot image atau ZIP recovery; **jangan flash**. Installer
lama mempunyai risiko yang dijelaskan di atas dan belum diadaptasi untuk
kandidat ini. Tahap selanjutnya adalah merancang dan memverifikasi integrasi
installer/boot, bukan menyebut compile evidence sebagai file flash siap pakai.

### Kendala AVB yang ditemukan selama integrasi

Pemeriksaan read-only `build-kit/scripts/audit_boot_avb_hash.py`, disilang-periksa
dengan `avbtool` terpin blob `7932b111ce2b8bb23ea50bebf42c201a20c4eea5`,
menemukan descriptor hash `boot` SHA-256 di footer image pengguna. Digest atas
50.405.376 byte image asli cocok. Header vbmeta yang tertanam memakai algorithm
`NONE`, jadi hasil ini **bukan verifikasi tanda tangan atau chain of trust**;
keadaan vbmeta eksternal dan bootloader tidak diketahui.

Untuk menguji konsekuensi metode repack, sebuah **fixture offline privat**
dibuat dengan kernel control1, ramdisk/DTB/header relevan dipertahankan, dan
metadata AVB lama disalin. Pemeriksaan struktur dan legacy boot ID lulus,
tetapi digest descriptor `boot` **tidak cocok**, dikonfirmasi oleh audit dan
`avbtool verify_image` pada file fixture bernama `boot.img` di direktori
terpisah. Ini bukan eksekusi installer, bukan boot perangkat, dan bukan bukti
mengapa 3.1 sebelumnya bootloop. Hasil ini menunjukkan mengapa kesamaan bytes
metadata AVB saja bukan syarat cukup untuk melepas kandidat baru.

Pada **salinan fixture privat lain**, hanya 32 byte digest descriptor yang
sudah ada dihitung ulang, tanpa mengubah flags, ukuran, atau vbmeta eksternal;
audit dan `avbtool` kemudian menyatakan hash embedded cocok. Karena algorithm
vbmeta embedded `NONE`, ini konsistensi hash tak bertanda tangan, **bukan**
otentikasi, validasi chain atau bukti boot. Ini uji manual offline untuk
menilai kelayakan teknis, bukan perubahan installer atau perintah flash.

Jangan memakai kedua fixture sebagai image untuk flash. Installer lama belum
lolos pemeriksaan AVB ini; belum ada keputusan untuk mengganti footer atau
menonaktifkan verifikasi. Signature, vbmeta eksternal, state runtime dan
ROM/modules tetap belum diverifikasi. Tes unit pemeriksa hash menggunakan
fixture sintetis dan `avbtool`, tanpa ponsel; script hanya membaca input dan
tidak menandatangani, memodifikasi, atau mem-flash. [CI audit 42565273307](https://github.com/dwp29/Syntenthica/actions/runs/42565273307)
lulus pada fixture sintetis; image pengguna tetap privat.
