# Rollercoaster Kernel — miatoll (joyeuse · curtana · excalibur · gram)

Kernel custom **Linux 4.14.357 OpenELA**, build 100% LLVM (clang 18.1.8 + ld.lld 18.1.8),
oleh **graziemille**. Versi aktif: **0.0.1**.

## Tiga build (bukan varian bertingkat — tujuannya beda)

| Build | Root | Fokus | Zip |
|---|---|---|---|
| **Chronicle** | KernelSU-Next 34000 | harian + penyamaran integrity maksimal | `Rollercoaster-Chronicle-0.0.1.zip` |
| **Lite** | – | harian, baterai, tanpa jejak root | `Rollercoaster-Lite-0.0.1.zip` |
| **Critical** | KernelSU-Next 34000 | gaming, FPS tinggi, latency rendah | `Rollercoaster-Critical-0.0.1.zip` |

## Struktur proyek

```
rollercoaster/
  VERSION                    nama, versi, daftar build
  build-rollercoaster.sh     builder: build-rollercoaster.sh <tree> <chronicle|lite|critical> [jobs]
  profiles/
    00-common.config         blok bersama (perf + A17 support + zram lz4/BBR)
    chronicle.config         root + SuSFS lengkap + schedutil + cfq
    lite.config              tanpa root + hemat daya + CPU_BOOST off
    critical.config          HZ=300 + performance + deadline + KGSL adreno-tz
  patches/
    aw8624-drop-timed-output.patch
```

## Build ulang

```bash
git clone --depth 1 -b a https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff tree
bash rollercoaster/build-rollercoaster.sh tree chronicle 2
bash rollercoaster/build-rollercoaster.sh tree lite      2
bash rollercoaster/build-rollercoaster.sh tree critical  2
```

Butuh: clang-18, lld-18, llvm-18, ccache, bc, bison, flex, zip. ±35–45 menit per build
(2 job) di mesin 2 core. Hasil di `output/`.

## Aturan penting yang sudah dipelajari (jangan diubah tanpa alasan)

1. **Basis defconfig harus defconfig lengkap milik tree**, bukan blok kita saja — kalau tidak,
   `olddefconfig` mematikan hampir semua driver.
2. `CONFIG_BUG_ON_DATA_CORRUPTION` **men-`select`** `DEBUG_LIST` → dua-duanya harus turun bareng.
3. `CONFIG_TCP_CONG_BBR` di dalam `menuconfig TCP_CONG_ADVANCED`; default TCP memakai symbol
   choice `CONFIG_DEFAULT_BBR` (bukan string `DEFAULT_TCP_CONG`).
4. Choice qdisc ada di dalam `if NET_SCH_DEFAULT` → perlu `CONFIG_NET_SCH_DEFAULT=y`.
5. **`CONFIG_FTRACE` tidak boleh dimatikan**: seluruh menu `UPROBE_EVENTS`/`BPF_EVENTS` ada di
   dalam `if FTRACE`. Tanpa `BPF_EVENTS`, Android 16 QPR2/17 bootloop.
6. `CONFIG_KSU_SUSFS_SUS_MEMFD` dan `KSU_SUSFS_TRY_UMOUNT` **tidak bisa** dipakai di tree ini
   (fungsi `susfs_add_sus_memfd()`/`susfs_add_try_umount()` belum ada) → build gagal.
7. `CONFIG_HZ_300` hanya di Critical; `HZ` lain mengikuti tree (100).
8. Driver touch `focaltech_touch` butuh header `haven` yang tidak ada di tree — pada build
   berbasis config port, pakai `TOUCHSCREEN_FTS_SPI`. (Tidak relevan untuk 3 build ini yang
   memakai defconfig miatoll bawaan.)

## Verifikasi cepat

```sh
cd output && sha256sum -c SHA256SUMS
unzip -p Rollercoaster-Chronicle-0.0.1.zip anykernel.sh | grep kernel.string
```

Integrity: baca `output/INTEGRITY-SETUP.md` (jujur soal batas STRONG).

---

## Catatan SYNTHETICA-PULSE: apa yang diubah, apa yang tidak

Seluruh berkas di folder ini berasal dari bundel **Rollercoaster 1.2.0** (`Rollercoaster-1.2.0-bundle.zip`
di Drive, 66.549.979 B, lihat `DOWNLOAD.md` §0). Satu-satunya perubahan yang pernah dilakukan proyek
SYNTHETICA-PULSE ada di `build-rollercoaster.sh`, dan sifatnya **aditif**:

```
NAME="${SP_BUILD_NAME:-$NAME}"      # ditambahkan sebelum LOCALVER dihitung
KVER="${SP_BUILD_KVER:-$KVER}"
```

- Tanpa `SP_BUILD_NAME` / `SP_BUILD_KVER`, builder berperilaku **persis** seperti aslinya
  (`LOCALVER=-Rollercoaster-Chronicle-1.2.0`, sudah diuji).
- Dengan keduanya, hanya string rilis yang berubah, mis. `-SYNTHETICA-PULSE-1.15`
  (dan `-…-perf` untuk profil port).
- Tidak ada config, patch, sumber kernel, atau tool yang disentuh oleh perubahan ini.

Selain itu, proyek **tidak** memakai `anykernel.sh` dan `ksud` di folder `anykernel/` untuk
mengemas hasil: zip kita dibangun `ci/package_release.py` + `ci/release/anykernel.sh` supaya ada
backup boot + rollback. `ksud` (5.518.552 B, sha256 `52ba3da4…cdef2`) dipakai apa adanya karena
harus cocok dengan driver di dalam kernel.

Atribusi: kernel Linux 4.14.357 OpenELA (GPL-2.0) + perubahan Rollercoaster oleh **graziemille**.
Profil, patch, builder dan `ksud` tetap milik karya itu dan tidak diklaim sebagai milik proyek ini.
