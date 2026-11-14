# Uji 8 patch Synthetica di Kinesis 4.14.344

Tanggal: 13 November 2026. Pohon: `clarencelol/kernel_xiaomi_sm6250` @ `kinesis-v29`
(commit `427fbc7`, 4.14.344, 11 Mei 2024).

## Ringkas

**Kedelapan patch Synthetica menempel di Kinesis** — dengan `patch -F3`
(kelonggaran konteks 3 baris), tanpa satu pun `.rej`.

| Patch | Hasil | Keterangan |
|---|---|---|
| `0001-mglru-4.14` | diterapkan +3577 baris | 1 dari 6 hunk butuh fuzz 3: `include <linux/sched.h>` di `include/linux/mm.h` |
| `0002-uclamp-walt-stune` | diterapkan +1524 baris | 2 hunk butuh fuzz 3: posisi `extern` di `sched/sysctl.h`, satu baris di `cpufreq_schedutil.c` |
| `0003-uclamp-correctness` | diterapkan +2 baris | bersih |
| `0004-mglru-anon-file` | diterapkan +3 baris | bersih |
| `0005-mglru-pagewalk-caf` | diterapkan | bersih (bukan "sudah ada", berbeda dari pohon 4.14.357) |
| `0006-neutron-enum-cast` | diterapkan +4 baris | bersih |
| `0001-ksu-manager-preserve-seccomp` | **sudah ada** di pohon Kinesis | tidak perlu ditambal |
| `0001-manager-fd-after-exec` | **sudah ada** di pohon Kinesis | tidak perlu ditambal |

Total: 44 berkas berubah, +5105/−303 baris.

## Kenapa `git apply --check` bilang KONFLIK

`git apply` menuntut konteks **persis**, sedangkan `patch` masih menerima
pergeseran konteks beberapa baris. Tiga hunk yang gagal di `git apply` semuanya
kegagalan **posisi**, bukan isi:

- `include/linux/mm.h` — di Kinesis `#include <linux/overflow.h>` tidak ada;
  patch menyisipkan `#include <linux/sched.h>` sesudahnya. Hasil akhirnya benar
  (baris 28), hanya jangkar konteksnya hilang.
- `include/linux/sched/sysctl.h` — letak `extern` handler bergeser.
- `kernel/sched/cpufreq_schedutil.c` — `*util = uclamp_util_with(rq, *util, NULL);`
  mendarat di baris 311, tepat setelah `boosted_cpu_util()`.

## Yang tetap harus dikerjakan sebelum build

1. **KernelSU-Next belum ada di pohon Kinesis.** Kinesis 4.14.344 sudah punya
   perbaikan seccomp dan fd-after-exec, tetapi bukan KernelSU-Next. Harus
   ditambahkan sumbernya, kalau tidak `CONFIG_KSU` tidak akan ada.
2. **SuSFS / NoMount** juga belum ada di pohon ini; Roll 3.3 memakainya, jadi
   sumbernya perlu disalin dari sana.
3. **Var firmware WLAN**: 0002 menyisipkan `uclamp_util_with()` ke jalur util
   WALT. Compile-check wajib sebelum ada klaim "siap".
4. `0005-mglru-pagewalk-caf` diterapkan bersih di Kinesis tetapi *sudah ada* di
   pohon 4.14.357 — jangan pakai keduanya bersamaan saat pindah pohon.

## Catatan soal 4.14.370

Tidak ada pohon publik 4.14.370. Kinesis tertinggi 4.14.344, Saamitk 4.14.357.
Yang terbukti: `Image.gz` di zip Roll 3.3 memuat string
`4.14.370-Rollercoaster-Roll.3.3`, jadi angkanya memang ditulis saat build —
tetapi pohon sumbernya tidak pernah dipublikasikan. `backslashxx/small_module`
bukan kernel: isinya modul KernelSU 860 byte berisi aturan SELinux.
