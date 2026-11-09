"""Host tests using fake ADB only; never tests recovery or a real phone."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build-kit/ci/s31-adb-capture/capture.py'
spec = importlib.util.spec_from_file_location('s31capture', SCRIPT)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class RecoveryCaptureTests(unittest.TestCase):
    def test_boot_reads_pstore_first_rejects_unsafe_names_and_records_missing(self):
        calls = []
        def fake(adb, serial, args):
            calls.append(args)
            if args == ['get-state']:
                return 0, b'device\n', 'ok'
            if args == ['shell', 'ls', '-1', '/sys/fs/pstore']:
                return 0, b'dmesg-ramoops-0\n../bad\nfoo;bad\ndmesg-ramoops-0\nconsole-ramoops-0\n', 'ok'
            if args[:3] == ['shell', 'ls', '-1']:
                if args[-1] == '/sdcard/Synthetica':
                    return 0, b'install-log-20261031.txt\ninstall-log-x;reboot.txt\n', 'ok'
                return 1, b'', 'command_failed'
            if args[-1] == '/proc/last_kmsg':
                return 1, b'', 'command_failed'
            return 0, b'private log\n', 'ok'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'boot'
            with mock.patch.object(capture, 'run_adb', side_effect=fake):
                report = capture.capture('boot', out, 'adb', 'SECRET-SERIAL')
            self.assertEqual(calls[0], ['get-state'])
            self.assertEqual(calls[1], ['shell', 'ls', '-1', '/sys/fs/pstore'])
            self.assertEqual(calls[2], ['exec-out', 'cat', '/sys/fs/pstore/dmesg-ramoops-0'])
            self.assertEqual(calls[4:6], [['exec-out', 'cat', '/proc/last_kmsg'],
                                         ['exec-out', 'cat', '/tmp/recovery.log']])
            self.assertIn(['exec-out', 'cat', '/sdcard/Synthetica/install-log-20261031.txt'], calls)
            self.assertNotIn(['exec-out', 'cat', '/sdcard/Synthetica/install-log-x;reboot.txt'], calls)
            self.assertTrue(all('bad' not in ' '.join(args) for args in calls))
            self.assertEqual(report['pstore_skipped_or_duplicate_names'], 3)
            self.assertEqual(report['files']['last_kmsg']['status'], 'command_failed')
            self.assertEqual((out / 'pstore-dmesg-ramoops-0').read_bytes(), b'private log\n')
            self.assertNotIn('SECRET-SERIAL', (out / 'STATUS.json').read_text())
            self.assertEqual(json.loads((out / 'STATUS.json').read_text()), report)
            with self.assertRaisesRegex(ValueError, 'must not exist'):
                capture.capture('boot', out, 'adb', None)

    def test_install_reads_recovery_only_and_empty_is_not_successful_capture(self):
        def fake(adb, serial, args):
            if args == ['get-state']:
                return 0, b'device\n', 'ok'
            if args == ['exec-out', 'cat', '/tmp/recovery.log']:
                return 0, b'', 'ok'
            self.assertEqual(args[:3], ['shell', 'ls', '-1'])
            self.assertIn(args[-1], capture.INSTALL_DIRS)
            return 1, b'', 'command_failed'
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(capture, 'run_adb', side_effect=fake):
            report = capture.capture('install', Path(temp) / 'session', 'adb', None)
            self.assertEqual(report['files']['recovery_log']['status'], 'empty')
            self.assertEqual(list(report['files']), ['recovery_log'])

    def test_recovery_state_is_accepted_but_sideload_is_not(self):
        def fake(adb, serial, args):
            if args == ['get-state']:
                return 0, b'recovery\n', 'ok'
            return 1, b'', 'command_failed'
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(capture, 'run_adb', side_effect=fake):
                report = capture.capture('install', Path(temp) / 'recovery', 'adb', None)
                self.assertEqual(report['adb_state'], 'recovery')
                self.assertEqual(report['files']['recovery_log']['status'], 'command_failed')
            with mock.patch.object(capture, 'run_adb', return_value=(0, b'sideload\n', 'ok')):
                report = capture.capture('boot', Path(temp) / 'sideload', 'adb', None)
                self.assertEqual(report['adb_state'], 'unexpected_state')
                self.assertEqual(report['files'], {})

    def test_no_adb_writes_no_log_and_records_failure(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(capture, 'run_adb', return_value=(None, b'', 'adb_unavailable')):
            report = capture.capture('boot', Path(temp) / 'session', 'adb', None)
            self.assertEqual(report['files'], {})
            self.assertEqual(report['adb_state'], 'adb_unavailable')

    def test_truncated_capture_is_marked_and_hash_is_for_saved_data(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(capture, 'MAX_BYTES', 4):
            report = capture.store(Path(temp), 'entry', b'1234567')
            self.assertEqual(report['status'], 'truncated')
            self.assertEqual((Path(temp) / 'entry').read_bytes(), b'1234')
            self.assertEqual(report['bytes_saved'], 4)
            self.assertEqual(report['sha256_saved'], capture.hashlib.sha256(b'1234').hexdigest())
            with self.assertRaises(FileExistsError):
                capture.store(Path(temp), 'entry', b'different')

    def test_adb_arguments_are_list_without_shell_and_timeout_is_reported(self):
        def fake_run(cmd, **kwargs):
            self.assertEqual(cmd, ['adb', '-s', 'identifier', 'exec-out', 'cat', '/tmp/recovery.log'])
            self.assertNotIn('shell', kwargs)
            self.assertEqual(kwargs['timeout'], capture.TIMEOUT)
            raise subprocess.TimeoutExpired(cmd, capture.TIMEOUT)
        with mock.patch.object(capture.subprocess, 'run', side_effect=fake_run):
            self.assertEqual(capture.run_adb('adb', 'identifier', ['exec-out', 'cat', '/tmp/recovery.log']),
                             (None, b'', 'timeout'))

    @unittest.skipIf(sys.platform == 'win32', 'POSIX executable fixture')
    def test_cli_with_fake_executable_only_uses_read_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adb = root / 'fake-adb'
            adb.write_text(f'''#!{sys.executable}
import sys
args = sys.argv[1:]
if args == ['get-state']:
    print('device')
elif args == ['shell', 'ls', '-1', '/sys/fs/pstore']:
    print('dmesg-ramoops-0')
elif args == ['exec-out', 'cat', '/sys/fs/pstore/dmesg-ramoops-0']:
    sys.stdout.buffer.write(b'fake panic data\\n')
elif args == ['exec-out', 'cat', '/proc/last_kmsg']:
    sys.exit(1)
elif args == ['exec-out', 'cat', '/tmp/recovery.log']:
    print('fake recovery')
else:
    sys.exit(91)
''')
            adb.chmod(0o700)
            output = root / 'result'
            result = subprocess.run([sys.executable, str(SCRIPT), '--stage', 'boot',
                                     '--out', str(output), '--adb', str(adb)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / 'pstore-dmesg-ramoops-0').read_bytes(), b'fake panic data\n')
            report = json.loads((output / 'STATUS.json').read_text())
            self.assertEqual(report['files']['last_kmsg']['status'], 'command_failed')
            self.assertEqual(report['files']['recovery_log']['status'], 'captured')

    def test_shell_metacharacters_cannot_enter_remote_pstore_path(self):
        for name in ('../x', '/x', 'x;reboot', '$(id)', 'x y', '.hidden', ''):
            self.assertIsNone(capture.NAME.fullmatch(name), name)
        for name in ('dmesg-ramoops-0', 'console-ramoops-0', 'pmsg-ramoops-0'):
            self.assertIsNotNone(capture.NAME.fullmatch(name), name)


if __name__ == '__main__':
    unittest.main()
