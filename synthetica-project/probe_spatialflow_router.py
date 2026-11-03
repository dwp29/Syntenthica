#!/usr/bin/env python3
"""Verify a throwaway MUSIC_PLAYER router and its pinned upstream target.

Uses independent Android XML readers on both APKs and verifies a *host test*
router signature. Never edits ROM images, installs applications, uploads APKs,
uses production keys, or claims Android/HyperOS runtime behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import apk_signer_output as signers
import preflight_spatialflow as pre
import probe_spatialflow_intent as intent
import scan_apk_packages as scan

ROUTER_PACKAGE='org.syntenthica.musicrouter'
ROUTER_ACTIVITY=ROUTER_PACKAGE+'.MusicPlayerRouter'
UPSTREAM_ACTIVITY=pre.APP_PACKAGE+'.MainActivity'
MUSIC='android.intent.action.MUSIC_PLAYER'
MAIN='android.intent.action.MAIN'
DEFAULT='android.intent.category.DEFAULT'
A='{http://schemas.android.com/apk/res/android}'
MAX_ROUTER=10*1024*1024

class RouterError(RuntimeError):pass


def source_prototype(manifest: bytes, preference: bytes) -> dict:
    if not 0<len(manifest)<=100_000 or not 0<len(preference)<=100_000:
        raise RouterError('Router source is outside bounds')
    try:r=ET.fromstring(manifest);p=ET.fromstring(preference)
    except ET.ParseError as exc:raise RouterError('Malformed router source XML') from exc
    if (r.tag!='manifest' or r.attrib!={'package':ROUTER_PACKAGE,A+'versionCode':'1',A+'versionName':'1.0'}
        or [x.tag for x in r]!=['uses-sdk','queries','application']):
        raise RouterError('Router manifest structure or package differs')
    sdk,q,app=list(r)
    if sdk.attrib!={A+'minSdkVersion':'26',A+'targetSdkVersion':'35'}:
        raise RouterError('Router SDK declaration differs')
    if q.attrib or len(q)!=1 or q[0].tag!='package' or q[0].attrib!={A+'name':pre.APP_PACKAGE}:
        raise RouterError('Router visibility declaration differs')
    if (app.attrib!={A+'allowBackup':'false',A+'usesCleartextTraffic':'false',A+'label':'SpatialFlow',
                     A+'icon':'@android:drawable/ic_media_play'} or len(app)!=1 or app[0].tag!='activity'):
        raise RouterError('Router application is not the expected nonprivileged prototype')
    activity=app[0]
    if (activity.attrib!={A+'name':'.MusicPlayerRouter',A+'exported':'true',A+'theme':'@android:style/Theme.NoDisplay'}
        or len(activity)!=1 or activity[0].tag!='intent-filter' or activity[0].attrib):
        raise RouterError('Router component differs')
    f=activity[0]
    if [(x.tag,x.attrib) for x in f]!=[('action',{A+'name':MUSIC}),('category',{A+'name':DEFAULT})]:
        raise RouterError('Router must expose only the simple MUSIC_PLAYER filter')
    if (p.tag!='preferred-activities' or p.attrib or len(p)!=1 or p[0].tag!='item'
        or p[0].attrib!={'name':ROUTER_PACKAGE+'/.MusicPlayerRouter'} or len(p[0])!=1
        or p[0][0].tag!='filter' or p[0][0].attrib
        or [(x.tag,x.attrib) for x in p[0][0]]!=[('action',{'name':MUSIC}),('cat',{'name':DEFAULT})]):
        raise RouterError('Router preferred-app prototype differs')
    return {'manifest_sha256':hashlib.sha256(manifest).hexdigest(),
            'preference_sha256':hashlib.sha256(preference).hexdigest(),
            'package':ROUTER_PACKAGE,'component':ROUTER_ACTIVITY}


def activity_from_tree(text: str, package: str, component: str, action: str) -> dict:
    """Read one activity with bounded aapt/aapt2 xmltree indentation."""
    if not text or len(text.encode())>intent.MAX_XML or scan.parse_xmltree_package(text)!=package:
        raise RouterError('Unexpected XML package or size')
    stack=[];roots=[]
    for line in text.splitlines():
        m=intent.ELEMENT.match(line)
        if m:
            indent=len(m.group(1).expandtabs(4));node=intent._node(m.group(2),indent)
            while stack and stack[-1]['indent']>=indent:stack.pop()
            if stack:stack[-1]['children'].append(node)
            else:roots.append(node)
            stack.append(node);continue
        m=intent.ATTRIBUTE.match(line)
        if m:
            indent=len(m.group(1).expandtabs(4));key=m.group(2)
            if key.startswith(intent.ANDROID_NAMESPACE):key='android:'+key[len(intent.ANDROID_NAMESPACE):]
            if not stack or indent<=stack[-1]['indent'] or key in stack[-1]['attrs']:
                raise RouterError('Ambiguous XML tree attribute')
            stack[-1]['attrs'][key]=m.group(3)
    manifests=[x for x in roots if x['tag']=='manifest']
    if len(manifests)!=1:raise RouterError('Expected one root manifest')
    r=manifests[0];apps=[x for x in r['children'] if x['tag']=='application']
    if len(apps)!=1:raise RouterError('Expected one application')
    app=apps[0]
    def enabled(node):
        v=node['attrs'].get('android:enabled')
        if v is None:return True
        parsed=intent._boolean(v)
        if parsed is None:raise RouterError('Cannot read enabled attribute')
        return parsed
    activities=[]
    for node in app['children']:
        if node['tag']!='activity':continue
        name=intent._name(node)
        if not name:raise RouterError('Unnamed activity')
        canonical=package+name if name.startswith('.') else package+'.'+name if '.' not in name else name
        if canonical==component:activities.append(node)
    if len(activities)!=1:raise RouterError('Expected exactly one target activity')
    target=activities[0];matching=[]
    for f in (x for x in target['children'] if x['tag']=='intent-filter'):
        actions=[intent._name(x) for x in f['children'] if x['tag']=='action']
        cats=[intent._name(x) for x in f['children'] if x['tag']=='category']
        if any(x is None for x in actions+cats):raise RouterError('Unnamed filter element')
        if action in actions:
            matching.append({'actions':sorted(actions),'categories':sorted(cats),
                             'data_count':sum(x['tag']=='data' for x in f['children'])})
    component_kinds=sorted(x['tag'] for x in app['children'] if x['tag'] in ('activity','activity-alias','service','receiver','provider'))
    uses_permissions=sorted(x['tag'] for x in r['children'] if x['tag'].startswith('uses-permission'))
    return {'package':package,'component':component,'exported':intent._boolean(target['attrs'].get('android:exported')),
            'application_enabled':enabled(app),'activity_enabled':enabled(target),
            'application_permission':app['attrs'].get('android:permission'),
            'activity_permission':target['attrs'].get('android:permission'),'matching_filters':matching,
            'component_kinds':component_kinds,'uses_permission_tags':uses_permissions}


def compare_activities(xml1: str, xml2: str, package: str, component: str, action: str, *,router: bool) -> dict:
    first=activity_from_tree(xml1,package,component,action);second=activity_from_tree(xml2,package,component,action)
    if first!=second:raise RouterError('Independent manifest readers disagree')
    if not (first['exported'] is True and first['application_enabled'] and first['activity_enabled']
            and first['application_permission'] is None and first['activity_permission'] is None):
        raise RouterError('Target activity is not explicitly exported and enabled')
    matches=first['matching_filters']
    if len(matches)!=1 or matches[0]['actions']!=[action] or DEFAULT not in matches[0]['categories'] or matches[0]['data_count']:
        raise RouterError('Target filter is not the expected no-data action')
    if router and (matches[0]['categories']!=[DEFAULT] or first['component_kinds']!=['activity'] or first['uses_permission_tags']):
        raise RouterError('Router has extra categories, components or permissions')
    return first


def inspect(router_apk: Path, upstream_apk: Path, source: Path, aapt: str,aapt2: str,apksigner: str,zipalign: str)->dict:
    for file in (router_apk,upstream_apk,source/'AndroidManifest.xml',source/'preferred-spatialflow-router.xml',
                 source/'src/org/syntenthica/musicrouter/MusicPlayerRouter.java'):
        if file.is_symlink() or not file.is_file():raise RouterError('Expected ordinary inputs')
    source_report=source_prototype((source/'AndroidManifest.xml').read_bytes(),(source/'preferred-spatialflow-router.xml').read_bytes())
    java=(source/'src/org/syntenthica/musicrouter/MusicPlayerRouter.java').read_bytes()
    if not 0<len(java)<=100_000:raise RouterError('Router Java source exceeds bound')
    source_report['java_sha256']=hashlib.sha256(java).hexdigest()
    router_size,router_sha=pre.digest_file(router_apk)
    if not 0<router_size<=MAX_ROUTER or pre.digest_file(upstream_apk)!=(pre.APP_SIZE,pre.APP_SHA256):
        raise RouterError('APK identity/size differs')
    tool_paths={'aapt':aapt,'aapt2':aapt2,'apksigner':apksigner,'zipalign':zipalign}
    tools={k:scan._tool_digest(v) for k,v in tool_paths.items()}
    if tools['aapt']==tools['aapt2']:raise RouterError('Two distinct readers required')
    with zipfile.ZipFile(router_apk) as z:
        infos=z.infolist();names=[x.filename for x in infos]
        if (len(names)>1000 or len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1
            or names.count('classes.dex')!=1 or any(x.flag_bits & 1 or x.file_size>MAX_ROUTER for x in infos)
            or sum(x.file_size for x in infos)>MAX_ROUTER or z.testzip() is not None):
            raise RouterError('Router APK members or CRC differ')
    def xml(file):return (pre.command([aapt,'dump','xmltree',str(file),'AndroidManifest.xml']),
                          pre.command([aapt2,'dump','xmltree','--file','AndroidManifest.xml',str(file)]))
    rx=xml(router_apk);ux=xml(upstream_apk)
    route=compare_activities(*rx,ROUTER_PACKAGE,ROUTER_ACTIVITY,MUSIC,router=True)
    upstream=compare_activities(*ux,pre.APP_PACKAGE,UPSTREAM_ACTIVITY,MAIN,router=False)
    if scan._run_tool([zipalign,'-c','-P','4','4',str(router_apk)]).returncode:
        raise RouterError('Router alignment failed')
    verify=scan._run_tool([apksigner,'verify','--verbose','--print-certs',str(router_apk)])
    output=verify.stdout.decode('utf-8','replace')+'\n'+verify.stderr.decode('utf-8','replace')
    certificates=signers.parse_certificates(output);schemes=signers.parse_schemes(output)
    if (verify.returncode or len(certificates)!=1 or signers.unparsed_signer_certificate_lines(output)
        or not schemes.get('2') or signers.aosp_public_development_certificate_name(certificates[0])):
        raise RouterError('Host test APK signature is invalid or ambiguous')
    if (pre.digest_file(router_apk)!=(router_size,router_sha) or pre.digest_file(upstream_apk)!=(pre.APP_SIZE,pre.APP_SHA256)
        or tools!={k:scan._tool_digest(v) for k,v in tool_paths.items()}):
        raise RouterError('An APK or reader changed during inspection')
    return {'schema':'synthetica-spatialflow-router-host-probe-v1','status':'EPHEMERAL_HOST_TEST_ONLY_NOT_SHIPPABLE',
        'router':{'bytes':router_size,'sha256':router_sha,'apk_v2_verified':True,'ephemeral_test_key_only':True,
                  'manifest':route},'upstream':{'bytes':pre.APP_SIZE,'sha256':pre.APP_SHA256,'manifest':upstream},
        'source_prototype':source_report,'two_manifest_readers_agree':True,'tool_sha256':tools,
        'limitations':['The APK was signed with a throwaway CI test key and must never be shipped.',
            'No ROM image, installed package, preference, production signing key, recovery or device was changed.',
            'Exported manifest routes do not prove activity startup, default selection, playback or boot on HyperOS.',
            'A persistent private signing/update strategy and candidate package collision scan remain required.',
            'Only MUSIC_PLAYER is addressed; VIEW/audio URIs and other defaults are unchanged.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--throwaway-test-only',action='store_true',required=True,help='Confirm this is a disposable, non-shippable test APK')
    for n in ('router-apk','upstream-apk','source','report'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('aapt','aapt2','apksigner','zipalign'):p.add_argument('--'+n,required=True)
    a=p.parse_args()
    if a.report.exists() or a.report.is_symlink() or not a.report.parent.is_dir():raise RouterError('Use a new report path')
    try:result=inspect(a.router_apk,a.upstream_apk,a.source,a.aapt,a.aapt2,a.apksigner,a.zipalign);code=0
    except (RouterError,pre.PreflightError,scan.PackageScanError,intent.IntentProbeError,signers.SignerOutputError,
            OSError,ValueError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-spatialflow-router-host-probe-v1','status':'INCOMPLETE_HOLD','error':str(exc)};code=1
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')));return code
if __name__=='__main__':sys.exit(main())
