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
        # CI also applies both patches to the complete SHA-verified archive.
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
