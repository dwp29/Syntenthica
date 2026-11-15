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

# --------------------------------------------------------------------------
# Perbaikan pohon, terpisah dari patch Synthetica.
#
# Build 43694424815 berhenti di drivers/misc/aw8624_haptic:
#     aw8624.h:25:10: fatal error: 'linux/timed_output.h' file not found
# Header itu ADA di pohon ini, di drivers/staging/android/timed_output.h --
# tempat 4.14 meletakkannya sebelum pindah ke include/linux. Driver tetangga
# (drv2624_haptic) sudah memakai path relatif untuk alasan yang sama; aw8624
# tidak. Yang diperbaiki adalah include-nya, bukan config: mematikan
# CONFIG_AW8624_HAPTIC akan menghilangkan haptic pada perangkat yang memakainya.
echo "-- perbaikan pohon: include timed_output.h"
python3 - drivers/misc/aw8624_haptic/aw8624.h <<'PYFIX'
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
if not p.exists():
    print(f"   {p} tidak ada -- dilewati")
    raise SystemExit(0)
s = p.read_text()
bad = "#include <linux/timed_output.h>"
good = "#include <../../../drivers/staging/android/timed_output.h>"
if bad not in s:
    print("   sudah diperbaiki atau bentuknya lain -- dilewati")
    raise SystemExit(0)
p.write_text(s.replace(bad, good, 1))
print(f"   {p}: include diarahkan ke path yang benar")
PYFIX

# --------------------------------------------------------------------------
# path_umount, disuntikkan SEBELUM build.
#
# Build 43695940575 berhenti di link:
#     ld.lld: error: undefined symbol: path_umount
#     >>> referenced by kernel_umount.c ... (umount_tw_func)
#     >>> did you mean: path_mount
#
# KernelSU-Next menyuntikkan path_umount sendiri dari drivers/kernelsu/Kbuild
# lewat sed ke fs/namespace.c. Itu jalan hanya bila Kbuild drivers/ dibaca
# SEBELUM fs/namespace.c dikompilasi. Dengan `make -j`, urutan itu tidak dijamin,
# dan di runner ia kalah balapan -- ccflags -DKSU_HAS_PATH_UMOUNT menyala, jadi
# kernel_umount.c memanggil path_umount, tetapi fungsinya tidak pernah masuk.
# Membiarkan ini bergantung pada nasib berarti build kadang lolos kadang tidak.
# Karena itu suntikan dilakukan di sini, deterministik, dengan teks yang SAMA
# dengan yang dipakai Kbuild (bukan versi karangan sendiri).
echo "-- path_umount: suntik deterministik ke fs/namespace.c"
python3 - <<'PYUM'
import pathlib

ns = pathlib.Path("fs/namespace.c")
ih = pathlib.Path("fs/internal.h")

if "int path_umount(struct path *path, int flags)" in ns.read_text():
    print("   sudah ada -- dilewati")
else:
    can = """static int can_umount(const struct path *path, int flags)
{
\tstruct mount *mnt = real_mount(path->mnt);

\tif (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))
\t\treturn -EINVAL;
\tif (!may_mount())
\t\treturn -EPERM;
\tif (path->dentry != path->mnt->mnt_root)
\t\treturn -EINVAL;
\tif (!check_mnt(mnt))
\t\treturn -EINVAL;
\tif (mnt->mnt.mnt_flags & MNT_LOCKED)
\t\treturn -EINVAL;
\tif (flags & MNT_FORCE && !capable(CAP_SYS_ADMIN))
\t\treturn -EPERM;
\treturn 0;
}

int path_umount(struct path *path, int flags)
{
\tstruct mount *mnt = real_mount(path->mnt);
\tint ret;

\tret = can_umount(path, flags);
\tif (!ret)
\t\tret = do_umount(mnt, flags);
\tdput(path->dentry);
\tmntput_no_expire(mnt);
\treturn ret;
}

"""
    text = ns.read_text()
    anchor = "static bool is_mnt_ns_file(struct dentry *dentry)"
    if anchor not in text:
        raise SystemExit("   GAGAL: jangkar is_mnt_ns_file tidak ada")
    ns.write_text(text.replace(anchor, can + anchor, 1))
    print("   fs/namespace.c: can_umount + path_umount disuntik")

if "int path_umount(struct path *path, int flags);" in ih.read_text():
    print("   fs/internal.h: sudah ada -- dilewati")
else:
    t = ih.read_text()
    a = "extern void __init mnt_init"
    if a not in t:
        raise SystemExit("   GAGAL: jangkar mnt_init tidak ada di fs/internal.h")
    a_end = t.index(a)
    line_end = t.index("\n", a_end) + 1
    t = t[:line_end] + "int path_umount(struct path *path, int flags);\n" + t[line_end:]
    ih.write_text(t)
    print("   fs/internal.h: deklarasi ditambahkan")

# Bukti, bukan asumsi: keduanya harus benar-benar ada sekarang.
for f, needle in ((ns, "int path_umount(struct path *path, int flags)"),
                  (ih, "int path_umount(struct path *path, int flags);")):
    if needle not in f.read_text():
        raise SystemExit(f"   GAGAL: {f} tetap tanpa path_umount")
print("   terverifikasi: definisi dan deklarasi ada")
PYUM

# --------------------------------------------------------------------------
# Batas ukuran sertifikat manager.
#
# check_block() di drivers/kernelsu/manager/apk_sign.c memakai
#     #define CERT_MAX_LENGTH 1024
# lalu membandingkan certificate_size dengan batas itu. Sertifikat v2 APK Pure
# Manager berukuran 1373 byte, jadi syarat "certificate_size > CERT_MAX_LENGTH"
# SELALU benar dan kompiler membuang perbandingannya. Buktinya dari image hasil
# build pertama: check_block memuat SUBS #1373 lalu langsung printk "cert length
# overlimit" tanpa cabang lain -- kernel menolak manager-nya sendiri, dan satu-
# satunya jejaknya satu baris di dmesg. Mengganti hash saja tidak pernah cukup.
#
# Batas dinaikkan ke 4096: cukup untuk sertifikat yang jauh lebih besar, tetap
# buffer kernel (4 KB per pemeriksaan), bukan 128 KB yang menempel di stack.
echo "-- batas sertifikat manager dinaikkan (1373 > 1024)"
python3 - <<'PYBOUND'
import pathlib
import sys

p = pathlib.Path("drivers/kernelsu/manager/apk_sign.c")
if not p.exists():
    sys.exit("   GAGAL: apk_sign.c tidak ada")
s = p.read_text()
old = "#define CERT_MAX_LENGTH 1024"
new = "#define CERT_MAX_LENGTH 4096"
if old not in s:
    if new in s:
        print("   sudah dinaikkan -- dilewati")
        raise SystemExit(0)
    sys.exit("   GAGAL: tidak menemukan CERT_MAX_LENGTH 1024")
s = s.replace(old, new, 1)
p.write_text(s)

# Bukti di sumber, bukan asumsi bahwa replace berhasil.
got = [l.strip() for l in p.read_text().splitlines() if "CERT_MAX_LENGTH 4" in l]
print(f"   apk_sign.c: {got}")
if "1373" in s and "#define CERT_MAX_LENGTH 4096" not in s:
    sys.exit("   GAGAL: batas tidak berubah")
PYBOUND

echo "-- semua patch Synthetica masuk dan fiturnya menyala"
