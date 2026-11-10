#!/usr/bin/env python3
"""Host-side guards for the standalone Manager 6.0.0 tree and its universal helpers."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import build_manager_60_standalone as builder

TREE = builder.TREE
ASSETS = TREE / "app/src/main/assets"
KOTLIN = TREE / "app/src/main/java/com/rifsxd/ksunext"


def read(relative: str) -> str:
    return (TREE / relative).read_text(encoding="utf-8")


def sha256_local(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StandaloneTreeTests(unittest.TestCase):
    def test_static_gates_pass(self) -> None:
        builder.verify_tree()

    def test_version_identity_is_70000(self) -> None:
        self.assertEqual(builder.VERSION_CODE, 70000)
        self.assertEqual(builder.VERSION_NAME, "6.0.0")
        self.assertEqual(builder.APP_ID, "net.ember.labs")
        self.assertEqual(builder.UAPI, 4)
        self.assertIn("versionCode = managerVersionCode", read("build.gradle.kts"))
        self.assertIn('applicationId = "net.ember.labs"', read("app/build.gradle.kts"))
        self.assertIn('Synthetica-6.0.0-Standalone-$name.apk', read("app/build.gradle.kts"))

    def test_no_signing_material_or_binary_payload_is_committed(self) -> None:
        for path in TREE.rglob("*"):
            if path.is_file():
                self.assertNotIn(path.suffix.lower(), {".p12", ".jks", ".keystore", ".pem", ".key", ".der"})
                self.assertFalse(path.is_symlink(), path)
        self.assertFalse((TREE / "app/src/main/jniLibs").exists(), "libksud.so must be injected at build time")

    def test_release_minification_and_no_upstream_downloader(self) -> None:
        # The standalone tree is self-contained: no script clones KernelSU-Next.
        for script in (ROOT / "build-kit/scripts").glob("build_manager_60*.py"):
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("KernelSU-Next.git", text)
            self.assertNotIn("prepare_source", text)
        self.assertIn("isMinifyEnabled = true", read("app/build.gradle.kts"))

    def test_universal_helpers_are_allowed_by_the_action_allowlist(self) -> None:
        actions = read("app/src/main/java/com/rifsxd/ksunext/ui/util/PixelRootActions40.kt")
        self.assertIn("profile_(daily|gaming|battery|cooldown|revert)", actions)
        self.assertIn("diag_(dmesg|pstore|boot)", actions)
        for module in ("ntfs", "wireguard", "zsmalloc", "lz4_compress", "zstd_compress"):
            self.assertIn(module, actions)
        self.assertIn("telemetry", actions)
        self.assertIn("kmod_status", actions)
        self.assertIn("synthetica-universal60.sh", actions)

    def test_universal_root_bridge_falls_back_to_su(self) -> None:
        actions = read("app/src/main/java/com/rifsxd/ksunext/ui/util/PixelRootActions40.kt")
        self.assertIn("fun canActImmediate60()", actions)
        # The probe must be the shared, UID-0-verified one; a local copy is how
        # the "|| sh always succeeds" false positive came back last time.
        self.assertIn("fun probeUniversalRoot60()", actions)
        self.assertIn("probeSuRoot()", actions)
        self.assertNotIn("id -u", actions)
        home = read("app/src/main/java/com/rifsxd/ksunext/ui/screen/Home.kt")
        self.assertIn("probeUniversalRoot60()", home)
        self.assertIn("UNIVERSAL ROOT", home)
        self.assertIn("manager60_universal_bridge_title", home)
        self.assertIn("detectRootChannel()", home)
        self.assertIn("RootChannel.SU", home)

    def test_root_shell_tries_su_before_the_bundled_ksud(self) -> None:
        cli = read("app/src/main/java/com/rifsxd/ksunext/ui/util/KsuCli.kt")
        # A phone with a real, kernel-provided su must never be shadowed by our
        # own libksud.so, which exists in every install regardless of kernel.
        chain_start = cli.index("fun createRootShellBuilder(")
        chain = cli[chain_start:cli.index("setCommands", chain_start)]
        self.assertLess(chain.index('append("su'), chain.index("debug su"))
        self.assertIn("--global-mnt", chain)
        self.assertNotIn('debug su -g', chain)
        # libsu reports ROOT_SHELL only after `id` printed uid=0; the exit code of
        # the whole `|| sh` chain is meaningless, so it must not be trusted alone.
        probe_start = cli.index("fun probeSuRoot()")
        probe = cli[probe_start:cli.index("fun probeSuRootGlobal()")]
        self.assertIn("shell.isRoot", probe)

    def test_root_channel_detection_is_offloaded_from_the_main_thread(self) -> None:
        # probeSuRoot() spawns a process and can block on the su prompt. This was
        # rewritten once already and lost in a workspace reset, so the signature
        # is now pinned: a non-suspend version silently blocks the first frame.
        cli = read("app/src/main/java/com/rifsxd/ksunext/ui/util/KsuCli.kt")
        self.assertIn("suspend fun detectRootChannel(): RootChannel = withContext(Dispatchers.IO) {", cli)
        home = read("app/src/main/java/com/rifsxd/ksunext/ui/screen/Home.kt")
        # ...and it must only be called from a coroutine scope.
        self.assertIn("LaunchedEffect(isManager)", home)
        self.assertIn("rootChannel = detectRootChannel()", home)

    def test_about_page_credits_author_source_licence_and_donation_slot(self) -> None:
        credit = read("app/src/main/java/com/rifsxd/ksunext/ui/util/AppCredit60.kt")
        self.assertIn('AUTHOR = "Pure_Saturday"', credit)
        self.assertIn('TELEGRAM_URL = "https://t.me/Pure_Saturday"', credit)
        self.assertIn('SOURCE_URL = "https://github.com/dwp29/Syntenthica"', credit)
        self.assertIn('LICENSE_SPDX = "GPL-3.0-only"', credit)
        # The donation slot stays empty on purpose until the author publishes one.
        self.assertIn('DONATE_URL = ""', credit)
        self.assertIn("donateConfigured", credit)

        about = read("app/src/main/java/com/rifsxd/ksunext/ui/screen/About.kt")
        for marker in ("AppCredit60.TELEGRAM_HANDLE", "R.drawable.ic_telegram",
                       "R.drawable.ic_github", "AppCredit60.SOURCE_URL",
                       "AppCredit60.LICENSE_SPDX", "R.string.about_donate",
                       "rememberSafeLinkOpener()"):
            self.assertIn(marker, about)
        # Disabled placeholder, not a dead link the user can tap.
        donate_block = about[about.index("R.string.about_donate_group"):]
        self.assertIn("enabled = false", donate_block)

        for drawable in ("ic_telegram", "ic_github", "ic_donate_placeholder"):
            path = TREE / f"app/src/main/res/drawable/{drawable}.xml"
            self.assertTrue(path.is_file(), f"missing drawable {drawable}")
            self.assertIn("<vector", path.read_text(encoding="utf-8"))
        notice = (TREE / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Pure_Saturday", notice)
        self.assertIn("GPL-3.0", notice)
        offer = (TREE / "SOURCE-OFFER.md").read_text(encoding="utf-8")
        self.assertIn("synthetica-manager/", offer)

    def test_animation_speed_and_json_backup_restore_are_wired(self) -> None:
        visual = read("app/src/main/java/com/rifsxd/ksunext/ui/theme/VisualStyles.kt")
        self.assertIn('ManagerAnimSpeedState = mutableStateOf("normal")', visual)
        self.assertIn("fun setManagerAnimSpeed(", visual)
        self.assertIn("fun exportManagerConfigJson(", visual)
        self.assertIn("fun importManagerConfigJson(", visual)
        self.assertIn('"turbo"', visual)
        self.assertIn('"reduced"', visual)
        self.assertIn("manager_anim_speed", visual)
        controls = read("app/src/main/java/com/rifsxd/ksunext/ui/theme/AppearanceControls.kt")
        self.assertIn("setManagerAnimSpeed(context, id)", controls)
        self.assertIn("exportManagerConfigJson(context)", controls)
        self.assertIn("importManagerConfigJson(context, text)", controls)
        self.assertIn("ClipboardManager", controls)

    def test_all_manager60_strings_are_localized(self) -> None:
        english = read("app/src/main/res/values/strings_manager50.xml")
        indonesian = read("app/src/main/res/values-in-rID/strings_manager50.xml")
        en_keys = set(re.findall(r'name="(manager60_[a-z0-9_]+)"', english))
        id_keys = set(re.findall(r'name="(manager60_[a-z0-9_]+)"', indonesian))
        self.assertGreaterEqual(len(en_keys), 45)
        self.assertEqual(en_keys, id_keys)
        used: set[str] = set()
        for path in KOTLIN.rglob("*.kt"):
            used.update(re.findall(r"R\.string\.(manager60_[a-z0-9_]+)", path.read_text(encoding="utf-8")))
        self.assertEqual(used, en_keys, f"unused or undefined: {used ^ en_keys}")

    def test_no_duplicate_top_level_declarations(self) -> None:
        """Two top-level functions with one signature break the Kotlin build.

        A stale copy of createRootShellBuilder() survived an edit and only
        surfaced as 'unresolved reference: build' at the call site, which points
        at the wrong line. Catching it here names the real problem.
        """
        import re as _re

        # Overloads are legal; only an identical name + parameter list is not.
        # Parameters are read from the same line plus wrapped continuation lines
        # up to the closing parenthesis of the declaration.
        decl = _re.compile(
            r"^(?:suspend |inline |private |internal |public )*fun ([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            _re.M,
        )
        bad: list[str] = []
        for path in sorted(KOTLIN.rglob("*.kt")):
            text = path.read_text(encoding="utf-8")
            seen: dict[str, int] = {}
            for m in decl.finditer(text):
                start = m.end() - 1
                depth = 0
                end = start
                for i in range(start, min(len(text), start + 4000)):
                    if text[i] == "(":
                        depth += 1
                    elif text[i] == ")":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                params = " ".join(text[start:end].split())
                key = f"{m.group(1)}{params}"
                seen[key] = seen.get(key, 0) + 1
            for key, count in seen.items():
                if count > 1:
                    bad.append(f"{path.relative_to(TREE)}: {key} declared {count}x")
        self.assertEqual(bad, [], "duplicate top-level declarations:\n" + "\n".join(bad))

    def test_strings_are_valid_aapt_input(self) -> None:
        """Reject strings aapt2 would fail on, before a 2-minute CI build.

        aapt2 aborts the whole build with a bare "Invalid unicode escape
        sequence in string" when an Android string contains a character that
        needs escaping. An unescaped apostrophe (kernel's) did exactly that.
        """
        import re as _re
        import xml.etree.ElementTree as _ET

        bad: list[str] = []
        for path in sorted((TREE / "app/src/main/res").glob("values*/strings*.xml")):
            root = _ET.parse(path).getroot()
            for node in root.findall("string"):
                name = node.get("name") or "?"
                value = "".join(node.itertext())
                # Single quotes and double quotes are the two characters aapt2
                # treats as string delimiters; backslash starts an escape.
                if _re.search(r"(?<!\\)'", value):
                    bad.append(f"{path.name}:{name}: unescaped apostrophe")
                if _re.search(r"(?<!\\)\\[^nt\\'\"@?]", value):
                    bad.append(f"{path.name}:{name}: invalid escape")
                if "\\\\" in value:
                    bad.append(f"{path.name}:{name}: doubled backslash")
        self.assertEqual(bad, [], "aapt2 would reject:\n" + "\n".join(bad))

    def test_locale_files_are_not_swapped(self) -> None:
        # Regression guard: the Indonesian strings belong in values-in-rID, the
        # English defaults in values/. They were once written the other way
        # round, which shows Indonesian text on an English phone and vice versa.
        english = read("app/src/main/res/values/strings_manager50.xml")
        indonesian = read("app/src/main/res/values-in-rID/strings_manager50.xml")
        self.assertIn("Root active via the kernel", english)
        self.assertIn("Root aktif lewat su kernel", indonesian)
        self.assertIn("reserved but still empty", english)
        self.assertIn("sudah disiapkan tetapi masih kosong", indonesian)
        # No Indonesian-only wording may leak into the default resource file.
        for phrase in ("Penulis belum", "Slot donasi", "Tidak ada root", "Pengembang"):
            self.assertNotIn(phrase, english)
        for phrase in ("reserved but still empty", "Developer of the Synthetica", "No root:"):
            self.assertNotIn(phrase, indonesian)

    def test_four_power_profiles_and_revert_exist_in_helper(self) -> None:
        helper = (ASSETS / "synthetica-control40.sh").read_text(encoding="utf-8")
        for profile in ("daily", "gaming", "battery", "cooldown"):
            self.assertIn(profile, helper)
        self.assertIn("CAP_PCT=80", helper)
        self.assertIn("CAP_PCT=70", helper)
        self.assertIn("profile_revert", helper)

    def test_release_strings_report_600(self) -> None:
        about = read("app/src/main/res/values/strings_synthetica.xml")
        self.assertIn("Manager 6.0.0", about)
        glass = read("app/src/main/java/com/rifsxd/ksunext/ui/theme/Glass.kt")
        self.assertIn("[6.0.0]", glass)
        self.assertIn("v6.0.0", glass)
        self.assertNotIn("MANAGER 5.0.1", read("app/src/main/java/com/rifsxd/ksunext/ui/theme/VisualStyles.kt"))


class UniversalHelperTests(unittest.TestCase):
    """Fake /sys + /proc only; no device, no root, no module is really loaded."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetica-universal60-")
        self.root = Path(self.tmp.name)
        self.sys = self.root / "sys"
        self.proc = self.root / "proc"
        self.mods = self.root / "mods"
        self.vendor = self.root / "vendor"
        self.pstore = self.root / "pstore"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fake_id(0)
        self.env = dict(
            os.environ,
            SP_SYSROOT=str(self.sys),
            SP_PROCSYS=str(self.proc),
            SP_MOD_DIR=str(self.mods),
            SP_VENDOR_MOD_DIR=str(self.vendor),
            SP_PSTORE_DIR=str(self.pstore),
            PATH=f"{self.bin}:{os.environ['PATH']}",
        )
        self.put("proc/meminfo", "MemTotal: 7800000 kB\nMemAvailable: 3000000 kB\nSwapTotal: 2000000 kB\nSwapFree: 1500000 kB")
        self.put("proc/sys/vm/swappiness", "60")
        self.put("proc/sys/net/ipv4/tcp_congestion_control", "bbr")
        self.put("proc/sys/net/core/default_qdisc", "fq_codel")
        self.put("proc/modules", "")
        self.put("sys/kernel/mm/lru_gen/enabled", "0x0007")
        self.put("sys/class/power_supply/battery/temp", "385")
        for policy, freq in (("policy0", "1800000"), ("policy6", "2200000")):
            base = f"sys/devices/system/cpu/cpufreq/{policy}"
            self.put(f"{base}/scaling_cur_freq", "1200000")
            self.put(f"{base}/cpuinfo_min_freq", "300000")
            self.put(f"{base}/cpuinfo_max_freq", freq)
            self.put(f"{base}/scaling_min_freq", "300000")
            self.put(f"{base}/scaling_max_freq", freq)
            self.put(f"{base}/scaling_governor", "schedutil")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_id(self, uid: int) -> None:
        path = self.bin / "id"
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{uid}'\n")
        path.chmod(0o755)

    def put(self, relative: str, value: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n")

    def run_helper(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(ASSETS / "synthetica-universal60.sh"), action],
            env=self.env, text=True, capture_output=True, timeout=20, check=False,
        )

    def test_telemetry_is_read_only_and_reports_cpu_gpu_memory(self) -> None:
        before = {p: p.read_text() for p in self.sys.rglob("*") if p.is_file()}
        result = self.run_helper("telemetry")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CPU_policy0: cur=1200MHz range=300-1800MHz gov=schedutil", result.stdout)
        self.assertIn("CPU_policy6: cur=1200MHz range=300-2200MHz gov=schedutil", result.stdout)
        self.assertIn("THERMAL_BATTERY: 38.5 C", result.stdout)
        self.assertIn("MEMORY: used=", result.stdout)
        self.assertIn("VM_MGLRU: enabled=0x0007", result.stdout)
        self.assertIn("NET_STACK: congestion=bbr qdisc=fq_codel", result.stdout)
        after = {p: p.read_text() for p in self.sys.rglob("*") if p.is_file()}
        self.assertEqual(before, after, "telemetry must never write to sysfs")

    def test_kmod_status_distinguishes_loaded_file_and_builtin(self) -> None:
        self.put("proc/modules", "wireguard 151552 0 - Live 0x0000000000000000")
        (self.mods).mkdir(parents=True, exist_ok=True)
        (self.mods / "ntfs.ko").write_bytes(b"\x7fELF")
        result = self.run_helper("kmod_status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("KMOD wireguard: state=LOADED", result.stdout)
        self.assertIn("KMOD ntfs: state=UNLOADED file=", result.stdout)
        self.assertIn("KMOD zstd_compress: state=UNLOADED file=BUILT_IN_OR_NOT_FOUND", result.stdout)

    def test_kmod_load_refuses_without_root(self) -> None:
        self.fake_id(2000)
        (self.mods).mkdir(parents=True, exist_ok=True)
        (self.mods / "ntfs.ko").write_bytes(b"\x7fELF")
        result = self.run_helper("kmod_load:ntfs")
        self.assertEqual(result.returncode, 2)
        self.assertIn("root required", result.stdout)

    def test_kmod_load_reports_missing_module_without_touching_system(self) -> None:
        result = self.run_helper("kmod_load:zstd_compress")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stdout)

    def test_kmod_unload_is_a_noop_when_not_loaded(self) -> None:
        result = self.run_helper("kmod_unload:zsmalloc")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("not currently loaded", result.stdout)

    def test_unknown_action_is_rejected(self) -> None:
        result = self.run_helper("rm_rf_everything")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported", result.stdout)

    def test_diag_pstore_reports_clean_state(self) -> None:
        self.pstore.mkdir(parents=True, exist_ok=True)
        result = self.run_helper("diag_pstore")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("clean", result.stdout)

    def test_diag_pstore_never_dumps_more_than_40_lines(self) -> None:
        self.pstore.mkdir(parents=True, exist_ok=True)
        (self.pstore / "console-ramoops-0").write_text("\n".join(f"line {i}" for i in range(500)))
        result = self.run_helper("diag_pstore")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("=== console-ramoops-0 ===", result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 45)

    def test_diag_boot_reports_kernel_and_selinux(self) -> None:
        self.put("proc/cmdline", "console=ttyMSM0 androidboot.slot_suffix=_a")
        result = self.run_helper("diag_boot")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("UNAME:", result.stdout)
        self.assertIn("SELINUX:", result.stdout)
        self.assertIn("CMDLINE: console=ttyMSM0", result.stdout)

    def test_diag_dmesg_requires_root(self) -> None:
        self.fake_id(2000)
        result = self.run_helper("diag_dmesg")
        self.assertEqual(result.returncode, 2)
        self.assertIn("root required", result.stdout)


