"""Host-only ROM-module audit tests; no real ROM or device is required."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import audit_synthetica2_rom_modules as audit  # noqa: E402
import audit_synthetica3_vendor as vendor  # noqa: E402


class InputAndInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.modules = self.root / "modules"
        self.modules.mkdir()

    def test_no_modules_or_unsafe_symlink_root_is_accepted(self):
        with self.assertRaisesRegex(ValueError, "no uncompressed"):
            audit.module_paths(self.modules)
        link = self.root / "link"
        link.symlink_to(self.modules, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "nonsymlink"):
            audit.module_paths(link)

    def test_nested_modules_symlinks_and_compressed_entries_are_separate(self):
        nested = self.modules / "nested"
        nested.mkdir()
        (nested / "real.ko").write_bytes(b"test")
        (nested / "compressed.ko.gz").write_bytes(b"test")
        (nested / "compressed.ko.lz4").write_bytes(b"test")
        (nested / "link.ko").symlink_to(nested / "real.ko")
        paths, skipped = audit.module_paths(self.modules)
        self.assertEqual([p.name for p in paths], ["real.ko"])
        self.assertEqual(len(skipped), 3)
        self.assertTrue(any(path.endswith("compressed.ko.lz4") for path in skipped))

    def test_synthetic_errors_are_not_counted_as_compatible(self):
        (self.modules / "broken.ko").write_bytes(b"not ELF")
        target = {"release": "test", "mode": "on", "image_sha256": "a", "certificate_sha256": "b"}
        report = audit.audit(self.modules, target)
        self.assertEqual(report["summary"]["module_files_found"], 1)
        self.assertEqual(report["summary"]["module_files_unparsed"], 1)
        self.assertEqual(report["summary"]["module_layout_matches"], 0)
        self.assertIn("no device test", report["scope"])

    def test_existing_signed_fixture_is_compared_without_modification(self):
        bundle = ROOT / "artifacts/synthetica-3.0"
        source = bundle / "signed-modules/tcp_bic.ko"
        module = self.modules / "tcp_bic.ko"
        shutil.copy2(source, module)
        before = hashlib.sha256(module.read_bytes()).hexdigest()
        target = vendor.load_bundle(bundle)
        target.update(mode="off", certificate_sha256=hashlib.sha256(target["cert"]).hexdigest())
        result = audit.audit(self.modules, target)
        summary = result["summary"]
        self.assertEqual((summary["module_files_parsed"], summary["module_layout_matches"],
                          summary["vermagic_matches"], summary["verified_with_exported_build_certificate"]), (1, 1, 1, 1))
        self.assertEqual(hashlib.sha256(module.read_bytes()).hexdigest(), before)


class CandidateValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.cert = b"test-only-public-certificate"
        raw = b"Linux version " + audit.s2x.EXPECTED_RELEASE.encode() + b" test\x00" + self.cert
        self.files = {"Image.gz.DO-NOT-FLASH": gzip.compress(raw), "generated.config.txt": b"config\n",
                      "Module.symvers": b"0x00000001 module_layout vmlinux EXPORT_SYMBOL\n",
                      "System.map": b"00000000 T module_layout\n", "module-signing-public-cert.x509": self.cert}
        hashes = {"image_sha256": "Image.gz.DO-NOT-FLASH", "config_sha256": "generated.config.txt",
                  "module_symvers_sha256": "Module.symvers", "system_map_sha256": "System.map",
                  "module_public_cert_sha256": "module-signing-public-cert.x509"}
        for name, data in self.files.items():
            (self.candidate / name).write_bytes(data)
        self.status = {"kind": "EXPERIMENTAL_COMPILED_ONLY_DO_NOT_FLASH", "release": audit.s2x.EXPECTED_RELEASE,
                       "base_source": audit.s2x.v3.SOURCE, "installer_created": False, "private_key_exported": False,
                       "mglru": {"variant": "on", "enabled_by_default": True}, "module_layout_crc": "0x00000001",
                       "same_build_modules_static_checks": {},
                       **{field: hashlib.sha256(self.files[name]).hexdigest() for field, name in hashes.items()}}
        self.save_status()

    def save_status(self):
        (self.candidate / "STATUS.json").write_text(json.dumps(self.status))

    def load(self):
        with mock.patch.object(audit.s2x.v3, "verified_baseline", return_value="baseline"), \
             mock.patch.object(audit.s2x, "check_config") as guard, \
             mock.patch.object(audit.s2x.v3, "verify_embedded_config") as embedded:
            result = audit.load_candidate(self.candidate, self.root / "baseline")
            guard.assert_called_once_with("baseline", "config\n", "on")
            embedded.assert_called_once()
            return result

    def test_valid_status_and_evidence_are_loaded(self):
        result = self.load()
        self.assertEqual(result["mode"], "on")
        self.assertEqual(result["symvers"]["module_layout"], 1)
        self.assertEqual(result["cert"], self.cert)

    def test_digest_tampering_is_rejected(self):
        (self.candidate / "Module.symvers").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.load()

    def test_wrong_variant_or_crc_is_rejected(self):
        self.status["mglru"]["enabled_by_default"] = False
        self.save_status()
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.load()
        self.status["mglru"]["enabled_by_default"] = True
        self.status["module_layout_crc"] = "0x00000002"
        self.save_status()
        with self.assertRaisesRegex(ValueError, "module_layout CRC"):
            self.load()

    def test_private_report_cannot_be_written_into_input(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            vendor.write_private(self.candidate / "report.json", {}, [self.candidate])


if __name__ == "__main__":
    unittest.main()
