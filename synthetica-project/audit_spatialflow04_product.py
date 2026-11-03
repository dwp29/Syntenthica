#!/usr/bin/env python3
"""Independently inspect two product files in the locked unpublished 04 draft.

Reconstructs the exact three already-verified raw parts in disposable scratch,
streams and hashes the complete super ZIP member, reconstructs its two pinned
product extents, and reads the two fixed files via pytsk3 without mounting.
No APK or image is installed, executed, uploaded or published. Matching hashes
prove byte preservation only, not device trust, runtime activation or boot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

import audit_gms_apex_signatures as gms_signature
import audit_gmssystem_apex as gms
import audit_vintf_candidate as vintf
import preflight_spatialflow as pre
import verify_preservation as guard

OUTPUT_NAME='synthetica-feature-20261103-04-spatialflow.zip'
RELEASE_ID=432276369
TAG='synthetica-feature-spatialflow-04-run-41576967077-1'
RECIPE_COMMIT='69e1972941cba9da90a939af8029da9e03ab2de2'
ZIP_BYTES=4_748_586_175
ZIP_SHA='7aa84e14e1b4e30aa0a70e222c8d9550b4d533c8016aa1f002d17fe460d96df8'
SUPER_SHA='bc7b59d0824bddb63ffa2d1a49b7f1030b3363cbfe7caa7e6fa55ad1839e5f54'
PRODUCT_BYTES=3_925_241_856
PRODUCT_SHA='e8504d1b387ac0dfeca063097ba88efe9b00a6874aad89a9d6443a3cfae50aad'
LP_SHA='a648fde5f228e6dcd9bbaea50be9662612205a938b214b53f6cc9560c85b49e6'
PRODUCT_WINDOWS=((1_048_576,3_892_736_000),(8_525_971_456,8_559_525_888))
APEX_PATH=gms.APEX_PATH
APP_PATH='/app/SpatialFlow/SpatialFlow.apk'
PARTS=(
 (704274886,1_610_612_736,'43bf226564c032384e07d6e2624b1be2113a7507a047081117e4e015cd1e2385'),
 (704277071,1_610_612_736,'30d99f3a41acf977311f66e59c721c80c207c1028ca49ddc9c241647737b747c'),
 (704281287,1_527_360_703,'6a2e6e710ce44694f3a552ea296dc9601fc5cb093f1bdfe399a3859285039c86'),
)
AUX=(
 (704286815,'BUILD-REPORT-SPATIALFLOW-04.json',13781,'93b8ead16e22911d90418c65b2cc52e2e4683244f6c92389603a4738347bc477'),
 (704286879,'MANIFEST-SPATIALFLOW-04.json',1692,'1254356192bd836dcfd1193039c2b28673114eeb62bd0ddbae53381c0c7580b7'),
)
CHUNK=4*1024*1024
MAX_FILE=512*1024*1024
class ProductAuditError(RuntimeError):pass


def release_snapshot(data: dict)->tuple:
    if (not isinstance(data,dict) or data.get('id')!=RELEASE_ID or data.get('tag_name')!=TAG
        or data.get('target_commitish')!=RECIPE_COMMIT or data.get('draft') is not True
        or data.get('prerelease') is not True or not isinstance(data.get('assets'),list)):
        raise ProductAuditError('The pinned 04 draft identity or status changed')
    expected=[(aid,OUTPUT_NAME+f'.{n:03d}',size,sha) for n,(aid,size,sha) in enumerate(PARTS,1)]+list(AUX)
    if len(data['assets'])!=len(expected):raise ProductAuditError('04 draft asset count changed')
    return pre.asset_snapshot(data,expected,draft=True)


def download(work: Path)->Path:
    before=release_snapshot(pre.gh_json(f'repos/{pre.REPO}/releases/{RELEASE_ID}'))
    dest=work/OUTPUT_NAME
    if dest.exists() or dest.is_symlink():raise ProductAuditError('Private reconstruction destination exists')
    combined=hashlib.sha256();total=0;complete=False
    try:
        with dest.open('xb') as out:
            for n,(_,size,sha) in enumerate(PARTS,1):
                name=OUTPUT_NAME+f'.{n:03d}';part=work/name
                if part.exists() or part.is_symlink():raise ProductAuditError('Private part destination exists')
                pre.command(['gh','release','download',TAG,'--repo',pre.REPO,'--pattern',name,'--dir',str(work)])
                with guard._open_regular(part)[0] as f:
                    snap=guard._snapshot(os.fstat(f.fileno()));h=hashlib.sha256();count=0
                    while data:=f.read(CHUNK):
                        count+=len(data);total+=len(data)
                        if count>size or total>ZIP_BYTES:raise ProductAuditError('A part exceeds its pinned size')
                        h.update(data);combined.update(data);out.write(data)
                    guard._check_unchanged(part,f,snap)
                if count!=size or h.hexdigest()!=sha:raise ProductAuditError('A part failed independent SHA-256')
                part.unlink()
                print(f'Verified private 04 part {n}',flush=True)
            out.flush();os.fsync(out.fileno())
        if (total!=ZIP_BYTES or combined.hexdigest()!=ZIP_SHA or pre.digest_file(dest)!=(ZIP_BYTES,ZIP_SHA)
            or release_snapshot(pre.gh_json(f'repos/{pre.REPO}/releases/{RELEASE_ID}'))!=before):
            raise ProductAuditError('Reconstructed 04 archive or release identity changed')
        complete=True;return dest
    finally:
        if not complete:dest.unlink(missing_ok=True)


def check_product_metadata(prefix: bytes,super_bytes: int)->dict:
    layout=vintf.lp.inspect_raw_super(prefix,super_bytes)
    slots=layout.get('metadata_slots')
    if layout.get('geometry_copies_match') is not True or not isinstance(slots,list) or len(slots)!=2:
        raise ProductAuditError('04 LP geometry or slot count differs')
    for slot in slots:
        primary=slot.get('primary',{});parts=primary.get('partitions',[]);devices=primary.get('block_devices',[])
        product=[x for x in parts if x.get('name')=='product']
        if (slot.get('copies_match') is not True or primary.get('header_and_tables_sha256')!=LP_SHA
            or len(devices)!=1 or devices[0].get('name')!='super' or devices[0].get('size_bytes_declared')!=super_bytes
            or len(product)!=1 or product[0].get('bytes')!=PRODUCT_BYTES or product[0].get('extent_count')!=2
            or product[0].get('first_extent')!={'sectors':(PRODUCT_WINDOWS[0][1]-PRODUCT_WINDOWS[0][0])//512,
                 'type':0,'target_sector':PRODUCT_WINDOWS[0][0]//512,'source_index':0}):
            raise ProductAuditError('04 product LP metadata differs from the pinned build')
    # The pinned, checksum-validated complete metadata hash binds the second
    # extent as well; full product and super hashes below independently bind bytes.
    return {'metadata_sha256':LP_SHA,'slots':len(slots),'product_extent_count':2,
            'geometry_and_slot_copies_match':True}


def copy_windows(stream,prefix: bytes,output,windows: tuple,*,total_size: int,total_sha: str,product_size: int,product_sha: str)->dict:
    if (not isinstance(prefix,bytes) or not prefix or type(total_size) is not int or total_size<=0
        or not re.fullmatch(r'[0-9a-f]{64}',total_sha) or not re.fullmatch(r'[0-9a-f]{64}',product_sha)
        or not windows or any(type(a) is not int or type(b) is not int or not 0<=a<b<=total_size for a,b in windows)
        or any(a[1]>b[0] for a,b in zip(windows,windows[1:]))
        or sum(b-a for a,b in windows)!=product_size):raise ProductAuditError('Invalid physical extent bounds')
    entire=hashlib.sha256();product=hashlib.sha256();pos=count=0
    def consume(data):
        nonlocal pos,count
        end=pos+len(data)
        if end>total_size:raise ProductAuditError('Super stream exceeds pinned size')
        entire.update(data)
        for start,stop in windows:
            a,b=max(pos,start),min(end,stop)
            if a<b:
                selected=data[a-pos:b-pos];output.write(selected);product.update(selected);count+=len(selected)
        pos=end
    consume(prefix)
    while data:=stream.read(CHUNK):consume(data)
    output.flush()
    if pos!=total_size or entire.hexdigest()!=total_sha or count!=product_size or product.hexdigest()!=product_sha:
        raise ProductAuditError('Super or reconstructed product did not match pinned identity')
    return {'super_bytes':pos,'super_sha256':entire.hexdigest(),'product_bytes':count,'product_sha256':product.hexdigest(),
            'complete_super_zip_member_crc_checked_at_eof':True}


def inspect_file(fs,path: str,expected_bytes: int,expected_sha: str)->dict:
    if vintf.pytsk3 is None:raise ProductAuditError('Filesystem reader unavailable')
    entry=fs.open(path=path);m=entry.info.meta
    if (m is None or not (m.flags & vintf.pytsk3.TSK_FS_META_FLAG_ALLOC)
        or m.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG or int(m.size)!=expected_bytes or not 0<expected_bytes<=MAX_FILE):
        raise ProductAuditError('Selected path is not the expected allocated regular file: '+path)
    h=hashlib.sha256();pos=0
    while pos<expected_bytes:
        data=entry.read_random(pos,min(CHUNK,expected_bytes-pos))
        if not data or len(data)>expected_bytes-pos:raise ProductAuditError('Short filesystem entry read')
        h.update(data);pos+=len(data)
    if h.hexdigest()!=expected_sha:raise ProductAuditError('Selected file hash differs: '+path)
    return {'path':'product:'+path,'bytes':pos,'sha256':h.hexdigest(),'allocated_regular_file':True}


def run(work: Path)->dict:
    if vintf.pytsk3 is None or not work.is_dir() or work.is_symlink() or any(work.iterdir()):
        raise ProductAuditError('An empty scratch directory and pytsk3 are required')
    archive=download(work);product=work/'product04.img'
    try:
        with zipfile.ZipFile(archive) as z:
            infos=z.infolist();names=[x.filename for x in infos]
            if len(names)!=len(set(names)) or names.count('super.img')!=1:raise ProductAuditError('Ambiguous candidate ZIP')
            info=z.getinfo('super.img')
            if info.file_size!=vintf.SUPER_BYTES or info.flag_bits & 1:raise ProductAuditError('Unexpected super ZIP member')
            with z.open(info) as stream,product.open('xb') as out:
                prefix=stream.read(vintf.lp.MAX_PREFIX);layout=check_product_metadata(prefix,vintf.SUPER_BYTES)
                extracted=copy_windows(stream,prefix,out,PRODUCT_WINDOWS,total_size=vintf.SUPER_BYTES,total_sha=SUPER_SHA,
                                       product_size=PRODUCT_BYTES,product_sha=PRODUCT_SHA)
        if pre.digest_file(product)!=(PRODUCT_BYTES,PRODUCT_SHA):raise ProductAuditError('Product readback differs')
        disk=vintf.pytsk3.Img_Info(str(product));fs=vintf.pytsk3.FS_Info(disk)
        if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:raise ProductAuditError('04 product is not ext4')
        apex_row=inspect_file(fs,APEX_PATH,gms_signature.APEX_BYTES,gms_signature.APEX_SHA256)
        app_row=inspect_file(fs,APP_PATH,pre.APP_SIZE,pre.APP_SHA256)
        if pre.digest_file(product)!=(PRODUCT_BYTES,PRODUCT_SHA) or pre.digest_file(archive)!=(ZIP_BYTES,ZIP_SHA):
            raise ProductAuditError('A private input changed during inspection')
        after=release_snapshot(pre.gh_json(f'repos/{pre.REPO}/releases/{RELEASE_ID}'))
        return {'schema':'synthetica-spatialflow04-product-preservation-v1','status':'READ_ONLY_04_PRODUCT_PRESERVATION_HOLD',
                'candidate04_zip_sha256':ZIP_SHA,'candidate04_release_id':RELEASE_ID,'release_still_draft':True,
                'metadata':layout,'extraction':extracted,'gms_apex_in_04':apex_row,'spatialflow_apk_in_04':app_row,
                'gms_apex_sha_matches_independent_candidate03_audit':True,'spatialflow_sha_matches_pinned_release':True,
                'candidate_and_product_input_unchanged':True,'release_asset_snapshot_count':len(after),
                'limitations':['File hashes establish static byte identity, not installation, signature authority, runtime activation or device trust.',
                               '04 remains unsigned, unpublished and not tested in recovery, AVB, boot, audio or on a device.',
                               'No package, image, release, device or user data was altered or published.']}
    finally:
        product.unlink(missing_ok=True)
        # Only disposable files created by this audit are removed; original draft is untouched.
        archive.unlink(missing_ok=True)


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    try:result=run(a.work);code=0
    except (ProductAuditError,pre.PreflightError,vintf.VintfAuditError,vintf.lp.LPError,guard.AuditError,
            OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-spatialflow04-product-preservation-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
