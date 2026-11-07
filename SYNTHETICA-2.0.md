# Synthetica 2.0

> **Koreksi keselamatan untuk `release/Synthetica-2.0.zip`:** installer tidak
> membuat backup boot otomatis dan, bila `/data/adb` dapat diakses, mencoba
> menulis `ksud` ke `/data/adb/ksud`. Abaikan klaim sebaliknya pada catatan
> build historis `STATUS.json`, `RELEASE-INFO.json`, dan
> `artifacts/ARTIFACTS-MANIFEST.txt`. Perbandingan dengan 3.0, termasuk batas
> perubahan DTB/ramdisk dan konfigurasi, ada di
> [SYNTHETICA-2.0-3.0-PERBANDINGAN.md](SYNTHETICA-2.0-3.0-PERBANDINGAN.md).

Satu batch, urutan tetap: **APK dulu, kernel kemudian** (job kernel `needs` job manager dan
menanam sertifikat APK itu). Tidak ada pasangan campur antar-batch.

| Hal | Nilai |
|---|---|
| Berkas flash | `Synthetica-2.0.zip` |
| APK | `Synthetica-2.0.apk`, nama aplikasi **Synthetica**, paket `net.ember.labs` |
| `uname -r` | `4.14.357-openela-Synthetica-2.0` |
| Basis kernel | resep 1.16 yang terbukti (tree `c1e6f795`, lineage chronicle) + profil baru `synthetica` |
| UI APK | glassmorphism iOS: gradien pucat, kartu putih tembus cahaya, tipografi sistem bersih, splash **Synthetica**, ikon kaca baru |

## Optimasi harian (config saja — tanpa OC, tanpa ubah thermal)

Basis 1.16 sudah daily (schedutil, CPU boost, BBR + fq_codel, zram LZ4). Profil `synthetica`
mencoba memilih I/O **mq-deadline**, mengaktifkan workqueue power-efficient, dan mematikan
statistik f2fs. Konfigurasi build yang tersimpan menunjukkan `CONFIG_MQ_IOSCHED_DEADLINE=y`
tetapi `CONFIG_DEFAULT_IOSCHED="cfq"`; itu bukan bukti scheduler yang aktif untuk setiap
perangkat/ROM. Audit CI memaksa `KSU=y`, `KSU_MANUAL_HOOK=y`,
`MQ_IOSCHED_DEADLINE=y`, governor schedutil.

## Installer (bahasa Inggris, ringkas)

- Mulai: **بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ** — sukses: **الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ**
- **Backup boot dinonaktifkan** (permintaan 2.0; simpan backup boot versimu sendiri).
- **Installation log** ditulis ke `<storage>/Synthetica/install-log-<waktu>.txt`
  (string kernel, hash Image.gz, hasil ksud, hasil tulis).
- Tanpa auto-reboot, tanpa modul, tanpa ubah /vendor.

## Status

`COMPILED_ONLY_UNVERIFIED` sampai diuji di HP. 1.21 tidak pernah di-flash (info pengguna);
yang dipakai sebagai basis adalah 1.16 + APK-nya yang terbukti normal.
