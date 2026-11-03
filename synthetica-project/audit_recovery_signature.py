#!/usr/bin/env python3
"""Read-only SHA-256 whole-file signature check against an explicit public key.

Models the ZIP footer/signed-byte range in the cited AOSP recovery verifier and
checks the extracted direct PKCS#7 signature with the host OpenSSL. Both the
package SHA-256 and public-key SPKI SHA-256 must be supplied as independent pins.
The certificate is a REFERENCE, not evidence that a recovery actually trusts it.
This is not the target OrangeFox verifier, ZIP/OTA metadata validation, AVB,
rollback, VINTF, device or boot verification. Never reads a private key, signs,
changes a package, contacts a device, or approves flashing.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from asn1crypto import cms, pem, x509
except ImportError:
    cms = pem = x509 = None

MAX_PACKAGE = 32 * 1024**3
MAX_CERTIFICATE = 64 * 1024
MAX_FOOTER = 0xffff
CHUNK = 4 * 1024 * 1024
EOCD = b'PK\x05\x06'
PIN = re.compile(r'[0-9a-f]{64}\Z')


class RecoverySignatureError(Exception):
    pass


def _pin(value: str, label: str) -> str:
    if not isinstance(value, str) or not PIN.fullmatch(value):
        raise RecoverySignatureError(f'{label} must be a lowercase SHA-256')
    return value


def _snapshot(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _open_regular(path: Path, limit: int):
    # O_NONBLOCK prevents a FIFO or other special path from hanging before fstat.
    flags = (os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
             | getattr(os, 'O_NONBLOCK', 0))
    if not hasattr(os, 'O_NOFOLLOW'):
        raise RecoverySignatureError('Host cannot refuse symlink input safely')
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise RecoverySignatureError('Input is missing, unreadable, or a symlink') from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise RecoverySignatureError('Input is not a bounded, nonempty regular file')
        return os.fdopen(fd, 'rb'), info
    except BaseException:
        os.close(fd)
        raise


def _read_at(stream, pos: int, length: int) -> bytes:
    stream.seek(pos)
    data = stream.read(length)
    if len(data) != length:
        raise RecoverySignatureError('Short input read')
    return data


def _footer(stream, length: int) -> tuple[int, bytes, dict]:
    """Locate the AOSP-style signature without trusting zipfile's search order."""
    if length < 28:
        raise RecoverySignatureError('Package is too small for a recovery footer')
    footer = _read_at(stream, length - 6, 6)
    if footer[2:4] != b'\xff\xff':
        raise RecoverySignatureError('Recovery whole-file signature footer is absent')
    signature_start, comment_size = struct.unpack_from('<HH', footer[0:2] + footer[4:6])
    if not (6 < signature_start <= comment_size <= MAX_FOOTER):
        raise RecoverySignatureError('Invalid recovery signature/comment lengths')
    eocd_size = 22 + comment_size
    if eocd_size > length:
        raise RecoverySignatureError('Recovery EOCD extends before the package')
    eocd = _read_at(stream, length - eocd_size, eocd_size)
    if eocd[:4] != EOCD or struct.unpack_from('<H', eocd, 20)[0] != comment_size:
        raise RecoverySignatureError('Recovery signature does not match the ZIP EOCD')
    if EOCD in eocd[4:]:
        raise RecoverySignatureError('Ambiguous extra ZIP EOCD marker in recovery comment')
    signature = eocd[-signature_start:-6]
    signed_bytes = length - comment_size - 2
    if not signature or signed_bytes <= 0:
        raise RecoverySignatureError('Empty recovery signature or signed range')
    return signed_bytes, signature, {'zip_comment_bytes': comment_size,
                                     'signature_block_bytes': len(signature),
                                     'signed_bytes': signed_bytes}


