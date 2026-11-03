#!/usr/bin/env python3
"""Exercise the *exact* 04 updater on ordinary disposable files, never a device.

The three pinned unpublished 04 parts are reconstructed and hashed. The real
updater and script execute unmodified in the existing unprivileged, networkless
QEMU/chroot sandbox, with a synthetic joyeuse property area and ONLY regular
files at the target names. All bytes of the 8 GiB super, boot, and dtbo outputs
are hashed and compared to the previously locked 04 build. This is not recovery,
real block-device I/O, a boot test, a signed-package test, or permission to flash.
Afterwards the verified super copy supplies a read-only camera capacity/collision
probe; no ROM images, APKs, or keys are uploaded, built, signed, or installed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile

import audit_boot_first_installer as boot_audit
import audit_spatialflow04_product as candidate04
import audit_updater_emulation as emu
import audit_vintf_candidate as vintf
import build_guarded_candidate as guarded
import preflight_spatialflow as pre
import verify_preservation as preservation

SCHEMA = 'synthetica-04-full-updater-host-emulation-v1'
SYSTEM_START = 3_893_362_688
SYSTEM_BYTES = 1_732_870_144
SYSTEM_SHA = '1a27a6d10de5bb55d2e5a0dc543af181e8227fb9970053f1880f0e86520d01f0'
# The final linear extent ends here; only the aligned tail is counted as a
# conservative bound for a single additional extent, not every tiny LP gap.
TAIL_START = 8_559_525_888
SUPER_BYTES = 8_589_934_592
CAMERA_BYTES = 127_878_632
CAMERA_SHA = '54dc2f389b74a1799c6b238699fa4a8b5cca829d93f5064da3f55457900e1792'
TREE_COMMIT = '2582e3859181d32372a669f0cdaad151095b8a53'
TREE_BLOBS = 94
TREE_TOTAL = 306_826_362
PARTS = {
    'super': (SUPER_BYTES, candidate04.SUPER_SHA),
    'boot': (134_217_728, '57f7c113ae8d5f331fd2b84e526c5f6fa083ae385844b317514fd1e91e55234d'),
    'dtbo': (25_165_824, emu.DTBO_SHA256),
}
CHUNK = 4 * 1024 * 1024
MAX_TREE = 2 * 1024 * 1024
MAX_FILE = 256 * 1024 * 1024

class FullEmulationError(RuntimeError):
    pass


def read_updater(candidate: Path) -> bytes:
    with zipfile.ZipFile(candidate) as archive:
        names = [i.filename for i in archive.infolist()]
        if len(names) != len(set(names)):
            raise FullEmulationError('Duplicate archive members')
        for name, (size, _) in PARTS.items():
            info = archive.getinfo(name + '.img')
            if info.file_size != size or info.flag_bits & 1:
                raise FullEmulationError('Unexpected image member: ' + name)
        script_info = archive.getinfo(guarded.SCRIPT)
        updater_info = archive.getinfo(boot_audit.BINARY)
        if script_info.file_size != 1569 or updater_info.file_size != 2_353_664:
            raise FullEmulationError('Unexpected updater or guarded script size')
        script, updater = archive.read(script_info), archive.read(updater_info)
        if emu.digest(script) != guarded.NEW_SCRIPT_SHA or emu.digest(updater) != boot_audit.BINARY_SHA256:
            raise FullEmulationError('Updater or guarded script identity changed')
        if archive.comment:
            raise FullEmulationError('The locked 04 package unexpectedly has a ZIP comment')
    return updater


def target_state(path: Path, limit: int) -> dict:
    """Stream-hash only an ordinary fake target; never materialize an 8 GiB buffer."""
    initial=path.lstat()
    if not stat.S_ISREG(initial.st_mode) or initial.st_size > limit:
        raise FullEmulationError('Fake target is not a bounded regular file')
    flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(path,flags),'rb') as stream:
        before=preservation._snapshot(os.fstat(stream.fileno()))
        if before!=preservation._snapshot(initial):raise FullEmulationError('Fake target changed while opening')
        h = hashlib.sha256(); size = 0
        while block := stream.read(CHUNK):
            size += len(block); h.update(block)
        preservation._check_unchanged(path, stream, before)
    return {'type': 'regular', 'bytes': size, 'sha256': h.hexdigest()}


def execution_summary(run, base: Path) -> dict:
    states = {name: target_state(base / name, size + 1024 * 1024) for name, (size, _) in PARTS.items()}
    exact = {name: (states[name]['bytes'], states[name]['sha256']) == spec for name, spec in PARTS.items()}
    return {'exit_code': run.returncode, 'finished_message_seen': emu.FINISHED_MESSAGE in run.stdout,
            'assert_failed': 'assert failed: package_extract_file(' in run.stdout,
            'fake_targets': states, 'matches_locked_04_members': exact,
            'all_outputs_match_locked_04': all(exact.values()),
            'stdout_tail': run.stdout[-1800:], 'stderr_tail': run.stderr[-1200:]}


def hypothetical_camera_capacity(system_free: int, camera_bytes: int = CAMERA_BYTES,
                                   tail_bytes: int = SUPER_BYTES - TAIL_START) -> dict:
    if any(type(x) is not int or x < 0 for x in (system_free, camera_bytes, tail_bytes)) or not camera_bytes:
        raise FullEmulationError('Invalid camera capacity inputs')
    # This is an intentionally optimistic ceiling. It assumes all usable system
    # free bytes and the entire tail could become camera space with zero ext4
    # overhead and no reserve. It does NOT authorize an LP or filesystem edit.
    ceiling = system_free + tail_bytes
    return {'camera_apk_bytes': camera_bytes, 'system_usable_free_bytes': system_free,
            'single_tail_bytes': tail_bytes, 'optimistic_ceiling_bytes': ceiling,
            'apk_exceeds_ceiling': camera_bytes > ceiling,
            'minimum_deficit_before_overhead_or_reserve_bytes': max(0, camera_bytes - ceiling),
            'does_not_include_native_libraries': True,
            'does_not_consider_reclaiming_or_repartitioning_existing_files': True,
            'does_not_measure_physical_device_super': True}


def camera_targets(tree: dict) -> list[dict]:
    if (not isinstance(tree, dict) or tree.get('sha') != TREE_COMMIT or tree.get('truncated') is not False
            or not isinstance(tree.get('tree'), list)):
        raise FullEmulationError('Leica tree identity or completeness differs')
    blobs = [x for x in tree['tree'] if isinstance(x, dict) and x.get('type') == 'blob']
    if (len(blobs) != TREE_BLOBS or any(type(x.get('size')) is not int or x['size'] <= 0
            or not re.fullmatch(r'[0-9a-f]{40}', x.get('sha', '')) for x in blobs)
            or sum(x['size'] for x in blobs) != TREE_TOTAL):
        raise FullEmulationError('Leica source tree blob inventory differs')
    targets = []; parts = {}; seen = set()
    for x in blobs:
        path = x.get('path')
        if not isinstance(path, str) or path in seen or not re.fullmatch(r'[A-Za-z0-9_./+.-]+', path):
            raise FullEmulationError('Unsafe or duplicate source tree path')
        seen.add(path)
        if not path.startswith('proprietary/system/'):
            continue
        dest = '/system/' + path.removeprefix('proprietary/system/')
        if '..' in Path(dest).parts or not dest.startswith('/system/'):
            raise FullEmulationError('Unsafe candidate destination')
        if dest.endswith(('MiuiCamera.apk.00', 'MiuiCamera.apk.01')):
            parts[dest[-2:]] = x
            continue
        targets.append({'path': dest, 'bytes': x['size'], 'git_blob_sha1': x['sha']})
    if (set(parts) != {'00','01'} or parts['00']['size'] + parts['01']['size'] != CAMERA_BYTES
            or parts['00']['sha'] != '605d07cdc014be5befea4a4a44beadea9bb8adaa'
            or parts['01']['sha'] != 'c0c55420cfc1183b2d2c48ea4f79d32c230684e0'):
        raise FullEmulationError('Pinned split Leica APK differs')
    targets.append({'path': '/system/priv-app/MiuiCamera/MiuiCamera.apk',
                    'bytes': CAMERA_BYTES, 'sha256': CAMERA_SHA})
    if len({x['path'] for x in targets}) != len(targets):
        raise FullEmulationError('Ambiguous merged candidate paths')
    return sorted(targets, key=lambda x: x['path'])


def compare_camera_paths(fs, targets: list[dict]) -> dict:
    rows=[]
    for target in targets:
        try: entry=fs.open(path=target['path'])
        except (OSError, RuntimeError, IOError):
            rows.append({**target, 'status':'not_seen_at_exact_path'}); continue
        m=entry.info.meta
        if (m is None or not (m.flags & vintf.pytsk3.TSK_FS_META_FLAG_ALLOC)
                or m.type != vintf.pytsk3.TSK_FS_META_TYPE_REG):
            rows.append({**target,'status':'existing_nonregular_or_unallocated'});continue
        size=int(m.size)
        if not 0 <= size <= MAX_FILE:
            rows.append({**target,'status':'existing_file_outside_read_bound','existing_bytes':size});continue
        sha256=hashlib.sha256();git=hashlib.sha1(f'blob {size}\0'.encode());pos=0
        while pos<size:
            data=entry.read_random(pos,min(CHUNK,size-pos))
            if not data or len(data)>size-pos:raise FullEmulationError('Short existing-file read')
            sha256.update(data);git.update(data);pos+=len(data)
        same = size==target['bytes'] and (sha256.hexdigest()==target['sha256'] if 'sha256' in target
                                          else git.hexdigest()==target['git_blob_sha1'])
        rows.append({**target,'status':'same_bytes_by_pinned_digest' if same else 'different_existing_file',
                     'existing_bytes':size,'existing_sha256':sha256.hexdigest(),
                     'existing_git_blob_sha1':git.hexdigest()})
    counts={key:sum(x['status']==key for x in rows) for key in (
        'not_seen_at_exact_path','same_bytes_by_pinned_digest','different_existing_file',
        'existing_nonregular_or_unallocated','existing_file_outside_read_bound')}
    return {'target_count':len(rows),'target_total_bytes':sum(x['bytes'] for x in rows),
            'counts':counts,'targets':rows,
            'limitations':['Exact paths only: an absent path is not proof a package or library is absent elsewhere.',
               'Replacing a different existing library can break existing applications; no path was modified.',
               'Git blob SHA-1 is used for pinned source comparison, not publisher authentication or runtime compatibility.',
               'System extents and metadata are from candidate 04, not measured device partitions.']}


def copy_system(super_image: Path, dest: Path) -> dict:
    if dest.exists() or dest.is_symlink():raise FullEmulationError('System output already exists')
    h=hashlib.sha256(); count=0
    with preservation._open_regular(super_image)[0] as source, dest.open('xb') as out:
        snap=preservation._snapshot(os.fstat(source.fileno()));source.seek(SYSTEM_START)
        while count<SYSTEM_BYTES:
            block=source.read(min(CHUNK,SYSTEM_BYTES-count))
            if not block:raise FullEmulationError('Short system extent')
            count+=len(block);h.update(block);out.write(block)
        out.flush(); preservation._check_unchanged(super_image,source,snap)
    if count!=SYSTEM_BYTES or h.hexdigest()!=SYSTEM_SHA or pre.digest_file(dest)!=(SYSTEM_BYTES,SYSTEM_SHA):
        raise FullEmulationError('System extent differs from the pinned 04 build')
    return {'bytes':count,'sha256':h.hexdigest()}


def system_probe(super_image: Path, root: Path, tree: dict) -> dict:
    if vintf.pytsk3 is None:raise FullEmulationError('The pinned ext4 reader is unavailable')
    with super_image.open('rb') as inp:
        prefix=inp.read(vintf.lp.MAX_PREFIX)
    metadata=candidate04.check_product_metadata(prefix,SUPER_BYTES)
    system=root/'system-disposable.img';identity=copy_system(super_image,system)
    metrics=pre.read_ext4_metrics(system)
    if metrics['free_blocks'] < metrics['reserved_blocks']:
        raise FullEmulationError('Invalid ext4 free/reserved count')
    free=(metrics['free_blocks']-metrics['reserved_blocks'])*metrics['block_size']
    disk=vintf.pytsk3.Img_Info(str(system));fs=vintf.pytsk3.FS_Info(disk)
    if fs.info.ftype != vintf.pytsk3.TSK_FS_TYPE_EXT4:raise FullEmulationError('System is not ext4')
    targets=camera_targets(tree);paths=compare_camera_paths(fs,targets)
    if pre.digest_file(system)!=(SYSTEM_BYTES,SYSTEM_SHA):raise FullEmulationError('System copy changed')
    return {'metadata':metadata,'system':identity,'ext4':metrics,
            'hypothetical_camera_capacity':hypothetical_camera_capacity(free), 'camera_paths':paths}


def run_sandbox(qemu: Path, updater: bytes, archive: Path, work: Path, tree: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix='synthetica-full-04-', dir=work) as td:
        root=Path(td)/'root';base=root/'dev/block/bootdevice/by-name';base.mkdir(parents=True)
        shutil.copyfile(qemu,root/'qemu');(root/'qemu').chmod(0o755)
        (root/'update-binary').write_bytes(updater);(root/'update-binary').chmod(0o755)
        (root/'input.zip').touch()
        prop=root/'dev/__properties__';prop.write_bytes(emu.fake_joyeuse_property_area());prop.chmod(0o444)
        for name in PARTS:(base/name).write_bytes(emu.SENTINEL)
        print('Executing the pinned 04 updater on fake regular-file targets only',flush=True)
        run=emu._exec_isolated(root,archive.absolute(),timeout=2400,
                               file_size_limit=SUPER_BYTES+1024*1024)
        execution=execution_summary(run,base)
        result={'execution':execution}
        if run.returncode==0 and execution['finished_message_seen'] and execution['all_outputs_match_locked_04']:
            print('All three fake target hashes matched; checking system capacity and collisions',flush=True)
            result['system_probe']=system_probe(base/'super',root,tree)
        return result


def run(work: Path, qemu: Path, tree_path: Path) -> dict:
    if (not work.is_dir() or work.is_symlink() or any(work.iterdir())
            or tree_path.is_symlink() or not tree_path.is_file() or tree_path.stat().st_size>MAX_TREE):
        raise FullEmulationError('Empty disposable work directory and bounded tree metadata required')
    tree=json.loads(tree_path.read_bytes());camera_targets(tree)
    qemu_identity=emu.regular_identity(qemu,None,emu.QEMU_SHA256)
    archive=candidate04.download(work)
    before=emu.regular_identity(archive,candidate04.ZIP_BYTES,candidate04.ZIP_SHA)
    updater=read_updater(archive)
    needed=SUPER_BYTES+PARTS['boot'][0]+PARTS['dtbo'][0]+SYSTEM_BYTES+1024**3
    if shutil.disk_usage(work).free<needed:
        raise FullEmulationError('Insufficient disposable space for fake image targets and system copy')
    result=run_sandbox(qemu,updater,archive,work,tree)
    after=emu.regular_identity(archive,candidate04.ZIP_BYTES,candidate04.ZIP_SHA)
    release=candidate04.release_snapshot(pre.gh_json(f'repos/{pre.REPO}/releases/{candidate04.RELEASE_ID}'))
    if before!=after or len(release)!=5:raise FullEmulationError('Source or draft inventory changed')
    ok=(result['execution']['exit_code']==0 and result['execution']['finished_message_seen']
        and result['execution']['all_outputs_match_locked_04'] and 'system_probe' in result)
    return {'schema':SCHEMA,'status':'HOST_FAKE_TARGETS_VERIFIED_HOLD' if ok else 'HOST_FAKE_TARGETS_FAILED_HOLD',
        'candidate_before':before,'candidate_after':after,'qemu':qemu_identity,
        'updater_sha256':boot_audit.BINARY_SHA256,'script_sha256':guarded.NEW_SCRIPT_SHA,
        'tree_source_commit':TREE_COMMIT,'source_draft_still_unchanged':True,
        'isolation':{'user_mount_pid_network_namespaces':True,'chroot':True,'input_read_only':True,
             'capabilities_dropped':True,'no_new_privileges':True,'targets_are_regular_files':True,
             'device_access':False},**result,
        'limitations':['A QEMU host simulation does not test OrangeFox, real block devices, flash, boot or hardware.',
           'The unsigned ZIP, recovery signature policy, external AVB/vbmeta, rollback and real-device partition capacity remain unverified.',
           'A successful extraction does not prove framework/vendor/SELinux compatibility or application functionality.',
           'No source APK, ROM image, key, release, or device was modified or published.']}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',required=True,type=Path);parser.add_argument('--qemu',required=True,type=Path)
    parser.add_argument('--leica-tree',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    a=parser.parse_args()
    if a.report.exists() or a.report.is_symlink() or not a.report.parent.is_dir():
        raise FullEmulationError('Use a new report path')
    try:
        result=run(a.work,a.qemu,a.leica_tree);code=0 if result['status']=='HOST_FAKE_TARGETS_VERIFIED_HOLD' else 1
    except (FullEmulationError,emu.SimulationError,candidate04.ProductAuditError,pre.PreflightError,
            preservation.AuditError,vintf.VintfAuditError,OSError,ValueError,zipfile.BadZipFile,KeyError) as exc:
        result={'schema':SCHEMA,'status':'INCOMPLETE_HOLD','error':str(exc),'device_access':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,separators=(',',':')),flush=True);return code

if __name__=='__main__':sys.exit(main())
