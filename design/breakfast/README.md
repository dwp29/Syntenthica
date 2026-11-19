# BREAKFAST — Spesifikasi Desain

Manajer kernel eksklusif untuk **Fresh-Milk** dan **CHEESE-BURGER**.
Bukan rebrand BakaSU. Struktur informasi, identitas, dan geraknya baru.

Nama `Fresh-Milk-14.03` menggantikan nama kerja sebelumnya (`Last-Dance-14.03`).

> **Gambar.** `*.png` adalah render konsep resolusi penuh (tidak di-commit —
> lihat `.gitignore`). Versi ringan yang di-commit ada di `preview/*.jpg`.
> Banner `16-banner.gif` (454 KB) ikut di-commit karena ia aset, bukan render.

Status: **dokumen desain.** Belum ada kode. Visual di bawah adalah render
konsep, bukan tangkapan layar aplikasi yang sudah jadi.

> Rincian per layar (state, pesan gagal, teks ID/EN) ada di
> **[`SPEC-LAYAR.md`](SPEC-LAYAR.md)**.

---

## 1. Prinsip yang mengikat desain ini

1. **App tahu ia di kernel apa.** Wajah berubah menurut kernel yang terdeteksi.
   Verifikasi lewat UAPI + capability flag, **bukan** string `uname`.
2. **Animasi membawa informasi.** Tidak ada gerak yang hanya hiasan.
3. **Tidak ada tombol berbahaya tanpa jalan pulang.** Flash wajib didahului backup.
4. **Yang tidak bisa diubah ditandai, bukan disembunyikan.** Parameter read-only
   diberi ikon kunci dan penjelasan.
5. **Satu sistem desain, dua wajah.** Token warna sama; hanya nilainya berbeda.

---

## 2. Dua wajah

| | **Fresh-Milk-14.03** | **CHEESE-BURGER-11.08** |
|---|---|---|
| Kesan | tenang, terpercaya | cepat, agresif |
| Latar | `#0D1117` | `#0A0A0C` |
| Aksen utama | `#4A9EFF` (biru) | `#FFB020` (amber) |
| Aksen sekunder | `#7EE787` (hijau, status sehat) | `#FF5C39` (oranye, peringatan) |
| Sudut kartu | 16 dp | 12 dp (lebih tajam) |
| Kepadatan | lega | padat, kontras tinggi |
| Animasi | halus, 280–400 ms | cepat, 160–240 ms |
| Bahasa visual | dashboard kesehatan | dashboard balap |

Keduanya berbagi: grid 4 dp, tipografi, ikon, dan struktur navigasi.

---

## 3. Navigasi — 5 tab

```
PULSE  ·  ROOT  ·  MODULES  ·  TUNING  ·  LAB
```

| Tab | Isi | Pengganti di BakaSU |
|---|---|---|
| **PULSE** | dashboard keadaan kernel: suhu, zram, MGLRU, uptime, skor stabilitas | HomePage |
| **ROOT** | daftar app superuser + izin, info mode hook | SuperUserPage |
| **MODULES** | modul terpasang, filter, update | ModulePage |
| **TUNING** | schedtune, uclamp, thermal, zram, MGLRU | *(baru)* |
| **LAB** | UGDP, diagnostik, pairing, ledger | *(baru)* |

Settings keluar dari dock, pindah ke ikon gerigi di header PULSE.
Alasan: Settings administratif, bukan keadaan perangkat.

---

## 4. Layar

### 01 — PULSE (Fresh-Milk)

![PULSE Fresh-Milk](01-pulse-fresh-milk.png)

- Cincin pulse besar: denyut mengikuti aktivitas CPU. **Berhenti saat idle**
  (hemat daya). Ini alasan animasinya ada, bukan sekadar bergerak.
- Empat kartu statistik: ZRAM, UPTIME, MGLRU, STABILITY.
- Tiga grafik garis 60 detik: CPU, Memory, Temperature.
- **Di atas cincin, banner GIF besar** (§16), tinggi maksimum 28% layar.

### 02 — TUNING

![TUNING](02-tuning.png)

Kontrol yang diusulkan (semua lewat API, bukan shell bebas):

| Kontrol | Nilai | Bisa ditulis? |
|---|---|---|
| Schedtune boost | 0–100 | ya (whitelist) |
| UCLAMP buckets | 3–5 | ya |
| Thermal profile | conservative / balanced / aggressive | ya |
| ZRAM compressor | lz4 / lz4kd / zstd | ya |
| MGLRU generations | 1–7 | tidak (butuh reboot) — ditandai kunci |