def _direct_signature(der: bytes) -> tuple[bytes, str]:
    if cms is None:
        raise RecoverySignatureError('Pinned asn1crypto parser is unavailable')
    try:
        info = cms.ContentInfo.load(der, strict=True)
        if info['content_type'].native != 'signed_data':
            raise RecoverySignatureError('Recovery signature is not PKCS#7 SignedData')
        signed = info['content']
        if signed['encap_content_info']['content_type'].native != 'data':
            raise RecoverySignatureError('Unsupported PKCS#7 content type')
        if signed['encap_content_info']['content'].native is not None:
            raise RecoverySignatureError('Recovery signature must have detached content')
        digests = signed['digest_algorithms']
        if len(digests) != 1 or digests[0]['algorithm'].native != 'sha256':
            raise RecoverySignatureError('Only a single SHA-256 digest is supported')
        signers = signed['signer_infos']
        if len(signers) != 1:
            raise RecoverySignatureError('Only one direct PKCS#7 signer is supported')
        signer = signers[0]
        if signer['digest_algorithm']['algorithm'].native != 'sha256':
            raise RecoverySignatureError('Signer digest is not SHA-256')
        if signer['signed_attrs'].native is not None:
            raise RecoverySignatureError('Signed attributes are not a direct recovery signature')
        signature = signer['signature'].native
        algorithm = signer['signature_algorithm']['algorithm'].native
        if not isinstance(signature, bytes) or not 8 <= len(signature) <= 8192:
            raise RecoverySignatureError('Invalid signature byte length')
        return signature, algorithm
    except (ValueError, TypeError, IndexError, KeyError, OverflowError) as exc:
        raise RecoverySignatureError('Malformed or unsupported PKCS#7 signature') from exc


def _certificate(path: Path) -> tuple[bytes, bytes, str, int]:
    with _open_regular(path, MAX_CERTIFICATE)[0] as stream:
        before = _snapshot(os.fstat(stream.fileno()))
        data = stream.read(MAX_CERTIFICATE + 1)
        if len(data) > MAX_CERTIFICATE or _snapshot(os.fstat(stream.fileno())) != before:
            raise RecoverySignatureError('Reference certificate changed or exceeded its limit')
    return _certificate_data(data)


def _certificate_data(data: bytes) -> tuple[bytes, bytes, str, int]:
    """Parse exactly one bounded public certificate, from DER or PEM bytes."""
    if x509 is None:
        raise RecoverySignatureError('Pinned asn1crypto parser is unavailable')
    if not 0 < len(data) <= MAX_CERTIFICATE:
        raise RecoverySignatureError('Reference certificate is empty or exceeds its limit')
    try:
        stripped = data.strip()
        if pem.detect(stripped):
            if not (stripped.startswith(b'-----BEGIN CERTIFICATE-----') and
                    stripped.endswith(b'-----END CERTIFICATE-----')):
                raise RecoverySignatureError('Reference must contain exactly one PEM certificate')
            entries = list(pem.unarmor(stripped, multiple=True))
            if len(entries) != 1 or entries[0][0] != 'CERTIFICATE':
                raise RecoverySignatureError('Reference must contain exactly one PEM certificate')
            der = entries[0][2]
        else:
            der = data
        cert = x509.Certificate.load(der, strict=True)
        spki = cert['tbs_certificate']['subject_public_key_info']
        algo, bits = spki['algorithm']['algorithm'].native, spki.bit_size
        cert_sig = cert['signature_algorithm']['algorithm'].native
        if algo == 'rsa':
            exponent = spki['public_key'].parsed['public_exponent'].native
            if bits not in (2048, 4096) or exponent not in (3, 65537):
                raise RecoverySignatureError('RSA public key is outside the reference recovery limits')
            if cert_sig != 'sha256_rsa':
                raise RecoverySignatureError('RSA reference certificate must identify SHA-256')
        elif algo == 'ec':
            curve = spki['algorithm']['parameters'].native
            if curve != 'secp256r1' or cert_sig != 'sha256_ecdsa':
                raise RecoverySignatureError('Only P-256 EC certificates identifying SHA-256 are supported')
        else:
            raise RecoverySignatureError('Only RSA and P-256 EC reference keys are supported')
        return der, spki.dump(), algo, bits
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        raise RecoverySignatureError('Malformed or unsupported reference certificate') from exc


def _hash_package(stream, length: int, signed_bytes: int) -> tuple[str, bytes]:
    stream.seek(0)
    whole, signed = hashlib.sha256(), hashlib.sha256()
    remaining, left = length, signed_bytes
    while remaining:
        data = stream.read(min(CHUNK, remaining))
        if not data:
            raise RecoverySignatureError('Package changed or ended during hashing')
        whole.update(data)
        count = min(left, len(data))
        if count:
            signed.update(data[:count])
            left -= count
        remaining -= len(data)
    if left:
        raise RecoverySignatureError('Incomplete signed-byte range')
    return whole.hexdigest(), signed.digest()


