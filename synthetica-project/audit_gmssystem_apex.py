#!/usr/bin/env python3
"""Inspect APKs inside the on-disk Google gmssystem APEX, without activation.

Extracts a single APEX from a verified product image, checks its ZIP payload,
and reads package IDs using two host manifest tools. EROFS uses a separately
controlled isolated reader. No device
code runs, images are not mounted or changed, and the APEX is not published.
APEX signatures, runtime activation, permissions and Play Services behavior are
NOT established by this inspection. Unsupported payloads remain inconclusive.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import zipfile
import audit_runtime_apex as apex
import audit_gms_erofs as erofs
import audit_vintf_candidate as vintf
import preflight_spatialflow as pre
import scan_apk_packages as scan
import verify_preservation as guard

APEX_PATH='/apex/com.google.android.gmssystem.prodvic.apex'
MAX_APEX=512*1024*1024
MAX_PATHS=40_000
MAX_DEPTH=40
MAX_APKS=500

class GmsApexError(RuntimeError):pass


def inspect_ext4(payload: Path,aapt: str,aapt2: str,scratch: Path) -> dict:
    if vintf.pytsk3 is None:raise GmsApexError('pytsk3 reader unavailable')
    raw=vintf.pytsk3.Img_Info(str(payload));fs=vintf.pytsk3.FS_Info(raw)
    if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:raise GmsApexError('Expected ext4 APEX payload')
    if not scratch.is_dir() or any(scratch.iterdir()):raise GmsApexError('Scratch must be empty')
    stack=[('/',int(fs.info.root_inum),0)];visited=set();count=0;results=[];links=[]
    temporary=scratch/'payload-entry.apk'
    while stack:
        parent,inode,depth=stack.pop()
        if inode in visited or depth>MAX_DEPTH:raise GmsApexError('Directory cycle or depth exceeded')
        visited.add(inode)
        for entry in fs.open_dir(inode=inode):
            ni,meta=entry.info.name,entry.info.meta
            if not ni or not ni.name or not (ni.flags & vintf.pytsk3.TSK_FS_NAME_FLAG_ALLOC):continue
            rawname=bytes(ni.name)
            if rawname in (b'.',b'..'):continue
            if b'/' in rawname or b'\0' in rawname or meta is None:raise GmsApexError('Unsafe APEX entry')
            if meta.type in (vintf.pytsk3.TSK_FS_META_TYPE_VIRT,vintf.pytsk3.TSK_FS_META_TYPE_VIRT_DIR):continue
            path=('' if parent=='/' else parent)+'/'+rawname.decode('utf-8','surrogateescape');count+=1
            if count>MAX_PATHS:raise GmsApexError('APEX path count exceeded')
            if meta.type==vintf.pytsk3.TSK_FS_META_TYPE_DIR:
                stack.append((path,int(meta.addr),depth+1));continue
            if meta.type==vintf.pytsk3.TSK_FS_META_TYPE_LNK:
                if len(links)>=MAX_APKS:raise GmsApexError('APEX symlink count exceeded')
                links.append({'path':path,'target':bytes(meta.link).decode('utf-8','surrogateescape') if meta.link is not None else None});continue
            if meta.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG or not path.lower().endswith('.apk'):continue
            if len(results)>=MAX_APKS:raise GmsApexError('APEX APK count exceeded')
            size=int(meta.size)
            try:
                sha=apex.copy_tsk_entry(entry,size,temporary,scan.MAX_APK_BYTES)
                if pre.digest_file(temporary)!=(size,sha):raise GmsApexError('APEX APK readback mismatch')
                package,method=scan.package_from_apk(temporary,aapt,aapt2)
                results.append({'path':path,'bytes':size,'sha256':sha,'package':package,'reader':method})
            finally:temporary.unlink(missing_ok=True)
    return {'paths_checked':count,'apk_count':len(results),'apks':sorted(results,key=lambda x:x['path']),
            'gms_package_found':any(x['package']=='com.google.android.gms' for x in results),
            'symlinks_not_followed':links}


def inspect_apex(package: Path,aapt: str,aapt2: str,scratch: Path,erofs_inspector=None) -> dict:
    if not scratch.is_dir() or any(scratch.iterdir()):raise GmsApexError('APEX scratch must be empty')
    before=pre.digest_file(package)
    if not 0<before[0]<=MAX_APEX:raise GmsApexError('APEX size exceeds bounds')
    tool1=scan._tool_digest(aapt);tool2=scan._tool_digest(aapt2)
    if tool1==tool2:raise GmsApexError('Distinct manifest readers required')
    with zipfile.ZipFile(package) as z:
        infos=z.infolist();names=[x.filename for x in infos]
        if len(infos)>apex.MAX_MEMBERS or len(names)!=len(set(names)):raise GmsApexError('Ambiguous APEX ZIP entries')
        members=[{'name':x.filename,'bytes':x.file_size} for x in infos]
    payload=scratch/'apex_payload.img'
    # Existing extractor enforces its own 256 MiB payload bound and ZIP CRC.
    meta=apex.extract_payload(package,payload);fmt=apex.payload_format(payload)
    data={'apex_bytes':before[0],'apex_sha256':before[1],'zip_members':members,
          'payload':{**meta,'filesystem':fmt},'aapt_sha256':tool1,'aapt2_sha256':tool2,
          'apex_signature_verified':False,'runtime_activation_tested':False,
          'limitations':['Hashes and ZIP CRC do not authenticate APEX signatures or Google provenance.',
                         'Contents on disk do not prove APEX activation, permissions, Play Services functionality or device certification.',
                         'Symlinks, other APEX files, dynamically installed updates and device data are not inspected.']}
    if fmt=='ext4':
        apks=scratch/'apks';apks.mkdir();data['payload']['contents']=inspect_ext4(payload,aapt,aapt2,apks)
        data['status']='READ_ONLY_APEX_CONTENTS_INSPECTED_HOLD'
    elif fmt=='erofs' and erofs_inspector is not None:
        data['payload']['contents']=erofs_inspector(payload)
        if data['payload']['contents']['input_sha256']!=meta['sha256']:
            raise GmsApexError('Isolated EROFS input differs from verified payload')
        data['status']='READ_ONLY_APEX_CONTENTS_INSPECTED_HOLD'
    else:
        data['status']='INCOMPLETE_UNSUPPORTED_APEX_FILESYSTEM_HOLD'
    if pre.digest_file(payload)!=(meta['bytes'],meta['sha256']) or pre.digest_file(package)!=before:
        raise GmsApexError('APEX or extracted payload changed during inspection')
    if (tool1,tool2)!=(scan._tool_digest(aapt),scan._tool_digest(aapt2)):raise GmsApexError('Readers changed during audit')
    return data


def run(work: Path,aapt: str,aapt2: str,otatools: Path | None=None) -> dict:
    if not work.is_dir() or any(work.iterdir()):raise GmsApexError('Work directory must be empty')
    sandbox=controls=None
    if otatools is not None:
        sandbox,controls=erofs.setup(otatools,work,aapt,aapt2)
        print('Isolated EROFS and independent manifest reader controls passed',flush=True)
    source=pre.download_candidate(work)
    lock=json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text());specs=vintf.part_specs(lock)
    image=work/'product.img'
    with zipfile.ZipFile(source) as z,z.open('super.img') as stream,image.open('xb') as out:
        prefix=stream.read(vintf.lp.MAX_PREFIX);windows=vintf.extent_windows(prefix,vintf.SUPER_BYTES,specs)
        vintf.copy_windows(stream,prefix,windows,{'product':out},vintf.SUPER_BYTES,pre.SUPER_SHA256)
    expected=(windows['product']['bytes'],windows['product']['sha256'])
    if pre.digest_file(image)!=expected:raise GmsApexError('Product extent failed verification')
    raw=vintf.pytsk3.Img_Info(str(image));fs=vintf.pytsk3.FS_Info(raw)
    if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:raise GmsApexError('Product is not ext4')
    entry=fs.open(path=APEX_PATH);m=entry.info.meta
    if m is None or m.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG:raise GmsApexError('APEX is not an ordinary file')
    package=work/'gmssystem.apex';sha=apex.copy_tsk_entry(entry,int(m.size),package,MAX_APEX)
    if pre.digest_file(package)!=(int(m.size),sha):raise GmsApexError('Extracted APEX failed readback')
    scratch=work/'apex-scratch';scratch.mkdir()
    def inspect_erofs(payload):
        raw_result=erofs.extract_raw(sandbox,payload,control=False)
        return erofs.decode_apks(raw_result,aapt,aapt2,work/'reader-scratch')
    result=inspect_apex(package,aapt,aapt2,scratch,inspect_erofs if sandbox is not None else None)
    if controls is not None:result['erofs_controls']=controls
    if pre.digest_file(image)!=expected or pre.digest_file(source)!=(pre.SOURCE_SIZE,pre.SOURCE_SHA256):
        raise GmsApexError('Source or product image changed during audit')
    result.update(schema='synthetica-gmssystem-apex-v1',source_candidate03_sha256=pre.SOURCE_SHA256,
                  apex_path='product:'+APEX_PATH,input_images_unchanged=True)
    return result


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path);p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True)
    p.add_argument('--otatools',type=Path,help='Pinned AOSP otatools for isolated EROFS; omitted means EROFS remains incomplete')
    a=p.parse_args()
    try:
        result=run(a.work,a.aapt,a.aapt2,a.otatools);code=0 if result['status']=='READ_ONLY_APEX_CONTENTS_INSPECTED_HOLD' else 1
    except (GmsApexError,erofs.GmsErofsError,erofs.check.CheckAuditError,erofs.erofs.ErofsAuditError,
            apex.ApexAuditError,scan.PackageScanError,pre.PreflightError,vintf.VintfAuditError,
            guard.AuditError,OSError,ValueError,zipfile.BadZipFile,RuntimeError) as exc:
        result={'schema':'synthetica-gmssystem-apex-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
