# Synthetica 2.0 — eksperimen Uclamp, MGLRU, dan Neutron

**Status: eksperimen pengembangan, bukan rilis atau paket flash.** Baseline 2.0,
APK Manager, dan resep yang digunakan 3.0 tidak diganti. BakaSU tidak dipasang.
Hasil build yang berhasil sekalipun hanya bukti kompilasi, bukan bukti aman untuk
perangkat atau kompatibel dengan modul vendor ROM.

## Cakupan dan default

| Komponen | Perlakuan eksperimen |
|---|---|
| WALT + SchedTune | Keduanya dipertahankan seperti konfigurasi 2.0 yang tersimpan. |
| Uclamp | Backport per-task dan CPU cgroup, dengan lima bucket; clamp default netral dan default boost RT tambahan 0. Pengaturan pengguna/ROM tetap bisa mengubah clamp. |
| MGLRU | Dikompilasi (`CONFIG_LRU_GEN=y`), tetapi **tidak diaktifkan saat boot** (`CONFIG_LRU_GEN_ENABLED=n`); statistik tambahan dimatikan. Pengujian MGLRU aktif masih diperlukan. |
| Thermal, frekuensi dan root | Tidak ada patch thermal, overclock, bypass signature modul, atau perubahan implementasi KernelSU-Next/Manager. Penjagaan konfigurasi menolak perubahan lain dari konfigurasi 2.0 tersimpan. |
| Neutron | Calon compiler dipin ke tag `06092026`, Clang `24.0.0git`, arsip SHA-256 `531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30`. CI membandingkan build yang sama dengan LLVM 18; itu bukan benchmark. |

MGLRU ditahan dalam keadaan runtime off karena perubahan MM 4.14 luas dan donor
melaporkan hang saat idle/charging pada versi terdahulu. Runtime off tidak
menghapus semua risiko: struktur kernel dan ABI tetap berubah. Kode Uclamp
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
perbaikan-perbaikan itu bukan jaminan backport sudah lengkap.

Build awal CI `42237485378` gagal: LLVM 18 menemukan definisi `ANON_AND_FILE`
yang hilang dari backport MGLRU; Neutron berhenti pada pemeriksaan karena paketnya
tidak menyertakan `llvm-size`. Keduanya ditangani di resep eksperimen: perbaikan
donor untuk definisi MGLRU ditambahkan, dan binary `aarch64-linux-gnu-size` host
digunakan hanya bila `llvm-size` tidak ada. Compiler dan linker tetap dari
toolchain yang dipilih. Kode build awal juga mengandung bug Uclamp yang sudah
dikoreksi pada patch lanjutan; jangan gunakan artefak run awal. Hasil build ulang
belum dapat dianggap berhasil sampai CI melaporkan kompilasi dan verifikasi lolos.

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
- `build-kit/ci/synthetica2-experimental/patches/` berisi diff source GPL yang dapat diperiksa; `features.config` adalah fragment eksperimen. Tidak ada source tree besar atau toolchain binary yang dikomit.
- Workflow `.github/workflows/synthetica2-experimental.yml` membuat dua build terpisah: LLVM 18 dan Neutron. Arsip source dan Neutron diverifikasi sebelum dipakai. Builder disalin ke direktori sementara, diubah hanya dalam salinan itu, dan dihentikan sebelum bagian AnyKernel/installer.
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
diberi nama `DO-NOT-FLASH`, konfigurasi, `System.map`, `Module.symvers`, dan
status; tidak memuat installer atau kunci privat. Enam modul yang dipilih oleh
konfigurasi 2.0 diperiksa terhadap CRC dan sertifikat dari build yang sama,
bukan diuji dimuat ke perangkat dan bukan validasi modul vendor ROM.

## Gerbang sebelum pengujian perangkat

1. Kedua build harus lolos kompilasi dan verifikasi konfigurasi/IKCONFIG; catat error tiap compiler secara terpisah.
2. Verifikasi perangkat/ROM, AVB, metode pemulihan, dan kompatibilitas seluruh modul vendor: vermagic, CRC `MODVERSIONS`, dan signer yang benar. Audit terdahulu menemukan ketidakcocokan modul vendor; jangan menonaktifkan pemeriksaan untuk memaksanya.
3. Setelah ada kandidat yang layak diuji, ukur boot, pengenalan Manager/root, kamera, jaringan, sleep/wake, idle sambil mengisi daya, tekanan RAM dan stabilitas lama.
4. Ukur performa, suhu dan baterai pada beban yang sama dengan baseline. MGLRU aktif dan clamp non-netral memerlukan pengujian terpisah; jangan diaktifkan hanya karena build berhasil.

Tidak ada flash, pengubahan perangkat, atau jaminan bebas regresi dalam eksperimen ini.
