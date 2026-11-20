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

## Unduhan

Rilis run 9 sudah diunggah ke Google Drive. Ketiga tautan berisi berkas yang
sama-sama sudah diverifikasi MD5 terhadap salinan di workspace.

| Berkas | ID Drive | Ukuran |
|---|---|---|
| `BREAKFAST-APK-run9.zip` (paket lengkap) | `12wkoTgDOpxixSOuRAxFm6tpNYvrXiJLa` | 698.586 B |
| `BREAKFAST-manager-0.1.0-run9.apk` (APK saja) | `1fsmJlurVjOd2LFOZTB58N9HTVwhXmCb5` | 695.872 B |
| `BREAKFAST-APK-verifikasi.txt` (lembar verifikasi) | `1ZYWI-wvkN3OhcfppbA84NrMzD8agxoF5` | 2.744 B |

```
BREAKFAST-APK-run9.zip                    48ab22d8c8e45242a990c09bdb29762f46a30c84090f5ead97025ac96a962543
BREAKFAST-manager-0.1.0-run9.apk          8b93c0a870fed4fce16fec4fd2b7c7d3dd4fe11f1710c4588ceb7d1a7df3402d
sertifikat penandatangan (SHA-256)        9c58d0d7582af0ac34847d46286b53fc9ad668110500e5a70894cc50bd89194e
```

Paket ZIP memuat: APK, lembar verifikasi, catatan sha256/badging/sertifikat/mode
penandatanganan, tujuh berkas JUnit XML (60 tes), log Gradle mentah, dan catatan
teknis ini.

## Yang masih terbuka setelah build ini

1. **Uji di perangkat.** Sampai APK dijalankan di atas kernel yang sudah
   di-boot, semua klaim di atas hanya berlaku untuk kompilasi dan logika.
   Ini satu-satunya pekerjaan yang tidak bisa diselesaikan dari sini.
2. **Kunci penandatangan tetap.** Jalurnya sudah ada: bila empat secret
   `BREAKFAST_KEYSTORE_B64`, `BREAKFAST_KEYSTORE_PASSWORD`,
   `BREAKFAST_KEY_ALIAS`, `BREAKFAST_KEY_PASSWORD` diisi, build memakai kunci
   stabil dan APK bisa menimpa versi lama. Workspace ini tidak punya hak admin
   untuk menambah secret (API Actions secrets menjawab 404), jadi saat ini yang
   berjalan adalah jalur kunci sementara.

## Ditulis setelah melihat perangkat sungguhan

Laporan layar dari pemasangan nyata (kernel `4.14.357-openela-synthetica-3.2`)
menemukan lima cacat yang tidak bisa ditangkap tes mana pun di sisi ini. Semua
sudah diperbaiki di run 11:

1. **Audit saling bertentangan.** Ringkasan "0 didukung, 6 baca-saja, 10 tidak
   ada" berjumlah 16 padahal audit memeriksa 15 node. Penyebabnya: node yang
   bisa dibaca tapi tidak bisa ditulis dihitung sebagai "baca-saja" tanpa
   dihitung sebagai hadir. Sekarang klasifikasi dibangun di atas satu
   `Observation` (nilai/terbaca/tertulis/izin) sehingga satu node hanya masuk
   satu kategori.
2. **Kesalahan menyalahkan kernel.** Tanpa root, `canWrite` bernilai salah untuk
   semua node, sehingga semuanya dilabeli "kernel menolak penulisan". Sekarang
   dibedakan: "perlu root untuk menulis" versus penolakan kernel yang sungguhan.
3. **Copy ledger menyebut objek yang salah.** Ledger membaca `dmesg`, bukan
   sysfs. Kalimatnya kini menyebut dmesg.
4. **Nama node panjang menabrak nilainya.** Kedua sisi sekarang membungkus
   sendiri dengan jarak.
