"""Research guards and host-shim schedules for the stalled marker candidate."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import probe_s40_susfs_stalled as stalled


class StalledGuardTests(unittest.TestCase):
    def test_patch_and_source_checked_before_scratch_creation(self):
        with tempfile.TemporaryDirectory(prefix='s40-stalled-test-') as temp:
            root = Path(temp)
            patch = root / 'bad.patch'
            patch.write_text('not the pinned patch\n')
            with mock.patch.object(stalled, 'PATCH', patch):
                with self.assertRaisesRegex(ValueError, 'patch SHA-256 mismatch'):
                    stalled.apply_stalled('bad source', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())
            with self.assertRaisesRegex(ValueError, 'input source SHA-256 mismatch'):
                stalled.apply_stalled('bad source', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())

    def test_scenario_anchors_fail_closed(self):
        with mock.patch.object(stalled.pending, 'MAIN', 'unexpected'):
            with self.assertRaisesRegex(ValueError, 'shim anchor'):
                stalled.stalled_main()


@unittest.skipUnless(shutil.which('git') and shutil.which('gcc'), 'git and gcc required')
class StalledScheduleTests(unittest.TestCase):
    def test_stalled_marker_needs_external_future_request(self):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            self.skipTest('set S40_ABI_SUSFS to pinned SUSFS source')
        result = stalled.probe(Path(susfs))
        for field in ('busy_requests_and_idle_boundary_schedules_modeled',
                      'failed_launch_concurrent_request_leaves_internal_stalled_marker',
                      'repeated_explicit_launch_failure_remains_stalled',
                      'later_explicit_request_can_recover_in_model',
                      'worker_skip_failed_can_publish_empty_bitmap_for_injected_errors',
                      'setter_skip_failed_can_report_success_for_injected_io_error'):
            self.assertTrue(result[field], field)
        for field in ('automatic_retry_or_external_failure_reporting_implemented',
                      'stalled_state_alone_guarantees_eventual_refresh',
                      'candidate_is_complete_or_safe_for_kernel',
                      'real_rcu_filesystem_selinux_kthreads_or_device_tested',
                      'susfs_2_4_integrated'):
            self.assertFalse(result[field], field)


if __name__ == '__main__':
    unittest.main()
