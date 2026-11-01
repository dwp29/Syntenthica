#!/usr/bin/env python3
"""Host-side tests for 2.1 controls; all sysfs/procfs nodes are fake files."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "build-kit/ci/ksun-cyberbrutal/assets/synthetica-control.sh"


class ControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetica-control-test-")
        self.root = Path(self.tmp.name)
        self.sys = self.root / "sys"
        self.proc = self.root / "proc"
        self.state = self.root / "state"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fake_id(0)
        self.env = dict(os.environ, SP_SYSROOT=str(self.sys), SP_PROCSYS=str(self.proc),
                        SP_STATE_DIR=str(self.state), PATH=f"{self.bin}:{os.environ['PATH']}")
        for path, value in {
            "proc/sys/kernel/random/boot_id": "11111111-1111-1111-1111-111111111111",
            "proc/sys/vm/swappiness": "60",
            "proc/sys/vm/page-cluster": "3",
            "sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors": "schedutil performance",
            "sys/devices/system/cpu/cpufreq/policy0/scaling_governor": "schedutil",
            "sys/devices/system/cpu/cpufreq/policy0/cpuinfo_min_freq": "300000",
            "sys/devices/system/cpu/cpufreq/policy0/cpuinfo_max_freq": "1800000",
            "sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies": "300000 1200000 1500000 1800000",
            "sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq": "300000",
            "sys/class/kgsl/kgsl-3d0/num_pwrlevels": "6",
            "sys/class/kgsl/kgsl-3d0/min_pwrlevel": "5",
            "sys/block/sda/queue/scheduler": "[cfq] mq-deadline",
        }.items():
            self.put(path, value)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_id(self, uid: int) -> None:
        p = self.bin / "id"
        p.write_text(f"#!/bin/sh\nprintf '%s\\n' '{uid}'\n")
        p.chmod(0o755)

    def put(self, path: str, value: str) -> None:
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value + "\n")

    def read(self, path: str) -> str:
        return (self.root / path).read_text().strip()

    def run_control(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["sh", str(SCRIPT), action], env=self.env, text=True,
                              capture_output=True, timeout=10, check=False)

    def test_gaming_and_real_restore(self) -> None:
        result = self.run_control("profile_gaming")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified=5 skipped=0 failed=0", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "40")
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq"), "1500000")
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_governor"), "performance")
        self.assertEqual(self.read("sys/class/kgsl/kgsl-3d0/min_pwrlevel"), "2")
        self.assertEqual(self.read("proc/sys/vm/page-cluster"), "0")
        # A second action must not overwrite the original snapshot.
        result = self.run_control("swap:80")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.run_control("profile_revert")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")
        self.assertEqual(self.read("proc/sys/vm/page-cluster"), "3")
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq"), "300000")
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_governor"), "schedutil")
        self.assertEqual(self.read("sys/class/kgsl/kgsl-3d0/min_pwrlevel"), "5")
        self.assertFalse(list(self.state.glob("*.tsv")))

    def test_partial_results_are_not_reported_as_success(self) -> None:
        result = self.run_control("profile_daily")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SKIPPED:", result.stdout)
        self.assertIn("skipped=1", result.stdout)
        self.assertIn("verified=6", result.stdout)
        self.assertEqual(self.read("sys/block/sda/queue/scheduler"), "mq-deadline")
        result = self.run_control("profile_revert")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.read("sys/block/sda/queue/scheduler"), "cfq")

    def test_invalid_requests_and_out_of_range_gpu_do_not_write(self) -> None:
        for action in ("swap:999", "ios:mq-deadline;touch-evil", "gpu:9"):
            result = self.run_control(action)
            self.assertNotEqual(result.returncode, 0, action)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")
        self.assertEqual(self.read("sys/class/kgsl/kgsl-3d0/min_pwrlevel"), "5")
        self.put("sys/class/kgsl/kgsl-3d0/num_pwrlevels", "2")
        result = self.run_control("gpu:7")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.read("sys/class/kgsl/kgsl-3d0/min_pwrlevel"), "5")

    def test_no_root_no_changes(self) -> None:
        self.fake_id(1001)
        result = self.run_control("swap:40")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root required", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")
        self.assertFalse(self.state.exists())

    def test_boot_id_prevents_using_an_old_snapshot(self) -> None:
        self.assertEqual(self.run_control("swap:40").returncode, 0)
        self.put("proc/sys/kernel/random/boot_id", "22222222-2222-2222-2222-222222222222")
        result = self.run_control("profile_revert")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("No prior changes", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "40")

    def test_concurrent_actions_are_rejected_without_changes(self) -> None:
        self.state.mkdir()
        (self.state / "lock-11111111-1111-1111-1111-111111111111").mkdir()
        result = self.run_control("swap:40")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another control action is running", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")

    def test_read_only_node_is_reported_as_failure(self) -> None:
        node = self.proc / "sys/vm/swappiness"
        node.chmod(0o444)
        result = self.run_control("swap:40")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not writable", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")

    def test_symlink_state_dir_is_refused(self) -> None:
        other = self.root / "other"
        other.mkdir()
        self.state.symlink_to(other, target_is_directory=True)
        result = self.run_control("swap:40")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("state directory unavailable", result.stdout)
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")


if __name__ == "__main__":
    unittest.main()