5. **`Kernel UAPI` menampilkan "—".** Nilainya kini dibaca dari
   `libkernelsu.so` (`Java_com_rifsxd_ksunext_Natives_getKernelUAPIVersion`),
   dengan digest dan keberadaan simbolnya dipin di CI. Kalau kernel tidak punya
   KernelSU-Next, tetap "—" — itu jawaban jujur.

Yang **tidak** perlu diperbaiki, meski terlihat seperti masalah di layar:

- **"Skor —" + "dmesg tidak bisa dibaca"** berarti aplikasi belum diberi root.
  Perilaku ini sesuai rancangan: skor tidak dikarang.
- **Tuning nonaktif pada kernel `synthetica-3.2`** karena kernel itu memang tidak
  ada di tabel pairing. Menebak tata letak sysfs kernel yang tidak dikenal lebih
  berbahaya daripada menonaktifkan tuning. Untuk menyalakannya, 3.2 harus
  diterbitkan lebih dulu lalu ditambahkan ke `breakfast-app/tools/pairing.json`.

Catatan: dua cacat di atas (butir 1 dan 2) hanya bisa ditemukan dari data
perangkat. Ini alasan konkret mengapa klaim "belum diuji di perangkat" terus
diulang: tanpa laporan Anda, APK run 9 akan tetap tampak benar.

## UI: dari daftar debug ke antarmuka

Build awal memakai widget bawaan Android. Itu cepat dibangun tetapi tidak bisa
membuat cincin, gradien, atau grafik, dan hasilnya memang terlihat seperti
daftar debug - bukan aplikasi. Desainnya sendiri sudah ada di
`design/breakfast/` (20 layar + `SPEC-LAYAR.md`) dan sebelumnya tidak dipakai.

| Aspek | Sebelum (run 11) | Sesudah (run 14) |
|---|---|---|
| Toolkit | View bawaan | Jetpack Compose |
| Ukuran APK | 724 KB | 6,6 MB |
| Navigasi | satu halaman memanjang | 5 tab: PULSE · ROOT · MODULES · TUNING · LAB |
| PULSE | tidak ada | cincin suhu, 4 kartu, 3 grafik 60 dtk, 2 dtk/tick |
| Tema | 5 tombol teks | pemilih dengan swatch, di balik ikon gerigi |
| Izin | 0 | 0 |

**Kenapa 6,6 MB.** Compose membawa runtime dan pustaka UI ke dalam APK. Itu
biaya yang dibayar untuk cincin, gradien, sparkline, dan animasi tab. Yang tidak
berubah: nol izin, tanpa INTERNET, tidak ada data yang disimpan atau dikirim.

**Yang masih belum terlihat.** UI ini belum pernah dijalankan. Lingkungan kerja
tidak punya emulator maupun Android SDK, jadi yang terbukti hanya kompilasi,
63 tes logika, dan APK yang terbentuk benar. Tampilan sebenarnya baru terbukti
saat dipasang di perangkat.

## Run 16: apa yang ditemukan perangkat, dan apa yang diperbaiki

Tujuh tangkapan layar dari pemasangan nyata menemukan 11 cacat. Semuanya
diperbaiki di run 16, dan tiap perbaikan punya tes regresi.

| # | Yang terlihat di layar | Penyebab | Perbaikan |
|---|---|---|---|
| 1 | `0 °C` hijau **"Normal"** | nilai `< 45` dianggap sehat, termasuk 0 | nilai di luar 5..125 °C = "tidak terukur"; busur tidak digambar |
| 2 | titik hijau di ujung busur kosong | *round cap* dari busur sepanjang nol | busur nol tidak digambar sama sekali |
| 3 | `Ker nel` | kolom nilai tanpa batas lebar, label menyusut | kedua kolom dibatasi + berbobot |
| 4 | kartu setinggi layar | sama dengan #3 | path panjang pindah ke `PathRow` |
| 5 | `UPTIME —` | bergantung `/proc/uptime` | `SystemClock.elapsedRealtime` |
| 6 | CPU Load garis kosong | `/proc/loadavg` tak terbaca | sebut sebabnya + cadangan `/proc/stat` |
| 7 | semua kartu `—` | aplikasi tak pernah minta root | kartu "tanpa root" + tombol BERI ROOT |
| 8 | LAB "tidak ada" vs TUNING "tidak bisa dibaca" | hanya ada 3 status | status keempat `UNREADABLE` |
| 9 | "Audit terakhir" = uptime | salah sambung | umur audit sebenarnya |
| 10 | MGLRU `—` vs `TIDAK ADA` | dua jalur tampilan | seragam |
| 11 | `zram_mem_limit` dua kali; ROOT/MODULES buntu; Memory datar | dedupe, aksi, skala | diperbaiki |

