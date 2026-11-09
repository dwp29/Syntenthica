#!/usr/bin/env python3
"""Package the exact offline-prepared private boot image as a guarded test ZIP."""
from __future__ import annotations
import argparse, hashlib, io, json, os, zipfile
from pathlib import Path
import audit_boot_avb_hash as avb
import audit_synthetica3_boot as audit
import build_synthetica31_control_boot as build
ROOT=Path(__file__).resolve().parents[2]
TEMPLATE=ROOT/'build-kit/ci/s31-control-installer/update-binary'
BASE=ROOT/'release/Synthetica-2.0.zip'
BASE_SHA='b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
CANDIDATE='5b772f4a8b8cc24c84ff57d619c63cd0710ff95858687aa4382350339f75564b'
BINARY='META-INF/com/google/android/update-binary'
README='''SY N T H E T I C A  3.1-control1 — ZIP UJI EKSPERIMENTAL

BELUM PERNAH DIUJI BOOT DI PERANGKAT. BUKAN PERBAIKAN BOOTLOOP TERBUKTI.
Target: Joyeuse + Infinity 4.1; tetapi identitas ROM/modul belum diverifikasi.
MGLRU tetap dikompilasi, namun default-nya nonaktif; UCLAMP dan root stack 3.1 tetap ada.

HANYA BOLEH DIPERTIMBANGKAN PADA ROM TARGET, BUKAN SISTEM ANDROID 16 SAAT INI.
Backup boot YANG TEPAT harus tersedia di luar perangkat serta OrangeFox dan cara
restore harus sudah dipastikan. Installer TIDAK membuat backup. Bootloop, hilang
root dan gangguan hardware tetap mungkin. Jangan wipe/format data atau mengubah
vbmeta untuk memaksa boot. Kesesuaian modul, sertifikat dan root belum diuji.

Installer memeriksa bootloader terbuka, device, slot, ukuran dan SHA-256 seluruh
boot saat ini terhadap image yang Anda berikan. Jika berbeda, instalasi dibatalkan
sebelum penulisan; jangan paksa atau menebak. Ini berarti image root-patched,
versi ROM lain, atau bahkan padding berbeda mungkin ditolak. Memasang image yang
berbeda hanya untuk melewati pemeriksaan bukan langkah yang disarankan.

ZIP menulis hanya boot, setelah memverifikasi kandidat, lalu membaca ulang hasil;
tidak menulis ksud, modul, dtbo, vbmeta, vendor, system atau userdata dan tidak
me-mount partisi. Bila penulisan/readback gagal, JANGAN REBOOT; pulihkan backup
boot yang tepat dari recovery. Tidak ada reboot otomatis.

Metadata AVB internal pada boot asli tidak bertanda tangan (algorithm NONE);
hash descriptor dihitung ulang untuk kandidat. Hash ini cocok, tetapi bukan
verifikasi signature atau chain: vbmeta eksternal/kepercayaan bootloader belum
diperiksa. Installer tidak menonaktifkan AVB dan tidak membuat signature baru.

Reference boot SHA-256: {reference}
Candidate boot SHA-256: {candidate}
Kernel Image.gz SHA-256: {kernel}
'''

def package(reference:Path, candidate:Path, output:Path):
    if output.exists() or output.is_symlink(): raise ValueError('refusing existing output')
    source=build.regular(reference,build.SIZE); target=build.regular(candidate,build.SIZE)
    if len(source)!=build.SIZE or build.sha(source)!=build.REFERENCE: raise ValueError('reference mismatch')
    if len(target)!=build.SIZE or build.sha(target)!=CANDIDATE: raise ValueError('candidate mismatch')
    before=audit.inspect_boot(reference); after=audit.inspect_boot(candidate)
    cmp=audit.compare_boot(before,after,build.IMAGE); check=avb.inspect(candidate)
    if not all(cmp['stable_header_fields_match'].values()) or not all(cmp['non_kernel_sections_match'].values()) or not cmp['candidate_kernel_equals_bundle_image'] or not cmp['candidate_legacy_boot_id_matches'] or not check['embedded_boot_hash']['digest_matches'] or not check['vbmeta_algorithm_none']:
        raise ValueError('candidate failed structural or embedded hash checks')
    b=build.regular(BASE,30_000_000)
    if build.sha(b)!=BASE_SHA: raise ValueError('base tools hash mismatch')
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        if z.namelist().count('tools/busybox')!=1: raise ValueError('missing busybox')
        bb=z.read('tools/busybox'); license=z.read('LICENSE')
    entry=TEMPLATE.read_bytes()
    for key,value,count in ((b'@REFERENCE@',build.REFERENCE.encode(),2),(b'@CANDIDATE@',CANDIDATE.encode(),1)):
        if entry.count(key)!=count: raise ValueError('unexpected installer template')
        entry=entry.replace(key,value)
    files={BINARY:entry,'META-INF/com/google/android/updater-script':b'# recovery update-binary only\n',
           'boot.img':target,'tools/busybox':bb,'LICENSE':license,
           'README-ID.txt':README.format(reference=build.REFERENCE,candidate=CANDIDATE,kernel=build.IMAGE).encode(),
           'BUILD-INFO.json':(json.dumps({'kind':'experimental_recovery_test_not_device_tested',
             'reference_boot_sha256':build.REFERENCE,'candidate_boot_sha256':CANDIDATE,'kernel_sha256':build.IMAGE,
             'auto_backup':False,'physical_boot':'NOT TESTED','external_avb_and_rom_modules':'NOT VERIFIED'},indent=2)+'\n').encode()}
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(fd,'wb') as f,zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,(2026,11,7,0,0,0));info.create_system=3
                info.external_attr=(0o100755 if name in (BINARY,'tools/busybox') else 0o100644)<<16
                z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        with zipfile.ZipFile(output) as z:
            if set(z.namelist())!=set(files) or len(z.namelist())!=len(files) or z.testzip(): raise ValueError('ZIP integrity failure')
            for name,data in files.items():
                if build.sha(z.read(name))!=build.sha(data): raise ValueError('ZIP member mismatch')
    except BaseException:
        output.unlink(missing_ok=True);raise
    with output.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(output),'bytes':output.stat().st_size,'sha256':digest,'candidate_sha256':CANDIDATE}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('reference','candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(a.reference,a.candidate,a.output),indent=2))
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,zipfile.BadZipFile) as e:raise SystemExit('Packaging refused: '+str(e))
