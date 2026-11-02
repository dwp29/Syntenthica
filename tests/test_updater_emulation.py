"""Host-sandbox regression checks; no test opens a real device or partition."""
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import audit_updater_emulation as emu
import build_guarded_candidate as builder


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sample_script():
    prop1, prop2 = emu.SCRIPT_PROPERTIES
    lines = [prop1 + b';'] * 6 + [prop2 + b';'] * 5
    for name in emu.PARTITIONS:
        lines.append(f'package_extract_file("{name}.img", "/dev/block/bootdevice/by-name/{name}");'.encode())
    return b'\n'.join(lines) + b'\n'


def guarded_script(script):
    for name in emu.PARTITIONS:
        old = f'package_extract_file("{name}.img", "/dev/block/bootdevice/by-name/{name}");'.encode()
        script = script.replace(old, b'assert(' + old[:-1] + b');')
    return script


def regular(data):
    return {"type": "regular", "bytes": len(data), "sha256": sha(data),
            "unchanged_sentinel": data == emu.SENTINEL}


def simulated_result(payloads, guarded, right=True, failure=None):
    states = {}
    for index, name in enumerate(emu.PARTITIONS):
        if name == failure:
            states[name] = {"type": "directory"}
            continue
        written = right and (failure is None or not guarded or index < emu.PARTITIONS.index(failure))
        states[name] = regular(payloads[name] if written else emu.SENTINEL)
    return {"exit_code": 1 if not right or (guarded and failure) else 0,
            "reported_completed": right and (failure is None or not guarded),
            "device_rejected": not right, "open_failure_reported": failure is not None,
            "assert_failed": bool(guarded and failure), "fake_targets": states}


class UpdaterSandboxTests(unittest.TestCase):
    def test_property_substitution_does_not_change_real_write_expressions(self):
        old = sample_script()
        new = guarded_script(old)
        with mock.patch.multiple(builder, OLD_SCRIPT_SHA=sha(old), NEW_SCRIPT_SHA=sha(new)):
            actual = emu.synthetic_script(old, False, True)
            protected = emu.synthetic_script(old, True, True)
        self.assertNotIn(b'getprop(', actual)
        self.assertEqual(actual.count(b'"joyeuse"'), 11)
        for name in emu.PARTITIONS:
            self.assertIn(f'package_extract_file("{name}.img"'.encode(), actual)
            self.assertIn(f'assert(package_extract_file("{name}.img"'.encode(), protected)

    def test_unexpected_script_is_refused_before_execution(self):
        with self.assertRaises(emu.SimulationError):
            emu.synthetic_script(b'not the pinned script', True, True)

    def test_bad_property_count_fails_closed(self):
        old = sample_script().replace(emu.SCRIPT_PROPERTIES[0], b'"x"', 1)
        with mock.patch.object(builder, 'OLD_SCRIPT_SHA', sha(old)):
            with self.assertRaises(emu.SimulationError):
                emu.synthetic_script(old, False, True)

    def test_synthetic_zip_only_contains_selected_fake_payloads(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'sample.zip'
            script = b'ui_print("test");\n'
            payloads = emu.make_payloads()
            emu.write_synthetic_zip(path, script, payloads)
            with zipfile.ZipFile(path) as z:
                self.assertEqual(set(z.namelist()), {builder.SCRIPT, 'super.img', 'boot.img', 'dtbo.img'})
                self.assertEqual(z.read(builder.SCRIPT), script)
                for name in emu.PARTITIONS:
                    self.assertEqual(z.read(name + '.img'), payloads[name])
            with self.assertRaises(emu.SimulationError):
                emu.write_synthetic_zip(path, script, payloads)

    def test_fake_property_area_contains_only_disposable_joyeuse_value(self):
        area = emu.fake_joyeuse_property_area()
        self.assertEqual(len(area), 128 * 1024)
        self.assertIn(b'ro.product.device\0', area)
        self.assertIn(b'joyeuse\0', area)
        self.assertNotIn(b'ro.build.product', area)

    def test_real_dtbo_fixture_must_match_pinned_hash_and_size(self):
        with self.assertRaises(emu.SimulationError):
            emu.make_payloads(b'not-a-real-dtbo')

    def test_validators_cover_success_wrong_device_and_all_open_failures(self):
        payloads = emu.make_payloads()
        for guarded in (False, True):
            for right, failure in ((True, None), (False, None),
                                   (True, 'super'), (True, 'boot'), (True, 'dtbo')):
                with self.subTest(guarded=guarded, right=right, failure=failure):
                    result = simulated_result(payloads, guarded, right, failure)
                    emu.validate_synthetic(result, payloads, guarded, right, failure)

    def test_validator_rejects_guarded_continuation_after_failure(self):
        payloads = emu.make_payloads()
        result = simulated_result(payloads, True, True, 'boot')
        result['fake_targets']['dtbo'] = regular(payloads['dtbo'])
        with self.assertRaises(emu.SimulationError):
            emu.validate_synthetic(result, payloads, True, True, 'boot')

    def test_real_zip_validator_requires_early_device_rejection(self):
        result = simulated_result(emu.make_payloads(), False, False)
        emu.validate_real_archive(result)
        result['fake_targets']['super'] = regular(b'changed')
        with self.assertRaises(emu.SimulationError):
            emu.validate_real_archive(result)

    def test_identity_rejects_symlinks_and_wrong_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sample'; p.write_bytes(b'abc')
            link = Path(d) / 'link'; link.symlink_to(p)
            self.assertEqual(emu.regular_identity(p, 3, sha(b'abc'))['bytes'], 3)
            with self.assertRaises(emu.SimulationError):
                emu.regular_identity(link, 3, sha(b'abc'))
            with self.assertRaises(emu.SimulationError):
                emu.regular_identity(p, 3, sha(b'wrong'))

    def test_no_unsafe_fallback_without_namespace_tool(self):
        with mock.patch.object(emu.shutil, 'which', return_value=None):
            with self.assertRaises(emu.SimulationError):
                emu._exec_isolated(Path('/unused'), Path('/unused'))

    def test_fake_file_size_limit_validator(self):
        payloads = emu.make_payloads()
        for guarded in (False, True):
            result = simulated_result(payloads, guarded, True, None)
            result['fake_targets']['super'] = regular(b'')
            result['file_limit_failure_reported'] = True
            result['exit_code'] = 1 if guarded else 0
            result['reported_completed'] = not guarded
            result['assert_failed'] = guarded
            if guarded:
                for name in ('boot', 'dtbo'):
                    result['fake_targets'][name] = regular(emu.SENTINEL)
            emu.validate_fake_file_limit(result, payloads, guarded)
            result['fake_targets']['super'] = regular(emu.SENTINEL)
            with self.assertRaises(emu.SimulationError):
                emu.validate_fake_file_limit(result, payloads, guarded)

    def test_invalid_file_size_limit_refused(self):
        with self.assertRaises(emu.SimulationError):
            emu._exec_isolated(Path('/unused'), Path('/unused'), file_size_limit=-1)

    def test_unknown_failure_target_refused(self):
        with self.assertRaises(emu.SimulationError):
            emu.run_sandbox(Path('/unused'), b'', Path('/unused'), 'recovery')


if __name__ == '__main__':
    unittest.main()
