# BREAKFAST — Spesifikasi Rinci per Layar

> **HOLD (2026-10-31).** Lihat `docs/HOLD-FITUR-DAN-RENCANA-KERNEL.md`.

Pelengkap `README.md`. Dokumen ini menjawab: **apa yang terjadi saat datanya
kosong, gagal, atau belum diaudit** — dan **teks apa** yang muncul, dalam dua
bahasa.

Status: dokumen desain. Belum ada kode.

---

## 1. Konvensi state

Setiap layar yang menampilkan data wajib punya keenam state ini. Layar yang
tidak punya salah satunya berarti belum selesai dirancang.

| State | Kapan | Yang tampil |
|---|---|---|
| `loading` | data sedang diambil, < 400 ms | kerangka (skeleton), tanpa spinner |
| `loading-lama` | > 400 ms | kerangka + teks "Mengambil data…" |
| `isi` | data ada | konten normal |
| `kosong` | berhasil, tapi tidak ada data | ikon + satu kalimat + satu aksi |
| `gagal` | pembacaan gagal | sebab + tombol "Coba lagi" |
| `belum-diaudit` | audit perangkat belum jalan | ajakan audit + penjelasan singkat |

Aturan tambahan:

1. **Tidak ada spinner berputar.** Kerangka lebih jujur karena menunjukkan
   bentuk data yang akan datang.
2. **Pesan gagal menyebut sebabnya**, bukan "Terjadi kesalahan". Contoh:
   `sysfs tidak bisa dibaca (izin ditolak)`.
3. **`kosong` selalu punya aksi.** Layar kosong tanpa tombol adalah jalan buntu.
4. **`belum-diaudit` bukan `kosong`.** Bedanya: kosong = tidak ada data,
   belum-diaudit = kita belum memeriksa. Jangan disamakan.

---

## 2. PULSE

### 2.1 Isi normal
Banner GIF (§16 README), cincin pulse, 4 kartu statistik, 3 grafik 60 detik.

### 2.2 State

| State | Tampilan |
|---|---|
| `loading` | kerangka cincin + 4 kotak abu-abu, banner sudah tampil |
| `isi` | normal |
| `belum-diaudit` | cincin tetap tampil, kartu statistik menampilkan `—`, ada baris ajakan audit |
| `gagal-baca-suhu` | cincin menampilkan `—` dengan label "suhu tidak tersedia" |
| `gagal-baca-dmesg` | kartu STABILITY menampilkan `—`, bukan angka |

### 2.3 Kartu statistik — perilaku saat data hilang

| Kartu | Sumber | Kalau gagal |
|---|---|---|
| ZRAM | `/sys/block/zram0/` | `—` + ikon info |
| UPTIME | `/proc/uptime` | `—` |
| MGLRU | `/sys/kernel/mm/lru_gen/enabled` | `TIDAK ADA` (bukan `—`, karena ini fakta kernel) |
| STABILITY | `dmesg` sejak boot | `—` |

> **Aturan:** `—` berarti "gagal dibaca". `TIDAK ADA` berarti "kernel tidak punya
> fiturnya". Dua hal ini tidak boleh tertukar.

### 2.4 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `pulse_title` | PULSE | PULSE |
| `pulse_cpu_temp` | Suhu CPU | CPU temp |
| `pulse_stat_zram` | ZRAM | ZRAM |
| `pulse_stat_uptime` | AKTIF | UPTIME |
| `pulse_stat_mglru` | MGLRU | MGLRU |
| `pulse_stat_stability` | STABILITAS | STABILITY |
| `pulse_unaudited_hint` | Perangkat belum diaudit. Jalankan audit untuk melihat kapabilitas kernel. | Device not audited yet. Run an audit to see kernel capabilities. |
| `pulse_audit_button` | Audit sekarang | Run audit |
| `pulse_unavailable` | tidak tersedia | unavailable |

---

## 3. ROOT

### 3.1 State

| State | Tampilan |
|---|---|
| `loading` | 6 baris kerangka |
| `isi` | daftar app + tiga status izin |
| `kosong` | "Belum ada app yang meminta root." + tombol "Muat ulang" |
| `gagal` | sebab + "Coba lagi" |
| `kernel-salah` | layar penuh: app tidak berjalan di Fresh-Milk / CHEESE-BURGER |

### 3.2 Baris app

| Elemen | Isi |
|---|---|
| ikon | ikon app, 40 dp |
| nama | nama app |
| paket | nama paket, monospace 11 sp, abu |
| izin | segmented: TANYA / IZINKAN / TOLAK |
| penanda | jumlah penolakan hari ini, hanya bila > 0 |