class ProfileHelperTests(unittest.TestCase):
    """The 4 power profiles on fake sysfs nodes; reversal must restore every value."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetica-control60-")
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "id").write_text("#!/bin/sh\nprintf '0\\n'\n")
        (self.bin / "id").chmod(0o755)
        self.env = dict(
            os.environ,
            SP_SYSROOT=str(self.root / "sys"),
            SP_PROCSYS=str(self.root / "proc"),
            SP_STATE_DIR=str(self.root / "state"),
            PATH=f"{self.bin}:{os.environ['PATH']}",
        )
        self.put("proc/sys/kernel/random/boot_id", "11111111-1111-1111-1111-111111111111")
        self.put("proc/sys/vm/swappiness", "60")
        self.put("proc/sys/vm/page-cluster", "3")
        base = "sys/devices/system/cpu/cpufreq/policy0"
        self.put(f"{base}/scaling_available_governors", "schedutil performance")
        self.put(f"{base}/scaling_governor", "schedutil")
        self.put(f"{base}/cpuinfo_min_freq", "300000")
        self.put(f"{base}/cpuinfo_max_freq", "2000000")
        self.put(f"{base}/scaling_available_frequencies", "300000 800000 1200000 1600000 1800000 2000000")
        self.put(f"{base}/scaling_min_freq", "300000")
        self.put(f"{base}/scaling_max_freq", "2000000")
        self.put("sys/class/kgsl/kgsl-3d0/num_pwrlevels", "6")
        self.put("sys/class/kgsl/kgsl-3d0/min_pwrlevel", "5")
        for queue in ("sda", "sdc"):
            self.put(f"sys/block/{queue}/queue/scheduler", "[cfq] mq-deadline")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def put(self, relative: str, value: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n")

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text().strip()

    def run_control(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(ASSETS / "synthetica-control40.sh"), action],
            env=self.env, text=True, capture_output=True, timeout=20, check=False,
        )

    def test_battery_profile_caps_at_80_percent_then_reverts(self) -> None:
        result = self.run_control("profile_battery")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"), "1600000")
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "80")
        self.assertEqual(self.read("sys/class/kgsl/kgsl-3d0/min_pwrlevel"), "5")
        revert = self.run_control("profile_revert")
        self.assertEqual(revert.returncode, 0, revert.stdout + revert.stderr)
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"), "2000000")
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "60")

    def test_cooldown_profile_caps_at_70_percent(self) -> None:
        result = self.run_control("profile_cooldown")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"), "1200000")
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "80")

    def test_gaming_profile_still_works(self) -> None:
        result = self.run_control("profile_gaming")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.read("sys/devices/system/cpu/cpufreq/policy0/scaling_governor"), "performance")
        self.assertEqual(self.read("proc/sys/vm/swappiness"), "40")

    def test_unknown_profile_is_rejected(self) -> None:
        result = self.run_control("profile_overclock")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported control action", result.stdout)


if __name__ == "__main__":
    unittest.main()
