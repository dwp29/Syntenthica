#!/usr/bin/env python3
"""Host-only regression checks; not a kernel boot, root, or thermal test."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build-kit/scripts/build_synthetica2_experimental.py"
spec = importlib.util.spec_from_file_location("s2x", SCRIPT)
s2x = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(s2x)


class ConfigGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = s2x.v3.verified_baseline(ROOT / "artifacts/generated.config.txt")
        cls.good = cls.baseline.replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                        'CONFIG_LOCALVERSION="-Synthetica-2.0-exp"')
        cls.good += "\n" + "\n".join((
            "CONFIG_UCLAMP_TASK=y", "CONFIG_UCLAMP_TASK_GROUP=y", "CONFIG_UCLAMP_BUCKETS_COUNT=5",
            "CONFIG_LRU_GEN=y", "# CONFIG_LRU_GEN_ENABLED is not set", "# CONFIG_LRU_GEN_STATS is not set",
            "CONFIG_NR_LRU_GENS=7", "CONFIG_TIERS_PER_GEN=4", ""))

    def test_only_reviewed_changes_are_allowed(self):
        changed = s2x.check_config(self.baseline, self.good)
        self.assertEqual(set(changed), set(s2x.ALLOWED_CHANGES))

    def test_existing_walt_and_schedtune_are_required(self):
        for sym in ("SCHED_WALT", "SCHED_TUNE", "CPU_FREQ_GOV_SCHEDUTIL", "CGROUP_SCHED"):
            with self.subTest(sym=sym):
                bad = self.good.replace(f"CONFIG_{sym}=y", f"# CONFIG_{sym} is not set")
                with self.assertRaisesRegex(ValueError, sym):
                    s2x.check_config(self.baseline, bad)

    def test_module_signature_and_verity_cannot_be_disabled(self):
        for sym in ("MODULE_SIG_FORCE", "MODVERSIONS", "SECURITY_SELINUX", "DM_VERITY", "KSU"):
            with self.subTest(sym=sym):
                bad = self.good.replace(f"CONFIG_{sym}=y", f"# CONFIG_{sym} is not set")
                with self.assertRaisesRegex(ValueError, sym):
                    s2x.check_config(self.baseline, bad)

    def test_mglru_on_at_boot_is_rejected_until_validated(self):
        bad = self.good.replace("# CONFIG_LRU_GEN_ENABLED is not set", "CONFIG_LRU_GEN_ENABLED=y")
        with self.assertRaisesRegex(ValueError, "LRU_GEN_ENABLED"):
            s2x.check_config(self.baseline, bad)

    def test_mglru_stats_and_unrequested_config_are_rejected(self):
        for bad in (self.good.replace("# CONFIG_LRU_GEN_STATS is not set", "CONFIG_LRU_GEN_STATS=y"),
                    self.good + "CONFIG_S2X_UNEXPECTED_OPTION=y\n"):
            with self.assertRaises(ValueError):
                s2x.check_config(self.baseline, bad)

    def test_missing_feature_wrong_bucket_or_duplicate_line_rejected(self):
        for bad in (self.good.replace("CONFIG_UCLAMP_TASK=y", "# CONFIG_UCLAMP_TASK is not set"),
                    self.good.replace("CONFIG_UCLAMP_BUCKETS_COUNT=5", "CONFIG_UCLAMP_BUCKETS_COUNT=20"),
                    self.good + "CONFIG_LRU_GEN=y\n"):
            with self.assertRaises(ValueError):
                s2x.check_config(self.baseline, bad)


class PatchSafetyTests(unittest.TestCase):
    def test_pinned_files_and_unchanged_real_manager_identity(self):
        s2x.check_inputs()
        manager = s2x.verify_manager()
        self.assertEqual(manager["package"], "net.ember.labs")
        self.assertEqual(manager["cert_sha256"], s2x.MANAGER_CERT_SHA)
        self.assertEqual(manager["cert_der_bytes"], 1381)

    def test_upstream_bucket_bounds_fix_covers_all_kconfig_values(self):
        patch = (s2x.INPUTS / "patches/0002-uclamp-walt-stune.patch").read_text()
        self.assertIn("return min_t(unsigned int, clamp_value / UCLAMP_BUCKET_DELTA,", patch)
        self.assertIn("UCLAMP_BUCKETS - 1);", patch)
        # Regression: 1024/51 == 20 is out-of-bounds for 20 buckets without the fix.
        self.assertEqual(1024 // ((1024 + 20 // 2) // 20), 20)
        for count in range(5, 21):
            delta = (1024 + count // 2) // count
            for value in range(1025):
                self.assertLess(min(value // delta, count - 1), count)

    def test_fork_sync_and_neutral_rt_default_are_present(self):
        patch = (s2x.INPUTS / "patches/0002-uclamp-walt-stune.patch").read_text()
        self.assertIn("write_unlock_irq(&tasklist_lock);\n \n \tproc_fork_connector(p);\n+\tsched_post_fork(p);", patch)
        self.assertIn("+void sched_post_fork(struct task_struct *p)\n+{\n+\tuclamp_post_fork(p);", patch)
        self.assertIn("+unsigned int sysctl_sched_uclamp_util_min_rt_default;", patch)
        self.assertIn("*util = boosted_cpu_util(cpu, &loadcpu->walt_load);\n+\t*util = uclamp_util_with(rq, *util, NULL);", patch)

    def test_mglru_has_anon_and_file_array_dimension(self):
        fix = (s2x.INPUTS / "patches/0004-mglru-anon-file.patch").read_text()
        self.assertIn("+#define ANON_AND_FILE 2", fix)
        fix = (s2x.INPUTS / "patches/0005-mglru-pagewalk-caf.patch").read_text()
        self.assertIn("-\t\tif (ops->p4d_entry) {", fix)
        self.assertIn(" \t\t\terr = walk->p4d_entry(p4d, addr, next, walk);", fix)

    def test_neutron_enum_fix_preserves_the_existing_error_value(self):
        patch = (s2x.INPUTS / "patches/0006-neutron-enum-cast.patch").read_text()
        self.assertIn("-\t\treturn A_ERROR;", patch)
        self.assertIn("+\t\treturn (QDF_STATUS)A_ERROR;", patch)
        self.assertNotIn("Wno-error", patch)
        code = r"""
