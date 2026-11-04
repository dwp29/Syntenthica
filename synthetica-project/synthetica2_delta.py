#!/usr/bin/env python3
"""Create/verify/restore a compact, NON-FLASHABLE Synthetica research delta.

Self-contained standard-library tool: the original private ROM ZIP remains the
source of unchanged bytes. The delta contains only changed 4 KiB super blocks,
a candidate boot image, small documentation, and this script. Verification
reconstructs super as a stream without writing the 8 GiB image. Restore writes
only the inert research ZIP and requires matching source and delta SHA-256.
Never flash the result; neither AVB nor kernel/module compatibility is proven.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zipfile
import zlib

SOURCE_SIZE = 4512854711
SOURCE_SHA = '454580f463e7f6ac922546075a2a033c6dc2fac3275e450573635a1ca7b0ec63'
SUPER_SIZE = 8589934592
SUPER_SHA = '2e440cfc9023c23c75a1ade13c8d1c32666ff8f3b253d4d7c4f245dd9540f6bf'
WINDOWS = [(1048576,3892736000),(3893362688,5626232832)]
BOOT_SHA = 'ba4c2db0e2cfc5ba1c0a365f3582b9daabcc401f5fd746367584a53855a5bb22'
DTBO_SHA = '9c1cd10bce76b257529e13e3577ecb0f9a195fea95e7b628bdf81bc3daa05ff2'
SUPER_NAME = 'DO-NOT-FLASH/super-candidate.img'
BOOT_NAME = 'DO-NOT-FLASH/boot-candidate.img'
DTBO_NAME = 'DO-NOT-FLASH/dtbo-original.img'
DOCS = ['README-DO-NOT-FLASH.txt','META-INF/com/google/android/update-binary',
        'META-INF/com/google/android/updater-script','audit/integration-report.json',
        'audit/super-stream-report.json','licenses/StevenBlack-LICENSE.txt']
INSTALLER = b'#!/sbin/sh\necho "DO NOT FLASH: host-only research archive; installer disabled" >&2\nexit 1\n'
UPDATER = b'abort("DO NOT FLASH: host-only research archive; installer disabled");\n'
MAGIC = b'SYNTH2-SUPER-DELTA-v1\n'
HEADER = struct.Struct('<QI')
BLOCK = 4096
CHUNK = 4 * 1024 * 1024
MAX_CHANGED_BYTES = 512 * 1024 * 1024
README = '''SYNTHETICA 2.0 -- DELTA RISET PARSIAL, JANGAN FLASH

Paket ini menghemat ruang karena menyimpan hanya blok super yang berubah,
kandidat boot dan dokumen. ROM asli TIDAK disertakan. Hasil restorasi adalah
arsip riset yang installernya selalu berhenti; bukan ROM recovery siap pakai.
AVB, tanda tangan modul, kompatibilitas ABI, boot dan semua fitur belum terbukti.
SpatialFlow tidak ditambahkan. Jangan flash secara manual atau melalui recovery.

Alat mandiri: tools/synthetica2_delta.py (Python 3, pustaka standar). Gunakan
ROM asli yang cocok SHA pada manifest dan SHA-256 paket delta yang diberikan
terpisah. Verifikasi: python3 synthetica2_delta.py verify --original ORIGINAL.zip
--delta DELTA.zip --delta-sha256 SHA256 --candidate KANDIDAT.zip
Restorasi: python3 synthetica2_delta.py restore --original ORIGINAL.zip --delta
DELTA.zip --delta-sha256 SHA256 --output DO-NOT-FLASH-RESTORED.zip
Paket dan ROM mengandung firmware privat; jangan publikasikan tanpa izin.
'''.encode('utf-8')


class DeltaError(ValueError): pass


def sha_file(path: Path) -> tuple[int,str]:
    if path.is_symlink() or not path.is_file():raise DeltaError('expected regular file: '+str(path))
    h=hashlib.sha256();size=0
    with path.open('rb') as f:
        while b:=f.read(CHUNK):h.update(b);size+=len(b)
    return size,h.hexdigest()


def read_exact(src, count: int) -> bytes:
    pieces=[]
    while count:
        b=src.read(count)
        if not b or len(b)>count:raise DeltaError('stream truncated or overlong')
        pieces.append(b);count-=len(b)
    return b''.join(pieces)


def zip_info(name: str, size=0) -> zipfile.ZipInfo:
    zi=zipfile.ZipInfo(name,(2026,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED
    zi.create_system=3;zi.external_attr=0o100644 << 16;zi.file_size=size
    return zi


def in_window(start: int, end: int, windows: list[tuple[int,int]]) -> bool:
    return any(a<=start<end<=b for a,b in windows)


def build_diff(old, new, patch, size: int, windows: list[tuple[int,int]], block=BLOCK, chunk=CHUNK) -> dict:
    if size<=0 or block<=0 or chunk<block or chunk%block or size%block:raise DeltaError('invalid diff dimensions')
    h_old=hashlib.sha256();h_new=hashlib.sha256();h_patch=hashlib.sha256()
    patch.write(MAGIC);h_patch.update(MAGIC)
    records=changed=0
    def emit(offset, payload):
        nonlocal records,changed
        end=offset+len(payload)
        if not in_window(offset,end,windows):raise DeltaError('changes escape allowed product/system extents')
        records+=1;changed+=len(payload)
        if changed>MAX_CHANGED_BYTES:raise DeltaError('delta is unexpectedly large')
        header=HEADER.pack(offset,len(payload));patch.write(header);patch.write(payload)
        h_patch.update(header);h_patch.update(payload)
    for position in range(0,size,chunk):
        n=min(chunk,size-position);a=read_exact(old,n);b=read_exact(new,n)
        h_old.update(a);h_new.update(b)
        if a==b:continue
        run_start=None
        for i in range(0,n,block):
            differs=a[i:i+block]!=b[i:i+block]
            if differs and run_start is None:run_start=i
            if not differs and run_start is not None:
                emit(position+run_start,b[run_start:i]);run_start=None
        if run_start is not None:emit(position+run_start,b[run_start:n])
    if old.read(1) or new.read(1):raise DeltaError('super stream exceeds expected size')
    return {'record_count':records,'changed_bytes':changed,'block_bytes':block,'chunk_bytes':chunk,
            'patch_sha256':h_patch.hexdigest(),'source_super_sha256':h_old.hexdigest(),
            'candidate_super_sha256':h_new.hexdigest(),'super_bytes':size}


def apply_diff(source, patch, dest, report: dict, windows: list[tuple[int,int]], compare=None) -> None:
    size,block,chunk=report['super_bytes'],report['block_bytes'],report['chunk_bytes']
    count=report['record_count']
    if (not all(isinstance(v,int) for v in (size,block,chunk,count)) or size<=0 or block<=0
            or chunk<block or chunk%block or size%block or not 0<=count<=size//block):
        raise DeltaError('invalid patch dimensions')
    h_old=hashlib.sha256();h_new=hashlib.sha256();h_patch=hashlib.sha256()
    magic=read_exact(patch,len(MAGIC));h_patch.update(magic)
    if magic!=MAGIC:raise DeltaError('patch magic differs')
    index=0;previous_end=0;changed=0
    def next_record():
        nonlocal index,previous_end,changed
        if index==count:return None
        header=read_exact(patch,HEADER.size);h_patch.update(header)
        offset,length=HEADER.unpack(header)
        if (not length or length>chunk or length%block or offset%block or offset<previous_end or offset+length>size
                or offset//chunk!=(offset+length-1)//chunk or not in_window(offset,offset+length,windows)):
            raise DeltaError('unsafe, overlapping or out-of-window patch record')
        data=read_exact(patch,length);h_patch.update(data);index+=1;previous_end=offset+length;changed+=length
        if changed>MAX_CHANGED_BYTES:raise DeltaError('patch exceeds changed byte limit')
        return offset,data
    record=next_record()
    for position in range(0,size,chunk):
        n=min(chunk,size-position);old=read_exact(source,n);h_old.update(old);new=bytearray(old)
        while record is not None and record[0]<position+n:
            offset,data=record
            if offset<position or offset+len(data)>position+n:raise DeltaError('patch record crosses a chunk')
            new[offset-position:offset-position+len(data)]=data
            record=next_record()
        h_new.update(new)
        if compare is not None and read_exact(compare,n)!=new:raise DeltaError('reconstructed super differs from candidate')
        if dest is not None:dest.write(new)
    if record is not None or source.read(1) or patch.read(1) or (compare is not None and compare.read(1)):
        raise DeltaError('unexpected bytes at end of patch or super')
    if (changed!=report['changed_bytes'] or h_patch.hexdigest()!=report['patch_sha256']
            or h_old.hexdigest()!=report['source_super_sha256'] or h_new.hexdigest()!=report['candidate_super_sha256']):
        raise DeltaError('reconstructed stream or patch hash differs')


def read_member(z, name, limit):
    infos=[i for i in z.infolist() if i.filename==name]
    if len(infos)!=1 or infos[0].file_size>limit:raise DeltaError('missing, duplicate or oversized member: '+name)
    return z.read(name)


def checked_original(path: Path):
    if sha_file(path)!=(SOURCE_SIZE,SOURCE_SHA):raise DeltaError('original ZIP differs from locked SHA and size')


def copy_member(src, dst) -> tuple[int,str]:
    h=hashlib.sha256();size=0
    while b:=src.read(CHUNK):dst.write(b);h.update(b);size+=len(b)
    return size,h.hexdigest()


def create(original: Path, candidate: Path, output: Path) -> dict:
    if 'DO-NOT-FLASH' not in output.name or output.suffix.lower()!='.zip' or output.exists() or output.is_symlink():
        raise DeltaError('choose a new DO-NOT-FLASH delta ZIP')
    checked_original(original);cand_size,cand_sha=sha_file(candidate)
    tmp=output.with_name(output.name+'.INCOMPLETE')
    if tmp.exists() or tmp.is_symlink():raise DeltaError('incomplete output already exists')
    created=False
    try:
        with zipfile.ZipFile(original) as base,zipfile.ZipFile(candidate) as candidate_zip,zipfile.ZipFile(tmp,'x',allowZip64=True) as delta:
            created=True
            expected={SUPER_NAME,BOOT_NAME,DTBO_NAME,*DOCS}
            if {x.filename for x in candidate_zip.infolist()}!=expected or len(candidate_zip.infolist())!=len(expected):
                raise DeltaError('candidate member set differs')
            if read_member(candidate_zip,DOCS[1],4096)!=INSTALLER or read_member(candidate_zip,DOCS[2],4096)!=UPDATER:
                raise DeltaError('candidate installer is not inert')
            integration=json.loads(read_member(candidate_zip,'audit/integration-report.json',1024*1024))
            super_report=json.loads(read_member(candidate_zip,'audit/super-stream-report.json',1024*1024))
            if (integration.get('status')!='INTEGRATED_IMAGES_NOT_FOR_FLASH' or integration.get('flashable') is not False
                    or super_report.get('source_sha256')!=SUPER_SHA or super_report.get('bytes')!=SUPER_SIZE):
                raise DeltaError('candidate provenance does not match locked original')
            if base.getinfo('super.img').file_size!=SUPER_SIZE or candidate_zip.getinfo(SUPER_NAME).file_size!=SUPER_SIZE:
                raise DeltaError('super size differs')
            with base.open('super.img') as old,candidate_zip.open(SUPER_NAME) as new,delta.open(zip_info('delta/super.patch'),'w',force_zip64=True) as patch:
                report=build_diff(old,new,patch,SUPER_SIZE,WINDOWS)
            if report['source_super_sha256']!=SUPER_SHA or report['candidate_super_sha256']!=super_report['output_sha256']:
                raise DeltaError('super hash differs from reports')
            with base.open('dtbo.img') as a,candidate_zip.open(DTBO_NAME) as b:
                ah=hashlib.sha256();bh=hashlib.sha256();size=0
                while data:=a.read(CHUNK):
                    other=read_exact(b,len(data));ah.update(data);bh.update(other);size+=len(data)
                    if data!=other:raise DeltaError('candidate dtbo differs from original')
                if b.read(1) or size!=25165824 or ah.hexdigest()!=DTBO_SHA or bh.hexdigest()!=DTBO_SHA:
                    raise DeltaError('dtbo integrity differs')
            member_specs={}
            for name in [BOOT_NAME,*DOCS]:
                limit=32*1024*1024 if name==BOOT_NAME else 2*1024*1024
                data=read_member(candidate_zip,name,limit)
                h=hashlib.sha256(data).hexdigest()
                if name==BOOT_NAME and (len(data)!=16703488 or h!=BOOT_SHA):raise DeltaError('candidate boot differs')
                member_specs[name]={'bytes':len(data),'sha256':h}
                delta.writestr(zip_info('files/'+name,len(data)),data)
            source=Path(__file__).read_bytes()
            manifest={'schema':'synthetica2-sparse-delta-v1','status':'DO_NOT_FLASH',
                      'source_zip_bytes':SOURCE_SIZE,'source_zip_sha256':SOURCE_SHA,
                      'candidate_zip_bytes':cand_size,'candidate_zip_sha256':cand_sha,
                      'windows':[list(w) for w in WINDOWS],'patch':report,'members':member_specs,
                      'tool_sha256':hashlib.sha256(source).hexdigest(), 'zip_zlib_version':zlib.ZLIB_VERSION,
                      'flashable':False,'device_tested':False,'spatialflow_added':False}
            docs={'README-DO-NOT-FLASH.txt':README,'manifest.json':json.dumps(manifest,indent=2,sort_keys=True).encode()+b'\n',
                  'tools/synthetica2_delta.py':source}
            for name,data in docs.items():delta.writestr(zip_info(name,len(data)),data)
        size,digest=sha_file(tmp)
        verify(original,tmp,digest,candidate)
        os.rename(tmp,output)
        return {'status':'VERIFIED_DELTA_NOT_FOR_FLASH','output':str(output),'bytes':size,'sha256':digest,
                'original_sha256':SOURCE_SHA,'candidate_sha256':cand_sha,'patch':report,
                'flashable':False,'device_tested':False,'source_unchanged':True}
    except BaseException:
        if created and tmp.is_file() and not tmp.is_symlink():tmp.unlink()
        raise


def open_manifest(delta: zipfile.ZipFile) -> dict:
    m=json.loads(read_member(delta,'manifest.json',1024*1024))
    expected={'delta/super.patch','README-DO-NOT-FLASH.txt','manifest.json','tools/synthetica2_delta.py',
              *('files/'+name for name in [BOOT_NAME,*DOCS])}
    if {x.filename for x in delta.infolist()}!=expected or len(delta.infolist())!=len(expected):raise DeltaError('delta member set differs')
    if (m.get('schema')!='synthetica2-sparse-delta-v1' or m.get('status')!='DO_NOT_FLASH' or m.get('flashable') is not False
            or m.get('source_zip_bytes')!=SOURCE_SIZE or m.get('source_zip_sha256')!=SOURCE_SHA
            or m.get('windows')!=[list(w) for w in WINDOWS]):raise DeltaError('delta manifest is invalid')
    p=m['patch']
    if (p['super_bytes']!=SUPER_SIZE or p['source_super_sha256']!=SUPER_SHA or p['block_bytes']!=BLOCK or p['chunk_bytes']!=CHUNK
            or not 0<=p['changed_bytes']<=MAX_CHANGED_BYTES):raise DeltaError('patch dimensions or source differs')
    if hashlib.sha256(read_member(delta,'tools/synthetica2_delta.py',1024*1024)).hexdigest()!=m['tool_sha256']:
        raise DeltaError('embedded tool hash differs')
    if read_member(delta,'files/'+DOCS[1],4096)!=INSTALLER or read_member(delta,'files/'+DOCS[2],4096)!=UPDATER:
        raise DeltaError('delta does not contain inert installer')
    for name in [BOOT_NAME,*DOCS]:
        spec=m['members'][name];limit=32*1024*1024 if name==BOOT_NAME else 2*1024*1024
        data=read_member(delta,'files/'+name,limit)
        if (len(data),hashlib.sha256(data).hexdigest())!=(spec['bytes'],spec['sha256']):raise DeltaError('payload member differs: '+name)
    if m['members'][BOOT_NAME]['sha256']!=BOOT_SHA:raise DeltaError('boot pin differs')
    return m


def verify(original: Path, delta_path: Path, delta_sha: str, candidate: Path | None = None) -> dict:
    if len(delta_sha)!=64 or any(c not in '0123456789abcdef' for c in delta_sha):raise DeltaError('delta SHA must be lowercase hexadecimal')
    checked_original(original)
    if sha_file(delta_path)[1]!=delta_sha:raise DeltaError('delta SHA differs')
    with zipfile.ZipFile(original) as base,zipfile.ZipFile(delta_path) as delta:
        m=open_manifest(delta)
        if candidate is not None and sha_file(candidate)!=(m['candidate_zip_bytes'],m['candidate_zip_sha256']):
            raise DeltaError('candidate ZIP differs')
        with base.open('super.img') as src,delta.open('delta/super.patch') as patch:
            if candidate is None:apply_diff(src,patch,None,m['patch'],WINDOWS)
            else:
                with zipfile.ZipFile(candidate) as z,z.open(SUPER_NAME) as comparison:
                    apply_diff(src,patch,None,m['patch'],WINDOWS,comparison)
        # Reading every remaining member to EOF checks every delta CRC.
        for entry in delta.infolist():
            if entry.filename=='delta/super.patch':continue
            with delta.open(entry) as src:
                while src.read(CHUNK):pass
    return {'status':'DELTA_VERIFIED_DO_NOT_FLASH','source_zip_sha256':SOURCE_SHA,'delta_sha256':delta_sha,
            'candidate_super_sha256':m['patch']['candidate_super_sha256'],
            'candidate_compared':candidate is not None,'patch_changed_bytes':m['patch']['changed_bytes'],
            'device_tested':False,'flashable':False}


def restore(original: Path, delta_path: Path, delta_sha: str, output: Path) -> dict:
    if 'DO-NOT-FLASH' not in output.name or output.suffix.lower()!='.zip' or output.exists() or output.is_symlink():
        raise DeltaError('choose a new DO-NOT-FLASH output ZIP')
    checked_original(original)
    if sha_file(delta_path)[1]!=delta_sha:raise DeltaError('delta SHA differs')
    tmp=output.with_name(output.name+'.INCOMPLETE')
    if tmp.exists() or tmp.is_symlink():raise DeltaError('incomplete output already exists')
    created=False
    try:
        with zipfile.ZipFile(original) as base,zipfile.ZipFile(delta_path) as delta,zipfile.ZipFile(tmp,'x',allowZip64=True) as result:
            created=True;m=open_manifest(delta)
            result.comment=b'DO NOT FLASH: host-only research archive, not signed or device-tested.'
            with base.open('super.img') as src,delta.open('delta/super.patch') as patch,result.open(zip_info(SUPER_NAME,SUPER_SIZE),'w',force_zip64=True) as dst:
                apply_diff(src,patch,dst,m['patch'],WINDOWS)
            for name,source_zip,source_name,expected in [
                (BOOT_NAME,delta,'files/'+BOOT_NAME,(m['members'][BOOT_NAME]['bytes'],BOOT_SHA)),
                (DTBO_NAME,base,'dtbo.img',(25165824,DTBO_SHA))]:
                with source_zip.open(source_name) as src,result.open(zip_info(name,expected[0]),'w',force_zip64=True) as dst:
                    if copy_member(src,dst)!=expected:raise DeltaError('boot/dtbo differs')
            for name in DOCS:
                data=read_member(delta,'files/'+name,2*1024*1024)
                result.writestr(zip_info(name,len(data)),data)
        actual=sha_file(tmp)
        if actual!=(m['candidate_zip_bytes'],m['candidate_zip_sha256']):
            raise DeltaError('restored ZIP bytes differ (possibly a different zlib version); output withheld')
        os.rename(tmp,output)
        return {'status':'RESTORED_IDENTICAL_NOT_FOR_FLASH','output':str(output),'bytes':actual[0],'sha256':actual[1],
                'device_tested':False,'flashable':False}
    except BaseException:
        if created and tmp.is_file() and not tmp.is_symlink():tmp.unlink()
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('create');a.add_argument('--original',required=True,type=Path);a.add_argument('--candidate',required=True,type=Path);a.add_argument('--output',required=True,type=Path)
    a=sub.add_parser('verify');a.add_argument('--original',required=True,type=Path);a.add_argument('--delta',required=True,type=Path);a.add_argument('--delta-sha256',required=True);a.add_argument('--candidate',type=Path)
    a=sub.add_parser('restore');a.add_argument('--original',required=True,type=Path);a.add_argument('--delta',required=True,type=Path);a.add_argument('--delta-sha256',required=True);a.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    try:
        if args.mode=='create':r=create(args.original,args.candidate,args.output)
        elif args.mode=='verify':r=verify(args.original,args.delta,args.delta_sha256,args.candidate)
        else:r=restore(args.original,args.delta,args.delta_sha256,args.output)
        print(json.dumps(r,sort_keys=True));return 0
    except (DeltaError,OSError,ValueError,KeyError,zipfile.BadZipFile,struct.error) as exc:
        print('Synthetica delta: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
