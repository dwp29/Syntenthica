import contextlib
import hashlib
import os
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import build_guarded_candidate as builder
from guarded_testdata import digest, manually_guard, synthetic_script, tiny_archive

REAL_OLD_SCRIPT_SHA = builder.OLD_SCRIPT_SHA
REAL_NEW_SCRIPT_SHA = builder.NEW_SCRIPT_SHA


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextlib.contextmanager
def configured_for_synthetic(source, original_expected):
    old = synthetic_script()
    new = manually_guard(old)
    expected = {name: dict(row) for name, row in original_expected.items()}
    expected[builder.SCRIPT]["bytes"] = len(new)
    expected[builder.SCRIPT]["sha256"] = digest(new)
    overrides = {"BASE_BYTES": source.stat().st_size, "BASE_SHA": file_sha(source),
                 "OLD_SCRIPT_SHA": digest(old), "NEW_SCRIPT_SHA": digest(new)}
    with mock.patch.multiple(builder, **overrides), \
         mock.patch.object(builder, "expectations", return_value=expected), \
         mock.patch.object(builder, "actual_updater_assert_shape", return_value={"test_fixture_only": True}):
        yield expected


class ScriptTransformationTests(unittest.TestCase):
    def setUp(self):
        self.old = synthetic_script()
        self.new = manually_guard(self.old)
        self.old_sha = mock.patch.object(builder, "OLD_SCRIPT_SHA", digest(self.old))
        self.new_sha = mock.patch.object(builder, "NEW_SCRIPT_SHA", digest(self.new))
        self.old_sha.start()
        self.new_sha.start()
        self.addCleanup(self.old_sha.stop)
        self.addCleanup(self.new_sha.stop)

    def test_exactly_three_wrappers_and_no_other_change(self):
        self.assertEqual(builder.guard_script(self.old), self.new)
        self.assertEqual(len(self.new) - len(self.old), 24)
        reversed_script = self.new
        for part in builder.PARTITIONS:
            old = f'package_extract_file("{part}.img", "/dev/block/bootdevice/by-name/{part}");'.encode()
            new = b"assert(" + old[:-1] + b");"
            self.assertEqual(reversed_script.count(new), 1)
            reversed_script = reversed_script.replace(new, old, 1)
        self.assertEqual(reversed_script, self.old)

    def test_rejects_unlocked_original(self):
        with self.assertRaises(builder.GuardBuildError):
            builder.guard_script(self.old + b" ")

    def test_rejects_missing_expected_write_even_if_identity_replaced(self):
        altered = self.old.replace(b'"dtbo.img"', b'"other.img"', 1)
        with mock.patch.object(builder, "OLD_SCRIPT_SHA", digest(altered)):
            with self.assertRaises(builder.GuardBuildError):
                builder.guard_script(altered)

    def test_rejects_duplicate_expected_write_even_if_identity_replaced(self):
        line = b'package_extract_file("super.img", "/dev/block/bootdevice/by-name/super");'
        altered = self.old + line
        with mock.patch.object(builder, "OLD_SCRIPT_SHA", digest(altered)):
            with self.assertRaises(builder.GuardBuildError):
                builder.guard_script(altered)

    def test_rejects_unexpected_result_hash(self):
        with mock.patch.object(builder, "NEW_SCRIPT_SHA", "0" * 64):
            with self.assertRaises(builder.GuardBuildError):
                builder.guard_script(self.old)

    def test_actual_lock_names_original_super_and_script(self):
        with mock.patch.multiple(builder, OLD_SCRIPT_SHA=REAL_OLD_SCRIPT_SHA, NEW_SCRIPT_SHA=REAL_NEW_SCRIPT_SHA):
            result = builder.expectations(ROOT / "synthetica-project/original-baseline.lock.json", self.new)
        self.assertEqual(result["super.img"]["sha256"], builder.BASE_SUPER_SHA)
        self.assertEqual(result[builder.SCRIPT]["sha256"], REAL_NEW_SCRIPT_SHA)
        self.assertEqual(result["boot.img"]["sha256"],
                         "57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d")
        self.assertEqual(result["dtbo.img"]["sha256"],
                         "9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2")


class ArchiveBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetica-guard-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir / "first.zip"
        self.output = self.dir / "second.zip"
        self.expected = tiny_archive(self.source)
        self.source_sha = file_sha(self.source)

    def test_synthetic_build_preserves_every_other_member_and_stream(self):
        with configured_for_synthetic(self.source, self.expected):
            result = builder.build(self.source, self.output, self.dir / "unused-lock")
            self.assertEqual(result["output"]["sha256"], file_sha(self.output))
            self.assertEqual(result["source"]["sha256"], self.source_sha)
            self.assertTrue(result["unchanged_member_uncompressed_content_verified"])
            self.assertTrue(result["unchanged_member_compressed_streams_identical"])
            self.assertFalse(result["output"]["signed_by_this_recipe"])
            self.assertEqual(result["status"], "host_verified_not_device_tested_not_flash_approved")
        self.assertEqual(file_sha(self.source), self.source_sha)
        self.assertFalse((self.dir / "second.zip.partial").exists())
        with zipfile.ZipFile(self.source) as old, zipfile.ZipFile(self.output) as new:
            self.assertEqual(old.namelist(), new.namelist())
            self.assertEqual(old.comment, new.comment)
            for name in old.namelist():
                self.assertEqual(builder.metadata_tuple(old.getinfo(name)), builder.metadata_tuple(new.getinfo(name)))
                if name == builder.SCRIPT:
                    self.assertEqual(new.read(name), manually_guard(old.read(name)))
                else:
                    self.assertEqual(old.read(name), new.read(name))
                    self.assertEqual(old.getinfo(name).CRC, new.getinfo(name).CRC)

    def test_refuses_incorrect_source_identity_without_creating_output(self):
        with configured_for_synthetic(self.source, self.expected), mock.patch.object(builder, "BASE_SHA", "0" * 64):
            with self.assertRaises(builder.GuardBuildError):
                builder.build(self.source, self.output, self.dir / "unused-lock")
        self.assertFalse(self.output.exists())
        self.assertFalse((self.dir / "second.zip.partial").exists())
        self.assertEqual(file_sha(self.source), self.source_sha)

    def test_refuses_existing_output_or_partial_without_changing_it(self):
        with configured_for_synthetic(self.source, self.expected):
            self.output.write_bytes(b"preexisting")
            with self.assertRaises(builder.GuardBuildError):
                builder.build(self.source, self.output, self.dir / "unused-lock")
            self.assertEqual(self.output.read_bytes(), b"preexisting")
            self.output.unlink()
            partial = self.dir / "second.zip.partial"
            partial.write_bytes(b"preexisting partial")
            with self.assertRaises(builder.GuardBuildError):
                builder.build(self.source, self.output, self.dir / "unused-lock")
            self.assertEqual(partial.read_bytes(), b"preexisting partial")

    def test_refuses_output_symlink_and_source_symlink(self):
        with configured_for_synthetic(self.source, self.expected):
            self.output.symlink_to(self.dir / "missing-target")
            with self.assertRaises(builder.GuardBuildError):
                builder.build(self.source, self.output, self.dir / "unused-lock")
            self.output.unlink()
            linked = self.dir / "linked.zip"
            linked.symlink_to(self.source)
            with self.assertRaises(builder.guard.AuditError):
                builder.build(linked, self.output, self.dir / "unused-lock")
        self.assertEqual(file_sha(self.source), self.source_sha)

    def test_bad_member_hash_fails_and_only_own_partial_is_removed(self):
        with configured_for_synthetic(self.source, self.expected) as expected:
            expected["super.img"]["sha256"] = "0" * 64
            with self.assertRaises(builder.GuardBuildError):
                builder.build(self.source, self.output, self.dir / "unused-lock")
        self.assertFalse(self.output.exists())
        self.assertFalse((self.dir / "second.zip.partial").exists())
        self.assertEqual(file_sha(self.source), self.source_sha)

    def test_raced_partial_file_not_deleted(self):
        partial = self.dir / "second.zip.partial"
        real_zipfile = zipfile.ZipFile

        def simulate_race(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, os.PathLike)) and Path(file) == partial and mode == "x":
                partial.write_bytes(b"created by someone else")
                raise FileExistsError("another process won the race")
            return real_zipfile(file, mode, *args, **kwargs)

        with configured_for_synthetic(self.source, self.expected):
            with mock.patch.object(builder.zipfile, "ZipFile", side_effect=simulate_race):
                with self.assertRaises(FileExistsError):
                    builder.build(self.source, self.output, self.dir / "unused-lock")
        self.assertEqual(partial.read_bytes(), b"created by someone else")

    def test_raw_compressed_stream_change_is_detected(self):
        with configured_for_synthetic(self.source, self.expected):
            builder.build(self.source, self.output, self.dir / "unused-lock")
        with zipfile.ZipFile(self.source) as a, zipfile.ZipFile(self.output) as b:
            original_infos = {i.filename: i for i in a.infolist()}
            output_infos = {i.filename: i for i in b.infolist()}
        with self.output.open("r+b") as f:
            offset = builder._raw_data_offset(f, output_infos["boot.img"])
            f.seek(offset)
            byte = f.read(1)
            f.seek(offset)
            f.write(bytes([byte[0] ^ 1]))
        with self.assertRaises(builder.GuardBuildError):
            builder.compare_raw_compressed(self.source, self.output, original_infos, output_infos)

    def test_duplicate_members_rejected(self):
        bad = self.dir / "duplicates.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(bad, "x") as z:
                z.writestr("same", b"one")
                z.writestr("same", b"two")
        with zipfile.ZipFile(bad) as z, self.assertRaises(builder.GuardBuildError):
            builder.zip_members(z, {"same": {"bytes": 3}})

    def test_path_traversal_member_rejected(self):
        bad = self.dir / "unsafe.zip"
        with zipfile.ZipFile(bad, "x") as z:
            z.writestr("../outside", b"unsafe")
        with zipfile.ZipFile(bad) as z, self.assertRaises(builder.GuardBuildError):
            builder.zip_members(z, {"../outside": {"bytes": 6}})

    def test_metadata_change_comparison(self):
        a = zipfile.ZipInfo("member", (2026, 11, 2, 4, 0, 0))
        b = zipfile.ZipInfo("member", (2026, 11, 2, 4, 0, 2))
        self.assertNotEqual(builder.metadata_tuple(a), builder.metadata_tuple(b))


if __name__ == "__main__":
    unittest.main()
