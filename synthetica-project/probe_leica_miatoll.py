#!/usr/bin/env python3
"""Inspect a pinned public miatoll Leica prebuilt as data, never install it.

Two Git blobs are reassembled only in disposable scratch and validated against
pinned object identities. Manifest and signature inspection is host-only; no
claim of authorship, distribution rights, camera HAL compatibility or device
functionality is made. No APK or image is uploaded by this script.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import zipfile
import preflight_spatialflow as pre
import apk_signer_output as signer_output
import scan_apk_packages as scan
import verify_preservation as guard

REPO='AbdoAhmedElbanaa/android_vendor_xiaomi_leicacamera_miatoll'
SOURCE_COMMIT='2582e3859181d32372a669f0cdaad151095b8a53'
PARTS=(('00',68_157_440,'605d07cdc014be5befea4a4a44beadea9bb8adaa'),
       ('01',59_721_192,'c0c55420cfc1183b2d2c48ea4f79d32c230684e0'))
MAX_APK=sum(x[1] for x in PARTS)
MAX_UNCOMPRESSED=1024*1024*1024
MAX_MEMBER=256*1024*1024
CHUNK=4*1024*1024

class LeicaProbeError(RuntimeError):pass


def part_identity(path: Path,size: int,expected: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{40}',expected) or size<=0:raise LeicaProbeError('Invalid pinned Git blob identity')
    sha1=hashlib.sha1();sha1.update(f'blob {size}\0'.encode('ascii'));sha256=hashlib.sha256();count=0
    with guard._open_regular(path)[0] as f:
        before=guard._snapshot(os.fstat(f.fileno()))
        while block:=f.read(CHUNK):
            count+=len(block)
            if count>size:raise LeicaProbeError('Pinned blob exceeds expected size')
            sha1.update(block);sha256.update(block)
        guard._check_unchanged(path,f,before)
    if count!=size or sha1.hexdigest()!=expected:raise LeicaProbeError('Git blob hash or size differs from pin')
    return sha256.hexdigest()


def download_part(work: Path,name: str,size: int,blob: str) -> Path:
    if not re.fullmatch(r'[0-9]{2}',name) or not re.fullmatch(r'[0-9a-f]{40}',blob) or not 0<size<=MAX_APK:
        raise LeicaProbeError('Unsafe pinned blob request')
    dest=work/('camera-part-'+name)
    if dest.exists() or dest.is_symlink():raise LeicaProbeError('Blob output already exists')
    endpoint=f'repos/{REPO}/git/blobs/{blob}'
    def limit():resource.setrlimit(resource.RLIMIT_FSIZE,(size+1,size+1))
    try:
        with dest.open('xb') as out:
            proc=subprocess.run(['gh','api','-H','Accept: application/vnd.github.raw+json',endpoint],
                                stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.DEVNULL,
                                timeout=600,preexec_fn=limit,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:raise LeicaProbeError('Pinned blob download failed or timed out') from exc
    if proc.returncode!=0:raise LeicaProbeError(f'Git blob download failed (exit {proc.returncode})')
    part_identity(dest,size,blob);return dest


def assemble(parts: list[tuple[Path,int,str]],dest: Path) -> tuple[dict,list[dict]]:
    if not parts or dest.exists() or dest.is_symlink():raise LeicaProbeError('Unsafe APK assembly inputs')
    h=hashlib.sha256();total=0;rows=[]
    with dest.open('xb') as out:
        for path,size,blob in parts:
            sha=part_identity(path,size,blob);rows.append({'git_blob_sha1':blob,'bytes':size,'sha256':sha})
            with guard._open_regular(path)[0] as f:
                before=guard._snapshot(os.fstat(f.fileno()));count=0
                while block:=f.read(CHUNK):
                    count+=len(block);total+=len(block)
                    if count>size or total>MAX_APK:raise LeicaProbeError('Part exceeded expected size')
                    h.update(block);out.write(block)
                guard._check_unchanged(path,f,before)
                if count!=size:raise LeicaProbeError('Part changed during assembly')
        out.flush();os.fsync(out.fileno())
    digest=h.hexdigest()
    if pre.digest_file(dest)!=(total,digest):raise LeicaProbeError('Assembled APK failed readback')
    for (path,size,blob),row in zip(parts,rows):
        if part_identity(path,size,blob)!=row['sha256']:raise LeicaProbeError('Blob changed during assembly')
    return {'bytes':total,'sha256':digest},rows


def apk_signature(apk: Path,apksigner: str) -> dict:
    tool_hash=scan._tool_digest(apksigner)
    env={k:v for k,v in os.environ.items() if not re.search(r'(TOKEN|SECRET|PASSWORD|CREDENTIAL)',k,re.I)}
    try:p=subprocess.run([apksigner,'verify','--verbose','--print-certs',str(apk)],stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300,env=env,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:raise LeicaProbeError('Signature tool did not complete') from exc
    if len(p.stdout)+len(p.stderr)>4*1024*1024:raise LeicaProbeError('Signature output exceeds bounds')
    out=p.stdout.decode('utf-8','replace')
    certs=signer_output.parse_certificates(out)
    schemes=signer_output.parse_schemes(out)
    if scan._tool_digest(apksigner)!=tool_hash:raise LeicaProbeError('Signature tool changed')
    diagnostic=signer_output.unparsed_signer_certificate_lines(out)
    certificate=certs[0] if len(certs)==1 and not diagnostic else None
    testkey=signer_output.matches_aosp_public_testkey(certificate)
    public_dev_key=signer_output.aosp_public_development_certificate_name(certificate)
    return {'verifier_exit_code':p.returncode,'signature_verified_on_host':p.returncode==0 and len(certs)==1 and not diagnostic,
            'signer_count':len(certs),'certificate_sha256':certificate,'schemes_reported':schemes,
            'matches_aosp_public_development_testkey':testkey,
            'known_aosp_public_development_certificate_name':public_dev_key,
            'production_key_gate':'REJECT_PUBLIC_TESTKEY' if public_dev_key is not None else 'NOT_ASSESSED',
            'unparsed_certificate_digest_lines':diagnostic,
            'tool_script_sha256':tool_hash,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'signer_authority_or_platform_trust_verified':False}


def inspect(apk: Path,identity: dict,aapt: str,aapt2: str,apksigner: str) -> dict:
    if pre.digest_file(apk)!=(identity['bytes'],identity['sha256']):raise LeicaProbeError('Input APK failed identity check')
    tool1,tool2=scan._tool_digest(aapt),scan._tool_digest(aapt2)
    if tool1==tool2:raise LeicaProbeError('Two distinct manifest readers required')
    with zipfile.ZipFile(apk) as z:
        members=z.infolist();names=[x.filename for x in members]
        if len(members)>100_000 or len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1:
            raise LeicaProbeError('Ambiguous APK archive')
        if any(x.flag_bits & 1 or x.file_size>MAX_MEMBER for x in members) or sum(x.file_size for x in members)>MAX_UNCOMPRESSED:
            raise LeicaProbeError('APK archive exceeds bounded unpacked size')
        if not 0<z.getinfo('AndroidManifest.xml').file_size<=scan.MAX_MANIFEST_BYTES:
            raise LeicaProbeError('APK manifest exceeds bounds')
        broken=z.testzip()
        if broken is not None:raise LeicaProbeError('APK ZIP CRC failure')
        native=[x.filename for x in members if re.fullmatch(r'lib/[^/]+/[^/]+\.so',x.filename)]
        abis=sorted(set(x.split('/')[1] for x in native))
        manifest=z.read('AndroidManifest.xml')
    package,method=scan.package_from_apk(apk,aapt,aapt2)
    xml1=scan._run_tool([aapt,'dump','xmltree',str(apk),'AndroidManifest.xml'])
    xml2=scan._run_tool([aapt2,'dump','xmltree','--file','AndroidManifest.xml',str(apk)])
    if xml1.returncode or xml2.returncode:raise LeicaProbeError('Both independent manifest readers must complete')
    first=scan.parse_xmltree_package(xml1.stdout.decode('utf-8','replace'))
    second=scan.parse_xmltree_package(xml2.stdout.decode('utf-8','replace'))
    if first!=package or second!=package:raise LeicaProbeError('APK package readers disagree')
    badging_result=scan._run_tool([aapt,'dump','badging',str(apk)])
    code=badging_result.returncode;badging=badging_result.stdout.decode('utf-8','replace')
    version=re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'",badging,re.M) if code==0 else None
    sdk=re.search(r"^sdkVersion:'([0-9]+)'",badging,re.M) if code==0 else None
    target=re.search(r"^targetSdkVersion:'([0-9]+)'",badging,re.M) if code==0 else None
    permissions=sorted(set(re.findall(r"^uses-permission: name='([^']+)'",badging,re.M))) if code==0 else []
    if len(permissions)>200:raise LeicaProbeError('Permission metadata exceeded bounds')
    signature=apk_signature(apk,apksigner)
    if pre.digest_file(apk)!=(identity['bytes'],identity['sha256']) or (tool1,tool2)!=(scan._tool_digest(aapt),scan._tool_digest(aapt2)):
        raise LeicaProbeError('APK or reader changed during audit')
    return {'apk':identity,'manifest_sha256':hashlib.sha256(manifest).hexdigest(),'manifest_bytes':len(manifest),
            'package':package,'manifest_reader':method,'independent_xml_readers_agree':True,'badging_exit':code,'version_code':version.group(2) if version else None,
            'version_name':version.group(3) if version else None,'min_sdk':int(sdk.group(1)) if sdk else None,
            'target_sdk':int(target.group(1)) if target else None,'permissions_declared':permissions,
            'zip_entries':len(members),'all_zip_member_crc_checked':True,
            'native_libs_in_apk':len(native),'native_abis_in_apk':abis,'apk_signature':signature,
            'aapt_sha256':tool1,'aapt2_sha256':tool2}


def run(work: Path,aapt: str,aapt2: str,apksigner: str) -> dict:
    if not work.is_dir() or work.is_symlink() or any(work.iterdir()):raise LeicaProbeError('Scratch must be empty and not a symlink')
    source=[]
    for name,size,blob in PARTS:
        path=download_part(work,name,size,blob);source.append((path,size,blob));print(f'Pinned source blob {name} verified',flush=True)
    apk=work/'MiuiCamera.apk';identity,rows=assemble(source,apk)
    if identity['bytes']!=MAX_APK:raise LeicaProbeError('Reconstructed APK length mismatch')
    result=inspect(apk,identity,aapt,aapt2,apksigner)
    return {'schema':'synthetica-leica-miatoll-prebuilt-probe-v1','status':'READ_ONLY_PREBUILT_INSPECTED_HOLD',
            'source_repo':REPO,'source_commit':SOURCE_COMMIT,'commit_signature_verified':False,'source_parts':rows,
            'inspection':result,'limitations':['Git blob identity is not proof of author, copyright permission or trusted release provenance.',
                'No APK, library, image or device was changed, installed, executed or published.',
                'A manifest or valid signature does not prove platform-key trust, camera HAL compatibility, sensor support or functionality.',
                'A match to the public AOSP development testkey is not an authenticated publisher and is rejected for production integration.',
                'The source blueprint declares privileged apps and platform signing; those prerequisites were not satisfied by this probe.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True);p.add_argument('--apksigner',required=True);a=p.parse_args()
    try:result=run(a.work,a.aapt,a.aapt2,a.apksigner);code=0
    except (LeicaProbeError,scan.PackageScanError,pre.PreflightError,guard.AuditError,
            OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-leica-miatoll-prebuilt-probe-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
