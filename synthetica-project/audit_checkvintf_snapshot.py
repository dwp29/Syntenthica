#!/usr/bin/env python3
"""Check a bounded, read-only VINTF snapshot with a pinned public AOSP tool.

Only a temporary copy of the already verified guarded candidate is read. XML is
copied from four verified ext4 extents without mounting and placed into an
isolated, read-only chroot. No image is modified, uploaded, installed or run.
The host tool sees no real ODM/APEX/SKU state or kernel. Therefore even its
COMPATIBLE/INCOMPATIBLE text is only an observation about this partial input,
not a verdict for the device or evidence of boot.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/hyperos4'))
import lp_metadata as lp
import audit_guarded_zip64_draft as draft
import audit_updater_emulation as emu
import audit_vintf_candidate as inventory
import audit_policy_metadata as policy_metadata
import github_guarded_release as transfer
import github_guarded_report_relay as relay
import verify_preservation as guard

# Public Android CI, aosp-android-latest-release, Android 17 x86_64, 16644040.
# The otatools SHA was independently compared with the public in-toto subject;
# its DSSE signature was NOT verified. The source revision is from the build's
# published manifest. AOSP's host tool is not the ROM's runtime libvintf.
AOSP_BUILD = '16644040'
AOSP_TARGET = 'aosp_cf_x86_64_only_phone-userdebug'
AOSP_ZIP_BYTES = 531_408_471
AOSP_ZIP_SHA256 = 'bc85557aa0c59a7d0b48b8175250948d67b2d0f293bd74eb8d5753ba4ad7781f'
CHECKVINTF_SHA256 = '6f7601b9409ac5db70d8b05bc98d117fe68456464e710eb2e2964c7edf1325db'
LIBVINTF_REVISION = 'df89ad736e14ac375f61d50fa543ae7cd746a140'
INVENTORY_SHA256 = 'f9d91cf569663d325f8d55294a9e1f1a947704743e9fca9229b207f739e1b58c'
INVENTORY_PATH = ROOT / 'research/hyperos4/HASIL-INVENTARIS-VINTF-KANDIDAT-02-2026-11-02.json'
HOST_LIBS = ('libdl.so.2', 'libpthread.so.0', 'libm.so.6', 'librt.so.1',
             'libgcc_s.so.1', 'libc.so.6', 'ld-linux-x86-64.so.2')
MAPPINGS = ('system', 'system_ext', 'product', 'vendor', 'odm', 'apex')
LEGACY_PATHS = {
    'system': ('/system/manifest.xml', '/system/compatibility_matrix.xml'),
    'vendor': ('/manifest.xml', '/compatibility_matrix.xml', '/odm/etc/manifest.xml'),
    'system_ext': (), 'product': (),
}
APEX_PATHS = {'system': '/system/apex', 'system_ext': '/apex', 'product': '/apex', 'vendor': '/apex'}
MAX_OUTPUT = 1024 * 1024


class CheckAuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    with guard._open_regular(path)[0] as stream:
        opened = guard._snapshot(os.fstat(stream.fileno()))
        digest = hashlib.sha256()
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
        guard._check_unchanged(path, stream, opened)
    return digest.hexdigest()


def prepare_tool(archive_path: Path, sandbox: Path) -> dict:
    """Extract only the exact pinned host executable, not keys or other tools."""
    if archive_path.stat().st_size != AOSP_ZIP_BYTES or sha256_file(archive_path) != AOSP_ZIP_SHA256:
        raise CheckAuditError('Public AOSP otatools ZIP does not match the audited build')
    target = sandbox / 'tool' / 'checkvintf'
    target.parent.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        matches = [item for item in archive.infolist() if item.filename == 'bin/checkvintf']
        if len(matches) != 1:
            raise CheckAuditError('Expected exactly one AOSP checkvintf executable')
        item = matches[0]
        if (item.is_dir() or item.flag_bits & 1 or not 0 < item.file_size <= 64 * 1024**2
                or stat.S_ISLNK(item.external_attr >> 16)):
            raise CheckAuditError('Unexpected AOSP executable ZIP entry')
        with archive.open(item) as src, target.open('xb') as out:
            shutil.copyfileobj(src, out, 1024 * 1024)
    if sha256_file(target) != CHECKVINTF_SHA256:
        raise CheckAuditError('AOSP checkvintf executable SHA-256 mismatch')
    target.chmod(0o555)
    readelf = subprocess.run(['readelf', '-d', str(target)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=True, text=True)
    needed = set(re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', readelf.stdout))
    if needed != set(HOST_LIBS):
        raise CheckAuditError(f'Unexpected host dynamic dependencies: {sorted(needed)}')
    host_dir = Path('/lib/x86_64-linux-gnu')
    dest_dir = sandbox / 'lib/x86_64-linux-gnu'
    dest_dir.mkdir(parents=True)
    lib_hashes = {}
    for name in HOST_LIBS:
        source = host_dir / name
        if not source.is_file():
            raise CheckAuditError(f'Host runtime library unavailable: {name}')
        destination = dest_dir / name
        shutil.copyfile(source, destination)
        destination.chmod(0o444)
        lib_hashes[name] = sha256_file(destination)
    (sandbox / 'lib64').mkdir()
    shutil.copyfile(dest_dir / 'ld-linux-x86-64.so.2', sandbox / 'lib64/ld-linux-x86-64.so.2')
    # The kernel must execute the ELF interpreter; it is still on a read-only
    # bind mount during the actual check.
    (sandbox / 'lib64/ld-linux-x86-64.so.2').chmod(0o555)
    (sandbox / 'readonly-marker').write_bytes(b'synthetic marker\n')
    return {'build': AOSP_BUILD, 'target': AOSP_TARGET,
            'otatools_bytes': AOSP_ZIP_BYTES, 'otatools_sha256': AOSP_ZIP_SHA256,
            'checkvintf_sha256': CHECKVINTF_SHA256, 'libvintf_revision': LIBVINTF_REVISION,
            'host_runtime_sha256': lib_hashes,
            'official_build_statement_digest_matched_in_probe': True,
            'official_statement_signature_verified': False}


def guest_path(partition: str, source_path: str) -> str:
    """Map only known VINTF paths to their Android guest partition."""
    path = PurePosixPath(source_path)
    if not path.is_absolute() or '..' in path.parts or str(path) != source_path or not source_path.endswith('.xml'):
        raise CheckAuditError('Unsafe or unexpected VINTF path')
    if partition == 'system' and (source_path.startswith('/system/etc/vintf/') or
                                  source_path in LEGACY_PATHS['system']):
        return source_path
    if partition in ('system_ext', 'product', 'vendor') and source_path.startswith('/etc/vintf/'):
        return f'/{partition}{source_path}'
    if partition == 'vendor' and (source_path.startswith('/odm/etc/vintf/') or
                                  source_path == '/odm/etc/manifest.xml'):
        return source_path
    if partition == 'vendor' and source_path in ('/manifest.xml', '/compatibility_matrix.xml'):
        return '/vendor' + source_path
    raise CheckAuditError(f'Unexpected VINTF input mapping for {partition}')


def capture_snapshot(snapshot: Path, seen: dict, partition: str, source_path: str, data: bytes) -> None:
    guest = guest_path(partition, source_path)
    if guest in seen or not data or len(data) > inventory.MAX_XML_BYTES:
        raise CheckAuditError('Duplicate, empty or oversized snapshot document')
    # Parse before writing and do not follow symlinks from the source image.
    inventory.parse_vintf(data, partition, source_path)
    relative = PurePosixPath(guest).relative_to('/')
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise CheckAuditError('Snapshot root is missing or is a symlink')
    parent = snapshot
    for component in relative.parts[:-1]:
        parent = parent / component
        if parent.is_symlink():
            raise CheckAuditError('Snapshot path contains a symlink')
        parent.mkdir(exist_ok=True)
        if not parent.is_dir():
            raise CheckAuditError('Snapshot path contains a non-directory')
    dest = parent / relative.parts[-1]
    if dest.exists() or dest.is_symlink():
        raise CheckAuditError('Snapshot path already exists')
    with dest.open('xb') as stream:
        stream.write(data)
    dest.chmod(0o444)
    seen[guest] = {'partition': partition, 'source_path': source_path,
                   'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def policy_observation(data: bytes, partition: str, source_path: str) -> dict | None:
    """Record explicit numeric SELinux VINTF versions, without simulating merge rules."""
    # The same bytes have already passed the bounded VINTF parser in capture.
    root = ET.fromstring(data)
    kind, xml_type = inventory._local(root.tag), root.get('type')
    if (kind, xml_type) not in (('manifest', 'device'), ('compatibility-matrix', 'framework')):
        return None
    version_tag = 'version' if kind == 'manifest' else 'sepolicy-version'
    versions, kernel_versions = [], []
    for section in inventory._children(root, 'sepolicy'):
        versions.extend(inventory._text(section, version_tag))
        kernel_versions.extend(inventory._text(section, 'kernel-sepolicy-version'))
    if not versions and not kernel_versions:
        return None
    if (len(versions) > 100 or len(kernel_versions) > 100 or
            any(not re.fullmatch(r'\d+(?:\.\d+)?(?:-\d+)?', v) for v in versions) or
            any(not re.fullmatch(r'\d+', v) for v in kernel_versions)):
        raise CheckAuditError('Unexpected SELinux VINTF version syntax')
    return {'partition': partition, 'path': source_path, 'type': xml_type,
            'level': root.get('level'), 'target_level': root.get('target-level'),
            'sepolicy_versions': versions, 'kernel_sepolicy_versions': kernel_versions}


def scan_legacy(image: Path, partition: str, capture, rows: list[dict]) -> None:
    """Look for the host tool's legacy fallbacks; no symlinks are followed."""
    fs = inventory.pytsk3.FS_Info(inventory.pytsk3.Img_Info(str(image)))
    for source_path in LEGACY_PATHS[partition]:
        row = {'partition': partition, 'path': source_path}
        try:
            entry = fs.open(source_path)
        except (OSError, RuntimeError):
            rows.append({**row, 'status': 'missing_or_unreadable'})
            continue
        meta = entry.info.meta
        if meta is None or not (meta.flags & inventory.pytsk3.TSK_FS_META_FLAG_ALLOC):
            rows.append({**row, 'status': 'missing_or_unreadable'})
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            rows.append({**row, 'status': 'symlink_not_followed'})
        elif meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG:
            rows.append({**row, 'status': 'not_regular'})
        else:
            data = inventory._read_tsk_file(entry, int(meta.size))
            capture(partition, source_path, data)
            rows.append({**row, 'status': 'read', 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})