### 3.3 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `root_title` | ROOT | ROOT |
| `root_perm_ask` | TANYA | ASK |
| `root_perm_allow` | IZINKAN | ALLOW |
| `root_perm_deny` | TOLAK | DENY |
| `root_empty` | Belum ada app yang meminta root. | No app has requested root yet. |
| `root_reload` | Muat ulang | Reload |
| `root_denied_today` | ditolak %d× hari ini | denied %d× today |
| `root_hook_mode` | Mode hook | Hook mode |
| `root_susfs` | SuSFS | SuSFS |

---

## 4. MODULES

### 4.1 State

| State | Tampilan |
|---|---|
| `loading` | kerangka kartu |
| `isi` | daftar modul + filter |
| `kosong` | "Belum ada modul terpasang." + "Jelajahi sumber" |
| `gagal` | sebab + "Coba lagi" |
| `ada-update` | chip UPDATE aktif dengan badge |

### 4.2 Filter

`SEMUA` → `AKTIF` → `NONAKTIF` → `UPDATE (n)`.

Aturan: filter yang menghasilkan nol hasil **tetap bisa dipilih**, dan
menampilkan `kosong` dengan kalimat khusus: *"Tidak ada modul nonaktif."*

### 4.3 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `mod_title` | MODUL | MODULES |
| `mod_filter_all` | SEMUA | ALL |
| `mod_filter_active` | AKTIF | ACTIVE |
| `mod_filter_disabled` | NONAKTIF | DISABLED |
| `mod_filter_update` | UPDATE | UPDATE |
| `mod_empty` | Belum ada modul terpasang. | No modules installed yet. |
| `mod_empty_filter` | Tidak ada modul %s. | No %s modules. |
| `mod_browse` | Jelajahi sumber | Browse sources |
| `mod_update_available` | PEMBARUAN TERSEDIA | UPDATE AVAILABLE |

---

## 5. TUNING

Bagian paling berisiko. Aturannya lebih ketat dari layar lain.

### 5.1 Alur wajib

```
buka TUNING
  → sudah diaudit?  tidak → layar "belum-diaudit", tombol "Audit sekarang"
                    ya    → tampilkan parameter sesuai status
  → user ubah slider
  → tombol APPLY aktif (ada perubahan tertunda)
  → tekan APPLY → dialog konfirmasi (bisa dimatikan di Settings)
  → tulis → verifikasi baca-ulang → tampilkan hasil
```

### 5.2 Status parameter

| Status | Tampilan | Bisa diubah |
|---|---|---|
| `supported` | slider + nilai | ya |
| `read-only` | nilai + ikon kunci + tooltip | tidak |
| `unsupported` | baris abu + alasan | tidak |
| `needs-reboot` | nilai + ikon power + catatan | tidak, sampai reboot |

Tooltip `read-only`: *"Kernel menyediakan nilai ini tapi menolak penulisan."*
Tooltip `needs-reboot`: *"Perubahan berlaku setelah reboot."*

### 5.3 Saat penulisan gagal

Empat sebab berbeda, empat pesan berbeda:

| Sebab | Pesan |
|---|---|
| izin ditolak | "Kernel menolak penulisan (izin ditolak)." |
| nilai di luar rentang | "Nilai harus antara %d dan %d." |
| node hilang mendadak | "Parameter hilang. Audit ulang diperlukan." |
| pembacaan balik tak cocok | "Nilai tertulis tapi tidak terbaca kembali. Cek manual." |

Keempatnya **bukan** "Terjadi kesalahan".

### 5.4 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `tun_title` | TUNING | TUNING |
| `tun_not_audited` | Parameter belum diaudit. Audit diperlukan sebelum mengubah apa pun. | Parameters not audited. An audit is required before changing anything. |
| `tun_apply` | TERAPKAN | APPLY CHANGES |
| `tun_reset` | KEMBALIKAN KE DEFAULT | RESET TO DEFAULT |
| `tun_confirm_title` | Terapkan perubahan? | Apply changes? |
| `tun_confirm_body` | %d parameter akan diubah. Bisa dikembalikan ke default kapan pun. | %d parameters will change. You can reset to default at any time. |
| `tun_ro_tip` | Kernel menyediakan nilai ini tapi menolak penulisan. | The kernel exposes this value but refuses writes. |
| `tun_reboot_tip` | Perubahan berlaku setelah reboot. | Takes effect after reboot. |
| `tun_err_perm` | Kernel menolak penulisan (izin ditolak). | Kernel refused the write (permission denied). |
| `tun_err_range` | Nilai harus antara %d dan %d. | Value must be between %d and %d. |
| `tun_err_gone` | Parameter hilang. Audit ulang diperlukan. | Parameter disappeared. Re-audit required. |
| `tun_err_mismatch` | Nilai tertulis tapi tidak terbaca kembali. Cek manual. | Written but not read back. Verify manually. |
| `tun_thermal_locked` | Proteksi termal tidak bisa dimatikan. | Thermal protection cannot be disabled. |

