# Hold Fitur + Rencana Kernel

Tanggal: 2026-10-31. Mengikat sampai dicabut.

---

## 1. Keputusan: fitur di-hold

Perintah: *"fitur di hold dulu sampai kernel siap"*.

| Area | Status | Yang boleh dikerjakan |
|---|---|---|
| Desain BREAKFAST | **HOLD** | tidak ada penambahan |
| Spesifikasi layar | **HOLD** | perbaikan fakta salah saja |
| Kode APK | **HOLD** | tidak ada |
| Kernel | **LANJUT** | ini prioritas sekarang |

Artefak desain yang sudah ada **tidak dihapus**. Ia jadi acuan saat fitur dibuka
lagi, tapi tidak dikembangkan lebih jauh sementara ini.

---

## 2. Fakta pembatas: build tidak bisa di sandbox

| Kebutuhan | Status di sandbox |
|---|---|
| `clang` | **tidak ada** |
| `aarch64-linux-gnu-gcc` | **tidak ada** |
| `dtc`, `bc`, `flex`, `bison` | **tidak ada** |
| `rsync` | tidak ada |
| Unduh toolchain dari GitHub | **bisa** (302, artefak terjangkau) |

**Kesimpulan:** kompilasi kernel **wajib** lewat GitHub Actions. Sandbox dipakai
untuk menulis resep, patch, config fragment, dan menganalisis hasil CI — bukan
untuk membangun image.

Jalur yang sudah terbukti: `.github/workflows/synthetica32-r1-kernel.yml`
(pemicu pada `push` path tertentu + `workflow_dispatch`).

---

## 3. Keputusan: root untuk Fresh-Milk & CHEESE-BURGER

Ada konflik yang belum terselesaikan dan harus dinyatakan jujur:

| Fakta | Sumber |
|---|---|
| Awalnya direncanakan **BakaSU** (UAPI 6) | permintaan user |
| Base 3.2 memakai **KernelSU-Next in-tree** | `defconfig` 3.2 |
| UAPI BakaSU **6**, kit KernelSU-Next **4** | verifikasi langsung |

**Keputusan yang diambil sekarang: tahap 1 tetap KernelSU-Next.**

Alasan:

1. Base 3.2 sudah teruji dengan KernelSU-Next. Mengganti root di percobaan
   pertama menambah **dua** variabel berubah sekaligus (kernel fitur + root),
   sehingga kalau gagal boot kita tidak tahu penyebabnya.
2. BakaSU adalah turunan SukiSU; mengganti berarti mem-port ulang SELinux hook,
   setuid hook, dan seluruh glue SuSFS.
3. Aturan kerja §1: klaim harus setara bukti. Mengganti root tanpa uji perangkat
   adalah risiko yang tidak perlu di tahap ini.

**Rencana:** BakaSU dipindah ke **tahap 2**, setelah Fresh-Milk tahap 1 terbukti
boot. Kalau user ingin BakaSU lebih awal, itu keputusan user — tapi
konsekuensinya harus dicatat di sini.

---

## 4. Temuan penting: SuSFS v2.4.0 tidak membawa `susfs_try_umount()`

Diperiksa dari `bagaasadit/Flow-Kernel` (miatoll, 4.14.357, SuSFS v2.4.0
NON-GKI). Fungsi yang diekspor `include/linux/susfs.h`:

```
susfs_add_sus_path, susfs_add_sus_path_loop, susfs_add_sus_kstat,
susfs_update_sus_kstat, susfs_add_open_redirect, susfs_add_sus_map,
susfs_set_uname, susfs_spoof_uname, susfs_enable_log,
susfs_set_cmdline_or_bootconfig, susfs_set_hide_sus_mnts_for_non_su_procs,
susfs_set_avc_log_spoofing, susfs_set_priority_uid_filter,
susfs_is_priority_uid_filtered, susfs_parse_priority_app_strings,
susfs_get_enabled_features, susfs_show_version, susfs_show_variant,
susfs_start_sdcard_monitor_fn, susfs_init
```

**`susfs_try_umount` / `susfs_add_try_umount` tidak ada** — `grep` = 0.

Konsekuensi:

- Naik dari v2.3.0 ke v2.4.0 **tidak** membuka `CONFIG_KSU_SUSFS_TRY_UMOUNT`.
  Komentar di defconfig 3.2 tetap berlaku.
- Fitur baru v2.4.0 yang **memang** ada: **AVC log spoofing**
  (`susfs_set_avc_log_spoofing`), **hide sus mounts untuk non-su**
  (`susfs_set_hide_sus_mnts_for_non_su_procs`), **priority uid filter**,
  **sus path loop**, **sdcard monitor**.
- `CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS` (`0x55561`) dan
  `CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING` (`0x60010`) tersedia.
- `CMD_SUSFS_UMOUNT_FOR_ZYGOTE_ISO_SERVICE` (`0x55562`) berstatus **deprecated**.

---

## 5. Rencana kernel — tahap

### Tahap 1 — Fresh-Milk-14.03 (stabilitas) — **kompilasi SELESAI**

Tujuan: kernel yang **paling mungkin boot**, dengan fitur 3.2 utuh.