def scan_apex_packages(image: Path, partition: str, rows: list[dict]) -> None:
    """Count apparent APEX packages without opening, extracting or activating them."""
    fs = inventory.pytsk3.FS_Info(inventory.pytsk3.Img_Info(str(image)))
    path = APEX_PATHS[partition]
    try:
        directory = fs.open_dir(path=path)
    except (OSError, RuntimeError):
        rows.append({'partition': partition, 'path': path, 'status': 'missing_or_unreadable'})
        return
    counts = {'regular_apex_or_capex': 0, 'directories': 0, 'symlinks': 0, 'other': 0}
    entries = 0
    for entry in directory:
        info, meta = entry.info.name, entry.info.meta
        if info is None or not info.name or not (info.flags & inventory.pytsk3.TSK_FS_NAME_FLAG_ALLOC):
            continue
        name = bytes(info.name)
        if name in (b'.', b'..'):
            continue
        entries += 1
        if entries > 5000:
            raise CheckAuditError('APEX directory exceeds bounded inventory limit')
        if meta is None:
            counts['other'] += 1
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_REG and name.lower().endswith((b'.apex', b'.capex')):
            counts['regular_apex_or_capex'] += 1
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_DIR:
            counts['directories'] += 1
        elif meta.type == inventory.pytsk3.TSK_FS_META_TYPE_LNK:
            counts['symlinks'] += 1
        else:
            counts['other'] += 1
    rows.append({'partition': partition, 'path': path, 'status': 'read',
                 'entry_count': entries, 'counts': counts})


