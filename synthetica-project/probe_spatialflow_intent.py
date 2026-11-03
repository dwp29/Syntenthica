#!/usr/bin/env python3
"""Read two independent host XML trees from the pinned SpatialFlow release APK.

Reports which exported activities claim MUSIC_PLAYER; does not run the APK,
prove code behavior, install anything, or make an application the default.
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
import scan_apk_packages as scan

ACTION='android.intent.action.MUSIC_PLAYER'
STRING=re.compile(r'="([^"]*)"')
ELEMENT=re.compile(r'^(\s*)E:\s+([\w-]+)(?:\s|$)')
ATTRIBUTE=re.compile(r'^(\s*)A:\s+([^\s(=]+)(?:\(0x[0-9a-fA-F]+\))?=(.*)$')
ANDROID_NAMESPACE='http://schemas.android.com/apk/res/android:'
MAX_XML=4*1024*1024

class IntentProbeError(RuntimeError):pass


def _node(tag,indent):return {'tag':tag,'indent':indent,'attrs':{},'children':[]}


def _string(value: str) -> str | None:
    match=STRING.search('='+value)
    return match.group(1) if match else None


def _boolean(value: str | None) -> bool | None:
    if value is None:return None
    v=value.strip().lower()
    if v in ('true','"true"','(type 0x12)0xffffffff','(type 0x12)0x1'):return True
    if v in ('false','"false"','(type 0x12)0x0','(type 0x12)0x00000000'):return False
    return None


def _name(node) -> str | None:
    return _string(node['attrs'].get('android:name',''))


def _canonical(name: str) -> str:
    if name.startswith('.'):return pre.APP_PACKAGE+name
    if '.' not in name:return pre.APP_PACKAGE+'.'+name
    return name


def parse_tree(text: str) -> list[dict]:
    if not text or len(text.encode())>MAX_XML or scan.parse_xmltree_package(text)!=pre.APP_PACKAGE:
        raise IntentProbeError('Unexpected XML package or size')
    stack=[];roots=[]
    for line in text.splitlines():
        m=ELEMENT.match(line)
        if m:
            indent=len(m.group(1).expandtabs(4));node=_node(m.group(2),indent)
            while stack and stack[-1]['indent']>=indent:stack.pop()
            if stack:stack[-1]['children'].append(node)
            else:roots.append(node)
            stack.append(node);continue
        m=ATTRIBUTE.match(line)
        if m:
            indent=len(m.group(1).expandtabs(4)); key=m.group(2)
            if key.startswith(ANDROID_NAMESPACE):key='android:'+key[len(ANDROID_NAMESPACE):]
            if not stack or indent<=stack[-1]['indent'] or key in stack[-1]['attrs']:
                raise IntentProbeError('Ambiguous XML tree attribute')
            stack[-1]['attrs'][key]=m.group(3)
    manifests=[x for x in roots if x['tag']=='manifest']
    if len(manifests)!=1:raise IntentProbeError('Expected one root manifest')
    apps=[x for x in manifests[0]['children'] if x['tag']=='application']
    if len(apps)!=1:raise IntentProbeError('Expected one application')
    matches=[]
    for comp in apps[0]['children']:
        if comp['tag'] not in ('activity','activity-alias'):continue
        for filt in (c for c in comp['children'] if c['tag']=='intent-filter'):
            actions=[_name(x) for x in filt['children'] if x['tag']=='action']
            if ACTION not in actions:continue
            name=_name(comp)
            if not name or any(x is None for x in actions):raise IntentProbeError('Unnamed matching component or action')
            categories=[_name(x) for x in filt['children'] if x['tag']=='category']
            if any(x is None for x in categories):raise IntentProbeError('Unnamed matching category')
            data=[{k:_string(v) if _string(v) is not None else v for k,v in sorted(x['attrs'].items())}
                  for x in filt['children'] if x['tag']=='data']
            matches.append({'component':_canonical(name),'kind':comp['tag'],'exported':_boolean(comp['attrs'].get('android:exported')),
                            'actions':sorted(actions),'categories':sorted(categories),'data':data})
    return sorted(matches,key=lambda x:json.dumps(x,sort_keys=True))


def compare_readers(aapt_text: str,aapt2_text: str) -> list[dict]:
    first=parse_tree(aapt_text);second=parse_tree(aapt2_text)
    if first!=second:
        lines=aapt2_text.splitlines(); hits=[i for i,x in enumerate(lines) if ACTION in x]
        excerpt=[]
        for i in hits[:2]:
            excerpt.extend(lines[max(0,i-7):min(len(lines),i+7)])
        detail=json.dumps({'aapt':first,'aapt2':second,'aapt2_music_excerpt':excerpt},sort_keys=True,separators=(',',':'))
        raise IntentProbeError('Two independent XML readers do not agree on MUSIC_PLAYER filters: '+detail[:5000])
    return first


def inspect(apk: Path,aapt: str,aapt2: str) -> dict:
    if pre.digest_file(apk)!=(pre.APP_SIZE,pre.APP_SHA256):raise IntentProbeError('APK is not the pinned release')
    aapt_hash=scan._tool_digest(aapt);aapt2_hash=scan._tool_digest(aapt2)
    if aapt_hash==aapt2_hash:raise IntentProbeError('Two distinct readers are required')
    xml1=pre.command([aapt,'dump','xmltree',str(apk),'AndroidManifest.xml'])
    xml2=pre.command([aapt2,'dump','xmltree','--file','AndroidManifest.xml',str(apk)])
    components=compare_readers(xml1,xml2)
    with zipfile.ZipFile(apk) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(infos)>100_000 or len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1:
            raise IntentProbeError('APK members are ambiguous')
        info=z.getinfo('AndroidManifest.xml')
        if not 0<info.file_size<=MAX_XML:raise IntentProbeError('APK manifest size is unexpected')
        data=z.read(info)
        manifest={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if pre.digest_file(apk)!=(pre.APP_SIZE,pre.APP_SHA256) or aapt_hash!=scan._tool_digest(aapt) or aapt2_hash!=scan._tool_digest(aapt2):
        raise IntentProbeError('APK or reader changed during inspection')
    return {'schema':'synthetica-spatialflow-release-intent-v1','status':'READ_ONLY_INTENT_INSPECTION_HOLD',
        'apk_sha256':pre.APP_SHA256,'apk_bytes':pre.APP_SIZE,'package':pre.APP_PACKAGE,
        'manifest':manifest,'aapt_sha256':aapt_hash,'aapt2_sha256':aapt2_hash,
        'music_player_filters':components,'two_readers_agree':True,
        'source_expected_component':pre.APP_PACKAGE+'.ui.ExternalPlayerActivity',
        'limitations':['Manifest routing is not proof that the release code matches the source or works at runtime.',
                       'No APK was modified, installed, set as default or tested on a device.',
                       'A MUSIC_PLAYER intent filter is not the only Android audio-opening path.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True)
    a=p.parse_args()
    try:
        if not a.work.is_dir() or any(a.work.iterdir()):raise IntentProbeError('Work directory must be empty')
        apk=pre.download_app(a.work);result=inspect(apk,a.aapt,a.aapt2);code=0
        if pre.app_release()[0][3]!=pre.APP_SHA256:raise IntentProbeError('Upstream release metadata changed')
    except (IntentProbeError,pre.PreflightError,scan.PackageScanError,OSError,ValueError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-spatialflow-release-intent-v1','status':'INCOMPLETE_HOLD','error':str(exc),'device_modified':False};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')),flush=True);return code
if __name__=='__main__':sys.exit(main())
