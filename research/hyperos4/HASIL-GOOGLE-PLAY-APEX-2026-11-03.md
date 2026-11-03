# Koreksi inventaris Google Play: GMS ditemukan dalam APEX — 3 November 2026

**Ringkasan terkini:** Paket `com.google.android.gms` **ditemukan secara statis dalam APEX** pada citra basis kandidat 03. Ini menggantikan ketidakpastian pada laporan inventaris awal yang hanya memeriksa enam root app/priv-app. Keberadaan file **bukan** bukti APEX aktif, layanan berjalan, sertifikat dipercaya, lisensi distribusi, Play Integrity, atau kompatibilitas perangkat. Kandidat 04 tetap **HOLD / JANGAN FLASH / JANGAN PUBLIKASIKAN**.

## Kronologi dan cakupan

1. [Inventaris awal 41577314268](https://github.com/dwp29/Syntenthica/actions/runs/41577314268) membaca 250 APK di enam root app/priv-app. Play Store `com.android.vending` dan Google Services Framework `com.google.android.gsf` ditemukan; `com.google.android.gms` **tidak ditemukan di enam root itu saja**. APEX belum diperiksa.
2. [Audit tambahan 41579262168](https://github.com/dwp29/Syntenthica/actions/runs/41579262168) menelusuri 12.301 path dalam salinan ext4 system, system_ext, product dan vendor; membaca 94 APK lain di luar root semula, melewati 250 APK yang sudah diperiksa serta dua APK framework. Tidak ada GMS di 94 APK itu, tetapi ditemukan `product:/apex/com.google.android.gmssystem.prodvic.apex` dan berkas konfigurasi terkait. Perangkat `/data`, isi APEX lain, symlink dan paket dinamis tetap di luar cakupan.
3. [Percobaan APEX 41579676931](https://github.com/dwp29/Syntenthica/actions/runs/41579676931) berhasil memverifikasi salinan dan CRC payload, tetapi berhenti **incomplete** karena filesystem **EROFS**, sehingga belum dapat menyimpulkan isinya.
4. [Audit APEX terisolasi 41580191549](https://github.com/dwp29/Syntenthica/actions/runs/41580191549), commit `ea0df405af9803434197a124b0b5e97576f2ff97`, berhasil membaca isi EROFS dan menemukan satu APK:

| Identitas | Hasil |
|---|---|
| APEX pada product | `/apex/com.google.android.gmssystem.prodvic.apex` |
| APEX ukuran / SHA-256 | 155.066.368 byte / `fdf44ee609c5290e749f8cf1ed81b144155fe0530be90eca4c2a806ff51873fd` |
| Payload EROFS / SHA-256 | 155.017.216 byte / `1a5cd6ad67122bb9c249e03f6629aa0eb80be4c2e71848cda211bd53c65d629b` |
| Path APK dalam APEX | `/priv-app/PrebuiltGmsCoreVic@263032xxx/PrebuiltGmsCoreVic.apk` |
| APK ukuran / SHA-256 | 227.669.823 byte / `05de4f30a39a0db182f50bca1adf82ed2a8c05c09463e1ccddbe9ae95b9301e3` |
| Package dari manifest | `com.google.android.gms` |

Dua pembaca `aapt` dan `aapt2` sepakat atas ID paket dari salinan manifest; CRC ZIP manifest diperiksa. Manifest-only reader diuji menggunakan APK SpatialFlow yang identitasnya dipatok, dan ekstraktor EROFS lolos kontrol sintetis positif serta malformed-negatif. `fsck.erofs` host AOSP yang dipatok dijalankan dengan network namespace, chroot read-only, tanpa capabilities dan dengan tmpfs terbatas; tidak menjalankan kode APEX. SHA otatools cocok dengan rujukan yang dipatok, tetapi signature statement sumber tool belum diverifikasi. Source 03 dan citra product dibaca ulang tanpa perubahan.

Audit build 04 melaporkan semua file biasa product lama yang dapat dijangkau dibandingkan berdasarkan hash, termasuk cakupan file yang ada pada product 03; isi APEX ini **tidak secara terpisah diekstrak ulang dari 04** pada audit ini. Tidak satu pun APK/ROM diunggah dari audit, tidak ada perangkat atau data pengguna yang disentuh.

## Yang belum dibuktikan

- Signature APEX, rantai trust, status aktivasi APEX, privapp permissions dan layanan saat boot belum diperiksa di perangkat.
- Play Store, login/sinkronisasi Google, Play Services, sertifikasi/attestation dan Play Integrity belum diuji; tidak ada jaminan fungsi atau kelulusan attestation.
- Tidak ada dasar dari temuan ini untuk menghapus atau menambahkan GApps yang berpotensi menggandakan paket bawaan.
- SpatialFlow masih belum default. Prototype preference hanya sumber dan tidak tercakup pada APK/ROM 04. Blocker signature ZIP, recovery, AVB, VINTF/SELinux, boot, fitur hardware dan lisensi tetap berlaku.

Detail mesin: `HASIL-APEX-GOOGLE-RUN-41580191549-2026-11-03.json`; hasil parsial sebelumnya tetap disimpan agar jejak batasnya tidak hilang.
