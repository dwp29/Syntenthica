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

## Run 25-30: ROOT dan MODULES

Fokus putaran ini hanya dua layar itu. Tidak ada fitur lain yang disentuh.

### ROOT berkata "tidak ditemukan" pada perangkat KernelSU

TUNING pada perangkat yang sama menunjukkan node schedutil terbaca dan sysfs
dipakai — hal yang mustahil tanpa root. Jadi aplikasinya yang salah, bukan
perangkatnya.

Sebabnya satu baris: `File.exists("/data/adb/ksu")`. Android mengembalikan
`false` bukan hanya untuk jalur yang tidak ada, tetapi juga untuk jalur yang
tidak boleh **dit traversali**. Sandbox aplikasi tidak bisa melihat `/data/adb`.
Kode membaca "tidak bisa melihat" sebagai "tidak ada".

Yang paling disayangkan: `libkernelsu.so` (13.896 byte) **sudah ada di dalam APK
sejak awal** dan tidak pernah dipanggil. Pustaka itu menjawab dari kernel:

| simbol | arti |
|---|---|
| `getVersion` | versi KernelSU |
| `getKernelUAPIVersion` / `getManagerUAPIVersion` | UAPI kernel dan manager |
| `isSuEnabled` | su aktif atau tidak |
| `getSuperuserCount` | berapa aplikasi diberi root |
| `isSafeMode` | modul dinonaktifkan setelah boot gagal |

Ketujuh simbol diverifikasi ada di pustaka sebelum dipanggil. Setiap baris ROOT
sekarang membawa asal-usulnya: `LIBRARY`, `SHELL`, `FILESYSTEM`, atau `UNKNOWN`.
"tidak ditemukan" hanya dicetak ketika direktori benar-benar bisa dibaca.

### MODULES mengklaim nol modul tanpa membuktikannya

Kode lama mengembalikan daftar kosong untuk **berkas tidak terbaca** dan untuk
**berkas kosong**, sehingga layar menyimpulkan "Kernel ini tidak memuat modul apa
pun". Bentuk kesalahannya identik dengan `0 °C`: ketiadaan yang tidak pernah
dibuktikan, dinyatakan sebagai fakta.

Sekarang `FileRead` membedakan `Ok`, `Denied`, `Missing`, `NotAFile`, `Failed`,
dan `ModuleScan` mengembalikan `Loaded`, `Unreadable`, atau `NoProcModules`.
Kalimat "0 modul" hanya boleh keluar dari `Loaded`, dan ada tes yang mengunci itu.

### Kegagalan proses yang lain

Enam kiriman gagal build karena kesalahan mekanis saya (impor, tipe, nama
bentrok). Sandbox tidak punya JDK, jadi CI dipakai sebagai kompiler — mahal dan
tidak adil terhadap waktu pengguna. Satu kegagalan bukan soal kode: build dan
verifikasi APK **lolos**, lalu langkah penyimpanan artefak kalah cepat karena
agent dan job push ke branch yang sama. APK yang sudah jadi terbuang. Langkah itu
sekarang mencoba ulang sampai lima kali.

## Run 31: force close, dan pustaka native yang memuat dirinya sendiri

Run 30 tidak bisa dibuka sama sekali. Run 24 — yang tidak pernah menyentuh
`libkernelsu.so` — bisa dibuka. Urutan itu sudah cukup untuk menunjuk tersangka,
dan tidak ada tersangka lain yang cocok.

Penyebabnya dua kesalahan saya yang bertumpuk:

`System.loadLibrary` diletakkan di dalam `by lazy`, jadi pustaka dimuat pada
pembacaan properti pertama — saat start-up, di worker — bukan di tempat yang
saya pilih. Blok `lazy` yang melempar juga dicoba ulang pada setiap akses,
sehingga kegagalan akan diulang selamanya.

Kesalahan kedua lebih berat: **initialiser pustaka native bisa memanggil
`abort()`**. Tidak ada `try/catch`, tidak ada `UncaughtExceptionHandler`, tidak
ada kode Kotlin yang berjalan setelahnya — prosesnya sudah hilang. Membungkus
pemuatan itu memang tidak akan pernah menolong, dan itu seharusnya sudah saya
tahu sebelum mengirimkannya. `UnsatisfiedLinkError` juga sebuah `Error`, bukan
`Exception`, jadi penanganan yang biasa pun tidak menjangkaunya.

Run 31 mengubah kontraknya:

- `Natives.load()` satu-satunya pintu masuk, mengembalikan `false` bila gagal.
  Tidak ada yang berjalan di berkas itu sebelum ia berhasil.
- Pustaka **tidak** dimuat saat start-up. Tombol di halaman ROOT adalah izinnya.
- `NativeGuard` menulis penanda "percobaan sedang jalan" ke disk sebelum memuat.
  Bila proses mati saat memuat, penanda itu selamat; start berikutnya melihatnya,
  menolak memuat lagi, dan menjelaskannya di layar dengan tombol untuk mencoba
  sekali lagi.