#include <assert.h>
typedef enum { A_ERROR = -1, A_OK = 0 } A_STATUS;
typedef enum { QDF_STATUS_SUCCESS, QDF_STATUS_E_RESOURCES } QDF_STATUS;
static QDF_STATUS old_return(void) { return A_ERROR; }
static QDF_STATUS cast_return(void) { return (QDF_STATUS)A_ERROR; }
int main(void) { assert(old_return() == cast_return()); return 0; }
"""
        with tempfile.TemporaryDirectory(prefix="s2x-enum-c-") as temp:
            src, binary = Path(temp) / "test.c", Path(temp) / "test"
            src.write_text(code)
            subprocess.run(["gcc", "-std=c99", str(src), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_uclamp_fix_executes_active_idle_and_group_corner_cases(self):
        # Compile the *actual newly patched C function bodies* against small
        # controlled stubs. This is not a kernel, concurrency, or device test.
        patch = (s2x.INPUTS / "patches/0003-uclamp-correctness.patch").read_text()
        updated = "\n".join(line[1:] for line in patch.splitlines()
                            if line.startswith((" ", "+")) and not line.startswith("+++"))
        start = updated.index("static inline void uclamp_rq_reinc_id(")
        end = updated.index("\n}", start) + len("\n}")
        reinc = updated[start:end]
        start = updated.index("\tstruct uclamp_se uc_req = p->uclamp_req[clamp_id];")
        end = updated.index("\n\treturn uc_req;", updated.index("#endif", start)) + len("\n\treturn uc_req;")
        restrict = "static struct uclamp_se restrict_test(struct task_struct *p, enum uclamp_id clamp_id)\n{\n" + updated[start:end] + "\n}"
        harness = r"""
