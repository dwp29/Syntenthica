# Audit host checkvintf parsial dan metadata SELinux

**Tanggal:** 2 November 2026. **Status:** hasil negatif pada snapshot yang disediakan ke alat, bukan vonis kompatibilitas atau kegagalan boot pada perangkat.

## Kesimpulan singkat

Pada [run 41456952143](https://github.com/dwp29/Syntenthica/actions/runs/41456952143), `checkvintf` AOSP menyelesaikan dua pemeriksaan atas snapshot parsial kandidat kedua. Keduanya mengembalikan **exit 65 / INCOMPATIBLE untuk snapshot ini**, dengan diagnostik bahwa manifest perangkat menyatakan sepolicy `30.0` yang tidak memenuhi matriks framework dan matriks framework untuk target FCM `4` tidak ditemukan. Ini adalah temuan host yang perlu ditangani secara hati-hati, **bukan bukti bahwa perangkat pasti gagal boot**.

Kesuksesan workflow berarti pengujian dan kontrolnya selesai, **bukan** berarti kandidat lolos kompatibilitas. Hasil ini tidak menjelaskan penyebab fastboot pada artefak lain. Fitur dan modul tetap **hold**, tidak ada kandidat baru yang dibuat, dan tidak ada perubahan pada image atau perangkat.

## Metode dan kendali

1. Tool `checkvintf` adalah binary x86-64 dari Android CI build `16644040`, target `aosp_cf_x86_64_only_phone-userdebug`. `otatools.zip` berukuran 531.408.471 byte SHA-256 `bc85557aa0c59a7d0b48b8175250948d67b2d0f293bd74eb8d5753ba4ad7781f`; binary tool SHA-256 `6f7601b9409ac5db70d8b05bc98d117fe68456464e710eb2e2964c7edf1325db`. Digest paket cocok dengan subject pernyataan build yang diperiksa pada probe sebelumnya; **tanda tangan pernyataan belum diverifikasi**. Versi libvintf pada manifest build adalah `df89ad736e14ac375f61d50fa543ae7cd746a140`.
2. Sebelum kandidat diunduh, tiga kontrol sintetis menggunakan tool yang sama: contoh kompatibel exit **0**, contoh sepolicy inkompatibel exit **65**, dan XML rusak exit **70**. Audit berhenti sebelum kandidat bila kontrol tidak sesuai. **54 tes regresi host** pada lima kelompok juga lulus di run terakhir.
3. Tool dijalankan dalam user/mount/PID/network namespace dan chroot dengan root bind read-only, tanpa token, capability, perangkat atau host `/proc`, serta `no_new_privs`. Hanya XML yang diperiksa yang disalin ke snapshot sementara; ZIP kandidat tidak dimasukkan ke chroot. Tidak ada XML mentah atau log mentah kandidat yang diterbitkan.
4. ZIP kandidat kedua berukuran **4.713.790.039 byte**, SHA-256 `395c79099ccb2718d6309ce24606071a017fbbf4afb313e9b741649ccf27c372`, identik sebelum dan sesudah. Pembacaan lengkap `super.img` menghasilkan CRC ZIP dan SHA-256 `3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673` yang cocok; empat extent system, system_ext, vendor dan product cocok sebelum/sesudah. Identitas **67 XML** cocok inventaris sebelumnya dan byte snapshot tidak berubah setelah pemeriksaan.
5. Run awal [41455002052](https://github.com/dwp29/Syntenthica/actions/runs/41455002052) dan [41455202131](https://github.com/dwp29/Syntenthica/actions/runs/41455202131) **gagal pada kontrol** karena izin interpreter ELF dan fixture sepolicy; keduanya berhenti sebelum kandidat. Kedua masalah diperbaiki dan diuji. [Run 41455368714](https://github.com/dwp29/Syntenthica/actions/runs/41455368714) dan [41456027522](https://github.com/dwp29/Syntenthica/actions/runs/41456027522) menyelesaikan audit; run terakhir menambah inventaris metadata policy baca-saja.

## Hasil checkvintf parsial

| Skenario | Asumsi | Hasil alat untuk input yang diberikan |
|---|---|---|
| `empty_properties` | SKU dan first API tidak diberikan | exit 65, `INCOMPATIBLE`; diagnostik FCM 4 dan sepolicy 30.0 |
| `hypothetical_first_api_30` | first API **diasumsikan** 30; SKU tidak diberikan | exit 65, `INCOMPATIBLE`; diagnostik yang sama |

Manifest vendor utama menyatakan `target-level=4` dan sepolicy **30.0**. Matriks framework system tanpa level yang terbaca mencantumkan sepolicy **31.0, 32.0, 33.0, 34.0, 202404, 202504, 202604**; matriks berlevel yang terlihat adalah **7, 8, 202404, 202504 dan 202604**. Alat itu sendiri melaporkan tidak menemukan framework matrix pada FCM 4 dan ketidakcocokan sepolicy 30.0. Matriks tanpa level tidak diabaikan; hasil ini berasal dari implementasi host yang ditentukan, bukan perbandingan nama file semata.

Direktori legacy yang dicari tidak ditemukan atau tidak terbaca. Sumber ODM yang diperiksa di dalam vendor juga `missing_or_unreadable`; kondisi tersebut **tidak** membuktikan ODM runtime kosong. Sebanyak **40 paket `.apex`/`.capex` reguler** dihitung tanpa membuka isinya: 36 system, 3 system_ext dan 1 product; lokasi vendor tidak ditemukan atau tidak terbaca. Tidak ada daftar APEX aktif/fragmen runtime yang disertakan. Kernel runtime tidak diberikan, sehingga persyaratan kernel tidak diuji.

## Metadata split SELinux: temuan terpisah

Audit kedua hanya membaca nama yang ditentukan, ukuran/hash berkas dan membandingkan isi berkas digest; tidak menerbitkan policy mentah, tidak mengompilasi policy dan tidak mengakses perangkat. Ini **bukan** pengulangan JSON detail init yang pernah diblokir provider.

- `vendor/etc/selinux/plat_sepolicy_vers.txt` menyatakan **31.0**, sedangkan field sepolicy **30.0** di atas berasal dari **manifest VINTF**. Keduanya adalah field berbeda; jangan menukar atau menganggap salah satunya otomatis nilai runtime yang lain.
- Berkas mapping `31.0.cil` terlihat sebagai file reguler di system, system_ext dan product. Ini hanya bukti keberadaan dalam snapshot; belum membuktikan isi policy cocok atau dapat dikompilasi/dimuat.
- Vendor memiliki `precompiled_sepolicy`; pasangan isi berkas digest yang dibaca untuk system, system_ext dan product **berbeda** dari masing-masing digest yang disimpan di sisi vendor. Path precompiled pada ODM di dalam vendor tidak ditemukan atau tidak terbaca. Perbandingan ini belum membuktikan policy mana yang dipilih perangkat, keberhasilan kompilasi, atau status SELinux saat boot.
- File platform policy, vendor policy, `plat_pub_versioned.cil` dan `secilc` terlihat pada salinan yang dibaca. Semua hanya diinventarisasi sebagai data; tidak dieksekusi. Rincian SHA-256 berkas dan daftar mapping numerik ada pada JSON hasil.

## Batasan dan keputusan

Snapshot tidak memuat keadaan ODM sebenarnya, APEX aktif, properti SKU/boot yang pasti, kernel runtime, implementasi HAL atau seluruh konfigurasi keamanan. `checkvintf` host bukan uji OrangeFox, AVB/vbmeta, anti-rollback, enkripsi, seluruh ABI/HAL, policy runtime, fungsi aplikasi, atau boot. Hasil negatif ini perlu ditindaklanjuti, namun bukan dasar untuk menyatakan perangkat pasti gagal dan bukan alasan melemahkan SELinux/AVB.

Sumber, kedua kandidat dan backup dipertahankan. Tidak ada flash, wipe, perubahan recovery/firmware/image atau pelemahan keamanan. Modul Magisk/KSU, kernel/Manager pengganti, serta penambahan fitur tetap **hold** sampai bukti kompatibilitas dan boot yang memadai tersedia. Tindakan pada perangkat atau perubahan di luar persetujuan awal tetap memerlukan persetujuan spesifik.

Hasil metadata lengkap: `HASIL-CHECKVINTF-PARSIAL-RUN-41456952143-2026-11-02.json` (SHA-256 `4617be0813deb56218b44c58d521d61287b7dd93a05554f883667efc5afee516`). Hasil dua run yang lebih awal dipertahankan terpisah untuk reproduksibilitas. JSON detail init yang pernah diblokir provider tidak dikirim ulang, dimodifikasi untuk melewati filter, atau dialihkan.
