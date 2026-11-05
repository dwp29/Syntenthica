"""Host-only tests: public build artifacts and synthetic init/Kbuild fixtures.

No ROM, device, private module, or private report is required by these tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "build-kit/scripts"
sys.path.insert(0, str(SCRIPTS))
import audit_synthetica3_vendor as audit  # noqa: E402
import verify_synthetica3_modules as verify  # noqa: E402
from test_synthetica3_boot import boot, dtbo, fdt  # noqa: E402

BUNDLE = ROOT / "artifacts/synthetica-3.0"
MODULES = BUNDLE / "signed-modules"


def payload(name: str) -> bytes:
    return verify.split_signature((MODULES / f"{name}.ko").read_bytes())[0]


class ParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload("rmnet_perf")

    def test_registered_callback_is_found_even_without_parmtype_metadata(self):
        elf = audit.ModuleELF(self.data)
        self.assertNotIn(b"parmtype=rmnet_perf_opt_mode\0", elf.sections[".modinfo"])
        self.assertTrue({"rmnet_perf_opt_mode", "rmnet_perf_ingress_deag"}
                        <= elf.registered_parameters())
        self.assertIn("debug", audit.ModuleELF(payload("gspca_main")).registered_parameters())

    def test_corrupted_parameter_string_is_not_accepted(self):
        elf = audit.ModuleELF(self.data)
        symbol = next(x for x in elf.symbols if x[0] == "__param_str_rmnet_perf_opt_mode")
        mutated = bytearray(self.data)
        mutated[elf.rows[symbol[3]][4] + symbol[4]] ^= 1
        with self.assertRaisesRegex(ValueError, "parameter name"):
            audit.ModuleELF(bytes(mutated)).registered_parameters()

    def test_corrupted_parameter_relocation_is_not_accepted(self):
        elf = audit.ModuleELF(self.data)
        symbol = next(x for x in elf.symbols if x[0] == "__param_rmnet_perf_opt_mode")
        section = elf.names.index("__param")
        mutated = bytearray(self.data)
        found = False
        for row in elf.rows:
            if row[1] != 4 or row[7] != section:
                continue
            for pos in range(row[4], row[4] + row[5], 24):
                target, _, addend = struct.unpack_from("<QQq", self.data, pos)
                if target == symbol[4]:
                    struct.pack_into("<q", mutated, pos + 16, addend + 1)
                    found = True
        self.assertTrue(found)
        with self.assertRaisesRegex(ValueError, "different string"):
            audit.ModuleELF(bytes(mutated)).registered_parameters()

    def test_truncated_elf_is_not_accepted(self):
        with self.assertRaises(ValueError):
            audit.ModuleELF(self.data[:80])


class VersionProviderTests(unittest.TestCase):
    def test_provider_evidence_does_not_conflate_map_and_exports(self):
        text = (
            "0x00000001 module_layout vmlinux EXPORT_SYMBOL\n"
            "0x00000002 builtin_ok vmlinux EXPORT_SYMBOL\n"
            "0x00000003 external_ok drivers/example/demo-driver EXPORT_SYMBOL_GPL\n"
            "0x00000004 external_missing drivers/example/unbundled EXPORT_SYMBOL\n"
            "0x00000005 different vmlinux EXPORT_SYMBOL\n"
            "0x00000006 ambiguous vmlinux EXPORT_SYMBOL\n"
            "0x00000006 ambiguous drivers/example/demo-driver EXPORT_SYMBOL\n"
        )
        target = {"symvers": verify.symvers_records(text),
                  "export_providers": audit.export_provider_index(text, {"demo_driver"}),
                  "map_names": {"different", "not_exported"}}
        versions = {"module_layout": 1, "builtin_ok": 2, "external_ok": 3,
                    "external_missing": 4, "different": 999, "not_exported": 7,
                    "missing": 8, "ambiguous": 6}
        result = audit.compare_version_records(versions, target)
        self.assertEqual((result["matched"], result["different"], result["absent_from_bundle"]), (5, 1, 2))
        differences = {row["symbol"]: row for row in result["unmatched_details"]}
        self.assertEqual(differences["different"]["module_crc"], "0x000003e7")
        self.assertEqual(differences["different"]["bundle_crc"], "0x00000005")
        self.assertEqual(differences["different"]["bundle_export_providers"][0]["kind"], "vmlinux")
        self.assertTrue(differences["not_exported"]["name_in_bundle_system_map"])
        self.assertIsNone(differences["not_exported"]["bundle_crc"])
        self.assertEqual(differences["not_exported"]["bundle_export_providers"], [])
        self.assertFalse(differences["missing"]["name_in_bundle_system_map"])
        loadable = {row["symbol"]: row for row in result["matching_only_loadable_providers"]}
        self.assertEqual(set(loadable), {"external_ok", "external_missing"})
        self.assertTrue(loadable["external_ok"]["providers"][0]["name_matches_bundled_module"])
        self.assertFalse(loadable["external_missing"]["providers"][0]["name_matches_bundled_module"])
        ambiguous = result["matching_ambiguous_providers"]
        self.assertEqual([row["symbol"] for row in ambiguous], ["ambiguous"])
        self.assertEqual({p["kind"] for p in ambiguous[0]["providers"]}, {"vmlinux", "loadable_module"})
        self.assertIn("not proof", result["scope"])

    def test_conflicting_provider_crc_is_rejected(self):
        text = ("0x1 module_layout vmlinux EXPORT_SYMBOL\n"
                "0x2 duplicate drivers/a/a EXPORT_SYMBOL\n"
                "0x3 duplicate drivers/b/b EXPORT_SYMBOL\n")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            audit.export_provider_index(text, set())


class ListAndInitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_lists_reject_unsafe_or_duplicate_names(self):
        (self.root / "modules.load").write_text("a.ko\nb.ko\n")
        (self.root / "modules.dep").write_text("/vendor/lib/modules/a.ko: b.ko\nb.ko:\n")
        load, deps = audit.read_lists(self.root)
        self.assertEqual(load, ["a.ko", "b.ko"])
        self.assertEqual(deps["a.ko"], ["b.ko"])
        (self.root / "modules.load").write_text("a.ko\na.ko\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit.read_lists(self.root)
        (self.root / "modules.load").write_text("../a.ko\n")
        with self.assertRaisesRegex(ValueError, "unsafe|unsupported"):
            audit.read_lists(self.root)
        with self.assertRaisesRegex(ValueError, "unsafe|unsupported"):
            audit.module_basename("a.ko.xz")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            audit.module_basename("a\\b.ko")

    def test_dependency_cycles_are_separate_from_missing_metadata(self):
        deps = {"a.ko": ["b.ko"], "b.ko": ["a.ko"], "c.ko": ["a.ko"],
                "d.ko": ["missing.ko"], "e.ko": []}
        self.assertEqual(audit.unresolved_cycles(deps, set(deps)), ["a.ko", "b.ko", "c.ko"])
        self.assertEqual(audit.unresolved_cycles({"a.ko": ["b.ko"], "b.ko": []},
                                                 {"a.ko", "b.ko"}), [])

    def test_init_literals_parameters_search_directories_and_unparsed_options(self):
        (self.root / "sample.rc").write_text('''
on property:example=1
    exec u:r:test:s0 -- /vendor/bin/modprobe -d /vendor/lib/modules demo first=1 callback="ok"
    exec u:r:test:s0 -- /vendor/bin/modprobe -r -d /other/modules demo
    insmod /vendor/lib/modules/second.ko example=1
    exec u:r:test:s0 -- /vendor/bin/modprobe --unknown demo
''')
        commands, unparsed = audit.init_commands(self.root, {"demo": {"first", "callback"}})
        self.assertEqual(len(commands), 3)
        self.assertEqual(len(unparsed), 1)
        self.assertEqual(commands[0]["search_dirs"], ["/vendor/lib/modules"])
        self.assertEqual(commands[0]["bundle_parameter_comparisons"][0]["not_found_in_bundle_parameters"], [])
        self.assertTrue(commands[1]["remove_requested"])
        self.assertEqual(commands[2]["operation"], "insmod")
        self.assertEqual(commands[2]["modules"], ["second"])

    def test_source_index_records_only_candidate_matches(self):
        tree = self.root / "source"
        (tree / "techpack/audio/4.0/config").mkdir(parents=True)
        (tree / "techpack/audio/4.0/config/atollauto.conf").write_text("CONFIG_BAR=y\n")
        (tree / "drivers/example").mkdir(parents=True)
        (tree / "drivers/example/Kbuild").write_text(
            "MODNAME := callback_driver\n"
            "obj-$(CONFIG_FOO) += demo-driver.o\n"
            "obj-$(CONFIG_BAR) += $(MODNAME).o\n"
        )
        idx = audit.source_index(tree, {"FOO": "m"})
        self.assertEqual(idx["demo_driver"][0]["generated_config"], "m")
        self.assertEqual(idx["callback_driver"][0]["atoll_auto_config"], "y")
        self.assertEqual(idx["callback_driver"][0]["generated_config"], "not present")


class BundleAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = audit.load_bundle(BUNDLE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.modules = self.root / "vendor-modules"
        self.modules.mkdir()
        for name in ("rmnet_perf", "rmnet_shs", "gspca_main"):
            shutil.copyfile(MODULES / f"{name}.ko", self.modules / f"{name}.ko")
        (self.modules / "modules.load").write_text("rmnet_perf.ko\nrmnet_shs.ko\ngspca_main.ko\n")
        (self.modules / "modules.dep").write_text(
            "/vendor/lib/modules/rmnet_perf.ko: /vendor/lib/modules/rmnet_shs.ko\n"
            "/vendor/lib/modules/rmnet_shs.ko:\n"
            "/vendor/lib/modules/gspca_main.ko:\n"
        )
        self.init = self.root / "init"
        self.init.mkdir()
        (self.init / "example.rc").write_text('''
on property:example=1
    exec u:r:test:s0 -- /vendor/bin/modprobe -d /vendor/lib/modules rmnet_perf rmnet_perf_opt_mode="udp"
    exec u:r:test:s0 -- /vendor/bin/modprobe -a -d /vendor/lib/modules rmnet_shs
''')

    def test_bundle_verification_and_module_signatures(self):
        self.assertEqual(self.target["release"], "4.14.357-openela-Synthetica-3.0")
        self.assertIn("rmnet_perf_opt_mode", self.target["parameters"]["rmnet_perf"])
        row = audit.audit_one(self.modules / "gspca_main.ko", self.target, True)
        self.assertEqual(row["signature_result"], "verified_with_bundle_certificate")
        self.assertTrue(row["module_layout_matches_bundle"])
        self.assertEqual(row["version_records"]["different"], 0)
        self.assertEqual(row["version_records"]["absent_from_bundle"], 0)
        self.assertEqual(row["version_records"]["unmatched_details"], [])
        symbol = "gspca_frame_add"
        provider = audit.compare_version_records({symbol: self.target["symvers"][symbol]}, self.target)
        self.assertEqual(provider["matched"], 1)
        only = provider["matching_only_loadable_providers"]
        self.assertEqual(only[0]["symbol"], symbol)
        self.assertEqual(only[0]["providers"][0]["module_name"], "gspca_main")
        self.assertTrue(only[0]["providers"][0]["name_matches_bundled_module"])

    def test_unsigned_or_modified_signature_not_mistaken_for_verified(self):
        path = self.modules / "gspca_main.ko"
        data = path.read_bytes()
        stripped, _ = verify.split_signature(data)
        path.write_bytes(stripped)
        self.assertEqual(audit.audit_one(path, self.target, True)["signature_result"], "no_appended_signature")
        # Alter a descriptive field without changing offsets or ELF structure.
        changed = data.replace(b"parm=debug:", b"parm=dEbug:", 1)
        self.assertNotEqual(data, changed)
        path.write_bytes(changed)
        self.assertEqual(audit.audit_one(path, self.target, True)["signature_result"],
                         "not_verified_with_bundle_certificate")

    def test_full_audit_is_read_only_and_reports_load_order_not_runtime_result(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.modules.iterdir()}
        report = audit.audit(self.modules, BUNDLE, self.init)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.modules.iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(report["modules_load_count"], 3)
        self.assertEqual(len(report["dependencies_later_in_load_list"]), 1)
        self.assertEqual(report["dependency_files_missing"], [])
        self.assertEqual(report["modules_in_or_depending_on_cycles"], [])
        self.assertTrue(all(r["module_layout_matches_bundle"] for r in report["modules"]))
        self.assertEqual(report["init_commands"][0]["bundle_parameter_comparisons"][0]
                         ["not_found_in_bundle_parameters"], [])
        inventory = {x["bundle_module"]: x for x in report["bundle_module_inventory"]}
        self.assertTrue(inventory["rmnet_perf"]["referenced_in_literal_init_commands"])
        self.assertTrue(inventory["rmnet_perf"]["same_name_in_extracted_modules_dep"])
        self.assertIn("not a load, boot", report["scope"])

    def test_cli_keeps_signature_scratch_outside_repository_and_inputs(self):
        destination = self.root / "private.json"
        seen = []

        def fake_audit(*args):
            scratch = Path(tempfile.gettempdir())
            seen.append(scratch)
            self.assertEqual(scratch.parent, self.root)
            self.assertEqual(scratch.stat().st_mode & 0o777, 0o700)
            return {"modules": []}

        previous = tempfile.tempdir
        with mock.patch.object(sys, "argv", ["audit", "--modules", str(self.modules),
                                            "--bundle", str(BUNDLE), "--output", str(destination)]), \
             mock.patch.object(audit, "audit", side_effect=fake_audit):
            self.assertEqual(audit.main(), 0)
        self.assertEqual(tempfile.tempdir, previous)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())
        self.assertTrue(destination.is_file())

    def test_cli_boot_dtbo_and_candidate_end_to_end_are_read_only(self):
        images = {
            "reference.img": boot(),
            "candidate.img": boot(kernel=b"different synthetic kernel"),
            "dtbo.img": dtbo([fdt(), fdt(b"test,second\0")]),
        }
        for name, raw in images.items():
            (self.root / name).write_bytes(raw)
        destination = self.root / "boot-report.json"
        argv = ["audit", "--modules", str(self.modules), "--init", str(self.init),
                "--bundle", str(BUNDLE), "--boot", str(self.root / "reference.img"),
                "--candidate-boot", str(self.root / "candidate.img"),
                "--dtbo", str(self.root / "dtbo.img"), "--output", str(destination)]
        with mock.patch.object(sys, "argv", argv):
            self.assertEqual(audit.main(), 0)
        report = json.loads(destination.read_text())
        self.assertEqual(os.stat(destination).st_mode & 0o777, 0o600)
        self.assertEqual(report["reference_boot"]["header_version"], 2)
        self.assertEqual(report["dtbo"]["entry_count"], 2)
        self.assertTrue(all(row["version_records"]["unmatched_details"] == [] for row in report["modules"]))
        self.assertTrue(all(report["boot_comparison"]["stable_header_fields_match"].values()))
        self.assertTrue(all(report["boot_comparison"]["non_kernel_sections_match"].values()))
        self.assertFalse(report["boot_comparison"]["candidate_kernel_equals_bundle_image"])
        self.assertTrue(report["boot_comparison"]["candidate_legacy_boot_id_matches"])
        self.assertEqual({name: (self.root / name).read_bytes() for name in images}, images)
        self.assertEqual(list(self.root.glob(".synthetica3-audit-*")), [])

    def test_cli_reports_mismatch_and_unexported_symbol_without_modifying_input(self):
        path = self.modules / "rmnet_perf.ko"
        raw = bytearray(path.read_bytes())
        payload, _ = verify.split_signature(bytes(raw))
        records = verify.elf_sections(payload)["__versions"]
        self.assertEqual(payload.count(records), 1)
        base = payload.index(records)
        changed_other = False
        for offset in range(0, len(records), 64):
            name = records[offset + 8:offset + 64].split(b"\0", 1)[0].decode("ascii")
            if name == "module_layout":
                struct.pack_into("<Q", raw, base + offset, 0xDEADBEEF)
            elif not changed_other:
                raw[base + offset + 8:base + offset + 64] = b"synthetic_missing\0".ljust(56, b"\0")
                changed_other = True
        self.assertTrue(changed_other)
        path.write_bytes(raw)
        before = hashlib.sha256(raw).digest()
        destination = self.root / "differences.json"
        argv = ["audit", "--modules", str(self.modules), "--bundle", str(BUNDLE),
                "--output", str(destination)]
        with mock.patch.object(sys, "argv", argv):
            self.assertEqual(audit.main(), 0)
        report = json.loads(destination.read_text())
        row = next(row for row in report["modules"] if row["file"] == path.name)
        self.assertEqual(row["signature_result"], "not_verified_with_bundle_certificate")
        details = {item["symbol"]: item for item in row["version_records"]["unmatched_details"]}
        self.assertEqual(details["module_layout"]["module_crc"], "0xdeadbeef")
        self.assertEqual(details["module_layout"]["bundle_export_providers"][0]["kind"], "vmlinux")
        self.assertIsNone(details["synthetic_missing"]["bundle_crc"])
        self.assertEqual(details["synthetic_missing"]["bundle_export_providers"], [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)
        self.assertEqual(os.stat(destination).st_mode & 0o777, 0o600)

    def test_cli_invalid_boot_inputs_leave_no_report(self):
        candidate = self.root / "candidate.img"
        candidate.write_bytes(boot())
        destination = self.root / "no-report.json"
        base = ["audit", "--modules", str(self.modules), "--bundle", str(BUNDLE),
                "--output", str(destination)]
        with mock.patch.object(sys, "argv", base + ["--candidate-boot", str(candidate)]):
            self.assertEqual(audit.main(), 1)
        self.assertFalse(destination.exists())
        symlink = self.root / "boot-link.img"
        symlink.symlink_to(candidate)
        with mock.patch.object(sys, "argv", base + ["--boot", str(symlink)]):
            self.assertEqual(audit.main(), 1)
        self.assertFalse(destination.exists())
        invalid_dtbo = self.root / "bad-dtbo.img"
        invalid_dtbo.write_bytes(b"not a dtbo")
        with mock.patch.object(sys, "argv", base + ["--boot", str(candidate), "--dtbo", str(invalid_dtbo)]):
            self.assertEqual(audit.main(), 1)
        self.assertFalse(destination.exists())
        self.assertEqual(candidate.read_bytes(), boot())
        self.assertEqual(list(self.root.glob(".synthetica3-audit-*")), [])

    def test_bundle_checksum_mismatch_is_rejected(self):
        copy = self.root / "bundle-copy"
        shutil.copytree(BUNDLE, copy)
        (copy / "README-DO-NOT-FLASH.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            audit.verify_manifest(copy)

    def test_module_symlinks_are_not_followed(self):
        path = self.modules / "gspca_main.ko"
        path.unlink()
        path.symlink_to(MODULES / "gspca_main.ko")
        with self.assertRaises(OSError):
            audit.audit_one(path, self.target, True)

    def test_report_is_private_exclusive_and_outside_repo_and_inputs(self):
        report = {"scope": "synthetic fixture"}
        with self.assertRaisesRegex(ValueError, "outside"):
            audit.write_private(ROOT / "private-fixture.json", report, [self.modules])
        with self.assertRaisesRegex(ValueError, "outside"):
            audit.write_private(self.modules / "private-fixture.json", report, [self.modules])
        with self.assertRaisesRegex(ValueError, "absolute"):
            audit.write_private(Path("relative.json"), report, [self.modules])
        output = self.root / "private-fixture.json"
        audit.write_private(output, report, [self.modules])
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            audit.write_private(output, {"changed": True}, [self.modules])
        self.assertEqual(output.read_bytes(), before)
        symlink = self.root / "link.json"
        symlink.symlink_to(output)
        with self.assertRaises(FileExistsError):
            audit.write_private(symlink, report, [self.modules])
        self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
