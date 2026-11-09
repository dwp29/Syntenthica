#!/usr/bin/env python3
"""Add a targeted unsigned-AVB repair to the otherwise unchanged 3.1 ZIP."""
import argparse, hashlib, json, zipfile
from pathlib import Path

BASE_SHA = '1ffe861ceaa2775e4f75bc9f7ecd4b7c56cf9c146f1690eb941c8dd2e5200d4a'
KERNEL_SHA = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
CORE_SHA = '0544478d92865e2f16aab00676de475af8bbbb0abecea738716f4aea3f484c9b'
ROM_BOOT_SHA = 'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f'
MARKER = b'  blockdev --setrw $BLOCK 2>/dev/null;\n'
PATCH = b'''  # Infinity 4.1 exact stock boot: correct a reproducible unsigned embedded AVB digest.
  # For all other inputs the 3.1 installer path is unchanged.
  s31_orig_sha=$($BIN/busybox sha256sum "$BOOTIMG" | $BIN/busybox cut -d' ' -f1);
  if [ "$s31_orig_sha" = "d33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f" ]; then
    ui_print "Infinity 4.1: repairing unsigned embedded AVB hash...";
    "$BIN/fix-avb" "$AKHOME/boot-new.img" "$BIN/busybox" || abort "AVB repair failed; boot not written.";
  fi;
'''
README = '''Synthetica 3.1 - AVB fix TEST

Kernel, ksud dan installer dasar sama dengan ZIP 3.1 sebelumnya. Paket ini
menghitung ulang hash AVB embedded UNSIGNED hanya ketika boot input identik
persis dengan boot resmi Infinity X 4.1 GAPPS 21.10.2026 yang diaudit. Pada boot
lain installer berjalan seperti 3.1 sebelumnya; ZIP tidak mengunci ke ROM itu.
Tidak memodifikasi vbmeta eksternal. Jika pemeriksaan AVB sasaran gagal,
pemasangan berhenti sebelum menulis boot.

Ini perbaikan masalah hash yang teramati offline, BUKAN jaminan boot A17.
Modul ROM Infinity yang diperiksa masih berbeda ABI/signature; pemuatan modul,
root, semua ROM/versi Android, boot fisik dan AVB eksternal belum teruji.

Sebelum flash pastikan Joyeuse/miatoll sesuai, bootloader terbuka, OrangeFox
berfungsi, dan backup boot yang tepat dapat dipulihkan. Installer asli tidak
membuat backup dan dapat mengganti /data/adb/ksud sebelum menulis boot. Jika
penulisan gagal, jangan reboot sebelum backup boot yang tepat dipulihkan.
Tidak wipe data dan jangan mengubah vbmeta untuk memaksa boot.
'''.encode()

def sha(data): return hashlib.sha256(data).hexdigest()

def package(base, helper, expected_helper_sha, output):
    if output.exists() or output.is_symlink(): raise ValueError('output already exists')
    if base.is_symlink() or not base.is_file() or helper.is_symlink() or not helper.is_file(): raise ValueError('inputs must be regular files')
    original=base.read_bytes();binary=helper.read_bytes()
    if sha(original)!=BASE_SHA or sha(binary)!=expected_helper_sha: raise ValueError('input hash mismatch')
    # Require little-endian ELF32 for ARM, with an absolute size bound.
    if len(binary)>2_000_000 or binary[:7]!=b'\x7fELF\x01\x01\x01' or int.from_bytes(binary[18:20],'little')!=40:
        raise ValueError('helper must be ARM32 ELF')
    with zipfile.ZipFile(base) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or z.testzip(): raise ValueError('bad source ZIP')
        data={name:z.read(name) for name in names}
    if sha(data['Image.gz'])!=KERNEL_SHA or sha(data['tools/ak3-core.sh'])!=CORE_SHA:
        raise ValueError('kernel/core mismatch')
    core=data['tools/ak3-core.sh']
    if core.count(MARKER)!=1 or b'fix-avb' in core: raise ValueError('unexpected core')
    data['tools/ak3-core.sh']=core.replace(MARKER,PATCH+MARKER)
    data['tools/fix-avb']=binary
    data['README-FLASH.txt']=README
    info=json.loads(data['BUILD-INFO.txt'])
    info['kind']='SYNTHETICA_3_1_TARGETED_UNSIGNED_AVB_FIX_TEST'
    info['avb_patch_scope']='exact public Infinity 4.1 GAPPS stock boot SHA only; other boot images use unchanged 3.1 installer path'
    info['avb_helper_sha256']=expected_helper_sha
    info['physical_boot_test']='NOT RUN'
    data['BUILD-INFO.txt']=(json.dumps(info,indent=2)+'\n').encode()
    try:
        with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for name,content in sorted(data.items()):
                zi=zipfile.ZipInfo(name,(2026,11,7,0,0,0));zi.create_system=3
                executable=name in ('META-INF/com/google/android/update-binary','anykernel.sh','ksud') or name.startswith('tools/')
                zi.external_attr=(0o100755 if executable else 0o100644)<<16
                z.writestr(zi,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        with zipfile.ZipFile(output) as z:
            if z.testzip() or set(z.namelist())!=set(data) or len(z.namelist())!=len(data): raise ValueError('output archive invalid')
            for n in data:
                if z.read(n)!=data[n]:raise ValueError('output content mismatch')
    except BaseException:
        output.unlink(missing_ok=True);raise
    return {'sha256':sha(output.read_bytes()),'bytes':output.stat().st_size,'image_sha256':KERNEL_SHA,'helper_sha256':expected_helper_sha}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','helper','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--helper-sha256',required=True)
    a=p.parse_args();print(json.dumps(package(a.base,a.helper,a.helper_sha256,a.output),indent=2))
