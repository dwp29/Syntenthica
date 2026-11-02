"""Checks for read-only reassembly and guarded updater emulation."""
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_guarded_zip64_draft as draft
import audit_updater_emulation as emu
import build_guarded_candidate as builder


def sha(value):
    return hashlib.sha256(value).hexdigest()


class DraftZip64Tests(unittest.TestCase):
    def test_verified_part_copy(self):
        with tempfile.TemporaryDirectory() as td:
            part = Path(td) / 'part'; part.write_bytes(b'small part')
            row = {'bytes': 10, 'sha256': sha(b'small part')}
            output = io.BytesIO(); total = hashlib.sha256()
            draft.append_verified_part(part, row, total, output)
            self.assertEqual(output.getvalue(), b'small part')
            self.assertEqual(total.hexdigest(), row['sha256'])

    def test_part_wrong_hash_and_length_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            part = Path(td) / 'part'; part.write_bytes(b'abc')
            for row in ({'bytes': 3, 'sha256': sha(b'bad')}, {'bytes': 99, 'sha256': sha(b'abc')}):
                with self.subTest(row=row), self.assertRaises(draft.DraftTestError):
                    draft.append_verified_part(part, row, hashlib.sha256(), io.BytesIO())

    def test_nonempty_work_directory_is_refused_before_network(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(draft.transfer, 'validate_context'):
            (Path(td) / 'existing').write_text('keep')
            with mock.patch.object(draft.transfer, 'read_release') as get:
                with self.assertRaises(draft.DraftTestError):
                    draft.download_existing_draft(Path(td))
                get.assert_not_called()
            self.assertEqual((Path(td) / 'existing').read_text(), 'keep')

    @unittest.skipUnless(
        Path('/tmp/synthetica-build-boot-first-r1/synthetica-boot-first-20261102-01.zip').is_file()
        and Path('/tmp/synthetica-qemu-ref-rurioss/qemu-aarch64-static').is_file(),
        'Local pinned reference and QEMU are optional')
    def test_sandbox_end_to_end_with_small_synthetic_container(self):
        # This is only a small fake ZIP with the real guarded script and updater;
        # the CI audit separately checks the exact 4.7 GB candidate SHA-256.
        source = Path('/tmp/synthetica-build-boot-first-r1/synthetica-boot-first-20261102-01.zip')
        qemu = Path('/tmp/synthetica-qemu-ref-rurioss/qemu-aarch64-static')
        with zipfile.ZipFile(source) as z:
            old, binary = z.read(builder.SCRIPT), z.read(emu.audit.BINARY)
        guarded = builder.guard_script(old)
        with tempfile.TemporaryDirectory() as td:
            small = Path(td) / 'synthetic-container.zip'
            with zipfile.ZipFile(small, 'x', zipfile.ZIP_DEFLATED) as z:
                z.writestr(builder.SCRIPT, guarded)
                z.writestr(emu.audit.BINARY, binary)
                for name, data in emu.make_payloads().items():
                    z.writestr(name + '.img', data)
            data = small.read_bytes()
            with mock.patch.multiple(draft, CANDIDATE_BYTES=len(data), CANDIDATE_SHA256=sha(data)):
                result = draft.audit_guarded_candidate(small, qemu)
            self.assertEqual(result['status'], 'all_scenarios_passed')
            self.assertEqual(result['scenario_count'], 7)
            self.assertEqual(result['candidate_before'], result['candidate_after'])
            self.assertEqual(result['actual_guarded_script_sha256'], builder.NEW_SCRIPT_SHA)


if __name__ == '__main__':
    unittest.main()
