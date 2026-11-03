#!/usr/bin/env python3
"""Store only a checked, unsigned SpatialFlow candidate as a separate HOLD draft.

Split into raw parts below GitHub's asset limit, verify asset metadata, then
independently redownload and hash every part. Never overwrite a release, tag,
asset, original or older candidate. Does not publish or approve a flash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import build_spatialflow_candidate as builder
import preflight_spatialflow as pre
import verify_preservation as guard

PART_BYTES = 1_610_612_736
CHUNK = 4 * 1024 * 1024
BRANCH = 'arena/96cbd65a-syntenthica'
REPORT_NAME = 'BUILD-REPORT-SPATIALFLOW-04.json'
MANIFEST_NAME = 'MANIFEST-SPATIALFLOW-04.json'

class ReleaseError(RuntimeError):
    pass


def api(path: str) -> dict:
    return pre.gh_json(path)


def checked_report(report: dict, output: Path) -> tuple[int, str]:
    if (report.get('schema') != 'synthetica-spatialflow-rom-candidate-v1'
            or report.get('status') != 'HOST_VERIFIED_DEVICE_UNTESTED_HOLD_DO_NOT_FLASH'
            or report.get('source', {}).get('sha256') != pre.SOURCE_SHA256
            or report.get('apk', {}).get('sha256') != pre.APP_SHA256
            or report.get('filesystem_audit', {}).get('status') != 'only_nonprivileged_spatialflow_paths_added'
            or report.get('filesystem_audit', {}).get('e2fsck_read_only_exit') != 0
            or report.get('super_comparison', {}).get('all_bytes_outside_metadata_and_product_extents_identical') is not True
            or report.get('super_comparison', {}).get('all_nonproduct_logical_partitions_identical') is not True
            or report.get('isolated_lpdump', {}).get('status') != 'ISOLATED_THIRD_PARTY_LPDUMP_AGREES'
            or report.get('package_collision_scan', {}).get('collision_found_in_scanned_roots') is not False
            or report.get('ota_metadata', {}).get('legacy_and_protobuf_values_equal') is not True):
        raise ReleaseError('Build report does not meet release-preservation requirements')
    info = report.get('output', {})
    size, sha = info.get('bytes'), info.get('sha256')
    if (info.get('name') != builder.OUTPUT_NAME or output.name != builder.OUTPUT_NAME
            or type(size) is not int or not 0 < size < guard.MAX_CANDIDATE_BYTES
            or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha)
            or info.get('signed_by_this_recipe') is not False):
        raise ReleaseError('Build report output identity is invalid')
    if pre.digest_file(output) != (size, sha):
        raise ReleaseError('Output file differs from the verified build report')
    return size, sha


def create_draft(tag: str, commit: str) -> int:
    if not re.fullmatch(r'synthetica-feature-spatialflow-04-run-[0-9]+-[0-9]+', tag):
        raise ReleaseError('Unexpected experimental draft tag')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ReleaseError('Missing exact build revision')
    notes = ('HOLD / JANGAN FLASH. Unggahan eksperimental belum lengkap sampai manifest ada. '
             'Kandidat ini menambahkan SpatialFlow biasa dan memperbesar product 32 MiB dalam super; belum memperbaiki VINTF/policy, '
             'belum ditandatangani, belum diuji recovery/AVB/boot, dan belum disetujui untuk flash. '
             'Raw parts bukan ZIP terpisah. Jangan dipublikasikan untuk komunitas sebelum hak distribusi dan uji terpenuhi.\n'
             f'Revisi resep: {commit}. Basis: kandidat 03 terverifikasi dari ZIP asli diza.')
    payload = {'tag_name': tag, 'target_commitish': BRANCH,
               'name': 'Syntenthica 04 SpatialFlow — EKSPERIMENTAL / HOLD',
               'body': notes, 'draft': True, 'prerelease': True,
               'generate_release_notes': False}
    p = subprocess.run(['gh', 'api', '--method', 'POST', f'repos/{pre.REPO}/releases', '--input', '-'],
                       input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise ReleaseError('Could not create a new separate unpublished draft; existing releases were not overwritten')
    try:
        release = json.loads(p.stdout)
    except ValueError as exc:
        raise ReleaseError('Draft creation returned invalid JSON') from exc
    number = release.get('id')
    if (type(number) is not int or release.get('tag_name') != tag or release.get('draft') is not True
            or release.get('target_commitish') != BRANCH or release.get('assets') != []):
        raise ReleaseError('New release was not the expected empty unpublished draft')
    return number


def draft(number: int, tag: str) -> dict:
    value = api(f'repos/{pre.REPO}/releases/{number}')
    if (value.get('id') != number or value.get('tag_name') != tag
            or value.get('draft') is not True or value.get('target_commitish') != BRANCH
            or not isinstance(value.get('assets'), list)):
        raise ReleaseError('Experimental draft changed or was published')
    return value


def upload(number: int, tag: str, path: Path, sha: str) -> None:
    release = draft(number, tag)
    if any(a.get('name') == path.name for a in release['assets']):
        raise ReleaseError('An asset with this name already exists; refusing to overwrite')
    size = path.stat().st_size
    if pre.digest_file(path) != (size, sha):
        raise ReleaseError('Upload source changed before transfer')
    pre.command(['gh', 'release', 'upload', tag, str(path), '--repo', pre.REPO])
    for attempt in range(4):
        release = draft(number, tag)
        matches = [a for a in release['assets'] if a.get('name') == path.name]
        if len(matches) == 1:
            asset = matches[0]
            if (asset.get('state') == 'uploaded' and asset.get('size') == size
                    and asset.get('digest') == 'sha256:' + sha):
                return
        if attempt < 3:
            time.sleep(2)
    raise ReleaseError('Uploaded asset metadata did not match its SHA-256 and size')


def split_and_upload(number: int, tag: str, output: Path, work: Path, size: int, expected: str) -> list[dict]:
    rows = []
    combined = hashlib.sha256()
    total = 0
    with guard._open_regular(output)[0] as stream:
        before = guard._snapshot(os.fstat(stream.fileno()))
        for index in range(1, (size + PART_BYTES - 1) // PART_BYTES + 1):
            path = work / (output.name + f'.{index:03d}')
            if path.exists() or path.is_symlink():
                raise ReleaseError('Part path already exists')
            h, count = hashlib.sha256(), 0
            with path.open('xb') as out:
                while count < PART_BYTES and total < size:
                    data = stream.read(min(CHUNK, PART_BYTES - count, size - total))
                    if not data:
                        raise ReleaseError('Build file ended while splitting')
                    out.write(data); h.update(data); combined.update(data)
                    count += len(data); total += len(data)
                out.flush(); os.fsync(out.fileno())
            row = {'number': index, 'name': path.name, 'bytes': count, 'sha256': h.hexdigest()}
            upload(number, tag, path, row['sha256'])
            path.unlink()
            rows.append(row)
            print(f'Uploaded and checked draft part {index}', flush=True)
        if stream.read(1):
            raise ReleaseError('Build file grew during splitting')
        guard._check_unchanged(output, stream, before)
    if total != size or combined.hexdigest() != expected:
        raise ReleaseError('Split parts did not reproduce complete build SHA-256')
    return rows


def redownload(number: int, tag: str, rows: list[dict], work: Path, expected_sha: str) -> None:
    before = draft(number, tag)
    expected_names = {row['name'] for row in rows}
    if {x.get('name') for x in before['assets']} != expected_names:
        raise ReleaseError('Unexpected or missing draft assets before independent download')
    stable = {a['name']: (a['id'], a['size'], a['digest']) for a in before['assets']}
    combined = hashlib.sha256()
    for row in rows:
        path = work / row['name']
        if path.exists() or path.is_symlink():
            raise ReleaseError('Redownload destination already exists')
        pre.command(['gh', 'release', 'download', tag, '--repo', pre.REPO,
                     '--pattern', row['name'], '--dir', str(work)])
        with guard._open_regular(path)[0] as f:
            snap = guard._snapshot(os.fstat(f.fileno()))
            h, count = hashlib.sha256(), 0
            while data := f.read(CHUNK):
                h.update(data); combined.update(data); count += len(data)
            guard._check_unchanged(path, f, snap)
        if count != row['bytes'] or h.hexdigest() != row['sha256']:
            raise ReleaseError('Independently downloaded part failed its SHA-256')
        path.unlink()
        print(f'Independently downloaded and verified part {row["number"]}', flush=True)
    after = draft(number, tag)
    if ({a['name']: (a['id'], a['size'], a['digest']) for a in after['assets']} != stable
            or combined.hexdigest() != expected_sha):
        raise ReleaseError('Draft assets changed or combined redownload hash did not match')


def run(report_path: Path, output: Path, work: Path, tag: str, commit: str) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise ReleaseError('Transfer work directory must be empty')
    if not report_path.is_file() or report_path.is_symlink() or report_path.stat().st_size > 1_000_000:
        raise ReleaseError('Build report must be a bounded ordinary file')
    report = json.loads(report_path.read_text())
    size, sha = checked_report(report, output)
    if not 1 <= (size + PART_BYTES - 1) // PART_BYTES <= 10:
        raise ReleaseError('Unexpected part count')
    number = create_draft(tag, commit)
    print(f'Created separate unpublished HOLD draft {number}', flush=True)
    rows = split_and_upload(number, tag, output, work, size, sha)
    redownload(number, tag, rows, work, sha)
    report_copy = work / REPORT_NAME
    report_copy.write_bytes(report_path.read_bytes())
    report_size, report_sha = pre.digest_file(report_copy)
    upload(number, tag, report_copy, report_sha)
    manifest = {'schema': 'synthetica-spatialflow-draft-parts-v1',
                'status': 'UNPUBLISHED_HOLD_DO_NOT_FLASH', 'release_id': number, 'tag': tag,
                'build_commit': commit, 'file_name': output.name, 'file_bytes': size, 'file_sha256': sha,
                'part_bytes': PART_BYTES, 'parts': rows, 'all_parts_independently_redownloaded': True,
                'build_report': {'name': REPORT_NAME, 'bytes': report_size, 'sha256': report_sha},
                'source_candidate03_sha256': pre.SOURCE_SHA256, 'app_sha256': pre.APP_SHA256,
                'signed_by_this_recipe': False, 'device_or_recovery_tested': False,
                'warning': 'Experimental private draft only. Raw parts are not individual flashable ZIPs. Do not flash.'}
    manifest_path = work / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    manifest_size, manifest_sha = pre.digest_file(manifest_path)
    upload(number, tag, manifest_path, manifest_sha)
    assets = draft(number, tag)['assets']
    if {a.get('name') for a in assets} != {x['name'] for x in rows} | {REPORT_NAME, MANIFEST_NAME}:
        raise ReleaseError('Final draft has unexpected or missing assets')
    if pre.digest_file(output) != (size, sha):
        raise ReleaseError('Output changed during transfer')
    return {**manifest, 'manifest_asset': {'bytes': manifest_size, 'sha256': manifest_sha},
            'draft_url': f'https://github.com/{pre.REPO}/releases/edit/{number}'}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--tag', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--result', required=True, type=Path)
    args = p.parse_args()
    try:
        result = run(args.report, args.output, args.work, args.tag, args.commit)
        args.result.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except (ReleaseError, pre.PreflightError, guard.AuditError, OSError, ValueError) as exc:
        result = {'schema': 'synthetica-spatialflow-draft-parts-v1', 'status': 'TRANSFER_INCOMPLETE_HOLD',
                  'error': str(exc), 'device_modified': False}
        args.result.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
