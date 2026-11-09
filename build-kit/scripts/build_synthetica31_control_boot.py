#!/usr/bin/env python3
"""Offline-only repack for the exact user-provided boot; never opens a device."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import zipfile
import audit_synthetica3_boot as boot
import audit_boot_avb_hash as avb

REFERENCE = 'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f'
EVIDENCE = '8b01dde5c65234654634d5dc9cbc97a071ba3dc0f5c3061bb3ec02c9ab15867c'
IMAGE = 'bb0f98da58541cdc7eb8131d60860d006e35efc56a8ca1b33ebe3cc7d003e226'
CONFIG = '13893cb7c775157de6b03d72d42bcd0d969a4ae31e79d0ad9f69346778a4b0c1'
SIZE = 134217728

def sha(b): return hashlib.sha256(b).hexdigest()

def regular(path, max_size):
    with boot.readonly_file(path) as (f,n):
        if n > max_size: raise ValueError('oversized input')
        data=f.read()
        if len(data)!=n: raise ValueError('short read')
    return data

def get_kernel(evidence: Path):
    raw=regular(evidence, 30_000_000)
    if sha(raw)!=EVIDENCE: raise ValueError('compile evidence hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist(); names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or z.testzip(): raise ValueError('invalid evidence archive')
        for n in ('Image.gz.DO-NOT-FLASH','generated.config.txt','STATUS.json'):
            if names.count(n)!=1 or z.getinfo(n).file_size>25_000_000: raise ValueError('missing or oversized evidence')
        image=z.read('Image.gz.DO-NOT-FLASH'); cfg=z.read('generated.config.txt'); status=json.loads(z.read('STATUS.json'))
    if sha(image)!=IMAGE or sha(cfg)!=CONFIG or status.get('kind')!='SYNTHETICA_3_1_CONTROL1_COMPILE_ONLY' or status.get('image_sha256')!=IMAGE:
        raise ValueError('unexpected kernel build evidence')
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as f: uncompressed=f.read(100_000_001)
    if len(uncompressed)>100_000_000 or uncompressed[0x38:0x3c]!=b'ARMd': raise ValueError('invalid ARM64 kernel')
    if b'Linux version 4.14.357-openela-synthetica-3.1-control1 ' not in uncompressed: raise ValueError('kernel release mismatch')
    if uncompressed.count(b'IKCFG_ST')!=1 or uncompressed.count(b'IKCFG_ED')!=1: raise ValueError('invalid config markers')
    a=uncompressed.index(b'IKCFG_ST')+8;b=uncompressed.index(b'IKCFG_ED')
    if b<=a or b-a>4_000_000 or gzip.decompress(uncompressed[a:b])!=cfg: raise ValueError('embedded config mismatch')
    return image

def boot_hash_offset(data: bytearray, info: dict):
    meta=info['footer']; start=meta['vbmeta_offset']; h=avb.HEADER.unpack_from(data,start)
    if h[5]!=0 or h[3]!=0: raise ValueError('only unsigned embedded vbmeta supported; do not modify signed metadata')
    pos=start+256+h[3]+h[14]; end=pos+h[15]; matches=[]
    while pos<end:
        tag, n=struct.unpack_from('>QQ',data,pos)
        if n%8 or n>end-pos-16: raise ValueError('invalid descriptor bounds')
        if tag==2:
            _,_,length,alg,nlen,slen,dlen,flags,_=avb.HASH_DESC.unpack_from(data,pos)
            if ((avb.HASH_DESC.size-16+nlen+slen+dlen+7)//8)*8!=n: raise ValueError('invalid hash descriptor')
            base=pos+avb.HASH_DESC.size
            if bytes(data[base:base+nlen])==b'boot':
                if alg.rstrip(b'\0')!=b'sha256' or dlen!=32 or flags!=0 or length!=meta['original_image_size']:
                    raise ValueError('unsupported boot hash descriptor')
                matches.append((base+nlen+slen,bytes(data[base+nlen:base+nlen+slen]),length))
        pos+=16+n
    if pos!=end or len(matches)!=1: raise ValueError('expected one boot hash descriptor')
    return matches[0]

def construct(reference: Path, evidence: Path, output: Path):
    if output.exists() or output.is_symlink(): raise ValueError('refusing existing output')
    original=regular(reference,SIZE)
    if len(original)!=SIZE or sha(original)!=REFERENCE: raise ValueError('wrong reference image')
    orig=boot.inspect_boot(reference); original_avb=avb.inspect(reference)
    if orig['file_sha256'] != REFERENCE or not orig['legacy_boot_id_matches_sha1'] or not original_avb['embedded_boot_hash']['digest_matches']:
        raise ValueError('reference image fails integrity checks')
    if orig['sections']['recovery_dtbo']['bytes'] or orig['sections']['second']['bytes']:
        raise ValueError('unsupported non-empty section')
    k=get_kernel(evidence); data=bytearray(original); meta=orig['avb']; limit=meta['original_image_size']
    if not meta['footer_at_end'] or limit>meta['vbmeta_offset']: raise ValueError('invalid original AVB layout')
    sections={n:original[x['offset']:x['offset']+x['bytes']] for n,x in orig['sections'].items() if n!='kernel'}
    page=orig['page_size']; pos=page; data[pos:limit]=bytes(limit-pos)
    struct.pack_into('<I',data,8,len(k));ident=hashlib.sha1()
    for part in (k,sections['ramdisk'],sections['second'],sections['recovery_dtbo'],sections['dtb']):
        if pos+len(part)>limit: raise ValueError('kernel and sections exceed image region')
        data[pos:pos+len(part)]=part;pos+=(len(part)+page-1)//page*page
        ident.update(part);ident.update(struct.pack('<I',len(part)))
    if pos>limit: raise ValueError('aligned boot exceeds image region')
    data[576:608]=ident.digest()+bytes(12)
    offset,salt,length=boot_hash_offset(data,original_avb)
    data[offset:offset+32]=hashlib.sha256(salt+data[:length]).digest()
    # Only the known unsigned descriptor digest is changed in the AVB region.
    if (data[meta['vbmeta_offset']:offset]!=original[meta['vbmeta_offset']:offset] or
        data[offset+32:]!=original[offset+32:]): raise ValueError('unexpected AVB/trailing-byte changes')
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data)
        candidate=boot.inspect_boot(output); check=boot.compare_boot(orig,candidate,IMAGE); ca=avb.inspect(output)
        if (not all(check['stable_header_fields_match'].values()) or not all(check['non_kernel_sections_match'].values())
                or not check['candidate_kernel_equals_bundle_image'] or not check['candidate_legacy_boot_id_matches']
                or not ca['embedded_boot_hash']['digest_matches'] or not ca['vbmeta_algorithm_none']):
            raise ValueError('candidate verification failed')
    except BaseException:
        output.unlink(missing_ok=True); raise
    return {'reference_sha256':REFERENCE,'image_sha256':IMAGE,'candidate_sha256':sha(data),'bytes':len(data),
            'scope':'Offline only. Unsigned embedded digest consistent; external AVB, ROM modules and physical boot unverified.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('reference','evidence','output'): p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(json.dumps(construct(a.reference,a.evidence,a.output),indent=2))
if __name__=='__main__':
    try: main()
    except (OSError, ValueError, zipfile.BadZipFile, struct.error) as e:
        print('Offline repack refused: '+str(e),file=sys.stderr);sys.exit(1)
