import contextlib
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
sys.path.insert(0, str(ROOT / 'tests'))
import build_ota_metadata_candidate as ota
import github_ota_metadata_release as transfer
from test_build_ota_metadata_candidate import configured, file_sha, fixture


def valid_release(assets=None):
    return {'id': transfer.RELEASE_ID, 'draft': True, 'tag_name': transfer.TAG,
            'target_commitish': transfer.BRANCH, 'assets': assets or []}


def asset(name, data):
    return {'name': name, 'state': 'uploaded', 'size': len(data),
            'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}


class OtaTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetica-ota-transfer-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_only_03_draft_is_writable(self):
        with mock.patch.object(transfer.old_transfer, 'gh_json', return_value=valid_release()) as read:
            self.assertEqual(transfer.read_release()['id'], transfer.RELEASE_ID)
            for invalid in (transfer.SOURCE_RELEASE_ID, transfer.OLDER_RELEASE_ID, 0, True, transfer.RELEASE_ID + 1):
                with self.subTest(invalid=invalid), self.assertRaises(transfer.TransferError):
                    transfer.read_release(invalid)
            self.assertEqual(read.call_count, 1)

    def test_must_be_draft_correct_tag_and_branch(self):
        for changes in ({'draft': False}, {'tag_name': 'other'}, {'target_commitish': 'main'}, {'id': 1}):
            release = valid_release()
            release.update(changes)
            with self.subTest(changes=changes), \
                 mock.patch.object(transfer.old_transfer, 'gh_json', return_value=release), \
                 self.assertRaises(transfer.TransferError):
                transfer.read_release()

    def test_unexpected_or_duplicate_assets_fail_closed(self):
        for assets in ([asset('unrelated', b'x')],
                       [asset(transfer.REPORT_NAME, b'x'), asset(transfer.REPORT_NAME, b'x')]):
            with self.subTest(assets=assets), \
                 mock.patch.object(transfer.old_transfer, 'gh_json', return_value=valid_release(assets)), \
                 self.assertRaises(transfer.TransferError):
                transfer.read_release()

    def test_context_must_match_exact_branch_repo_and_token(self):
        good = {'GITHUB_REPOSITORY': transfer.REPO, 'GITHUB_REF': 'refs/heads/' + transfer.BRANCH,
                'GH_TOKEN': 'not-a-real-token'}
        with mock.patch.dict(os.environ, good, clear=True):
            transfer.validate_context()
        for key, value in (('GITHUB_REPOSITORY', 'other/repo'), ('GITHUB_REF', 'refs/heads/main'), ('GH_TOKEN', '')):
            bad = dict(good)
            bad[key] = value
            with self.subTest(key=key), mock.patch.dict(os.environ, bad, clear=True), self.assertRaises(transfer.TransferError):
                transfer.validate_context()

    def test_conflicting_existing_asset_is_not_uploaded_or_deleted(self):
        path = self.dir / transfer.REPORT_NAME
        path.write_bytes(b'new')
        with mock.patch.object(transfer, 'read_release', return_value=valid_release([asset(path.name, b'old')])), \
             mock.patch.object(transfer.subprocess, 'run') as run:
            with self.assertRaises(transfer.TransferError):
                transfer.upload_verified(path, hashlib.sha256(b'new').hexdigest())
            run.assert_not_called()
        self.assertEqual(path.read_bytes(), b'new')

    def test_matching_existing_asset_is_reused_without_upload(self):
        path = self.dir / transfer.REPORT_NAME
        path.write_bytes(b'matches')
        with mock.patch.object(transfer, 'read_release', return_value=valid_release([asset(path.name, b'matches')])), \
             mock.patch.object(transfer.subprocess, 'run') as run:
            transfer.upload_verified(path, hashlib.sha256(b'matches').hexdigest())
            run.assert_not_called()

    def test_reconstructs_only_hash_locked_parts_in_order(self):
        contents = [b'first', b'second', b'third']
        specs = tuple((len(part), hashlib.sha256(part).hexdigest()) for part in contents)
        full = b''.join(contents)
        destination = self.dir / ota.BASE_NAME
        work = self.dir / 'work'
        work.mkdir()
        def download(name, folder):
            index = int(name[-3:]) - 1
            path = folder / name
            path.write_bytes(contents[index])
            return path
        with mock.patch.object(transfer, 'SOURCE_PARTS', specs), \
             mock.patch.object(ota, 'BASE_BYTES', len(full)), \
             mock.patch.object(ota, 'BASE_SHA', hashlib.sha256(full).hexdigest()), \
             mock.patch.object(transfer, 'old_inventory', return_value={'immutable': 'yes'}), \
             mock.patch.object(transfer.old_relay, 'download', side_effect=download):
            transfer.download_source(destination, work)
        self.assertEqual(destination.read_bytes(), full)
        self.assertEqual(list(work.iterdir()), [])

    def test_mismatching_source_part_stops_reconstruction(self):
        contents = [b'first', b'second', b'third']
        specs = tuple((len(part), '0' * 64) for part in contents)
        destination = self.dir / ota.BASE_NAME
        work = self.dir / 'work'
        work.mkdir()
        def download(name, folder):
            path = folder / name
            path.write_bytes(contents[int(name[-3:]) - 1])
            return path
        with mock.patch.object(transfer, 'SOURCE_PARTS', specs), \
             mock.patch.object(transfer, 'old_inventory', return_value={}), \
             mock.patch.object(transfer.old_relay, 'download', side_effect=download):
            with self.assertRaises(transfer.TransferError):
                transfer.download_source(destination, work)

    def test_report_validation_rechecks_ota_and_all_member_identities(self):
        source = self.dir / ota.BASE_NAME
        candidate = self.dir / transfer.FILE_NAME
        specs, contents = fixture(source)
        with configured(source, specs, contents[ota.previous.SCRIPT]):
            report = ota.build(source, candidate, self.dir / 'lock')
            transfer.validate_report(report, source, candidate, self.dir / 'lock')
            bad = dict(report)
            bad['source_unchanged_during_build'] = False
            with self.assertRaises(transfer.TransferError):
                transfer.validate_report(bad, source, candidate, self.dir / 'lock')
            bad = dict(report)
            bad['output_members'] = [dict(r) for r in report['output_members']]
            bad['output_members'][0]['sha256'] = '0' * 64
            with self.assertRaises(transfer.TransferError):
                transfer.validate_report(bad, source, candidate, self.dir / 'lock')
        self.assertEqual(file_sha(source), report['source']['sha256'])

    def test_part_asset_set_must_be_exact(self):
        row = {'name': transfer.REPORT_NAME, 'bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}
        with mock.patch.object(transfer, 'read_release', return_value=valid_release([asset(transfer.REPORT_NAME, b'x')])):
            transfer.verify_assets([row])
        with mock.patch.object(transfer, 'read_release', return_value=valid_release([])):
            with self.assertRaises(transfer.TransferError):
                transfer.verify_assets([row])


if __name__ == '__main__':
    unittest.main()
