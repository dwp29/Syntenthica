"""Guard and deterministic host-shim tests for the incomplete pending candidate."""
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
import probe_s40_susfs_pending as pending
import probe_s40_susfs_priority as priority


class PendingGuardTests(unittest.TestCase):
    def test_patch_and_input_pin_checked_before_creating_scratch(self):
        with tempfile.TemporaryDirectory(prefix='s40-pending-test-') as temp:
            root = Path(temp)
            bad = root / 'bad.patch'
            bad.write_text('not the pinned patch\n')
            with mock.patch.object(pending, 'PATCH', bad):
                with self.assertRaisesRegex(ValueError, 'patch SHA-256 mismatch'):
                    pending.apply_pending('anything', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())
            with self.assertRaisesRegex(ValueError, 'input source SHA-256 mismatch'):
                pending.apply_pending('not the pinned source', root / 'scratch')
            self.assertFalse((root / 'scratch').exists())

    def test_model_refuses_unpinned_source_and_ambiguous_shim(self):
        with self.assertRaisesRegex(ValueError, 'Unpinned pending candidate'):
            pending.program('untrusted source', 'header')
        for text in ('missing', 'anchor anchor'):
            with self.assertRaisesRegex(ValueError, 'shim anchor'):
                pending.replace_once(text, 'anchor', 'replacement')


@unittest.skipUnless(shutil.which('gcc') and shutil.which('git'), 'gcc and git required')
class PinnedPendingModelTests(unittest.TestCase):
    def test_scheduled_interleavings_and_known_failure(self):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            self.skipTest('set S40_ABI_SUSFS to pinned source')
        result = pending.probe(Path(susfs))
        for name in ('generation_guard_preserves_new_config_in_model',
                     'busy_requests_coalesce_into_another_pass_in_model',
                     'requests_immediately_before_and_after_idle_transition_modeled',
                     'failed_worker_creation_can_still_drop_concurrent_request_in_model',
                     'later_request_can_recover_after_modeled_failure'):
            self.assertTrue(result[name], name)
        for name in ('candidate_is_complete_or_safe_for_kernel',
                     'real_rcu_filesystem_selinux_kthreads_or_device_tested',
                     'susfs_2_4_integrated'):
            self.assertFalse(result[name], name)

    def test_program_rejects_modified_header(self):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            self.skipTest('set S40_ABI_SUSFS to pinned source')
        root = Path(susfs)
        original = priority.checked_susfs_file(root, priority.SOURCE)
        header = priority.checked_susfs_file(root, priority.HEADER)
        with tempfile.TemporaryDirectory(prefix='s40-pending-source-') as temp:
            guarded = priority.apply_candidate(original, Path(temp) / 'guard')
            candidate = pending.apply_pending(guarded, Path(temp) / 'pending')
        with self.assertRaisesRegex(ValueError, 'Unpinned priority header'):
            pending.program(candidate, header + '\n')


if __name__ == '__main__':
    unittest.main()
