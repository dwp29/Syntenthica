# Perbandingan Synthetica 2.0 dan 3.0 — installer dan dasar kernel

**Lingkup:** pemeriksaan statis atas dua ZIP yang tepat, bukan pemasangan ke
perangkat. Pengguna melaporkan 2.0 hampir selalu boot di berbagai ROM/varian;
identitas ZIP, ROM, dan hasil pada setiap perangkat tersebut belum semuanya
diverifikasi secara independen. Nama perangkat yang dikenali installer bukan
bukti bahwa kernel, modul, DTB atau AVB cocok pada perangkat itu.

## Paket yang dibandingkan

| Paket | SHA-256 ZIP | Sumber pemeriksaan |
|---|---|---|
| `release/Synthetica-2.0.zip` | `b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c` | ZIP rilis 2.0 di repositori, CRC semua entri diperiksa |
| `synthetica-3.0.zip` | `16b32f57381005c08cbee0ec684397dc91acc77f5b2ccbb4ef7f4b99a9a791e6` | ZIP kandidat 3.0 asli dari Drive, CRC semua entri diperiksa |

Ini **bukan** perbandingan dengan `Synthetica-2.0-EXP-Neutron-MGLRU-on-TEST`.
Eksperimen 2.0 tersebut adalah paket berbeda yang sudah memakai guard mirip
3.0. Jika ZIP 2.0 yang digunakan oleh penguji ternyata berbeda hash, perlu
membandingkan ZIP itu juga. Tidak ada skrip dari ZIP di atas yang dijalankan
pada ponsel dan tidak ada partisi ponsel yang dibaca atau ditulis.

## Perbedaan installer

| Hal | Synthetica 2.0 rilis | Synthetica 3.0 asli |
|---|---|---|
| Nama device | `miatoll`, `curtana`, `excalibur`, `gram`, `joyeuse` | `joyeuse`, `miatoll` |
| Versi Android | `supported.versions` kosong; tidak ada filter versi Android eksplisit | Sama: kosong |
| Tool utama | AnyKernel3 `dump_boot`/`write_boot` dan `ak3-core.sh` | Custom writer dan `prepare-boot.sh`, memakai backend AnyKernel3 |
| BusyBox/MagiskBoot | Identik byte demi byte dengan versi di ZIP 3.0 | Identik dengan 2.0; yang berbeda adalah alur dan persyaratannya |
| DTB boot | ZIP tidak membawa DTB. Jalur normal memilih DTB hasil split boot tanpa mengharuskan satu hash tertentu; cabang Magisk **dapat mem-patch DTB** | Tidak membawa DTB. Hanya menerima DTB dengan SHA-256 `6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239`, lalu memeriksa bahwa byte DTB hasil repack sama |
| Partisi DTBO | ZIP tidak membawa `dtbo`/`dtbo.img`; fungsi generik `flash_generic dtbo` tidak punya file input untuk ditulis | Tidak membawa atau langsung menulis DTBO |
| Ramdisk | Di-unpack dan dikemas ulang. Tidak ada pembandingan byte setelah repack; jalur Magisk dapat mengubah perilaku patching | Menolak ramdisk Magisk/tidak dikenal dan membandingkan byte ramdisk sebelum/sesudah repack |
| `ksud` dan `/data` | Jika `/data/adb` dapat diakses, skrip mencoba me-remount `/data` read-write dan menyalin `ksud` ke `/data/adb/ksud` **sebelum** `dump_boot`/`write_boot` | Writer tidak memasang `ksud` atau modul; backend asli tetap menjalankan `setup_env`/`mount_all`, sehingga tidak dapat dijamin seluruh filesystem tidak pernah di-mount read-write |
| Validasi dan penulisan | Memeriksa identitas device, melakukan split/repack, dan memeriksa ukuran hasil. Tidak ada allowlist hash DTB, pemeriksaan unlock/slot yang setara dengan 3.0, atau pembacaan balik byte hasil tulis yang setara | Memeriksa unlock, slot yang terdeteksi, ukuran/read-only partisi boot, boot-v2, AVB metadata struktural, hash kernel/DTB, ramdisk, komponen hasil repack, dan membandingkan hasil tulis terhadap image kandidat |
| Backup dan reboot | Tidak ada backup boot otomatis; tidak auto-reboot | Sama |
| AVB | `PATCH_VBMETA_FLAG=auto`; ada cabang patch terkait Magisk. Efek aktual tergantung kondisi dan format boot | Menjaga byte metadata AVB yang diperiksa; **tidak** memverifikasi validitas signature setelah kernel berubah |

Pemeriksaan device AnyKernel membaca beberapa properti recovery dan menerima
jika salah satunya cocok; `miatoll` adalah nama keluarga/unified, bukan satu
model fisik. Keduanya memilih path boot `/dev/block/bootdevice/by-name/boot`;
2.0 menyetel `IS_SLOT_DEVICE=0` dan tidak membuktikan perangkat tidak memiliki
slot. Ruang lingkup versi Android kosong **tidak** menjamin semua Android atau
ROM bisa boot.

