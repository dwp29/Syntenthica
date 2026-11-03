"""Parse bounded Android apksigner signer output without treating it as trust.

The SDK has printed both numbered legacy signers and newer V3.0/V3.1 labels.
Source-stamp certificates and unrecognized labels are intentionally excluded.
Callers must check the verifier exit status and decide whether an ambiguous or
rotated multi-certificate result is acceptable. This parser never asserts that
a certificate belongs to an author or is trusted by an Android device.
"""
from __future__ import annotations
import re

MAX_OUTPUT=4*1024*1024
# SHA-256 of DER public certificate in AOSP platform_build testkey.x509.pem
# at commit 3d9c9aacdb6ca0b745b3048dad88d0db4680d50e. It is a public dev key,
# never a production or publisher-trust anchor. Other public keys are not checked.
AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256='a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc'
SIGNER=(r'(?:Signer(?: #[0-9]+)?|V(?:1|2|3(?:\.[012])?|4) Signer(?: #[0-9]+)?)')
SDK_RANGE=(r'(?: \(minSdkVersion=[0-9]+(?: \(dev release=true\))?, maxSdkVersion=[0-9]+\))?')
CERT_LINE=re.compile(r'^'+SIGNER+r':?'+SDK_RANGE+r' certificate SHA-256 digest: ([0-9a-fA-F]{64})$',re.M)
SCHEME_LINE=re.compile(r'^Verified using v(1|2|3(?:\.[012])?|4) scheme .*: (true|false)$',re.M)

class SignerOutputError(ValueError):pass


def parse_certificates(text: str) -> list[str]:
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_OUTPUT:
        raise SignerOutputError('Apksigner output exceeds bounds')
    return sorted({x.lower() for x in CERT_LINE.findall(text)})


def matches_aosp_public_testkey(certificate_sha256: str | None) -> bool | None:
    """Check one known public development cert; None means unavailable."""
    if certificate_sha256 is None:return None
    if not isinstance(certificate_sha256,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',certificate_sha256):
        raise SignerOutputError('Invalid signer certificate SHA-256')
    return certificate_sha256.lower()==AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256


def unparsed_signer_certificate_lines(text: str) -> list[str]:
    """Report unknown signer digest labels even when another label parsed.

    Source-stamp digests are not APK signers. An otherwise unrecognized SHA-256
    certificate line is ambiguous and must prevent callers from asserting a
    single, unambiguous signer. Returned diagnostics are bounded.
    """
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_OUTPUT:
        raise SignerOutputError('Apksigner output exceeds bounds')
    result=[]
    for line in text.splitlines():
        if 'certificate SHA-256 digest:' not in line or line.startswith('Source Stamp '):
            continue
        if not CERT_LINE.fullmatch(line):
            result.append(line[:500])
            if len(result)>=8:break
    return result


def parse_schemes(text: str) -> dict[str,bool]:
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_OUTPUT:
        raise SignerOutputError('Apksigner output exceeds bounds')
    found={}
    for scheme,value in SCHEME_LINE.findall(text):
        if scheme in found:raise SignerOutputError('Duplicate signature scheme result')
        found[scheme]=value=='true'
    return found
