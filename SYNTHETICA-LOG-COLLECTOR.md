# Synthetica Log Collector 1.0

Collector ini adalah ZIP diagnostik terpisah untuk dijalankan setelah kegagalan instalasi kernel atau ketika masuk kembali ke recovery setelah bootloop. ZIP ini **bukan kernel, modul, pembetulan error, atau recovery**. Ia tidak mengubah ZIP/kernel 3.0 yang sudah dibagikan.

## Keselamatan dan privasi

- Tidak melakukan flash, mount/decrypt otomatis, format/wipe, reboot, mengubah bootloader/AVB, mengunggah data, atau memasang layanan. Ia menulis folder laporan dan, bila tersedia, arsip `.tar.gz` di storage yang sudah ter-mount dan dapat ditulis; storage tersebut bisa berupa partisi userdata/SD/USB. Jika tidak ada, laporan ditempatkan di `/tmp` recovery yang **hilang saat reboot**.
- Properti `getprop`, `build.prop` dan cmdline dibatasi ke daftar metadata terpilih. Header boot dibaca hanya untuk angka format/ukuran; image boot, ramdisk, kunci atau partisi mentah tidak disalin. Tidak ada daftar aplikasi atau file pengguna yang sengaja dikumpulkan.
- **Log mentah** recovery, logcat, dmesg, last_kmsg, pstore dan log installer tetap bisa mengandung serial, nama file/aplikasi, alamat jaringan, akun, token atau informasi pribadi lain. Tidak ada klaim redaksi lengkap. Tinjau sebelum membagikan, dan kirim hanya secara privat.
- Tidak semua recovery mendukung ZIP shell tidak bertanda tangan, akses ADB, logd, pstore, tools bawaan atau storage terenkripsi. Sebagian input mungkin kosong, tidak tersedia, tidak bisa dibaca, terpotong atau timeout; `STATUS.tsv` membedakannya. Tidak adanya log crash bukan bukti bahwa tidak ada crash.

## Penggunaan singkat

Panduan lengkap tersedia sebagai `README-ID.txt` di dalam ZIP dan pada `build-kit/ci/log-collector/README-ID.txt`.

1. Bila install kernel menghasilkan Error 1, **jangan ulangi flash**. Tetap di recovery dan simpan log asli melalui fitur recovery Copy/Save Log atau `adb pull /tmp/recovery.log recovery-sebelum-collector.log` terlebih dahulu bila tersedia. Menjalankan ZIP baru dapat menambah/mengganti recovery log atau `last_install`.
2. Jika aman dan custom recovery mendukungnya, pilih Install dan jalankan ZIP **collector** ini; bukan kernel dan bukan modul Manager. Catat lokasi `Archive:`/`Report folder:` yang muncul. Stock recovery dapat menolak ZIP unsigned; jangan melemahkan verifikasi untuk menjalankannya.
3. Ambil arsip `.tar.gz` atau seluruh folder; bila muncul `TEMPORARY /tmp`, jalankan `adb pull /tmp/Synthetica-logs ./Synthetica-logs` sebelum reboot. Recovery berbeda dapat memblokir ADB atau akses file; cara lain adalah fitur file manager/Copy Log atau storage eksternal yang sudah dimount sendiri.
4. Jika install gagal **saat menulis atau memverifikasi boot**, jangan reboot; pulihkan backup boot yang tepat di recovery. Jika bootloop, kembali ke recovery secepat mungkin, ambil log bila aman, kemudian pulihkan backup yang benar untuk device/ROM/slot. Jangan wipe data, mengubah vbmeta, atau menebak image/slot untuk memaksa boot.

Metode ADB tanpa menjalankan ZIP, jika recovery menyediakan shell:

```text
adb push collector.sh /tmp/synthetica-collector.sh
adb shell sh /tmp/synthetica-collector.sh
```

`collector.sh` bisa diekstrak dari ZIP. Ini tetap bergantung pada shell, tools, izin dan storage di recovery.

## Informasi yang diperlukan untuk diagnosis

Minta model/codename perangkat, ROM dan versi Android, jenis/versi recovery, slot bila ada, cara instalasi (recovery/Manager), nama dan SHA-256 ZIP kernel, seluruh pesan error/foto, serta laporan collector dan salinan recovery log awal. Jangan minta serial, IMEI, akun, password, kunci, atau image mentah. **Error 1 adalah kode generik**, bukan penyebab spesifik.

Synthetica 3.0 yang sebelumnya dibagikan memakai pemeriksaan untuk joyeuse/miatoll, boot tanpa A/B, ukuran dan format boot, DTB referensi, bootloader dan ramdisk. Kegagalan di device/ROM lain bisa saja merupakan penolakan keselamatan yang disengaja, tetapi penyebab kasus ini **belum diketahui tanpa log**. Jangan hilangkan pemeriksaan tersebut, menebak kompatibilitas dari versi Android saja, atau menyatakan perangkat lain didukung berdasarkan collector.

## Struktur dan pengujian

- `build-kit/ci/log-collector/collector.sh`: payload shell mandiri yang sama untuk recovery dan ADB.
- `build-kit/scripts/package_log_collector.py`: build deterministik, menolak overwrite dan memverifikasi daftar isi, mode dan CRC ZIP; hanya script dan panduan, tanpa kernel/native binary.
- `tests/test_synthetica_log_collector.py`: filesystem recovery palsu; menguji Error 1, pstore/last_kmsg, properti, header palsu, ukuran log, symlink, fallback `/tmp`, protokol output recovery, timeout dan larangan perintah mutasi.
- `tests/run_collector_android_emulator.py` dan `.github/workflows/synthetica-log-collector.yml`: menjalankan shell collector pada emulator Android dengan filesystem dan isi log palsu, **bukan** pengujian custom recovery atau perangkat fisik.
- Dilarang menyamakan sukses simulasi dengan keberhasilan recovery, kemampuan mengambil crash log, kompatibilitas flash, atau pembuktian penyebab bootloop.

Validasi 7 November 2026: suite host keseluruhan menjalankan 237 tes, 17 di-skip; 17 tes khusus collector lulus. [CI 42381698938](https://github.com/dwp29/Syntenthica/actions/runs/42381698938) lulus untuk fixture host serta shell emulator Android 35 x86_64. Kedua job mengemas ZIP dengan SHA-256 `47de133c4aa4c48a71dad40094eb7e01215abd6dd11fc8f10906433bd4213726`, sama dengan ZIP yang disiapkan untuk dibagikan. Emulator hanya memakai data buatan, **tidak menjalankan custom recovery**, tidak mensimulasikan flash atau bootloop nyata, dan belum ada pengujian pada perangkat fisik.

Collector lama di `release/Synthetica-2.0-LOG.zip` adalah artefak historis. Ia memiliki perilaku dan klaim privasi yang berbeda; untuk prosedur ini gunakan collector 1.0 baru dan panduannya.