def verify_inventory(docs: list[dict], seen: dict) -> None:
    """Compare exact XML identities against the previous independent run."""
    if sha256_file(INVENTORY_PATH) != INVENTORY_SHA256:
        raise CheckAuditError('The previous pinned inventory report has changed')
    prior = json.loads(INVENTORY_PATH.read_text(encoding='utf-8'))
    if prior.get('candidate_before', {}).get('sha256') != draft.CANDIDATE_SHA256:
        raise CheckAuditError('The prior inventory is not for this candidate')
    keys = ('partition', 'path', 'bytes', 'sha256')
    def normalized(records):
        return sorted(tuple(row[k] for k in keys) for row in records)
    if normalized(prior['documents']) != normalized(docs):
        raise CheckAuditError('Fresh VINTF XML inventory differs from the pinned prior run')
    for doc in docs:
        guest = guest_path(doc['partition'], doc['path'])
        item = seen.get(guest, {})
        if (item.get('partition') != doc['partition'] or item.get('source_path') != doc['path']
                or item.get('sha256') != doc['sha256'] or item.get('bytes') != doc['bytes']):
            raise CheckAuditError('Snapshot document differs from the freshly verified extent')


def create_synthetic_fixture(base: Path, matrix_version: str, *, malformed: bool = False) -> None:
    """AOSP releasetools-style minimal fixture; only disposable synthetic XML."""
    files = {
        'system/manifest.xml': '<manifest version="1.0" type="framework"/>',
        'system/etc/vintf/compatibility_matrix.1.xml':
            '<compatibility-matrix version="1.0" level="1" type="framework">'
            f'<sepolicy><sepolicy-version>{matrix_version}</sepolicy-version>'
            '<kernel-sepolicy-version>0</kernel-sepolicy-version></sepolicy></compatibility-matrix>',
        'vendor/etc/vintf/manifest.xml': ('<manifest' if malformed else
            '<manifest version="1.0" target-level="1" type="device">'
            '<sepolicy><version>0.0</version></sepolicy></manifest>'),
        'vendor/compatibility_matrix.xml': '<compatibility-matrix version="1.0" type="device"/>',
    }
    for mapping in MAPPINGS:
        (base / mapping).mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        path.chmod(0o444)


