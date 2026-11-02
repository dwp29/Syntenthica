# Build 03 boot-first — perbaikan metadata OTA

**Tanggal:** 2 November 2026. **Hasil:** build terpisah dibuat, diuji di host, dan disimpan sebagai draf. **Status: HOLD / JANGAN FLASH.** Ini belum menyelesaikan kompatibilitas ROM atau membuktikan boot di Redmi Note 9 Pro joyeuse.

## Akses build

- [Draf build 03 di GitHub](https://github.com/dwp29/Syntenthica/releases/edit/431662583) — hanya akun yang berwenang pada repositori yang dapat mengakses draf. Draf tidak dipublikasikan.
- ZIP gabungan: `synthetica-boot-first-20261102-03-ota-metadata.zip`
- Ukuran gabungan: **4.713.790.282 byte**; SHA-256: `bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425`.
- Draf memuat tiga **potongan mentah**, laporan `BUILD-REPORT-BOOT-FIRST-03.json`, dan `MANIFEST-GITHUB-BOOT-FIRST-03.json`. Potongan bukan ZIP yang dapat di-flash satu per satu; jangan mencampurnya dengan kandidat lain. Walaupun digabung dan hash cocok, kandidat ini tetap **belum layak untuk flash**.

| Bagian | Ukuran byte | SHA-256 |
|---|---:|---|
| `.001` | 1.610.612.736 | `f9455edf98db92e327a46f252771afaaa9c71007779e4906b13042e9ac0c4bc3` |
| `.002` | 1.610.612.736 | `ecd0b4fd69b40c6e66fb602dd3a6c830cfafc5d9f48294de4ce8fc45874033d1` |
| `.003` | 1.492.564.810 | `f3b64562251c0711446840ed39cab448a9af57ed4b076527fd93ad317664431e` |

## Yang diperbaiki dan diuji

Kandidat 03 dibuat dari kandidat 02 yang sudah dikunci hash. Hanya nilai property-files pada `META-INF/com/android/metadata` dan `metadata.pb` diubah; keduanya disimpan tanpa kompresi (`ZIP_STORED`) untuk akses rentang langsung. Format teks dan protobuf sama, dan semua field metadata lainnya dipertahankan secara semantik. Acuan adalah [schema dan implementasi AOSP yang dipin](https://github.com/aosp-mirror/platform_build/tree/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae/tools/releasetools).

| Entri | Offset data aktual | Ukuran | Pemeriksaan |
|---|---:|---:|---|
| `metadata` | 447 | 412 | ZIP_STORED; offset, panjang, dan byte rentang langsung cocok |
| `metadata.pb` | 62 | 326 | ZIP_STORED; offset, panjang, dan byte rentang langsung cocok |

Seluruh anggota sumber dan hasil dibaca dengan SHA-256 dan CRC ZIP; compressed stream semua anggota selain dua metadata identik. `super.img`, `boot.img`, `dtbo.img`, updater-script dan update-binary tetap identik dengan kandidat 02. Tiga potongan yang diunggah diunduh ulang, masing-masing hash dan hash gabungannya diperiksa. `unzip -t` berhasil dan struktur ZIP64/lokal/central diperiksa. **97 tes regresi host** lulus. [Run build 41477695884](https://github.com/dwp29/Syntenthica/actions/runs/41477695884) selesai sukses; sukses berarti proses packaging dan verifikasi host selesai, bukan lulus boot.

Metadata hasil check-run tersedia sebagai `HASIL-BUILD-03-RUN-41477695884-2026-11-02.json` (SHA-256 `23a195d558090fb0673b9650c4a16f29d46454d2811020ff292291ca5e8a04a8`). Pada JSON check-run, label `unchanged_members` berisi **seluruh** anggota terverifikasi, termasuk dua metadata yang berubah; daftar `changed_members` secara eksplisit menunjukkan pengecualiannya. Identitas per bagian dan build report juga ada pada manifest draf.

## Mengapa masih HOLD

- Perbaikan ini **hanya packaging**, bukan perbaikan framework, vendor, kernel, VINTF, SELinux atau AVB. Snapshot VINTF parsial kandidat 02 sebelumnya memperoleh exit 65 / INCOMPATIBLE; karena image tetap sama, temuan tersebut belum diselesaikan oleh build 03. Snapshot parsial bukan pembuktian gagal boot pada perangkat.
- ZIP baru tidak ditandatangani oleh resep ini; keberterimaan signature oleh recovery dan kepercayaan AVB/vbmeta perangkat belum terbukti. `otacert` di dalam ZIP tidak membuktikan signature whole-file. Parameter boot warisan yang meminta SELinux permissive juga tidak diubah dan status runtime tidak diketahui.
- Tidak ada pengujian pada recovery atau perangkat, dan tidak ada flash, wipe, maupun perubahan keamanan. Backup dan sumber, serta draf 01 dan 02, tetap dipertahankan. Fitur kamera, audio/Dolby, KernelSU/Manager, debloat dan optimasi tetap hold sampai dasar boot terbukti.

Langkah substantif berikutnya adalah memperoleh/membangun kombinasi framework, vendor dan policy yang benar-benar kompatibel untuk joyeuse, lalu memvalidasi signing/AVB yang sah. Mengganti angka deklarasi FCM atau sepolicy saja tidak membuktikan kompatibilitas.
