# Pemeriksaan simbol dan pembanding byte VNDK 30 — 3 November 2026

**Status: HOLD / JANGAN FLASH.** Semua hasil di bawah adalah pemeriksaan host, bukan bukti ABI, kepercayaan signer, recovery, atau boot perangkat. Tidak ada image atau perangkat yang diubah.

## Probe simbol berversi

[Run 41556140046](https://github.com/dwp29/Syntenthica/actions/runs/41556140046), [check 125656693726](https://api.github.com/repos/dwp29/Syntenthica/check-runs/125656693726), selesai sukses **sebagai proses probe**. Dari 194 executable vendor yang memenuhi kriteria, 191 dibaca karena memiliki dependensi langsung ke satu atau lebih dari sembilan nama library terpilih; tiga tidak memiliki dependensi langsung terpilih. Probe tidak menemukan referensi simbol **berversi** yang dapat dibandingkan ke sembilan library tersebut. Kedelapan belas provider 32/64-bit tidak memiliki definisi versi eksplisit yang dapat dibandingkan. Daftar observasi kosong, sehingga **kompatibilitas ABI tetap inkonklusif**, bukan lulus atau gagal. Simbol tanpa versi, shared-library vendor, dependensi transitif, ODM, namespace, interposisi, dan aktivasi runtime tidak dibuktikan.

Snapshot memeriksa kandidat 02 yang `super.img`-nya identik dengan kandidat 03. ZIP kandidat dan extent diperiksa sebelum/sesudah. Hasil lengkap tersimpan dalam `HASIL-SIMBOL-VNDK-RUN-41556140046-2026-11-03.json`, SHA-256 `21f8a1176b39f847f7830d2dc7be94dd6a8f4c574e4b329606db2293465881f3`.

## Perbandingan hash byte-ke-byte dengan snapshot AOSP

Sembilan library yang sama, masing-masing untuk ARM 32-bit dan AArch64 64-bit, dibandingkan dengan [snapshot AOSP VNDK 30](https://github.com/aosp-mirror-neo/platform_prebuilts_vndk_v30/tree/5f9884aa352825291757dfd6694b874ad8c1805e) pada commit `5f9884aa352825291757dfd6694b874ad8c1805e`, root tree `b4003df94aa31ffc53655ff075857b3486b9ff3d`. Blob referensi diambil hanya untuk pemeriksaan; setiap ukuran dan Git blob SHA-1 diverifikasi sebelum SHA-256 dihitung. SHA-256 kandidat berasal dari check run di atas.

**Hasil: 18 dari 18 SHA-256 identik** untuk `libbase.so`, `libbinder.so`, `libc++.so`, `libcrypto.so`, `libcutils.so`, `libhardware.so`, `libhidlbase.so`, `libssl.so`, dan `libutils.so`, pada kedua bitness. Rincian jalur, ukuran, SHA-1 blob, dan pasangan SHA-256 ada di `HASIL-PERBANDINGAN-VNDK30-AOSP-2026-11-03.json`, SHA-256 `fd215e1f0839edcb13bd3e3868043d3961542d626b8f462dc9526af988dad4c3`.

Ini menunjukkan bahwa **18 file terpilih identik byte** dengan snapshot referensi yang dipin, tetapi tidak membuktikan bahwa semua 572 library APEX identik, bahwa commit referensi ditandatangani, atau bahwa library aktif, dapat dicapai linker, kompatibel ABI, dipercaya, maupun dapat boot. Tidak ada donor yang dimasukkan ke kandidat; perbedaan hash pun tidak otomatis berarti rusak. Kesamaan ini memberi alasan untuk tidak mengganti sembilan library tersebut secara acak.

## Jangan mengisi `vndkVersion` APEX sembarangan

Manifest dalam/luar APEX kandidat identik dan berisi nama `com.android.vndk.v30`, versi `1`, serta field `vndkVersion` kosong. [Manifest referensi VNDK 30 AOSP](https://github.com/aosp-mirror-neo/platform_packages_modules_vndk/blob/2e2799dd657d16d4456be0674c21784be9114141/apex/apex_manifest.v30.json) juga hanya mencantumkan nama dan versi. Pada [apexd referensi](https://github.com/aosp-mirror-neo/platform_system_apex/blob/75c8ee81684d118ef3af2a4e898b8835da0be0c8/apexd/apexd.cpp), `VerifyVndkVersion` menerima field kosong; ketika diisi, ia memeriksa partisi vendor/ODM atau product dan mengembalikan error untuk partisi lain. Mengisi field pada APEX `system_ext` berisiko salah jika jalur itu diterapkan. Sumber referensi tidak terbukti identik dengan apexd ROM, dan kecocokan bentuk manifest bukan bukti aktivasi atau trust.

Masalah VINTF dan policy terdahulu, penandatanganan ZIP dan rantai AVB yang dipercaya, serta uji boot dan fitur tetap terbuka. Jangan mengubah deklarasi semata, melemahkan pemeriksaan, atau mem-flash kandidat ini.
