"""Exercise Synthetica 3.0 module gates using synthetic, actually signed ELF files.

Fixtures are not real drivers and must never be installed on a device. Native
assembler output has only its ELF machine field changed for parser coverage.
"""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_synthetica3_modules", ROOT / "build-kit/scripts/verify_synthetica3_modules.py"
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_synthetica3", ROOT / "build-kit/scripts/build_synthetica3.py"
)
build = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(build)
RELEASE = "4.14.357-openela-Synthetica-3.0"
LAYOUT_CRC = 0x08EFCBB0
SYMVERS = "0x08efcbb0\tmodule_layout\tvmlinux\tEXPORT_SYMBOL\n0x12345678\tfake_symbol\tvmlinux\tEXPORT_SYMBOL\n"


class SignedModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.counter = 0
        for name in ("signer", "different"):
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-subj", "/CN=" + name, "-addext", "basicConstraints=critical,CA:FALSE",
                "-keyout", str(cls.directory / (name + ".key")),
                "-out", str(cls.directory / (name + ".pem")),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.cert = cls.der("signer")
        cls.other_cert = cls.der("different")
        cls.symvers = verifier.symvers_records(SYMVERS)
        cls.modules = {
            name: cls.make_module(name, depends="rmnet_shs" if name == "rmnet_perf" else "")
            for name in verifier.MODULE_CONFIG
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def der(cls, name):
        return subprocess.run([
            "openssl", "x509", "-in", str(cls.directory / (name + ".pem")), "-outform", "DER"
        ], check=True, stdout=subprocess.PIPE).stdout

    @classmethod
    def make_module(cls, name="rmnet_perf", release=RELEASE, layout=LAYOUT_CRC,
                    extra_crc=0x12345678, depends="", symbol="fake_symbol", signer="signer",
                    flags="SMP preempt mod_unload modversions aarch64", author=b"original"):
        cls.counter += 1
        base = cls.directory / ("fixture-" + str(cls.counter))
        source, obj, payload, signature = (base.with_suffix(ext) for ext in (".s", ".o", ".bin", ".p7s"))
        source.write_text(
            '.section .modinfo,"a"\n'
            f'.asciz "name={name}"\n'
            f'.asciz "vermagic={release} {flags}"\n'
            '.asciz "license=GPL v2"\n'
            '.asciz "author=original"\n'
            f'.asciz "depends={depends}"\n'
            '.section __versions,"a"\n.balign 64\n'
            f'.quad {layout}\n.asciz "module_layout"\n.balign 64\n'
            f'.quad {extra_crc}\n.asciz "{symbol}"\n.balign 64\n', encoding="ascii"
        )
        subprocess.run(["gcc", "-c", str(source), "-o", str(obj)], check=True, stdout=subprocess.DEVNULL)
        data = bytearray(obj.read_bytes())
        data[18:20] = struct.pack("<H", 183)  # Parser fixture only, NOT executable AArch64 code.
        if len(author) != len(b"original"):
            raise ValueError("fixture author replacement must preserve section offsets")
        data = data.replace(b"author=original", b"author=" + author, 1)
        payload.write_bytes(data)
        subprocess.run([
            "openssl", "cms", "-sign", "-binary", "-in", str(payload),
            "-signer", str(cls.directory / (signer + ".pem")),
            "-inkey", str(cls.directory / (signer + ".key")), "-outform", "DER",
            "-out", str(signature), "-nosmimecap", "-noattr",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sig = signature.read_bytes()
        return bytes(data) + sig + struct.pack(">BBBBB3sI", 0, 0, 2, 0, 0, b"\0\0\0", len(sig)) + verifier.SIG_MAGIC

    def check(self, data, name="rmnet_perf", cert=None, kernel=None):
        cert = self.cert if cert is None else cert
        kernel = b"raw kernel contains " + cert + b" exactly once" if kernel is None else kernel
        return verifier.verify_module(
            data, name=name, release=RELEASE, symvers=self.symvers,
            certificate_der=cert, raw_kernel=kernel,
        )

    def setUp(self):
        self.stage_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.stage_temp.cleanup)
        self.stage = Path(self.stage_temp.name) / "kernel"
        self.stage.mkdir()
        for name, data in self.modules.items():
            path = self.stage / (name + ".ko")
            path.write_bytes(data)
        self.config = {key: "m" for key in verifier.MODULE_CONFIG.values()}

    def collect(self):
        return verifier.collect(self.stage, config=self.config, release=RELEASE,
                                certificate_der=self.cert, raw_kernel=b"x" + self.cert + b"y",
                                symvers_text=SYMVERS)

    def test_real_pkcs7_and_all_version_records_are_verified(self):
        checked = self.check(self.modules["rmnet_perf"])
        self.assertEqual(checked["name"], "rmnet_perf")
        self.assertEqual(checked["module_layout_crc"], "0x08efcbb0")
        self.assertEqual(checked["version_records_verified"], 2)
        self.assertEqual(checked["dependencies"], ["rmnet_shs"])
        self.assertTrue(checked["signature_verified_with_embedded_certificate"])
        self.assertEqual(len(self.collect()), 6)

    def test_builder_loads_verifier_and_collects_same_build_output(self):
        out = Path(self.stage_temp.name) / "out"
        dest = out / "synthetica3-modules/lib/modules" / RELEASE / "kernel"
        dest.parent.mkdir(parents=True)
        shutil.copytree(self.stage, dest)
        config = "".join(f"CONFIG_{key}={value}\n" for key, value in self.config.items()).encode()
        result = build.collect_module_evidence(out, config, b"x" + self.cert + b"y", self.cert, SYMVERS)
        self.assertEqual(set(result), set(verifier.MODULE_CONFIG))
        self.assertTrue(all(row[1]["signature_verified_with_embedded_certificate"] for row in result.values()))

    def test_non_ascii_descriptive_metadata_allowed_but_identity_is_strict(self):
        signed = self.make_module(author=b"J\xc3\xb6rg XY")
        self.assertEqual(self.check(signed)["name"], "rmnet_perf")
        with self.assertRaisesRegex(ValueError, "non-ASCII required.*name"):
            verifier.module_info(b"name=rmnet_\xff\0vermagic=valid\0")
        with self.assertRaisesRegex(ValueError, "duplicate.*name"):
            verifier.module_info(b"name=one\0name=two\0vermagic=valid\0")

    def test_changed_payload_signature_and_wrong_certificate_are_rejected(self):
        data = self.modules["rmnet_perf"]
        changed = data.replace(b"author=original", b"author=tampered", 1)
        self.assertNotEqual(data, changed)
        with self.assertRaisesRegex(ValueError, "signature"):
            self.check(changed)
        with self.assertRaisesRegex(ValueError, "signature"):
            self.check(data, cert=self.other_cert)
        with self.assertRaisesRegex(ValueError, "certificate"):
            self.check(data, kernel=b"no certificate")
        with self.assertRaisesRegex(ValueError, "certificate"):
            self.check(data, kernel=self.cert + self.cert)

    def test_layout_and_other_symbol_crc_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "MODVERSIONS.*module_layout"):
            self.check(self.make_module(layout=0x6968EE15))
        with self.assertRaisesRegex(ValueError, "MODVERSIONS.*fake_symbol"):
            self.check(self.make_module(extra_crc=0x87654321))
        with self.assertRaisesRegex(ValueError, "MODVERSIONS.*missing_symbol"):
            self.check(self.make_module(symbol="missing_symbol"))

    def test_wrong_name_release_and_unselected_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, "name"):
            self.check(self.make_module(name="impostor"))
        with self.assertRaisesRegex(ValueError, "vermagic"):
            self.check(self.make_module(release="4.14.190-perf"))
        with self.assertRaisesRegex(ValueError, "vermagic"):
            self.check(self.make_module(flags="SMP mod_unload modversions aarch64"))
        with self.assertRaisesRegex(ValueError, "dependency"):
            self.check(self.make_module(depends="not_selected"))

    def test_unsigned_bad_header_and_truncated_elf_rejected(self):
        data = self.modules["rmnet_perf"]
        payload, _ = verifier.split_signature(data)
        with self.assertRaisesRegex(ValueError, "signature"):
            self.check(payload)
        with self.assertRaises(ValueError):
            self.check(data[:-1])
        with self.assertRaisesRegex(ValueError, "ELF"):
            verifier.elf_sections(b"not an ELF")

    def test_missing_duplicate_symlink_or_unexpected_module_rejected(self):
        victim = self.stage / "tcp_bic.ko"
        original = victim.read_bytes()
        victim.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.collect()
        victim.write_bytes(original)
        dup = self.stage / "other/tcp_bic.ko"
        dup.parent.mkdir()
        dup.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.collect()
        dup.unlink()
        victim.unlink()
        victim.symlink_to(self.stage / "tcp_htcp.ko")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.collect()
        victim.unlink()
        victim.write_bytes(original)
        (self.stage / "unknown.ko").write_bytes(original)
        with self.assertRaisesRegex(ValueError, "module set"):
            self.collect()

    def test_all_failed_modules_are_reported_without_exporting_results(self):
        for name in ("tcp_bic", "rmnet_perf"):
            path = self.stage / (name + ".ko")
            path.write_bytes(path.read_bytes().replace(b"author=original", b"author=tampered", 1))
        with self.assertRaises(ValueError) as caught:
            self.collect()
        self.assertIn("tcp_bic: module signature", str(caught.exception))
        self.assertIn("rmnet_perf: module signature", str(caught.exception))

    def test_cyclic_loadable_dependencies_are_rejected(self):
        (self.stage / "rmnet_shs.ko").write_bytes(self.make_module(name="rmnet_shs", depends="rmnet_perf"))
        with self.assertRaisesRegex(ValueError, "cyclic"):
            self.collect()

    def test_config_and_symvers_are_fail_closed(self):
        self.config["RMNET_SHS"] = "y"
        with self.assertRaisesRegex(ValueError, "config"):
            self.collect()
        self.config["RMNET_SHS"] = "m"
        self.config["UNEXPECTED_MODULE"] = "m"
        with self.assertRaisesRegex(ValueError, "config"):
            self.collect()
        with self.assertRaisesRegex(ValueError, "conflicting"):
            verifier.symvers_records(SYMVERS + "0x87654321\tfake_symbol\tvmlinux\n")
        with self.assertRaisesRegex(ValueError, "module_layout"):
            verifier.symvers_records("0x00000000\tmodule_layout\tvmlinux\n")


if __name__ == "__main__":
    unittest.main()
