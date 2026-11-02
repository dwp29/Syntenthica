#!/usr/bin/env python3
"""Reconstruct candidate 02 and transfer candidate 03 to its separate draft.

Only GitHub Actions on the approved branch may use this tool. Candidate 01
and 02 draft assets are read-only; no existing assets are ever overwritten or
deleted. This never publishes a release, signs an OTA, or touches a device.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

import build_ota_metadata_candidate as builder
import build_guarded_candidate as previous
import github_guarded_release as old_transfer
import github_guarded_report_relay as old_relay
import verify_preservation as guard

REPO = 'dwp29/Syntenthica'
BRANCH = 'arena/96cbd65a-syntenthica'
SOURCE_RELEASE_ID = 431299268
OLDER_RELEASE_ID = 431195621
RELEASE_ID = 431662583
TAG = 'synthetica-boot-first-20261102-03-ota-metadata-draft'
FILE_NAME = builder.OUTPUT_NAME
REPORT_NAME = 'BUILD-REPORT-BOOT-FIRST-03.json'
MANIFEST_NAME = 'MANIFEST-GITHUB-BOOT-FIRST-03.json'
PART_BYTES = 1536 * 1024 * 1024
CHUNK = 4 * 1024 * 1024
SOURCE_PARTS = (
    (1_610_612_736, '3d19137f7e18c189e9574ab9ef8b5f2c514516b21ac62f442248c8a0ef91e125'),
    (1_610_612_736, '32b7dae474f55dfcf4a2866b8470eba8559da424cc75f4139484ac59f568ab97'),
    (1_492_564_567, 'ebd7aaf261e3081d237a26f73b2debde35a306b4cac0dfd5fb2c95804f9b23d4'),
)


class TransferError(Exception):
    pass


def validate_context() -> None:
    if (os.environ.get('GITHUB_REPOSITORY') != REPO
            or os.environ.get('GITHUB_REF') != f'refs/heads/{BRANCH}'
            or not os.environ.get('GH_TOKEN')):
        raise TransferError('This transfer requires the approved repository/branch Actions context')


def read_release(number: int = RELEASE_ID) -> dict:
    if type(number) is not int or number != RELEASE_ID or number in (SOURCE_RELEASE_ID, OLDER_RELEASE_ID):
        raise TransferError('Only the distinct 03 draft is allowed as an upload target')
    release = old_transfer.gh_json(f'repos/{REPO}/releases/{number}')
    if (release.get('id') != RELEASE_ID or release.get('draft') is not True
            or release.get('tag_name') != TAG or release.get('target_commitish') != BRANCH
            or not isinstance(release.get('assets'), list)):
        raise TransferError('03 release is not the expected separate unpublished draft')
    allowed = {f'{FILE_NAME}.{i:03d}' for i in range(1, 4)} | {REPORT_NAME, MANIFEST_NAME}
    names = [a.get('name') for a in release['assets']]
    if len(names) != len(set(names)) or any(name not in allowed for name in names):
        raise TransferError('03 draft has duplicate or unexpected assets; nothing was overwritten')
    return release


def old_inventory() -> dict:
    release = old_transfer.read_release(SOURCE_RELEASE_ID)
    assets = old_relay.metadata_assets(release)
    for index, (size, expected) in enumerate(SOURCE_PARTS, 1):
        name = f'{builder.BASE_NAME}.{index:03d}'
        if not old_transfer.asset_matches(assets[name], name, size, expected):
            raise TransferError(f'Candidate 02 source part metadata changed: {name}')
    return old_relay.stable_inventory(assets)


def download_source(destination: Path, work: Path) -> None:
    if destination.name != builder.BASE_NAME or destination.exists() or destination.is_symlink():
        raise TransferError('Source reconstruction must use a new candidate 02 path')
    if not work.is_dir() or any(work.iterdir()):
        raise TransferError('Source download work directory must be empty')
    before = old_inventory()
    combined = hashlib.sha256()
    total = 0
    with destination.open('xb') as out:
        for index, (size, expected) in enumerate(SOURCE_PARTS, 1):
            name = f'{builder.BASE_NAME}.{index:03d}'
            part = old_relay.download(name, work)
            h = hashlib.sha256()
            count = 0
            with guard._open_regular(part)[0] as stream:
                snapshot = guard._snapshot(os.fstat(stream.fileno()))
                while data := stream.read(CHUNK):
                    count += len(data)
                    if count > size:
                        raise TransferError('Source part exceeds pinned size')
                    h.update(data)
                    combined.update(data)
                    out.write(data)
                guard._check_unchanged(part, stream, snapshot)
            if count != size or h.hexdigest() != expected:
                raise TransferError(f'Source part hash or size mismatch: {name}')
            total += count
            part.unlink()  # Only this runner's verified temporary download.
            print(f'Candidate 02 source part {index}/3 verified.', flush=True)
        out.flush()
        os.fsync(out.fileno())
    if total != builder.BASE_BYTES or combined.hexdigest() != builder.BASE_SHA:
        raise TransferError('Reconstructed candidate 02 does not match its pinned full SHA-256')
    if old_inventory() != before:
        raise TransferError('Candidate 02 draft assets changed during source reconstruction')
    print('Candidate 02 reconstructed and its complete SHA-256 verified.', flush=True)


def validate_report(report: dict, source: Path, candidate: Path, lock_path: Path) -> None:
    if (report.get('schema') != 'synthetica-boot-first-ota-metadata-repair-v1'
            or report.get('status') != 'host_verified_not_device_tested_not_flash_approved'
            or report.get('source', {}).get('sha256') != builder.BASE_SHA
            or report.get('source', {}).get('bytes') != builder.BASE_BYTES
            or set(report.get('changed_members', [])) != builder.CHANGED
            or any(report.get(name) is not True for name in (
                'source_all_member_hashes_and_crc_verified', 'source_unchanged_during_build',
                'unchanged_member_uncompressed_content_verified',
                'unchanged_member_compressed_streams_identical'))):
        raise TransferError('Candidate build report lacks the required preservation guarantees')
    output = report.get('output', {})
    size, digest = output.get('bytes'), output.get('sha256')
    if (output.get('name') != FILE_NAME or type(size) is not int or not 0 < size <= guard.MAX_CANDIDATE_BYTES
            or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
            or output.get('signed_by_this_recipe') is not False):
        raise TransferError('Candidate output identity or unsigned status is invalid')
    if source.name != builder.BASE_NAME or candidate.name != FILE_NAME:
        raise TransferError('Input or output basename is not the pinned candidate')
    previous.file_identity(source, builder.BASE_BYTES, builder.BASE_SHA)
    old_transfer.verify_regular_digest(candidate, size, digest)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(candidate) as new:
        script = old.read(previous.SCRIPT)
        if hashlib.sha256(script).hexdigest() != previous.NEW_SCRIPT_SHA:
            raise TransferError('Unexpected candidate 02 installer')
        expected = previous.expectations(lock_path, script)
        old_text, old_pb = old.read(builder.METADATA), old.read(builder.METADATA_PB)
        for name in builder.CHANGED:
            data = new.read(name)
            expected[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        previous.zip_members(new, expected)
    rows = report.get('output_members')
    expected_files = {name: spec for name, spec in expected.items() if not spec.get('directory')}
    if not isinstance(rows, list) or len(rows) != len(expected_files):
        raise TransferError('Build report member list is incomplete')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('name') not in expected_files or row['name'] in seen:
            raise TransferError('Build report contains an unexpected or duplicate member')
        name = row['name']
        if (row.get('bytes') != expected_files[name]['bytes'] or row.get('sha256') != expected_files[name]['sha256']
                or row.get('zip_crc_verified_at_eof') is not True):
            raise TransferError(f'Build report member identity is incorrect: {name}')
        seen.add(name)
    if seen != set(expected_files):
        raise TransferError('Build report is missing members')
    verification = builder.verify_ota(candidate, old_text, old_pb)
    if verification != report.get('ota_metadata_verification'):
        raise TransferError('Independent OTA offset and protobuf verification differs from report')
    if (not verification['property_files'] or verification['zip_comment_bytes'] != 0
            or any(not row['stored'] or not row['direct_range_matches'] for row in verification['property_files'])):
        raise TransferError('Metadata range bytes or unsigned ZIP comment are invalid')


def asset_matches(asset: dict, name: str, size: int, digest: str) -> bool:
    return old_transfer.asset_matches(asset, name, size, digest)


def upload_verified(path: Path, digest: str) -> None:
    size = path.stat().st_size
    existing = [x for x in read_release()['assets'] if x.get('name') == path.name]
    if existing:
        if len(existing) != 1 or not asset_matches(existing[0], path.name, size, digest):
            raise TransferError(f'Conflicting existing 03 asset is never overwritten: {path.name}')
        print(f'Existing asset already matches: {path.name}', flush=True)
        return
    print(f'Uploading 03 draft asset: {path.name} ({size} bytes)', flush=True)
    result = subprocess.run(['gh', 'release', 'upload', TAG, str(path), '--repo', REPO], check=False)
    if result.returncode:
        raise TransferError(f'Upload failed: {path.name}')
    for attempt in range(4):
        matches = [a for a in read_release()['assets'] if a.get('name') == path.name]
        if len(matches) == 1 and asset_matches(matches[0], path.name, size, digest):
            print(f'GitHub confirms size and SHA-256: {path.name}', flush=True)
            return
        if attempt < 3:
            time.sleep(2)
    raise TransferError(f'GitHub did not confirm the uploaded asset: {path.name}')


def split_upload(candidate: Path, work: Path, size: int, expected_sha: str) -> list[dict]:
    if (size + PART_BYTES - 1) // PART_BYTES != 3:
        raise TransferError('Expected exactly three candidate parts')
    snapshot = old_transfer.verify_regular_digest(candidate, size, expected_sha)
    rows, total = [], 0
    combined = hashlib.sha256()
    with guard._open_regular(candidate)[0] as stream:
        if guard._snapshot(os.fstat(stream.fileno())) != snapshot:
            raise TransferError('Candidate changed between identity and splitting')
        for index in range(1, 4):
            name = f'{FILE_NAME}.{index:03d}'
            path = work / name
            single = hashlib.sha256()
            count = 0
            with path.open('xb') as out:
                while count < PART_BYTES and total < size:
                    data = stream.read(min(CHUNK, PART_BYTES - count, size - total))
                    if not data:
                        raise TransferError('Candidate ended early while splitting')
                    out.write(data)
                    single.update(data)
                    combined.update(data)
                    count += len(data)
                    total += len(data)
                out.flush()
                os.fsync(out.fileno())
            row = {'number': index, 'name': name, 'bytes': count, 'sha256': single.hexdigest()}
            upload_verified(path, row['sha256'])
            path.unlink()
            rows.append(row)
        if stream.read(1):
            raise TransferError('Candidate grew during splitting')
        guard._check_unchanged(candidate, stream, snapshot)
    if total != size or combined.hexdigest() != expected_sha:
        raise TransferError('Combined uploaded-part stream differs from full candidate SHA-256')
    return rows


def verify_assets(rows: list[dict]) -> None:
    assets = read_release()['assets']
    if len(assets) != len(rows) or {a.get('name') for a in assets} != {r['name'] for r in rows}:
        raise TransferError('03 draft does not contain exactly the expected assets')
    for row in rows:
        asset = next(a for a in assets if a.get('name') == row['name'])
        if not asset_matches(asset, row['name'], row['bytes'], row['sha256']):
            raise TransferError(f'03 draft asset identity mismatch: {row["name"]}')


def redownload_parts(rows: list[dict], work: Path, full_size: int, full_sha: str) -> None:
    combined, total = hashlib.sha256(), 0
    before = old_relay.stable_inventory({a['name']: a for a in read_release()['assets']})
    for row in rows:
        path = work / row['name']
        if path.exists() or path.is_symlink():
            raise TransferError('Refusing to overwrite a verification download')
        result = subprocess.run(['gh', 'release', 'download', TAG, '--repo', REPO,
                                 '--pattern', row['name'], '--dir', str(work)], check=False)
        if result.returncode:
            raise TransferError('Independent part redownload failed')
        single, count = hashlib.sha256(), 0
        with guard._open_regular(path)[0] as f:
            snapshot = guard._snapshot(os.fstat(f.fileno()))
            while data := f.read(CHUNK):
                count += len(data)
                single.update(data)
                combined.update(data)
            guard._check_unchanged(path, f, snapshot)
        if count != row['bytes'] or single.hexdigest() != row['sha256']:
            raise TransferError('Redownloaded candidate part differs from uploaded hash')
        path.unlink()
        total += count
        print(f'Redownload verified: {row["name"]}', flush=True)
    if total != full_size or combined.hexdigest() != full_sha:
        raise TransferError('Redownloaded combined candidate SHA-256 differs')
    after = old_relay.stable_inventory({a['name']: a for a in read_release()['assets']})
    if before != after:
        raise TransferError('03 draft assets changed during independent redownload')


def finish_notes(size: int, digest: str) -> None:
    read_release()
    notes = (
        'DRAF 03 SELESAI — HOLD / JANGAN FLASH.\n\n'
        'Ini kandidat perbaikan packaging OTA, bukan ROM yang terbukti dapat boot. '
        'Metadata teks dan protobuf memiliki offset aktual dan disimpan tanpa kompresi; '
        'semua image, installer dan anggota lain identik dengan kandidat 02.\n\n'
        'Snapshot VINTF parsial masih menunjukkan inkompatibilitas. ZIP tidak ditandatangani '
        'oleh resep ini; kepercayaan signature, AVB, recovery dan boot perangkat belum terbukti. '
        'Tidak ada tindakan flash, wipe, atau perubahan keamanan yang dilakukan.\n\n'
        'Tiga file bernomor adalah potongan mentah dari satu ZIP, bukan file flash terpisah. '
        f'Ukuran gabungan {size} byte; SHA-256 {digest}. '
        'Rincian, hash tiap bagian dan laporan pemeriksaan ada di manifest dan laporan.\n'
    )
    proc = subprocess.run(['gh', 'api', '--method', 'PATCH', f'repos/{REPO}/releases/{RELEASE_ID}',
                           '-f', f'body={notes}', '-f', f'tag_name={TAG}',
                           '-f', f'target_commitish={BRANCH}'], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode or read_release().get('body') != notes:
        raise TransferError('Could not safely save and verify 03 draft notes')


def publish(source: Path, candidate: Path, report_path: Path, unzip_log: Path,
            work: Path, lock_path: Path) -> dict:
    validate_context()
    read_release()
    if report_path.name != REPORT_NAME or not work.is_dir() or any(work.iterdir()):
        raise TransferError('Report name or empty disposable work directory is invalid')
    if report_path.stat().st_size > 1024 * 1024 or unzip_log.stat().st_size > 1024 * 1024:
        raise TransferError('Report or unzip log exceeds bounded size')
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    validate_report(report, source, candidate, lock_path)
    if 'No errors detected in compressed data of ' not in unzip_log.read_text(encoding='utf-8'):
        raise TransferError('Independent unzip -t verification did not pass')
    output = report['output']
    rows = split_upload(candidate, work, output['bytes'], output['sha256'])
    report_row = {'name': REPORT_NAME, 'bytes': len(report_bytes), 'sha256': hashlib.sha256(report_bytes).hexdigest()}
    upload_verified(report_path, report_row['sha256'])
    manifest = {
        'schema': 'synthetica-ota-metadata-github-parts-v1',
        'status': 'HOLD_NOT_FLASH_APPROVED', 'file_name': FILE_NAME,
        'file_bytes': output['bytes'], 'file_sha256': output['sha256'],
        'part_count': 3, 'part_bytes': PART_BYTES, 'parts': rows,
        'build_report': report_row, 'previous_candidate_sha256': builder.BASE_SHA,
        'recipe_commit': os.environ.get('GITHUB_SHA', ''),
        'host_unzip_test_passed': True, 'device_or_recovery_tested': False,
        'signed_by_this_recipe': False,
        'warning': 'HOLD: packaging-only repair, unsigned, VINTF/AVB/device boot unresolved. Raw parts are not flashable.',
    }
    path = work / MANIFEST_NAME
    with path.open('x', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')
    manifest_row = {'name': MANIFEST_NAME, 'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    upload_verified(path, manifest_row['sha256'])
    path.unlink()
    all_rows = rows + [report_row, manifest_row]
    verify_assets(all_rows)
    redownload_parts(rows, work, output['bytes'], output['sha256'])
    verify_assets(all_rows)
    finish_notes(output['bytes'], output['sha256'])
    verify_assets(all_rows)
    print('03 draft: all five assets and independent part redownload verified; HOLD.', flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    fetch = sub.add_parser('fetch-source')
    fetch.add_argument('--destination', type=Path, required=True)
    fetch.add_argument('--work', type=Path, required=True)
    upload = sub.add_parser('upload')
    for arg in ('source', 'candidate', 'report', 'unzip-log', 'work'):
        upload.add_argument('--' + arg, type=Path, required=True)
    upload.add_argument('--lock', type=Path, default=Path(__file__).with_name('original-baseline.lock.json'))
    upload.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    validate_context()
    if args.operation == 'fetch-source':
        read_release()
        download_source(args.destination, args.work)
    else:
        if args.result.exists() or args.result.is_symlink():
            raise TransferError('Result summary path already exists')
        manifest = publish(args.source, args.candidate, args.report, args.unzip_log, args.work, args.lock)
        with args.result.open('x', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write('\n')


if __name__ == '__main__':
    try:
        main()
    except (TransferError, old_transfer.TransferError, old_relay.RelayError,
            builder.OtaBuildError, previous.GuardBuildError, guard.AuditError,
            OSError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(f'OTA draft transfer refused: {exc}')