| # | Perubahan | Risiko |
|---|---|---|
| 1 | Base: resep 3.2-r1 (`build_synthetica32_r1.py`) | rendah — sudah 359 tes lulus |
| 2 | `CONFIG_LOCALVERSION="-fresh-milk-14.03"` | rendah |
| 3 | `EXTRAVERSION` tetap `-openela`, jadi uname = `4.14.357-openela-<LOCALVERSION>` (§5.1) | rendah |
| 4 | SuSFS v2.3.0 → v2.4.0 | **dibatalkan sekarang** — tetap v2.3.0; v2.4.0 tidak membuka TRY_UMOUNT |
| 5 | `CONFIG_TMPFS_XATTR=y` | rendah |
| 6 | `CONFIG_CRYPTO_ZSTD=y` | rendah |
| 7 | `CONFIG_CRYPTO_LZ4HC=y` | rendah |
| 8 | Perbaikan haptic (3 hipotesis, §6) | sedang |

### 5.1 Soal nama di `uname -r`

`CONFIG_LOCALVERSION` **menggantikan** localversion, bukan menambah. Huruf
besar/kecil **persis** seperti yang ditulis. Jadi untuk `Fresh-Milk-14.03`
dengan kapital, nilainya `CONFIG_LOCALVERSION="-Fresh-Milk-14.03"`.

**Keputusan: kapital.** `Fresh-Milk-14.03` dan `CHEESE-BURGER-11.08`, sesuai
desain BREAKFAST.

#### Koreksi penting (ditemukan lewat CI)

Dokumen ini sempat menyiratkan nama kernel disetel dengan menulis fragment
config. **Itu salah.** `ci/rollercoaster/build-rollercoaster.sh` membentuk
`CONFIG_LOCALVERSION` dari `SP_BUILD_NAME` dan `SP_BUILD_KVER`:

```sh
LOCALVER="-${NAME}-${KVER}"
```

Menulis fragment config tidak berpengaruh apa pun pada nama rilis. Karena itu:

- identitas ada di tabel varian `build_fresh_milk.py`, bukan di config;
- `SP_BUILD_NAME` / `SP_BUILD_KVER` wajib berkapitalisasi benar;
- CI punya asersi yang gagal kalau hasil build menyimpang.

#### Bukti

Run **44546020859**, kedua varian sukses:

| | Fresh-Milk | CHEESE-BURGER |
|---|---|---|
| LOCALVERSION terbangun | `"-Fresh-Milk-14.03"` | `"-CHEESE-BURGER-11.08"` |
| config berubah dari 3.1 | `LOCALVERSION` saja | `LOCALVERSION` saja |
| ekspor dibandingkan | 12.236 | 12.236 |
| selisih ABI | 0 | 0 |

Rincian: `docs/FRESH-MILK-BUILD.md`.

### Tahap 2 — CHEESE-BURGER-11.08 (gaming)

**Revisi setelah membaca kit.** Rencana awal (thermal/boost/GPU/ION berbeda)
tidak dipakai. Alasannya: kit sudah punya pemisahan ini sebagai **profil**,
dan profil yang berbeda dari `synthetica` berarti config berbeda dari 3.1 —
tepat hal yang dijaga oleh resep 3.2-r1.

| Profil | Dipakai | Isi |
|---|---|---|
| `ci/rollercoaster/profiles/synthetica.config` | **ya**, kedua varian | schedutil, mq-deadline, WQ power-efficient |
| `ci/rollercoaster/profiles/critical.config` | **tidak** | HZ 300, governor performance, KGSL, Adreno devfreq |

Jadi saat ini **kedua varian memakai config yang sama persis**. Yang berbeda
hanya nama. Ini disengaja: membuat CHEESE-BURGER benar-benar gaming menuntut
profil `critical`, dan itu berarti ABI-nya tidak lagi identik dengan 3.1 —
keputusan yang harus diambil sadar, bukan sebagai efek samping.

**Terbuka:** kalau CHEESE-BURGER memang harus lebih cepat, langkahnya adalah
mengizinkan `critical.config` secara eksplisit sebagai varian kedua, lengkap
dengan penjaga ABI-nya sendiri.

### Tahap 3 — BakaSU

Setelah tahap 1 boot. Porting root + glue SuSFS ke UAPI 6.

---

## 6. Haptic — tiga hipotesis, ditandai sebagai hipotesis

Tidak ada log `dumpsys vibrator_manager`. Perbaikan dilakukan bersamaan.

| # | Perbaikan | Dasar |
|---|---|---|
| 1 | Lewati kompensasi vbat untuk getar < 50 ms | `aw8624_haptic_ram_vbat_comp()` menskala gain dengan voltase baterai (`AW8624_VBAT_REFER=4200`) |
| 2 | Periksa jeda retry I2C | log boot menunjukkan `i2c_read error=-107` (ENOTCONN) pada percobaan pertama |
| 3 | Periksa urutan tulis `duration` → `activate` | efek pendek butuh trigger cepat |

**Peringatan jujur:** tanpa `dumpsys`, ini **bukan diagnosis**. Ketiganya bisa
salah sasaran. Kalau getar masih hilang setelah ketiganya, langkah berikutnya
adalah meminta log — bukan menambah perbaikan keempat yang ditebak.

---

## 7. Yang harus dikonfirmasi sebelum CI dijalankan

1. **Kapitalisasi nama** di `CONFIG_LOCALVERSION`.
2. **Root tahap 1**: setuju tetap KernelSU-Next, atau tetap BakaSU sekarang?
3. **SuSFS v2.4.0** dinaikkan di tahap 1, atau tetap v2.3.0 dulu supaya
   variabelnya lebih sedikit?
