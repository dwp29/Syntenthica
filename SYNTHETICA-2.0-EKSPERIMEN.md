# Synthetica 2.0 — eksperimen Uclamp, MGLRU, dan Neutron

**Status: eksperimen pengembangan, bukan rilis atau paket flash.** Target yang
dilaporkan pengguna adalah Joyeuse dengan Lunaris AOSP GMS 3.13 Android 16;
[tautan ROM yang diberikan](https://artifacts.serverhive.in/?id=lunaris-aosp-miatoll-20261103-045856621051)
menampilkan metadata `Lunaris-AOSP-miatoll-Community-3.13-GMS-2026110303.zip`
(bukan build resmi 3.12 yang tercantum di direktori lama). Hash arsip ROM sudah
cocok dengan metadata publik, tetapi identitas build yang terpasang belum
diverifikasi. Baseline 2.0, APK Manager,
dan resep yang digunakan 3.0 tidak diganti. BakaSU tidak dipasang. Hasil build
yang berhasil sekalipun hanya bukti kompilasi, bukan bukti aman untuk perangkat
atau kompatibel dengan modul vendor ROM.

## Metadata ROM yang diberikan

API Artifact Explorer untuk build yang diberikan mencantumkan arsip Community
3.13 GMS, ukuran `2.925.420.062` byte, SHA-256 **yang diterbitkan server**
`37263a7671b93ec4ae506574925b3e5d97a14756ab7152b138208a3b6b0f33d7`.
Server juga mencantumkan `boot.img`, `dtbo.img`, `recovery.img`, `vbmeta.img`
dan `super_empty.img` terpisah; hash yang diterbitkan untuk boot, DTBO dan vbmeta
dicatat dalam `SOURCES.json`. Gofile menampilkan nama arsip yang sama. Metadata
Ketiga image referensi publik `boot.img`, `dtbo.img`, dan `vbmeta.img` sudah
didownload dan cocok dengan hash yang dipublikasikan. Arsip ROM berukuran
`2.925.420.062` byte juga diunduh dan cocok dengan SHA-256 publik pada run
`42260746566`. Isi arsip adalah block OTA (`*.new.dat.br`), bukan `payload.bin`;
run `42261865876` merekonstruksi `vendor.img` dan `boot.img` secara read-only.
`boot.img` **di dalam ZIP** berhash
`1d3f3b36b087bd7f36941ac4784287421d9f25d573c4f19b19e93cf0797da389`,
berbeda dari hash boot terpisah yang diterbitkan server; banner kernel di boot
ZIP adalah `4.14.357-SuperPotato+2`. [Audit `42262455808`](https://github.com/dwp29/Syntenthica/actions/runs/42262455808)
menemukan bagian kernel dan DTB kedua boot identik, tetapi **ramdisk berbeda**.
Jangan menganggap kedua image identik atau memilih image boot cadangan hanya
berdasarkan nama. Pencarian di vendor hasil ekstraksi dan ramdisk boot tidak
menemukan `.ko` untuk dibandingkan; ekstraksi vendor melaporkan sebagian kegagalan
perubahan ownership, dan partisi lain belum diperiksa. Upaya lanjutan
`42263147839` terhenti karena halaman Gofile tidak memuat berkas; bukan bukti
bahwa ROM atau modul hilang. Jadi belum boleh menarik kesimpulan bahwa ROM tidak
menggunakan modul. Pada [audit read-only `42258937123`](https://github.com/dwp29/Syntenthica/actions/runs/42258937123),
`boot.img` memiliki header Android v2, page 4096, ramdisk LZ4 legacy dan bagian
DTB terpisah; `dtbo.img` memiliki empat entry. Kedua image memiliki footer AVB;
header `vbmeta.img` tercatat memiliki flags `0x3`. Ini hanya struktur berkas,
bukan verifikasi signature atau status bootloader/perangkat. Semua komponen boot
perlu dipertahankan dan divalidasi saat merancang installer; jangan mengubah atau
menonaktifkan verifikasi untuk memaksa boot. Hasil ini belum membuktikan bahwa
ROM tersebut benar terpasang di Joyeuse, atau bahwa modul di dalamnya cocok dan
tepercaya oleh kernel.

## Cakupan dan default

| Komponen | Perlakuan eksperimen |
|---|---|
| WALT + SchedTune | Keduanya dipertahankan seperti konfigurasi 2.0 yang tersimpan. |
| Uclamp | Backport per-task dan CPU cgroup, dengan lima bucket; clamp default netral dan default boost RT tambahan 0. Pengaturan pengguna/ROM tetap bisa mengubah clamp. |
| MGLRU | Atas permintaan pengguna, varian eksperimen **aktif secara default** (`CONFIG_LRU_GEN=y`, `CONFIG_LRU_GEN_ENABLED=y`). Varian kontrol Neutron mematikan default MGLRU untuk pembandingan; statistik tambahan tetap dimatikan. Keduanya belum diuji pada perangkat. |
| Thermal, frekuensi dan root | Tidak ada patch thermal, overclock, bypass signature modul, atau perubahan implementasi KernelSU-Next/Manager. Penjagaan konfigurasi menolak perubahan lain dari konfigurasi 2.0 tersimpan. |
| Neutron | Calon compiler dipin ke tag `06092026`, Clang `24.0.0git`, arsip SHA-256 `531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30`. CI membandingkan build yang sama dengan LLVM 18; itu bukan benchmark. |

MGLRU aktif dalam varian yang diminta, tetapi backport MM 4.14 ini luas dan donor
melaporkan hang saat idle/charging pada versi terdahulu; laporan itu tidak
membuktikan penyebab atau kejadian pada ROM pengguna. Varian kontrol dengan
runtime default off juga tidak menghapus semua risiko: struktur kernel dan ABI
tetap berubah. Kode Uclamp
menerapkan clamp setelah `boosted_cpu_util()` yang sudah ada; tidak ada boost
statis tambahan yang dipaksakan. Namun WALT, SchedTune, I/O-wait, dan nilai yang
dikirim userspace tetap dapat memengaruhi frekuensi. `uclamp.max` adalah hint,
bukan batas frekuensi absolut. Belum ada bukti bahwa kombinasi ini lebih dingin,
lebih hemat, atau lebih cepat pada perangkat pengguna.

Backport Uclamp menerapkan perbaikan upstream untuk indeks bucket, accounting
runqueue aktif dan penanganan idle, batas min/max cgroup, propagasi group baru,
serta inisialisasi runqueue. `sched_post_fork()` dihubungkan setelah publikasi
task. Donor CASS dan defconfig donor sengaja tidak diambil: target ini menggunakan
WALT, bukan scheduler CASS donor. Integrasi ini masih perlu review dan uji runtime;
perbaikan-perbaikan itu bukan jaminan backport sudah lengkap. Kontrol CPU
`uclamp.min/max` terdaftar pada cgroup legacy (v1) tree ini; jangan mengasumsikan
antarmuka cgroup v2 atau kebijakan placement CASS sudah didukung.

Build awal CI `42237485378` gagal: LLVM 18 menemukan definisi `ANON_AND_FILE`
yang hilang dari backport MGLRU; Neutron berhenti pada pemeriksaan karena paketnya
tidak menyertakan `llvm-size`. Keduanya ditangani di resep eksperimen: perbaikan
donor untuk definisi MGLRU ditambahkan, dan binary `aarch64-linux-gnu-size` host
digunakan hanya bila `llvm-size` tidak ada. Compiler dan linker tetap dari
toolchain yang dipilih. Build ulang `42241223420` mencapai kompilasi dengan
kedua compiler tetapi gagal pada callback `pagewalk` donor dan penggunaan
`clamp()` dengan bit-field Uclamp; keduanya dikoreksi di patch lanjutan. Kode
build awal juga mengandung bug accounting Uclamp yang dikoreksi. Jangan gunakan
artefak dari kedua run tersebut.

### Bukti build MGLRU-on yang diminta

Pada [run `42258512643`](https://github.com/dwp29/Syntenthica/actions/runs/42258512643),
job Neutron MGLRU-on, Neutron MGLRU-off, dan LLVM 18 MGLRU-on selesai dengan
guard statis lulus. Audit
terpisah `42260895446` memastikan hash image/config/certificate/symvers, config
tertanam, release, dan source metadata konsisten. Kedua konfigurasi hanya
berbeda pada `LRU_GEN_ENABLED`, compiler/linker dan `module_layout` CRC
(`0xed5659d1`) sama, tetapi sertifikat modul publiknya **berbeda**. Image on:
`3a9f39f8f7ea79c9251a896050dfeb60395f1194a064f91a85a8fe8ae38adaea`;
image off: `b6a1756de6696ae6fafc4598768efb9126d1b9087b276ecb1d8bb9aeb1523c8b`.
Tidak ada bukti boot, pairing Manager, suhu, baterai atau kompatibilitas modul
perangkat. Semua artefak tetap `DO-NOT-FLASH` dan memiliki retensi 7 hari;
LLVM 18-on lulus guard di CI asal dan belum diaudit terpisah seperti Neutron.
Pada host, 125 unit test lolos dengan fixture source untuk rangkaian patch;
itu tetap bukan simulasi runtime kernel.

### Bukti build sebelumnya — MGLRU default off

Pada run `42241943772` (commit `eb64744`), build LLVM 18 **lulus kompilasi dan
pemeriksaan statis**; Neutron gagal pada konversi enum di driver Wi-Fi. Run
`42243864941` menemukan dua konversi serupa berikutnya. Patch lanjutan memberikan
cast eksplisit di ketiga lokasi yang mempertahankan nilai error yang sudah ada,
tanpa mematikan pemeriksaan compiler. Pada run `42245943990`, Neutron sudah
mengompilasi kernel dan modul, tetapi **ditolak** oleh penjaga identitas Manager.
Diagnosis object-only `42248121703` menunjukkan LLVM 24 mengubah perbandingan
nama paket menjadi konstanta instruksi, sehingga string paket tidak tersimpan
utuh dalam objek. Eksperimen berikutnya menggunakan `-fno-builtin-strncmp` hanya
untuk `apk_sign.o`, tanpa mengubah kode atau identitas KernelSU, agar string tetap
dapat diaudit; diagnosis `42248498236` menunjukkan flag, string dan pemanggilan
`strncmp` pada objek. Guard juga memeriksa identitas pada image, literal objek,
flag, dan relocasi panggilan. Job Neutron dan LLVM 18 pada [run `42250049696`](https://github.com/dwp29/Syntenthica/actions/runs/42250049696)
sudah selesai dan lulus build serta guard statis. [Audit terpisah](https://github.com/dwp29/Syntenthica/actions/runs/42252015075)
memverifikasi arsip Neutron, image, konfigurasi, identitas ter-link, objek
Manager, dan `Module.symvers`. Artifact
`Synthetica-2.0-neutron-DO-NOT-FLASH-42250049696` memiliki digest arsip SHA-256
`65c6fb5a6e60f0b845510c9d9a78e8ac0db39e0d6dff84d4fbf4888a4f47a114`
(retensi CI 7 hari) dan SHA-256 image
`cda7b5691dc2fa06b7d9be963ee48fdff224511aba4bbe668a4b02033e413a39`.
Enam modul build yang sama hanya diperiksa statis oleh CI asal; tidak ikut sebagai
installer. CRC `module_layout` Neutron juga `0xed5659d1`, berbeda dari
`0x6968ee15` pada 41 modul sampel ROM yang diperiksa sebelumnya. Sampel itu
**bukan bukti** tentang modul Lunaris 3.13 yang sedang dipakai pengguna. Ini tetap
bukan bukti Manager bekerja, modul ROM kompatibel, atau kernel aman di-flash.

Neutron juga memperingatkan frame stack `check_block` sebesar 2240 byte terhadap
batas peringatan 2048 byte. Peringatan ini perlu ditinjau dalam konteks stack dan
diuji; peringatan saja tidak membuktikan overflow. Artifact LLVM 18 hanya bukti build,
bukan installer dan bukan bukti aman untuk flash:
`Synthetica-2.0-clang18-DO-NOT-FLASH-42241943772`, digest arsip SHA-256
`dee0be086e8eb3de86b8d0ee105157eb322726d66615e585ce503bd7007f59e7`
(retensi CI 7 hari). Audit terpisah run `42244023150` memverifikasi digest
arsip, image, konfigurasi tertanam, identitas Manager yang ter-link, dan CRC
`Module.symvers`. SHA-256 image adalah
`8077223685a3913588c4c2cb0de8665ede2a333b0860791cb255b3566e2ae060`.
CRC `module_layout`-nya `0xed5659d1`, berbeda dari `0x6968ee15` pada 41 modul
sampel ROM yang pernah diaudit. Ini bukti ketidakcocokan ABI untuk sampel itu;
bukan alasan untuk menonaktifkan pemeriksaan versi atau signature. Run terbaru
juga menghasilkan artifact LLVM 18 `Synthetica-2.0-clang18-DO-NOT-FLASH-42250049696`
dengan digest arsip SHA-256
`648f799cdfde02c8cca2d44238678fb3353d3ccd4ffcc7bf1d001c8faf29172d`; guard
statisnya lulus dalam CI asal, sedangkan audit terpisah yang disebut di atas
berlaku untuk artifact LLVM 18 sebelumnya.

## Sumber dan reproduksi

- Source kernel dasar dipin ke
  [`Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795`](https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/commit/c1e6f795b557b7bf92220c91f05a42b456de7a74),
  dengan SHA-256 arsip `a68c9e306a3e14de92a258b185531a2562e3631f616a74b7882fc2667ac10ec0`.
- MGLRU berasal dari backport dan follow-up
  [`NothingTransition/CustomKernel1`](https://github.com/NothingTransition/CustomKernel1/commit/133620cdd409cc872f03ede532a0e37591359f5d).
  Identitas commit dan pengecualian tercatat dalam `build-kit/ci/synthetica2-experimental/SOURCES.json`.
- Uclamp berasal dari seri commit
  [`iput-object/kernel_xiaomi_sm6250`](https://github.com/iput-object/kernel_xiaomi_sm6250/compare/1cea11c0e0ea3e6a97d3c438f4630ed1e1eb1f0c...7b29cbd9de7e4427f546b2715729985ee64d2271),
  dengan perubahan target, [perbaikan batas bucket](https://github.com/torvalds/linux/commit/6d2f8909a5fabb73fe2a63918117943986c39b6c)
  dan perbaikan upstream lanjutan yang dirujuk per commit di manifest.
  Seri donor mencakup karya Patrick Bellasi, penulis upstream lainnya dan pemelihara donor; riwayat mereka tetap dirujuk di manifest.
- `build-kit/ci/synthetica2-experimental/patches/` berisi diff source GPL yang dapat diperiksa. `features.config` memuat fitur bersama, sedangkan `mglru-on.config` dan `mglru-off.config` memilih default untuk masing-masing varian. Ketiganya dipin. Tidak ada source tree besar atau toolchain binary yang dikomit. Metadata ROM di `SOURCES.json` adalah snapshot saat build; verifikasi arsip yang dilakukan sesudahnya dicatat di atas.
- `build-kit/scripts/extract_synthetica2_block_ota.py` hanya memproses full block OTA dengan operasi `new` yang terverifikasi dan menulis vendor/boot ke direktori baru di luar repo. `audit_synthetica2_rom_modules.py` membandingkan modul yang diekstrak dengan evidence build tanpa memodifikasi atau memuatnya; laporan rinci bersifat privat. Format delta/unknown dan bukti build yang tidak cocok ditolak, bukan dilewati.
- Workflow `.github/workflows/synthetica2-experimental.yml` membangun Neutron/MGLRU-on, LLVM 18/MGLRU-on, dan kontrol Neutron/MGLRU-off secara terpisah. Ia memeriksa bahwa kedua konfigurasi Neutron hanya berbeda pada default MGLRU; ini **bukan** benchmark maupun uji perangkat. Arsip source dan Neutron diverifikasi sebelum dipakai. Builder disalin ke direktori sementara, diubah hanya dalam salinan itu, dan dihentikan sebelum bagian AnyKernel/installer.
- **Batas penting kontrol A/B:** karena kedua job Neutron membuat key signing sementara sendiri, sertifikat modul publik yang tertanam **berbeda**. Perbandingan konfigurasi/toolchain tidak berarti seluruh kondisi runtime identik; kemungkinan modul yang dapat dipercaya juga bisa berbeda. Jangan gunakan pasangan ini sebagai benchmark MGLRU yang valid sebelum trust/module ABI diselesaikan dan kondisi kunci disamakan. Menyalakan/mematikan MGLRU pada image yang sama setelah validasi merupakan alternatif yang menjaga sertifikat tetap sama, tetapi efek transisi dan reboot juga harus diperhitungkan.
- KernelSU-Next dan identitas Manager lama dipertahankan: paket `net.ember.labs`, sertifikat DER 1381 byte, SHA-256 `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`. Identitas yang tertaut bukan bukti pairing atau root berhasil.

Uji host yang dapat dijalankan tanpa perangkat:

```sh
python3 -m unittest discover -s tests -p 'test_synthetica2_experimental.py' -v
python3 -m unittest discover -s tests -p 'test_synthetica3_*.py' -q
```

Tes host mencakup pengujian fungsi C Uclamp yang diekstrak dari patch dengan
stub terkontrol; ini tidak menguji locking atau scheduler kernel sebenarnya.
`prepare-tree` dan CI juga menjalankan `git apply --check` untuk tiap patch pada
salinan source yang dipin. Hasil build yang lolos pemeriksaan berisi image yang
diberi nama `DO-NOT-FLASH`, konfigurasi, `System.map`, `Module.symvers`, objek
`manager-apk_sign.o`, sertifikat modul **publik**, dan status; tidak memuat
installer atau kunci privat. Enam modul yang dipilih oleh
konfigurasi 2.0 diperiksa terhadap CRC dan sertifikat dari build yang sama,
bukan diuji dimuat ke perangkat dan bukan validasi modul vendor ROM.

## Gerbang sebelum pengujian perangkat

Data read-only yang diperlukan dari perangkat saat ini: `adb shell uname -r`,
`adb shell getprop ro.product.device`, `adb shell getprop ro.build.fingerprint`,
dan `adb shell cat /proc/modules` bila dapat dibaca. Ini membantu identifikasi
build dan modul yang benar-benar aktif, tetapi tidak sendirinya membuktikan ABI,
keyring, atau isi backup boot. Jangan kirim nomor seri, akun, atau kunci privat.

1. Kedua build harus lolos kompilasi dan verifikasi konfigurasi/IKCONFIG; catat error tiap compiler secara terpisah.
2. Verifikasi perangkat/ROM, AVB, metode pemulihan, dan kompatibilitas seluruh modul vendor: vermagic, CRC `MODVERSIONS`, dan signer yang benar. Audit terdahulu menemukan ketidakcocokan modul vendor; jangan menonaktifkan pemeriksaan untuk memaksanya.
3. Setelah ada kandidat yang layak diuji, ukur boot, pengenalan Manager/root, kamera, jaringan, sleep/wake, idle sambil mengisi daya, tekanan RAM dan stabilitas lama.
4. Setelah gerbang di atas terpenuhi, uji varian MGLRU-on dan kontrol MGLRU-off dengan toolchain serta beban yang sama. Catat status MGLRU aktual karena userspace bisa mengubahnya; ukur tekanan RAM, respons, suspend/idle sambil charging, suhu dan baterai. Perubahan clamp non-netral perlu pengujian terpisah.

Jika nanti pengujian perangkat sudah aman untuk dilakukan, data awal yang bisa
dibaca tanpa mengubah setelan meliputi:

```sh
adb shell getprop ro.product.device
adb shell getprop ro.build.fingerprint
adb shell uname -a
adb shell 'cat /sys/kernel/mm/lru_gen/enabled 2>/dev/null || echo unavailable'
adb shell 'cat /proc/pressure/memory 2>/dev/null || echo unavailable'
```

Backport ini melaporkan `1`/`0` pada file `lru_gen/enabled`; file yang tidak
tersedia bukan bukti bahwa MGLRU mati. Bandingkan A/B setelah perangkat stabil,
dengan brightness, jaringan, aplikasi, suhu lingkungan, dan beban yang sama;
ulangi pengukuran agar perubahan acak tidak disangka manfaat. Jangan meninggalkan
uji suspend/charging tanpa pengawasan pada build yang belum tervalidasi.

### Pemeriksaan tambahan terhadap pemaketan boot

Pada [run `42265188285`](https://github.com/dwp29/Syntenthica/actions/runs/42265188285),
`magiskboot` bawaan ZIP 2.0 dijalankan melalui emulasi ARM terhadap **boot v2
sintetis**, bukan boot perangkat atau ROM yang terpasang. Setelah kernel
percobaan dimasukkan, pemeriksaan byte menemukan header stabil dan bagian
ramdisk, DTB, second dan recovery DTBO fixture tidak berubah; footer AVB tetap
terlihat. Pemeriksaan ini **tidak** memverifikasi signature AVB, membuktikan
perangkat dapat boot, atau menguji installer pada perangkat. Mengganti kernel
membuat hash/signature lama untuk boot tidak lagi dapat diasumsikan valid.

Installer 2.0 lama bukan otomatis aman sebagai pembungkus eksperimen: dalam
kondisi tertentu saat Magisk terdeteksi, core-nya dapat mem-patch DTB dan skrip
lamanya juga memasang `ksud`. Boot yang benar-benar terpasang, kondisi trust,
dan kompatibilitas modul Lunaris masih belum terbukti. File yang disiapkan
untuk dibagikan karena itu tetap **bukti kompilasi, bukan ZIP installer**;
`Image.gz.DO-NOT-FLASH` adalah kernel mentah, bukan `boot.img`, dan jangan
langsung di-flash. Tidak ada flash, pengubahan perangkat, atau jaminan bebas
regresi dalam eksperimen ini.
