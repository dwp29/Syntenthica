#!/usr/bin/env python3
"""Read-only preflight for a separate, non-privileged SpatialFlow ROM candidate.

Downloads byte-locked existing draft 03 and upstream's arm64 release onto a
throwaway host, verifies both, and examines existing ext4 images without
mounting or executing device code. Does not edit, package, sign or flash a ROM.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

import audit_vintf_candidate as vintf
import verify_preservation as guard

REPO = 'dwp29/Syntenthica'
RELEASE_ID = 431662583
RELEASE_TAG = 'synthetica-boot-first-20261102-03-ota-metadata-draft'
SOURCE_NAME = 'synthetica-boot-first-20261102-03-ota-metadata.zip'
SOURCE_SIZE = 4_713_790_282
SOURCE_SHA256 = 'bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425'
PARTS = (
    (702335311, 1_610_612_736, 'f9455edf98db92e327a46f252771afaaa9c71007779e4906b13042e9ac0c4bc3'),
    (702339193, 1_610_612_736, 'ecd0b4fd69b40c6e66fb602dd3a6c830cfafc5d9f48294de4ce8fc45874033d1'),
    (702343142, 1_492_564_810, 'f3b64562251c0711446840ed39cab448a9af57ed4b076527fd93ad317664431e'),
)
APP_REPO = 'MythicalSHUB/SpatialFlow'
APP_TAG = 'v1.8.2'
APP_COMMIT = '8a40906d074ab95b2bfa32481bfae140dfdfcbed'
APP_ID = 653997616
APP_NAME = 'app-arm64-v8a-release.apk'
APP_SIZE = 45_521_038
APP_SHA256 = 'a3c5349073f9819764f185022867a9d47c58347d9c34573423e6397f33f9233d'
APP_PACKAGE = 'com.codetrio.spatialflow'
SUPER_SHA256 = '3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673'
CHUNK = 4 * 1024 * 1024

class PreflightError(RuntimeError):
    pass


def command(args: list[str], *, limit: int = 4 * 1024 * 1024) -> str:
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightError(f'Could not run {Path(args[0]).name}: {type(exc).__name__}') from exc
    if p.returncode:
        # GitHub may print signed asset URLs; never emit those or the token.
        text = p.stderr.decode('utf-8', 'replace')[:1200]
        text = re.sub(r'https?://[^\s\"\']+', '[URL redacted]', text)
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if token:
            text = text.replace(token, '[token redacted]')
        operation = ' '.join(args[:3])
        raise PreflightError(f'{operation} failed with exit {p.returncode}: {text[:500]}')
    if len(p.stdout) > limit:
        raise PreflightError(f'{Path(args[0]).name} output exceeded the bound')
    return p.stdout.decode('utf-8', 'replace')


def gh_json(path: str) -> dict:
    try:
        data = json.loads(command(['gh', 'api', path]))
    except (ValueError, TypeError) as exc:
        raise PreflightError('Invalid GitHub API JSON') from exc
    if not isinstance(data, dict):
        raise PreflightError('Unexpected GitHub API response')
    return data


def asset_snapshot(release: dict, expected: list[tuple[int, str, int, str]], *, draft: bool) -> tuple:
    if release.get('draft') is not draft or not isinstance(release.get('assets'), list):
        raise PreflightError('Release status or assets are unexpected')
    result = []
    for asset_id, name, size, sha in expected:
        matches = [a for a in release['assets'] if a.get('name') == name]
        if len(matches) != 1:
            raise PreflightError('Release asset is missing or duplicated: ' + name)
        item = matches[0]
        if (item.get('id') != asset_id or item.get('size') != size
                or item.get('digest') != 'sha256:' + sha or item.get('state') != 'uploaded'):
            raise PreflightError('Release asset metadata does not match its pinned identity: ' + name)
        result.append((asset_id, name, size, sha))
    return tuple(result)


def candidate_release() -> tuple:
    data = gh_json(f'repos/{REPO}/releases/{RELEASE_ID}')
    if data.get('id') != RELEASE_ID or data.get('tag_name') != RELEASE_TAG:
        raise PreflightError('The pinned draft is not the expected release')
    expected = [(aid, f'{SOURCE_NAME}.{i:03}', size, sha)
                for i, (aid, size, sha) in enumerate(PARTS, 1)]
    return asset_snapshot(data, expected, draft=True)


def app_release() -> tuple:
    data = gh_json(f'repos/{APP_REPO}/releases/tags/{APP_TAG}')
    if data.get('tag_name') != APP_TAG or data.get('prerelease') is not False:
        raise PreflightError('The upstream application is not the pinned stable release')
    return asset_snapshot(data, [(APP_ID, APP_NAME, APP_SIZE, APP_SHA256)], draft=False)


def digest_file(path: Path) -> tuple[int, str]:
    with guard._open_regular(path)[0] as f:
        before = guard._snapshot(os.fstat(f.fileno()))
        h = hashlib.sha256()
        total = 0
        while data := f.read(CHUNK):
            h.update(data)
            total += len(data)
        guard._check_unchanged(path, f, before)
    return total, h.hexdigest()


def download_app(work: Path) -> Path:
    before = app_release()
    app = work / APP_NAME
    if app.exists() or app.is_symlink():
        raise PreflightError('Application download path already exists')
    command(['gh', 'release', 'download', APP_TAG, '--repo', APP_REPO,
             '--pattern', APP_NAME, '--dir', str(work)])
    if digest_file(app) != (APP_SIZE, APP_SHA256) or app_release() != before:
        raise PreflightError('Application asset changed or failed SHA-256 verification')
    return app


def download_candidate(work: Path) -> Path:
    before = candidate_release()
    destination = work / SOURCE_NAME
    if destination.exists() or destination.is_symlink():
        raise PreflightError('Candidate reconstruction path already exists')
    combined = hashlib.sha256()
    total = 0
    with destination.open('xb') as out:
        for i, (_, size, expected) in enumerate(PARTS, 1):
            name = f'{SOURCE_NAME}.{i:03}'
            path = work / name
            if path.exists() or path.is_symlink():
                raise PreflightError('Temporary part path already exists')
            command(['gh', 'release', 'download', RELEASE_TAG, '--repo', REPO,
                     '--pattern', name, '--dir', str(work)])
            with guard._open_regular(path)[0] as f:
                snap = guard._snapshot(os.fstat(f.fileno()))
                h = hashlib.sha256()
                count = 0
                while data := f.read(CHUNK):
                    count += len(data)
                    if count > size:
                        raise PreflightError('Candidate part exceeds its locked size')
                    h.update(data)
                    combined.update(data)
                    out.write(data)
                guard._check_unchanged(path, f, snap)
            if count != size or h.hexdigest() != expected:
                raise PreflightError('Candidate part failed SHA-256 verification')
            total += count
            path.unlink()
            print(f'Candidate 03 part {i}/3 verified', flush=True)
        out.flush()
        os.fsync(out.fileno())
    if total != SOURCE_SIZE or combined.hexdigest() != SOURCE_SHA256 or candidate_release() != before:
        raise PreflightError('Reconstructed candidate or source asset metadata changed')
    if digest_file(destination) != (SOURCE_SIZE, SOURCE_SHA256):
        raise PreflightError('Reconstructed candidate failed independent readback')
    return destination


def inspect_apk(apk: Path, aapt: str, apksigner: str, zipalign: str) -> dict:
    if digest_file(apk) != (APP_SIZE, APP_SHA256):
        raise PreflightError('Application differs from its pinned release')
    badging = command([aapt, 'dump', 'badging', str(apk)])
    manifest = command([aapt, 'dump', 'xmltree', str(apk), 'AndroidManifest.xml'])
    signatures = command([apksigner, 'verify', '--verbose', '--print-certs', str(apk)])
    command([zipalign, '-c', '-p', '4', str(apk)])
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging, re.M)
    sdk = re.search(r"^sdkVersion:'([0-9]+)'", badging, re.M)
    target = re.search(r"^targetSdkVersion:'([0-9]+)'", badging, re.M)
    native = re.search(r'^native-code: (.+)$', badging, re.M)
    certs = sorted(set(x.lower() for x in re.findall(
        r'^(?:Signer #[0-9]+|V[1-4] Signer(?: #[0-9]+)?):? certificate SHA-256 digest: ([0-9a-fA-F]{64})$',
        signatures, re.M)))
    if (not package or package.group(1) != APP_PACKAGE or package.group(3) != '1.8.2'
            or not sdk or not target or int(sdk.group(1)) > 37
            or not native or "'arm64-v8a'" not in native.group(1) or len(certs) != 1):
        detail = {'package_line': next((x[:500] for x in badging.splitlines() if x.startswith('package:')), None),
                  'sdk': sdk.group(1) if sdk else None, 'target': target.group(1) if target else None,
                  'native': native.group(1) if native else None, 'signer_count': len(certs),
                  'signer_lines': [x[:200] for x in signatures.splitlines() if 'certificate SHA-256' in x][:3]}
        raise PreflightError('APK identity/API/ABI/signer unexpected: ' + json.dumps(detail, separators=(',', ':')))
    if not re.search(r'^Verified using v[23] scheme .*: true$', signatures, re.M):
        raise PreflightError('APK does not pass a modern Android signature scheme')
    if 'android:sharedUserId' in manifest:
        raise PreflightError('APK requests a shared UID and cannot be treated as an ordinary app')
    permissions = sorted(set(re.findall(r"^uses-permission: name='([^']+)'", badging, re.M)))
    if not permissions or len(permissions) > 100:
        raise PreflightError('APK manifest permissions could not be bounded')
    with zipfile.ZipFile(apk) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or 'AndroidManifest.xml' not in names:
            raise PreflightError('APK contains duplicate members or no manifest')
        broken = z.testzip()
        if broken:
            raise PreflightError('An APK member failed CRC')
        libraries = [i for i in infos if i.filename.startswith('lib/') and i.filename.endswith('.so')]
        if not libraries or any(not i.filename.startswith('lib/arm64-v8a/') for i in libraries):
            raise PreflightError('APK native libraries do not match the expected arm64-only release')
        if any(i.compress_type != zipfile.ZIP_STORED for i in libraries):
            raise PreflightError('Native libraries are compressed; packaging assumptions do not hold')
    if digest_file(apk) != (APP_SIZE, APP_SHA256):
        raise PreflightError('Application changed during inspection')
    return {'name': APP_NAME, 'bytes': APP_SIZE, 'sha256': APP_SHA256, 'upstream_repo': APP_REPO,
            'release_tag': APP_TAG, 'source_commit_claimed_by_tag': APP_COMMIT,
            'package': package.group(1), 'version_code': package.group(2), 'version_name': package.group(3),
            'min_sdk': int(sdk.group(1)), 'target_sdk': int(target.group(1)), 'abis': native.group(1),
            'signer_certificate_sha256': certs[0].lower(), 'apk_signature_verified_on_host': True,
            'apk_signer_previously_trusted': False, 'zipalign_4k_native_passed': True,
            'shared_user_id_declared': False, 'native_library_count': len(libraries),
            'native_libraries_uncompressed': True, 'permissions_declared': permissions}


def read_ext4_metrics(image: Path) -> dict:
    info = command(['/usr/sbin/dumpe2fs', '-h', str(image)])
    fields = {}
    for field in ('Block count', 'Reserved block count', 'Free blocks', 'Block size', 'Free inodes', 'Filesystem features'):
        m = re.search(r'^' + re.escape(field) + r':\s*(.+)$', info, re.M)
        if not m:
            raise PreflightError('Missing ext4 superblock field: ' + field)
        fields[field] = m.group(1).strip()
    for field in ('Block count', 'Reserved block count', 'Free blocks', 'Block size', 'Free inodes'):
        if not fields[field].isdigit():
            raise PreflightError('Non-numeric ext4 superblock field: ' + field)
    fsck = subprocess.run(['/usr/sbin/e2fsck', '-f', '-n', str(image)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False)
    if fsck.returncode != 0:
        raise PreflightError(f'Read-only e2fsck did not pass (exit {fsck.returncode})')
    return {'blocks': int(fields['Block count']), 'reserved_blocks': int(fields['Reserved block count']),
            'free_blocks': int(fields['Free blocks']), 'block_size': int(fields['Block size']),
            'free_bytes_including_reserved': int(fields['Free blocks']) * int(fields['Block size']),
            'free_inodes': int(fields['Free inodes']), 'features': fields['Filesystem features'],
            'e2fsck_read_only_exit': fsck.returncode}


def extract_extents(source: Path, work: Path, lock: dict) -> dict:
    specs = vintf.part_specs(lock)
    images = {name: work / (name + '-before.img') for name in ('system', 'system_ext', 'product')}
    if any(path.exists() or path.is_symlink() for path in images.values()):
        raise PreflightError('Extent output path already exists')
    with zipfile.ZipFile(source) as z, z.open('super.img') as stream:
        prefix = stream.read(vintf.lp.MAX_PREFIX)
        windows = vintf.extent_windows(prefix, vintf.SUPER_BYTES, specs)
        from contextlib import ExitStack
        with ExitStack() as stack:
            outputs = {name: stack.enter_context(path.open('xb')) for name, path in images.items()}
            vintf.copy_windows(stream, prefix, windows, outputs, vintf.SUPER_BYTES, SUPER_SHA256)
    return {name: {'path': path, 'window': windows[name]} for name, path in images.items()}


def inspect_paths(image: Path) -> dict:
    if vintf.pytsk3 is None:
        raise PreflightError('pytsk3 is required')
    disk = vintf.pytsk3.Img_Info(str(image))
    fs = vintf.pytsk3.FS_Info(disk)
    if fs.info.ftype != vintf.pytsk3.TSK_FS_TYPE_EXT4:
        raise PreflightError('Expected ext4 image')
    apps = []
    for root in ('/app', '/priv-app', '/system/app', '/system/priv-app'):
        try:
            directory = fs.open_dir(path=root)
        except (OSError, RuntimeError, IOError):
            continue
        names = sorted(bytes(e.info.name.name).decode('utf-8', 'surrogateescape') for e in directory
                       if e.info.name and e.info.name.name and e.info.name.flags & vintf.pytsk3.TSK_FS_NAME_FLAG_ALLOC
                       and bytes(e.info.name.name) not in (b'.', b'..'))
        if any('spatialflow' in n.lower() for n in names):
            raise PreflightError('SpatialFlow-named entry already exists in ' + root)
        apps.append({'path': root, 'entries': len(names), 'sample_names': names[:3]})
    return {'application_directories': apps}


def run(work: Path, aapt: str, apksigner: str, zipalign: str) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise PreflightError('Work directory must be empty and already exist')
    lock = json.loads((Path(__file__).parent / 'original-baseline.lock.json').read_text())
    app = download_app(work)
    app_result = inspect_apk(app, aapt, apksigner, zipalign)
    print('Upstream APK identity, signature, ABI, manifest and alignment inspected', flush=True)
    source = download_candidate(work)
    extents = extract_extents(source, work, lock)
    partitions = {}
    for name, item in extents.items():
        image = item['path']
        size, sha = digest_file(image)
        if (size, sha) != (item['window']['bytes'], item['window']['sha256']):
            raise PreflightError('Extracted extent did not pass readback: ' + name)
        with image.open('rb') as f:
            f.seek(-64, os.SEEK_END)
            avb_footer = f.read(4) == b'AVBf'
        metrics = read_ext4_metrics(image)
        paths = inspect_paths(image)
        partitions[name] = {'bytes': size, 'sha256': sha, 'avb_footer_present': avb_footer,
                            'ext4': metrics, **paths}
        print(name + ' extent checked read-only', flush=True)
    if digest_file(source) != (SOURCE_SIZE, SOURCE_SHA256):
        raise PreflightError('Candidate source changed during extraction')
    return {'schema': 'synthetica-spatialflow-preflight-v1',
            'status': 'READ_ONLY_PREFLIGHT_NOT_A_ROM_BUILD_HOLD',
            'source': {'name': SOURCE_NAME, 'bytes': SOURCE_SIZE, 'sha256': SOURCE_SHA256,
                       'source_and_draft_unchanged': True},
            'application': app_result, 'partitions': partitions,
            'limitations': ['Space and APK metadata do not prove the app will install, run, or coexist with existing packages.',
                            'An absent filesystem AVB footer does not establish external vbmeta or trust.',
                            'No image was edited or ROM built, signed, flashed, or tested on a device.',
                            'Upstream APK signing validity does not authenticate its author or its source-to-binary correspondence.']}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--aapt', required=True)
    p.add_argument('--apksigner', required=True)
    p.add_argument('--zipalign', required=True)
    args = p.parse_args()
    try:
        result = run(args.work, args.aapt, args.apksigner, args.zipalign)
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except (PreflightError, vintf.VintfAuditError, guard.AuditError,
            OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {'schema': 'synthetica-spatialflow-preflight-v1', 'status': 'FAILED_HOLD',
                  'error': str(exc), 'device_or_rom_modified': False}
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