#include <assert.h>
#include <stdbool.h>
#define CONFIG_UCLAMP_TASK_GROUP 1
#define UCLAMP_FLAG_IDLE 1
/* Model the 4.14 type-checking clamp: typeof(bitfield) is invalid. */
#define kernel_min(x, y) ({ typeof(x) _x = (x); typeof(y) _y = (y); _x < _y ? _x : _y; })
#define kernel_max(x, y) ({ typeof(x) _x = (x); typeof(y) _y = (y); _x > _y ? _x : _y; })
#define clamp(val, lo, hi) kernel_min((typeof(val))kernel_max(val, lo), hi)
enum uclamp_id { UCLAMP_MIN, UCLAMP_MAX, UCLAMP_CNT };
struct uclamp_se { unsigned int value : 11; bool active; bool user_defined; };
struct task_group { struct uclamp_se uclamp[UCLAMP_CNT]; bool autogroup; };
struct task_struct { struct uclamp_se uclamp[UCLAMP_CNT], uclamp_req[UCLAMP_CNT]; struct task_group *tg; };
struct rq { unsigned int uclamp_flags; int inc[UCLAMP_CNT], dec[UCLAMP_CNT]; };
static struct task_group root_task_group;
static struct task_group *task_group(struct task_struct *p) { return p->tg; }
static bool task_group_is_autogroup(struct task_group *g) { return g->autogroup; }
static void uclamp_se_set(struct uclamp_se *se, unsigned int value, bool user) { se->value = value; se->user_defined = user; }
static void uclamp_rq_dec_id(struct rq *rq, struct task_struct *p, enum uclamp_id id) {
    assert(p->uclamp[id].active); rq->dec[id]++; p->uclamp[id].active = false;
    if (id == UCLAMP_MAX) rq->uclamp_flags |= UCLAMP_FLAG_IDLE;
}
static void uclamp_rq_inc_id(struct rq *rq, struct task_struct *p, enum uclamp_id id) {
    assert(!p->uclamp[id].active); rq->inc[id]++; p->uclamp[id].active = true;
}
""" + reinc + "\n" + restrict + r"""
int main(void) {
    struct task_group group = { .uclamp = {{.value=307}, {.value=512}} };
    struct task_struct task = { .tg=&group, .uclamp_req = {{.value=614}, {.value=205}} };
    struct rq rq = { .uclamp_flags=UCLAMP_FLAG_IDLE };
    /* Inactive tasks must never be re-accounted or change idle state. */
    uclamp_rq_reinc_id(&rq, &task, UCLAMP_MAX);
    assert(!rq.dec[UCLAMP_MAX] && !rq.inc[UCLAMP_MAX] && rq.uclamp_flags == UCLAMP_FLAG_IDLE);
    /* Min updates must not clear the independently held max-idle flag. */
    task.uclamp[UCLAMP_MIN].active = true;
    uclamp_rq_reinc_id(&rq, &task, UCLAMP_MIN);
    assert(rq.dec[UCLAMP_MIN] == 1 && rq.inc[UCLAMP_MIN] == 1 && rq.uclamp_flags == UCLAMP_FLAG_IDLE);
    /* A last-task max re-accounting must clear its transient idle flag. */
    task.uclamp[UCLAMP_MAX].active = true; rq.uclamp_flags = 0;
    uclamp_rq_reinc_id(&rq, &task, UCLAMP_MAX);
    assert(rq.dec[UCLAMP_MAX] == 1 && rq.inc[UCLAMP_MAX] == 1 && rq.uclamp_flags == 0);
    /* Crossed per-task requests are constrained within the group range. */
    assert(restrict_test(&task, UCLAMP_MIN).value == 512);
    assert(restrict_test(&task, UCLAMP_MAX).value == 307);
    group.uclamp[UCLAMP_MIN].value = 0; group.uclamp[UCLAMP_MAX].value = 1024;
    assert(restrict_test(&task, UCLAMP_MIN).value == 614);
    assert(restrict_test(&task, UCLAMP_MAX).value == 205);
    task.tg = &root_task_group;
    assert(restrict_test(&task, UCLAMP_MIN).value == 614);
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="s2x-uclamp-c-") as temp:
            src, binary = Path(temp) / "test.c", Path(temp) / "test"
            src.write_text(harness)
            subprocess.run(["gcc", "-std=gnu99", "-Wall", "-Werror", str(src), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_uclamp_group_online_and_initial_rq_are_guarded(self):
        patch = (s2x.INPUTS / "patches/0003-uclamp-correctness.patch").read_text()
        self.assertIn("+\trq->uclamp_flags = UCLAMP_FLAG_IDLE;", patch)
        self.assertIn("+\tif (parent) {", patch)  # not the pre-scheduler root callback
        self.assertIn("+\t\tmutex_lock(&uclamp_mutex);", patch)
        self.assertIn("+\t\trcu_read_lock();", patch)
        self.assertIn("+\t\tcpu_util_update_eff(css);", patch)
        self.assertIn("+\t\tmutex_unlock(&uclamp_mutex);", patch)
        self.assertIn("+\tfor_each_clamp_id(clamp_id)\n+\t\tuclamp_rq_reinc_id(rq, p, clamp_id);", patch)

    def test_no_root_or_thermal_source_files_are_touched(self):
        for name in s2x.PATCHES:
            patch = (s2x.INPUTS / "patches" / name).read_text()
            paths = [row.split(" b/", 1)[1] for row in patch.splitlines() if row.startswith("diff --git ")]
            self.assertTrue(paths)
            for path in paths:
                self.assertNotIn("kernelsu", path.lower())
                self.assertNotIn("thermal", path.lower())
                self.assertNotIn("defconfig", path.lower())

    def test_git_apply_chain_to_real_pinned_source_when_fixture_supplied(self):
        # Optional sparse copy of the affected, unmodified pinned source files.
        # CI also applies the patch chain to the complete SHA-verified archive.
        fixture = os.environ.get("S2X_PATCH_FIXTURE")
        if not fixture:
            self.skipTest("no locally extracted source fixture")
        with tempfile.TemporaryDirectory(prefix="s2x-patch-") as temp:
            tree = Path(temp) / "tree"
            shutil.copytree(fixture, tree)
            s2x.prepare_tree(tree)
            core = (tree / "kernel/sched/core.c").read_text()
            fork = (tree / "kernel/fork.c").read_text()
            self.assertIn("UCLAMP_BUCKETS - 1);", core)
            self.assertIn("if (!p->uclamp[clamp_id].active)\n\t\treturn;", core)
            self.assertIn("rq->uclamp_flags = UCLAMP_FLAG_IDLE;", core)
            self.assertIn("#define ANON_AND_FILE 2", (tree / "include/linux/mmzone.h").read_text())
            pagewalk = (tree / "mm/pagewalk.c").read_text()
            self.assertNotIn("ops->p4d_entry", pagewalk)
            self.assertEqual(pagewalk.count("err = walk->p4d_entry(p4d, addr, next, walk);"), 1)
            ce = (tree / "drivers/staging/qca-wifi-host-cmn/hif/src/ce/ce_main.c").read_text()
            self.assertEqual(ce.count("return (QDF_STATUS)A_ERROR;"), 1)
            self.assertIn("sched_post_fork(p);", fork)
            self.assertIn("$(KCONFIG_CONFIG) FORCE", (tree / "kernel/Makefile").read_text())
            duplicate = subprocess.run(
                ["git", "apply", "--check", str(s2x.INPUTS / "patches/0001-mglru-4.14.patch")],
                cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(duplicate.returncode, 0)  # no silent double application


class IsolatedBuildTests(unittest.TestCase):
    def test_prepare_makes_no_installer_and_keeps_originals_unchanged(self):
        builder = ROOT / "build-kit/ci/rollercoaster/build-rollercoaster.sh"
        profile = ROOT / "build-kit/ci/rollercoaster/profiles/synthetica.config"
        before = {p: s2x.v3.digest(p) for p in (builder, profile, ROOT / "release/Synthetica-2.0.apk")}
        with tempfile.TemporaryDirectory(prefix="s2x-kit-test-") as temp:
            kit = Path(temp) / "kit"
            s2x.prepare(ROOT / "build-kit", kit, ROOT / "artifacts/generated.config.txt")
            text = (kit / "ci/rollercoaster/build-rollercoaster.sh").read_text()
            driver = (kit / "scripts/build_chronicle_base.py").read_text()
            profile_copy = (kit / "ci/rollercoaster/profiles/synthetica.config").read_text()
            self.assertIn("S2X_TOOLCHAIN_BIN", text)
            self.assertIn('S2X_SIZE_TOOL=/usr/bin/aarch64-linux-gnu-size', text)
            self.assertIn('SIZE="$S2X_SIZE_TOOL"', text)
            self.assertNotIn('export PATH="/usr/lib/llvm-18/bin:', text)
            self.assertIn('"prepare-tree", "--tree", str(tree)', driver)
            self.assertIn("S2X_HELPER", text)
            self.assertIn("CONFIG_UCLAMP_TASK=y", profile_copy)
            self.assertIn("# CONFIG_LRU_GEN_ENABLED is not set", profile_copy)
            self.assertIn("synthetica2-experimental-modules", text)
            self.assertNotIn("patch_cmdline", text)
            self.assertNotIn("# --- kemas AnyKernel3", text)
            self.assertTrue(text.rstrip().endswith("exit 0"))
            with self.assertRaises(ValueError):
                s2x.prepare(ROOT / "build-kit", kit, ROOT / "artifacts/generated.config.txt")
        self.assertEqual(before, {p: s2x.v3.digest(p) for p in before})

    def test_refuse_tree_inside_repo(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            s2x.ensure_disposable(ROOT / "build-kit")

    def test_compiler_must_be_the_requested_version_and_neutron_archive_pinned(self):
        with tempfile.TemporaryDirectory(prefix="s2x-tools-") as temp:
            tools = Path(temp)
            for name, version in (("clang", "Ubuntu clang version 18.1.3"), ("ld.lld", "LLD 18.1.3")):
                tool = tools / name
                tool.write_text('#!/bin/sh\necho "' + version + '"\n')
                tool.chmod(0o755)
            self.assertEqual(s2x.toolchain_info("clang18", tools, None)["kind"], "clang18")
            with self.assertRaisesRegex(ValueError, "wrong neutron"):
                s2x.toolchain_info("neutron", tools, None)
            (tools / "clang").write_text('#!/bin/sh\necho "clang version 24.0.0git"\n')
            (tools / "ld.lld").write_text('#!/bin/sh\necho "LLD 24.0.0"\n')
            archive = tools / "bad.tar.zst"
            archive.write_bytes(b"not the pinned archive")
            with self.assertRaisesRegex(ValueError, "does not match"):
                s2x.toolchain_info("neutron", tools, archive)


if __name__ == "__main__":
    unittest.main()