Tombol tetap di bawah: **APPLY CHANGES** + **RESET TO DEFAULT**.
Reset mengembalikan nilai ke default 3.2, bukan ke nilai pabrik.

### 03 — PULSE (CHEESE-BURGER)

![PULSE CHEESE-BURGER](03-cheeseburger-pulse.png)

Wajah yang sama, informasi berbeda. Gauge FPS + suhu, dan **grafik throttle**:
menampilkan apakah performa turun setelah 2 menit. Ini kejujuran yang jarang
ada di app tuning — kebanyakan hanya menampilkan angka tertinggi.

### 04 — ROOT

![ROOT](04-root.png)

- Pill identitas: `BakaSU · UAPI 6`, mode hook, versi SuSFS.
- Tiga status izin: ASK / ALLOW / DENY.
- Baris yang ditolak diberi penanda amber + jumlah penolakan hari ini.

### 05 — MODULES

![MODULES](05-modules.png)

Filter ALL / ACTIVE / DISABLED / UPDATE. Kartu update diberi border amber.
FAB untuk memasang modul dari berkas.

### 06 — LAB (UGDP)

![LAB UGDP](06-lab-ugdp.png)

UGDP masuk sebagai panel, bukan terminal. Tiga profil:
battery saver / balanced / performance. Parameter read-only ditandai kunci,
sesuai aturan UGDP: *"tidak menerima shell command bebas"*.

### 07 — HIDING (SuSFS)

![HIDING](07-susfs.png)

Tab: STATUS, PATH, MOUNT, KSTAT, MAP, OPEN REDIRECT, STANDARD.
Kartu status menampilkan fitur yang aktif dengan centang, dan yang **tidak
tersedia** dengan ikon info amber — misalnya `TRY_UMOUNT` yang tidak ada di
port 4.14. Ini menghindari kebingungan: user melihat batas kemampuan kernel,
bukan toggle yang gagal diam-diam.

### 08 — SAFE FLASH

![SAFE FLASH](08-safe-flash.png)

Alur tiga langkah: **BACKUP → VERIFY → FLASH**.
- Backup `boot` **wajib**, tidak bisa dilewati.
- Verifikasi sha256 sebelum menulis.
- Restore tersedia kapan pun.

Layar ini menambal celah nyata: 3.2-r1 belum punya installer sama sekali
(`installer_created: false`). BREAKFAST bisa menjadi installer pertama.

### 09 — Gerak

![Motion spec](09-motion-storyboard.png)

Contoh spesifikasi gerak untuk cincin pulse:

```
0 ms      arc mulai dari 0°
400 ms    sweep ease-out
1200 ms   ripple 0→130%, opacity 40%→0
2000 ms   tahan, lalu ulang
easing    cubic-bezier(0.22, 1, 0.36, 1)
idle      denyut berhenti untuk hemat daya
```

Pola yang sama dipakai untuk seluruh app:

| Elemen | Gerak | Alasan |
|---|---|---|
| Pindah tab | shared axis horizontal | menunjukkan posisi, bukan tumpukan |
| Kartu masuk | stagger 40 ms | menunjukkan prioritas |
| Angka berubah | putar digit, bukan fade | arah perubahan terbaca |
| Konfirmasi berbahaya | haptic + tahan 400 ms | mencegah salah tekan |
| Ledger error baru | slide dari atas | tidak menghentikan kerja user |

---

### 10 — ABOUT & CREATOR

![About & Creator](10-about-creator.png)

Halaman pembuat. Berisi:

| Bagian | Isi |
|---|---|
| CREATOR | **@Pure_Saturday**, peran, perangkat target (miatoll) |
| COMMUNITY | channel Telegram **https://t.me/breakfastch** + tombol buka |
| SUPPORT | pintasan ke halaman Donate |
| SOURCE CODE | tautan sumber GPL-3.0 |
| KERNELS SUPPORTED | dua chip identitas kernel |

Aturan: **tidak ada data pribadi selain yang sengaja dipublikasikan.** Channel
Telegram dibuka lewat intent, app tidak menyimpan token atau nomor telepon.

### 11 — SUPPORT (Donate)

![Donate](11-donate.png)

- Tiga nominal cepat, satu tombol lanjut.
- **Tidak ada pembayaran di dalam app.** App hanya membuka tautan eksternal;
  tidak ada kredensial, tidak ada nomor rekening yang ditanam.
- Halaman ini tidak boleh memblokir fitur apa pun. Kata kuncinya: *free and
  stays free*.

### 12 — SETTINGS

![Settings](12-settings.png)

Pindah dari dock ke ikon gerigi di header PULSE. Berisi:

