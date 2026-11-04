import ast
import gzip
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build-kit/scripts/build_synthetica3.py"
spec = importlib.util.spec_from_file_location("synthetica3_build", SCRIPT)
s3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s3)
BASELINE_PATH = ROOT / "artifacts/generated.config.txt"
MANAGER = ROOT / "build-kit/artifacts/manager/MANAGER.json"


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = s3.verified_baseline(BASELINE_PATH)
        cls.new = cls.old.replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                  'CONFIG_LOCALVERSION="-Synthetica-3.0"')

    def test_only_release_identity_may_change(self):
        changes = s3.check_config(self.old, self.new)
        self.assertEqual(list(changes), ["LOCALVERSION"])
        self.assertGreater(len(s3.read_config(self.old)), 4900)

    def test_lowercase_kconfig_symbol_is_checked(self):
        self.assertIn("I2C_MUX_PCA954x", s3.read_config(self.old))
        changed = self.new.replace("CONFIG_I2C_MUX_PCA954x=y", "CONFIG_I2C_MUX_PCA954x=m")
        self.assertNotEqual(changed, self.new)
        with self.assertRaisesRegex(ValueError, "I2C_MUX_PCA954x"):
            s3.check_config(self.old, changed)

    def test_security_cannot_be_relaxed(self):
        for symbol in ("MODULE_SIG_FORCE", "MODVERSIONS", "SECURITY_SELINUX", "DM_VERITY"):
            with self.subTest(symbol=symbol):
                changed = self.new.replace(f"CONFIG_{symbol}=y", f"# CONFIG_{symbol} is not set")
                self.assertNotEqual(changed, self.new)
                with self.assertRaises(ValueError):
                    s3.check_config(self.old, changed)

    def test_force_load_is_rejected(self):
        changed = self.new.replace("# CONFIG_MODULE_FORCE_LOAD is not set", "CONFIG_MODULE_FORCE_LOAD=y")
        with self.assertRaisesRegex(ValueError, "MODULE_FORCE_LOAD"):
            s3.check_config(self.old, changed)

    def test_features_cannot_silently_disappear(self):
        changed = self.new.replace("CONFIG_KSU=y", "# CONFIG_KSU is not set")
        with self.assertRaisesRegex(ValueError, "KSU"):
            s3.check_config(self.old, changed)

    def test_unexpected_release_rejected(self):
        with self.assertRaisesRegex(ValueError, "LOCALVERSION"):
            s3.check_config(self.old, self.old)

    def test_duplicate_and_invalid_options_are_rejected(self):
        for extra in ("CONFIG_MODULE_SIG_FORCE=n", "CONFIG_MODULE_SIG_FORCE invalid"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                s3.read_config(self.new + "\n" + extra + "\n")

    def test_wrong_baseline_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.write_text(self.old + "\n")
            with self.assertRaisesRegex(ValueError, "does not match"):
                s3.verified_baseline(p)


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.config = b"CONFIG_EXAMPLE=y\n"
        self.manager = {"package": "test.manager", "cert_sha256": "123456"}
        self.raw = (b"Linux version " + s3.EXPECTED_RELEASE.encode() + b" (build)\nKernelSU\0"
                    + b"test.manager\0" + b"123456\0IKCFG_ST" + gzip.compress(self.config)
                    + b"IKCFG_ED")

    def test_embedded_config_and_identity(self):
        s3.verify_image(self.raw, self.config, self.manager)

    def test_config_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            s3.verify_embedded_config(self.raw, b"CONFIG_EXAMPLE=n\n")

    def test_invalid_or_ambiguous_markers_rejected(self):
        for raw in (self.raw.replace(b"IKCFG_ED", b"missing"), self.raw + b"IKCFG_ST"):
            with self.subTest(raw=raw[-12:]), self.assertRaises(ValueError):
                s3.verify_embedded_config(raw, self.config)

    def test_corrupt_embedded_gzip_rejected(self):
        raw = b"IKCFG_STnot-a-gzipIKCFG_ED"
        with self.assertRaisesRegex(ValueError, "gzip"):
            s3.verify_embedded_config(raw, self.config)

    def test_bad_release_or_manager_rejected(self):
        with self.assertRaisesRegex(ValueError, "release"):
            s3.verify_image(self.raw.replace(b"Synthetica-3.0", b"Synthetica-2.0"), self.config, self.manager)
        with self.assertRaisesRegex(ValueError, "manager"):
            s3.verify_image(self.raw.replace(b"test.manager", b"other"), self.config, self.manager)
        with self.assertRaisesRegex(ValueError, "KernelSU"):
            s3.verify_image(self.raw.replace(b"KernelSU", b"missing"), self.config, self.manager)


class PrepareTests(unittest.TestCase):
    def test_disposable_copy_does_not_change_v2(self):
        source = ROOT / "build-kit"
        originals = {name: s3.digest(source / name) for name in s3.PINNED_INPUTS}
        with tempfile.TemporaryDirectory() as d:
            destination = Path(d) / "kit"
            s3.prepare(source, destination, BASELINE_PATH)
            for name, digest in originals.items():
                self.assertEqual(s3.digest(source / name), digest)
            builder = destination / "ci/rollercoaster/build-rollercoaster.sh"
            driver = destination / "scripts/build_chronicle_base.py"
            text = builder.read_text()
            self.assertIn('check-config --baseline "$S3_BASELINE"', text)
            self.assertIn("foreign vermagic bypass found", text)
            self.assertNotIn("# --- kemas AnyKernel3 ", text)
            subprocess.run(["bash", "-n", str(builder)], check=True)
            ast.parse(driver.read_text())
            self.assertIn('"fix-ikconfig"', driver.read_text())
            self.assertIn("kernel source archive does not match the pin", driver.read_text())
            self.assertIn("refusing to reuse an existing kernel tree", driver.read_text())
            self.assertNotIn('    status = {\n', driver.read_text())
            self.assertFalse((destination / "ci/rollercoaster/patches/port-allow-foreign-vermagic.patch").exists())
            self.assertEqual(s3.digest(destination / "artifacts/manager/MANAGER.json"), s3.digest(MANAGER))
            with self.assertRaisesRegex(ValueError, "existing"):
                s3.prepare(source, destination, BASELINE_PATH)

    def test_changed_input_refuses_to_create_build_kit(self):
        real_digest = s3.digest
        source = ROOT / "build-kit"
        with tempfile.TemporaryDirectory() as d:
            destination = Path(d) / "kit"
            def changed(path):
                return "bad" if str(path).endswith("build-rollercoaster.sh") else real_digest(path)
            with mock.patch.object(s3, "digest", side_effect=changed):
                with self.assertRaisesRegex(ValueError, "input changed"):
                    s3.prepare(source, destination, BASELINE_PATH)
            self.assertFalse(destination.exists())

    def test_source_and_destination_must_be_disjoint(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            s3.prepare(ROOT / "build-kit", ROOT / "build-kit/unused-3.0-test", BASELINE_PATH)

    def test_ikconfig_patch_requires_exact_input(self):
        old = "$(obj)/config_data.gz: $(KBUILD_SRC)/arch/arm64/configs/vendor/stock_defconfig FORCE\n"
        with tempfile.TemporaryDirectory() as d:
            tree = Path(d)
            (tree / "kernel").mkdir()
            makefile = tree / "kernel/Makefile"
            makefile.write_text(old)
            with self.assertRaisesRegex(ValueError, "differs"):
                s3.fix_ikconfig(tree)
            with mock.patch.object(s3, "SOURCE_MAKEFILE_SHA256", s3.digest(makefile)):
                s3.fix_ikconfig(tree)
                self.assertEqual(makefile.read_text(), "$(obj)/config_data.gz: $(KCONFIG_CONFIG) FORCE\n")
                with self.assertRaisesRegex(ValueError, "differs"):
                    s3.fix_ikconfig(tree)


class FinishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_temp = tempfile.TemporaryDirectory()
        p = Path(cls.cert_temp.name)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=Unit Test Only", "-keyout", str(p / "key.pem"),
                        "-out", str(p / "cert.pem")], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        cls.cert = subprocess.run(["openssl", "x509", "-in", str(p / "cert.pem"), "-outform", "DER"],
                                  check=True, stdout=subprocess.PIPE).stdout

    @classmethod
    def tearDownClass(cls):
        cls.cert_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.kit, self.out, self.result = root / "kit", root / "out", root / "result"
        (self.kit / "artifacts/manager").mkdir(parents=True)
        (self.out / "certs").mkdir(parents=True)
        shutil.copyfile(MANAGER, self.kit / "artifacts/manager/MANAGER.json")
        old = BASELINE_PATH.read_text()
        self.config = old.replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                  'CONFIG_LOCALVERSION="-Synthetica-3.0"').encode()
        (self.out / ".config").write_bytes(self.config)
        (self.kit / "artifacts/generated.config.txt").write_bytes(self.config)
        self.manager = json.loads(MANAGER.read_text())
        self.raw = (b"Linux version " + s3.EXPECTED_RELEASE.encode() + b" test\nKernelSU\0"
                    + self.manager["package"].encode() + b"\0" + self.manager["cert_sha256"].encode()
                    + b"\0IKCFG_ST" + gzip.compress(self.config) + b"IKCFG_ED\0" + self.cert)
        self.write_image(self.raw)
        (self.out / "Module.symvers").write_text("0x12345678\tmodule_layout\tvmlinux\tEXPORT_SYMBOL\n")
        (self.out / "System.map").write_text("00000000 T example\n")
        (self.out / "certs/signing_key.x509").write_bytes(self.cert)

    def write_image(self, raw):
        (self.kit / "artifacts/Image.gz").write_bytes(gzip.compress(raw))

    def finish(self):
        with mock.patch.object(s3, "MIN_IMAGE_BYTES", 0):
            s3.finish(self.kit, self.out, BASELINE_PATH, ROOT / "artifacts/Image.gz", self.result)

    def test_finish_produces_only_reviewable_nonflashable_files(self):
        self.finish()
        status = json.loads((self.result / "STATUS.json").read_text())
        self.assertEqual(status["status"], "COMPILED_ONLY_DO_NOT_FLASH")
        self.assertEqual(status["module_layout_crc"], "0x12345678")
        self.assertTrue(status["embedded_config_matches_generated"])
        self.assertFalse(status["same_public_certificate_found_in_2_0_image"])
        self.assertFalse(status["private_signing_key_exported"])
        self.assertEqual(len(list(self.result.iterdir())), 8)
        self.assertFalse(any(p.suffix in {".pem", ".key", ".zip"} for p in self.result.iterdir()))
        subprocess.run(["sha256sum", "-c", "SHA256SUMS.txt"], cwd=self.result,
                       check=True, stdout=subprocess.DEVNULL)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.finish()

    def test_mismatched_public_cert_fails_before_output(self):
        self.write_image(self.raw.replace(self.cert, b"not-the-certificate"))
        with self.assertRaisesRegex(ValueError, "certificate"):
            self.finish()
        self.assertFalse(self.result.exists())

    def test_missing_modversion_fails_before_output(self):
        (self.out / "Module.symvers").write_text("0x00000000\tmodule_layout\tvmlinux\tEXPORT_SYMBOL\n")
        with self.assertRaisesRegex(ValueError, "module_layout"):
            self.finish()
        self.assertFalse(self.result.exists())

    def test_manager_tampering_fails_before_output(self):
        (self.kit / "artifacts/manager/MANAGER.json").write_text('{}')
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.finish()
        self.assertFalse(self.result.exists())

    def test_collected_config_tampering_fails_before_output(self):
        (self.kit / "artifacts/generated.config.txt").write_bytes(b"other")
        with self.assertRaisesRegex(ValueError, "collected config"):
            self.finish()
        self.assertFalse(self.result.exists())


if __name__ == "__main__":
    unittest.main()
