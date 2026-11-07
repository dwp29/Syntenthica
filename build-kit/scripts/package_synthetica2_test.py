#!/usr/bin/env python3
"""Package an explicitly untested Joyeuse experimental recovery installer.

The original Actions artifact remains compile-only evidence. This separate
installer changes the current boot only after conservative runtime checks.
No device, module ABI, AVB trust, or root compatibility is established here.
No signing keys or kernel modules are included.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer'
BASE = ROOT / 'release/Synthetica-2.0.zip'
BASE_SHA256 = 'b1a0be5c7402a14d25f64fab495d6dd7e945dab18fa55c2fd164c5ced853897c'
IMAGE_SHA256 = '3a9f39f8f7ea79c9251a896050dfeb60395f1194a064f91a85a8fe8ae38adaea'
REFERENCE_DTB_SHA256 = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
EVIDENCE_SHA256 = '742068c09eb99f6eb37d55aa3ee1bca9ee156db592d10d3d901fca738900dabc'
BASE_FILES = ('LICENSE', 'META-INF/com/google/android/update-binary',
              'META-INF/com/google/android/updater-script', 'tools/busybox', 'tools/magiskboot')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_zip_unique(z: zipfile.ZipFile, name: str, max_size: int) -> bytes:
    infos = [x for x in z.infolist() if x.filename == name]
    if len(infos) != 1 or infos[0].file_size > max_size:
        raise ValueError('missing, duplicate or oversized ZIP member: ' + name)
    return z.read(infos[0])


def collect(evidence: Path) -> dict[str, bytes]:
    raw_base = BASE.read_bytes()
    raw_evidence = evidence.read_bytes()
    if sha(raw_base) != BASE_SHA256 or sha(raw_evidence) != EVIDENCE_SHA256:
        raise ValueError('base ZIP or downloaded compile evidence checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(raw_base)) as z:
        files = {name: read_zip_unique(z, name, 4_000_000) for name in BASE_FILES}
    # The upstream backend otherwise creates a persistent debug archive of the
    # unpacked workspace (including the user's boot image) when a debug marker
    # exists. Disable only that function; no silent boot copies to userdata.
    name = 'META-INF/com/google/android/update-binary'
    backend = files[name]
    start, end = backend.find(b'debugging() {\n'), backend.find(b'\ncleanup() {\n')
    if start < 0 or end < start or backend.count(b'debugging() {\n') != 1:
        raise ValueError('unexpected AnyKernel debugging function; refusing to patch')
    files[name] = backend[:start] + b'debugging() { :; } # disabled for this test installer\n' + backend[end:]
    with zipfile.ZipFile(io.BytesIO(raw_evidence)) as z:
        image = read_zip_unique(z, 'Image.gz.DO-NOT-FLASH', 25_000_000)
        config = read_zip_unique(z, 'generated.config.txt', 1_000_000)
        status = json.loads(read_zip_unique(z, 'STATUS.json', 100_000))
    if (sha(image) != IMAGE_SHA256 or status['image_sha256'] != IMAGE_SHA256
            or sha(config) != status['config_sha256']
            or status['kind'] != 'EXPERIMENTAL_COMPILED_ONLY_DO_NOT_FLASH'
            or status['compiler']['kind'] != 'neutron'
            or status['mglru']['variant'] != 'on'
            or status['mglru']['enabled_by_default'] is not True
            or status['mglru']['runtime_tested'] is not False
            or status['installer_created'] is not False
            or status['private_key_exported'] is not False
            or b'CONFIG_LRU_GEN=y\n' not in config
            or b'CONFIG_LRU_GEN_ENABLED=y\n' not in config):
        raise ValueError('unexpected experimental build evidence')
    with gzip.GzipFile(fileobj=io.BytesIO(image)) as f:
        raw_image = f.read(128 * 1024 * 1024 + 1)
    if len(raw_image) > 128 * 1024 * 1024:
        raise ValueError('uncompressed kernel exceeds size limit')
    sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
    from build_synthetica3 import verify_embedded_config
    verify_embedded_config(raw_image, config)
    if b'Linux version 4.14.357-openela-Synthetica-2.0-exp' not in raw_image:
        raise ValueError('unexpected kernel release')
    files.update({
        'Image.gz': image,
        'anykernel.sh': (SCRIPTS / 'anykernel.sh').read_bytes(),
        'tools/prepare-boot.sh': (SCRIPTS / 'prepare-boot.sh').read_bytes(),
        'README-FLASH.txt': (SCRIPTS / 'README-FLASH.txt').read_bytes(),
    })
    if (IMAGE_SHA256.encode() not in files['anykernel.sh']
            or REFERENCE_DTB_SHA256.encode() not in files['anykernel.sh']):
        raise ValueError('runtime installer guards are not pinned to the intended inputs')
    metadata = {
        'kind': 'EXPERIMENTAL_RECOVERY_INSTALLER_NOT_DEVICE_TESTED',
        'target': 'joyeuse/miatoll; runtime boot structure and reference DTB guarded',
        'compiler': status['compiler']['clang_version'].splitlines()[0],
        'mglru_default': 'enabled in embedded kernel config; runtime untested',
        'image_sha256': IMAGE_SHA256,
        'reference_dtb_sha256': REFERENCE_DTB_SHA256,
        'original_compile_evidence_sha256': EVIDENCE_SHA256,
        'reference_installer_sha256': BASE_SHA256,
        'physical_boot_test': 'NOT RUN',
        'rom_module_abi_and_signatures': 'NOT VERIFIED',
        'avb_boot_trust': 'NOT VERIFIED; existing signature may not validate the modified boot',
        'manager_and_root': 'NOT TESTED; existing userspace is not changed',
        'writes': ['boot partition only, after runtime checks'],
        'does_not_write': ['vbmeta', 'dtbo', 'vendor', 'system', 'userdata', 'ksud', 'modules'],
        'auto_backup': False,
    }
    files['BUILD-INFO.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    return files


def package(evidence: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    files = collect(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if name in ('anykernel.sh', 'tools/prepare-boot.sh', 'tools/busybox',
                                          'tools/magiskboot', 'META-INF/com/google/android/update-binary') else 0o644
                info.external_attr = (0o100000 | mode) << 16
                z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None or set(z.namelist()) != set(files):
                raise ValueError('created ZIP failed integrity verification')
            if sha(z.read('Image.gz')) != IMAGE_SHA256:
                raise ValueError('created ZIP contains an unexpected kernel')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print(json.dumps({'path': str(output), 'bytes': output.stat().st_size,
                      'sha256': sha(output.read_bytes()), 'image_sha256': IMAGE_SHA256,
                      'kind': 'EXPERIMENTAL_RECOVERY_INSTALLER_NOT_DEVICE_TESTED'}, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    package(args.evidence, args.output)


if __name__ == '__main__':
    main()
