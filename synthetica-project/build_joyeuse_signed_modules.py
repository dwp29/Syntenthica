#!/usr/bin/env python3
"""Build the missing Joyeuse network modules with their kernel, not around its checks.

This extends the existing isolated Synthetica build: RMNET_SHS, RMNET_PERF and
MSM_11AD_PROXY are compiled and signed in the SAME build as the kernel. The
original builder and ROM are untouched. Output is not an installer, is not a
ROM, and is not approved for flashing. Other vendor module ABI/signatures,
AVB, actual device behavior and the original RAM disk remain unresolved.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('joyeuse_builtin_build', HERE / 'build_joyeuse_builtin_experiment.py')
if spec is None or spec.loader is None:
    raise RuntimeError('Cannot load existing kernel build helper')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

MODULES = ('rmnet_perf', 'rmnet_shs', 'msm_11ad_proxy')
CONFIG = {'RMNET_PERF': 'm', 'RMNET_SHS': 'm', 'MSM_11AD': 'm'}
SIG_MAGIC = b'~Module signature appended~\n'
MAX_MODULE = 32 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare(source: Path, destination: Path, fragment: Path) -> None:
    base.prepare(source, destination, fragment)
    profile = destination / 'ci/rollercoaster/profiles/synthetica.config'
    profile.write_text(profile.read_text() + '\n# Build the ROM-requested 11ad proxy with this kernel.\nCONFIG_MSM_11AD=m\n')
    builder = destination / 'ci/rollercoaster/build-rollercoaster.sh'
    text = builder.read_text()
    anchor = 'python3 "$SP_EXPERIMENT_GUARD" check-config --baseline "$SP_EXPERIMENT_BASELINE_CONFIG" --generated "$OUT/.config"\n'
    if text.count(anchor) != 1:
        raise ValueError('kernel config guard anchor differs')
    guards = ''.join(f"grep -qx 'CONFIG_{name}={value}' \"$OUT/.config\" || {{ echo 'Missing required module {name}'; exit 1; }}\n"
                     for name, value in CONFIG.items())
    text = text.replace(anchor, anchor + guards)
    image_build = 'make -j"$JOBS" "${MO[@]}" Image.gz\n'
    if text.count(image_build) != 1:
        raise ValueError('kernel Image.gz build anchor differs')
    # modules_install uses CONFIG_MODULE_SIG_ALL and the private key generated
    # for this same build. It remains in the disposable out directory only.
    module_build = '''echo "--- Build and sign matching Joyeuse network modules ---"
make -j"$JOBS" "${MO[@]}" modules
make "${MO[@]}" INSTALL_MOD_PATH="$OUT/joyeuse-modules" modules_install
'''
    text = text.replace(image_build, image_build + module_build)
    builder.write_text(text)
    print('Prepared one isolated kernel-and-matching-modules build; no security check disabled.')


def split_signature(data: bytes) -> tuple[bytes, bytes]:
    if len(data) > MAX_MODULE or not data.endswith(SIG_MAGIC):
        raise ValueError('missing or oversized module signature')
    trailer_end = len(data) - len(SIG_MAGIC)
    if trailer_end <= 12:
        raise ValueError('truncated module signature trailer')
    algo, digest, id_type, signer_len, key_len, p0, p1, p2, sig_len = struct.unpack_from('>8BI', data, trailer_end - 12)
    if (algo, digest, id_type, signer_len, key_len, p0, p1, p2) != (0, 0, 2, 0, 0, 0, 0, 0):
        raise ValueError('unsupported module signature trailer')
    start = trailer_end - 12 - sig_len
    if sig_len < 128 or start <= 0:
        raise ValueError('invalid module signature length')
    return data[:start], data[start:trailer_end - 12]


def elf_sections(payload: bytes) -> dict[str, bytes]:
    if len(payload) < 64:
        raise ValueError('truncated ELF')
    h = struct.unpack_from('<16sHHIQQQIHHHHHH', payload, 0)
    ident, kind, machine, version = h[:4]
    shoff, ehsize, shentsize, shnum, shstrndx = h[6], h[8], h[11], h[12], h[13]
    if (ident[:7] != b'\x7fELF\x02\x01\x01' or kind != 1 or machine != 183 or version != 1
            or ehsize != 64 or shentsize != 64 or not 0 < shnum <= 4096 or shstrndx >= shnum
            or shoff < 64 or shoff + shentsize * shnum > len(payload)):
        raise ValueError('module must be bounded AArch64 little-endian ELF64 ET_REL')
    rows = [struct.unpack_from('<IIQQQQIIQQ', payload, shoff + 64 * i) for i in range(shnum)]
    names_row = rows[shstrndx]
    names = payload[names_row[4]:names_row[4] + names_row[5]]
    if names_row[4] + names_row[5] > len(payload) or names_row[1] != 3:
        raise ValueError('invalid ELF section string table')
    sections = {}
    for row in rows:
        name_offset, section_type, _, _, offset, size, _, _, _, _ = row
        if name_offset >= len(names):
            raise ValueError('bad ELF section name offset')
        stop = names.find(b'\0', name_offset)
        if stop < 0:
            raise ValueError('unterminated ELF section name')
        try:
            name = names[name_offset:stop].decode('ascii')
        except UnicodeError as exc:
            raise ValueError('non-ASCII ELF section name') from exc
        if section_type != 8 and offset + size > len(payload):
            raise ValueError('ELF section out of bounds')
        if name in ('.modinfo', '__versions'):
            if name in sections:
                raise ValueError('duplicate required ELF section')
            sections[name] = payload[offset:offset + size]
    if set(sections) != {'.modinfo', '__versions'}:
        raise ValueError('module lacks modinfo or MODVERSIONS')
    return sections


def module_info(section: bytes) -> dict[str, str]:
    if not section or not section.endswith(b'\0'):
        raise ValueError('invalid modinfo')
    entries = {}
    for row in section.split(b'\0'):
        if not row:
            continue
        try:
            text = row.decode('ascii')
        except UnicodeError as exc:
            raise ValueError('non-ASCII modinfo') from exc
        name, sep, value = text.partition('=')
        if sep and name in ('vermagic', 'name', 'depends'):
            if name in entries:
                raise ValueError('duplicate important modinfo field')
            entries[name] = value
    if 'name' not in entries or 'vermagic' not in entries:
        raise ValueError('module name or vermagic missing')
    return entries


def version_records(data: bytes) -> dict[str, int]:
    # Linux 4.14 modversion_info is an unsigned long CRC + 56-byte name on arm64.
    if not data or len(data) % 64 or len(data) > 1024 * 1024:
        raise ValueError('invalid MODVERSIONS records')
    rows = {}
    for offset in range(0, len(data), 64):
        crc = struct.unpack_from('<Q', data, offset)[0]
        raw = data[offset + 8:offset + 64]
        name, sep, tail = raw.partition(b'\0')
        if not sep or any(tail) or not name or crc > 0xffffffff:
            raise ValueError('invalid MODVERSIONS record')
        try:
            name_text = name.decode('ascii')
        except UnicodeError as exc:
            raise ValueError('non-ASCII version symbol') from exc
        if name_text in rows:
            raise ValueError('duplicate MODVERSIONS symbol')
        rows[name_text] = crc
    if 'module_layout' not in rows:
        raise ValueError('module_layout version is missing')
    return rows


def symvers_records(text: str) -> dict[str, int]:
    rows = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3 or not fields[0].startswith('0x'):
            raise ValueError('invalid Module.symvers')
        try:
            crc = int(fields[0], 16)
        except ValueError as exc:
            raise ValueError('invalid symvers CRC') from exc
        if not 0 <= crc <= 0xffffffff:
            raise ValueError('symvers CRC out of range')
        name = fields[1]
        if name in rows and rows[name] != crc:
            raise ValueError('conflicting symvers entries')
        rows[name] = crc
    if 'module_layout' not in rows:
        raise ValueError('kernel module_layout symvers missing')
    return rows


def verify_pkcs7(payload: bytes, signature: bytes, certificate_der: bytes) -> None:
    # Mathematical verification against this exact certificate. This is not a
    # claim that the target device actually booted or trusted the keyring.
    with tempfile.TemporaryDirectory(prefix='joyeuse-module-verify-') as temp:
        folder = Path(temp)
        for name, data in (('module', payload), ('signature.der', signature), ('cert.der', certificate_der)):
            (folder / name).write_bytes(data)
        cert_pem = folder / 'cert.pem'
        commands = [
            ['openssl', 'x509', '-inform', 'DER', '-in', str(folder / 'cert.der'), '-out', str(cert_pem)],
            ['openssl', 'cms', '-verify', '-binary', '-inform', 'DER', '-in', str(folder / 'signature.der'),
             '-content', str(folder / 'module'), '-certfile', str(cert_pem), '-noverify', '-out', os.devnull],
        ]
        for command in commands:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode:
                raise ValueError('module signature does not verify with the kernel certificate')


def verify_module(data: bytes, *, name: str, release: str, certificate_der: bytes,
                  raw_kernel: bytes, symvers: dict[str, int]) -> dict:
    if not certificate_der or raw_kernel.count(certificate_der) != 1:
        raise ValueError('kernel does not contain exactly one matching module-signing certificate')
    payload, signature = split_signature(data)
    sections = elf_sections(payload)
    info = module_info(sections['.modinfo'])
    if info['name'] != name or info['vermagic'].split(' ', 1)[0] != release:
        raise ValueError('module name or kernel release differs')
    dependencies = [value for value in info.get('depends', '').split(',') if value]
    if any(dep not in MODULES for dep in dependencies):
        raise ValueError('module depends on an unbundled loadable module')
    versions = version_records(sections['__versions'])
    for symbol, crc in versions.items():
        if symvers.get(symbol) != crc:
            raise ValueError(f'module MODVERSIONS mismatch or missing export: {symbol}')
    verify_pkcs7(payload, signature, certificate_der)
    return {'name': name, 'bytes': len(data), 'sha256': sha(data), 'vermagic': info['vermagic'],
            'version_records_verified': len(versions), 'dependencies': dependencies,
            'signature_math_verified_with_embedded_certificate': True}


def finish(kit: Path, out: Path, baseline: Path, result: Path) -> None:
    config = base.read_config((out / '.config').read_text())
    for name, value in CONFIG.items():
        if config.get(name) != value:
            raise ValueError(f'required module configuration is missing: {name}')
    raw_kernel = gzip.decompress((kit / 'artifacts/Image.gz').read_bytes())
    certificate = (out / 'certs/signing_key.x509').read_bytes()
    symvers = symvers_records((out / 'Module.symvers').read_text())
    stage = out / 'joyeuse-modules/lib/modules' / base.EXPECTED_RELEASE / 'kernel'
    modules = {}
    for name in MODULES:
        matches = list(stage.rglob(name + '.ko'))
        if len(matches) != 1 or matches[0].is_symlink() or not matches[0].is_file():
            raise ValueError(f'expected exactly one signed {name}.ko')
        data = matches[0].read_bytes()
        modules[name] = (data, verify_module(data, name=name, release=base.EXPECTED_RELEASE,
                                             certificate_der=certificate, raw_kernel=raw_kernel, symvers=symvers))
    if result.exists() or result.is_symlink() or not result.parent.is_dir():
        raise ValueError('result must be a new directory')
    with tempfile.TemporaryDirectory(prefix='.joyeuse-result-', dir=result.parent) as tmp:
        staged_result = Path(tmp) / 'result'
        base.finish(kit, out, baseline, staged_result)
        module_dir = staged_result / 'signed-modules'
        module_dir.mkdir()
        for name, (data, _) in modules.items():
            (module_dir / (name + '.ko')).write_bytes(data)
        (staged_result / 'kernel-module-public-cert.der').write_bytes(certificate)
        status_path = staged_result / 'STATUS.json'
        status = json.loads(status_path.read_text())
        status['matching_network_modules'] = {
            'certificate_sha256': sha(certificate), 'kernel_contains_exact_certificate': True,
            'signatures_and_modversion_records_checked': True,
            'modules': [value[1] for value in modules.values()],
            'runtime_keyring_and_device_load': 'NOT_TESTED',
            'rom_integration': 'NOT_DONE',
        }
        status['vendor_module_compatibility'] = 'NOT_PROVEN except static checks on the three newly built network modules'
        status_path.write_text(json.dumps(status, indent=2) + '\n')
        (staged_result / 'README-DO-NOT-FLASH.txt').write_text(
            'DO NOT FLASH. Kernel and three source-built signed modules only; not a ROM or installer.\n'
            'RMNET_PERF, RMNET_SHS and MSM_11AD_PROXY are compiled with the same kernel and key.\n'
            'Signatures and recorded CRCs match statically; runtime load is NOT tested.\n'
            'Other vendor modules, AVB, original RAM disk and device boot remain unresolved.\n'
            'Module signature enforcement and MODVERSIONS remain enabled; private key not exported.\n')
        if any('signing_key.pem' in path.name for path in staged_result.rglob('*')):
            raise ValueError('private signing key must never be exported')
        os.rename(staged_result, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--fragment', type=Path, required=True)
    f = commands.add_parser('finish')
    f.add_argument('--kit', type=Path, required=True)
    f.add_argument('--out', type=Path, required=True)
    f.add_argument('--baseline', type=Path, required=True)
    f.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.destination, args.fragment)
    else:
        finish(args.kit, args.out, args.baseline, args.result)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, UnicodeError, struct.error, subprocess.SubprocessError) as exc:
        print('Kernel/module build withheld: ' + str(exc), file=sys.stderr)
        sys.exit(1)