**Catatan yang paling penting:** cacat #1 bukan cacat tampilan. Aplikasi
mengarang angka sehat pada metrik yang paling mudah dipercaya, dan itu
membatalkan klaim "tidak pernah mengarang angka". Klaim itu sekarang dijaga
oleh tes, bukan oleh niat.

## Run 17-20: klaim yang tidak pernah dibuktikan

Tangkapan layar run 16 memperlihatkan bahwa perbaikan suhu bekerja (81 °C,
"Panas", cincin oranye) dan umur audit bekerja ("40 detik lalu"). Tetapi
tangkapan yang sama memperlihatkan cacat yang bentuknya persis sama dengan
`0 °C`: menyatakan fakta yang tidak pernah ditetapkan.

| Yang terlihat | Klaim yang dibuat | Bukti sesungguhnya |
|---|---|---|
| LAB: 10 node "tidak ada" | node tidak ada di kernel | `File.exists()` = false karena direktori induk tidak bisa ditelusuri |
| TUNING: "node tidak ada di kernel ini" | idem, untuk node yang sama | audit hanya tidak bisa memeriksa |
| PULSE: "perangkat ini tidak punya su" | tidak ada root | KernelSU terpasang; dmesg dan sysfs dipakai |
| Grafik Memory | garis datar di dasar | nilai 61% nyata, skalanya yang salah |
| UPTIME "0j" | nol jam | 20 menit |

Aturan yang sekarang berlaku, dan dijaga tes:

1. **Ketiadaan butuh bukti.** `tidak ada` hanya keluar kalau isi direktori induk
   sudah dibaca dan nama node tidak ada di dalamnya. Selain itu
   `tidak bisa dipastikan`. Status support menjadi lima, dan kelimanya selalu
   berjumlah 16.
2. **Satu fakta, satu kata.** LAB, TUNING, dan PULSE memakai sumber yang sama;
   tidak ada lagi tiga kata berbeda untuk satu node.
3. **Klaim tentang perangkat butuh pemeriksaan perangkat.** "Tidak punya su"
   hanya boleh diucapkan setelah memeriksa penanda pengelola root.
4. **Angka yang benar bisa tetap menyesatkan.** Grafik dengan skala
   min..maks deret menggambar 61% datar sebagai garis di lantai; sekarang deret
   persen memakai pita nyata. "0j" menjadi "20m".
5. **Fungsi yang tidak pernah menunggu tidak punya batas waktu.** `RootBridge`
   membaca stdout sampai EOF sebelum `waitFor`, sehingga timeout 10 detik tidak
   pernah bisa terjadi.

Yang tidak bisa diperbaiki dari sisi aplikasi: kalau SELinux atau kebijakan
KernelSU memblokir proses aplikasi, aplikasi sekarang **mengatakannya**, bukan
berpura-pura node-nya tidak ada.

## Run 21-22: suhu yang tidak bergerak, dan suntingan yang gagal diam-diam

Dua tangkapan layar berturut-turut menunjukkan cincin pada 81 °C lalu 88 °C.
Angka seperti itu tidak wajar untuk ponsel yang sedang menganggur, dan memang
bukan suhu.

