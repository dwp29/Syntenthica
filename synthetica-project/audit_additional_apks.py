#!/usr/bin/env python3
"""Inspect nonstandard APK locations and GMS-related paths in pinned ROM images.

Reads system, system_ext, product and vendor copies from the locked candidate
03. Existing app/priv-app roots are already covered by the regular inventory;
this examines ordinary APK files outside those roots, excluding framework APKs,
plus bounded matching path/symlink names. Never mounts, executes or modifies
an image or APK. ZIP/APEX contents, symlink targets and device /data are not
examined, so a missing match is not proof that a package is absent on a device.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

import audit_vintf_candidate as vintf
import preflight_spatialflow as pre
import scan_apk_packages as packages
import verify_preservation as guard

PARTITIONS = ('system', 'system_ext', 'product', 'vendor')
MAX_PATHS = 200_000
MAX_DEPTH = 60
MAX_EXTRA_APKS = 2500
MAX_MATCHES = 50
PATH_RE = re.compile(r'(google|gms|gapp|play.?service|phonesky|preload)', re.I)
PACKAGE_RE = re.compile(r'^(?:com\.google\.|com\.android\.vending$|com\.codetrio\.spatialflow$|com\.android\.axion\.sandbox$|com\.android\.camera|com\.miui\.camera)', re.I)

class AdditionalAuditError(RuntimeError):
    pass


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + '/')


def previously_scanned(partition: str, path: str) -> bool:
    return any(_under(path, root) for root in packages.ROOTS.get(partition, ()))


def framework_path(partition: str, path: str) -> bool:
    roots = ('/system/framework', '/framework') if partition == 'system' else ('/framework',)
    return any(_under(path, root) for root in roots)


def _read_apk(entry, size: int, output: Path) -> str:
    if not 0 < size <= packages.MAX_APK_BYTES:
        raise AdditionalAuditError('An additional APK exceeds its bounded size')
    h=hashlib.sha256();pos=0
    with output.open('xb') as out:
        while pos<size:
            data=entry.read_random(pos,min(packages.CHUNK,size-pos))
            if not data or len(data)>min(packages.CHUNK,size-pos):
                raise AdditionalAuditError('Could not read an additional APK completely')
            out.write(data);h.update(data);pos+=len(data)
    if pre.digest_file(output)!=(size,h.hexdigest()):
        raise AdditionalAuditError('An extracted additional APK did not pass readback')
    return h.hexdigest()


def inspect(images: dict[str,Path], aapt: str, aapt2: str, scratch: Path) -> dict:
    if vintf.pytsk3 is None or set(images)!=set(PARTITIONS):
        raise AdditionalAuditError('The four ext4 partitions and pytsk3 are required')
    if not scratch.is_dir() or any(scratch.iterdir()):
        raise AdditionalAuditError('Scan scratch directory must be empty')
    tools={'aapt_sha256':packages._tool_digest(aapt),'aapt2_sha256':packages._tool_digest(aapt2)}
    if os.path.samefile(aapt,aapt2) or tools['aapt_sha256']==tools['aapt2_sha256']:
        raise AdditionalAuditError('Two distinct Android readers are required')
    paths_checked=0; extra_apks=0; skipped_known=0; skipped_framework=0
    named_hits=[];named_total=0; symlinks=[]; symlink_total=0; apk_hits=[]
    fallback=[]; temporary=scratch/'additional.apk'
    for partition in PARTITIONS:
        raw=vintf.pytsk3.Img_Info(str(images[partition]));fs=vintf.pytsk3.FS_Info(raw)
        if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:
            raise AdditionalAuditError('Expected ext4 partition: '+partition)
        stack=[('/',int(fs.info.root_inum),0)];visited=set()
        while stack:
            parent,inode,depth=stack.pop()
            if inode in visited or depth>MAX_DEPTH:
                raise AdditionalAuditError('Directory cycle or excessive depth: '+partition+':'+parent)
            visited.add(inode)
            for entry in fs.open_dir(inode=inode):
                ni,meta=entry.info.name,entry.info.meta
                if not ni or not ni.name or not (ni.flags & vintf.pytsk3.TSK_FS_NAME_FLAG_ALLOC):continue
                name=bytes(ni.name)
                if name in (b'.',b'..'):continue
                if b'/' in name or b'\0' in name or meta is None:
                    raise AdditionalAuditError('Unsafe filesystem entry')
                if meta.type in (vintf.pytsk3.TSK_FS_META_TYPE_VIRT,vintf.pytsk3.TSK_FS_META_TYPE_VIRT_DIR):continue
                path=('' if parent=='/' else parent)+'/'+name.decode('utf-8','surrogateescape')
                paths_checked+=1
                if paths_checked>MAX_PATHS:raise AdditionalAuditError('Filesystem path limit exceeded')
                if PATH_RE.search(path):
                    named_total+=1
                    if len(named_hits)<MAX_MATCHES:
                        named_hits.append({'partition':partition,'path':path,'inode_type':int(meta.type),'bytes':int(meta.size)})
                if meta.type==vintf.pytsk3.TSK_FS_META_TYPE_DIR:
                    stack.append((path,int(meta.addr),depth+1));continue
                if meta.type==vintf.pytsk3.TSK_FS_META_TYPE_LNK:
                    target=bytes(meta.link).decode('utf-8','surrogateescape') if meta.link is not None else None
                    if path.lower().endswith('.apk') or PATH_RE.search(path) or (target is not None and PATH_RE.search(target)):
                        symlink_total+=1
                        if len(symlinks)<MAX_MATCHES:symlinks.append({'partition':partition,'path':path,'target':target})
                    continue
                if meta.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG or not path.lower().endswith('.apk'):continue
                if previously_scanned(partition,path):skipped_known+=1;continue
                if framework_path(partition,path):skipped_framework+=1;continue
                extra_apks+=1
                if extra_apks>MAX_EXTRA_APKS:raise AdditionalAuditError('Additional APK count limit exceeded')
                try:
                    sha=_read_apk(entry,int(meta.size),temporary)
                    try: package,method=packages.package_from_apk(temporary,aapt,aapt2)
                    except packages.PackageScanError as exc:
                        raise AdditionalAuditError('Cannot inspect '+partition+':'+path+': '+str(exc)) from exc
                    if method!='aapt_badging':fallback.append(partition+':'+path)
                    if PACKAGE_RE.search(package):
                        if len(apk_hits)>=MAX_MATCHES:raise AdditionalAuditError('Matching package count limit exceeded')
                        apk_hits.append({'partition':partition,'path':path,'bytes':int(meta.size),'sha256':sha,
                                         'package':package,'reader':method})
                finally: temporary.unlink(missing_ok=True)
        print(f'{partition}: filesystem paths walked without mounting',flush=True)
    if tools!={'aapt_sha256':packages._tool_digest(aapt),'aapt2_sha256':packages._tool_digest(aapt2)}:
        raise AdditionalAuditError('Host readers changed during the audit')
    return {'filesystem_paths_checked':paths_checked,'additional_apks_checked':extra_apks,
            'apks_in_previously_scanned_roots_skipped':skipped_known,'framework_apks_skipped':skipped_framework,
            'matching_extra_apks':apk_hits,'matching_gms_package_found':any(x['package']=='com.google.android.gms' for x in apk_hits),
            'potential_spatialflow_collision_outside_roots':any(x['package']==pre.APP_PACKAGE for x in apk_hits),
            'gms_related_name_matches':named_hits,'gms_related_name_count':named_total,
            'gms_related_names_truncated':named_total>len(named_hits),
            'relevant_symlinks_not_followed':symlinks,'relevant_symlink_count':symlink_total,
            'relevant_symlinks_truncated':symlink_total>len(symlinks),
            'xmltree_fallback_paths':fallback,'tool_sha256':tools,
            'limitations':['Only allocated ext4 paths in four image copies were walked.',
                'Previously scanned app roots, framework APKs, APEX/ZIP contents, symlink targets and device data were not inspected by this pass.',
                'A package match is not proof that Android installs it, that it works, is licensed, or is certified.']}


def run(work: Path,aapt: str,aapt2: str) -> dict:
    if not work.is_dir() or any(work.iterdir()):raise AdditionalAuditError('Work directory must be empty')
    source=pre.download_candidate(work)
    lock=json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text())
    specs=vintf.part_specs(lock); images={n:work/(n+'-copy.img') for n in PARTITIONS}
    with zipfile.ZipFile(source) as z,z.open('super.img') as stream,ExitStack() as stack:
        prefix=stream.read(vintf.lp.MAX_PREFIX)
        windows=vintf.extent_windows(prefix,vintf.SUPER_BYTES,specs)
        outputs={n:stack.enter_context(path.open('xb')) for n,path in images.items()}
        vintf.copy_windows(stream,prefix,windows,outputs,vintf.SUPER_BYTES,pre.SUPER_SHA256)
    for name,path in images.items():
        if pre.digest_file(path)!=(windows[name]['bytes'],windows[name]['sha256']):
            raise AdditionalAuditError('Extracted extent failed readback: '+name)
    scratch=work/'extra-scan';scratch.mkdir(); result=inspect(images,aapt,aapt2,scratch)
    for name,path in images.items():
        if pre.digest_file(path)!=(windows[name]['bytes'],windows[name]['sha256']):
            raise AdditionalAuditError('Image changed during read-only audit: '+name)
    if pre.digest_file(source)!=(pre.SOURCE_SIZE,pre.SOURCE_SHA256):
        raise AdditionalAuditError('Source archive changed during audit')
    return {'schema':'synthetica-additional-apk-audit-v1','status':'READ_ONLY_ADDITIONAL_APK_AUDIT_HOLD',
            'source_candidate03_sha256':pre.SOURCE_SHA256,'input_images_unchanged':True,'audit':result}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True);args=p.parse_args()
    try: result=run(args.work,args.aapt,args.aapt2);code=0
    except (AdditionalAuditError,packages.PackageScanError,pre.PreflightError,vintf.VintfAuditError,
            guard.AuditError,OSError,ValueError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-additional-apk-audit-v1','status':'INCOMPLETE_HOLD',
                'error':str(exc),'device_modified':False};code=1
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,separators=(',',':')),flush=True);return code

if __name__=='__main__':sys.exit(main())
