#!/usr/bin/env python3
"""Interactively sign a verified 4.0 Manager using the original private key.

The keystore must remain outside the checkout. No password is accepted on the
command line or sent to CI. Only the kernel-pinned public certificate is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
from sign_neon_manager_locally import apksigner_certificate, command_output, keytool_certificate

EXPECTED_CERT = 'fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140'


def require_expected_cert(cert: str) -> None:
    if cert != EXPECTED_CERT:
        raise ValueError('The certificate does not match the original trusted Manager key; no APK will be produced')


def validate_package(aapt: Path, apk: Path) -> None:
    badging = command_output([str(aapt), 'dump', 'badging', str(apk)])
    first = badging.splitlines()[0] if badging else ''
    for token in ("name='net.ember.labs'", "versionCode='50000'", "versionName='4.0.0'"):
        if token not in first:
            raise ValueError(f'Not the intended 4.0 Manager APK: {token} missing')


def payload_digests(apk: Path) -> dict[str, str]:
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('APK has duplicate ZIP entries')
        if z.testzip() is not None:
            raise ValueError('APK has a corrupted ZIP entry')
        def signature_file(name: str) -> bool:
            upper = name.upper()
            return upper == 'META-INF/MANIFEST.MF' or bool(re.fullmatch(r'META-INF/[^/]+\.(SF|RSA|DSA|EC)', upper))
        return {name: hashlib.sha256(z.read(name)).hexdigest() for name in names if not signature_file(name)}


def validate_schemes(text: str) -> None:
    for scheme in ('v2', 'v3'):
        if not re.search(rf'Verified using {scheme} scheme[^\n]*:\s*true\s*$', text, re.MULTILINE | re.IGNORECASE):
            raise ValueError(f'APK signature {scheme} was not verified')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True, help='verified unsigned Manager APK')
    parser.add_argument('--expected-sha256', required=True, help='independently obtained unsigned APK SHA-256')
    parser.add_argument('--keystore', type=Path, required=True, help='original private keystore outside this checkout')
    parser.add_argument('--alias', required=True, help='alias of the original Manager signing key')
    parser.add_argument('--out', type=Path, required=True, help='new signed APK path; must not exist')
    parser.add_argument('--build-tools', type=Path, required=True, help='Android SDK build-tools directory')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise ValueError('Run in an interactive terminal so passwords do not appear in arguments or logs')
    apk, keystore, output = args.apk.resolve(), args.keystore.resolve(), args.out.resolve()
    if not apk.is_file() or not keystore.is_file() or not output.parent.is_dir():
        raise ValueError('Input APK, keystore or output directory is missing')
    if keystore == ROOT or ROOT in keystore.parents:
        raise ValueError('The private keystore must not be placed inside the repository')
    if output.exists() or output in (apk, keystore):
        raise ValueError('Output must be a new file and must not overwrite an input')
    expected_hash = args.expected_sha256.lower()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_hash) or hashlib.sha256(apk.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Unsigned APK SHA-256 does not match the independently supplied value')
    keytool = shutil.which('keytool')
    apksigner = args.build_tools / 'apksigner'
    zipalign = args.build_tools / 'zipalign'
    aapt = args.build_tools / 'aapt'
    if not keytool or any(not p.is_file() or not os.access(p, os.X_OK) for p in (apksigner, zipalign, aapt)):
        raise ValueError('keytool and Android SDK apksigner, zipalign and aapt are required')

    validate_package(aapt, apk)
    subprocess.run([str(zipalign), '-c', '-p', '4', str(apk)], check=True)
    subprocess.run([str(zipalign), '-c', '-P', '16', '4', str(apk)], check=True)
    subprocess.run([sys.executable, str(ROOT / 'tests/verify_synthetica40_apk.py'), str(apk)], check=True)
    unsigned = subprocess.run([str(apksigner), 'verify', str(apk)], capture_output=True, text=True)
    if unsigned.returncode == 0 or 'DOES NOT VERIFY' not in unsigned.stdout + unsigned.stderr:
        raise ValueError('Input is not the expected unsigned APK')
    original_payload = payload_digests(apk)

    print('Verify the original local certificate. keytool will prompt for the keystore password.', flush=True)
    keytool_text = command_output([keytool, '-J-Duser.language=en', '-J-Duser.country=US', '-list', '-v',
                                   '-keystore', str(keystore), '-alias', args.alias])
    require_expected_cert(keytool_certificate(keytool_text))
    with tempfile.TemporaryDirectory(prefix='.synthetica-sign40-', dir=output.parent) as tmp:
        signed = Path(tmp) / 'signed.apk'
        print('Certificate matches. apksigner will prompt for the passwords locally.', flush=True)
        subprocess.run([str(apksigner), 'sign', '--ks', str(keystore), '--ks-key-alias', args.alias,
                        '--out', str(signed), str(apk)], check=True)
        signature = command_output([str(apksigner), 'verify', '--verbose', '--print-certs', str(signed)])
        require_expected_cert(apksigner_certificate(signature))
        validate_schemes(signature)
        validate_package(aapt, signed)
        subprocess.run([str(zipalign), '-c', '-p', '4', str(signed)], check=True)
        subprocess.run([str(zipalign), '-c', '-P', '16', '4', str(signed)], check=True)
        if payload_digests(signed) != original_payload:
            raise ValueError('Signing changed the non-signature APK payload')
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, 'wb') as dst, signed.open('rb') as src:
                shutil.copyfileobj(src, dst)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    print('Signed Manager APK:', output)
    print('SHA-256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print('Pinned certificate, v2/v3 signatures, alignment and unchanged payload verified.')
    print('Android update, device runtime and root behavior are not verified by signing.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Signing refused: {exc}', file=sys.stderr)
        sys.exit(1)