| Grup | Isi |
|---|---|
| LANGUAGE | Bahasa Indonesia / English (dua-duanya) |
| APPEARANCE | ikut kernel, atau pilih manual |
| SECURITY | konfirmasi sebelum flash, konfirmasi sebelum tulis tunable, lokasi backup |
| ABOUT | About & Creator, lisensi open source |

### 13 — CUSTOMIZE

![Customize](13-customize.png)

Menyiapkan jalan untuk **multi-tema**. Tiga sumbu, terpisah satu sama lain:

| Sumbu | Pilihan | Catatan |
|---|---|---|
| **Theme** | Follow kernel, Fresh-Milk, Cheese-Burger, Mint, Grape, Monochrome | "Follow kernel" = default, ikut kernel terdeteksi |
| **Accent** | 8 warna (biru, amber, teal, ungu, pink, hijau, merah, abu) | hanya mengubah aksen, tema tetap |
| **Motion** | Animasi on/off, intensitas (Subtle/Balanced/Lively), haptic on/off | |

Aturan tema:

1. **Tema = token, bukan salinan layar.** Setiap tema hanya mendefinisikan
   `colors`, `shapes`, `type scale`, `motion spec`. Tidak ada layout ganda.
2. **Tema tidak boleh mengubah alur.** Tombol yang sama, di tempat yang sama.
3. **Tema baru harus lulus kontras.** Rasio minimum 4.5:1 untuk teks badan,
   3:1 untuk teks besar. Ini diperiksa, bukan dikira-kira.
4. **`Follow kernel` selalu tersedia** dan menjadi default saat pertama pasang.

### 14 — MODULE SOURCES

![Module sources](14-repo-sources.png)

Sumber modul ditambahkan lewat daftar, **bukan** pencarian bebas di internet.

| Sumber | Kategori | Bentuk |
|---|---|---|
| Magisk Modules Alt Repo | root modules | repo GitHub |
| KernelSU Modules | root modules | repo GitHub |
| LSPosed Modules | Xposed | repo GitHub |
| Dolby Atmos ports | audio | repo GitHub |
| GCam Ports | camera | repo GitHub |
| Samsung Good Lock ports | OneUI apps | repo GitHub |
| Viper4Android / JamesDSP | audio DSP | repo GitHub |
| Folder lokal | manual | `/sdcard/Modules` |

Aturan keamanan sumber:

1. **Daftar bawaan bersifat kurasi**, bukan hasil pencarian. Isinya diperiksa
   dulu, bukan sekadar ditempel.
2. **Sumber pihak ketiga wajib ditandai.** Kalau user menambah repo sendiri,
   app menampilkan peringatan: *"Sumber tidak diverifikasi"*.
3. **Tidak ada eksekusi otomatis.** Mengunduh ≠ memasang. Pemasangan tetap
   lewat alur konfirmasi.
4. **Setiap unduhan menampilkan sha256** bila sumber menyediakannya; kalau
   tidak, itu juga dikatakan.

### 15 — MODULE DETAIL

![Module detail](15-module-detail.png)

Halaman sedetail mungkin, dengan informasi yang **selalu** ditampilkan:

| Blok | Isi |
|---|---|
| Hero | ikon, nama, pengembang, versi, status verifikasi |
| Stat tiles | ukuran, terakhir diperbarui, jumlah unduhan, versi |
| Tab | Description, Changelog, Screenshots, Files, Permissions |
| Kompatibilitas | 3 baris centang/silang: perangkat, Android, batas kernel |
| Peringatan | kartu amber bila modul butuh HAL/partisi khusus |
| Aksi | "VIEW ON GITHUB" (sekunder) + "DOWNLOAD" (primer) |

Aturan detail:

1. **Statistik unduhan berasal dari sumber**, bukan karangan. Kalau sumber tidak
   menyediakan, tampil `—`.
2. **Tab Permissions wajib ada** — modul bisa menulis ke sistem; user berhak
   tahu apa yang dimintanya.
3. **Ukuran dan sha256 ditampilkan sebelum unduh**, bukan sesudah.
4. Status "VERIFIED" hanya diberikan untuk sumber kurasi, dan artinya
   **"dari sumber resmi"**, bukan "aman". Kata "aman" tidak boleh dipakai.

### 16 — Banner depan (GIF)

![Banner](16-banner.gif)

Banner besar di halaman PULSE, format **GIF animasi** (`16-banner.gif`,
420×236, 14 frame, 454 KB, loop tak berujung).

Isi banner: dua identitas kernel dalam satu komposisi — biru untuk
**FRESH-MILK-14.03**, amber untuk **CHEESE-BURGER-11.08** — dengan denyut
halus, sapuan cahaya, dan partikel mengambang.