---

## 6. LAB (UGDP)

| State | Tampilan |
|---|---|
| `belum-diaudit` | tombol audit, tanpa profil |
| `supported` | 3 profil + 4 metrik |
| `read-only` | metrik tampil, profil dikunci + alasan |
| `unsupported` | "Perangkat ini tidak mendukung UGDP." + sebab |

Aturan UGDP yang mengikat:

1. **Tidak ada shell bebas.** Semua aksi lewat API terbatas.
2. **Proteksi termal tidak bisa dimatikan.**
3. **Profil dikembalikan ke balanced** saat service berhenti.

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `lab_ugdp_title` | UGDP · Profil Game Universal | UGDP · Universal Game Device Profile |
| `lab_profile_balanced` | SEIMBANG | BALANCED |
| `lab_profile_performance` | PERFORMA | PERFORMANCE |
| `lab_profile_battery` | HEMAT DAYA | BATTERY SAVER |
| `lab_unsupported` | Perangkat ini tidak mendukung UGDP. | This device does not support UGDP. |
| `lab_no_shell` | Semua aksi lewat API terbatas, tanpa shell. | All actions go through a restricted API, no shell. |

---

## 7. HIDING (SuSFS)

### 7.1 Aturan tampil

Fitur yang **tersedia** diberi centang hijau. Fitur yang **tidak tersedia**
diberi ikon info amber **beserta alasannya** — bukan disembunyikan.

Contoh nyata dari kernel kita:

```
TRY_UMOUNT      ⓘ tidak tersedia — port SuSFS 4.14 tidak membawa
                  susfs_try_umount(); gunakan jalur umount bawaan KSU-Next
SUS_MEMFD       ⓘ tidak tersedia — dimatikan di defconfig
```

### 7.2 Menambah path

Alur: ketik path → validasi bentuk → periksa keberadaan → tambahkan.

| Kegagalan | Pesan |
|---|---|
| path tidak diawali `/` | "Path harus diawali /." |
| path tidak ada | "Path tidak ditemukan di perangkat ini." |
| sudah ada di daftar | "Path ini sudah disembunyikan." |

### 7.3 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `hide_title` | PENYEMBUNYIAN | HIDING |
| `hide_tab_status` | STATUS | STATUS |
| `hide_tab_path` | PATH | PATH |
| `hide_tab_mount` | MOUNT | MOUNT |
| `hide_tab_kstat` | KSTAT | KSTAT |
| `hide_tab_map` | MAP | MAP |
| `hide_tab_redirect` | REDIRECT | OPEN REDIRECT |
| `hide_tab_standard` | STANDAR | STANDARD |
| `hide_add_hint` | Tambah path… | Add path… |
| `hide_unavailable` | tidak tersedia | unavailable |
| `hide_err_slash` | Path harus diawali /. | Path must start with /. |
| `hide_err_missing` | Path tidak ditemukan di perangkat ini. | Path not found on this device. |
| `hide_err_dup` | Path ini sudah disembunyikan. | This path is already hidden. |

---

## 8. FLASH TERKENDALI (SAFE FLASH)

### 8.1 Alur

```
pilih berkas → baca sha256 → cocokkan dengan sumber
  → BACKUP boot (wajib, tidak bisa dilewati)
  → VERIFY (sha256 + kecocokan perangkat)
  → FLASH
  → tawarkan reboot
```

### 8.2 Larangan

| Situasi | Perilaku |
|---|---|
| sha256 tidak cocok | **berhenti**, tidak ada tombol lanjut |
| perangkat tidak cocok | **berhenti**, sebut perangkat yang diharapkan vs terdeteksi |
| backup gagal | **berhenti**, tidak boleh flash |
| penyimpanan < 2× ukuran image | **berhenti** sebelum backup |

Tidak ada jalan pintas. Tidak ada "lewati backup".

### 8.3 Teks

