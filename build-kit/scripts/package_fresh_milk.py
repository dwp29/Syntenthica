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
SCRIPTS = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer'
BASE = ROOT / 'release/Synthetica-2.0.zip'
BASE_SHA256 = 'b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
ENTRY_SHA256 = 'd6fa389a46945be0c050cd462bcfc46123004242728011c4bce7d2cbd2d0bbe3'
PREPARE_SHA256 = '0a6eedd69f2d2432b57bcaf64d7bd291b6466b59ad0658a6ed5ba403228a7ad4'
REFERENCE_DTB_SHA256 = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
UPDATE_BINARY = 'META-INF/com/google/android/update-binary'
BASE_FILES = ('LICENSE', 'META-INF/com/google/android/update-binary',
              'META-INF/com/google/android/updater-script', 'tools/busybox', 'tools/magiskboot')
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
    prepare = (SCRIPTS / 'prepare-boot.sh').read_bytes()
    if sha(entry) != ENTRY_SHA256 or sha(prepare) != PREPARE_SHA256:
        raise ValueError('tested installer template changed')

    # The installer verifies the exact image it may write.
    entry = replace_once(entry, TEMPLATE_IMAGE_SHA256.encode(), image_sha.encode())
    entry = replace_once(entry, b'kernel.string=Synthetica 2.0 Experimental - Neutron - MGLRU ON',
                         f'kernel.string={spec["name"]} {spec["kver"]} - Neutron - MGLRU ON'.encode())
    entry = replace_once(entry, b"'Synthetica 2.0 EXPERIMENTAL - Neutron / MGLRU ON'",
                         f"'{spec['release']}'".encode())
    if entry.count(REFERENCE_DTB_SHA256.encode()) != 1:
        raise ValueError('reference DTB guard is missing or ambiguous')

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
        'writes': ['boot partition only, after runtime checks'],
        'does_not_write': ['vbmeta', 'dtbo', 'vendor', 'system', 'userdata', 'ksud', 'modules'],
        'auto_backup': False,
    }
    files.update({
        'Image.gz': image,
        'anykernel.sh': entry,
        'tools/prepare-boot.sh': prepare,
        'README-FLASH.txt': (SCRIPTS / 'README-FLASH.txt').read_bytes(),
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
                'anykernel.sh', 'tools/prepare-boot.sh', 'tools/busybox', 'tools/magiskboot',
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
