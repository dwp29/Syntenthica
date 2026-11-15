#!/bin/bash
# Tanam fitur Synthetica 3.2 ke pohon 4.14.357 yang sudah membawa SuSFS + KernelSU.
#
# Kenapa skrip ini ada, dan kenapa bukan patch gabungan 4.14.344:
#
# Patch gabungan `ufo01/01-synthetica32-and-susfs-tracking.patch` dibuat di atas
# Kinesis 4.14.344. Diukur dengan `git apply --check` di pohon 4.14.357: 13 dari 67
# berkas gagal. Patch asli Synthetica -- enam berkas terpisah -- justru menempel
# BERSIH di 4.14.357, tapi HANYA kalau dijalankan berurutan:
#   0003 mengubah `enum uclamp_id` -> `unsigned int` pada kode yang baru ada setelah
#        0002 menempel, jadi 0003 diuji sendirian pasti konflik.
#   0005 menyentuh pagewalk yang baru ditulis 0001.
# Jadi urutan itu syarat, bukan selera. Skrip ini menjalankannya berurutan dan
# berhenti keras kalau satu saja tidak menempel.
#
# Yang TIDAK dilakukan skrip ini: menanam SuSFS, KernelSU, atau NoMount. Pohon 357
# yang dipakai (Saamitk/kernel_xiaomi_sm6250-switchoff) sudah membawa ketiganya.
# Menanam ulang berarti menabrak kode yang sudah ada, dan itu yang membuat patch
# gabungan 344 gagal di 30 berkas.
set -euo pipefail

TREE="${1:?usage: apply_synthetica357.sh <kernel-tree> <patch-dir> [defconfig]}"
PATCHES="${2:?butuh direktori berisi 0001..0006 Synthetica}"
DEF="${3:-arch/arm64/configs/vendor/xiaomi/miatoll_defconfig}"

cd "$TREE"

ORDER=(
  0001-mglru-4.14.patch
  0002-uclamp-walt-stune.patch
  0003-uclamp-correctness.patch
  0004-mglru-anon-file.patch
  0005-mglru-pagewalk-caf.patch
  0006-neutron-enum-cast.patch
)

for p in "${ORDER[@]}"; do
  f="$PATCHES/$p"
  [ -f "$f" ] || { echo "-- TIDAK ADA: $f"; exit 1; }
  if git apply --check -p1 "$f" 2>/tmp/apply-err.txt; then
    git apply -p1 "$f"
    echo "OK      $p"
  else
    echo "GAGAL   $p"
    sed -n '1,10p' /tmp/apply-err.txt
    exit 1
  fi
done

# Patch yang "sukses" tapi menempel di tempat salah akan menghasilkan kernel tanpa
# fitur. Setiap hitungan di bawah adalah penjaga terhadap itu.
check() {
  local what="$1" file="$2" pattern="$3" min="$4"
  local n
  n=$(grep -c "$pattern" "$file" 2>/dev/null || true)
  if [ "${n:-0}" -lt "$min" ]; then
    echo "GAGAL   $what: $file hanya $n kemunculan '$pattern' (butuh >= $min)"
    exit 1
  fi
  echo "OK      $what ($n)"
}

check "MGLRU di vmscan"        mm/vmscan.c            "lru_gen"       100
check "MGLRU Kconfig"          mm/Kconfig             "config LRU_GEN"  1
check "UCLAMP di sched/core"   kernel/sched/core.c    "uclamp"         50
check "UCLAMP di sched.h"      include/linux/sched.h  "uclamp"          3

# Fitur harus DINYALAKAN, bukan hanya ada di kode. Tanpa config, MGLRU dan UCLAMP
# tidak ikut dikompilasi sama sekali -- persis kegagalan yang dulu lolos dari tiga
# pemeriksaan berturut-turut karena yang diperiksa hanya nama berkas.
python3 - "$DEF" <<'PY'
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
lines = p.read_text().splitlines()
want = [
    "CONFIG_LRU_GEN=y",
    "CONFIG_LRU_GEN_ENABLED=y",
    "CONFIG_UCLAMP_TASK=y",
    "CONFIG_UCLAMP_TASK_GROUP=y",
    "CONFIG_NR_LRU_GENS=7",
    "CONFIG_UCLAMP_BUCKETS_COUNT=5",
]
have = {l.split("=")[0].strip() for l in lines if l.strip().startswith("CONFIG_")}
add = [w for w in want if w.split("=")[0] not in have]
if add:
    lines.extend(["", "# Synthetica 3.2: MGLRU + UCLAMP (ditanam apply_synthetica357.sh)"] + add)
    p.write_text("\n".join(lines) + "\n")
    print(f"-- defconfig: {len(add)} baris ditambahkan")
else:
    print("-- defconfig: sudah lengkap")
PY

echo "-- semua patch Synthetica masuk dan fiturnya menyala"
