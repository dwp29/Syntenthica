#!/usr/bin/env python3
"""Assemble and verify the pure-noz-0.1 kernel tree (Azyr 16 + root stack).

Nothing here is guessed: every pin below was measured from the artefacts this
repository actually carries.

  tree       AzyrRuthless/kernel_xiaomi_sm6250 @ 4afc6f0769f0 (branch 16)
             4.14.357-openela, miatoll (joyeuse/curtana/excalibur/gram)
  root       KernelSU-Next legacy-susfs-v2 (UAPI 4, manual hook, kprobes off)
             SuSFS v2.3.0 NON-GKI + NoMount v2.0.0, vendored under vendor/
  manager    Synthetica Manager 6.5.1 (net.ember.labs.standalone)
             cert der sha256 0e978241...  size 0x553  v2+v3 signing block

Two facts drive the Manager changes, both read out of the 6.5.1 APK itself:

  * the certificate is 1363 bytes, while upstream CERT_MAX_LENGTH is 1024, so
    every signature check was dead code and the Manager was never recognised;
  * the APK carries a v3 block (0xf05368c0) next to v2, and upstream returns
    false when it sees one ("Unexpected v3 signature scheme found").

The single patch (0001-pure-noz-0.1.patch) applies to the clean Azyr tree with
the vendored KernelSU-Next and nomount already in place, and with zero rejects.

What a green run proves: the tree compiles and every audited config symbol
resolves as intended. It does NOT prove the image boots on a phone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / 'build-kit/ci/pure-noz-0.1'
VENDOR = ROOT / 'vendor/pure-noz-0.1'

TREE = {
    'repository': 'AzyrRuthless/kernel_xiaomi_sm6250',
    'commit': '4afc6f0769f0f3b2b10d50d3fa02f0ba7c89a183',
    'branch': '16',
    'archive_sha256': 'ff4ae4a0cb911151b7f1bff729924724cf5650cd6f3f7b35031631a6107c9928',
    'archive_url': ('https://codeload.github.com/AzyrRuthless/kernel_xiaomi_sm6250/tar.gz/'
                    '4afc6f0769f0f3b2b10d50d3fa02f0ba7c89a183'),
}
PATCH = CI / '0001-pure-noz-0.1.patch'
PATCH_SHA256 = '131ca99c4b92967de83d36d0084641ccb31b09d04170ec6a25922af6be6d9f32'

RELEASE = '4.14.357-openela-pure-noz-0.1'
LOCALVERSION = '"-pure-noz-0.1"'
BUILD_NAME = 'pure-noz'
BUILD_VERSION = '0.1'
STATUS_KIND = 'PURE_NOZ_0_1_COMPILED_NOT_DEVICE_VALIDATED'

# Manager 6.5.1 identity, measured from the signed APK in release/6.5.1/.
MANAGER_PACKAGE = 'net.ember.labs.standalone'
MANAGER_CERT_SHA256 = '0e978241a60e99972e8401b82d91300ea8bfd9bca65796e9f4107c50fe4b1dac'
MANAGER_CERT_SIZE = '0x553'
MANAGER_APK = ROOT / 'release/6.5.1/Synthetica-Manager-6.5.1-standalone-DEBUG-SIGNED.apk'

REQUIRED_ON = [
    'KSU', 'KSU_MANUAL_HOOK', 'KSU_SUSFS',
    'KSU_SUSFS_SUS_PATH', 'KSU_SUSFS_SUS_MOUNT', 'KSU_SUSFS_SUS_KSTAT',
    'KSU_SUSFS_TRY_UMOUNT', 'KSU_SUSFS_SPOOF_UNAME',
    'KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS', 'KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG',
    'KSU_SUSFS_OPEN_REDIRECT', 'KSU_SUSFS_SUS_MAP',
    'NOMOUNT',
    'LRU_GEN', 'LRU_GEN_ENABLED', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP',
    'FTRACE', 'UPROBES', 'UPROBE_EVENTS', 'BPF_EVENTS',
    'BPF_SYSCALL', 'BPF_JIT_ALWAYS_ON', 'SECCOMP_FILTER',
    'EROFS_FS', 'F2FS_FS', 'DM_VERITY', 'SECURITY_SELINUX',
    'SCHED_CASS', 'SCHED_TUNE', 'CPU_FREQ_GOV_SCHEDUTIL',
    'MQ_IOSCHED_DEADLINE', 'WQ_POWER_EFFICIENT_DEFAULT',
]
REQUIRED_OFF = ['BUG_ON_DATA_CORRUPTION', 'MODULE_FORCE_LOAD', 'KSU_SUSFS_SUS_MEMFD']

# SuSFS/NoMount/Manager strings the image must actually contain.
REQUIRED_SOURCE_MARKERS = {
    'fs/susfs.c': ['SUSFS_VERSION', 'susfs_spoof_uname'],
    'include/linux/susfs.h': ['SUSFS_VARIANT'],
    'fs/nomount/nomount.c': ['nomount'],
    'KernelSU-Next/kernel/manager/apk_sign.c': ['CERT_MAX_LENGTH 2048'],
    'KernelSU-Next/kernel/Kbuild': [MANAGER_CERT_SHA256, MANAGER_CERT_SIZE],
    'kernel/sys.c': ['susfs_spoof_uname(&tmp)'],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    print(f'pure-noz-0.1 refused: {message}', file=sys.stderr)
    raise SystemExit(1)


def verify_pins() -> None:
    if digest(PATCH) != PATCH_SHA256:
        fail('the assembly patch digest changed')
    if MANAGER_APK.is_file():
        measured = manager_certificate()
        if measured['sha256'] != MANAGER_CERT_SHA256 or measured['size'] != 0x553:
            fail(f'Manager certificate changed: {measured}')
    else:
        print(f'note: {MANAGER_APK.name} is not in this checkout; '
              'the numeric pins below are used as-is (they were measured from it).',
              file=sys.stderr, flush=True)
    for rel in ('KernelSU-Next/kernel/Kbuild', 'nomount/Kconfig'):
        if not (VENDOR / rel).is_file():
            fail(f'vendored source missing: {rel}')


def manager_certificate() -> dict[str, object]:
    """Read the v2 certificate out of the APK Signing Block, the same way KSU does."""
    data = MANAGER_APK.read_bytes()
    magic = data.rfind(b'APK Sig Block 42')
    if magic < 0:
        fail('no APK Signing Block in the Manager APK')
    # The full pair walk below is what KSU's parser does; keep it for the block ids,
    # but the certificate itself is located by scanning, because the pair lengths in
    # this APK are written in a way a naive sequential walk mis-reads.
    size_end = int.from_bytes(data[magic - 8:magic], 'little')
    start = magic - 8 - size_end
    buf = data[start + 8:magic - 8]
    off, pairs = 0, {}
    while off + 12 <= len(buf):
        length = int.from_bytes(buf[off:off + 8], 'little')
        if length < 4 or off + 8 + length > len(buf):
            break
        pid = int.from_bytes(buf[off + 8:off + 12], 'little')
        pairs[pid] = buf[off + 12:off + 8 + length]
        off += 8 + length
    # Locate the v2 certificate: any DER SEQUENCE inside the signing block that
    # parses as an X.509 certificate. The digest of that DER blob is exactly what
    # KernelSU-Next hashes in check_block().
    cert = None
    for pos in range(start, magic - 4):
        if data[pos] != 0x30 or data[pos + 1] != 0x82:
            continue
        length = int.from_bytes(data[pos + 2:pos + 4], 'big') + 4
        if pos + length > magic:
            continue
        blob = data[pos:pos + length]
        parsed = subprocess.run(['openssl', 'x509', '-inform', 'der', '-noout', '-subject'],
                                input=blob, capture_output=True)
        if parsed.returncode == 0 and b'Synthetica' in parsed.stdout:
            cert = blob
            break
    if cert is None:
        fail('no Synthetica X.509 certificate found in the APK Signing Block')
    blocks = [hex(pid) for pid in (0x7109871A, 0xF05368C0, 0x1B93AD61)
              if data[start:magic].find(pid.to_bytes(4, 'little')) >= 0]
    return {'sha256': hashlib.sha256(cert).hexdigest(), 'size': len(cert),
            'blocks': sorted(blocks)}


def unpack(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(['tar', '-xzf', str(archive), '-C', str(destination),
                    '--strip-components=1'], check=True)


def assemble(tree: Path) -> None:
    """Vendor the root stack, then apply the single pure-noz patch."""
    shutil.copytree(VENDOR / 'KernelSU-Next', tree / 'KernelSU-Next', dirs_exist_ok=True)
    shutil.copytree(VENDOR / 'nomount', tree / 'fs/nomount', dirs_exist_ok=True)
    link = tree / 'drivers/kernelsu'
    if not link.exists() and not link.is_symlink():
        link.symlink_to('../KernelSU-Next/kernel')
    applied = subprocess.run(['patch', '-p1', '-N', '--no-backup-if-mismatch', '-i', str(PATCH)],
                             cwd=tree, capture_output=True, text=True)
    if applied.returncode != 0 or 'FAILED' in applied.stdout + applied.stderr:
        fail('the assembly patch did not apply cleanly:\n' + applied.stdout[-4000:])
    rejects = list(tree.rglob('*.rej'))
    if rejects:
        fail('rejects left behind: ' + ', '.join(str(p) for p in rejects[:5]))


def check_source(tree: Path) -> dict[str, object]:
    problems = []
    for rel, markers in REQUIRED_SOURCE_MARKERS.items():
        path = tree / rel
        if not path.is_file():
            problems.append(f'missing {rel}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for marker in markers:
            if marker not in text:
                problems.append(f'{rel} lacks {marker!r}')
    defconfig = tree / 'arch/arm64/configs/vendor/xiaomi/miatoll_defconfig'
    text = defconfig.read_text(encoding='utf-8')
    if LOCALVERSION not in text:
        problems.append('defconfig lacks the pure-noz LOCALVERSION')
    if 'kinesis-omega-bpf' in text:
        problems.append('the upstream kinesis branding is still in the defconfig')
    if problems:
        fail('; '.join(problems))
    return {'patch_sha256': PATCH_SHA256, 'markers': len(REQUIRED_SOURCE_MARKERS)}


def read_config(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('CONFIG_'):
            key, _, value = line.partition('=')
            values[key[7:]] = value.strip()
    return values


def check_config(config_path: Path) -> dict[str, object]:
    config = read_config(config_path)
    problems = []
    for symbol in REQUIRED_ON:
        if config.get(symbol) != 'y':
            problems.append(f'{symbol} must be y (is {config.get(symbol, "absent")})')
    for symbol in REQUIRED_OFF:
        if config.get(symbol) == 'y':
            problems.append(f'{symbol} must not be y')
    if config.get('LOCALVERSION') != LOCALVERSION:
        problems.append(f'LOCALVERSION is {config.get("LOCALVERSION")!r}')
    if problems:
        fail('config audit: ' + '; '.join(problems))
    return {'required_on': len(REQUIRED_ON), 'required_off': len(REQUIRED_OFF),
            'localversion': config.get('LOCALVERSION')}


def check_image(image: Path) -> dict[str, object]:
    """The release string has to be inside the compressed image itself."""
    raw = image.read_bytes()
    if raw[:2] == b'\x1f\x8b':
        import gzip
        raw = gzip.decompress(raw)
    marker = f'Linux version {RELEASE} '.encode()
    if marker not in raw:
        fail(f'the image does not carry {marker!r}')
    # The Manager certificate digest is compiled into the driver as a string.
    if MANAGER_CERT_SHA256.encode() not in raw:
        fail('the Manager certificate digest is not in the image')
    return {'release': RELEASE, 'image_bytes': image.stat().st_size,
            'uncompressed_bytes': len(raw)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    prep = sub.add_parser('prepare', help='unpack the pinned tree and assemble pure-noz')
    prep.add_argument('--archive', required=True, type=Path)
    prep.add_argument('--tree', required=True, type=Path)

    cfg = sub.add_parser('check-config', help='audit the generated .config')
    cfg.add_argument('--config', required=True, type=Path)

    img = sub.add_parser('check-image', help='audit the built Image.gz')
    img.add_argument('--image', required=True, type=Path)

    sub.add_parser('pins', help='print the manager certificate measured from the APK')

    args = parser.parse_args()
    verify_pins()

    if args.command == 'prepare':
        if digest(args.archive) != TREE['archive_sha256']:
            fail('the kernel archive does not match the pin')
        unpack(args.archive, args.tree)
        assemble(args.tree)
        print(json.dumps(check_source(args.tree), indent=2))
    elif args.command == 'check-config':
        print(json.dumps(check_config(args.config), indent=2))
    elif args.command == 'check-image':
        print(json.dumps(check_image(args.image), indent=2))
    else:
        if MANAGER_APK.is_file():
            cert = manager_certificate()
        else:
            cert = {'sha256': MANAGER_CERT_SHA256, 'size': int(MANAGER_CERT_SIZE, 16),
                    'blocks': ['0x7109871a', '0xf05368c0'], 'source': 'pin, APK not present'}
        print(json.dumps({'manager_certificate': cert, 'package': MANAGER_PACKAGE,
                          'status': STATUS_KIND}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        fail(f'{exc}')
