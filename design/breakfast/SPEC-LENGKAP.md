# BREAKFAST — Pelengkap Spesifikasi

> **HOLD (2026-10-31).** Lihat `docs/HOLD-FITUR-DAN-RENCANA-KERNEL.md`.

Mengisi empat hal yang masih terbuka di `SPEC-LAYAR.md` §14.

Status: dokumen desain. Belum ada kode.

---

## 1. Stability Ledger — rumus dan ambang

### 1.1 Sumber data

`dmesg` sejak boot, difilter. Hanya tiga kelas kejadian yang dihitung:

| Kelas | Pola | Bobot |
|---|---|---|
| `Oops` | `Internal error: Oops`, `Unable to handle kernel` | 10 |
| `BUG` | `kernel BUG at`, `BUG: ` | 8 |
| `WARN` | `WARNING: CPU:`, `WARNING: at` | 3 |

Yang **tidak** dihitung: `Call trace:`, `---[ end trace ]---`, pesan driver
biasa, `pr_err` dari driver, kegagalan I2C/probe yang pulih.

### 1.2 Rumus

```
beban      = Σ (bobot × jumlah_kejadian)
umur_jam   = uptime dalam jam
skor_mentah = 100 − (beban × 10) / max(umur_jam, 1)
skor        = clamp(round(skor_mentah), 0, 100)
```

Contoh:

| Kejadian | Uptime | Beban | Skor |
|---|---|---|---|
| tidak ada | apa pun | 0 | **100** |
| 1 WARN | 1 jam | 3 | 70 |
| 1 WARN | 10 jam | 3 | 97 |
| 1 Oops | 5 jam | 10 | 80 |
| 2 Oops + 1 WARN | 2 jam | 23 | 0 |

### 1.3 Ambang tampilan

| Skor | Warna | Label |
|---|---|---|
| 90–100 | hijau `#7EE787` | Stabil |
| 70–89 | biru `#4A9EFF` | Normal |
| 40–69 | amber `#FFB020` | Perlu perhatian |
| 0–39 | oranye `#FF5C39` | Bermasalah |

### 1.4 Batasan yang harus dinyatakan di app

1. **Skor bukan diagnosis.** Ia mengukur *perubahan*, bukan kesehatan absolut.
2. **Kegagalan yang pulih tidak dihitung.** Kalau dihitung, satu driver yang
   retry I2C saat boot akan selamanya membuat skor jelek.
3. **Kalau `dmesg` tidak bisa dibaca** (izin, `CONFIG_SECURITY_DMESG_RESTRICT`),
   skor tampil `—` dengan alasan. **Tidak pernah dikarang.**
4. **Skor kembali 100 setelah reboot**, karena sumbernya `dmesg` sejak boot.
   Ini harus dikatakan di UI, kalau tidak user mengira skornya permanen.

### 1.5 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `ledger_title` | Catatan Stabilitas | Stability Ledger |
| `ledger_score` | Skor | Score |
| `ledger_stable` | Stabil | Stable |
| `ledger_normal` | Normal | Normal |
| `ledger_attention` | Perlu perhatian | Needs attention |
| `ledger_trouble` | Bermasalah | Trouble |
| `ledger_since_boot` | Sejak boot terakhir | Since last boot |
| `ledger_no_dmesg` | dmesg tidak bisa dibaca, skor tidak tersedia. | dmesg unreadable, score unavailable. |
| `ledger_group_title` | Kejadian per driver | Events per driver |
| `ledger_empty` | Tidak ada kejadian tercatat. | No events recorded. |

---

## 2. Whitelist parameter TUNING

Hanya parameter yang **terbukti ada di source** yang masuk daftar. Sisanya
menunggu audit perangkat.

### 2.1 Terverifikasi dari source