# Executed only after a new user, mount, PID and network namespace is created.
# The host libraries and the XML snapshot are bind-mounted read-only, chrooted,
# and capabilities are cleared before the fixed official tool is started.
_ISOLATED_LAUNCHER = r'''
import ctypes, os, resource, subprocess, sys
root, *args = sys.argv[1:]
subprocess.run(['/usr/bin/mount', '--bind', root, root], check=True)
subprocess.run(['/usr/bin/mount', '-o', 'remount,bind,ro', root], check=True)
try:
    fd = os.open(root + '/readonly-marker', os.O_WRONLY)
except OSError:
    pass
else:
    os.close(fd)
    raise RuntimeError('read-only root verification failed')
os.chroot(root)
os.chdir('/')
if os.path.exists('/proc') or os.path.exists('/dev') or os.path.exists('/home'):
    raise RuntimeError('unexpected host paths in isolated root')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
libc = ctypes.CDLL(None, use_errno=True)
class Header(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class Data(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32),
                ('inheritable', ctypes.c_uint32)]
header = Header(0x20080522, 0)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'no_new_privs')
empty = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(empty)) != 0:
    raise OSError(ctypes.get_errno(), 'capset')
actual = (Data * 2)()
if libc.capget(ctypes.byref(header), ctypes.byref(actual)) != 0 or any(
        x.effective or x.permitted or x.inheritable for x in actual):
    raise RuntimeError('capabilities were not cleared')
os.closerange(3, 4096)
os.execve('/tool/checkvintf', ['/tool/checkvintf'] + args,
          {'PATH': '/empty', 'LANG': 'C', 'LD_LIBRARY_PATH': '/lib/x86_64-linux-gnu'})
'''


def build_args(snapshot: str, first_api: int | None) -> list[str]:
    if not re.fullmatch(r'/(?:fixture-(?:pass|fail|bad)|snapshot)', snapshot):
        raise CheckAuditError('Unexpected in-sandbox snapshot path')
    args = ['--check-compat']
    for part in MAPPINGS:
        args.extend(['--dirmap', f'/{part}:{snapshot}/{part}'])
    if first_api is not None:
        if type(first_api) is not int or not 1 <= first_api <= 100:
            raise CheckAuditError('Invalid synthetic first API property')
        args.extend(['--property', f'ro.product.first_api_level={first_api}'])
    return args


