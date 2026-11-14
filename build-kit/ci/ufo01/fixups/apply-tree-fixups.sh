#!/bin/bash
# Three fixes the Kinesis tree needs before it will link. Each one is here because a
# build log named it, not because it seemed like a good idea.
set -euo pipefail
TREE="${1:?usage: apply-tree-fixups.sh <kernel-tree>}"
cd "$TREE"

# 1. KernelSU-Next appends `obj-$(CONFIG_KSU) += kernelsu/` to drivers/Makefile and
#    `source "drivers/kernelsu/Kconfig"` to drivers/Kconfig when `make mrproper` ran
#    between, both files get reset and the module is never built -- which is why
#    CONFIG_KSU silently vanished and "No hooks were defined" appeared. Ensure wiring.
# Exactly one wiring line. The recipe already appends one, the build step appends
# another, and two of them compile the module twice and duplicate its symbols again.
python3 - <<'PY'
import pathlib
p = pathlib.Path("drivers/Makefile")
lines = p.read_text().splitlines()
out, seen = [], False
for line in lines:
    if line.strip().startswith("obj-$(CONFIG_KSU)") and "kernelsu" in line:
        if seen:
            continue           # drop the duplicate, keep one
        seen = True
    out.append(line)
if not seen:
    out.append("obj-$(CONFIG_KSU) += kernelsu/")
p.write_text("\n".join(out) + "\n")
print("-- drivers/Makefile: KSU wired exactly once")
PY
grep -q 'drivers/kernelsu/Kconfig' drivers/Kconfig || {
  printf '\nsource "drivers/kernelsu/Kconfig"\n' >> drivers/Kconfig
}

# 2. Kinesis' kernel/sysctl.c registers sched_conservative_pl and
#    sched_many_wakeup_threshold in kern_table, but nothing in the tree defines
#    either symbol, so vmlinux fails to link. Provide them where the other WALT
#    tunables live.
if ! grep -rqs '^unsigned int sysctl_sched_conservative_pl' kernel/sched/; then
  cat >> kernel/sched/tune.c <<'C'

#ifdef CONFIG_SCHED_WALT
/* Kinesis registers these in kernel/sysctl.c kern_table but never defines them. */
unsigned int sysctl_sched_conservative_pl;
unsigned int sysctl_sched_many_wakeup_threshold;
#endif
C
fi

# 3. KernelSU-Next's Kbuild injects path_umount with a sed anchored on
#    `static bool is_mnt_ns_file`. In Kinesis that line is preceded by a different
#    signature block than the one the pattern expects, so the insert never happens
#    and the link fails on an undefined path_umount. Insert it directly.
if ! grep -q '^int path_umount(struct path \*path, int flags)$' fs/namespace.c; then
  python3 - <<'PY'
import pathlib
p = pathlib.Path("fs/namespace.c")
s = p.read_text()
# can_umount is what path_umount calls, and Kinesis has no such function. KernelSU-Next
# supplies it with its own sed; that sed did not fire either, so the call had no
# declaration and clang stopped on -Wimplicit-function-declaration.
CAN = """static int can_umount(const struct path *path, int flags)
{
        struct mount *mnt = real_mount(path->mnt);

        if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))
                return -EINVAL;
        if (!may_mount())
                return -EPERM;
        if (path->dentry != path->mnt->mnt_root)
                return -EINVAL;
        if (!check_mnt(mnt))
                return -EINVAL;
        if (mnt->mnt.mnt_flags & MNT_LOCKED)
                return -EINVAL;
        if (flags & MNT_FORCE && !capable(CAP_SYS_ADMIN))
                return -EPERM;
        return 0;
}

"""
if "int path_umount(struct path *path, int flags)" not in s:
    fn = """int path_umount(struct path *path, int flags)
{
        struct mount *mnt = real_mount(path->mnt);
        int ret;

        ret = can_umount(path, flags);
        if (!ret)
                ret = do_umount(mnt, flags);

        dput(path->dentry);
        mntput_no_expire(mnt);
        return ret;
}

"""
    anchor = "static bool is_mnt_ns_file(struct dentry *dentry)"
    if anchor in s:
        if "static int can_umount" not in s:
            s = s.replace(anchor, CAN + fn + anchor, 1)
        else:
            s = s.replace(anchor, fn + anchor, 1)
        p.write_text(s)
        print("-- inserted path_umount into fs/namespace.c")
    else:
        raise SystemExit("anchor is_mnt_ns_file not found")
PY
fi
if ! grep -q 'int path_umount' fs/internal.h; then
  printf '\nint path_umount(struct path *path, int flags);\n' >> fs/internal.h
fi

# Verify every fix landed. A fixup script that silently does nothing is worse than none.
fail=0
grep -q 'obj-$(CONFIG_KSU) += kernelsu/' drivers/Makefile || { echo "FAIL: KSU not wired"; fail=1; }
grep -q '^int path_umount(struct path \*path, int flags)$' fs/namespace.c || { echo "FAIL: path_umount missing"; fail=1; }
grep -q '^static int can_umount' fs/namespace.c || { echo "FAIL: can_umount missing"; fail=1; }
grep -rqs '^unsigned int sysctl_sched_conservative_pl' kernel/sched/ || { echo "FAIL: sysctl missing"; fail=1; }
[ "$fail" -eq 0 ] && echo "-- tree fixups applied and verified"
exit "$fail"
