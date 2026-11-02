# Hasil lanjutan boot-first: policy dan VINTF

**Tanggal:** 2 November 2026. **Status: BELUM SELESAI / HOLD / JANGAN FLASH.** Perbaikan image system/vendor, tanda tangan tepercaya, dan boot perangkat belum terbukti. Kandidat 03 tetap merupakan perbaikan **packaging metadata OTA**, bukan ROM yang sudah kompatibel.

## Yang diuji

[Run 41484231021](https://github.com/dwp29/Syntenthica/actions/runs/41484231021) dan [run 41485767990](https://github.com/dwp29/Syntenthica/actions/runs/41485767990) membaca kandidat 02 yang diverifikasi dengan SHA-256 `395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372`. `super.img`-nya identik dengan kandidat 03: `3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673`. Keempat extent dan input snapshot diperiksa; identitas kandidat sebelum dan sesudah sama. Tool host `secilc` dan `checkvintf` AOSP berasal dari `otatools.zip` Android CI build 16644040 yang dipin berdasarkan hash. Kecocokan hash bukan verifikasi tanda tangan sumber tool. Compiler dan VINTF dieksekusi tanpa jaringan pada root read-only; output compiler sementara berada di tmpfs dan tidak disimpan ke paket atau dipasang ke perangkat.

### Policy SELinux

- **Kompilasi ketat** input CIL system, system_ext, product dan vendor yang tersedia, dengan pemeriksaan `neverallow` **aktif**, menghasilkan exit **255**. Diagnostik memuat **290 catatan kegagalan pemeriksaan `neverallow`**: 193 menunjuk ke CIL system, 7 system_ext, 3 product, dan 87 vendor public. Ini adalah jumlah catatan pada snapshot tersebut, bukan jumlah aturan unik, penolakan runtime, atau bukti kegagalan boot. Kontrol sintetis positif, simbol tidak dikenal dan pelanggaran `neverallow` menghasilkan keluaran yang diharapkan.
- **Perbandingan referensi AOSP init** yang terpisah menggunakan flag `-N` dan menghasilkan exit **0** serta policy sementara 1.585.876 byte (SHA-256 `bb02d18b0aeb24abb560c6e747425cf41a04c5794c656adbf721c542034851e4`). Flag ini melewati **assertion pada saat kompilasi**, bukan mematikan SELinux enforcement perangkat. Kontrol sintetis dengan simbol tidak dikenal tetap ditolak; untuk fixture sintetis, binary hasil perbandingan identik dengan binary tanpa assertion. Ini **bukan** kelulusan pemeriksaan ketat, bukan perubahan policy ROM, dan bukan bukti bahwa policy bisa dimuat atau boot pada perangkat.
- [AOSP init yang dipin](https://github.com/aosp-mirror/platform_system_core/blob/a3b721a32242006b59cb12bd62c9133632af3a2d/init/selinux.cpp) memperlihatkan pemakaian `-N` pada jalur referensinya. Implementasi dan jalur init ROM, versi policy yang didukung kernel, serta policy ODM/genfs/SKU aktual belum diketahui. Jangan menganggap referensi host identik dengan perilaku perangkat.

### VINTF

- Snapshot parsial asli menghasilkan exit **65 / INCOMPATIBLE**: field versi sepolicy manifest vendor adalah **30.0**, sedangkan rentang yang dibaca dari matriks framework dimulai dari **31.0**; matriks framework tepat untuk target FCM **4** juga tidak ditemukan pada lokasi yang dibaca.
- File `plat_sepolicy_vers.txt` vendor yang diperiksa berisi **31.0** dan mapping terkait tersedia. Ketika field VINTF 30.0 diubah menjadi 31.0 **hanya pada salinan sementara**, kesalahan sepolicy tersebut tidak lagi dilaporkan, tetapi `checkvintf` tetap exit **65 / INCOMPATIBLE**: matriks device meminta **VNDK 30**, sementara manifest framework dalam snapshot hanya mencantumkan **VNDK 34**. Matriks target FCM 4 tetap tidak ditemukan. Salinan XML telah dipulihkan; tidak ada patch yang dimasukkan ke image.
- Hasil ini mengidentifikasi lebih dari satu ketidakcocokan deklaratif, tetapi bukan pembuktian bahwa suatu library benar-benar hilang, ABI cocok/tidak cocok, atau perangkat gagal/berhasil boot. ODM, SKU, APEX aktif dan kernel sesungguhnya tidak disertakan sepenuhnya.

## Keputusan dan pekerjaan yang masih terhalang

Tidak dibuat kandidat 04 yang sekadar mengganti deklarasi VINTF atau menyalin library acak: itu dapat menutupi masalah tanpa membuktikan policy, VNDK, ABI HAL, ataupun keamanan. Menghapus `neverallow`, menambah izin sembarangan, memalsukan deklarasi, mematikan verifikasi, atau mengubah enforcement bukan solusi yang disetujui.

Perbaikan substantif memerlukan kombinasi framework/vendor/policy yang memang dibangun dan diuji untuk joyeuse, termasuk implementasi VNDK yang kompatibel dan konfigurasi partisi/ODM yang benar. Untuk membuat paket yang dapat diverifikasi, diperlukan juga proses signing yang dipercaya oleh recovery dan verifikasi rantai AVB/vbmeta serta rollback yang sesuai. Kunci privat tidak boleh dikirim melalui chat atau dikomit ke repo. Setelah itu dibutuhkan pengujian perangkat yang sesuai dan terpisah; belum ada izin atau tindakan flash, wipe, format, atau penggantian recovery pada sesi ini.

Kandidat 03 tetap tersedia sebagai [draf terbatas](https://github.com/dwp29/Syntenthica/releases/edit/431662583): 4.713.790.282 byte, SHA-256 `bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425`. Tiga potongan bukan ZIP siap flash. Paket ini **unsigned oleh resep**, trust recovery/AVB belum diketahui, dan boot tidak diuji. Sumber serta kandidat sebelumnya tetap dipertahankan; fitur/modul/optimasi tetap hold.

Hasil mesin yang diringkas ada di `HASIL-POLICY-COMPAT-RUN-41484231021-2026-11-02.json` dan `HASIL-POLICY-COMPAT-RUN-41485767990-2026-11-02.json` di repo. Status sukses workflow berarti **pengujian host selesai**, bukan produk lolos atau siap flash.
