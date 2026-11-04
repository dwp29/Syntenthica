import gzip
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "synthetica-project/build_joyeuse_builtin_experiment.py"
SPEC = importlib.util.spec_from_file_location("joyeuse_builtin_experiment", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
FRAGMENT = ROOT / "build-kit/ci/rollercoaster/profiles/joyeuse-builtins-experimental.config"
BASELINE = ROOT / "artifacts/generated.config.txt"


def generated_config():
    lines = BASELINE.read_text().splitlines()
    overrides = {**dict.fromkeys(mod.REQUIRED, "y"), **dict.fromkeys(mod.DISABLED, "n")}
    used = set()
    for index, line in enumerate(lines):
        parsed = mod.read_config(line)
        if not parsed:
            continue
        key = next(iter(parsed))
        if key in overrides:
            value = overrides[key]
            lines[index] = f"CONFIG_{key}={value}" if value != "n" else f"# CONFIG_{key} is not set"
            used.add(key)
    for key in sorted(set(overrides) - used):
        value = overrides[key]
        lines.append(f"CONFIG_{key}={value}" if value != "n" else f"# CONFIG_{key} is not set")
    return "\n".join(lines) + "\n"


class TestJoyeuseBuiltinExperiment(unittest.TestCase):
    def test_fragment_is_narrow_and_does_not_disable_security(self):
        mod.check_fragment(FRAGMENT.read_text())
        with self.assertRaisesRegex(ValueError, "allowlist"):
            mod.check_fragment(FRAGMENT.read_text().replace("CONFIG_MODULE_SIG_FORCE=y", "# CONFIG_MODULE_SIG_FORCE is not set"))
        with self.assertRaises(ValueError):
            mod.check_fragment(FRAGMENT.read_text() + "\nCONFIG_MODULE_FORCE_LOAD=y\n")

    def test_generated_config_keeps_security_and_requires_all_builtins(self):
        baseline = mod.verified_baseline(BASELINE)
        candidate = generated_config()
        delta = mod.check_config(baseline, candidate)
        self.assertEqual(delta["USB_GSPCA"], {"baseline": "m", "experiment": "y"})
        self.assertEqual(delta["BRIDGE_NETFILTER"], {"baseline": "n", "experiment": "y"})
        for key in ("MODULE_SIG_FORCE", "MODVERSIONS", "SECURITY_SELINUX", "QCA_CLD_WLAN", "EXFAT_FS"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.check_config(baseline, candidate.replace(f"CONFIG_{key}=y", f"# CONFIG_{key} is not set"))
        with self.assertRaisesRegex(ValueError, "forbidden"):
            mod.check_config(baseline, candidate.replace("# CONFIG_MODULE_FORCE_LOAD is not set", "CONFIG_MODULE_FORCE_LOAD=y"))
        with self.assertRaisesRegex(ValueError, "security configuration changed"):
            mod.check_config(baseline, candidate.replace("CONFIG_SECURITY_SELINUX_DEVELOP=y", "# CONFIG_SECURITY_SELINUX_DEVELOP is not set"))

    def test_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.read_config("CONFIG_TEST=y\n# CONFIG_TEST is not set\n")

    def test_prepare_is_isolated_and_never_packages(self):
        source = ROOT / "build-kit"
        before = {name: mod.digest(source / name) for name in mod.PINNED_INPUTS}
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "kit"
            mod.prepare(source, dest, FRAGMENT)
            builder = (dest / "ci/rollercoaster/build-rollercoaster.sh").read_text()
            self.assertIn('"$SP_EXPERIMENT_GUARD" check-config', builder)
            self.assertNotIn("# --- kemas AnyKernel3", builder)
            self.assertNotIn('zip -r9 "$ZIP"', builder)
            self.assertIn("DO NOT FLASH", builder)
            self.assertEqual(mod.digest(dest / "artifacts/manager/MANAGER.json"), before["artifacts/manager/MANAGER.json"])
            self.assertNotIn('    status = {\n', (dest / "scripts/build_chronicle_base.py").read_text())
            self.assertIn("CONFIG_USB_GSPCA=y", (dest / "ci/rollercoaster/profiles/synthetica.config").read_text())
            with self.assertRaisesRegex(ValueError, "overwrite"):
                mod.prepare(source, dest, FRAGMENT)
        self.assertEqual(before, {name: mod.digest(source / name) for name in mod.PINNED_INPUTS})

    def test_finish_requires_linked_symbols_and_excludes_signing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit, out, result = root / "kit", root / "out", root / "result"
            (kit / "artifacts").mkdir(parents=True)
            (out / "certs").mkdir(parents=True)
            (out / ".config").write_text(generated_config())
            (out / "certs/signing_key.pem").write_text("PRIVATE KEY MUST NOT BE EXPORTED")
            (out / "System.map").write_text("00000000 T br_netfilter_init\n")
            with self.assertRaisesRegex(ValueError, "not linked"):
                mod.finish(kit, out, BASELINE, result)
            self.assertFalse(result.exists())
            (out / "System.map").write_text("".join(f"00000000 T {s}\n" for s in mod.REQUIRED_SYMBOLS))
            (out / "Module.symvers").write_text("test\n")
            with gzip.open(kit / "artifacts/Image.gz", "wb", compresslevel=1) as image:
                image.write(("Linux version " + mod.EXPECTED_RELEASE + " test\n").encode())
                image.write(os.urandom(8 * 1024 * 1024 + 1024))
            mod.finish(kit, out, BASELINE, result)
            status = json.loads((result / "STATUS.json").read_text())
            self.assertEqual(status["status"], "COMPILED_ONLY_DO_NOT_FLASH")
            self.assertTrue(status["security_config_unchanged"])
            self.assertEqual(status["boot_test"], "NOT_RUN")
            self.assertTrue((result / "DO-NOT-FLASH-JOYEUSE-BUILTIN-Image.gz").is_file())
            self.assertFalse(any("signing_key" in p.name for p in result.rglob("*")))
            self.assertFalse(any(p.suffix == ".zip" for p in result.iterdir()))


if __name__ == "__main__":
    unittest.main()