Aturan banner:

1. **Ukuran dibatasi.** 454 KB masih di atas target ≤ 400 KB. Kalau perlu
   turun lagi, kurangi jumlah warna (32 → 24) sebelum menurunkan resolusi.
2. **Banner berhenti saat layar tidak terlihat.** GIF yang berjalan di latar
   belakang menguras baterai. Ini wajib, bukan opsional.
3. **Banner tidak boleh menutupi informasi.** Tinggi maksimum 28% layar;
   konten PULSE harus tetap terlihat tanpa scroll untuk bagian atas.
4. **Ada fallback statis** `preview/16-banner-frame0.jpg` untuk perangkat atau
   keadaan di mana animasi dimatikan user.

## 4A. Konsep yang diadopsi dari UGDP Starter

Sumber: `UGDP-Starter-Source.zip` (Drive). Isi sebenarnya adalah **kerangka
read-only**, bukan modul performa jadi: `mode: monitor`, `service.sh` hanya
mencetak info perangkat, `performance` dan `battery` berlabel *"not active in
starter"*. Nilainya ada di prinsipnya, bukan di kodenya.

Lima konsep yang diadopsi:

### 1. Audit sebelum kontrol

UGDP: *"Collect output before any tuning. Some paths may not exist on a given
kernel/ROM; that is useful information, not a reason to create them manually."*

**Penerapan:** BREAKFAST menjalankan **audit perangkat sekali** saat pertama
dibuka, dan mengulanginya kalau `uname -r` berubah. Audit mencatat, untuk setiap
parameter: node ada/tidak, izin baca/tulis, nilai sekarang, dan rentang yang
diizinkan driver.

**Tanpa audit, tab TUNING tidak menampilkan slider yang bisa ditulis.** Lebih
baik menampilkan "belum diaudit" daripada slider yang gagal diam-diam.

### 2. Tiga status, bukan dua

| Status | Arti | Tampilan |
|---|---|---|
| **supported** | node ada, bisa ditulis | slider aktif |
| **read-only** | node ada, hanya bisa dibaca | nilai + ikon kunci |
| **unsupported** | node tidak ada | baris abu-abu + alasan |

Ini menggantikan rencana awal yang hanya punya "bisa tulis" dan "dikunci".
Bedanya penting: `read-only` berarti kernel *punya* fiturnya, `unsupported`
berarti tidak punya sama sekali.

### 3. Pemulihan state

UGDP memakai `restore_on_exit: true`, artinya profil dikembalikan saat service
berhenti. **Penerapan:** BREAKFAST menyimpan (a) nilai default 3.2, (b) nilai
terakhir yang diterapkan user, dan bisa mengembalikan ke default kapan pun —
bukan hanya saat exit. Default 3.2 **tidak pernah ditimpa**; ia dibaca dari
kernel saat audit.

### 4. Proteksi termal bukan sakelar

UGDP menaruh `thermal_protection: true` sebagai konstanta config, bukan toggle.
**Penerapan:** BREAKFAST **tidak akan pernah** menawarkan opsi mematikan
proteksi termal. Yang bisa diubah hanya agresivitasnya
(conservative/balanced/aggressive), dan `aggressive` tetap tunduk pada trip point
bawaan kernel. Trip point **tidak pernah** ditulis.

### 5. Interval polling adaptif

UGDP memakai `poll_interval_ms: 3000`. Untuk grafik 60 detik itu terlalu kasar.
**Penerapan:** 1 detik saat layar aktif, berhenti total saat layar mati.
Alasannya baterai: dashboard yang menguras baterai membatalkan gunanya.

### Yang tidak diadopsi

| Dari UGDP | Alasan |
|---|---|
| WebUI JavaScript | BREAKFAST native Compose; WebUI hanya untuk modul |
| `device_codename_expected: joyeuse` | miatoll unified: curtana/excalibur/gram/joyeuse |
| `cpu_policy: "bounded"` | terlalu kabur; kita butuh node dan nilai nyata |
| Bentuk modul terpisah | UGDP jadi halaman native di BREAKFAST |

Catatan: dokumen arsitektur UGDP menyebut integrasi **"Both"** (modul + halaman
native). ZIP starter **hanya berisi modul**. Halaman native belum ada dan harus
ditulis sendiri — itu pekerjaan BREAKFAST, bukan pekerjaan yang diwarisi.

## 5. Yang dibuang dari BakaSU Official

BakaSU punya **35 layar**. Daftar ini yang diusulkan dibuang — **perlu persetujuan
sebelum dikerjakan**, sesuai permintaan.

