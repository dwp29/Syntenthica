# UFO-0.1 — cara memasang di pohon Kinesis

Basis: `clarencelol/kernel_xiaomi_sm6250` @ `kinesis-v29` (4.14.344, commit `427fbc7`).

## Isi paket

| Berkas | Isi |
|---|---|
| `01-synthetica32-and-susfs-tracking.patch` | 274 KB — diff semua berkas kernel yang berubah (MGLRU, UCLAMP, WALT, SuSFS hooking, wiring Kbuild/Kconfig, hook KernelSU) |
| `untracked/` | berkas baru: `KernelSU-Next/`, `fs/nomount/`, `fs/susfs.c`, `include/linux/susfs{,def}.h`, `tools/root-integration/` |
| `miatoll_defconfig` | defconfig akhir, sudah ditambal |
| `02-untracked-files.txt` | daftar berkas baru |

## Langkah

```bash
git clone --depth 1 -b kinesis-v29 https://github.com/clarencelol/kernel_xiaomi_sm6250 ufo
cd ufo

# 1. berkas baru lebih dulu
cp -a ../ufo-pkg/untracked/KernelSU-Next        .
cp -a ../ufo-pkg/untracked/fs/nomount           fs/
cp     ../ufo-pkg/untracked/fs/susfs.c          fs/
cp     ../ufo-pkg/untracked/include/linux/susfs*.h include/linux/
cp -a ../ufo-pkg/untracked/tools/root-integration tools/
ln -sfn ../KernelSU-Next/kernel drivers/kernelsu

# 2. sisanya
git apply ../ufo-pkg/01-synthetica32-and-susfs-tracking.patch
cp ../ufo-pkg/miatoll_defconfig arch/arm64/configs/vendor/xiaomi/

# 3. audit — harus keluar AUDIT PASSED
bash tools/root-integration/audit_hooks.sh .
```

## Yang sudah diverifikasi

- `AUDIT PASSED` untuk hook call sites, wiring Kbuild/Kconfig, SuSFS symbol, dan defconfig.
- Semua 8 patch Synthetica menempel tanpa `.rej`.
- SuSFS v2.3.0 · KernelSU-Next (legacy-susfs-v2) · NoMount v2.0.0 · MGLRU · UCLAMP + WALT.

## Yang BELUM diverifikasi — jangan dianggap selesai

1. **Belum pernah dikompilasi.** Tidak ada toolchain aarch64 di mesin ini.
2. **Belum diuji boot.** Tidak ada perangkat.
3. **`CONFIG_KSU_SUSFS_TRY_UMOUNT` harus tetap `n`.** `susfs_add_try_umount()`
   dipanggil di `KernelSU-Next/kernel/supercall/supercall.c:158` tetapi tidak
   didefinisikan di `fs/susfs.c` pohon ini. Kalau dinyalakan, **link gagal**.
   Audit masih melaporkan ini sebagai error; itu peringatan yang benar.
4. `CONFIG_KSU_KPROBES_HOOK` tidak diset (manual hook dipakai).

## Soal permintaan "no drain, no hot, deep sleep"

Itu **hasil**, bukan saklar. Yang bisa dikerjakan di sisi kernel:

- MGLRU (`LRU_GEN_ENABLED=y`) — mengurangi tekanan memori, sumber drain umum di 4GB RAM.
- UCLAMP + WALT + schedutil — frekuensi lebih tenang saat idle.
- `WQ_POWER_EFFICIENT_DEFAULT`, `SUSPEND_SKIP_SYNC`, thermal QTI aktif.

Tapi "deep sleep bekerja" hanya bisa dibuktikan dengan **mengukur** di perangkat:
`dumpsys batterystats`, `cat /sys/power/suspend_stats/success`, dan screen-off
selama satu malam. Tidak ada build yang bisa menjaminnya tanpa angka itu.
