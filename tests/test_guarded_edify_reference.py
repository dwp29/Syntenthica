"""Execute only a mocked host reference edify; NEVER the Android updater."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/edify_lineage_8d9befac"
sys.path.insert(0, str(ROOT / "synthetica-project"))
import build_guarded_candidate as builder
from guarded_testdata import digest, manually_guard, synthetic_script


class EdifyReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bison = os.environ.get("SYNTHETICA_BISON") or shutil.which("bison")
        cls.flex = os.environ.get("SYNTHETICA_FLEX") or shutil.which("flex")
        cls.compiler = os.environ.get("CXX") or shutil.which("g++")
        cls.m4 = os.environ.get("M4") or shutil.which("m4")
        if not all((cls.bison, cls.flex, cls.compiler, cls.m4)):
            if os.environ.get("SYNTHETICA_REQUIRE_EDIFY") == "1":
                raise RuntimeError("m4, bison, flex and a C++ compiler are required")
            raise unittest.SkipTest("Host reference requires m4, bison, flex and a C++ compiler")
        cls.temp = tempfile.TemporaryDirectory(prefix="synthetica-edify-reference-")
        cls.addClassCleanup(cls.temp.cleanup)
        build = Path(cls.temp.name)
        env = {**os.environ, "M4": cls.m4}
        commands = [
            [cls.bison, f"--defines={build / 'parser.h'}", f"--output={build / 'parser.cpp'}",
             str(FIXTURE / "edify/parser.yy")],
            [cls.flex, f"--outfile={build / 'lexer.cpp'}", str(FIXTURE / "edify/lexer.ll")],
            [cls.compiler, "-std=c++17", "-O2", "-Wno-deprecated-declarations",
             "-I" + str(build), "-I" + str(FIXTURE / "edify"),
             "-I" + str(FIXTURE / "edify/include"), "-I" + str(FIXTURE / "otautil/include"),
             "-I" + str(FIXTURE / "host-shims"), str(FIXTURE / "edify/expr.cpp"),
             str(build / "parser.cpp"), str(build / "lexer.cpp"), str(FIXTURE / "host_harness.cpp"),
             "-o", str(build / "reference")],
        ]
        for cmd in commands:
            subprocess.run(cmd, check=True, env=env, capture_output=True, timeout=120)
        cls.binary = build / "reference"

    def run_reference(self, script, partition="none", mode="none"):
        result = subprocess.run([str(self.binary), partition, mode], input=script, capture_output=True,
                                check=True, timeout=10)
        lines = dict(line.split("=", 1) for line in result.stdout.decode("ascii").splitlines())
        self.assertEqual(lines["parsed"], "1")
        lines["writes"] = lines["writes"].split(",") if lines["writes"] else []
        return lines

    def exercise_original_and_guarded(self, old, new):
        parts = ["super", "boot", "dtbo"]
        for script in (old, new):
            with self.subTest(scenario="success", guarded=script == new):
                result = self.run_reference(script)
                self.assertEqual((result["aborted"], result["completed"], result["writes"]),
                                 ("0", "1", parts))
            with self.subTest(scenario="wrong-device", guarded=script == new):
                result = self.run_reference(script, "wrong-device", "none")
                self.assertEqual((result["aborted"], result["completed"], result["writes"]),
                                 ("1", "0", []))
            for index, part in enumerate(parts):
                with self.subTest(scenario="null", part=part, guarded=script == new):
                    result = self.run_reference(script, part, "null")
                    self.assertEqual((result["aborted"], result["completed"], result["writes"]),
                                     ("1", "0", parts[:index + 1]))
                with self.subTest(scenario="empty", part=part, guarded=script == new):
                    result = self.run_reference(script, part, "empty")
                    if script == old:
                        self.assertEqual((result["aborted"], result["completed"], result["writes"]),
                                         ("0", "1", parts))
                    else:
                        self.assertEqual((result["aborted"], result["completed"], result["writes"],
                                          result["error_present"]), ("1", "0", parts[:index + 1], "1"))

    def test_reference_parser_and_mocks_on_small_synthetic_script(self):
        old = synthetic_script()
        expected = manually_guard(old)
        with mock.patch.multiple(builder, OLD_SCRIPT_SHA=digest(old), NEW_SCRIPT_SHA=digest(expected)):
            self.assertEqual(builder.guard_script(old), expected)
        self.exercise_original_and_guarded(old, expected)

    def test_reference_parser_rejects_syntax_error(self):
        bad = b'assert(package_extract_file("super.img",);\n'
        result = subprocess.run([str(self.binary), "none", "none"], input=bad, capture_output=True,
                                timeout=10)
        self.assertNotEqual(result.returncode, 0)

    def test_exact_previous_candidate_script_when_available(self):
        path = os.environ.get("SYNTHETICA_REFERENCE_ZIP")
        if not path:
            self.skipTest("No local copy of the pinned first candidate supplied")
        with zipfile.ZipFile(path, "r", allowZip64=True) as archive:
            info = archive.getinfo(builder.SCRIPT)
            self.assertEqual(info.file_size, 1545)
            original = archive.read(info)
            updater = archive.read(builder.static_audit.BINARY)
        observation = builder.actual_updater_assert_shape(updater)
        self.assertEqual(observation["updater_sha256"], builder.static_audit.BINARY_SHA256)
        self.assertEqual(observation["evaluate_call_address"], 0x351EEC)
        self.assertEqual(observation["selected_string_length_zero_branch_address"], 0x351F08)
        self.assertEqual(digest(original), builder.OLD_SCRIPT_SHA)
        guarded = builder.guard_script(original)
        self.assertEqual(digest(guarded), builder.NEW_SCRIPT_SHA)
        self.exercise_original_and_guarded(original, guarded)


if __name__ == "__main__":
    unittest.main()
