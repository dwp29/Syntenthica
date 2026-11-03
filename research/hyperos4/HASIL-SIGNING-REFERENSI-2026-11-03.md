# Triage signing ZIP recovery — 3 November 2026

**Status: HOLD / JANGAN FLASH.** Ini adalah kesimpulan dari metadata build yang terverifikasi dan pembacaan source referensi, bukan uji terhadap recovery yang terpasang atau perangkat.

## Bukti pada kandidat 03

[Run build 41477695884](https://github.com/dwp29/Syntenthica/actions/runs/41477695884) menghasilkan ZIP kandidat 03 berukuran 4.713.790.282 byte, SHA-256 `bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425`. Resep tidak menandatangani ZIP; pemeriksaan ZIP yang dihasilkan mencatat **ZIP comment 0 byte**. Metadata `META-INF/com/android/otacert` ada, tetapi keberadaan sertifikat itu sendiri tidak merupakan tanda tangan whole-file atau bukti key dipercaya. Lihat `HASIL-BUILD-03-RUN-41477695884-2026-11-02.json` dan `BUILD-BOOT-FIRST-03-METADATA-OTA-2026-11-02.md`.

[Verifier AOSP referensi](https://github.com/aosp-mirror-neo/platform_bootable_recovery/blob/9565b5ee790a4ae7acd0c6c04a2b3e0c7eeced3c/otautil/verifier.cpp) membaca tanda tangan whole-file dari ZIP comment dan mensyaratkan `signature_start` lebih besar dari enam byte serta tidak melebihi ukuran comment. Kedua syarat tersebut tidak dapat dipenuhi bila comment berukuran nol. Dengan demikian, kandidat 03 **tidak memiliki format signature whole-file yang dapat lolos verifier referensi tersebut**. Ini kesimpulan format, bukan pelaksanaan verifier pada ZIP 03.

Pada [source OrangeFox yang ditinjau](https://github.com/ymdzq/OrangeFox_Recovery/blob/ff8c75dbc8036e33b3aaee88e5620001d5d9157f/twrpinstall/twinstall.cpp), pemeriksaan ZIP dilakukan **bersyarat** dan menggunakan kunci dari `/system/etc/security/otacerts.zip`; [verifier pada source yang sama](https://github.com/ymdzq/OrangeFox_Recovery/blob/ff8c75dbc8036e33b3aaee88e5620001d5d9157f/twrpinstall/verifier.cpp) memakai syarat footer yang sama. Build dan setting OrangeFox yang benar-benar terpasang belum diperiksa. Karena itu kita tidak menyimpulkan bahwa recovery pengguna pasti menolak atau menerima paket, dan tidak menyarankan menonaktifkan verifikasi.

## Persyaratan untuk kandidat masa depan

- Signature recovery yang sah perlu dibuat dengan mekanisme dan identitas penandatangan yang **benar-benar dipercaya oleh recovery target**, lalu diverifikasi; sertifikat dalam paket atau kunci uji buatan sendiri saja tidak membuktikan trust. Jangan mengirim kunci privat ke chat atau memasukkannya ke repositori.
- Signing tidak boleh dianggap hanya menambahkan beberapa byte: [AOSP `FinalizeMetadata`](https://github.com/aosp-mirror/platform_build/blob/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae/tools/releasetools/ota_utils.py) menjelaskan bahwa signapk dapat mengubah urutan dan padding entri. Implementasi tersebut melakukan signing awal, menghitung/finalisasi property-files, menandatangani ulang, dan memverifikasi offset pada ZIP final. Mekanisme apa pun yang dipilih harus memeriksa ulang `metadata` dan `metadata.pb` terhadap offset dan panjang aktual ZIP yang **sudah ditandatangani**, serta memverifikasi signature-nya.
- Signature ZIP tidak menggantikan verifikasi AVB/vbmeta, rollback index, kecocokan framework/vendor/policy atau pengujian perangkat. Rantai trust AVB dan kondisi perangkat masih belum diketahui.

Tidak ada key, ZIP baru, perubahan recovery, perubahan verifikasi, atau tindakan pada perangkat yang dibuat dalam triage ini.