def run_isolated(sandbox: Path, snapshot: str, first_api: int | None) -> tuple[dict, str]:
    unshare = shutil.which('unshare')
    if not unshare or not Path('/usr/bin/mount').is_file():
        raise CheckAuditError('Required user, network and mount isolation is unavailable')
    args = [unshare, '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            sys.executable, '-I', '-S', '-c', _ISOLATED_LAUNCHER, str(sandbox),
            *build_args(snapshot, first_api)]
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    try:
        stdout, stderr = process.communicate(timeout=75)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise CheckAuditError('Isolated checkvintf exceeded its time limit') from exc
    if len(stdout) + len(stderr) > MAX_OUTPUT:
        raise CheckAuditError('Isolated checkvintf output exceeded its bound')
    out = stdout.decode('utf-8', 'replace')
    err = stderr.decode('utf-8', 'replace')
    markers = [line.strip() for line in out.splitlines() if line.strip() in ('COMPATIBLE', 'INCOMPATIBLE')]
    if process.returncode == 0 and markers == ['COMPATIBLE']:
        result = 'compatible_for_supplied_snapshot'
    elif process.returncode == 65 and markers == ['INCOMPATIBLE']:
        result = 'incompatible_for_supplied_snapshot'
    else:
        result = 'tool_error_or_incomplete_input'
    combined = out + '\n' + err
    # Only fixed diagnostic markers and numeric values are relayed; raw metadata
    # and raw tool logs remain on the disposable runner and are never published.
    missing_fcm = re.search(r'Cannot find framework matrix at FCM version (\d+)', combined)
    sepolicy_mismatch = re.search(
        r"Sepolicy version (\d+(?:\.\d+)?) doesn't satis(?:i)?fy the requirements", combined)
    diagnostic_markers = {
        'missing_exact_target_fcm_matrix': 'Cannot find framework matrix at FCM version' in combined,
        'device_vs_framework_matrix_incompatible': 'Device manifest and framework compatibility matrix are incompatible' in combined,
        'framework_vs_device_matrix_incompatible': 'Framework manifest and device compatibility matrix are incompatible' in combined,
        'no_device_manifest': 'No device manifest' in combined or 'No device HAL manifest' in combined,
        'no_framework_manifest': 'No framework manifest file' in combined,
        'no_framework_matrix': 'No framework matrix file' in combined,
        'no_device_matrix': 'No device matrix file' in combined,
        'failed_parsing': 'Cannot parse' in combined or 'Error parsing' in combined,
        'fragment_merge_error': 'Cannot add manifest fragment' in combined or 'Cannot add ODM manifest' in combined,
        'apex_mentioned': 'apex' in combined.lower(),
        'nfc_mentioned': 'android.hardware.nfc' in combined,
        'sepolicy_mentioned': 'sepolicy' in combined.lower(),
        'explicit_sepolicy_version_mismatch': sepolicy_mismatch is not None,
    }
    return ({'exit_code': process.returncode, 'tool_result': result,
             'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
             'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
             'missing_fcm_version_reported': missing_fcm.group(1) if missing_fcm else None,
             'mismatched_sepolicy_version_reported': sepolicy_mismatch.group(1) if sepolicy_mismatch else None,
             'diagnostic_markers': diagnostic_markers}, combined)


