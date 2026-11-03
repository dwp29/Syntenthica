#!/usr/bin/env python3
"""Bounded offline extraction of APK manifests from a single EROFS image.

A pinned AOSP fsck.erofs runs without network or capabilities in a read-only
chroot with a bounded, noexec tmpfs. Only bounded manifest bytes and hashes
cross the namespace boundary; no APK or ROM code is executed or published.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import zipfile
import audit_checkvintf_snapshot as check
import audit_erofs_extract as erofs
import preflight_spatialflow as pre
import scan_apk_packages as scan

MAX_OUTPUT=24*1024*1024
MAX_MANIFEST=8*1024*1024
MAX_TOTAL_MANIFESTS=16*1024*1024
MAX_APKS=100
class GmsErofsError(RuntimeError):pass

# Only trusted code below executes in the namespace. Filesystem contents are
# untrusted data. Python modules needed after chroot are preloaded; no host
# binary from the image is launched. fsck logs and extracted files never leave
# tmpfs. The parent receives bounded manifest bytes and metadata only.
_LAUNCHER=r'''
import base64, ctypes, encodings.cp437, hashlib, json, os, resource, signal, stat, subprocess, sys, zipfile, zlib
root, mode = sys.argv[1:3]
if mode not in ('control','candidate'): raise RuntimeError('bad mode')
subprocess.run(['/usr/bin/mount','--make-rprivate','/'],check=True)
subprocess.run(['/usr/bin/mount','--bind',root,root],check=True)
subprocess.run(['/usr/bin/mount','-o','remount,bind,ro',root],check=True)
try: fd=os.open(root+'/readonly-marker',os.O_WRONLY)
except OSError: pass
else: os.close(fd);raise RuntimeError('root is writable')
subprocess.run(['/usr/bin/mount','-t','tmpfs','-o','size=768m,nr_inodes=12000,mode=0700,nosuid,nodev,noexec','tmpfs',root+'/out'],check=True)
os.chroot(root);os.chdir('/')
if any(os.path.exists(x) for x in ('/proc','/dev','/home')):raise RuntimeError('unexpected host paths')
os.mkdir('/out/extracted',0o700)
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(256*1024**2,256*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
libc=ctypes.CDLL(None,use_errno=True)
class Header(ctypes.Structure): _fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
class Data(ctypes.Structure): _fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
h=Header(0x20080522,0);empty=(Data*2)()
if libc.prctl(38,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'no_new_privs')
if libc.capset(ctypes.byref(h),ctypes.byref(empty))!=0:raise OSError(ctypes.get_errno(),'capset')
actual=(Data*2)()
if libc.capget(ctypes.byref(h),ctypes.byref(actual))!=0 or any(x.effective or x.permitted or x.inheritable for x in actual):raise RuntimeError('capabilities retained')
os.closerange(3,4096)
with open('/out/fsck.log','wb') as log:
    proc=subprocess.run(['/tool/fsck.erofs','--no-xattrs','--no-preserve','--extract=/out/extracted','/input/payload.erofs'],
                        input=b'',stdout=log,stderr=log,env={'PATH':'/empty','LANG':'C','LD_LIBRARY_PATH':'/lib/x86_64-linux-gnu'},timeout=150)
try:os.kill(-1,signal.SIGKILL)
except ProcessLookupError:pass
with open('/out/fsck.log','rb') as f: log_data=f.read(32*1024*1024+1)
result={'tool_exit_code':proc.returncode,'tool_log_bytes':len(log_data),'tool_log_sha256':hashlib.sha256(log_data).hexdigest(),
        'root_read_only':True,'tmpfs_bytes_limit':768*1024*1024,'tmpfs_inode_limit':12000,
        'no_new_privs':True,'capabilities_dropped':True,'paths_checked':0,'apks':[],'symlinks_not_followed':[]}
if mode=='control':result['synthetic_log']=log_data[:8192].decode('utf-8','replace')
if proc.returncode==0:
    total_manifest=0
    def fail(e):raise e
    for parent,dirs,files in os.walk('/out/extracted',topdown=True,onerror=fail,followlinks=False):
        if parent.count('/')>43:raise RuntimeError('depth limit')
        keep=[]
        for name in sorted(dirs):
            p=parent+'/'+name;s=os.lstat(p);result['paths_checked']+=1
            if stat.S_ISLNK(s.st_mode):
                if len(result['symlinks_not_followed'])>=100:raise RuntimeError('symlink limit')
                result['symlinks_not_followed'].append({'path':p[len('/out/extracted'):],'target':os.readlink(p)})
            elif stat.S_ISDIR(s.st_mode):keep.append(name)
            else:raise RuntimeError('unexpected directory entry')
        dirs[:]=keep
        for name in sorted(files):
            p=parent+'/'+name;s=os.lstat(p);result['paths_checked']+=1
            if stat.S_ISLNK(s.st_mode):
                if len(result['symlinks_not_followed'])>=100:raise RuntimeError('symlink limit')
                result['symlinks_not_followed'].append({'path':p[len('/out/extracted'):],'target':os.readlink(p)});continue
            if not stat.S_ISREG(s.st_mode) or not name.lower().endswith('.apk'):continue
            if len(result['apks'])>=100:raise RuntimeError('apk count limit')
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as f:
                st=os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=256*1024*1024:raise RuntimeError('apk size limit')
                h=hashlib.sha256()
                while True:
                    block=f.read(1024*1024)
                    if not block:break
                    h.update(block)
                f.seek(0)
                with zipfile.ZipFile(f) as z:
                    infos=z.infolist();names=[x.filename for x in infos]
                    if len(infos)>100000 or len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1:raise RuntimeError('ambiguous apk')
                    info=z.getinfo('AndroidManifest.xml')
                    if info.flag_bits & 1 or not 0<info.file_size<=8*1024*1024 or info.compress_type not in (0,8):raise RuntimeError('manifest size/type limit')
                    data=z.read(info)
                total_manifest+=len(data)
                if total_manifest>16*1024*1024:raise RuntimeError('manifest aggregate limit')
                after=os.fstat(f.fileno())
                if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('apk changed')
                result['apks'].append({'path':p[len('/out/extracted'):],'bytes':st.st_size,'sha256':h.hexdigest(),
                                       'manifest_bytes':len(data),'manifest_sha256':hashlib.sha256(data).hexdigest(),
                                       'manifest_zip_crc_checked':True,'manifest_base64':base64.b64encode(data).decode('ascii')})
        if result['paths_checked']>40000:raise RuntimeError('path limit')
print(json.dumps(result,separators=(',',':')),flush=True)
'''


def _reader_package(manifest: bytes,aapt: str,aapt2: str,scratch: Path) -> str:
    if not 0<len(manifest)<=MAX_MANIFEST:raise GmsErofsError('Manifest is empty or oversized')
    target=scratch/'manifest-only.apk'
    if target.exists() or target.is_symlink():raise GmsErofsError('Reader scratch not empty')
    try:
        with zipfile.ZipFile(target,'x') as z:z.writestr('AndroidManifest.xml',manifest)
        first=scan.parse_xmltree_package(pre.command([aapt,'dump','xmltree',str(target),'AndroidManifest.xml']))
        second=scan.parse_xmltree_package(pre.command([aapt2,'dump','xmltree','--file','AndroidManifest.xml',str(target)]))
        if first!=second:raise GmsErofsError('Manifest-only readers disagree')
        return first
    finally:target.unlink(missing_ok=True)


def manifest_reader_control(apk: Path,aapt: str,aapt2: str,scratch: Path) -> dict:
    if pre.digest_file(apk)!=(pre.APP_SIZE,pre.APP_SHA256):raise GmsErofsError('Control APK differs from pinned release')
    with zipfile.ZipFile(apk) as z:
        infos=z.infolist();names=[x.filename for x in infos]
        if len(names)!=len(set(names)) or names.count('AndroidManifest.xml')!=1:raise GmsErofsError('Control APK has ambiguous manifest')
        info=z.getinfo('AndroidManifest.xml')
        if not 0<info.file_size<=MAX_MANIFEST:raise GmsErofsError('Control manifest exceeds bound')
        data=z.read(info)
    package=_reader_package(data,aapt,aapt2,scratch)
    if package!=pre.APP_PACKAGE or pre.digest_file(apk)!=(pre.APP_SIZE,pre.APP_SHA256):raise GmsErofsError('Manifest-only reader control failed')
    return {'pinned_control_apk_sha256':pre.APP_SHA256,'package':package,'both_xml_readers_agree':True,
            'manifest_sha256':hashlib.sha256(data).hexdigest()}


def extract_raw(sandbox: Path,image: Path, *, control: bool) -> dict:
    if not shutil.which('unshare') or not 0<image.stat().st_size<=erofs.MAX_INPUT:
        raise GmsErofsError('Missing namespace tool or oversized EROFS payload')
    before=pre.digest_file(image);dest=sandbox/'input/payload.erofs'
    if dest.exists() or dest.is_symlink():raise GmsErofsError('Sandbox input exists')
    shutil.copyfile(image,dest);dest.chmod(0o444)
    if pre.digest_file(dest)!=before:raise GmsErofsError('Sandbox payload copy mismatch')
    args=[shutil.which('unshare'),'--user','--map-root-user','--mount','--net','--pid','--fork',
          sys.executable,'-I','-S','-c',_LAUNCHER,str(sandbox),'control' if control else 'candidate']
    proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          start_new_session=True,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    try:out,err=proc.communicate(timeout=180)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid,signal.SIGKILL);proc.communicate();raise GmsErofsError('EROFS sandbox timed out') from exc
    finally:dest.unlink(missing_ok=True)
    if proc.returncode or len(out)+len(err)>MAX_OUTPUT:
        safe=err.decode('utf-8','replace')[:2000] if control else 'raw candidate diagnostics withheld'
        raise GmsErofsError(f'EROFS isolated launcher failed ({proc.returncode}): {safe}')
    try:result=json.loads(out)
    except (UnicodeError,ValueError) as exc:raise GmsErofsError('Invalid isolated output') from exc
    if pre.digest_file(image)!=before:raise GmsErofsError('EROFS input changed')
    result['input_sha256']=before[1];return result


def decode_apks(result: dict,aapt: str,aapt2: str,scratch: Path) -> dict:
    if result.get('tool_exit_code')!=0:raise GmsErofsError('EROFS extraction failed')
    if not all(result.get(k) is True for k in ('root_read_only','no_new_privs','capabilities_dropped')):
        raise GmsErofsError('EROFS isolation checks failed')
    apks=result.get('apks');total=0
    if not isinstance(apks,list) or len(apks)>MAX_APKS:raise GmsErofsError('APK list exceeds bounds')
    rows=[];seen=set()
    for item in apks:
        try:
            path=item['path'];manifest=base64.b64decode(item['manifest_base64'],validate=True)
            if (not isinstance(path,str) or not path.startswith('/') or path in seen or not path.lower().endswith('.apk')
                or item['manifest_bytes']!=len(manifest) or item['manifest_sha256']!=hashlib.sha256(manifest).hexdigest()
                or item['manifest_zip_crc_checked'] is not True or not re.fullmatch(r'[0-9a-f]{64}',item['sha256'])
                or not 0<item['bytes']<=256*1024**2):raise GmsErofsError('Untrusted manifest metadata failed validation')
        except (KeyError,TypeError,ValueError) as exc:raise GmsErofsError('Untrusted manifest metadata malformed') from exc
        seen.add(path);total+=len(manifest)
        if total>MAX_TOTAL_MANIFESTS:raise GmsErofsError('Manifest aggregate exceeds bound')
        package=_reader_package(manifest,aapt,aapt2,scratch)
        rows.append({k:item[k] for k in ('path','bytes','sha256','manifest_bytes','manifest_sha256','manifest_zip_crc_checked')}
                    | {'package':package,'reader':'aapt_and_aapt2_xmltree_manifest_only'})
    return {'paths_checked':result['paths_checked'],'apk_count':len(rows),'apks':rows,
            'gms_package_found':any(x['package']=='com.google.android.gms' for x in rows),
            'symlinks_not_followed':result.get('symlinks_not_followed',[]),
            'isolation':{k:result[k] for k in ('root_read_only','no_new_privs','capabilities_dropped','tmpfs_bytes_limit','tmpfs_inode_limit')},
            'tool_exit_code':result['tool_exit_code'],'input_sha256':result['input_sha256'],
            'tool_log_bytes':result['tool_log_bytes'],'tool_log_sha256':result['tool_log_sha256']}


def setup(otatools: Path,work: Path,aapt: str,aapt2: str) -> tuple[Path,dict]:
    sandbox=work/'erofs-sandbox';sandbox.mkdir()
    check_tool=check.prepare_tool(otatools,sandbox)
    erofs_tool=erofs.prepare_tools(otatools,sandbox,check.HOST_LIBS)
    tree=work/'erofs-control/tree/app';tree.mkdir(parents=True)
    sample=b'synthetic-binary-manifest-for-extraction-only'
    with zipfile.ZipFile(tree/'sample.apk','x') as z:z.writestr('AndroidManifest.xml',sample)
    image=work/'erofs-control/good.img'
    proc=subprocess.run([shutil.which('unshare'),'--user','--map-root-user','--net','--pid','--fork',str(sandbox/'tool/mkfs.erofs'),str(image),str(tree.parent)],
                        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    if proc.returncode:raise GmsErofsError('Synthetic EROFS creation failed')
    good=extract_raw(sandbox,image,control=True)
    if (good.get('tool_exit_code')!=0 or len(good.get('apks',[]))!=1
        or base64.b64decode(good['apks'][0]['manifest_base64'],validate=True)!=sample):
        raise GmsErofsError('Synthetic EROFS positive control failed: '+str(good)[:1500])
    bad=work/'erofs-control/bad.img';bad.write_bytes(b'not an erofs filesystem')
    negative=extract_raw(sandbox,bad,control=True)
    if negative.get('tool_exit_code')==0 or negative.get('apks')!=[]:raise GmsErofsError('Malformed EROFS control was not rejected')
    sample_dir=work/'reader-control';sample_dir.mkdir();apk=pre.download_app(sample_dir)
    scratch=work/'reader-scratch';scratch.mkdir();reader=manifest_reader_control(apk,aapt,aapt2,scratch)
    return sandbox,{'aosp_tool':erofs_tool,'pinned_otatools_sha256':check_tool['otatools_sha256'],
                    'statement_signature_verified':False,'synthetic_positive_passed':True,
                    'synthetic_malformed_rejected':True,'real_manifest_reader_control':reader}
