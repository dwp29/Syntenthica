#!/usr/bin/env python3
"""Host tests for 2.1 legacy boost; paths and device commands are fakes."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "build-kit/ci/ksun-cyberbrutal/assets/synthetica-boost-compat.sh"


class BoostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetica-boost-test-")
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.proc = self.root / "proc"
        self.service = self.root / "service.d"
        self.command("id", "echo 0")
        self.env = dict(os.environ, SP_PROCSYS=str(self.proc), SP_SERVICE_DIR=str(self.service),
                        PATH=f"{self.bin}:{os.environ['PATH']}")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def command(self, name: str, body: str) -> None:
        p = self.bin / name
        p.write_text(f"#!/bin/sh\n{body}\n")
        p.chmod(0o755)

    def put(self, relative: str, value: str) -> None:
        p = self.proc / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value + "\n")

    def run_boost(self, action: str, value: str = "88") -> subprocess.CompletedProcess[str]:
        return subprocess.run(["sh", str(SCRIPT), action, value], env=self.env, text=True,
                              capture_output=True, timeout=10, check=False)

    def test_status_is_read_only(self) -> None:
        result = self.run_boost("status")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NETWORK_BOOT=not installed", result.stdout)
        self.assertIn("AUDIO_BOOT=not installed", result.stdout)
        self.assertFalse(self.service.exists())

    def test_startup_scripts_are_opt_in_and_removable(self) -> None:
        result = self.run_boost("network_boot_on")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.service / "synthetica-boost.sh").is_file())
        self.assertIn("NETWORK_BOOT=installed", self.run_boost("status").stdout)
        result = self.run_boost("audio_boot_on", "92")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        generated = (self.service / "synthetica-sound.sh").read_text()
        self.assertIn('tinymix "$ctl" 92', generated)
        self.assertEqual(subprocess.run(["sh", "-n", str(self.service / "synthetica-sound.sh")]).returncode, 0)
        self.assertIn("AUDIO_BOOT=installed", self.run_boost("status").stdout)
        self.assertEqual(self.run_boost("network_boot_off").returncode, 0)
        self.assertEqual(self.run_boost("audio_boot_off").returncode, 0)
        self.assertFalse((self.service / "synthetica-boost.sh").exists())
        self.assertFalse((self.service / "synthetica-sound.sh").exists())

    def test_invalid_gain_is_rejected(self) -> None:
        for gain in ("83", "97", "92;touch-a-file"):
            self.assertNotEqual(self.run_boost("audio_boot_on", gain).returncode, 0)
        self.assertFalse(self.service.exists())

    def test_missing_audio_controls_report_partial_failure(self) -> None:
        self.command("tinymix", 'case "$1" in "RX1 Digital Volume") exit 1 ;; *) exit 0 ;; esac')
        result = self.run_boost("audio_once", "88")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted=2 failed=1", result.stdout)
        self.assertIn("audio effect not measured", result.stdout)

    def test_network_writes_fake_nodes_and_reads_them_back(self) -> None:
        for path, value in {
            "sys/net/core/rmem_max": "1", "sys/net/core/wmem_max": "1",
            "sys/net/ipv4/tcp_fastopen": "1", "sys/net/core/default_qdisc": "pfifo_fast",
            "sys/net/ipv4/tcp_available_congestion_control": "cubic bbr",
            "sys/net/ipv4/tcp_congestion_control": "cubic",
        }.items():
            self.put(path, value)
        self.command("iw", 'case "$*" in *"get power_save"*) echo "Power save: off" ;; esac; exit 0')
        result = self.run_boost("network_once")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified=6 unavailable_or_failed=0", result.stdout)
        self.assertEqual((self.proc / "sys/net/ipv4/tcp_congestion_control").read_text().strip(), "bbr")

    def test_root_and_symlink_guards(self) -> None:
        self.command("id", "echo 1001")
        self.assertNotEqual(self.run_boost("network_boot_on").returncode, 0)
        self.assertFalse(self.service.exists())
        self.command("id", "echo 0")
        dest = self.root / "elsewhere"
        dest.mkdir()
        self.service.symlink_to(dest, target_is_directory=True)
        self.assertNotEqual(self.run_boost("network_boot_on").returncode, 0)
        self.assertFalse(list(dest.iterdir()))


if __name__ == "__main__":
    unittest.main()
