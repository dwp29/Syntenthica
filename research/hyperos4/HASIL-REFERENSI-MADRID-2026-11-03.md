# Pembandingan metadata referensi Madrid — 3 November 2026

**Kandidat joyeuse 03 tetap HOLD / JANGAN FLASH.** Ini pembacaan metadata publik yang terbatas, bukan download atau pencangkokan image, pembuktian asal source port, validasi signature, atau uji perangkat.

## Referensi yang ditemukan

[Katalog pihak ketiga pada commit `aec2464`](https://github.com/XiaomiFirmwareUpdater/xmfirmwareupdater.github.io/blob/aec2464da65583892b2ac1a319fd583df1197d96/pages/hyperos/updates/madrid/OS4.0.17.0.XEOCNXM.md) mencantumkan paket `madrid-ota_full-OS4.0.17.0.XEOCNXM-user-17.0-c38824c8fe.zip` untuk **Xiaomi 18 Pro Max / madrid**, dengan MD5 yang diklaim `c38824c8fee14778a5049872f4511d9a`. Katalog mengklaim file berasal dari server Xiaomi; identitas pengirim, MD5 seluruh file dan signature **tidak diverifikasi** dalam probe ini. Kesesuaian nomor versi dengan properti yang telah terlihat pada port dan klaim pembuat port adalah petunjuk untuk ditelusuri, bukan bukti setiap file atau build manifest pembuatnya.

[Run 41570282521](https://github.com/dwp29/Syntenthica/actions/runs/41570282521), commit `aa61e5697f9edff74c53ae0d882022ed6d5ddc5d`, menjalankan 12 kontrol sintetis tanpa skip, lalu membaca **20 permintaan HTTP Range sejumlah 510.921 byte** dari objek yang melaporkan ukuran 12.431.011.865 byte. Tidak mengunduh payload utuh atau image. Server mendukung partial content; ETag dan Last-Modified ada dan konsisten selama pembacaan, tetapi keduanya bukan autentikasi isi.

- Metadata ZIP yang terbaca: `pre-device=madrid`, tipe OTA `AB`, `post-sdk-level=37`, `post-security-patch-level=2026-09-01`, dan `post-build-incremental=17OS4.0.260925.012628646.QCPECN.S`. CRC dua anggota metadata diperiksa terhadap central directory yang sama, bukan terhadap sumber tepercaya terpisah.
- Manifest payload berukuran **443.344 byte**, SHA-256 bytes yang dibaca `9c6e5593b75ec889dfff78f0b7456038d324a5d867447d19fa96c6105aed66b6`, memuat **66** nama partisi. Dekoder protobuf independen cocok dengan parser terbatas untuk subset nama, ukuran, hash, block size dan minor version. Field mengikuti [AOSP `update_metadata.proto` pada `4ff0491`](https://github.com/aosp-mirror-neo/platform_system_update_engine/blob/4ff049167edfe381966619f3123681f2e6c02138/update_metadata.proto).
- `METADATA_HASH` dan `METADATA_SIZE` yang diiklankan cocok dengan header dan manifest yang dibaca. Ini hanya konsistensi internal dari sumber yang sama; metadata signature, isi payload, SHA/MD5 keseluruhan dan identitas penandatangan **belum diverifikasi**.
- Upaya awal [41569455316](https://github.com/dwp29/Syntenthica/actions/runs/41569455316) berakhir **neutral/inconclusive** karena parser terlalu membatasi karakter nama partisi; dukungan titik dan tanda hubung ditambahkan dengan tes sebelum probe sukses. [41570011275](https://github.com/dwp29/Syntenthica/actions/runs/41570011275) lalu membaca metadata; run terakhir menambahkan dekoder protobuf independen dan dua image pembanding. `success` pada check berarti probe terbatas selesai, bukan ROM lolos.

## Pembanding terhadap kandidat 03

Kolom Madrid adalah **ukuran target yang diklaim manifest**, bukan hasil hash image yang diunduh. Kolom joyeuse diambil dari [snapshot extent](HASIL-POLICY-COMPAT-RUN-41485767990-2026-11-02.json) dan [hasil build 03](HASIL-BUILD-03-RUN-41477695884-2026-11-02.json) yang sudah dipin; `boot`/`dtbo` adalah anggota ZIP kandidat 03 yang sebelumnya dibaca dan CRC-nya diperiksa. [Data lengkap](HASIL-REFERENSI-MADRID-RUN-41570282521-2026-11-03.json).

| Objek | Joyeuse, byte terukur | Madrid, byte diklaim manifest |
|---|---:|---:|
| system extent | 1.732.870.144 | 977.055.744 |
| system_ext extent | 1.407.295.488 | 817.618.944 |
| product extent | 3.891.687.424 | 5.667.659.776 |
| vendor extent | 1.490.268.160 | 1.512.128.512 |
| boot ZIP member | 134.217.728 | 100.663.296 |
| dtbo ZIP member | 25.165.824 | 8.388.608 |

Enam ukuran berbeda, sehingga keenam **rentang byte utuh yang dibandingkan tidak identik sebagai representasi berukuran sama**. Extent yang dialokasikan dapat mencakup padding, sedangkan sisi Madrid adalah ukuran image target yang dideklarasikan. Perbedaan ini **tidak** membuktikan semua file berbeda, menentukan asal satu library, menyatakan penyebab boot gagal, atau menguji ABI. Hash target Madrid di JSON hanya klaim manifest dan tidak boleh disebut hash image yang telah diverifikasi.

Sumber framework/vendor serta manifest build yang terbukti menghasilkan port diza masih belum ditemukan. Tidak ada alasan untuk menyalin partisi Madrid ke joyeuse: ini perangkat berbeda, dan perbandingan metadata bukan verifikasi kompatibilitas. Jangan flash paket Madrid pada joyeuse.

## Klarifikasi unggahan pengguna dan policy

Laporan verifikasi yang sudah ada di Drive menyelesaikan pertanyaan ukuran 54 volume: `.z01`–`.z53` dan `.zip` total **4.489.218.289 byte** adalah ZIP64 luar terkompresi yang berisi `H0S4diza.zip`; ZIP dalam berukuran **4.512.854.711 byte**, SHA-256 `454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63`, identik dengan baseline yang diverifikasi. Perbedaan ukuran luar/dalam adalah kompresi, bukan bukti arsip berbeda. [Laporan verifikasi unggahan ulang](https://drive.google.com/file/d/1fuKPB3mS1NIMU4icUrFmiJiGD5UNn6Wb/view). Volume luar bukan ZIP instalasi individual; arsip besar tidak diunduh ulang untuk temuan ini.

Analisis ulang JSON policy terdahulu menunjukkan 290 **catatan** `neverallow` di kompilasi ketat berasal dari lokasi assertion yang dilaporkan sebagai `system.cil` 193, `vendor_public.cil` 87, `system_ext.cil` 7, dan `product.cil` 3. Hitungan ini bukan assertion unik dan lokasi assertion **bukan** pembuktian lokasi aturan penyebabnya. Mode pembanding `-N` exit 0 hanya melewati assertion kompilasi pada salinan host; ia tidak mematikan enforcement dan tidak membuktikan policy dipilih/dimuat atau perangkat boot. Tidak ada policy mentah yang diekspor atau dipasang.