| Kunci | Indonesia | English |
|---|---|---|
| `flash_title` | FLASH TERKENDALI | SAFE FLASH |
| `flash_step_backup` | CADANGAN | BACKUP |
| `flash_step_verify` | VERIFIKASI | VERIFY |
| `flash_step_flash` | FLASH | FLASH |
| `flash_sha_ok` | Checksum cocok | Checksum matches |
| `flash_sha_bad` | Checksum tidak cocok. Flash dibatalkan. | Checksum mismatch. Flash cancelled. |
| `flash_device_ok` | Perangkat cocok | Device matches |
| `flash_device_bad` | Perangkat tidak cocok: diharapkan %s, terdeteksi %s. | Device mismatch: expected %s, detected %s. |
| `flash_backup_failed` | Cadangan gagal. Flash dibatalkan. | Backup failed. Flash cancelled. |
| `flash_backup_mandatory` | Cadangan wajib. Tidak bisa dilewati. | Backup is mandatory. It cannot be skipped. |
| `flash_go` | FLASH KERNEL | FLASH KERNEL |
| `flash_restore` | Pulihkan cadangan | Restore backup |

---

## 9. CUSTOMIZE

| State | Tampilan |
|---|---|
| `isi` | pratinjau 3 tema + daftar + aksen + gerak |
| `gagal` | "Tema gagal dimuat." + "Coba lagi" |

Aturan: mengubah tema **langsung terlihat** di pratinjau, tapi baru tersimpan
setelah "SIMPAN TEMA". Menutup halaman tanpa simpan = kembali ke sebelumnya.

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `cus_title` | KUSTOMISASI | CUSTOMIZE |
| `cus_theme` | TEMA | THEME |
| `cus_accent` | AKSEN | ACCENT |
| `cus_motion` | GERAK | MOTION |
| `cus_follow_kernel` | Ikuti kernel | Follow kernel |
| `cus_animations` | Animasi | Animations |
| `cus_intensity` | Intensitas gerak | Motion intensity |
| `cus_subtle` | Halus | Subtle |
| `cus_balanced` | Seimbang | Balanced |
| `cus_lively` | Hidup | Lively |
| `cus_haptic` | Getar saat konfirmasi | Haptic on confirm |
| `cus_save` | SIMPAN TEMA | SAVE THEME |
| `cus_contrast_fail` | Tema ini gagal uji kontras dan tidak bisa dipakai. | This theme failed the contrast test and cannot be used. |

---

## 10. MODULE SOURCES & DETAIL

### 10.1 Sumber

| State | Tampilan |
|---|---|
| `kosong` | "Belum ada sumber." + "Tambah sumber" |
| `isi` | daftar sumber bawaan + sumber user |
| `gagal-jaringan` | "Tidak bisa menghubungi %s." + "Coba lagi" |
| `sumber-tidak-verifikasi` | baris diberi label amber |

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `src_title` | SUMBER MODUL | MODULE SOURCES |
| `src_popular` | SUMBER POPULER | POPULAR SOURCES |
| `src_yours` | SUMBER ANDA | YOUR SOURCES |
| `src_add` | TAMBAH SUMBER | ADD SOURCE |
| `src_search` | Cari sumber atau tempel URL | Search sources or paste a URL |
| `src_unverified` | Sumber tidak diverifikasi | Unverified source |
| `src_offline` | Tidak bisa menghubungi %s. | Can't reach %s. |

### 10.2 Detail modul

| State | Tampilan |
|---|---|
| `loading` | kerangka hero + tab |
| `isi` | 5 tab penuh |
| `gagal` | "Detail tidak bisa dimuat." + "Buka di GitHub" |
| `runtime-mismatch` | kartu amber: "Modul ini mungkin tidak cocok untuk kernel Anda." |

Aturan label:

- **VERIFIED** hanya untuk sumber kurasi, artinya **"dari sumber resmi"**.
- Kata **"aman"** tidak pernah dipakai.
- Statistik yang tidak tersedia tampil `—`.

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `det_tab_desc` | DESKRIPSI | DESCRIPTION |
| `det_tab_changelog` | RIWAYAT | CHANGELOG |
| `det_tab_shots` | TANGKAPAN | SCREENSHOTS |
| `det_tab_files` | BERKAS | FILES |
| `det_tab_perms` | IZIN | PERMISSIONS |
| `det_verified` | RESMI | VERIFIED |
| `det_download` | UNDUH | DOWNLOAD |
| `det_github` | LIHAT DI GITHUB | VIEW ON GITHUB |
| `det_size` | Ukuran | Size |
| `det_updated` | Diperbarui | Updated |
| `det_downloads` | Unduhan | Downloads |
| `det_mismatch` | Modul ini mungkin tidak cocok untuk kernel Anda. | This module may not match your kernel. |

