"""Host-only control-flow checks for bounded synthetic-test runner."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import signal
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s3rc_qemu_runner', ROOT / 'build-kit/scripts/run_synthetica3_rc_qemu.py')
runner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(runner)


class BoundedRunnerTests(unittest.TestCase):
    def test_success_uses_isolated_session(self):
        process = mock.Mock(pid=12345, returncode=0)
        process.communicate.return_value = ('test ... ok\n\nOK\n', None)
        with mock.patch.object(runner.subprocess, 'Popen', return_value=process) as launch:
            runner.run_case('test_repack_preserves_sections_header_and_vbmeta_bytes', 30)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertEqual(launch.call_args.kwargs['cwd'], ROOT / 'tests')
        process.communicate.assert_called_once_with(timeout=30)

    def test_failure_and_skip_are_not_success(self):
        for code, output in ((1, 'FAIL\n'), (0, 'OK (skipped=1)\n'), (0, 'no result\n')):
            process = mock.Mock(pid=12345, returncode=code)
            process.communicate.return_value = (output, None)
            with self.subTest(code=code, output=output), \
                 mock.patch.object(runner.subprocess, 'Popen', return_value=process), \
                 self.assertRaises(ValueError):
                runner.run_case('test_case', 30)

    def test_timeout_kills_only_the_child_session_and_reports_failure(self):
        process = mock.Mock(pid=12345, returncode=-9)
        process.communicate.side_effect = [subprocess.TimeoutExpired('test', 30), ('partial log\n', None)]
        with mock.patch.object(runner.subprocess, 'Popen', return_value=process), \
             mock.patch.object(runner.os, 'killpg') as kill, \
             self.assertRaisesRegex(ValueError, 'timed out'):
            runner.run_case('test_case', 30)
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)


if __name__ == '__main__':
    unittest.main()