| Parameter | Path sysfs | Rentang | Status awal |
|---|---|---|---|
| `zram_comp_algorithm` | `/sys/block/zram0/comp_algorithm` | `lz4`, `lz4kd`, `zstd` | supported |
| `zram_disksize` | `/sys/block/zram0/disksize` | integer > 0 | **needs-reboot** |
| `zram_mem_limit` | `/sys/block/zram0/mem_limit` | integer ≥ 0 | supported |
| `schedutil_up_rate` | `/sys/devices/system/cpu/cpu*/cpufreq/schedutil/up_rate_limit_us` | 0–50000 | perlu audit |
| `schedutil_down_rate` | `…/down_rate_limit_us` | 0–50000 | perlu audit |
| `schedutil_iowait` | `…/iowait_boost_enable` | 0/1 | perlu audit |

Catatan penting:

- **`zram_disksize` hanya bisa diset sebelum zram diaktifkan.** Sesudahnya
  kernel menolak. Karena itu statusnya `needs-reboot`, bukan `supported`.
- **`lz4kd` hanya tersedia** kalau `CONFIG_CRYPTO_LZ4KD=y` — di 3.2 **ya**.
  Daftar algoritma harus dibaca dari node itu sendiri, bukan dari daftar
  hardcoded. Kalau `zstd` tidak ada, jangan tawarkan.
- **Node `schedutil/*` belum terbukti ada** di tree ini. Source memakai
  `gov_attr_set`, tapi eksposur sysfs-nya tidak saya verifikasi. **Statusnya
  wajib `perlu audit`** sampai dijalankan di perangkat.

### 2.2 Ditolak masuk whitelist

| Kandidat | Alasan |
|---|---|
| thermal trip point | dilarang UGDP; risiko hardware |
| `scaling_max_freq` mentah | bisa melewati batas thermal |
| `scaling_governor` | mengubah ini bisa mematikan schedutil dan membatalkan semua tuning lain |
| `vm.swappiness` | efeknya tidak terasa di Android; sering menyesatkan |
| `kernel.sched_*` global | di Android dikelola framework; konflik |
| apa pun di `/proc/sys/kernel/` | terlalu berisiko, terlalu luas |

### 2.3 Aturan whitelist

1. **Daftar ini bukan daftar hitam.** Parameter yang tidak ada di daftar tidak
   bisa ditulis. Titik.
2. **Daftar algoritma zram dibaca dari node**, bukan dari kode.
3. **Rentang divalidasi ganda**: di app dan di kernel. App menolak lebih dulu.
4. **Setiap penulisan dibaca ulang.** Kalau tidak cocok, itu kegagalan (§5.3
   `SPEC-LAYAR.md`).

---

## 3. Tema — sisa tiga yang belum dibuat

Enam tema total. Dua sudah ada (Last-Dance, Cheese-Burger), satu bawaan
(Follow kernel). Tiga sisanya:

| Tema | Latar | Aksen | Sekunder | Kesan |
|---|---|---|---|---|
| **Mint** | `#0B1512` | `#3DDC97` | `#8AE6C0` | segar, tenang |
| **Grape** | `#120D18` | `#A56BFF` | `#D3B4FF` | dalam, kreatif |
| **Monochrome** | `#0C0C0C` | `#D6D6D6` | `#8A8A8A` | netral, tanpa warna |

### 3.1 Kontras — dihitung, bukan dikira

Rasio kontras teks terhadap latar (WCAG 2.1):

| Tema | Teks utama `#F2F2F2` | Teks sekunder `#9A9A9A` | Aksen vs latar | Ambang |
|---|---|---|---|---|
| Mint | 16.6:1 | 6.6:1 | 10.5:1 | lolos |
| Grape | 17.1:1 | 6.8:1 | 5.6:1 | lolos |
| Monochrome | 17.5:1 | 7.0:1 | 13.5:1 | lolos |
| Last-Dance | 16.9:1 | 6.7:1 | 6.9:1 | lolos |
| Cheese-Burger | 17.7:1 | 7.0:1 | 10.8:1 | lolos |

Angka di atas dihitung dengan rumus WCAG 2.1 (`(L1+0.05)/(L2+0.05)`), bukan
perkiraan. Ambang teks badan 4.5:1, elemen non-teks 3:1.

**Aturan:** tema baru **wajib** melewati uji kontras otomatis sebelum bisa
dipilih. Tema yang gagal tidak muncul di daftar, dan kalau dipaksa lewat
konfigurasi impor, app menampilkan `cus_contrast_fail`.