- Worker start-up dibungkus: kegagalan apa pun menjadi kalimat di halaman ROOT,
  bukan force close.
- `RootStatus.snapshot(allowLibrary)` default `false`, sehingga jalur aman adalah
  yang didapat pemanggil yang lupa memikirkannya.

100 tes JVM lulus (97 dari run 30 + `NativeGuardTest` 2 + `NativeMarkerLogicTest`
1). APK `versionCode 31`, sha256 `c54ee28d…`, tanda tangan sementara sehingga
run 30 harus di-uninstall lebih dulu.

Belum terbukti: aplikasi benar-benar terbuka di perangkat, dan ROOT/MODULES
terisi. Keduanya menunggu tangkapan dari perangkat.

## Audit sisi kernel: kenapa root tidak pernah muncul

Keluhan yang sah dan menutup semua pekerjaan APK: tanpa root, halaman ROOT dan
MODULES tidak akan pernah punya isi. Jadi yang diperiksa kali ini bukan aplikasi,
melainkan paket kernelnya.

**Satu. ZIP tidak memasang `ksud`.** `build-kit/scripts/package_fresh_milk.py`
mendaftarkan `ksud` di `does_not_write`. KernelSU memerlukan proses userspace itu
untuk menyalakan root dan membuat `/data/adb/ksu`. Sebuah kernel bisa membawa
driver yang sempurna dan tetap tidak pernah memberikan root tanpa `ksud`. Ini juga
menjelaskan kenapa `/data/adb` selalu "tidak terbaca" di setiap tangkapan:
direktorinya belum pernah dibuat, jadi tidak ada yang bisa dibaca.

**Dua. Kernel hanya menerima satu identitas Manager.** Dengan mendekompres
`artifacts/Image.gz` langsung, isinya memuat tepat satu kemunculan `net.ember.labs`
dan satu kemunculan sertifikat `fe833710…`, dan tidak memuat `com.rifsxd.ksunext`
maupun sertifikat manager lain. Panjang sertifikat yang tertanam `0x53d` — cocok
dengan manager 1.19.1 yang dipin, bukan 2.0 (`0x565`). Artinya APK bawaan
`com.rifsxd.ksunext`, atau manager yang ditandatangani kunci lain, memang akan
ditolak kernel itu. Penolakan itu by design, bukan kerusakan aplikasi.

**Tiga. `/debug_ramdisk/su` bukan bukti root.** Jalur itu dibuat oleh manager; di
tangkapan terakhir aplikasi menyebutnya apa adanya dan tetap menandai status root
sebagai BELUM DIKETAHUI. Pemeriksaan yang otoritatif tetap `su -c id -u`.

Urutan yang harus dibetulkan ada di paket kernel, bukan di APK: ZIP ikut memasang
`ksud`, APK manager berasal dari keluarga sertifikat yang diterima kernel itu, dan
baru setelah keduanya cocok root bisa muncul. Aplikasi tidak bisa menambal
ketiadaan itu, dan tidak lagi berpura-pura bisa.

## Multi-manager: BakaSU dan KernelSU-Next tidak bisa berdampingan di satu kernel

Pertanyaan yang diajukan: BREAKFAST berbasis BakaSU, Synthetica Manager berbasis
KernelSU-Next — bisakah keduanya jalan bersama?

Jawabannya perlu dipisah menjadi dua hal yang sering tertukar.

**Backend root tidak bisa dua.** Kernel 4.14 hanya memuat satu backend: BakaSU,
KernelSU-Next, SukiSU, dan APatch semuanya membajak jalur `setuid` dan `reboot`
yang sama. `docs/HOLD-FITUR-DAN-RENCANA-KERNEL.md` §3 sudah mencatat keputusan ini:
BakaSU (UAPI 6) ditunda, dan base 3.2 memakai KernelSU-Next in-tree (UAPI 4) karena
mengganti backend sekaligus menambah fitur menghilangkan kemampuan membedakan mana
yang membuat kernel gagal boot. Jadi "BREAKFAST berbasis BakaSU" bukan keadaan yang
ada sekarang, dan tidak bisa dibuat tanpa mengganti backend kernel.

**Manager bisa lebih dari satu, dan sudah begitu.** Sebuah manager hanyalah
aplikasi yang berbicara kepada backend. Kernel hanya mengakui satu identitas manager
(`net.ember.labs` + sertifikat `fe833710…`), tetapi aplikasi lain tetap boleh meminta
`su`. Karena itu Synthetica Manager dan BREAKFAST sudah berjalan bersama di
perangkat yang sama; memasang BREAKFAST tidak mengubah apa pun untuk root.

**Yang harus dilakukan supaya BREAKFAST mendapat root.** Tiga hal, dan hanya satu
di antaranya urusan aplikasi:

1. ZIP kernel harus memasang `ksud` (belum; lihat bagian audit di atas).
2. Aplikasi harus diizinkan di daftar aplikasi Synthetica Manager. KernelSU tidak
   memunculkan permintaan izin dengan sendirinya untuk uid yang belum terdaftar:
   `su` hanya memberi shell bila uid itu ada di allowlist. Tanpa langkah ini,
   aplikasi akan selamanya melihat "izin belum diberikan".
