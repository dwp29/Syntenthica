"""Model a specific upstream priority-filter race with host shims only."""
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
import probe_s40_susfs_priority as priority


class PriorityProbeGuardTests(unittest.TestCase):
    def test_exact_function_extraction_rejects_missing_and_duplicate(self):
        source = 'static int sample(void) {\n  if (1) {\n    return 1;\n  }\n}\n'
        self.assertEqual(priority.extract_function(source, 'static int sample('), source.rstrip())
        with self.assertRaisesRegex(ValueError, 'Expected one'):
            priority.extract_function(source, 'static int missing(')
        with self.assertRaisesRegex(ValueError, 'Expected one'):
            priority.extract_function(source + source, 'static int sample(')
        with self.assertRaisesRegex(ValueError, 'Unterminated'):
            priority.extract_function('static int broken(void) {\n', 'static int broken(')

    def test_candidate_patch_hash_is_checked_before_application(self):
        with tempfile.TemporaryDirectory(prefix='s40-priority-bad-patch-') as temp:
            root = Path(temp)
            bad = root / 'bad.patch'
            bad.write_text('not the pinned patch\n')
            with mock.patch.object(priority, 'PATCH', bad):
                with self.assertRaisesRegex(ValueError, 'patch SHA-256 mismatch'):
                    priority.apply_candidate('anything', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())

    def test_candidate_rejects_unpinned_original_before_creating_scratch(self):
        with tempfile.TemporaryDirectory(prefix='s40-priority-bad-source-') as temp:
            root = Path(temp) / 'scratch'
            with self.assertRaisesRegex(ValueError, 'Original research source SHA-256 mismatch'):
                priority.apply_candidate('not the pinned source', root)
            self.assertFalse(root.exists())

    def test_source_helpers_reject_unrecognized_priority_block(self):
        with self.assertRaisesRegex(ValueError, 'priority globals'):
            priority.source_parts('not the expected source', 'not the expected header')


@unittest.skipUnless(shutil.which('gcc') and shutil.which('git'), 'gcc and git required')
class RealPinnedPriorityModelTests(unittest.TestCase):
    def test_actual_upstream_and_research_guard_under_fixed_schedule(self):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            self.skipTest('set S40_ABI_SUSFS to the pinned 2.4 source')
        result = priority.probe(Path(susfs))
        self.assertTrue(result['baseline_worker_can_publish_stale_bitmap_in_modeled_interleaving'])
        self.assertTrue(result['research_generation_guard_preserves_newer_bitmap_in_same_model'])
        self.assertTrue(result['another_sequential_refresh_recovers_in_model'])
        self.assertTrue(result['busy_refresh_request_can_be_lost_in_second_scheduled_model'])
        self.assertTrue(result['research_generation_guard_does_not_prevent_lost_uid_refresh'])
        self.assertTrue(result['later_request_recovers_after_simulated_uid_change'])
        self.assertFalse(result['candidate_patch_applied_to_kernel_or_release'])
        self.assertFalse(result['real_rcu_filesystem_selinux_faults_or_device_tested'])
        self.assertFalse(result['full_concurrency_or_refresh_correctness_proven'])


if __name__ == '__main__':
    unittest.main()
