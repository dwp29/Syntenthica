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
- [`test_synthetica40.py`](tests/test_synthetica40.py)

## Fitur yang sedang dikerjakan dan hambatannya

| Bidang | Keadaan eksperimen; bukan bukti runtime |
| --- | --- |
| KernelSU-Next | Source 3.4.2 UAPI **5** diintegrasikan ke resep. UAPI 5 tidak otomatis cocok dengan Manager dan `ksud` Synthetica 5.0.1 UAPI **4**; migrasi ketiganya dan uji root masih diperlukan. |
| Identitas Manager | Paket dan digest sertifikat publik lama dipin. Parser tanda tangan KSUN diadaptasi untuk sertifikat 1.381-byte dengan batas dan pemeriksaan hash tetap aktif; tidak menerima sembarang sertifikat. **Sertifikat sama saja tidak membuat UAPI cocok.** Parser 3.4.2 juga menolak blok signing tambahan yang tidak dikenal; APK referensi lama mempunyai blok v3 selain v2. Kompatibilitas APK nyata masih harus ditangani dengan aman dan diuji; pemeriksaan tidak dilonggarkan. |
| Manager 5.0.1 | Multi-tema, Device Check, profil, modul/WebUI dan Control/Boost tetap ada pada resep lama, **belum dimigrasikan** ke backend UAPI 5. Upgrade in-place tetap membutuhkan kunci penandatangan asli dan versionCode yang lebih tinggi. |
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
  termasuk simulasi urutan dan kegagalan prebuild SELinux. Uji parser
  menjalankan kode C yang diadaptasi dengan I/O dan kripto simulasi; ini tidak
  membuktikan bahwa APK diterima oleh kernel nyata.
- CI [42545132387](https://github.com/dwp29/Syntenthica/actions/runs/42545132387)
  menggunakan commit sebelumnya, sebelum perbaikan tracepoint dan urutan
  SELinux. Hasilnya tidak boleh dianggap bukti untuk resep yang diperbarui.

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
