# Observasi simbol tanpa versi VNDK 30 — 3 November 2026

**Status: HOLD / JANGAN FLASH.** [Run 41564623121](https://github.com/dwp29/Syntenthica/actions/runs/41564623121) selesai sukses **sebagai pengumpulan diagnostik host**, bukan kelulusan ABI atau perangkat. Kandidat 03 tidak berubah dan perangkat tidak disentuh.

## Ruang lingkup dan kontrol

Untuk executable vendor yang menyebut satu atau lebih dari sembilan nama library VNDK 30 terpilih dalam `DT_NEEDED`, probe membandingkan **nama** simbol undefined global/weak yang tidak memiliki versi dengan gabungan nama yang diekspor provider APEX terpilih dan disebut langsung oleh executable yang sama, pada bitness yang sama. Simbol undefined tidak diatribusikan ke suatu library tertentu. Provider yang tidak terbaca dan cakupan provider terpilih yang tidak lengkap akan dicatat terpisah; weak dipisahkan dari strong. Nama mentah simbol tidak diterbitkan.

- **194 executable** memenuhi kriteria; **191** diparsing, tiga tidak memiliki dependensi langsung terpilih. Dari 191, **20** tidak memiliki nama undefined global/weak tanpa versi yang memenuhi kriteria.
- Semua **18 provider** terpilih, sembilan masing-masing untuk ARM dan AArch64, terbaca. SHA-256 masing-masing cocok dengan metadata kandidat run sebelumnya dan [pembanding blob AOSP yang dipin](HASIL-SIMBOL-DAN-HASH-VNDK30-2026-11-03.md).
- Terdapat **8.272 pasangan executable–nama–binding** yang dibandingkan. Sebanyak 6.534 entri undefined lain dikecualikan oleh filter versi/lokal/hidden; angka itu bukan temuan mismatch. Tidak ada provider terpilih yang unreadable dalam run ini.
- Tes lokal dan CI mencakup **103 regresi** pada 12 kelompok, termasuk delapan tes probe baru dengan ELF sintetis strong/weak, provider di luar cakupan, versi/default/hidden, 32/64-bit dan filesystem ext4 read-only. Blob AOSP terpilih juga berhasil diparsing secara lokal setelah hash diperiksa. Berkas kandidat, `super.img` dan extent yang diaudit diverifikasi tidak berubah.

## Ringkasan observasi

| Bitness | Binding | Observasi dalam provider APEX terpilih yang disebut langsung | Nama berbeda dalam kelompok | Pasangan executable–nama–binding |
|---|---|---|---:|---:|
| 32 | strong | nama sama terlihat | 96 | 192 |
| 32 | strong | nama tidak terlihat dalam cakupan terpilih | 293 | 297 |
| 64 | strong | nama sama terlihat | 943 | 4.311 |
| 64 | strong | nama tidak terlihat dalam cakupan terpilih | 2.597 | 3.471 |
| 64 | weak | nama tidak terlihat dalam cakupan terpilih | 1 | 1 |

Satu nama yang sama dapat muncul pada banyak executable dan kelompok bitness/binding berbeda; hitungan nama per kelompok tidak boleh dianggap jumlah nama unik global. Provider yang sama namanya dapat berjumlah lebih dari satu; tabel ini menghitung satu observasi per pasangan executable–nama–binding, bukan resolusi linker.

**Tidak terlihat dalam kumpulan terpilih bukan berarti simbol atau library hilang.** Simbol yang sama dapat disediakan library langsung lain yang tidak dipilih, dependensi transitif, atau provider lain; weak juga dapat sah tidak terselesaikan. Sebaliknya, **nama yang sama bukan bukti symbol type, versi, namespace, interposisi, ABI, aktivasi APEX, signer trust, atau boot**. Vendor shared libraries sebagai consumer, ODM, seluruh provider lain dan keadaan runtime tidak diaudit oleh probe ini.

Strict `secilc` pada run yang sama tetap exit **255**, dan snapshot `checkvintf` asli tetap exit **65**. Keduanya tetap terbatas pada input host yang diberikan, bukan hasil boot perangkat. Signing ZIP, trust recovery/AVB, kombinasi framework/vendor/policy yang cocok dan uji perangkat tetap belum selesai.

Hasil metadata lengkap: `HASIL-SIMBOL-TANPA-VERSI-RUN-41564623121-2026-11-03.json`, SHA-256 `13ff19956482db5a8d89574965472a50fa280714130d0a2f5259ecbe56334894`; [check 125684235171](https://api.github.com/repos/dwp29/Syntenthica/check-runs/125684235171). Tidak ada kandidat baru, donor, policy lemah, key privat, perubahan image atau tindakan flash dalam pemeriksaan ini.
