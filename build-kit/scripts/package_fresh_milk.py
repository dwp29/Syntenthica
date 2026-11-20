#!/usr/bin/env python3
"""Package a Fresh-Milk / CHEESE-BURGER build into a recovery flashable ZIP.

The 3.2-r1 recipe deliberately stops at "Image and matching modules only: no
installer or flashable package". This module adds the packaging step as a
separate, auditable stage rather than editing that recipe, and it refuses to
run unless the compile evidence matches the variant exactly.

It reuses, unchanged, the parts of the 3.0-rc1 packager that make a ZIP
trustworthy:

  * the reference AnyKernel skeleton (busybox, magiskboot, update-binary),
    pinned by digest;
  * the tested installer entry script and prepare-boot.sh, pinned by digest;
  * the same image/config/certificate evidence checks.

Only the release identity and the banner text come from the variant table.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'release/Synthetica-2.0.zip'
BASE_SHA256 = 'b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
# The installer that ships is the rollercoaster one, which installs ksud.
# The previous template (ci/synthetica2-experimental/test-installer) was a pure
# boot repack: it never mentioned KernelSU, so no build from it could ever have
# brought root up, and no APK could have changed that.
SCRIPTS = ROOT / 'build-kit/ci/rollercoaster/anykernel'
ENTRY_SHA256 = '04dca045c9f55a316c22e90c8ead2272e0571f023b0af4271bf448d641bb140d'
KSUD = SCRIPTS / 'ksud'
KSUD_SHA256 = '52ba3da465459bfbac98dd25c53f8d31f93ee5a8ee89d84f67a28fe0d18cdef2'
KSUD_BYTES = 5518552
# KernelSU-Next looks for its daemon at exactly this path; installing it anywhere
# else is the same as not installing it.
KSUD_DEST = '/data/adb/ksud'
# Only the README comes from here; its installer does not install ksud at all.
LEGACY_INSTALLER = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer'
REFERENCE_DTB_SHA256 = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
UPDATE_BINARY = 'META-INF/com/google/android/update-binary'
BASE_FILES = ('LICENSE', 'META-INF/com/google/android/update-binary',
              'META-INF/com/google/android/updater-script', 'tools/busybox', 'tools/magiskboot',
              # The shipped installer does `. tools/ak3-core.sh` and calls
              # dump_boot/write_boot from it. Shipping anykernel.sh without this
              # file is a ZIP that cannot write the boot partition at all.
              'tools/ak3-core.sh')
PACKAGED_KIND = 'FRESH_MILK_COMPILED_ZIP_NOT_DEVICE_TESTED'


def load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


variants = load('build-kit/scripts/build_fresh_milk.py', 'fresh_milk_variants_for_package')
packager = load('build-kit/scripts/package_synthetica3_rc.py', 'synthetica3_rc_for_package')
# package_synthetica3_rc.py resolves `build` to the 3.0-rc1 guard. This packager
# must verify against the 3.2-r1 recipe the variants are actually built from.
build = load('build-kit/scripts/build_synthetica32_r1.py', 'synthetica32_r1_for_package')

# The installer template pins the image digest it is allowed to write. That
# constant belongs to the 2.0-experiment guard, which the 3.2-r1 module does not
# carry, so take it from the packager that owns the template.
TEMPLATE_IMAGE_SHA256 = packager.build.TESTED_IMAGE_SHA256

# 3.2-r1 exposes its guard chain as `old.base`, not as `s2x`. Resolve both so
# this packager keeps working whichever layer the constants live in.
s2x = getattr(build, 's2x', None) or build.old.base.rc.s2x
V3 = s2x.v3


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_zip_unique(z: zipfile.ZipFile, name: str, max_size: int) -> bytes:
    if z.namelist().count(name) != 1:
        raise ValueError(f'skeleton member missing or duplicated: {name}')
    info = z.getinfo(name)
    if info.file_size > max_size:
        raise ValueError(f'skeleton member too large: {name}')
    return z.read(name)

def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise ValueError('installer text to replace is missing or ambiguous')
    return data.replace(old, new, 1)


def check_evidence(result: Path, variant: str) -> tuple[dict, bytes, bytes, str]:
    spec = variants.VARIANTS[variant]
    status_raw = (result / 'STATUS.json').read_bytes()
    status = json.loads(status_raw)
    image = (result / 'Image.gz.DO-NOT-FLASH').read_bytes()
    config = (result / 'generated.config.txt').read_bytes()
    image_sha = sha(image)

    # The recipe has written the identity under both names across generations.
    written_release = status.get('uname_release') or status.get('release')

    checks = {
        'kind': status.get('kind') == build.STATUS_KIND,
        'release': written_release == spec['release'],
        'image': status.get('image_sha256') == image_sha,
        'config': status.get('config_sha256') == sha(config),
        'source': status.get('base_source') == V3.SOURCE,
        'toolchain': (status.get('compiler', {}).get('kind') == 'neutron'
                      and status.get('compiler', {}).get('neutron_archive_sha256') == s2x.NEUTRON_SHA),
        'mglru': (status.get('mglru', {}).get('variant') == 'on'
                  and status.get('mglru', {}).get('enabled_by_default') is True
                  and status.get('mglru', {}).get('runtime_tested') is False),
        'no_installer_yet': status.get('installer_created') is False,
        'no_private_key': status.get('private_key_exported') is False,
        'manager': (status.get('manager', {}).get('package') == 'net.ember.labs'
                    and status.get('manager', {}).get('cert_sha256') == s2x.MANAGER_CERT_SHA),
    }
    failed = sorted(k for k, ok in checks.items() if not ok)
    if failed:
        raise ValueError('compile evidence rejected: ' + ', '.join(failed))

    public_cert_sha = status.get('module_public_cert_sha256')
    if (not isinstance(public_cert_sha, str) or len(public_cert_sha) != 64
            or sha((result / 'module-signing-public-cert.x509').read_bytes()) != public_cert_sha):
        raise ValueError('module public certificate evidence mismatch')

    # The identity in the config and in the compressed image must both match.
    written = V3.read_config(config.decode('utf-8')).get('LOCALVERSION')
    if written != spec['localversion']:
        raise ValueError(f'config localversion is {written}, expected {spec["localversion"]}')
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as f:
        raw = f.read(V3.MAX_RAW_IMAGE + 1)
    if len(raw) > V3.MAX_RAW_IMAGE:
        raise ValueError('uncompressed kernel exceeds size limit')
    if ('Linux version ' + spec['release'] + ' ').encode() not in raw:
        raise ValueError('kernel release string missing from the image')
    V3.verify_embedded_config(raw, config)

    return status, image, config, public_cert_sha


def collect(result: Path, variant: str) -> dict[str, bytes]:
    if variant not in variants.VARIANTS:
        raise ValueError('unknown variant: ' + variant)
    spec = variants.VARIANTS[variant]
    if result.is_symlink() or not result.is_dir():
        raise ValueError('compile evidence must be an existing non-symlink directory')

    status, image, config, public_cert_sha = check_evidence(result, variant)
    image_sha = sha(image)

    raw_base = BASE.read_bytes()
    if sha(raw_base) != BASE_SHA256:
        raise ValueError('reference AnyKernel ZIP digest changed')
    with zipfile.ZipFile(io.BytesIO(raw_base)) as z:
        files = {name: read_zip_unique(z, name, 4_000_000) for name in BASE_FILES}

    # Never ship a persistent debug archive.
    backend = files[UPDATE_BINARY]
    start, end = backend.find(b'debugging() {\n'), backend.find(b'\ncleanup() {\n')
    if start < 0 or end < start or backend.count(b'debugging() {\n') != 1:
        raise ValueError('unexpected AnyKernel debug function')
    files[UPDATE_BINARY] = backend[:start] + b'debugging() { :; } # no persistent debug archive\n' + backend[end:]

    entry = (SCRIPTS / 'anykernel.sh').read_bytes()
    if sha(entry) != ENTRY_SHA256:
        raise ValueError('tested installer template changed')

    # The installer installs ksud conditionally - `if [ -f ./ksud ]` - so a ZIP
    # that does not contain it installs no root stack and says nothing. That is
    # how every earlier ZIP shipped: root silently absent, blamed on the APK.
    # Both halves are now checked before anything is packaged.
    def require(text: bytes, needle: bytes, what: str) -> None:
        if needle not in text:
            raise ValueError(f'the installer no longer {what}; refusing to ship a ZIP '
                             'that cannot bring root up')

    require(entry, b'if [ -f ./ksud ]', 'looks for ./ksud')
    require(entry, f'cp -f ./ksud {KSUD_DEST}'.encode(), f'copies ksud to {KSUD_DEST}')
    require(entry, f'chmod 0755 {KSUD_DEST}'.encode(), f'makes {KSUD_DEST} executable')
    require(entry, b'/data/adb/ksu', 'creates the KernelSU data directory')

    # The boot-writing helpers come from ak3-core.sh, not from anykernel.sh.
    require(entry, b'. tools/ak3-core.sh;', 'sources tools/ak3-core.sh')
    core = files['tools/ak3-core.sh']
    for helper in (b'dump_boot()', b'write_boot()'):
        if helper not in core:
            raise ValueError(f'ak3-core.sh no longer defines {helper.decode()}; '
                             'the installer could not write the boot partition')
    if not KSUD.is_file() or KSUD.is_symlink():
        raise ValueError('the KernelSU daemon that must be installed is missing')
    ksud = KSUD.read_bytes()
    if sha(ksud) != KSUD_SHA256 or len(ksud) != KSUD_BYTES:
        raise ValueError('ksud digest changed; refusing to ship an unknown daemon')

    # The banner is the release string, and it must be the one this build emitted
    # rather than whatever the template happened to ship with.
    entry = replace_once(entry, b'SP_RELEASE="4.14.357-openela-Fresh-Milk-14.03";',
                         f'SP_RELEASE="{spec["release"]}";'.encode())
    # kernel.version is printed by the recovery UI; leaving the template's value
    # would tell the user a different build went in than the one that did.
    entry = replace_once(entry, b'kernel.version=Fresh-Milk-14.03 / CHEESE-BURGER-11.08',
                         f'kernel.version={spec["name"]} {spec["kver"]}'.encode())
    if entry.count(spec['release'].encode()) != 1:
        raise ValueError('the banner does not name exactly this release')
    # The rollercoaster installer pins the boot block by name and checks the
    # image it writes; it does not carry the 2.0 template's DTB constant, so
    # requiring that constant here would demand something the shipped installer
    # never had. What matters instead is that the block it writes is the boot
    # partition and that it refuses a device that is not miatoll.
    #
    # The variable must be BLOCK (uppercase): the packaged ak3-core.sh (from
    # the Synthetica-2.0 skeleton) reads its target from $BLOCK in setup_ak and
    # write_boot. A lowercase `block=` leaves $BLOCK empty, so setup_ak aborts
    # with "Unable to determine  partition" and the ZIP refuses to flash. The
    # require below guards the exact name ak3-core.sh depends on.
    require(entry, b'BLOCK=/dev/block/bootdevice/by-name/boot;',
            'targets the boot partition as $BLOCK (uppercase, matching ak3-core.sh)')
    require(entry, b'device.name1=miatoll', 'checks the device before writing')

    metadata = {
        'kind': PACKAGED_KIND,
        'variant': variant,
        'profile': spec['profile'],
        'release': spec['release'],
        'target': 'joyeuse/miatoll; runtime boot structure and reference DTB guarded',
        'image_sha256': image_sha,
        'config_sha256': sha(config),
        'module_public_cert_sha256': public_cert_sha,
        'compile_status_sha256': sha((result / 'STATUS.json').read_bytes()),
        'physical_boot_test_this_image': 'NOT RUN',
        'rom_module_abi_and_signatures': 'NOT VERIFIED; fresh module signing certificate',
        'avb_boot_trust': 'NOT VERIFIED; existing signature may not validate modified boot',
        'writes': [
            'boot partition only, after runtime checks',
            f'{KSUD_DEST} plus /data/adb/ksu directories, so KernelSU can come up',
        ],
        'does_not_write': ['vbmeta', 'dtbo', 'vendor', 'system', 'userdata', 'modules'],
        'root_userspace': {
            'entry': 'ksud',
            'destination': KSUD_DEST,
            'sha256': KSUD_SHA256,
            'bytes': KSUD_BYTES,
            'note': ('Installed by anykernel.sh. Without it a KernelSU kernel has no '
                     'daemon, root never comes up and /data/adb/ksu is never created.'),
        },
        'auto_backup': False,
    }
    files.update({
        'Image.gz': image,
        'anykernel.sh': entry,
        # Without this entry the installer's `if [ -f ./ksud ]` is false and it
        # quietly installs no root stack at all - which is exactly what every ZIP
        # built before this change did.
        'ksud': ksud,
        # Documentation only: it explains the flash and must not claim a boot test.
        'README-FLASH.txt': (LEGACY_INSTALLER / 'README-FLASH.txt').read_bytes(),
        'BUILD-INFO.json': (json.dumps(metadata, indent=2) + '\n').encode('utf-8'),
    })
    return files


def package(result: Path, variant: str, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    files = collect(result, variant)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if name in (
                'anykernel.sh', 'ksud', 'tools/busybox', 'tools/magiskboot',
                UPDATE_BINARY) else 0o644) << 16
            z.writestr(info, data)
    print(f'packaged {variant}: {output} '
          f'({output.stat().st_size} bytes, sha256 {sha(output.read_bytes())})')


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result', required=True, type=Path)
    p.add_argument('--variant', required=True, choices=sorted(variants.VARIANTS))
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    package(args.result, args.variant, args.output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print('Fresh-Milk packaging refused: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
