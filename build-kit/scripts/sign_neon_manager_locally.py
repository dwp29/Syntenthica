#!/usr/bin/env python3
"""Interactively sign an unsigned Neon Manager with the *original* local key.

No password is accepted on the command line or written to this repository.
The tool rejects any signer whose public certificate does not match the kernel's
pinned Manager identity. This cannot recreate a lost private signing key.
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

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CERT = 'fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140'


def command_output(command: list[str]) -> str:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=None, check=True).stdout


def keytool_certificate(text: str) -> str:
    matches = re.findall(r'^\s*SHA256:\s*([0-9A-Fa-f:]+)\s*$', text, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('Could not uniquely read the keystore alias certificate SHA-256')
    return matches[0].replace(':', '').lower()


def apksigner_certificate(text: str) -> str:
    matches = re.findall(r'^Signer #\d+ certificate SHA-256 digest:\s*([0-9A-Fa-f]+)\s*$', text, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('Expected exactly one APK signer and one certificate digest')
    return matches[0].lower()


def require_expected_cert(cert: str) -> None:
    if cert != EXPECTED_CERT:
        raise ValueError('The certificate does not match the original trusted Manager key; no APK will be produced')


def validate_package(aapt: Path, apk: Path) -> None:
    badging = command_output([str(aapt), 'dump', 'badging', str(apk)])
    first = badging.splitlines()[0] if badging else ''
    for token in ("name='net.ember.labs'", "versionCode='40000'", "versionName='3.0.0'"):
        if token not in first:
            raise ValueError(f'Not the intended Neon Manager APK: {token} missing')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True, help='verified unsigned Manager APK')
    parser.add_argument('--expected-sha256', required=True, help='independently obtained SHA-256 of that unsigned APK')
    parser.add_argument('--keystore', type=Path, required=True, help='original local private keystore (never copied)')
    parser.add_argument('--alias', required=True, help='original signing key alias')
    parser.add_argument('--out', type=Path, required=True, help='new signed APK path; must not exist')
    parser.add_argument('--build-tools', type=Path, required=True, help='Android SDK build-tools directory')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise ValueError('Run in an interactive terminal so passwords never appear in shell arguments or logs')
    apk, keystore, output = args.apk.resolve(), args.keystore.resolve(), args.out.resolve()
    if not apk.is_file() or not keystore.is_file() or not output.parent.is_dir():
        raise ValueError('Input APK, keystore or output directory is missing')
    if output.exists() or output in (apk, keystore):
        raise ValueError('Output must be a new file and must not overwrite the APK or keystore')
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
    subprocess.run([sys.executable, str(ROOT / 'tests/verify_synthetica30_apk.py'), str(apk)], check=True)
    unsigned = subprocess.run([str(apksigner), 'verify', str(apk)], capture_output=True, text=True)
    if unsigned.returncode == 0 or 'DOES NOT VERIFY' not in unsigned.stdout + unsigned.stderr:
        raise ValueError('Input is not the expected unsigned APK')

    print('Verify the original local certificate. keytool will prompt for the keystore password.', flush=True)
    keytool_text = command_output([keytool, '-J-Duser.language=en', '-J-Duser.country=US', '-list', '-v',
                                   '-keystore', str(keystore), '-alias', args.alias])
    require_expected_cert(keytool_certificate(keytool_text))

    with tempfile.TemporaryDirectory(prefix='.synthetica-sign-', dir=output.parent) as tmp:
        signed = Path(tmp) / 'signed.apk'
        print('Certificate matches. apksigner will now prompt for the passwords locally.', flush=True)
        subprocess.run([str(apksigner), 'sign', '--ks', str(keystore), '--ks-key-alias', args.alias,
                        '--out', str(signed), str(apk)], check=True)
        signature = command_output([str(apksigner), 'verify', '--verbose', '--print-certs', str(signed)])
        require_expected_cert(apksigner_certificate(signature))
        validate_package(aapt, signed)
        subprocess.run([str(zipalign), '-c', '-p', '4', str(signed)], check=True)
        # O_EXCL prevents overwriting a file created by another process after validation.
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, 'wb') as dst, signed.open('rb') as src:
                shutil.copyfileobj(src, dst)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    print('Signed Manager APK:', output)
    print('SHA-256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print('Certificate matches the pinned kernel identity; Android install and runtime remain untested.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Signing refused: {exc}', file=sys.stderr)
        sys.exit(1)