---

## 11. ABOUT, SUPPORT, SETTINGS

### 11.1 About

| Elemen | Nilai |
|---|---|
| CREATOR | `@Pure_Saturday` |
| Telegram | `https://t.me/breakfastch` |
| Source | GPL-3.0 |
| Kernel didukung | `Fresh-Milk-14.03`, `CHEESE-BURGER-11.08` |

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `abt_creator` | PEMBUAT | CREATOR |
| `abt_community` | KOMUNITAS | COMMUNITY |
| `abt_telegram` | Kanal Telegram | Telegram Channel |
| `abt_support` | Dukung pengembangan | Support Development |
| `abt_source` | Kode sumber | Source Code |
| `abt_kernels` | KERNEL YANG DIDUKUNG | KERNELS SUPPORTED |

### 11.2 Support (Donate)

Aturan: **tidak ada pembayaran di dalam app.** Hanya membuka tautan luar.
Tidak ada nomor rekening, tidak ada kredensial.

| Kunci | Indonesia | English |
|---|---|---|
| `sup_title` | DUKUNGAN | SUPPORT |
| `sup_free` | BREAKFAST gratis dan akan tetap gratis. | BREAKFAST is free and stays free. |
| `sup_why` | Dukungan Anda membiayai server build dan perangkat uji. | Your support pays for build servers and test devices. |
| `sup_other` | CARA LAIN | OTHER WAYS |
| `sup_thanks` | TERIMA KASIH | THANK YOU |

### 11.3 Settings

| Kunci | Indonesia | English |
|---|---|---|
| `set_title` | PENGATURAN | SETTINGS |
| `set_language` | BAHASA | LANGUAGE |
| `set_appearance` | TAMPILAN | APPEARANCE |
| `set_security` | KEAMANAN | SECURITY |
| `set_about` | TENTANG | ABOUT |
| `set_confirm_flash` | Konfirmasi sebelum flash | Require confirmation before flashing |
| `set_confirm_tunable` | Konfirmasi sebelum mengubah parameter | Require confirmation before writing tunables |
| `set_backup_path` | Lokasi cadangan | Backup location |
| `set_licenses` | Lisensi sumber terbuka | Open source licenses |

---

## 12. Layar di luar dukungan kernel

Tampil ketika kernel bukan Fresh-Milk maupun CHEESE-BURGER.

| Elemen | Isi |
|---|---|
| judul | "Kernel tidak dikenali" |
| isi | nama kernel terdeteksi + dua nama yang diharapkan |
| aksi 1 | "Tetap buka mode terbatas" → hanya PULSE baca-saja |
| aksi 2 | "Tutup" |

Teks:

| Kunci | Indonesia | English |
|---|---|---|
| `bad_kernel_title` | Kernel tidak dikenali | Unrecognized kernel |
| `bad_kernel_body` | Terdeteksi: %s. BREAKFAST dirancang untuk Fresh-Milk-14.03 dan CHEESE-BURGER-11.08. | Detected: %s. BREAKFAST is built for Fresh-Milk-14.03 and CHEESE-BURGER-11.08. |
| `bad_kernel_limited` | Tetap buka mode terbatas | Open in limited mode |
| `bad_kernel_close` | Tutup | Close |

---

## 13. Aturan penulisan teks

1. **Kalimat aktif, bukan pasif.** "Kernel menolak penulisan", bukan
   "Penulisan ditolak".
2. **Sebutkan angka, bukan kata samar.** "3 parameter" bukan "beberapa".
3. **Tidak ada tanda seru.** Tidak ada "Ups!", tidak ada emoji.
4. **Bahasa Indonesia memakai istilah teknis apa adanya**: sysfs, kernel,
   sha256, bukan diterjemahkan paksa.
5. **Nama kernel tidak diterjemahkan** dan selalu monospace.
6. **Panjang maksimum** satu pesan: 120 karakter ID, 110 karakter EN.
   Lebih dari itu dipindah ke kartu penjelasan.
7. **Kata terlarang**: "aman", "dijamin", "100%", "pasti berhasil".

---

## 14. Yang belum ditentukan

1. Angka ambang Stability Ledger (rumusnya belum ditulis).
2. Format kode warna tema tambahan (Mint, Grape, Monochrome) — belum dibuatkan
   pratinjau.
3. Daftar lengkap parameter TUNING yang masuk whitelist.
4. Apakah audit boleh dijalankan ulang manual, atau hanya otomatis saat
   `uname -r` berubah.
