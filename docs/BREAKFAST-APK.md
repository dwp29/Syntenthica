# BREAKFAST manager - APK

APK pengelola kernel untuk varian **Fresh-Milk** dan **CHEESE-BURGER**. Dibangun
di CI, bukan di mesin lokal: sandbox ini tidak punya Java maupun Android SDK.

## Berkas

| Berkas | Keterangan |
|---|---|
| `ci-stage/breakfast/BREAKFAST-manager.apk` | APK siap pasang, 678.328 B |
| `ci-stage/breakfast/APK-SHA256.txt` | sidik jari APK |
| `ci-stage/breakfast/APK-BADGING.txt` | `package`, `versionCode`, `versionName` |
| `ci-stage/breakfast/TEST-*.xml` | hasil 38 tes JVM |
| `ci-stage/breakfast/TESTS-PASSED` | penanda bahwa tes pada run ini lulus |

Sidik jari yang saat ini berlaku:

```
d6e7529ae72583f932c0e795dae151e36da4fe002be9861548da827e5d75ee05
package  app.breakfast.manager
version  0.1.0-run6 (versionCode 6)
compileSdk 36 · minSdk 26 · targetSdk 36
```

## Memasang

```sh
adb install -r ci-stage/breakfast/BREAKFAST-manager.apk
```

APK ditandatangani dengan kunci sementara yang dibuat ulang **setiap run CI**.
Karena itu pembaruan antar-run tidak bisa dipasang menimpa yang lama; copot
dulu (`adb uninstall app.breakfast.manager`). Ini disengaja: tidak ada kunci
penandatangan berumur panjang yang bisa bocor, dan tidak ada yang bisa
menganggap APK ini sebagai rilis resmi.

Aplikasi meminta **nol izin** - tanpa INTERNET, tanpa penyimpanan. Root diambil
lewat `su` milik KernelSU hanya saat membaca `dmesg`.

## Membangun ulang

```sh
# di CI: .github/workflows/breakfast-apk.yml (jalankan via push atau manual)
# di mesin dengan Android SDK:
cd breakfast-app
./gradlew :app:testDebugUnitTest      # 38 tes
./gradlew :app:assembleRelease -PbreakfastVersionCode=6 -PbreakfastVersionName=0.1.0-run6
```

Pemeriksaan yang tidak butuh JVM bisa dijalankan di mana saja:

```sh
python3 breakfast-app/tools/gen_pairing.py   # tabel pairing -> Kotlin
python3 breakfast-app/tools/check_logic.py   # rumus, kontras, whitelist
```

## Apa yang benar-benar sudah terbukti, dan apa yang belum

**Terbukti:**

- APK terkompilasi, `zipalign -c -p 4` lulus, `unzip -t` utuh, blok tanda
  tangan v2/v3 ada.
- 38 tes JVM lulus, dan merah bila satu harapan salah - dibuktikan dengan
  sengaja merusak satu asersi (commit `73879ac`), lalu dikembalikan.
- Skor ledger cocok dengan kelima contoh angka di `SPEC-LENGKAP.md`.
- Kelima tema lolos WCAG: teks terendah 16,6:1, aksen terendah 5,6:1.
- Parameter di luar whitelist tidak bisa ditulis; tes membuktikan tidak ada
  penulisan yang terjadi saat nilai ditolak.

**Belum terbukti:**

- **APK belum pernah dijalankan di perangkat.** Tidak ada satu pun bukti UI,
  pembacaan `dmesg`, atau penulisan sysfs yang nyata. Yang ada hanya
  kompilasi dan tes logika murni.
- Kernel Fresh-Milk dan CHEESE-BURGER sendiri belum pernah di-boot. Tabel
  pairing karena itu menandai keduanya `compiled_not_boot_tested`, dan layar
  utama menampilkan "dikompilasi, belum diuji boot".
- Tuning belum punya tombol tulis di UI. Mesin tulisnya (`TuningEngine`) sudah
  ada dan teruji, tetapi layar hanya membaca nilai. Tombol menulis butuh
  keputusan terpisah, karena setiap penulisan mengubah perangkat orang lain.

## Pagar yang dipasang

1. **Whitelist tertutup.** `scaling_max_freq`, `scaling_governor`,
   `vm.swappiness`, trip termal, dan seluruh `/proc/sys/kernel` tidak bisa
   dinyatakan sebagai parameter, jadi tidak bisa ditulis bahkan karena salah
   ketik.
2. **Tuning butuh kernel yang dikenal.** `uname -r` dicocokkan persis dengan
   tabel pairing; kernel lain mendapat "dinonaktifkan" dan penjelasannya,
   bukan slider yang menulis ke node yang salah.
3. **dmesg tak terbaca menghasilkan "—".** Bukan 0, bukan 100. Angka palsu
   pada skor kesehatan adalah hal yang wajar ditindaklanjuti pengguna.
4. **Setiap penulisan dibaca balik.** Penulisan yang diabaikan kernel
   dilaporkan gagal, bukan berhasil.
5. **Warna status tidak ikut tema.** Merah tetap merah di semua tema; ada tes
   yang mengunci ini.

## Yang perlu diputuskan sebelum rilis

1. **Kunci penandatangan tetap.** APK sekarang tidak bisa diperbarui. Untuk
   rilis, kunci harus disimpan sebagai secret CI, bukan dibuat per run.
2. **Tombol tulis.** Mesinnya siap; keputusan apakah pengguna boleh mengubah
   zram dari aplikasi belum diambil.
3. **Uji di perangkat.** Sampai kernel di-boot dan APK dijalankan di atasnya,
   semua klaim di atas hanya berlaku untuk kompilasi dan logika.
