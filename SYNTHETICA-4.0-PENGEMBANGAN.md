# Synthetica 4.0 — pengembangan Linux 6.18

> **JANGAN FLASH.** Ini pekerjaan pengembangan dan bukti kompilasi, bukan
> Synthetica 4.0 lengkap, `boot.img`, ZIP recovery, atau pengganti kernel pada
> ponsel. Jangan memasang sampel modulnya. Belum ada uji boot Joyeuse, ROM,
> AVB, root, penyimpanan terenkripsi, radio, kamera, suspend, atau perangkat.

## Dasar dan ruang lingkup

Resep eksperimen menggunakan **Linux 6.18.58 yang nyata**, dari
[`7829hw/linux-miatoll-6.18@76e733e54156`](https://github.com/7829hw/linux-miatoll-6.18/tree/76e733e54156ad08cef3926e46c5ad25e2a5cc52).
Pohon ini menyertakan DTS Joyeuse Tianma dan Huaxing; itu bukan bukti boot
Joyeuse. Uji perangkat dan sebagian uji Android yang dilaporkan upstream
berasal dari **curtana** dan konfigurasi yang berbeda. Bring-up Android dan
beberapa fitur perangkat kerasnya masih belum lengkap. Ini bukan ACK/GKI
`android17-6.18` dan bukan kernel 4.14 yang diganti nama.

Eksperimen ini **tidak menggunakan** kandidat 3.2 berbasis 2.0 yang ditolak.
Baseline fitur yang dibandingkan adalah Synthetica 3.1 / 3.2-r1; resep dan
Manager sebelumnya tetap ada, tidak diganti atau dihapus. Hasil baru **belum
memenuhi** seluruh baseline, sehingga tidak dipasarkan sebagai upgrade.

Pin commit, SHA-256 arsip, toolchain dan detail identitas ada di
[`inputs.json`](build-kit/ci/synthetica40/inputs.json). Source diambil ke
scratch, diverifikasi dan disalin ke pohon kerja terpisah. Konfigurasi
menggabungkan fragment upstream SM7125, miatoll, LineageOS dan
[`experimental.config`](build-kit/ci/synthetica40/experimental.config); semua
permintaan konfigurasi efektif diperiksa setelah `olddefconfig`. Resep:

- [`build_synthetica40.py`](build-kit/scripts/build_synthetica40.py)
- [`build_synthetica40_kernel.sh`](build-kit/scripts/build_synthetica40_kernel.sh)
- [`synthetica40-kernel-dev.yml`](.github/workflows/synthetica40-kernel-dev.yml)
- [`test_synthetica40.py`](tests/test_synthetica40.py),
  [`test_s40_guard.py`](tests/test_s40_guard.py), dan
  [`test_s40_apk_guard.py`](tests/test_s40_apk_guard.py)

## Fitur yang sedang dikerjakan dan hambatannya

| Bidang | Keadaan eksperimen; bukan bukti runtime |
| --- | --- |
| KernelSU-Next | Source 3.4.2 UAPI **5** diintegrasikan ke resep. UAPI 5 tidak otomatis cocok dengan Manager dan `ksud` Synthetica 5.0.1 UAPI **4**; migrasi ketiganya dan uji root masih diperlukan. |
| Identitas Manager | Paket dan digest sertifikat publik lama dipin. Parser tanda tangan KSUN diadaptasi untuk sertifikat 1.381-byte dengan batas dan pemeriksaan hash tetap aktif; tidak menerima sembarang sertifikat. **Sertifikat sama saja tidak membuat UAPI cocok.** Parser 3.4.2 juga menolak blok signing tambahan yang tidak dikenal; APK referensi lama mempunyai blok v3 selain v2. Kompatibilitas APK nyata masih harus ditangani dengan aman dan diuji; pemeriksaan tidak dilonggarkan. |
| Manager 5.0.1 | Resep dan APK lama tetap UAPI 4. Prototipe **source-only/unsigned** mempertahankan overlay multi-tema dan memasang JNI/header serta `ksud` UAPI 5 yang dipin; ini belum membuktikan migrasi runtime, fitur, kompatibilitas APK, atau kemampuan upgrade. Upgrade in-place tetap membutuhkan kunci penandatangan asli dan versionCode yang lebih tinggi. |
| SUSFS 2.4.0 | **Belum terintegrasi.** Patch resmi `a2165b6f` memang versi 2.4.0, tetapi patch kernel 6.1 dan glue KSU-nya gagal `git apply --check` pada 6.18 dan KSUN 3.4.2 yang dipin. Harus di-port dan diuji, termasuk UID priority filter `0x60030`, hook VFS, `ksu_susfs`, SELinux dan interaksi root/NoMount. Mengubah label versi atau memasang LKM GKI bukan solusinya. |
| NoMount | Source NoMount 2.2.0 dipin dan dihubungkan built-in, dengan tool `nm` dari commit yang sama. Enum perintah, struktur payload dan magic kernel/userspace dibandingkan; protokolnya **22**, berbeda dari protokol 20 r1. Flag upstream `-fno-stack-protector` untuk driver dihapus agar tidak mengurangi proteksi stack build. Konfigurasi dan kompilasi bukan bukti bahwa redirection, UID isolation atau WebUI bekerja. Modul/metamodule userspace belum dipaketkan sebagai release. |
| MGLRU / UCLAMP | MGLRU default aktif dan UCLAMP diminta pada source 6.18. Ini bukan jaminan bahwa implementasi, antarmuka tuning atau perilaku patch MGLRU 3.1/r1 identik. |
| Scheduler | WALT vendor 4.14 tidak tersedia di source mainline ini. Tidak diklaim dipertahankan; pengganti atau port, antarmuka Control/Boost dan uji performa masih terbuka. |
| zRAM / filesystem | LZO, LZ4, LZ4HC dan ZSTD serta default LZO diminta; ZRAM_DEDUP milik baseline belum dipertahankan. EROFS, F2FS, fscrypt, verity, overlayfs dan inline encryption diminta. `DM_DEFAULT_KEY` vendor serta wrapped-key/FBE ROM belum terbukti tersedia/kompatibel. Opsi sama tidak berarti data lama bisa didekripsi. |
| Keamanan modul / SELinux | Konfigurasi meminta SELinux, seccomp, stack protector, modversions dan signature enforcement SHA-512. Modul contoh bertanda tangan dengan **kunci sementara build**, bukan kunci ROM; tidak membuktikan modul vendor dapat dimuat atau dipercaya. Perbedaan ABI/security policy tetap menjadi blocker. |

## Kemajuan validasi awal

- Konfigurasi lokal hasil gabungan lolos **599 permintaan efektif**. Tracepoint
  `sys_enter` yang dibutuhkan KernelSU kini benar-benar diaktifkan, bukan hanya
  mengandalkan `HAVE_SYSCALL_TRACEPOINTS`.
- Driver NoMount dan KernelSU-Next serta SELinux berhasil dikompilasi menjadi
  objek ARM64 secara lokal. Resep sekarang membangun SELinux terlebih dahulu
  untuk menghindari race pada header yang dihasilkan. Ini **belum** kompilasi
  kernel penuh atau uji boot. Kompilasi awal menggunakan LLVM 23.1.5 dan shim
  `m4` lokal yang belum tervalidasi; bukan bukti build Neutron/release.
- Sembilan uji source/parser dan lima uji guard/alur build lulus secara lokal,
  termasuk simulasi urutan dan kegagalan prebuild SELinux. Satu uji tambahan
  menjalankan parser C KSUN yang disiapkan terhadap layout APK referensi 2.0:
  parser **menolak** APK tersebut yang memiliki blok v2 dan v3. Fixture yang
  blok v3-nya dibuang hanya untuk pengujian dapat melewati parser, tetapi sudah
  berubah dan **bukan APK bertanda tangan valid**; jangan dipasang. I/O dan
  fungsi hash pada uji ini disimulasikan. Ini bukan pengujian penerimaan APK
  di kernel/Android nyata, dan tidak membenarkan pelonggaran parser keamanan.
- CI [42545132387](https://github.com/dwp29/Syntenthica/actions/runs/42545132387)
  gagal pada tracepoint di commit sebelumnya. Run tersebut menggunakan resep
  sebelum perbaikan tracepoint dan urutan SELinux; hasilnya tidak boleh dianggap
  bukti untuk resep yang diperbarui.

## Bukti kompilasi 6.18.58

CI [42545930921](https://github.com/dwp29/Syntenthica/actions/runs/42545930921)
berhasil untuk commit `c9d2248bda9d376da9a92748415b590017eacc20`: Image,
empat DTB curtana/Joyeuse, 200 modul yang terpasang ke scratch, dan CLI NoMount
arm64 dikompilasi dengan Neutron yang dipin. CI memeriksa arsitektur, vermagic,
dan trailer tanda tangan 200 modul; itu **bukan** verifikasi kriptografi
terhadap semua 200 modul atau uji pemuatan. Build terpisah
[42546928142](https://github.com/dwp29/Syntenthica/actions/runs/42546928142)
juga lulus pada commit `5aeeadf`; setiap build memakai kunci modul sementara,
sehingga image dan hash-nya tidak diharapkan identik.

| Bukti, bukan artefak flash | SHA-256 / nilai |
| --- | --- |
| ZIP `DO-NOT-FLASH` | `a39cb458c55b22d89d3e0981fd2834eafdbdce7c114671d242e1fccce67f16a2` |
| Image gzip | `20ee0d55f52a6333fbf45df9165d2a30739fca711a209e31cff58378f047635c` |
| Image tanpa kompresi | `9bac7d528a206204ba83a59c23d7b24a21810f46ff0cde13fb39cbcd19547608` |
| `module_layout` / simbol | `0xdd02b758` / 15.001 simbol ekspor |

Audit offline [`verify_s40_compile_evidence.py`](build-kit/scripts/verify_s40_compile_evidence.py)
lulus pada [CI 42548454635](https://github.com/dwp29/Syntenthica/actions/runs/42548454635).
Audit memeriksa whitelist ZIP, manifest, provenance, konfigurasi, struktur Image/DTB,
CLI, sertifikat publik di Image, serta **tanda tangan PKCS#7 dan CRC simbol tiga
modul contoh** `tcp_bic`, `tcp_htcp`, `tcp_westwood`. Tes negatif juga menolak
modul yang diubah meskipun checksum luar diperbarui. Sertifikat ini dibuat untuk
build tersebut, bukan bukti bahwa ROM mempercayainya. Audit tidak memverifikasi
kriptografi 197 modul lain dan tidak membuktikan kompatibilitas ABI vendor.
Pin dan hash bukti tersimpan di
[`compile-42545930921.json`](build-kit/ci/s40-evidence/compile-42545930921.json).
Artefak CI disimpan tujuh hari; blob Git yang tidak direferensikan juga tidak
dijamin disimpan permanen. Tidak ada `boot.img`, installer, ramdisk, atau private
key dalam bukti.

## Prototipe migrasi Manager UAPI 5

[`prepare_s40_manager_uapi5.py`](build-kit/scripts/prepare_s40_manager_uapi5.py)
menyalin source UAPI 4 yang dipin ke scratch, menerapkan overlay Manager 5.0.1,
kemudian mengganti dua header UAPI dan JNI `ksu.cc` dengan source KSUN 3.4.2.
`ksud` arm64 berasal dari **aset release upstream**, bukan hasil build source
lokal; ukuran dan SHA-256 `2771a2ae989b522b5d70f3288ad5a2f379488962d09c1fe11e13a745eba89362`
dipin sebelum disalin. Daftar pin dan provenance ada di
[`inputs.json`](build-kit/ci/manager-uapi5-dev/inputs.json). Resep membuat
hanya source dan, bila diminta, APK **unsigned** di scratch. CI
[`s40-manager-uapi5-dev.yml`](.github/workflows/s40-manager-uapi5-dev.yml)
mengekspor diagnostik saja, bukan APK atau kunci.

Uji lokal membandingkan source 5.0.1 dengan prototipe: hanya delapan file yang
diperbolehkan berubah (dua header, JNI, daemon, dua file versi/output dan dua
label), sedangkan gate `kernelUAPIVersion == managerUAPIVersion` tetap utuh.
Uji kompilasi host menjalankan fungsi JNI baru dengan flag support simulasi;
ini bukan pengujian ioctl atau root perangkat. `EVENT_SERVICES` dan flag
feature UAPI 5 memerlukan `ksud` yang sesuai dan pengujian runtime. Source
`ksud` 3.4.2 juga secara eksplisit menolak blok v3/v3.1; mengganti daemon saja
**tidak** menyelesaikan blocker penandatanganan APK. Prototipe belum signed,
belum dapat dipasang sebagai update, dan belum terbukti kompatibel dengan kernel
lama maupun kernel baru. Jangan pasang dan jangan gunakan kunci produksi untuk
memaksakan pengujian ini.

CI Manager [42546928237](https://github.com/dwp29/Syntenthica/actions/runs/42546928237)
berhasil mengompilasi prototipe tetapi **gagal** saat verifikasi: Android Gradle
mengubah ukuran `ksud` saat packaging. Perbaikan `keepDebugSymbols` mempertahankan
byte daemon; CI berikutnya
[42547583829](https://github.com/dwp29/Syntenthica/actions/runs/42547583829)
**berhasil** membangun dan memeriksa identitas paket, versionCode, ABI, hash
`ksud`, alignment, izin dan status unsigned. CI hanya menyimpan diagnostik,
bukan APK. Hasil ini tetap bukan uji instalasi atau runtime.

CI fixture [42549101585](https://github.com/dwp29/Syntenthica/actions/runs/42549101585)
lulus untuk [`probe_s40_apk_signing.py`](build-kit/scripts/probe_s40_apk_signing.py).
APK **sintetis** v2-only dan v2+v3 ditandatangani dengan kunci sementara dan
keduanya lolos verifikasi `apksigner`. Parser C kernel yang disiapkan dan parser
Rust `ksud` masing-masing menerima v2-only dan menolak v2+v3; parser C juga
menolak hash sertifikat yang salah. Pada fixture yang isinya diubah, `apksigner`
menolak tanda tangan, tetapi parser sertifikat C masih menerimanya: parser ini
**bukan verifikator integritas APK** dan bergantung pada pemeriksaan Android.

Ini harness **host**, dengan shim I/O/crypto dan sertifikat uji, bukan kernel
atau Android yang berjalan. Kunci dan APK fixture tidak diekspor; CI menyimpan
laporan saja. Hasilnya tidak membuktikan upgrade Manager lama, penerimaan APK
di perangkat, keamanan otorisasi root, atau kompatibilitas ROM dan perangkat.

Pengujian berikutnya memperluas fixture tersebut ke prototipe Manager UAPI 5
hasil build yang sebenarnya: APK unsigned diperiksa dahulu, lalu ditandatangani
dengan kunci sementara **di scratch** untuk menguji v2/v3, payload dan alignment.
Hasilnya baru dapat diklaim setelah CI selesai; kunci sementara tidak cocok
dengan identitas yang dipin pada kernel dan tidak dapat menjadi upgrade in-place
atas Manager lama. Tidak ada APK atau kunci yang akan diekspor.

## Pemetaan ABI SUSFS 2.4

Audit sumber [`audit_s40_susfs_abi.py`](build-kit/scripts/audit_s40_susfs_abi.py)
memeriksa source yang dipin dan mengompilasi **deklarasi struct yang diekstrak**
untuk target arm64 kernel dan Android, tanpa syscall atau memuat modul. Audit
lulus lokal dan pada [CI 42549978945](https://github.com/dwp29/Syntenthica/actions/runs/42549978945):
16 command aktif `ksu_susfs` 2.4 cocok dengan nomor dan daftar dispatcher
patch kernel 2.4; ukuran, alignment dan offset 13 payload cocok; 12 bit KSTAT dan
lima nilai `UID_SCHEME` cocok. Payload UID priority `0x60030` berukuran 65.540
byte pada arm64, dengan `err` di offset 65.536. Ini memeriksa ABI deklarasi,
bukan implementasi, kondisi compiler aktual, atau perilaku runtime.

Arsip KSUN 3.4.2 memang membawa source **LKM terpisah** beridentitas 2.3.0,
tetapi parent Kbuild KSUN yang dipakai resep tidak membangunnya. Dispatcher LKM
itu tidak menangani command priority 2.4, dan field `is_statically` pada payload
KSTAT-nya adalah `int` 4 byte, sedangkan source userspace/kernel 2.4 memakai
`bool` 1 byte. Offset field berikutnya tetap sama; perbedaan ini perlu diuji,
bukan otomatis dinyatakan pasti gagal. LKM dan KSUN juga menargetkan simbol
reboot arm64 yang sama, meski magic keduanya berbeda; interaksi hook dan NoMount
belum diuji. Karena itu source LKM ini **bukan pengganti SUSFS 2.4** dan tidak
boleh dipasang atau sekadar diganti nomor versinya.

### Race priority filter yang perlu ditangani sebelum port

Model host [`probe_s40_susfs_priority.py`](build-kit/scripts/probe_s40_susfs_priority.py)
menjalankan fungsi setter, worker, parser dan lookup yang diekstrak dari source
2.4 yang dipin. Pada interleaving terjadwal, worker mengambil snapshot daftar
lama, setter menerbitkan daftar baru, lalu worker menimpa bitmap baru dengan
hasil lama. Daftar nama yang tersimpan dan bitmap dapat berbeda sampai refresh
berikutnya. I/O packages list, credential, user copy dan RCU disimulasikan;
ini **bukan** reproduksi pada kernel atau ponsel. Model dan pengujian guard
lulus pada [CI 42550360156](https://github.com/dwp29/Syntenthica/actions/runs/42550360156).

Kandidat [`research-only-priority-generation.patch`](build-kit/ci/s40-susfs-abi/research-only-priority-generation.patch)
menolak publikasi snapshot yang generasinya sudah usang dan lolos interleaving
yang sama dalam model lokal. Patch hanya diterapkan ke salinan scratch untuk
pengujian, **belum** menjadi bagian kernel 4.0. Guard sempit itu belum membuktikan
seluruh perilaku konkurensi/RCU, fault, keamanan SELinux, atau bahwa refresh
instalasi/uninstall tidak terlewat saat perubahan konfigurasi berulang; semua
itu tetap perlu dirancang dan diuji sebelum port dipakai.

## Interpretasi bukti

Jika CI berhasil, arsip buktinya hanya berisi image dan DTB dengan nama
`DO-NOT-FLASH`, konfigurasi, simbol, sertifikat publik, beberapa modul
`DO-NOT-LOAD`, dan metadata. Tidak ada installer, boot image lengkap, ramdisk,
private key, atau klaim kompatibilitas. Key penandatangan modul dibuat per
build dan tidak diekspor, sehingga byte image tidak dijanjikan identik antar
build. Static check terhadap vermagic dan trailer tanda tangan bukan uji
pemuatan modul maupun trust ROM.

Status build serta hasil uji spesifik dicatat setelah CI selesai. Build yang
berhasil pun **tidak** mengubah semua hambatan di atas menjadi selesai.
