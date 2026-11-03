#!/usr/bin/env python3
"""Validate a newly built *unsigned* SpatialFlow source APK on a host.

Checks APK integrity, the arm64 split and the patched MUSIC_PLAYER manifest
using two Android tools. A success is not a signed/installable release, a
preferred default, source-to-upstream-binary equivalence, or a device/audio test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

import preflight_spatialflow as pre
import prepare_spatialflow_music_intent as patch
import prepare_spatialflow_preference as preference
import probe_spatialflow_intent as intent
import scan_apk_packages as scan

class SourceBuildError(RuntimeError):pass


def inspect(apk: Path, source_manifest: Path, aapt: str, aapt2: str, apksigner: str, zipalign: str)->dict:
    for path in (apk,source_manifest):
        if path.is_symlink() or not path.is_file():raise SourceBuildError('Inputs must be ordinary files')
    apk_bytes,apk_sha=pre.digest_file(apk)
    if not 0<apk_bytes<=scan.MAX_APK_BYTES:raise SourceBuildError('Built APK exceeds its bound')
    manifest_bytes=source_manifest.read_bytes()
    pref,pref_result=preference.prepare(manifest_bytes)
    tools={name:scan._tool_digest(value) for name,value in
           (('aapt',aapt),('aapt2',aapt2),('apksigner',apksigner),('zipalign',zipalign))}
    if tools['aapt']==tools['aapt2']:raise SourceBuildError('Two distinct manifest readers required')
    with zipfile.ZipFile(apk) as z:
        members=z.infolist();names=[x.filename for x in members]
        if (len(names)>100_000 or len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1
                or any(x.flag_bits & 1 or x.file_size>256*1024*1024 for x in members)
                or sum(x.file_size for x in members)>1024*1024*1024):
            raise SourceBuildError('Built APK ZIP members are ambiguous or encrypted')
        if any(re.fullmatch(r'META-INF/[^/]+\.(?:SF|RSA|DSA|EC)',x,re.IGNORECASE) for x in names):
            raise SourceBuildError('Unexpected APK v1 signing files')
        if z.testzip() is not None:raise SourceBuildError('Built APK failed ZIP CRC validation')
        # Reject a v2/v3 APK Signing Block, valid or damaged, immediately before
        # the ZIP central directory. A verifier error alone is not enough.
        with apk.open('rb') as binary:
            if z.start_dir>=16:
                binary.seek(z.start_dir-16)
                if binary.read(16)==b'APK Sig Block 42':
                    raise SourceBuildError('Unexpected APK signing block')
        m=z.getinfo('AndroidManifest.xml')
        if not 0<m.file_size<=scan.MAX_MANIFEST_BYTES:raise SourceBuildError('Manifest outside bounds')
        manifest=z.read(m)
        native=sorted(x for x in names if re.fullmatch(r'lib/[^/]+/[^/]+\.so',x))
        if not native or any(not x.startswith('lib/arm64-v8a/') for x in native):
            raise SourceBuildError('APK is not the expected arm64-only native split')
    first=pre.command([aapt,'dump','xmltree',str(apk),'AndroidManifest.xml'])
    second=pre.command([aapt2,'dump','xmltree','--file','AndroidManifest.xml',str(apk)])
    routes=intent.compare_readers(first,second)
    expected={'component':pre.APP_PACKAGE+'.MainActivity','kind':'activity','exported':True,
              'actions':[patch.ACTION],'categories':[patch.CATEGORY],'data':[]}
    if routes!=[expected]:raise SourceBuildError('Built manifest does not expose the expected patched route')
    badging=pre.command([aapt,'dump','badging',str(apk)])
    match=re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'",badging,re.M)
    if not match or match.groups()!=(pre.APP_PACKAGE,'10','1.8.2'):
        raise SourceBuildError('Built APK identity differs from source version 1.8.2')
    align=scan._run_tool([zipalign,'-c','-P','4','4',str(apk)])
    if align.returncode:raise SourceBuildError('Built APK did not pass 4 KiB zip alignment')
    signing=scan._run_tool([apksigner,'verify','--verbose','--print-certs',str(apk)])
    # This stage deliberately has no signing credentials: a signed result is
    # unexpected, and a failing verifier alone never proves trust or usability.
    if signing.returncode==0:raise SourceBuildError('Unexpected signed APK in unsigned-only build')
    if b'DOES NOT VERIFY' not in (signing.stdout+signing.stderr):
        raise SourceBuildError('APK verifier did not report the expected unsigned result')
    if pre.digest_file(apk)!=(apk_bytes,apk_sha):raise SourceBuildError('Built APK changed during verification')
    if tools!={name:scan._tool_digest(value) for name,value in
               (('aapt',aapt),('aapt2',aapt2),('apksigner',apksigner),('zipalign',zipalign))}:
        raise SourceBuildError('A host inspection tool changed')
    return {'schema':'synthetica-spatialflow-source-build-v1','status':'UNSIGNED_HOST_BUILD_ROUTE_VERIFIED_NOT_INSTALLED',
        'source_commit':patch.SOURCE_COMMIT,'apk':{'bytes':apk_bytes,'sha256':apk_sha,
          'package':pre.APP_PACKAGE,'version_code':'10','version_name':'1.8.2','native_libraries':len(native),
          'native_abi':'arm64-v8a','zip_crc_checked':True,'zipalign_4k_passed':True,
          'apksigner_verify_exit':signing.returncode,'signed_release_not_verified':True},
        'manifest':{'bytes':len(manifest),'sha256':hashlib.sha256(manifest).hexdigest(),
                    'music_player_filters':routes,'two_readers_agree':True},
        'preference_prototype_sha256':hashlib.sha256(pref).hexdigest(),
        'preference_prototype_status':pref_result['status'],'tool_sha256':tools,
        'limitations':['No signing key, installed application, ROM image or device was used.',
            'Unsigned verifier failure does not by itself classify every possible APK signing block.',
            'No preference was installed; Android/HyperOS resolution and audio playback are untested.',
            'Upstream private cloud configuration values were not supplied; their dependent features are unverified.',
            'Source-to-upstream-release binary identity and package update signing compatibility are not established.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','source-manifest','report'):p.add_argument('--'+name,required=True,type=Path)
    for name in ('aapt','aapt2','apksigner','zipalign'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    if a.report.exists() or a.report.is_symlink() or not a.report.parent.is_dir():raise SourceBuildError('Use a new report path')
    try:result=inspect(a.apk,a.source_manifest,a.aapt,a.aapt2,a.apksigner,a.zipalign);code=0
    except (SourceBuildError,pre.PreflightError,scan.PackageScanError,intent.IntentProbeError,
            preference.PreferenceError,OSError,ValueError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-spatialflow-source-build-v1','status':'BUILD_VERIFICATION_INCOMPLETE',
                'error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')));return code
if __name__=='__main__':sys.exit(main())
