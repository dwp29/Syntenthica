"""Exercise the prepared KSUN signing-block parser with a real APK layout.

File I/O and the digest are mocked: these tests are NOT APK signature
verification, kernel execution, or evidence of Android installation.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_synthetica40 as s40

V2_ID = 0x7109871A
V3_ID = 0xF05368C0


def apk_parts(data: bytes):
    """Split the known reference APK; this helper is not a general ZIP parser."""
    eocd = data.rfind(b'PK\x05\x06')
    if eocd < 0:
        raise ValueError('reference EOCD missing')
    cd_size, cd = struct.unpack_from('<II', data, eocd + 12)
    if cd + cd_size != eocd or data[cd - 16:cd] != b'APK Sig Block 42':
        raise ValueError('reference signing block or central directory invalid')
    size = struct.unpack_from('<Q', data, cd - 24)[0]
    head = cd - size - 8
    if head < 0 or struct.unpack_from('<Q', data, head)[0] != size:
        raise ValueError('reference signing block lengths disagree')
    pairs = []
    pos, end = head + 8, cd - 24
    while pos < end:
        length = struct.unpack_from('<Q', data, pos)[0]
        if length < 4 or pos + 8 + length > end:
            raise ValueError('invalid reference signing pair')
        pairs.append((struct.unpack_from('<I', data, pos + 8)[0], data[pos:pos + 8 + length]))
        pos += 8 + length
    if pos != end:
        raise ValueError('invalid reference pair boundary')
    return eocd, cd, head, pairs


def fixture_with_pairs(data: bytes, pairs: list[bytes]) -> bytes:
    """Rewrite only a disposable test fixture; it is no longer a signed APK."""
    eocd, cd, head, _ = apk_parts(data)
    body = b''.join(pairs)
    length = len(body) + 24
    block = struct.pack('<Q', length) + body + struct.pack('<Q', length) + b'APK Sig Block 42'
    result = bytearray(data[:head] + block + data[cd:])
    new_cd = head + len(block)
    struct.pack_into('<I', result, eocd + new_cd - cd + 16, new_cd)
    return bytes(result)


@unittest.skipUnless(shutil.which('gcc'), 'gcc required')
class PreparedApkParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepared = os.environ.get('S40_TEST_PREPARED')
        if not prepared:
            raise unittest.SkipTest('S40_TEST_PREPARED required for actual parser tests')
        cls.source = Path(prepared) / 'drivers/kernelsu/manager/apk_sign.c'
        if not cls.source.is_file():
            raise AssertionError('prepared KSUN parser not found')

    def test_real_parser_rejects_reference_v3_and_malformed_pairs(self):
        data = (ROOT / 'release/Synthetica-2.0.apk').read_bytes()
        _, _, _, pairs = apk_parts(data)
        self.assertIn(V3_ID, [kind for kind, _ in pairs])
        v2_pairs = [pair for kind, pair in pairs if kind == V2_ID]
        self.assertEqual(len(v2_pairs), 1)
        v2 = v2_pairs[0]
        value = v2[12:]
        offset = 12  # signers, first signer and signed-data length fields
        digest_size = struct.unpack_from('<I', value, offset)[0]
        offset += 4 + digest_size
        cert_sequence_size = struct.unpack_from('<I', value, offset)[0]
        cert_size = struct.unpack_from('<I', value, offset + 4)[0]
        offset += 8
        cert = value[offset:offset + cert_size]
        self.assertGreaterEqual(cert_sequence_size, 4 + cert_size)
        self.assertEqual(cert_size, s40.CERT_SIZE)
        self.assertEqual(hashlib.sha256(cert).hexdigest(), s40.CERT_HASH)

        v2_only = fixture_with_pairs(data, [v2])
        duplicate = fixture_with_pairs(data, [v2, v2])
        unknown = struct.pack('<QI', 5, 0x12345678) + b'x'
        unknown_pair = fixture_with_pairs(data, [v2, unknown])
        wrong_cert = bytearray(v2_only)
        cert_pos = wrong_cert.find(cert)
        self.assertGreaterEqual(cert_pos, 0)
        wrong_cert[cert_pos] ^= 1
        malformed = bytearray(v2_only)
        _, _, head, _ = apk_parts(v2_only)
        struct.pack_into('<Q', malformed, head + 8, (1 << 64) - 1)
        zip64 = bytearray(v2_only)
        eocd, _, _, _ = apk_parts(v2_only)
        struct.pack_into('<I', zip64, eocd - 20, 0x07064B50)

        signer = self.source.read_text()
        start = signer.index('static bool read_exact(')
        end = signer.index('\n#ifdef CONFIG_KSU_DEBUG\n\nint ksu_debug_manager_appid', start)
        actual = signer[start:end]
        cert_literal = ','.join(str(x) for x in cert)
        digest_literal = ','.join(str(x) for x in bytes.fromhex(s40.CERT_HASH))
        preamble = r'''
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/types.h>
#include <stdio.h>
#include <fcntl.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define SHA256_DIGEST_SIZE 32
#define GFP_KERNEL 0
#define IS_ERR(p) ((p) == NULL)
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)
static const unsigned char expected_cert[] = { CERT_LITERAL };
static const unsigned char expected_digest[] = { DIGEST_LITERAL };
struct file { unsigned char *data; size_t len; };
static void *kmalloc(size_t n, int flags) { (void)flags; return malloc(n); }
static void kfree(void *p) { free(p); }
static struct file *ksu_filp_open_nonotify(const char *path, int flags) {
    (void)flags;
    FILE *input = fopen(path, "rb");
    if (!input) return NULL;
    if (fseek(input, 0, SEEK_END) != 0) { fclose(input); return NULL; }
    long length = ftell(input);
    if (length < 0 || fseek(input, 0, SEEK_SET) != 0) { fclose(input); return NULL; }
    struct file *f = malloc(sizeof(*f));
    if (!f) { fclose(input); return NULL; }
    f->len = (size_t)length; f->data = malloc(f->len ? f->len : 1);
    if (!f->data || fread(f->data, 1, f->len, input) != f->len) {
        free(f->data); free(f); fclose(input); return NULL;
    }
    fclose(input); return f;
}
static loff_t generic_file_llseek(struct file *f, loff_t offset, int whence) {
    return whence == SEEK_END ? (loff_t)f->len + offset : -1;
}
static ssize_t kernel_read(struct file *f, void *buffer, size_t n, loff_t *pos) {
    if (*pos < 0 || (size_t)*pos > f->len || n > f->len - (size_t)*pos) return -1;
    memcpy(buffer, f->data + *pos, n); *pos += n; return (ssize_t)n;
}
static int filp_close(struct file *f, void *unused) {
    (void)unused; free(f->data); free(f); return 0;
}
static int ksu_sha256(const unsigned char *data, unsigned n, unsigned char *out) {
    // A mock for the exact, separately SHA-256-checked reference DER bytes.
    if (n == sizeof(expected_cert) && memcmp(data, expected_cert, n) == 0)
        memcpy(out, expected_digest, 32);
    else
        memset(out, 0, 32);
    return 0;
}
static void bin2hex(char *out, const unsigned char *in, size_t n) {
    const char *digits = "0123456789abcdef";
    for (size_t i = 0; i < n; ++i) { out[i*2] = digits[in[i] >> 4]; out[i*2+1] = digits[in[i] & 15]; }
}
'''.replace('CERT_LITERAL', cert_literal).replace('DIGEST_LITERAL', digest_literal)
        harness = r'''
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    bool expected = argv[1][0] == '1';
    bool accepted = check_v2_signature(argv[2], sizeof(expected_cert), "EXPECTED_HASH");
    if (accepted != expected) {
        fprintf(stderr, "expected %d, got %d for %s\n", expected, accepted, argv[2]);
        return 1;
    }
    return 0;
}
'''.replace('EXPECTED_HASH', s40.CERT_HASH)
        cases = {
            'reference-v2-v3.apk': (data, False),
            'rewritten-v2-only-NOT-A-VALID-APK': (v2_only, True),
            'duplicate-v2': (duplicate, False),
            'unknown-pair': (unknown_pair, False),
            'wrong-certificate': (bytes(wrong_cert), False),
            'malformed-pair-length': (bytes(malformed), False),
            'zip64-marker': (bytes(zip64), False),
            'truncated': (v2_only[:-40], False),
        }
        with tempfile.TemporaryDirectory(prefix='s40-apk-parser-') as temp:
            directory = Path(temp)
            c = directory / 'parser.c'
            exe = directory / 'parser'
            c.write_text(preamble + actual + harness)
            subprocess.run(['gcc', '-std=gnu11', '-O1', '-Werror', '-Wall', '-Wextra',
                            '-Wno-pointer-sign', str(c), '-o', str(exe)], check=True)
            for name, (content, expected) in cases.items():
                with self.subTest(case=name):
                    apk = directory / name
                    apk.write_bytes(content)
                    result = subprocess.run([str(exe), '1' if expected else '0', str(apk)],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
