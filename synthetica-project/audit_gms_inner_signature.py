#!/usr/bin/env python3
"""Verify the previously identified GMS APK inside a pinned APEX, host only.

A modified bounded EROFS launcher exports exactly one hash-pinned APK to a
pre-created, private disposable runner file descriptor; no ROM code executes.
The Android host apksigner reads the file after positive, corrupt and unsigned
controls. The temporary APK is never uploaded, installed or published. A
verified signature is self-consistency only, not Google/device trust or runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import zipfile

import apk_signer_output as signer
import audit_erofs_extract as tool
import audit_gms_erofs as erofs
import audit_gmssystem_apex as gms
import audit_gms_apex_signatures as apex_signature
import audit_runtime_apex as apex
import audit_vintf_candidate as vintf
import preflight_spatialflow as pre
import scan_apk_packages as scan
import verify_preservation as guard

GMS_PATH='/priv-app/PrebuiltGmsCoreVic@263032xxx/PrebuiltGmsCoreVic.apk'
GMS_SIZE=227_669_823
GMS_SHA='05de4f30a39a0db182f50bca1adf82ed2a8c05c09463e1ccddbe9ae95b9301e3'
MAX_APK=256*1024**2
class InnerError(RuntimeError):pass


def _launcher(base: str=erofs._LAUNCHER)->str:
    """Add a single pinned export FD to the already-tested EROFS launcher."""
    changes=[
        ("root, mode = sys.argv[1:3]", "root, mode = sys.argv[1:3]\nexportfd=int(sys.argv[3]);exportpath=sys.argv[4];exportsize=int(sys.argv[5]);exportsha=sys.argv[6]\nif not 3<=exportfd<4096:raise RuntimeError('bad export fd')"),
        ("os.closerange(3,4096)","os.closerange(3,exportfd);os.closerange(exportfd+1,4096)"),
        ("                f.seek(0)\n                with zipfile.ZipFile(f) as z:",'''                f.seek(0)
                if p[len('/out/extracted'):] == exportpath:
                    if st.st_size != exportsize or h.hexdigest() != exportsha:raise RuntimeError('export identity mismatch')
                    written=0
                    while True:
                        chunk=f.read(1024*1024)
                        if not chunk:break
                        view=memoryview(chunk)
                        while view:
                            n=os.write(exportfd,view)
                            if n<=0:raise RuntimeError('short export write')
                            written+=n;view=view[n:]
                    if written!=exportsize:raise RuntimeError('short export')
                    os.fsync(exportfd)
                    result['exported']={'bytes':written,'sha256':exportsha,'path':exportpath}
                    f.seek(0)
                with zipfile.ZipFile(f) as z:''')]
    for old,new in changes:
        if base.count(old)!=1:raise InnerError('EROFS launcher changed unexpectedly')
        base=base.replace(old,new,1)
    return base


def _validate_identity(path: str,size: int,sha: str)->None:
    if (not isinstance(path,str) or len(path)>512 or not path.startswith('/') or not path.lower().endswith('.apk')
        or any(not part or part in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.@+-]+',part) for part in path[1:].split('/'))
        or not isinstance(size,int) or not 0<size<=MAX_APK or not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{64}',sha)):
        raise InnerError('Unsafe or unbounded export identity')


def export_raw(sandbox: Path,image: Path,output: Path,*,path: str,size: int,sha: str,control: bool=False)->dict:
    _validate_identity(path,size,sha)
    if not shutil.which('unshare') or not 0<image.stat().st_size<=tool.MAX_INPUT:raise InnerError('Missing namespace tool or oversized EROFS')
    before=pre.digest_file(image);dest=sandbox/'input/payload.erofs'
    if dest.exists() or dest.is_symlink() or output.exists() or output.is_symlink():raise InnerError('Temporary path already exists')
    fd=None;complete=False
    try:
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        shutil.copyfile(image,dest);dest.chmod(0o444)
        if pre.digest_file(dest)!=before:raise InnerError('Sandbox input copy changed')
        args=[shutil.which('unshare'),'--user','--map-root-user','--mount','--net','--pid','--fork',
              sys.executable,'-I','-S','-c',_launcher(),str(sandbox),'control' if control else 'candidate',
              str(fd),path,str(size),sha]
        proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              pass_fds=(fd,),start_new_session=True,env={'PATH':'/usr/bin:/bin','LANG':'C'})
        try:out,err=proc.communicate(timeout=180)
        except subprocess.TimeoutExpired as exc:
            os.killpg(proc.pid,signal.SIGKILL);proc.communicate();raise InnerError('EROFS export timed out') from exc
        if proc.returncode or len(out)+len(err)>erofs.MAX_OUTPUT:
            safe=err.decode('utf-8','replace')[:2000] if control else 'candidate diagnostics withheld'
            raise InnerError(f'EROFS export sandbox failed ({proc.returncode}): {safe}')
        try:result=json.loads(out)
        except (UnicodeError,ValueError) as exc:raise InnerError('Invalid isolated export result') from exc
        if (result.get('tool_exit_code')!=0 or result.get('exported')!={'bytes':size,'sha256':sha,'path':path}
            or not all(result.get(k) is True for k in ('root_read_only','no_new_privs','capabilities_dropped'))
            or pre.digest_file(output)!=(size,sha) or pre.digest_file(image)!=before):
            raise InnerError('Export or isolation verification failed')
        result['input_sha256']=before[1];complete=True;return result
    finally:
        if fd is not None:os.close(fd)
        dest.unlink(missing_ok=True)
        if not complete:output.unlink(missing_ok=True)


def verify_apk(apk: Path,apksigner: str)->dict:
    before=pre.digest_file(apk)
    if not 0<before[0]<=MAX_APK:raise InnerError('APK size outside bound')
    verifier=Path(apksigner)
    if not verifier.is_file() or not os.access(verifier,os.X_OK):raise InnerError('apksigner unavailable')
    env={k:v for k,v in os.environ.items() if not re.search(r'(TOKEN|SECRET|PASSWORD|CREDENTIAL)',k,re.I)}
    try:proc=subprocess.run([str(verifier),'verify','--verbose','--print-certs',str(apk)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300,check=False,env=env)
    except (OSError,subprocess.TimeoutExpired) as exc:raise InnerError('Signature verifier did not complete') from exc
    if len(proc.stdout)+len(proc.stderr)>signer.MAX_OUTPUT:raise InnerError('Verifier output exceeded bound')
    text=proc.stdout.decode('utf-8','replace');certs=signer.parse_certificates(text);schemes=signer.parse_schemes(text)
    if pre.digest_file(apk)!=before:raise InnerError('APK changed during verification')
    return {'bytes':before[0],'sha256':before[1],'verifier_exit_code':proc.returncode,
            'signature_verified_on_host':proc.returncode==0 and len(certs)==1 and any(schemes.get(x) for x in ('2','3','3.1','3.2')),
            'certificate_sha256':certs[0] if len(certs)==1 else None,'unique_certificate_count':len(certs),'schemes_reported':schemes,
            'verifier_stdout_sha256':hashlib.sha256(proc.stdout).hexdigest(),'verifier_stderr_sha256':hashlib.sha256(proc.stderr).hexdigest(),
            'tool_script_sha256':scan._tool_digest(apksigner),'signer_identity_or_device_trust_verified':False}


def mutate_one_zip_byte(src: Path,dst: Path)->None:
    if dst.exists() or dst.is_symlink():raise InnerError('Corrupt control path exists')
    with zipfile.ZipFile(src) as z:
        entries=[x for x in z.infolist() if x.compress_size>0 and not (x.flag_bits & 1)]
        if not entries:raise InnerError('No mutable compressed bytes')
        item=entries[0]
    shutil.copyfile(src,dst)
    with dst.open('r+b') as f:
        f.seek(item.header_offset);header=f.read(30)
        if len(header)!=30 or header[:4]!=b'PK\x03\x04':raise InnerError('Unexpected ZIP local header')
        namesize,extrasize=struct.unpack_from('<HH',header,26)
        offset=item.header_offset+30+namesize+extrasize
        if offset>=dst.stat().st_size:raise InnerError('ZIP data offset outside file')
        f.seek(offset);original=f.read(1)
        if len(original)!=1:raise InnerError('ZIP data byte missing')
        f.seek(offset);f.write(bytes((original[0]^1,)))
    with zipfile.ZipFile(dst) as z:
        if len(z.infolist())==0:raise InnerError('Corrupt control lost ZIP directory')


def controls(work: Path,sandbox: Path,apksigner: str)->dict:
    signed=work/'reader-control'/pre.APP_NAME
    if pre.digest_file(signed)!=(pre.APP_SIZE,pre.APP_SHA256):raise InnerError('Signed control differs from pinned app')
    valid=verify_apk(signed,apksigner)
    if not valid['signature_verified_on_host']:raise InnerError('Signed APK control failed')
    copy=work/'corrupt-control.apk';mutate_one_zip_byte(signed,copy)
    bad=verify_apk(copy,apksigner);copy.unlink()
    if bad['verifier_exit_code']==0 or bad['signature_verified_on_host']:raise InnerError('Corrupt APK control was accepted')
    unsigned=work/'unsigned-control.apk'
    with zipfile.ZipFile(signed) as z:manifest=z.read('AndroidManifest.xml')
    with zipfile.ZipFile(unsigned,'x') as z:z.writestr('AndroidManifest.xml',manifest)
    no_sig=verify_apk(unsigned,apksigner);unsigned.unlink()
    if no_sig['verifier_exit_code']==0 or no_sig['signature_verified_on_host']:raise InnerError('Unsigned APK control was accepted')
    tree=work/'export-control/tree/app';tree.mkdir(parents=True);shutil.copyfile(signed,tree/'control.apk')
    image=work/'export-control/good.img'
    proc=subprocess.run([shutil.which('unshare'),'--user','--map-root-user','--net','--pid','--fork',
                         str(sandbox/'tool/mkfs.erofs'),str(image),str(tree.parent)],stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    if proc.returncode:raise InnerError('Export control EROFS creation failed')
    exported=work/'exported-control.apk'
    raw=export_raw(sandbox,image,exported,path='/app/control.apk',size=pre.APP_SIZE,sha=pre.APP_SHA256,control=True)
    control_sig=verify_apk(exported,apksigner);exported.unlink()
    if not control_sig['signature_verified_on_host'] or raw.get('exported',{}).get('sha256')!=pre.APP_SHA256:
        raise InnerError('Signed EROFS export control failed')
    try:export_raw(sandbox,image,exported,path='/app/control.apk',size=pre.APP_SIZE,sha='0'*64,control=True)
    except InnerError:pass
    else:raise InnerError('Wrong export hash was accepted')
    if exported.exists() or exported.is_symlink():raise InnerError('Failed export left file')
    return {'signed_apk_verified':True,'corrupt_signed_apk_rejected':True,'unsigned_apk_rejected':True,
            'signed_apk_sha256':pre.APP_SHA256,'exported_signed_apk_verified':True,
            'wrong_export_hash_rejected_and_cleaned':True,
            'verifier_script_sha256':valid['tool_script_sha256']}


def run(work: Path,otatools: Path,aapt: str,aapt2: str,apksigner: str)->dict:
    if not work.is_dir() or work.is_symlink() or any(work.iterdir()):raise InnerError('Work directory must be empty')
    sandbox,erofs_controls=erofs.setup(otatools,work,aapt,aapt2)
    signature_controls=controls(work,sandbox,apksigner)
    print('EROFS and signed/corrupt/unsigned/export controls passed',flush=True)
    source=pre.download_candidate(work);lock=json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text())
    image=work/'product.img'
    with zipfile.ZipFile(source) as z,z.open('super.img') as stream,image.open('xb') as out:
        prefix=stream.read(vintf.lp.MAX_PREFIX);windows=vintf.extent_windows(prefix,vintf.SUPER_BYTES,vintf.part_specs(lock))
        vintf.copy_windows(stream,prefix,windows,{'product':out},vintf.SUPER_BYTES,pre.SUPER_SHA256)
    expected=(windows['product']['bytes'],windows['product']['sha256'])
    if pre.digest_file(image)!=expected:raise InnerError('Product extent differs')
    disk=vintf.pytsk3.Img_Info(str(image));fs=vintf.pytsk3.FS_Info(disk)
    if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:raise InnerError('Product is not ext4')
    entry=fs.open(path=gms.APEX_PATH);meta=entry.info.meta
    if meta is None or meta.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG or int(meta.size)!=apex_signature.APEX_BYTES:
        raise InnerError('APEX entry differs')
    package=work/'gmssystem.apex';digest=apex.copy_tsk_entry(entry,apex_signature.APEX_BYTES,package,gms.MAX_APEX)
    if digest!=apex_signature.APEX_SHA256:raise InnerError('APEX hash differs')
    payload=work/'payload.img';info=apex.extract_payload(package,payload)
    if info['sha256']!=apex_signature.PAYLOAD_SHA256 or apex.payload_format(payload)!='erofs':raise InnerError('Payload identity differs')
    target=work/'private-gms-control.apk'
    try:
        raw=export_raw(sandbox,payload,target,path=GMS_PATH,size=GMS_SIZE,sha=GMS_SHA)
        contents=erofs.decode_apks(raw,aapt,aapt2,work/'reader-scratch')
        rows=[x for x in contents['apks'] if x['path']==GMS_PATH]
        if len(rows)!=1 or rows[0]['package']!='com.google.android.gms' or rows[0]['sha256']!=GMS_SHA:
            raise InnerError('Independent package readers disagree with expected GMS')
        signature=verify_apk(target,apksigner)
    finally:target.unlink(missing_ok=True)
    if (pre.digest_file(payload)!=(info['bytes'],info['sha256']) or pre.digest_file(package)!=(apex_signature.APEX_BYTES,apex_signature.APEX_SHA256)
        or pre.digest_file(image)!=expected or pre.digest_file(source)!=(pre.SOURCE_SIZE,pre.SOURCE_SHA256)):
        raise InnerError('Candidate inputs changed during audit')
    return {'schema':'synthetica-gms-inner-signature-v1','status':'READ_ONLY_INNER_APK_SIGNATURE_HOLD',
            'source_candidate03_sha256':pre.SOURCE_SHA256,'apex_sha256':apex_signature.APEX_SHA256,
            'apex_payload_sha256':apex_signature.PAYLOAD_SHA256,'apk_path':GMS_PATH,
            'package_identity':rows[0],'apk_signature':signature,'ero_fs_isolation':contents['isolation'],
            'erofs_controls':erofs_controls,'signature_and_export_controls':signature_controls,
            'input_images_unchanged':True,'temporary_apk_removed':not target.exists(),
            'limitations':['Host signature self-consistency does not establish Google provenance, device trust, permissions or activation.',
                           'No candidate package was installed, executed, modified, uploaded or published; a control copy was deliberately corrupted.',
                           'Candidate 04, external vbmeta, recovery and boot were not tested by this audit.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--otatools',required=True,type=Path);p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True);p.add_argument('--apksigner',required=True)
    a=p.parse_args()
    try:
        result=run(a.work,a.otatools,a.aapt,a.aapt2,a.apksigner);code=0 if result['apk_signature']['signature_verified_on_host'] else 1
    except (InnerError,erofs.GmsErofsError,erofs.check.CheckAuditError,tool.ErofsAuditError,apex.ApexAuditError,
            scan.PackageScanError,pre.PreflightError,vintf.VintfAuditError,guard.AuditError,signer.SignerOutputError,
            OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-gms-inner-signature-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
