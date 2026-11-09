from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "build-kit/scripts"
sys.path.insert(0, str(SCRIPTS))
import build_synthetica40 as s40


class SourceAndConfigTests(unittest.TestCase):
    def test_pins_are_genuine_and_not_the_rejected_2_0_baseline(self):
        self.assertEqual(s40.PINS["kernel"]["version"], "6.18.58")
        self.assertEqual(s40.PINS["ksun"]["uapi"], 5)
        self.assertEqual(s40.PINS["nomount"]["protocol"], 22)
        self.assertFalse(s40.PINS["susfs_research_only"]["included_in_kernel"])
        self.assertFalse(s40.PINS["manager_identity"]["compatible_with_experimental_kernel"])
        for name in ("kernel", "ksun", "nomount", "susfs_research_only"):
            self.assertEqual(len(s40.PINS[name]["commit"]), 40)
            self.assertEqual(len(s40.PINS[name]["archive_sha256"]), 64)

    def test_archive_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "source.tar.gz"
            p.write_bytes(b"wrong input")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                s40.verify_archive("nomount", p)

    def test_exact_anchor_guard_rejects_missing_or_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            f = Path(temp) / "file"
            f.write_text("old\n")
            s40.replace_once(f, "old", "new")
            self.assertEqual(f.read_text(), "new\n")
            with self.assertRaises(ValueError):
                s40.replace_once(f, "old", "oops")
            f.write_text("old old")
            with self.assertRaises(ValueError):
                s40.replace_once(f, "old", "oops")

    def test_work_directory_safety(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "input"
            source.mkdir()
            s40.check_work_directory(base / "work", [source])
            for unsafe in (ROOT, ROOT / "foo", source, source / "output", base):
                with self.subTest(path=unsafe), self.assertRaises(ValueError):
                    s40.check_work_directory(unsafe, [source])
            (base / "work").mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                s40.check_work_directory(base / "work", [source])

    def test_config_last_fragment_wins_and_missing_is_not_silent(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            (d / "a").write_text('CONFIG_X=m\n# CONFIG_Y is not set\n')
            (d / "b").write_text('CONFIG_X=y\nCONFIG_Z="text"\n')
            (d / "actual").write_text('CONFIG_X=y\nCONFIG_Z="text"\n')
            s40.check_config(d / "actual", [d / "a", d / "b"])
            (d / "actual").write_text('CONFIG_X=m\nCONFIG_Z="text"\n')
            with self.assertRaisesRegex(ValueError, "CONFIG_X"):
                s40.check_config(d / "actual", [d / "a", d / "b"])

    def test_nomount_abi_mismatched_order_and_struct_are_rejected(self):
        template = '''
#define NOMOUNT_MAGIC_SIG 0x4E4F4D4F554E54ULL
%s
enum { NM_CMD_UNSPEC = 0, NM_CMD_GET_VERSION, NM_CMD_ADD_RULE, };
struct nm_payload { %s magic; unsigned int cmd; int status; char buffer[4068]; } __attribute__((packed));
struct nm_rule_hdr { unsigned int flags; unsigned short v_len; } __attribute__((packed));
struct nm_del_hdr { unsigned int uid; unsigned short v_len; } __attribute__((packed));
%s
'''
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            (d / "kernel/src").mkdir(parents=True)
            (d / "userspace/src").mkdir(parents=True)
            kh = d / "kernel/src/nomount.h"
            uh = d / "userspace/src/nm.h"
            kh.write_text(template % ('#define NOMOUNT_BASE_VERSION "22"', 'u64', ''))
            uh.write_text(template % ('', 'unsigned long long', '_Static_assert(sizeof(struct nm_payload) == 4096, "size");'))
            s40.check_nomount_protocol(d)
            uh.write_text(uh.read_text().replace('NM_CMD_GET_VERSION, NM_CMD_ADD_RULE', 'NM_CMD_ADD_RULE, NM_CMD_GET_VERSION'))
            with self.assertRaisesRegex(ValueError, "command"):
                s40.check_nomount_protocol(d)
            uh.write_text(template % ('', 'unsigned long long', '_Static_assert(sizeof(struct nm_payload) == 4096, "size");'))
            uh.write_text(uh.read_text().replace('unsigned short v_len', 'unsigned int v_len'))
            with self.assertRaisesRegex(ValueError, "nm_rule_hdr"):
                s40.check_nomount_protocol(d)

    def test_reference_apk_v2_certificate_identity_and_v3_block(self):
        data = (ROOT / "release/Synthetica-2.0.apk").read_bytes()
        eocd = data.rfind(b"PK\x05\x06")
        cd = struct.unpack_from("<I", data, eocd + 16)[0]
        size = struct.unpack_from("<Q", data, cd - 24)[0]
        self.assertEqual(data[cd - 16:cd], b"APK Sig Block 42")
        pos, end, ids, v2 = cd - size, cd - 24, set(), None
        while pos < end:
            length = struct.unpack_from("<Q", data, pos)[0]
            kind = struct.unpack_from("<I", data, pos + 8)[0]
            ids.add(kind)
            if kind == 0x7109871A:
                v2 = data[pos + 12:pos + 8 + length]
            pos += 8 + length
        self.assertEqual(pos, end)
        self.assertIn(0xF05368C0, ids, "reference APK has an additional v3 signing block")
        self.assertIsNotNone(v2)
        def get_u32(buf, index):
            return struct.unpack_from("<I", buf, index)[0]
        # signers -> first signer -> signed_data -> digests -> certificates
        off = 4 + 4 + 4
        digest_size = get_u32(v2, off)
        off += 4 + digest_size
        cert_list_size = get_u32(v2, off)
        off += 4
        cert_size = get_u32(v2, off)
        off += 4
        self.assertLessEqual(cert_size + 4, cert_list_size)
        cert = v2[off:off + cert_size]
        self.assertEqual(cert_size, s40.CERT_SIZE)
        self.assertEqual(hashlib.sha256(cert).hexdigest(), s40.CERT_HASH)


class ActualPreparedKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("S40_TEST_PREPARED")
        if not path:
            raise unittest.SkipTest("S40_TEST_PREPARED not provided; compiled-source tests require the pinned prepared tree")
        cls.tree = Path(path)
        if not cls.tree.is_dir():
            raise AssertionError("S40_TEST_PREPARED is not a directory")

    def test_integrated_sources_and_security_contract(self):
        driver = self.tree / "drivers/kernelsu"
        kbuild = (driver / "Kbuild").read_text()
        signer = (driver / "manager/apk_sign.c").read_text()
        self.assertIn('KSU_VERSION_FALLBACK := 33355', kbuild)
        self.assertIn('KSU_VERSION_TAG_FALLBACK := v3.4.2', kbuild)
        self.assertIn('KSU_MANAGER_PACKAGE ?= net.ember.labs', kbuild)
        self.assertIn(f'KSU_NEXT_MANAGER_SIZE := 0x{s40.CERT_SIZE:x}', kbuild)
        self.assertIn(s40.CERT_HASH, kbuild)
        self.assertIn('KERNEL_SU_UAPI_VERSION = 5;', (driver / "include/uapi/supercall.h").read_text())
        self.assertIn('#define CERT_MAX_LENGTH 2048', signer)
        self.assertIn('certificate_size != expected_size', signer)
        self.assertIn('strcmp(expected_sha256, hash_str) == 0', signer)
        # Do not broaden upstream's APK-signing-block acceptance on a root path.
        self.assertIn('id != 0x42726577u', signer)
        self.assertIn('goto invalid;', signer)
        self.assertNotIn('-fno-stack-protector', (self.tree / 'fs/nomount/Makefile').read_text())
        self.assertIn('#define NOMOUNT_BASE_VERSION "22"', (self.tree / 'fs/nomount/nomount.h').read_text())
        self.assertFalse((self.tree / 'fs/susfs.c').exists(), 'SUSFS 2.4 is not falsely claimed as integrated')

    @unittest.skipUnless(shutil.which("gcc"), "gcc required")
    def test_real_certificate_parser_with_mocked_io_and_crypto(self):
        signer = (self.tree / "drivers/kernelsu/manager/apk_sign.c").read_text()
        start = signer.index('static bool read_exact(')
        end = signer.index('static __always_inline bool check_v2_signature', start)
        actual = signer[start:end]
        preamble = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/types.h>
#include <stdio.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define SHA256_DIGEST_SIZE 32
#define GFP_KERNEL 0
#define pr_info(...) ((void)0)
struct file { unsigned char *data; size_t len; };
static int allocations, fail_alloc, fail_hash;
static void *kmalloc(size_t n, int flags) { (void)flags; if (fail_alloc) return NULL; void *p=malloc(n); if (p) allocations++; return p; }
static void kfree(void *p) { if (p) { allocations--; free(p); } }
static ssize_t kernel_read(struct file *f, void *b, size_t n, loff_t *pos) {
    if (*pos < 0 || (size_t)*pos > f->len || n > f->len - (size_t)*pos) return -1;
    memcpy(b, f->data + *pos, n); *pos += n; return n;
}
static int ksu_sha256(const unsigned char *data, unsigned n, unsigned char *out) {
    if (fail_hash) return -1;
    if (!n) return -1;
    memset(out, data[0] == 0xaa ? 0x42 : 0x24, 32); return 0;
}
static void bin2hex(char *out, const unsigned char *in, size_t n) {
    const char *d="0123456789abcdef";
    for (size_t i=0;i<n;i++) { out[i*2]=d[in[i]>>4]; out[i*2+1]=d[in[i]&15]; }
}
'''
        tests = r'''
static void put32(unsigned char *p, u32 n) { p[0]=n; p[1]=n>>8; p[2]=n>>16; p[3]=n>>24; }
static int run(unsigned len, int expected, int corrupt, int allocation_fail, int hash_fail, int truncate) {
    unsigned total=24+len;
    unsigned char *b=calloc(1,total);
    put32(b,20+len); put32(b+4,16+len); put32(b+8,12+len); put32(b+12,0); put32(b+16,4+len); put32(b+20,len);
    memset(b+24, corrupt ? 0xbb : 0xaa, len);
    struct file f={b,truncate ? total-1 : total}; loff_t pos=0;
    const char *hash="4242424242424242424242424242424242424242424242424242424242424242";
    fail_alloc=allocation_fail; fail_hash=hash_fail;
    bool result=check_block(&f,&pos,f.len,len,hash); free(b);
    if (allocations != 0 || result != expected) return 1;
    return 0;
}
int main(void) {
    if (run(1381,1,0,0,0,0)) return 1;
    if (run(1381,0,1,0,0,0)) return 2;
    if (run(2049,0,0,0,0,0)) return 3;
    if (run(1381,0,0,1,0,0)) return 4;
    if (run(1381,0,0,0,1,0)) return 5;
    if (run(1381,0,0,0,0,1)) return 6;
    puts("real parser: valid, digest mismatch, size cap, OOM, hash failure and truncation passed");
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            c = Path(temp) / 'signer_test.c'
            exe = Path(temp) / 'signer_test'
            c.write_text(preamble + actual + tests)
            subprocess.run(['gcc', '-std=gnu11', '-Werror', '-Wall', '-Wextra', '-Wno-pointer-sign', str(c), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
            self.assertIn('passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
