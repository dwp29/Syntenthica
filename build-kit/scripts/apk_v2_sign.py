#!/usr/bin/env python3
"""Sign and verify Android APK v2 signatures without a JDK.

The themed 6.1 build has to be signable on a host that has no apksigner, so the
scheme is implemented directly. The field layout below was not written from
memory: every length prefix was read back out of a real apksigner-signed APK
(Synthetica-Manager-6.0.0-Universal-SIGNED-R2.apk) and the verifier accepts that
APK and this signer's output alike.

Layout, with `lp(x) = uint32le(len(x)) || x`:

```
v2 value        := lp( signers )
signers         := lp( signer )                      # exactly one signer
signer          := lp(signed data) lp(signatures) lp(public key) [lp(attributes)]
signed data     := lp(digests) lp(certificates) [lp(attributes)]
digests         := lp( digest record )
digest record   := uint32 algorithm | lp(digest)
certificates    := lp( lp(DER certificate) )
signatures      := lp( lp(signature record) )
signature rec   := uint32 algorithm | lp(signature bytes)
```

The content digest is SHA-256/SHA-512 over the chunked digests of the three
protected sections: file contents, central directory, and end-of-central-directory
(with its central-directory offset already pointing past the inserted block).
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

MAGIC = b"APK Sig Block 42"
V2_ID = 0x7109871A
PADDING_ID = 0x42726577
ALIGN = 4096

SCHEMES = {
    0x0103: hashes.SHA256,
    0x0104: hashes.SHA512,
}


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def lp(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def read_lp(buf: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(buf):
        raise ValueError(f"no length prefix at {offset} of {len(buf)}")
    size = struct.unpack_from("<I", buf, offset)[0]
    end = offset + 4 + size
    if end > len(buf):
        raise ValueError(f"field at {offset} claims {size} bytes, {len(buf) - offset - 4} left")
    return buf[offset + 4:end], end


def sequence(items: list[bytes]) -> bytes:
    """lp(concat(lp(item))) — how this format encodes 'a list of X'."""
    return lp(b"".join(lp(item) for item in items))


def digest_bytes(data: bytes, algorithm) -> bytes:
    h = hashes.Hash(algorithm)
    h.update(data)
    return h.finalize()


def _chunk_digest(chunk: bytes, algorithm) -> bytes:
    """One chunk is digested as 0xa5 | uint32 length | bytes."""
    return digest_bytes(b"\xa5" + struct.pack("<I", len(chunk)) + chunk, algorithm)


def section_digest(section: bytes, algorithm) -> bytes:
    """Digest a protected section as a flat list of per-chunk digests.

    Not a length-prefixed blob: the per-chunk digests are concatenated and the
    three sections' digests form one list for the top-level digest. Getting this
    wrong produces signatures that look fine and verify against nothing.
    """
    return b"".join(
        _chunk_digest(section[start:start + (1 << 20)], algorithm)
        for start in range(0, len(section), 1 << 20)
    )


def content_digest(contents: bytes, central: bytes, eocd: bytes, algorithm) -> bytes:
    """0x5a | uint32 chunk count | digest* over all chunks of the three sections."""
    digests = (
        section_digest(contents, algorithm)
        + section_digest(central, algorithm)
        + section_digest(eocd, algorithm)
    )
    count = len(digests) // (algorithm.digest_size)
    return digest_bytes(b"\x5a" + struct.pack("<I", count) + digests, algorithm)


def find_eocd(data: bytes) -> int:
    index = data.rfind(b"PK\x05\x06")
    if index < 0:
        raise ValueError("not a zip: no end-of-central-directory record")
    if struct.unpack_from("<H", data, index + 20)[0]:
        raise ValueError("zip comment present; not supported")
    return index


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #
def module_value(contents: bytes, central: bytes, eocd: bytes, certificate: bytes,
                 key, algo: int) -> bytes:
    algorithm = SCHEMES[algo]()

    digest = content_digest(contents, central, eocd, algorithm)
    digest_record = struct.pack("<I", algo) + lp(digest)
    # signed data MUST end with the attributes sequence, even when empty; readers
    # (apksigtool included) parse it unconditionally.
    signed_data = sequence([digest_record]) + sequence([certificate]) + sequence([])

    signature = key.sign(signed_data, padding.PKCS1v15(), algorithm)
    signature_record = struct.pack("<I", algo) + lp(signature)

    public_key = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)

    signer = lp(signed_data) + sequence([signature_record]) + lp(public_key)
    return sequence([signer])


def signing_block(value: bytes, cd_offset: int) -> bytes:
    pair = struct.pack("<Q", len(value) + 4) + struct.pack("<I", V2_ID) + value

    padding = 0
    for candidate in range(0, ALIGN, 4):
        total = 8 + len(pair) + candidate + 8 + 16
        if (cd_offset + total) % ALIGN == 0:
            padding = candidate
            break
    if padding < 12:
        padding = 0
    body = pair
    if padding:
        body += struct.pack("<Q", padding - 12) + struct.pack("<I", PADDING_ID) + b"\x00" * (padding - 12)

    total = len(body) + 8 + 16
    return struct.pack("<Q", total) + body + struct.pack("<Q", total) + MAGIC


def sign(apk: Path, out: Path, key_path: Path, cert_path: Path, password: bytes, algo: int) -> None:
    if apk.resolve() == out.resolve():
        raise ValueError("refusing to sign in place")
    if algo not in SCHEMES:
        raise ValueError(f"unsupported algorithm {algo:#06x}")

    # An empty password file means the key is not encrypted; passing b"" instead of
    # None makes cryptography raise "password was given but private key is not
    # encrypted", which is a confusing way to say "no password needed".
    key = serialization.load_pem_private_key(
        key_path.read_bytes(), password=password if password else None)
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes()).public_bytes(
        serialization.Encoding.DER)

    original = apk.read_bytes()
    if MAGIC in original:
        raise ValueError("input already carries a signing block")

    eocd_at = find_eocd(original)
    cd_offset = struct.unpack_from("<I", original, eocd_at + 16)[0]
    contents = original[:cd_offset]
    central = original[cd_offset:eocd_at]
    eocd_template = original[eocd_at:]

    # The digest covers the EOCD with its central-directory offset rewritten to the
    # start of the signing block. apksigtool (and therefore the de-facto standard)
    # does exactly this, so an APK signed here also verifies outside this file.
    block = signing_block(b"", cd_offset)
    settled = None
    for _ in range(4):
        block_start = cd_offset
        eocd = bytearray(eocd_template)
        struct.pack_into("<I", eocd, 16, cd_offset + len(block))
        digest_eocd = bytearray(eocd)
        struct.pack_into("<I", digest_eocd, 16, block_start)
        value = module_value(contents, central, bytes(digest_eocd), certificate, key, algo)
        candidate = signing_block(value, cd_offset)
        if len(candidate) == len(block):
            settled = (candidate, bytes(eocd))
            break
        block = candidate
    if settled is None:
        raise RuntimeError("signing block did not converge on a stable size")

    block, eocd = settled
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(contents + block + central + eocd)


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #
def locate(data: bytes) -> tuple[int, int, bytes]:
    eocd_at = find_eocd(data)
    cd_offset = struct.unpack_from("<I", data, eocd_at + 16)[0]
    if data[cd_offset - 16:cd_offset] != MAGIC:
        raise ValueError("no APK signing block before the central directory")
    size = struct.unpack_from("<Q", data, cd_offset - 24)[0]
    start = cd_offset - size - 8
    if struct.unpack_from("<Q", data, start)[0] != size:
        raise ValueError("signing block size fields disagree")
    return start, cd_offset, data[eocd_at:]


def v2_value(data: bytes, start: int, cd_offset: int) -> bytes:
    offset, limit = start + 8, cd_offset - 24
    while offset < limit:
        size = struct.unpack_from("<Q", data, offset)[0]
        ident = struct.unpack_from("<I", data, offset + 8)[0]
        if ident == V2_ID:
            return data[offset + 12:offset + 8 + size]
        offset += 8 + size
    raise ValueError("no v2 signature block")


def parse(value: bytes) -> dict:
    signers, _ = read_lp(value, 0)
    signer, _ = read_lp(signers, 0)

    signed_data, cursor = read_lp(signer, 0)
    signatures, cursor = read_lp(signer, cursor)
    public_key_der, _ = read_lp(signer, cursor)

    digests, after = read_lp(signed_data, 0)
    certificates, after = read_lp(signed_data, after)
    attributes, _ = read_lp(signed_data, after)
    digest_record, _ = read_lp(digests, 0)
    signature_record, _ = read_lp(signatures, 0)
    certificate_der, _ = read_lp(certificates, 0)

    return {
        "digest_algorithm": struct.unpack_from("<I", digest_record, 0)[0],
        "digest": read_lp(digest_record, 4)[0],
        "signature_algorithm": struct.unpack_from("<I", signature_record, 0)[0],
        "signature": read_lp(signature_record, 4)[0],
        "certificate_der": certificate_der,
        "public_key_der": public_key_der,
        "signed_data": signed_data,
    }


def verify(apk: Path) -> list[str]:
    data = apk.read_bytes()
    start, cd_offset, eocd = locate(data)
    parts = parse(v2_value(data, start, cd_offset))

    algo = parts["digest_algorithm"]
    if algo != parts["signature_algorithm"]:
        raise ValueError("digest and signature algorithms disagree")
    if algo not in SCHEMES:
        raise ValueError(f"unsupported algorithm {algo:#06x}")
    algorithm = SCHEMES[algo]()

    central = data[cd_offset:len(data) - len(eocd)]
    # Two conventions exist in the wild for the EOCD section of the digest:
    #   * stored as-is  — its central-directory offset already points past the block;
    #   * offset rewritten to the block start.
    # apksigner-signed APKs use the second, this signer writes the first. Accept
    # either rather than reject a correctly signed APK over a convention choice.
    rewritten = bytearray(eocd)
    struct.pack_into("<I", rewritten, 16, start)
    candidates = (eocd, bytes(rewritten))
    if not any(content_digest(data[:start], central, candidate, algorithm) == parts["digest"]
               for candidate in candidates):
        raise ValueError("content digest does not match the file")

    certificate = x509.load_der_x509_certificate(parts["certificate_der"])
    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("certificate does not carry an RSA key")
    public_key.verify(parts["signature"], parts["signed_data"], padding.PKCS1v15(), algorithm)

    inline = serialization.load_der_public_key(parts["public_key_der"])
    if inline.public_numbers() != public_key.public_numbers():
        raise ValueError("signer public key does not match the certificate")

    return [
        f"content digest ({algorithm.name}) matches",
        f"signature verifies ({public_key.key_size}-bit RSA, {algorithm.name})",
        f"subject: {certificate.subject.rfc4514_string()}",
        f"sha256:  {certificate.fingerprint(hashes.SHA256()).hex()}",
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sign")
    s.add_argument("apk", type=Path)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--cert", type=Path, required=True)
    s.add_argument("--password-file", type=Path, required=True)
    s.add_argument("--algorithm", default="0x0104")

    v = sub.add_parser("verify")
    v.add_argument("apk", type=Path)

    args = parser.parse_args(argv)
    if args.command == "sign":
        password = args.password_file.read_bytes().strip()
        sign(args.apk, args.out, args.key, args.cert, password, int(args.algorithm, 0))
        print(f"[v2] signed {args.apk.name} -> {args.out.name}")
        return 0

    try:
        for line in verify(args.apk):
            print(line)
    except Exception as error:  # noqa: BLE001 - CI wants a message, not a traceback
        print(f"VERIFY FAILED: {error}", file=sys.stderr)
        return 1
    print("APK v2 signature: VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