**Penyebab.** Pembaca mengambil nilai terbesar dari setiap `thermal_zone` yang
tipenya mengandung "cpu". Kernel punya zona seperti `cpu-0-limit`,
`cpu-0-trip-point-0`, dan `cpu-0-stage`: isinya suhu **ambang** tempat kernel
mulai menurunkan kecepatan. Ambang adalah konstanta; ia tidak berubah ketika CPU
menjadi panas. Mengambil maksimum atas semua zona berarti memilih konstanta itu
dan menggambarnya sebagai pengukuran.

**Perbaikan.** Zona hanya dianggap termometer bila namanya menunjuk sensor
(`cpu`/`soc`/`gpu`/`tsens`/`apc`) **dan** tidak mengandung penanda ambang
(`limit`/`trip`/`stage`/`threshold`/`cool`/`warn`/`crit`/`virtual`/…). Cincin
sekarang menyebut nama zona yang dipakai, dan LAB menampilkan seluruh zona
beserta nilainya, sehingga angka di layar bisa diperiksa alih-alih dipercaya.

**Kegagalan proses.** LAB mencetak `0 / 6 / 3 / 1` — empat angka berjumlah 10
untuk audit 16 node. Penyebabnya bukan logika, melainkan sebuah `replace()` di
skrip penyuntingan yang tidak cocok dan **tidak bersuara**. Dua langkah
diambil:

1. Angka itu sekarang dihasilkan dari laporan (`countsLine`/`countsLegend`), dan
   tes memastikan kelima keranjang selalu berjumlah `nodes.size`.
2. `tools/verify_edits.py` berjalan di CI dan **menggagalkan build** bila
   perubahan yang diklaim tidak ada di dalam sumber. Diam bukan lagi hasil yang
   mungkin dari sebuah suntingan.

## Run 23-24: tiga halaman yang kosong, dan 88 °C yang akhirnya terbaca

### Halaman yang ternyata placeholder

ROOT, MODULES, dan setelan bukan "kurang rapi" — mereka belum ada. ROOT hanya
satu tombol dengan tulisan "halamannya belum dibuat", MODULES menyatakan daftar
modul "belum ada di build ini" (padahal `/proc/modules` bisa dibaca tanpa root),
dan setelan hanya pemilih tema.

Sekarang:

| Halaman | Isi | Sumber fakta |
|---|---|---|
| ROOT | pengelola root, jalur `su`, uid proses, izin dmesg, izin tulis node | diperiksa saat dibuka |
| MODULES | modul termuat: nama, ukuran, pemakai | `/proc/modules` |
| SETELAN | laju sampel 1/2/5/10 dtk, tema, kernel, varian, audit, reset | preferensi + probe |

`null` (tidak bisa dibaca) dan daftar kosong (tidak ada modul) sengaja tidak
pernah disatukan; keduanya jawaban yang berbeda.

### 88 °C bukan ambang, dan bukan sensor CPU

LAB run 22 menampilkan seluruh zona termal:

```
soc          88,0 °C   <- dipakai cincin
aoss-0-usr   40,4 °C
cpu-0-0-usr  39,8 °C
cpu-0-1-usr  39,2 °C
pm6150-tz    37,0 °C
```

Cincin diberi label "CPU" tetapi diberi nilai dari zona bernama `soc`.
Sekarang cincin memilih sensor `cpu` lebih dulu, lalu `gpu`, lalu yang lain;
zona `soc` tetap tampil di LAB. Kalau kernel tidak punya sensor `cpu`, cincin
tetap menyebut nama zona yang dipakainya — angka yang tidak bisa diatribusikan
tidak boleh tampil sebagai angka.

### Angka yang tidak boleh diketik dua kali

Baris "Hasil" di LAB pernah menampilkan `0 / 6 / 3 / 6 / 1` dengan legenda
terpotong. Sekarang satu baris per keranjang, dihasilkan dari laporan itu
sendiri (`countsBreakdown`), dan `counted()` menjamin jumlahnya sama dengan
`nodes.size`.