def run_controls(sandbox: Path) -> list[dict]:
    cases = [('pass', '0.0', False, 'compatible_for_supplied_snapshot'),
             ('fail', '1.0', False, 'incompatible_for_supplied_snapshot'),
             ('bad', '0.0', True, 'tool_error_or_incomplete_input')]
    rows = []
    for name, version, malformed, expected in cases:
        create_synthetic_fixture(sandbox / f'fixture-{name}', version, malformed=malformed)
        observed, raw = run_isolated(sandbox, f'/fixture-{name}', 29)
        if observed['tool_result'] != expected:
            # These are explicitly synthetic inputs, so bounded debugging text
            # cannot disclose ROM metadata. Never print candidate tool output.
            raise CheckAuditError(f'Synthetic {name} expected {expected}, got {observed}:\n{raw[:6000]}')
        rows.append({'scenario': name, 'expected': expected, **observed})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--otatools', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True, help='new empty disposable directory')
    parser.add_argument('--report', type=Path, required=True, help='new small JSON metadata report')
    args = parser.parse_args()
    if not args.work.is_dir() or args.work.is_symlink() or any(args.work.iterdir()):
        raise CheckAuditError('Work directory must be new, empty, and not a symlink')
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise CheckAuditError('Report must be a new file in an existing directory')
    sandbox = args.work / 'isolated-root'
    sandbox.mkdir()
    tool = prepare_tool(args.otatools, sandbox)
    print('Running positive, negative and malformed synthetic controls', flush=True)
    controls = run_controls(sandbox)
    print('All three isolated synthetic controls produced the expected categories', flush=True)
    snapshot = sandbox / 'snapshot'
    for part in MAPPINGS:
        (snapshot / part).mkdir(parents=True, exist_ok=True)
    seen, legacy, apex, policies = {}, [], [], []
    policy_files, mapping_dirs, private_policy_text = [], [], {}
    def capture(partition, path, data):
        capture_snapshot(snapshot, seen, partition, path, data)
        observation = policy_observation(data, partition, path)
        if observation is not None:
            policies.append(observation)
    def scan_extra(image, partition):
        scan_legacy(image, partition, capture, legacy)
        scan_apex_packages(image, partition, apex)
        policy_metadata.scan(image, partition, policy_files, mapping_dirs, private_policy_text)
    download = args.work / 'download'
    download.mkdir()
    candidate = draft.download_existing_draft(download)
    before = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    with (ROOT / 'synthetica-project/original-baseline.lock.json').open(encoding='utf-8') as stream:
        specs = inventory.part_specs(json.load(stream))
    docs, roots, groups = [], [], []
    for names in (('system', 'system_ext', 'vendor'), ('product',)):
        more_docs, more_roots, group = inventory.audit_group(candidate, download, names, specs,
                                                               capture=capture, scan_extra=scan_extra)
        docs.extend(more_docs)
        roots.extend(more_roots)
        groups.append(group)
    verify_inventory(docs, seen)
    print(f'Checking {len(docs)} unchanged inventory XML files plus {sum(r["status"] == "read" for r in legacy)} readable legacy files', flush=True)
    # These are deliberately alternative, hypothetical property settings. They
    # are NOT claims about the physical device's actual first API or SKU.
    default_result, _ = run_isolated(sandbox, '/snapshot', None)
    assumed_api30, _ = run_isolated(sandbox, '/snapshot', 30)
    for guest, item in seen.items():
        path = snapshot.joinpath(*PurePosixPath(guest).relative_to('/').parts)
        if path.stat().st_size != item['bytes'] or sha256_file(path) != item['sha256']:
            raise CheckAuditError('A snapshot document changed during isolated tool execution')
    after = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    result = {
        'schema': 'synthetica-checkvintf-partial-snapshot-v1',
        'scope': 'verified guarded candidate, four ext4 partitions; host-only partial snapshot',
        'tool': tool,
        'synthetic_controls': controls,
        'candidate_before': before, 'candidate_after': after,
        'groups': groups, 'scan_roots': roots, 'legacy_inputs': legacy,
        'apex_package_counts_only': apex, 'explicit_sepolicy_observations': policies,
        'split_policy_static_metadata': policy_metadata.summarize(policy_files, mapping_dirs, private_policy_text),
        'snapshot_documents': len(seen), 'prior_inventory_documents': len(docs),
        'prior_inventory_identities_match': True, 'snapshot_documents_unchanged_after_checks': True,
        'scenarios': [
            {'name': 'empty_properties', 'assumption': 'SKU and first API not supplied', **default_result},
            {'name': 'hypothetical_first_api_30',
             'assumption': 'first API 30 is hypothetical; SKU not supplied', **assumed_api30},
        ],
        'isolation': {'user_mount_pid_network_namespaces': True, 'chroot': True,
                      'root_bind_readonly': True, 'capabilities_dropped': True,
                      'no_new_privileges': True, 'candidate_zip_excluded_from_chroot': True,
                      'no_devices_or_host_proc': True},
        'limitations': [
            'Partial metadata snapshot only: real ODM/APEX state, SKU, boot properties and runtime library implementation are unknown.',
            'Absent or unreadable ODM inputs and absent APEX metadata were represented by empty temporary directories, not proved absent on the device.',
            'Kernel runtime information was not supplied; checkvintf skips kernel requirements.',
            'Host AOSP checkvintf and its in-toto digest are identified, but the official statement signature was not verified and the ROM runtime may differ.',
            'A tool result for this snapshot is not a complete compatibility verdict, recovery test, AVB validation, or device boot proof.',
            'No image was modified, uploaded, installed or executed; no device was accessed.',
        ],
    }
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print('Partial VINTF snapshot audit finished; no device verdict is asserted.', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CheckAuditError, policy_metadata.PolicyMetadataError, inventory.VintfAuditError, lp.LPError, draft.DraftTestError,
            emu.SimulationError, relay.RelayError, transfer.TransferError, guard.AuditError,
            OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f'::error title=Partial VINTF snapshot audit stopped::{exc}', file=sys.stderr)
        raise SystemExit(1)
