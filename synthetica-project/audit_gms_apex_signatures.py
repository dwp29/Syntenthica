#!/usr/bin/env python3
"""Check a pinned Google APEX's self-consistency without asserting device trust.

The outer APK signature is checked by Android's host apksigner. The payload's
embedded AVB signature/hashtree is checked by a pinned AOSP verifier in a
networkless chroot after synthetic controls. Certificate/key matches are not
trust anchors and do not prove APEX activation, device AVB or boot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import audit_apex_avb_verify as avb
import audit_checkvintf_snapshot as check
import audit_gmssystem_apex as gms
import audit_runtime_apex as apex
import audit_vintf_candidate as vintf
import audit_vndk_apex as vndk
import apk_signer_output as signer_output
import preflight_spatialflow as pre
import scan_apk_packages as scan
import verify_preservation as guard

APEX_BYTES=155_066_368
APEX_SHA256='fdf44ee609c5290e749f8cf1ed81b144155fe0530be90eca4c2a806ff51873fd'
PAYLOAD_SHA256='1a5cd6ad67122bb9c249e03f6629aa0eb80be4c2e71848cda211bd53c65d629b'

class GmsSignatureError(RuntimeError):pass


def outer_signature(apex_path: Path,apksigner: str) -> dict:
    if pre.digest_file(apex_path)!=(APEX_BYTES,APEX_SHA256):raise GmsSignatureError('APEX differs from the verified input')
    tool=Path(apksigner)
    if not tool.is_file() or not os.access(tool,os.X_OK):raise GmsSignatureError('Android apksigner unavailable')
    # The trusted host verifier reads the ZIP; the package is never installed or executed.
    env={k:v for k,v in os.environ.items() if not re.search(r'(TOKEN|SECRET|PASSWORD|CREDENTIAL)',k,re.I)}
    try:proc=subprocess.run([str(tool),'verify','--verbose','--print-certs',str(apex_path)],stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,env=env,timeout=300,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:raise GmsSignatureError('Outer signature verifier did not complete') from exc
    if len(proc.stdout)+len(proc.stderr)>4*1024*1024:raise GmsSignatureError('Outer signature output too large')
    out=proc.stdout.decode('utf-8','replace')
    certs=signer_output.parse_certificates(out)
    schemes=signer_output.parse_schemes(out)
    diagnostic=signer_output.unparsed_signer_certificate_lines(out)
    # apksigner exit zero indicates cryptographic self-consistency for its SDK rules,
    # but a missing or ambiguous signer is still marked incomplete.
    return {'verifier_exit_code':proc.returncode,'outer_signature_verified_by_host':proc.returncode==0 and len(certs)==1 and not diagnostic,
            'certificate_sha256':certs[0] if len(certs)==1 and not diagnostic else None,'signer_count':len(certs),
            'unparsed_signer_certificate_digest_lines':diagnostic,
            'schemes_reported':schemes,'tool_stdout_sha256':hashlib.sha256(proc.stdout).hexdigest(),
            'tool_stderr_sha256':hashlib.sha256(proc.stderr).hexdigest(),'tool_script_sha256':scan._tool_digest(apksigner),
            'signer_identity_or_device_trust_verified':False}


def inspect(apex_path: Path,work: Path,sandbox: Path,apksigner: str) -> dict:
    if pre.digest_file(apex_path)!=(APEX_BYTES,APEX_SHA256):raise GmsSignatureError('Unexpected APEX identity')
    with zipfile.ZipFile(apex_path) as z:
        if len(z.infolist())>apex.MAX_MEMBERS:raise GmsSignatureError('APEX ZIP member limit')
        manifest=vndk.small_member(z,'apex_manifest.pb');key=vndk.small_member(z,'apex_pubkey')
        info=vndk.parse_apex_manifest(manifest)
    payload=work/'payload.img';meta=apex.extract_payload(apex_path,payload)
    if meta['sha256']!=PAYLOAD_SHA256:raise GmsSignatureError('APEX payload identity differs')
    structure=vndk.avb_header_observation(payload,key)
    verification=avb.verify_isolated(sandbox,payload)
    if verification['input_sha256']!=PAYLOAD_SHA256:raise GmsSignatureError('AVB verifier input differs')
    outer=outer_signature(apex_path,apksigner)
    if pre.digest_file(payload)!=(meta['bytes'],PAYLOAD_SHA256) or pre.digest_file(apex_path)!=(APEX_BYTES,APEX_SHA256):
        raise GmsSignatureError('Input changed during signature audit')
    return {'status':'READ_ONLY_APEX_SIGNATURE_CHECKS_HOLD','apex_bytes':APEX_BYTES,'apex_sha256':APEX_SHA256,
            'outer_apex_manifest':info,'bundled_apex_pubkey_sha256':hashlib.sha256(key).hexdigest(),
            'outer_apk_signature':outer,'payload_sha256':PAYLOAD_SHA256,'payload_zip_crc_checked':meta['zip_crc_checked_at_eof'],
            'payload_avb_structure':structure,'payload_avb_verification':verification,
            'limitations':['Self-consistent signatures and keys do not establish signer identity, device trust or APEX activation.',
                           'APK inside the APEX, external vbmeta, recovery and boot were not verified by this audit.',
                           'No image or device was modified; no private key was requested or used.']}


def prepare_sandbox(work: Path,otatools: Path,avbtool: Path) -> tuple[Path,dict,dict]:
    if not work.is_dir() or work.is_symlink() or any(work.iterdir()):
        raise GmsSignatureError('Work directory must be empty and not a symlink')
    sandbox=work/'sandbox';sandbox.mkdir();aosp=check.prepare_tool(otatools,sandbox)
    # check.prepare_tool creates the tool/runtime tree, not the mount point.
    # The isolated AVB launcher mounts its bounded tmpfs here before chroot.
    (sandbox/'out').mkdir()
    avb_tool=avb.prepare(sandbox,avbtool)
    return sandbox,aosp,avb_tool


def run(work: Path,otatools: Path,avbtool: Path,apksigner: str) -> dict:
    sandbox,aosp,avb_tool=prepare_sandbox(work,otatools,avbtool)
    controls=avb.run_controls(sandbox,work,avbtool)
    print('Four AVB synthetic controls passed',flush=True)
    source=pre.download_candidate(work);lock=json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text())
    image=work/'product.img'
    with zipfile.ZipFile(source) as z,z.open('super.img') as stream,image.open('xb') as out:
        prefix=stream.read(vintf.lp.MAX_PREFIX);windows=vintf.extent_windows(prefix,vintf.SUPER_BYTES,vintf.part_specs(lock))
        vintf.copy_windows(stream,prefix,windows,{'product':out},vintf.SUPER_BYTES,pre.SUPER_SHA256)
    expected=(windows['product']['bytes'],windows['product']['sha256'])
    if pre.digest_file(image)!=expected:raise GmsSignatureError('Product extent readback mismatch')
    disk=vintf.pytsk3.Img_Info(str(image));fs=vintf.pytsk3.FS_Info(disk)
    if fs.info.ftype!=vintf.pytsk3.TSK_FS_TYPE_EXT4:raise GmsSignatureError('Product image is not ext4')
    item=fs.open(path=gms.APEX_PATH);meta=item.info.meta
    if meta is None or meta.type!=vintf.pytsk3.TSK_FS_META_TYPE_REG or int(meta.size)!=APEX_BYTES:
        raise GmsSignatureError('APEX is not the expected regular file')
    package=work/'gmssystem.apex';digest=apex.copy_tsk_entry(item,APEX_BYTES,package,gms.MAX_APEX)
    if digest!=APEX_SHA256:raise GmsSignatureError('APEX copy hash mismatch')
    result=inspect(package,work,sandbox,apksigner)
    if pre.digest_file(image)!=expected or pre.digest_file(source)!=(pre.SOURCE_SIZE,pre.SOURCE_SHA256):
        raise GmsSignatureError('Source or product image changed')
    result.update(schema='synthetica-gms-apex-signatures-v1',source_candidate03_sha256=pre.SOURCE_SHA256,
                  input_images_unchanged=True,apex_path='product:'+gms.APEX_PATH,
                  avb_tool=avb_tool,avb_synthetic_controls=controls,pinned_otatools_sha256=aosp['otatools_sha256'])
    return result


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--otatools',required=True,type=Path);p.add_argument('--avbtool',required=True,type=Path);p.add_argument('--apksigner',required=True)
    a=p.parse_args()
    try:
        result=run(a.work,a.otatools,a.avbtool,a.apksigner)
        ok=(result['outer_apk_signature']['outer_signature_verified_by_host']
            and result['payload_avb_verification']['payload_signature_and_hashtree_verified_with_embedded_key'])
        result['both_host_checks_passed']=bool(ok);code=0 if ok else 1
    except (GmsSignatureError,avb.AvbProbeError,check.CheckAuditError,vndk.VndkApexError,apex.ApexAuditError,
            scan.PackageScanError,pre.PreflightError,vintf.VintfAuditError,guard.AuditError,OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-gms-apex-signatures-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
