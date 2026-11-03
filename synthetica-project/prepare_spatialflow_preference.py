#!/usr/bin/env python3
"""Prepare a HOLD-only preferred-app XML for the *patched source* manifest.

This XML is not included in candidate 04. It must not be used with the
unpatched release APK. It targets only MUSIC_PLAYER and is not proof of Android
17 behavior, a first-boot default, or successful playback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import prepare_spatialflow_music_intent as patch

PATCHED_MANIFEST_SHA256='7b550c685db1106722cb9224619454910c46baa2caef1424a6db75fd7374b8c7'
COMPONENT='com.codetrio.spatialflow/.MainActivity'
PREFERENCE=(b'<?xml version="1.0" encoding="utf-8"?>\n'
 b'<preferred-activities>\n'
 b'    <item name="com.codetrio.spatialflow/.MainActivity">\n'
 b'        <filter>\n'
 b'            <action name="android.intent.action.MUSIC_PLAYER" />\n'
 b'            <cat name="android.intent.category.DEFAULT" />\n'
 b'        </filter>\n'
 b'    </item>\n'
 b'</preferred-activities>\n')

class PreferenceError(RuntimeError):pass


def prepare(manifest: bytes, *, expected_sha256: str=PATCHED_MANIFEST_SHA256) -> tuple[bytes,dict]:
    if not 0<len(manifest)<=patch.MAX_MANIFEST or hashlib.sha256(manifest).hexdigest()!=expected_sha256:
        raise PreferenceError('Patched source manifest differs from the pinned output')
    try:root=ET.fromstring(manifest)
    except ET.ParseError as exc:raise PreferenceError('Malformed source manifest') from exc
    apps=root.findall('application')
    if root.tag!='manifest' or len(apps)!=1:raise PreferenceError('Unexpected manifest structure')
    app=apps[0];activities=app.findall('activity');candidates=[]
    for activity in activities:
        for f in activity.findall('intent-filter'):
            if any(x.get(patch.ANDROID+'name')==patch.ACTION for x in f.findall('action')):
                candidates.append((activity,f))
    if len(candidates)!=1:raise PreferenceError('Patched manifest must expose exactly one MUSIC_PLAYER filter')
    activity,f=candidates[0]
    if (activity.get(patch.ANDROID+'name')!=patch.MAIN or activity.get(patch.ANDROID+'exported')!='true'
        or f.attrib or len(f)!=2 or f[0].tag!='action' or f[1].tag!='category'
        or f[0].attrib!={patch.ANDROID+'name':patch.ACTION}
        or f[1].attrib!={patch.ANDROID+'name':patch.CATEGORY}):
        raise PreferenceError('Patched component/filter is not the expected simple exported route')
    output=PREFERENCE
    report={'status':'SOURCE_PROTOTYPE_HOLD_NOT_IN_ROM_NOT_A_DEVICE_TEST',
            'patched_manifest_sha256':expected_sha256,'preference_sha256':hashlib.sha256(output).hexdigest(),
            'component':COMPONENT,'action':patch.ACTION,'category':patch.CATEGORY,
            'limitations':['Prototype applies only to the patched source; the existing 04 APK targets a different activity.',
                'Only MUSIC_PLAYER is covered; VIEW/audio URI resolution and all other defaults are unchanged.',
                'No APK, preference, ROM or device has been built, installed, configured or tested.',
                'AOSP Android 15 logic is a reference, not proof of Xiaomi Android 17 behavior or existing-user migration.']}
    return output,report


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--patched-manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        if a.patched_manifest.is_symlink() or not a.patched_manifest.is_file() or a.output.exists() or a.output.is_symlink():
            raise PreferenceError('Use an ordinary existing source and a new output path')
        data=a.patched_manifest.read_bytes();out,report=prepare(data)
        with a.output.open('xb') as f:f.write(out);f.flush();os.fsync(f.fileno())
        if a.patched_manifest.read_bytes()!=data:raise PreferenceError('Manifest changed during preparation')
        print(json.dumps(report,indent=2));return 0
    except (PreferenceError,OSError) as exc:
        print('Preference prototype not prepared: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
