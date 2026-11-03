#!/usr/bin/env python3
"""Compare a pinned *public* AOSP development certificate with a prior check.

No private key is read or used. This is a certificate fingerprint comparison,
not a signature-authority, device-trust, platform-key or license assessment.
The Leica APK remains rejected for production when its signature matches the
publicly known AOSP development testkey.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import apk_signer_output as signer

AOSP_COMMIT='3d9c9aacdb6ca0b745b3048dad88d0db4680d50e'
AOSP_BLOB='e242d83e2bf72169ab0abd5280d4d455caef71eb'
PEM_BYTES=1675
PEM_SHA='a4384ba815b9499a5ce349b4e33c1755278873fe2eac150a068823f526e6dbde'
DER_SHA='a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc'
LEICA_HEAD='ed3c28e0e76c7efd0f1c5aee199c81b29e338bee'
LEICA_CHECK=125740850789
LEICA_APK_SHA='54dc2f389b74a1799c6b238699fa4a8b5cca829d93f5064da3f55457900e1792'
class PublicCertificateError(RuntimeError):pass


def inspect(pem: bytes,check: dict,openssl: str='/usr/bin/openssl')->dict:
    if (len(pem)!=PEM_BYTES or hashlib.sha256(pem).hexdigest()!=PEM_SHA
        or hashlib.sha1(f'blob {len(pem)}\0'.encode()+pem).hexdigest()!=AOSP_BLOB):
        raise PublicCertificateError('Public AOSP certificate differs from pinned Git blob')
    if (not isinstance(check,dict) or check.get('id')!=LEICA_CHECK or check.get('head_sha')!=LEICA_HEAD
        or check.get('name')!='Synthetica Leica miatoll source probe' or check.get('status')!='completed'
        or check.get('conclusion')!='success'):
        raise PublicCertificateError('Prior Leica check identity or conclusion differs')
    try:
        r=json.loads(check['output']['summary']);inspection=r['inspection'];apk=inspection['apk'];sig=inspection['apk_signature']
        cert=sig['certificate_sha256']
    except (KeyError,TypeError,ValueError) as exc:raise PublicCertificateError('Leica check result malformed') from exc
    if (r.get('schema')!='synthetica-leica-miatoll-prebuilt-probe-v1' or r.get('status')!='READ_ONLY_PREBUILT_INSPECTED_HOLD'
        or r.get('source_commit')!='2582e3859181d32372a669f0cdaad151095b8a53' or apk.get('sha256')!=LEICA_APK_SHA
        or sig.get('signature_verified_on_host') is not True or sig.get('verifier_exit_code')!=0
        or sig.get('signer_authority_or_platform_trust_verified') is not False or sig.get('unparsed_certificate_digest_lines')!=[]):
        raise PublicCertificateError('Prior Leica signature result is incomplete')
    if not isinstance(cert,str) or len(cert)!=64:raise PublicCertificateError('Leica certificate digest unavailable')
    try:
        proc=subprocess.run([openssl,'x509','-inform','PEM','-outform','DER'],input=pem,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,timeout=20,check=False,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    except (OSError,subprocess.TimeoutExpired) as exc:raise PublicCertificateError('OpenSSL certificate conversion failed') from exc
    if proc.returncode or not 0<len(proc.stdout)<=8192 or len(proc.stderr)>8192:
        raise PublicCertificateError('OpenSSL did not parse the public certificate')
    digest=hashlib.sha256(proc.stdout).hexdigest()
    if digest!=DER_SHA or signer.matches_aosp_public_testkey(digest) is not True:
        raise PublicCertificateError('AOSP DER fingerprint differs from the testkey guard')
    match=(cert==digest)
    return {'schema':'synthetica-aosp-public-testkey-reference-v1','status':'PUBLIC_CERTIFICATE_COMPARISON_HOLD',
            'aosp_source':{'repository':'aosp-mirror/platform_build','commit':AOSP_COMMIT,
                           'path':'target/product/security/testkey.x509.pem','git_blob_sha1':AOSP_BLOB,
                           'pem_bytes':PEM_BYTES,'pem_sha256':PEM_SHA,'der_sha256':digest,
                           'source_commit_signature_verified':False},
            'leica_source_apk_sha256':LEICA_APK_SHA,'leica_check_run':LEICA_CHECK,'leica_check_head':LEICA_HEAD,
            'leica_certificate_sha256':cert,'leica_matches_public_aosp_testkey':match,
            'production_key_gate':'REJECT_PUBLIC_TESTKEY' if match else 'NOT_ASSESSED',
            'device_platform_key_checked':False,'signature_proves_publisher_identity':False,'private_key_requested_or_used':False,
            'limitations':['AOSP testkey is a known development key, not an acceptable publisher or production trust anchor.',
                'A different certificate would not by itself prove authenticity, license, platform trust or device compatibility.',
                'The upstream Android.bp requests platform signing; this comparison concerns the reconstructed prebuilt only.',
                'No APK, image, release, device, user data or private key was altered or used.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--public-certificate',required=True,type=Path)
    p.add_argument('--check-run',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    try:
        if a.public_certificate.is_symlink() or a.check_run.is_symlink() or a.public_certificate.stat().st_size>4096 or a.check_run.stat().st_size>200_000:
            raise PublicCertificateError('Inputs must be bounded ordinary files')
        result=inspect(a.public_certificate.read_bytes(),json.loads(a.check_run.read_text()))
        if not result['leica_matches_public_aosp_testkey']:raise PublicCertificateError('Expected testkey match not observed')
        code=0
    except (PublicCertificateError,signer.SignerOutputError,OSError,ValueError) as exc:
        result={'schema':'synthetica-aosp-public-testkey-reference-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