3. Halaman ROOT harus bisa membedakan "ditolak" dari "belum ditanya" — itu bug
   aplikasi yang diperbaiki di commit ini (lihat bawah).

## Tiga kesalahan yang ditemukan dari pertanyaan itu

**Verdict ROOT salah urutan.** Pemeriksaan "pengelola root tidak terbaca" dijalankan
lebih dulu, sehingga menelan kasus yang sebenarnya terjadi: manager terbaca, `su`
menolak. Sekarang `su` ditimbang lebih dulu; hanya bila keduanya buta jawabannya
"BELUM DIKETAHUI", dan kalimatnya menyebut dua sebab yang berbeda: backend memang
tidak ada, atau profil terisolasi sehingga `su` tidak dipasang untuk proses ini.

**MODULES membaca berkas yang salah.** Halaman itu membaca `/proc/modules`, yaitu
objek kernel `*.ko`, bukan modul yang dipasang orang. Modul KernelSU ada di
`/data/adb/modules`, dan itulah yang ditanyakan. Sekarang dua daftar ditampilkan
terpisah — "modul terpasang" dari `/data/adb/modules`, "modul kernel termuat" dari
`/proc/modules` — dan masing-masing punya kalimatnya sendiri. Hanya pembacaan yang
berhasil boleh berkata "0 modul".

**Hitung pengguna root dari API manager.** `getSuperuserCount()` adalah ioctl yang
hanya boleh dijawab untuk manager atau root, yang tidak akan pernah diberikan kepada
aplikasi ini. Angka itu tidak lagi dipakai sebagai fakta. Sebagai gantinya ada baris
**multi-manager** yang membaca `CONFIG_KSU` dari `/proc/config.gz`: satu backend,
disebut namanya, atau "tidak bisa dipastikan" bila berkasnya tidak terbaca.

## Run 34

Build pertama yang lolos setelah tiga kesalahan saya sendiri tertangkap CI:
`installedModules` dipakai tiga kali tanpa pernah dideklarasikan (tiga
unresolved-reference), kalimat verdict baru kehilangan frasa "tidak bisa
memeriksa" yang diuji, dan saya salah menghitung baris `lines()` sebagai tujuh
padahal enam. Ketiganya diperbaiki di tesnya atau di kodenya — bukan dengan
melonggarkan tes.

112 tes JVM, 0 gagal. `versionCode 34`, sha256 `cbcfe239…`, tanda tangan sementara
sehingga build sebelumnya harus di-uninstall lebih dulu.

APK: https://drive.google.com/file/d/18JLQ1bXUpCu1hwQBXYhMNx7JZezuPNXS/view
Bundel: https://drive.google.com/file/d/1sgSgAW3yQJCYEAObSRMfzF1C0PyZht7P/view
Verifikasi: https://drive.google.com/file/d/1nJAAFRVtlqAg3EAXHenDP2yp2M6khqm9/view

Belum terbukti: root menyala, ROOT/MODULES terisi data nyata. Keduanya menunggu
ZIP kernel yang memasang `ksud` dan izin aplikasi di Synthetica Manager.

## Run 36: "paired" ternyata hanya `uname -r`

Kritik itu tepat, dan lebih berharga daripada tiga putaran sebelumnya. Yang
disebut "kernel cocok" di aplikasi ini tidak pernah mengukur apa pun:

```
tools/pairing.json
    { "release": "4.14.357-openela-Fresh-Milk-14.03", "tuning": true }

KernelPairing.canTune(release, kernels, hasRoot) = hasRoot && nama ada di tabel
```

Tidak ada satu node sysfs pun yang dibaca untuk membukanya. Kolom `tuning` diisi
saat kernel diterbitkan, dari namanya. Akibatnya tiga, dan semuanya nyata: nama
yang cocok dianggap izin (slider muncul untuk node yang mungkin tidak ada),
kernel bagus dengan nama asing ditolak, dan lencana kernel di PULSE diberi warna
aksen seolah nama itu sebuah putusan.

Yang menggantikannya:

- Kendali TUNING hanya muncul bila audit **membaca node itu** di perangkat dan
  mendapat nilai. Itu satu-satunya syarat.
- Nama kernel turun jadi keterangan: tidak membuka, tidak memblokir.
- `"tuning"` dihapus dari tabel dan dari kode hasil generate. Setiap baris kini
  `capabilities_verified: false` dengan `evidence: "none"`, karena memang begitu
  keadaannya.
- `canTune()` dihapus, bukan dihaluskan kalimatnya: aturan yang ia wakili adalah
  bugnya.
- `check_logic.py` menggagalkan build bila ada baris tabel yang kembali mengklaim
  tuning atau kapabilitas terverifikasi.

Konsekuensi yang harus diterima: selama node belum bisa dibaca (dan itu butuh
root, yang masih menunggu `ksud` di ZIP kernel), halaman TUNING akan kosong. Itu
jawaban yang benar, bukan kemunduran.
