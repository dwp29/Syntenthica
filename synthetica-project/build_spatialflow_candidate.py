#!/usr/bin/env python3
"""Build a distinct, unsigned, HOLD-only ROM candidate with SpatialFlow as an ordinary app.

The input is locked candidate 03, itself derived from the verified original
port. Only /product/app/SpatialFlow/{SpatialFlow.apk} is added to a copy of
its ext4 product filesystem. No vendor/audio/security policy, boot, DTBO,
installer, OTA metadata or existing applications are intentionally changed.
All source ZIP members, partition extents, modified filesystem content, output
ZIP members and OTA offsets are checked. The recipe never touches a device and
does not claim boot, runtime compatibility, trusted signature, or safety.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

import audit_boot_first_installer as installer
import audit_vintf_candidate as vintf
import build_boot_candidate as boot
import build_guarded_candidate as guarded
import build_ota_metadata_candidate as ota
import compare_ext4_boot as ext4_guard
import feature_ext4
import preflight_spatialflow as pre
import scan_apk_packages
import verify_preservation as guard

OUTPUT_NAME = 'synthetica-feature-20261103-04-spatialflow.zip'
TEXT_SHA = '9ae0bd0b1e014fe3288adebb832ed5da6a1e0f12176c54aa03957cbe754a81fe'
PROTO_SHA = '5e653f522d0b854b314dff27bba0e77735b667bd06f0bdaacb2d9254500102c9'
CHUNK = 4 * 1024 * 1024
RESERVE_BYTES = 8 * 1024 * 1024

class FeatureBuildError(RuntimeError):
    pass


def source_specs(lock_path: Path, z: zipfile.ZipFile) -> tuple[dict, dict, bytes, bytes]:
    script = z.read(guarded.SCRIPT)
    if len(script) != 1569 or hashlib.sha256(script).hexdigest() != guarded.NEW_SCRIPT_SHA:
        raise FeatureBuildError('Pinned guarded installer differs from candidate 03')
    expected = guarded.expectations(lock_path, script)
    expected[ota.METADATA] = {'bytes': 412, 'sha256': TEXT_SHA}
    expected[ota.METADATA_PB] = {'bytes': 326, 'sha256': PROTO_SHA}
    infos = guarded.zip_members(z, expected)
    if z.comment or any(i.flag_bits for i in infos.values()):
        raise FeatureBuildError('Source ZIP comment or flags are unexpected')
    text, proto = z.read(ota.METADATA), z.read(ota.METADATA_PB)
    for name, data in ((ota.METADATA, text), (ota.METADATA_PB, proto)):
        spec = expected[name]
        if len(data) != spec['bytes'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise FeatureBuildError('Source OTA metadata differs from candidate 03')
    return expected, infos, text, proto


def check_source_members(z: zipfile.ZipFile, expected: dict, infos: dict) -> list[dict]:
    rows = []
    for name, info in infos.items():
        spec = expected[name]
        if info.is_dir():
            if not spec.get('directory') or info.file_size or info.compress_size:
                raise FeatureBuildError('Unexpected source directory member')
        else:
            rows.append(guarded.inspect_member(z, info, spec))
    return rows


def validate_space(metrics: dict, apk_size: int) -> None:
    free = metrics['free_blocks'] - metrics['reserved_blocks']
    if free < 0 or metrics['free_inodes'] < 2:
        raise FeatureBuildError('Product filesystem lacks free inodes or usable blocks')
    if free * metrics['block_size'] < apk_size + RESERVE_BYTES:
        raise FeatureBuildError('Product filesystem lacks sufficient non-reserved free space')


def package(source: Path, output: Path, source_infos: dict, replacement: Path, extent: dict,
            replacement_sha: str) -> dict:
    if output.exists() or output.is_symlink():
        raise FeatureBuildError('Output path already exists')
    super_result = None
    with source.open('rb') as source_file, zipfile.ZipFile(source_file) as zin, \
            zipfile.ZipFile(output, 'x', allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zout:
        zout.comment = zin.comment
        for info in sorted(source_infos.values(), key=lambda x: x.header_offset):
            if info.filename != 'super.img':
                ota.add_precompressed(zout, source_file, info)
                continue
            new_info = boot._new_zipinfo(info)
            with zin.open(info) as src, zout.open(new_info, 'w', force_zip64=True) as dst, replacement.open('rb') as new:
                super_result = boot._replace_system(src, dst, new,
                    {'begin': extent['start'], 'end': extent['end'], 'bytes': extent['bytes']},
                    pre.SUPER_SHA256, replacement_sha)
    if not super_result or super_result['bytes'] != vintf.SUPER_BYTES or super_result['sha256'] == pre.SUPER_SHA256:
        raise FeatureBuildError('Super replacement is absent, has wrong length, or is unchanged')
    with output.open('rb') as f:
        os.fsync(f.fileno())
    return super_result


def compare_compressed_others(source: Path, output: Path, old: dict, new: dict) -> int:
    count = 0
    with source.open('rb') as left, output.open('rb') as right:
        for name, a in old.items():
            if name == 'super.img':
                continue
            b = new[name]
            if (a.compress_type, a.compress_size) != (b.compress_type, b.compress_size):
                raise FeatureBuildError('Unchanged ZIP member compression differs: ' + name)
            left.seek(guarded._raw_data_offset(left, a))
            right.seek(guarded._raw_data_offset(right, b))
            remaining = a.compress_size
            while remaining:
                n = min(CHUNK, remaining)
                x, y = left.read(n), right.read(n)
                if len(x) != n or len(y) != n or x != y:
                    raise FeatureBuildError('Unchanged ZIP member compressed data differs: ' + name)
                remaining -= n
            count += 1
    return count


def compare_supers(source: Path, output: Path, windows: dict, new_product_sha: str,
                   expected_super_sha: str) -> dict:
    product = windows['product']
    pos = 0
    old_super, new_super = hashlib.sha256(), hashlib.sha256()
    hashes = {name: hashlib.sha256() for name in windows}
    counts = {name: 0 for name in windows}
    with zipfile.ZipFile(source) as za, zipfile.ZipFile(output) as zb, \
            za.open('super.img') as old, zb.open('super.img') as new:
        while True:
            a, b = old.read(CHUNK), new.read(CHUNK)
            if len(a) != len(b):
                raise FeatureBuildError('Super stream lengths differ')
            if not a:
                break
            end = pos + len(a)
            old_super.update(a); new_super.update(b)
            if pos < product['start']:
                n = min(len(a), product['start'] - pos)
                if a[:n] != b[:n]:
                    raise FeatureBuildError('Super bytes before product changed')
            if end > product['end']:
                n = max(0, product['end'] - pos)
                if a[n:] != b[n:]:
                    raise FeatureBuildError('Super bytes after product changed')
            for name, window in windows.items():
                lo, hi = max(pos, window['start']), min(end, window['end'])
                if lo < hi:
                    data = b[lo-pos:hi-pos]
                    hashes[name].update(data); counts[name] += len(data)
            pos = end
            if pos and pos % (2 * 1024**3) == 0:
                print(f'Independently compared {pos // 1024**3} / 8 GiB of super', flush=True)
    if (pos != vintf.SUPER_BYTES or old_super.hexdigest() != pre.SUPER_SHA256
            or new_super.hexdigest() != expected_super_sha):
        raise FeatureBuildError('Complete super readback hash or length mismatch')
    result = []
    for name, window in windows.items():
        expected = new_product_sha if name == 'product' else window['sha256']
        if counts[name] != window['bytes'] or hashes[name].hexdigest() != expected:
            raise FeatureBuildError('Logical partition readback mismatch: ' + name)
        result.append({'name': name, 'bytes': counts[name], 'sha256': hashes[name].hexdigest(),
                       'unchanged_from_candidate03': name != 'product'})
    return {'bytes_compared': pos, 'all_bytes_outside_product_identical': True,
            'old_and_new_super_zip_crc_checked': True, 'partitions': result}


def build(work: Path, output: Path, aapt: str, apksigner: str, zipalign: str) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise FeatureBuildError('Work directory must already exist and be empty')
    if output.name != OUTPUT_NAME or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FeatureBuildError('Output must be a new path with the fixed experimental build name')
    partial = output.with_name(output.name + '.partial')
    if partial.exists() or partial.is_symlink():
        raise FeatureBuildError('Partial output path already exists')
    lock_path = Path(__file__).with_name('original-baseline.lock.json')
    lock = json.loads(lock_path.read_text())
    apk = pre.download_app(work)
    apk_info = pre.inspect_apk(apk, aapt, apksigner, zipalign)
    source = pre.download_candidate(work)
    with zipfile.ZipFile(source) as z:
        expected, source_infos, old_text, old_proto = source_specs(lock_path, z)
        check_source_members(z, expected, source_infos)
    ota.verify_ota(source, old_text, old_proto)
    print('Candidate 03 members, CRCs and OTA offsets verified', flush=True)
    extents = pre.extract_extents(source, work, lock)
    partitions = {}
    for name, item in extents.items():
        path, window = item['path'], item['window']
        if pre.digest_file(path) != (window['bytes'], window['sha256']):
            raise FeatureBuildError('Extracted partition failed independent readback: ' + name)
        partitions[name] = pre.read_ext4_metrics(path)
    validate_space(partitions['product'], pre.APP_SIZE)
    scan_dir = work / 'package-scan'; scan_dir.mkdir()
    collision = scan_apk_packages.scan({n: v['path'] for n, v in extents.items()}, aapt, scan_dir, pre.APP_PACKAGE)
    print('Existing APK names scanned; no collision in the checked roots', flush=True)
    product_before = extents['product']['path']
    product_after = work / 'product-after.img'
    edit_dir = work / 'edit'; edit_dir.mkdir()
    filesystem = feature_ext4.edit(product_before, product_after, apk, edit_dir, pre.APP_SHA256)
    print('SpatialFlow added to product copy; filesystem preservation and fsck passed', flush=True)
    # Only disposable, independently verified copies owned by this run are removed.
    for name in ('system', 'system_ext', 'product'):
        extents[name]['path'].unlink()
    try:
        super_result = package(source, partial, source_infos, product_after, extents['product']['window'],
                               filesystem['after_sha256'])
        print('Experimental ZIP written; verifying independent readback', flush=True)
        output_expected = {name: dict(spec) for name, spec in expected.items()}
        output_expected['super.img']['sha256'] = super_result['sha256']
        with zipfile.ZipFile(partial) as z:
            output_infos = guarded.zip_members(z, output_expected)
            output_members = check_source_members(z, output_expected, output_infos)
        compressed_count = compare_compressed_others(source, partial, source_infos, output_infos)
        metadata = ota.verify_ota(partial, old_text, old_proto)
        specs = vintf.part_specs(lock)
        with zipfile.ZipFile(source) as z, z.open('super.img') as s:
            windows = vintf.extent_windows(s.read(vintf.lp.MAX_PREFIX), vintf.SUPER_BYTES, specs)
        super_check = compare_supers(source, partial, windows, filesystem['after_sha256'], super_result['sha256'])
        if pre.digest_file(source) != (pre.SOURCE_SIZE, pre.SOURCE_SHA256):
            raise FeatureBuildError('Source candidate changed during build')
        if pre.digest_file(apk) != (pre.APP_SIZE, pre.APP_SHA256):
            raise FeatureBuildError('Source application changed during build')
        size, sha = pre.digest_file(partial)
        if not 0 < size < guard.MAX_CANDIDATE_BYTES:
            raise FeatureBuildError('Output size is out of range')
        os.replace(partial, output)
        return {'schema': 'synthetica-spatialflow-rom-candidate-v1',
                'status': 'HOST_VERIFIED_DEVICE_UNTESTED_HOLD_DO_NOT_FLASH',
                'source': {'name': pre.SOURCE_NAME, 'bytes': pre.SOURCE_SIZE, 'sha256': pre.SOURCE_SHA256},
                'output': {'name': output.name, 'bytes': size, 'sha256': sha, 'signed_by_this_recipe': False},
                'apk': apk_info, 'package_collision_scan': collision, 'input_ext4': partitions,
                'filesystem_audit': filesystem, 'super': super_result, 'super_comparison': super_check,
                'output_members': output_members, 'all_other_compressed_members_identical': compressed_count,
                'ota_metadata': metadata, 'other_existing_apps_preserved': True,
                'limitations': ['SpatialFlow inclusion is not proof it installs, opens, plays audio, or supports 4GB RAM.',
                    'This does not repair previously reported partial VINTF/SELinux policy incompatibilities.',
                    'Recovery whole-file signature and external AVB/vbmeta trust are not validated.',
                    'No device/recovery test, flashing, data wipe, or firmware/security change was performed.',
                    'The APK release signature is valid but not independently authenticated against a previously trusted author key.',
                    'Private experimental build only; distribution rights for ROM and bundled dependencies remain unresolved.']}
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--aapt', required=True)
    parser.add_argument('--apksigner', required=True)
    parser.add_argument('--zipalign', required=True)
    args = parser.parse_args()
    try:
        result = build(args.work, args.output, args.aapt, args.apksigner, args.zipalign)
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except (FeatureBuildError, pre.PreflightError, vintf.VintfAuditError, guarded.GuardBuildError,
            guard.AuditError, ota.OtaBuildError, installer.AuditError, boot.BuildError,
            feature_ext4.FeatureImageError, ext4_guard.ComparisonError, scan_apk_packages.PackageScanError,
            OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {'schema': 'synthetica-spatialflow-rom-candidate-v1', 'status': 'BUILD_FAILED_HOLD',
                  'error': str(exc), 'device_modified': False}
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
