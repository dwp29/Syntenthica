#!/usr/bin/env python3
"""Stage the pinned SpatialFlow MUSIC_PLAYER fix in a clean disposable checkout.

Moves only the pre-existing intent filter to MainActivity and adds an independent
Gradle distribution checksum. Does not build, sign, install, or touch ROM images.
Use only a dedicated scratch checkout, never the caller's working source tree.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile

import prepare_spatialflow_music_intent as patch

WRAPPER_SHA = '6b4f2bc9ae1cc63596e38d99efb78ff2d6e86b9e47e9742cac118685c1d3f55f'
WRAPPER_JAR_SHA = '76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3'
GRADLE_SHA = 'acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a'
URL = b'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip\n'
MAX_SOURCE = 1_000_000

class StageError(RuntimeError):pass


def digest(data: bytes) -> str:return hashlib.sha256(data).hexdigest()


def checked_regular(path: Path, expected: str) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE:
        raise StageError('Expected a bounded ordinary source file')
    data=path.read_bytes()
    if digest(data)!=expected:raise StageError('Pinned source file digest differs: '+path.name)
    return data


def wrapper_with_checksum(data: bytes) -> bytes:
    if digest(data)!=WRAPPER_SHA or data.count(URL)!=1 or b'distributionSha256Sum=' in data:
        raise StageError('Gradle wrapper configuration differs from pinned upstream')
    return data.replace(URL,URL+b'distributionSha256Sum='+GRADLE_SHA.encode('ascii')+b'\n',1)


def git_checkout_identity(root: Path) -> None:
    env={'PATH':'/usr/bin:/bin','LANG':'C','HOME':str(root)}
    try:
        head=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,check=True,env=env,timeout=30)
        status=subprocess.run(['git','-C',str(root),'status','--porcelain','--untracked-files=all'],
                              capture_output=True,check=True,env=env,timeout=30)
    except (OSError,subprocess.SubprocessError) as exc:raise StageError('Cannot verify source checkout') from exc
    if head.stdout.decode('ascii','strict').strip()!=patch.SOURCE_COMMIT or status.stdout:
        raise StageError('Source checkout is not clean at the pinned commit')


def stage(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():raise StageError('A non-symlink source checkout is required')
    root=root.resolve();git_checkout_identity(root)
    manifest=root/'app/src/main/AndroidManifest.xml';wrapper=root/'gradle/wrapper/gradle-wrapper.properties'
    jar=root/'gradle/wrapper/gradle-wrapper.jar'
    if any(not x.resolve().is_relative_to(root) for x in (manifest,wrapper,jar)):
        raise StageError('Source paths escape the disposable checkout')
    original=checked_regular(manifest,patch.SOURCE_SHA256)
    wrapper_before=checked_regular(wrapper,WRAPPER_SHA);checked_regular(jar,WRAPPER_JAR_SHA)
    changed,report=patch.patch_manifest(original);wrapped=wrapper_with_checksum(wrapper_before)
    # Exclusive temporary files remain alongside the intended source files so
    # os.replace is atomic for each. Restore the manifest if the second write
    # fails; this checkout is still only disposable source, not a ROM image.
    prepared=[]
    try:
        for target,data in ((manifest,changed),(wrapper,wrapped)):
            fd,tmp=tempfile.mkstemp(prefix='.synthetica-stage-',dir=target.parent)
            prepared.append(Path(tmp))
            os.fchmod(fd,stat.S_IMODE(target.stat().st_mode))
            with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(prepared[0],manifest)
        try:os.replace(prepared[1],wrapper)
        except BaseException:
            manifest.write_bytes(original)
            raise
    finally:
        for path in prepared:path.unlink(missing_ok=True)
    if manifest.read_bytes()!=changed or wrapper.read_bytes()!=wrapped:
        raise StageError('Staged source readback differs')
    return {'status':'STAGED_FOR_UNSIGNED_HOST_BUILD_NOT_INSTALLED',
            'source_commit':patch.SOURCE_COMMIT,'source_manifest_sha256':patch.SOURCE_SHA256,
            'patched_manifest_sha256':digest(changed),'wrapper_original_sha256':WRAPPER_SHA,
            'wrapper_patched_sha256':digest(wrapped),'wrapper_jar_sha256':WRAPPER_JAR_SHA,
            'gradle_distribution_sha256':GRADLE_SHA,'music_player_to':report['music_player_to'],
            'limitations':['The build still needs Android SDK and public dependencies.',
                'A staged manifest does not prove build success, APK signing, default selection or playback.',
                'Replacing the release APK requires a compatible signing/update strategy.']}


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    if a.report.exists() or a.report.is_symlink() or not a.report.parent.is_dir():raise StageError('Use a new report path')
    try:result=stage(a.source);code=0
    except (StageError,patch.PatchError,OSError,ValueError) as exc:result={'status':'STAGING_FAILED','error':str(exc)};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')));return code
if __name__=='__main__':sys.exit(main())
