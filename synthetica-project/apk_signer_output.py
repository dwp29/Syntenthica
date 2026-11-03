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
# Curated public development certificates from that source tree. This is not
# an exhaustive list: absence is NOT evidence that a certificate is trusted.
AOSP_PUBLIC_DEVELOPMENT_CERTIFICATES={
    AOSP_PUBLIC_TESTKEY_CERTIFICATE_SHA256:'testkey',
    'c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8':'platform',
    '28bbfe4a7b97e74681dc55c2fbb6ccb8d6c74963733f6af6ae74d8c3a6e879fd':'shared',
    '465983f7791f2abeb43ea2cbdc7f21a8260b72bc08a55c839fc1a43bc741a81e':'media',
    'e1dbadce60dc080d15b58a014b0dcf9400e24de23fa00b287a5a982bfebda2ee':'networkstack',
    'a6ccc500ff0e7421200eb66a7fe174ef1b00e52ca91727070cbedf061ff76c35':'bluetooth',
    'fae9122a8721d6e2a196d2224dffcf773c9127e2bb956cbddb40b009192ffdfd':'nfc',
    'abf21f9e2af1d881cc673fddcefa6ed9c269a437bd64b279cf45844cfd589126':'sdk_sandbox',
    'ce7b2b47ae2b7552c8f92cc29124279883041fb623a5f194a82c9bf15d492aa0':'cts_uicc_2021',
}
SIGNER=(r'(?:Signer(?: #[0-9]+)?|V(?:1|2|3(?:\.[012])?|4) Signer(?: #[0-9]+)?)')
SDK_RANGE=(r'(?: \(minSdkVersion=[0-9]+(?: \(dev release=true\))?, maxSdkVersion=[0-9]+\))?')
CERT_LINE=re.compile(r'^'+SIGNER+r':?'+SDK_RANGE+r' certificate SHA-256 digest: ([0-9a-fA-F]{64})$',re.M)
SCHEME_LINE=re.compile(r'^Verified using v(1|2|3(?:\.[012])?|4) scheme .*: (true|false)$',re.M)

class SignerOutputError(ValueError):pass


def parse_certificates(text: str) -> list[str]:
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_OUTPUT:
        raise SignerOutputError('Apksigner output exceeds bounds')
    return sorted({x.lower() for x in CERT_LINE.findall(text)})


def aosp_public_development_certificate_name(certificate_sha256: str | None) -> str | None:
    """Return a known AOSP development-key name, never a trust verdict."""
    if certificate_sha256 is None:return None
    if not isinstance(certificate_sha256,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',certificate_sha256):
        raise SignerOutputError('Invalid signer certificate SHA-256')
    return AOSP_PUBLIC_DEVELOPMENT_CERTIFICATES.get(certificate_sha256.lower())


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
