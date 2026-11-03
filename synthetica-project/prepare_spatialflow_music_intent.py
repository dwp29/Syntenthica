#!/usr/bin/env python3
"""Prepare a source-only MUSIC_PLAYER routing fix for the pinned SpatialFlow tag.

This does not build, sign, install or configure a default player. The pinned
source's external-file popup closes when launched with no URI, even though it
advertises MUSIC_PLAYER. Move that one filter to the exported main activity;
leave file/audio VIEW filters and every other manifest node unchanged. The
release APK's correspondence to this source is unverified.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

SOURCE_COMMIT = '8a40906d074ab95b2bfa32481bfae140dfdfcbed'
SOURCE_GIT_BLOB = 'b9a113d207ab11e341b8e69906fb4947836190a7'
SOURCE_SHA256 = 'f1012fab2e47995dfe7107280fb6a91283d32f1039e83b0542d7676311c49fee'
ANDROID = '{http://schemas.android.com/apk/res/android}'
ACTION = 'android.intent.action.MUSIC_PLAYER'
CATEGORY = 'android.intent.category.DEFAULT'
MAIN = '.MainActivity'
EXTERNAL = '.ui.ExternalPlayerActivity'
OLD_FILTER = ('''            <intent-filter>\n'''
              '''                <action android:name="android.intent.action.MUSIC_PLAYER" />\n'''
              '''                <category android:name="android.intent.category.DEFAULT" />\n'''
              '''            </intent-filter>\n''')
MAIN_MARKER = '            <!-- Fallback intent filter for direct intent launches without duplicating launcher icon -->\n'
MAX_MANIFEST = 1_000_000

class PatchError(RuntimeError):
    pass


def _shape(e):
    return (e.tag, tuple(sorted(e.attrib.items())), (e.text or '').strip(), tuple(_shape(c) for c in e))


def _activity(app, name):
    values = [x for x in app.findall('activity') if x.get(ANDROID+'name') == name]
    if len(values) != 1 or values[0].get(ANDROID+'exported') != 'true':
        raise PatchError('Expected exactly one exported activity: ' + name)
    return values[0]


def patch_manifest(data: bytes, *, expected_sha256: str = SOURCE_SHA256) -> tuple[bytes, dict]:
    if not 0 < len(data) <= MAX_MANIFEST or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise PatchError('Source manifest differs from the pinned content')
    try:
        text = data.decode('utf-8')
        root = ET.fromstring(data)
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise PatchError('Source manifest is not valid UTF-8 XML') from exc
    if root.tag != 'manifest' or len(root.findall('application')) != 1:
        raise PatchError('Unexpected manifest structure')
    app = root.find('application'); main, external = _activity(app, MAIN), _activity(app, EXTERNAL)
    matches = []
    for activity in app.findall('activity'):
        for item in activity.findall('intent-filter'):
            if any(a.get(ANDROID+'name') == ACTION for a in item.findall('action')):
                matches.append((activity, item))
    if len(matches) != 1 or matches[0][0] is not external:
        raise PatchError('MUSIC_PLAYER must occur only on the expected external activity')
    filt = matches[0][1]
    if (filt.attrib or len(filt) != 2 or filt[0].tag != 'action' or filt[1].tag != 'category'
            or filt[0].attrib != {ANDROID+'name': ACTION} or filt[1].attrib != {ANDROID+'name': CATEGORY}):
        raise PatchError('MUSIC_PLAYER filter differs from the expected simple action/category')
    if text.count(OLD_FILTER) != 1 or text.count(MAIN_MARKER) != 1:
        raise PatchError('Source formatting is not the pinned patchable form')
    expected = copy.deepcopy(root)
    expected_app = expected.find('application')
    expected_main, expected_ext = _activity(expected_app, MAIN), _activity(expected_app, EXTERNAL)
    moving = next(f for f in expected_ext.findall('intent-filter')
                  if any(a.get(ANDROID+'name') == ACTION for a in f.findall('action')))
    expected_ext.remove(moving); expected_main.insert(0, moving)
    changed = text.replace(OLD_FILTER, '', 1).replace(MAIN_MARKER, OLD_FILTER+'\n'+MAIN_MARKER, 1).encode('utf-8')
    try:
        actual = ET.fromstring(changed)
    except ET.ParseError as exc:
        raise PatchError('Generated XML failed validation') from exc
    if _shape(actual) != _shape(expected):
        raise PatchError('Generated manifest changed nodes beyond the single intended filter')
    return changed, {'status': 'SOURCE_PATCH_ONLY_NOT_BUILT_NOT_SIGNED_NOT_INSTALLED',
                     'source_commit': SOURCE_COMMIT, 'source_git_blob': SOURCE_GIT_BLOB,
                     'source_manifest_sha256': expected_sha256,
                     'patched_manifest_sha256': hashlib.sha256(changed).hexdigest(),
                     'music_player_from': EXTERNAL, 'music_player_to': MAIN,
                     'other_manifest_nodes_identical': True,
                     'limitations': ['Source-to-release-APK correspondence is not authenticated.',
                       'No APK was compiled, signed, installed, made default, or tested on a device.',
                       'Existing release APK is not modified by this source-only patch.']}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.source.is_symlink() or not args.source.is_file() or args.output.exists() or args.output.is_symlink():
            raise PatchError('Use an existing ordinary source and a new output path')
        before=args.source.read_bytes(); after,report=patch_manifest(before)
        with args.output.open('xb') as out: out.write(after);out.flush();os.fsync(out.fileno())
        if args.source.read_bytes()!=before: raise PatchError('Source changed during patch preparation')
        print(json.dumps(report,indent=2));return 0
    except (PatchError,OSError) as exc:
        print('Source patch not prepared: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__': sys.exit(main())