### 3.2 Aturan warna status

Warna status (hijau/amber/oranye/merah) **tidak ikut berubah** antar tema.
Alasan: merah harus tetap berarti bahaya di semua tema. Tema hanya mengubah
latar, aksen, dan bentuk — bukan semantik warna.

Pengecualian: Monochrome memakai **pola** (garis, titik) selain warna untuk
status, karena warna netral menghilangkan pembeda.

---

## 4. Audit — kapan dijalankan

Jawaban: **otomatis, dan bisa manual, tapi manual dibatasi.**

| Pemicu | Kapan | Boleh |
|---|---|---|
| Pertama pasang | saat app pertama dibuka | ✅ otomatis |
| `uname -r` berubah | setelah flash kernel | ✅ otomatis |
| Tombol "Audit sekarang" | kapan pun | ✅ manual |
| Setelah perubahan config | tidak dideteksi otomatis | ⚠️ user harus manual |

### 4.1 Aturan

1. **Audit manual selalu boleh**, tapi diberi jeda minimum 30 detik antar
   audit untuk mencegah spam pembacaan sysfs.
2. **Audit tidak menulis apa pun.** Ia hanya membaca.
3. **Hasil audit disimpan** dengan cap `uname -r` + waktu. Kalau `uname -r`
   berubah, hasil lama **dibuang**, bukan diperbarui sebagian.
4. **Audit gagal tidak menghapus hasil lama.** Kalau manual audit gagal,
   hasil sebelumnya tetap dipakai, dengan penanda "hasil lama, %s lalu".
5. **Audit mencatat apa yang tidak ada**, bukan hanya yang ada. Daftar
   `unsupported` sama pentingnya dengan `supported`.

### 4.2 Yang diperiksa audit

| Grup | Node |
|---|---|
| CPU freq | `/sys/devices/system/cpu/cpu*/cpufreq/` |
| Governor attr | `…/schedutil/*` |
| ZRAM | `/sys/block/zram0/{comp_algorithm,disksize,mem_limit}` |
| MGLRU | `/sys/kernel/mm/lru_gen/{enabled,min_ttl_ms}` |
| Thermal | `/sys/class/thermal/thermal_zone*/` + `trip_point_*` (baca saja) |
| GPU | `/sys/class/kgsl/kgsl-3d0/` |
| SuSFS | `/sys/kernel/susfs/` (versi, fitur) |
| KernelSU | UAPI lewat ioctl, bukan sysfs |

Untuk setiap node: **ada/tidak, izin (`ls -l`), pembacaan berhasil/tidak,
nilai sekarang**.

### 4.3 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `audit_title` | Audit perangkat | Device audit |
| `audit_run` | Audit sekarang | Run audit |
| `audit_running` | Memeriksa %d node… | Checking %d nodes… |
| `audit_done` | Audit selesai: %d didukung, %d baca-saja, %d tidak ada. | Audit done: %d supported, %d read-only, %d unavailable. |
| `audit_stale` | Hasil lama, %s lalu. | Stale result, %s ago. |
| `audit_cooldown` | Tunggu %d detik sebelum audit lagi. | Wait %d seconds before auditing again. |
| `audit_failed` | Audit gagal: %s | Audit failed: %s |
| `audit_no_write` | Audit hanya membaca, tidak mengubah apa pun. | Audit is read-only. |

---

## 5. Yang masih terbuka setelah ini

Sungguh-sungguh terbuka, bukan basa-basi:

1. **Apakah `schedutil/*` benar ada** di miatoll — harus dibuktikan di
   perangkat. Sampai itu terjadi, statusnya `perlu audit` dan slider-nya
   **tidak ditampilkan**.
2. **Angka bobot Stability Ledger** (§1.1) adalah pilihan desain, bukan hasil
   pengukuran. Kalau setelah dipakai ternyata skor terlalu sensitif atau terlalu
   tumpul, bobotnya perlu disetel — dan penyesuaian itu harus dicatat.
3. **Tema tambahan di luar enam** belum dirancang. Format tokennya sudah
   disiapkan, tapi tidak ada janji berapa banyak tema akan ada.