def _verify_with_openssl(spki: bytes, sig: bytes, digest: bytes, key_type: str) -> str:
    executable = shutil.which('openssl')
    if not executable:
        raise RecoverySignatureError('Host OpenSSL is unavailable')
    with tempfile.TemporaryDirectory(prefix='recovery-signature-public-') as tmp:
        root = Path(tmp)
        key, signature, hashed = root / 'public.der', root / 'signature.bin', root / 'digest.bin'
        key.write_bytes(spki)
        signature.write_bytes(sig)
        hashed.write_bytes(digest)
        args = [executable, 'pkeyutl', '-verify', '-pubin', '-keyform', 'DER', '-inkey', str(key),
                '-in', str(hashed), '-sigfile', str(signature), '-pkeyopt', 'digest:sha256']
        if key_type == 'rsa':
            args.extend(['-pkeyopt', 'rsa_padding_mode:pkcs1'])
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RecoverySignatureError('Host OpenSSL failed or timed out') from exc
        if result.returncode != 0:
            raise RecoverySignatureError('Recovery signature does not match the specified public key')
    return 'openssl_pkeyutl_sha256_prehashed'


def audit(package: Path, reference_cert: Path, expected_archive_sha256: str,
          expected_public_key_sha256: str) -> dict:
    _pin(expected_archive_sha256, 'Expected archive digest')
    _pin(expected_public_key_sha256, 'Expected public-key digest')
    cert_der, spki, key_type, key_bits = _certificate(reference_cert)
    key_sha = hashlib.sha256(spki).hexdigest()
    if not hmac.compare_digest(key_sha, expected_public_key_sha256):
        raise RecoverySignatureError('Reference certificate public key does not match its independent pin')
    with _open_regular(package, MAX_PACKAGE)[0] as stream:
        before = _snapshot(os.fstat(stream.fileno()))
        length = before[3]
        signed_bytes, container, footer = _footer(stream, length)
        signature, sig_algo = _direct_signature(container)
        allowed = {'rsa': {'rsassa_pkcs1v15', 'sha256_rsa'}, 'ec': {'sha256_ecdsa'}}
        if sig_algo not in allowed[key_type]:
            raise RecoverySignatureError('PKCS#7 signature algorithm does not match the reference key')
        archive_sha, signed_digest = _hash_package(stream, length, signed_bytes)
        if not hmac.compare_digest(archive_sha, expected_archive_sha256):
            raise RecoverySignatureError('Package SHA-256 does not match its independent pin')
        verifier = _verify_with_openssl(spki, signature, signed_digest, key_type)
        if _snapshot(os.fstat(stream.fileno())) != before:
            raise RecoverySignatureError('Package changed during the signature audit')
    return {'schema': 'synthetica-recovery-signature-audit-v1',
            'status': 'signature_matches_explicit_reference_key_only_not_flash_approval',
            'package_bytes': length, 'package_sha256': archive_sha,
            'signed_range_sha256': signed_digest.hex(), **footer,
            'reference_certificate_der_sha256': hashlib.sha256(cert_der).hexdigest(),
            'reference_public_key_spki_sha256': key_sha,
            'public_key_type': key_type, 'public_key_bits': key_bits,
            'pkcs7_signature_algorithm': sig_algo, 'verifier': verifier,
            'signature_matches_reference_public_key': True,
            'recovery_certificate_trust_or_settings_verified': False,
            'target_recovery_implementation_executed': False,
            'zip_members_or_ota_offsets_validated': False,
            'device_avb_rollback_or_boot_verified': False,
            'limitations': [
                'The supplied certificate/key pin must be established independently; an embedded package certificate is not a trust anchor.',
                'This bounded host implementation is not the installed recovery verifier or a complete ZIP/OTA/AVB validator.',
                'Only SHA-256 direct PKCS#7 signatures with one RSA or P-256 signer are supported; others are refused, not declared invalid.',
                'A valid signature says nothing about compatibility, AVB trust, rollback, decryption, device boot or permission to flash.',
                'No private key, candidate modification, signing operation, device access or security-setting change was performed.',
            ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--reference-certificate', type=Path, required=True,
                        help='Public X.509 certificate; its trust by recovery is not assumed')
    parser.add_argument('--expected-archive-sha256', required=True)
    parser.add_argument('--expected-public-key-sha256', required=True,
                        help='SHA-256 of DER SubjectPublicKeyInfo, obtained independently')
    args = parser.parse_args()
    try:
        result = audit(args.package, args.reference_certificate, args.expected_archive_sha256,
                       args.expected_public_key_sha256)
    except (RecoverySignatureError, OSError) as exc:
        print(f'Recovery signature audit refused: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
