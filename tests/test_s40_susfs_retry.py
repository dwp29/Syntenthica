"""Research guards and host-shim schedules for the retry candidate."""
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
import probe_s40_susfs_retry as retry


class RetryGuardTests(unittest.TestCase):
    def test_patch_and_source_checked_before_scratch_creation(self):
        with tempfile.TemporaryDirectory(prefix='s40-retry-test-') as temp:
            root = Path(temp)
            patch = root / 'bad.patch'
            patch.write_text('not the pinned patch\n')
            with mock.patch.object(retry, 'PATCH', patch):
                with self.assertRaisesRegex(ValueError, 'patch SHA-256 mismatch'):
                    retry.apply_retry('bad source', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())
            with self.assertRaisesRegex(ValueError, 'input source SHA-256 mismatch'):
                retry.apply_retry('bad source', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())

    def test_unpinned_candidate_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unpinned retry candidate source'):
            retry.program('not the candidate', 'not the header')

    def test_control_uses_the_stalled_not_the_retry_pin(self):
        with self.assertRaisesRegex(ValueError, 'Unpinned retry candidate source'):
            retry.control_program('not the stalled candidate', 'not the header')


@unittest.skipUnless(shutil.which('git') and shutil.which('gcc'), 'git and gcc required')
class RetryScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            raise unittest.SkipTest('set S40_ABI_SUSFS to the pinned 2.4 source')
        cls.susfs = Path(susfs)

    def test_control_really_loses_the_concurrent_request(self):
        """Without this, a passing retry run would prove nothing.

        The pinned stalled candidate runs the identical harness with only
        ``EXPECT_RECOVERED`` flipped, and it must drop the request that arrived
        while the doomed ``kthread_run`` was blocked.
        """
        self.assertEqual(retry.control(self.susfs),
                         'control: blocked failure dropped the concurrent request')

    def test_retry_candidate_redrives_and_stays_claimable(self):
        result = retry.probe(self.susfs)
        for field in ('generation_guard_preserves_new_config_in_model',
                      'busy_requests_coalesce_into_another_pass_in_model',
                      'requests_immediately_before_and_after_idle_transition_modeled',
                      'failed_launch_no_longer_drops_concurrent_request_in_model',
                      'exhausted_retry_leaves_claimable_retry_state_not_idle',
                      'later_request_completes_refresh_after_exhausted_retry_in_model'):
            self.assertTrue(result[field], field)
        for field in ('candidate_is_complete_or_safe_for_kernel',
                      'real_rcu_filesystem_selinux_kthreads_or_device_tested',
                      'susfs_2_4_integrated'):
            self.assertFalse(result[field], field)
        self.assertEqual(result['scope'], 'HOST_SHIM_SCHEDULE_MODEL_ONLY')


if __name__ == '__main__':
    unittest.main()