**Koreksi catatan historis 2.0:** `release/STATUS.json` dan
`artifacts/ARTIFACTS-MANIFEST.txt` menyebut backup boot otomatis, sedangkan
`release/RELEASE-INFO.json` menyebut tidak ada penulisan `/data`. Isi installer
ZIP yang diperiksa bertentangan dengan kedua klaim itu: tidak ada backup boot
otomatis, dan `ksud` dapat ditulis ke `/data/adb/ksud`. Catatan build historis
dibiarkan utuh sebagai arsip; untuk perilaku paket ini rujuk skrip di dalam ZIP
serta koreksi ini. Jangan mengandalkan backup otomatis.

## Dasar kernel dan modul

- Keduanya menggunakan basis source yang dipin di
  [`Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795`](https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/tree/c1e6f795b557b7bf92220c91f05a42b456de7a74),
  tetapi image dan resep build-nya **tidak identik**. Banner 2.0 menunjukkan
  Ubuntu Clang 18.1.3; 3.0 menunjukkan Neutron Clang 24.0.0git.
- Membandingkan `artifacts/generated.config.txt` yang dicatat pada build 2.0
  dengan konfigurasi yang benar-benar tertanam di image 3.0 menghasilkan
  delapan perbedaan setelah opsi hilang/nonaktif dinormalisasi: `LOCALVERSION`,
  `LRU_GEN`, `LRU_GEN_ENABLED`, `NR_LRU_GENS`, `TIERS_PER_GEN`,
  `UCLAMP_BUCKETS_COUNT`, `UCLAMP_TASK`, dan `UCLAMP_TASK_GROUP`. Ini bukan
  daftar seluruh perubahan source: 3.0 juga memakai backport MGLRU/Uclamp dan
  patch khusus Manager. Keduanya mencatat `MODVERSIONS=y` dan
  `MODULE_SIG_FORCE=y`; tidak ada bypass yang disarankan.
- Konfigurasi **tertanam** dalam image rilis 2.0 ternyata sama byte demi byte
  dengan `arch/arm64/configs/vendor/stock_defconfig` pada source yang dipin
  (SHA-256 `8188e2539466a3e6797e98dd704b4b5a8e6439b21c08ba8d2a82b2829a8b190d`),
  bukan konfigurasi 2.0 yang direkam saat build (SHA-256
  `248af9218b5ed9dd82202956d99991f97428c3010565a810eac3c9e6f71ff33b`).
  Aturan `kernel/Makefile` source lama memang menunjuk ke `stock_defconfig`.
  Karena itu jangan menyimpulkan opsi kernel 2.0 dari IKCONFIG yang tertanam
  saja. Jalur build 3.0 memperbaiki aturan tersebut dan memverifikasi bahwa
  konfigurasi tertanam cocok dengan konfigurasi build.
- Audit 2.0 sebelumnya merekonstruksi CRC `module_layout` `0x08efcbb0` untuk
  image rilis 2.0. `Module.symvers` build yang tepat untuk 3.0 ini menunjukkan
  `0xed5659d1` dan sertifikat modul publik SHA-256
  `fccecddc68e8828ff42c59be08f3aca01baf1f07e9caf8369ce69e8fad4bd062`.
  Perbedaan CRC dan sertifikat per build berarti keberhasilan 2.0 tidak
  menjamin modul vendor pada ROM yang sama diterima oleh 3.0. Tidak ada modul
  ROM aktual milik penguji Infinity yang diperiksa dalam audit ini.

## Apa arti temuan ini untuk Error 1?

Installer 2.0 dapat **melanjutkan lebih jauh** pada nama device dan DTB yang
3.0 asli tolak; ini masuk akal sebagai salah satu penjelasan perbedaan
pengalaman. Dalam log Lunaris yang sudah diperiksa, 3.0 memang menolak DTB
sebelum menulis boot. Penyebab Error 1 pada Infinity dan tiga laporan lain
belum diketahui. Lolos installer juga tidak sama dengan berhasil boot atau
berfungsinya semua driver/modul.

Arah perbaikan adalah mengambil **cakupan nama device 2.0**, tetapi bukan
menyalin installernya secara buta. Kandidat kompatibilitas 3.0 yang sudah ada
mengakui lima nama yang sama dan menghindari mount oleh backend, sambil tetap
mempertahankan pemeriksaan slot, unlock, boot, ramdisk, DTB, integritas dan
readback. Kandidat itu **belum layak flash luas**: ia masih menerima satu hash
DTB referensi, dan belum lulus uji recovery/boot fisik. Menambah dukungan DTB
memerlukan profil dan bukti perangkat/ROM yang relevan; jangan secara otomatis
menimpa DTB/DTBO ROM atau menonaktifkan AVB untuk memaksa boot.

Uji regresi perbandingan ada di `tests/test_synthetica3_compat.py`; paket 2.0
serta ZIP 3.0 asli diverifikasi hash-nya sebelum dipakai. Rangkaian lokal
lulus **272 tes, 38 dilewati** dengan ZIP dan bukti build 3.0 yang dipin;
uji runtime memakai fixture/file sementara, bukan perangkat. Laporan
investigasi 3.0 lainnya ada di `SYNTHETICA-3.0-MIATOLL-AUDIT.md`.