| Layar BakaSU | Alasan usulan |
|---|---|
| `DynamicManagerScreen` | dukungan multi-manager sudah dihapus dari BakaSU sendiri (commit `97c102b`); app kita tunggal |
| ~~`ModuleRepo`, `OnlineModuleDetail`, `RepositorySources`~~ | **DIBATALKAN** — user meminta halaman module browser lengkap (§14, §15). Layar ini **dibangun ulang**, bukan diwarisi |
| `ScriptRun` | menjalankan skrip manifest: bertentangan dengan aturan UGDP "tanpa shell bebas", dan berbahaya |
| `Template`, `TemplateEditor` | pembuat modul — pekerjaan developer, bukan user |
| `UmountManagerScreen` | bertabrakan dengan panel HIDING/SuSFS kita; satu tempat saja |
| ~~`themeSettings/*`, `BackgroundCropActivity`~~ | **DIBATALKAN** — user meminta multi-tema (§13). **Dibangun ulang** sebagai CUSTOMIZE dengan token tema |
| `about/OpenSourceLicenseScreen` | **dipertahankan** sebagai kewajiban lisensi, tapi dipindah ke Settings |

Yang **dipertahankan** dari BakaSU: `SuperUserPage`, `ModulePage`, `Flash`,
`Install`, `KernelFlash`, `About` (wajib GPL), `SuSFSConfig*` (digabung ke HIDING).

---

## 6. Keputusan yang sudah diambil

| # | Hal | Keputusan |
|---|---|---|
| 1 | Nama package | **`app.breakfast.manager`** |
| 2 | Tab TUNING menulis sysfs | **Boleh**, dengan whitelist + tombol reset |
| 3 | Skor stabilitas | **Jadi** (Stability Ledger) |
| 4 | Bahasa UI | **Indonesia + English** |
| 5 | Daftar buang §5 | **Disetujui seluruhnya** |
| 6 | Halaman pembuat | **@Pure_Saturday** + channel Telegram |
| 7 | Donate | **Ada**, sebagai halaman tanpa pembayaran in-app |
| 8 | Identitas pembuat tampil publik | **Ya** — `@Pure_Saturday`, `t.me/breakfastch` |
| 9 | Prinsip UGDP | **Diadopsi seluruhnya** (§4A) |
| 10 | Multi-tema | **Ya** — CUSTOMIZE (§13), 6 tema awal |
| 11 | Module browser lengkap | **Ya** — kurasi multi-sumber (§14) + detail (§15) |
| 12 | Banner depan | **GIF animasi** (§16), dengan fallback statis |

### Konsekuensi dari keputusan 2 (TUNING boleh menulis)

Menulis sysfs menambah risiko nyata, jadi ada empat pengaman wajib:

1. **Whitelist**, bukan daftar hitam. Hanya parameter yang terdaftar yang bisa ditulis.
2. **Validasi rentang** di app sebelum menulis; nilai di luar rentang ditolak.
3. **Konfirmasi** sebelum apply, bisa dimatikan di Settings.
4. **RESET TO DEFAULT** selalu tersedia, mengembalikan nilai default 3.2.

Parameter yang **tidak** bisa ditulis tetap ditandai ikon kunci, misalnya
jumlah generasi MGLRU (butuh reboot) dan apa pun yang tidak ada node sysfs-nya.

### Konsekuensi dari keputusan 3 (skor stabilitas)

Skor berasal dari hitungan `Oops`/`BUG`/`WARN` di `dmesg` sejak boot,
dinormalisasi terhadap uptime. Rumus dan ambang ditulis di dokumen teknis
terpisah sebelum implementasi. Skor **bukan** klaim kesehatan perangkat —
hanya indikator perubahan. Kalau `dmesg` tidak bisa dibaca, skor ditampilkan
sebagai `—`, bukan angka palsu.

### Konsekuensi dari keputusan 4 (dua bahasa)

Seluruh string lewat `strings.xml` + `values-in/`. Tidak ada teks yang ditanam
langsung di Compose. Nama kernel (`Fresh-Milk-14.03`, `CHEESE-BURGER-11.08`)
**tidak** diterjemahkan — itu identitas, bukan label.

---

## 7. Rujukan

| Sumber | Dipakai untuk |
|---|---|
| `UGDP-Starter-Source.zip` (Drive, 8.422 B) | prinsip audit/status/pemulihan (§4A) |
| `docs/KERNEL-WORK-RULES.md` | aturan kerja kernel yang mengikat |
| `SYNTHETICA-3.2-r1.md` + `artifacts/synthetica-3.2/STATUS.json` | baseline fitur kernel |
| BakaSU Official (35 layar) | bahan pembanding daftar buang (§5) |
