#!/usr/bin/env python3
"""Probe APK v2/v3 policy with throwaway keys and host-compiled source only.

Uses an isolated no-code fixture or a verified unsigned development Manager.
It never uses a production key, installs an APK, or exports the key or signed
fixtures. This is not an Android update, device, root, or kernel-runtime test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_synthetica40 as s40
import verify_s40_manager_uapi5_apk as manager_guard

V2 = 0x7109871A
V3 = 0xF05368C0
V31 = 0x1B93AD61
PADDING = 0x42726577
MAX_APK = 32 * 1024 * 1024
# The first is the deterministic output of the 3.4.2 preparation in this repo;
# the second is the unmodified 3.4.2 ksud source. Do not silently run a probe
# against a different parser and present it as this experiment.
PREPARED_PARSER_SHA256 = 'e8f1a427758a27cf3a6892a64fe29a420bcd005084d034d5693a50106bbfc6cb'
KSUD_PARSER_SHA256 = 'd1eb1b793184fd64780414382353cb4583d9f8000da3bd0ea436fcf99fe18486'


def checked_source(path: Path, expected: str) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Missing or symlinked parser source: {path}')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f'Parser source SHA-256 mismatch: {path}')
    return content.decode('utf-8')


def inspect_apk(path: Path) -> tuple[list[int], bytes]:
    """Extract pair IDs and first v2 certificate from a bounded test APK.

    This is a fixture helper, not a cryptographic APK signature verifier.
    """
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_APK:
        raise ValueError('Missing, symlinked or oversized APK fixture')
    data = path.read_bytes()
    eocd = data.rfind(b'PK\x05\x06')
    if eocd < 0 or eocd + 22 > len(data):
        raise ValueError('APK fixture EOCD missing')
    size_cd, cd = struct.unpack_from('<II', data, eocd + 12)
    if cd < 32 or cd + size_cd != eocd or data[cd - 16:cd] != b'APK Sig Block 42':
        raise ValueError('APK fixture signing block missing')
    block_size = struct.unpack_from('<Q', data, cd - 24)[0]
    head = cd - block_size - 8
    if head < 0 or struct.unpack_from('<Q', data, head)[0] != block_size:
        raise ValueError('APK fixture block sizes differ')
    ids, v2_values = [], []
    pos, end = head + 8, cd - 24
    while pos < end:
        if pos + 12 > end:
            raise ValueError('APK fixture pair header truncated')
        size = struct.unpack_from('<Q', data, pos)[0]
        if size < 4 or size > end - pos - 8:
            raise ValueError('APK fixture pair size invalid')
        kind = struct.unpack_from('<I', data, pos + 8)[0]
        ids.append(kind)
        if kind == V2:
            v2_values.append(data[pos + 12:pos + 8 + size])
        pos += 8 + size
    if pos != end or len(v2_values) != 1:
        raise ValueError('APK fixture must contain exactly one bounded v2 block')
    value = v2_values[0]

    def field(start: int, limit: int) -> tuple[int, int]:
        if start + 4 > limit:
            raise ValueError('APK fixture length field truncated')
        length = struct.unpack_from('<I', value, start)[0]
        start += 4
        if length > limit - start:
            raise ValueError('APK fixture nested field exceeds container')
        return start, start + length

    signers = field(0, len(value))
    signer = field(signers[0], signers[1])
    signed = field(signer[0], signer[1])
    digests = field(signed[0], signed[1])
    certs = field(digests[1], signed[1])
    cert = field(certs[0], certs[1])
    return ids, value[cert[0]:cert[1]]


def run(command: list[str], *, env: dict[str, str] | None = None, expect_success: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.returncode == 0) != expect_success:
        detail = (result.stdout + '\n' + result.stderr)[-4000:]
        raise RuntimeError(f'{Path(command[0]).name} returned {result.returncode}: {detail}')
    return result


KERNEL_PREAMBLE = r'''
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/types.h>
#include <stdio.h>
#include <fcntl.h>
#include <openssl/sha.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define SHA256_DIGEST_SIZE 32
#define GFP_KERNEL 0
#define IS_ERR(p) ((p) == NULL)
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)
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
    return SHA256(data, n, out) ? 0 : -1;
}
static void bin2hex(char *out, const unsigned char *in, size_t n) {
    const char *digits = "0123456789abcdef";
    for (size_t i = 0; i < n; ++i) { out[i*2] = digits[in[i] >> 4]; out[i*2+1] = digits[in[i] & 15]; }
}
'''
KERNEL_MAIN = r'''
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    unsigned long size = strtoul(argv[2], NULL, 10);
    if (size > 2048 || strlen(argv[3]) != 64) return 2;
    bool expected = argv[4][0] == '1';
    bool accepted = check_v2_signature(argv[1], (unsigned)size, argv[3]);
    if (accepted != expected) {
        fprintf(stderr, "expected %d, got %d for %s\n", expected, accepted, argv[1]);
        return 1;
    }
    return 0;
}
'''


def compile_kernel_probe(prepared: Path, directory: Path) -> Path:
    signer = checked_source(prepared / 'drivers/kernelsu/manager/apk_sign.c', PREPARED_PARSER_SHA256)
    if '#define CERT_MAX_LENGTH 2048' not in signer or 'kmalloc(certificate_size, GFP_KERNEL)' not in signer:
        raise ValueError('Expected the actual prepared, bounded certificate parser')
    begin = signer.index('static bool read_exact(')
    end = signer.index('\n#ifdef CONFIG_KSU_DEBUG\n\nint ksu_debug_manager_appid', begin)
    source = directory / 'kernel-parser.c'
    output = directory / 'kernel-parser'
    source.write_text(KERNEL_PREAMBLE + signer[begin:end] + KERNEL_MAIN)
    run(['gcc', '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-pointer-sign',
         str(source), '-lcrypto', '-o', str(output)])
    return output


def derive_prepared_parser(ksun: Path, directory: Path) -> Path:
    """Recreate just the pinned build's parser for host tests, not a kernel tree."""
    upstream = ksun / 'kernel/manager/apk_sign.c'
    source = checked_source(upstream, s40.PINS['ksun']['sentinels']['kernel/manager/apk_sign.c'])
    root = directory / 'derived-prepared-parser'
    target = root / 'drivers/kernelsu/manager/apk_sign.c'
    target.parent.mkdir(parents=True)
    target.write_text(source)
    # Mirrors prepare() in build_synthetica40.py. Verify the entire result
    # against the exact prepared parser hash before compiling the host shim.
    s40.replace_once(target, '#define CERT_MAX_LENGTH 1024\n', '#define CERT_MAX_LENGTH 2048\n')
    s40.replace_once(target,
        '\tchar cert[CERT_MAX_LENGTH];\n'
        '\tif (!read_exact(fp, cert, certificate_size, pos, certificates_end))\n'
        '\t\treturn false;\n\n'
        '\tunsigned char digest[SHA256_DIGEST_SIZE];\n'
        '\tif (ksu_sha256(cert, certificate_size, digest)) {\n',
        '\tunsigned char digest[SHA256_DIGEST_SIZE];\n'
        '\tchar *cert = kmalloc(certificate_size, GFP_KERNEL);\n'
        '\tint digest_result;\n'
        '\tif (!cert)\n'
        '\t\treturn false;\n'
        '\tif (!read_exact(fp, cert, certificate_size, pos, certificates_end)) {\n'
        '\t\tkfree(cert);\n'
        '\t\treturn false;\n'
        '\t}\n'
        '\tdigest_result = ksu_sha256(cert, certificate_size, digest);\n'
        '\tkfree(cert);\n'
        '\tif (digest_result) {\n')
    checked_source(target, PREPARED_PARSER_SHA256)
    return root


def kernel_probe(executable: Path, apk: Path, certificate: bytes, expected: bool, *,
                 digest: str | None = None, size: int | None = None) -> None:
    expected_hash = digest if digest is not None else hashlib.sha256(certificate).hexdigest()
    expected_size = len(certificate) if size is None else size
    run([str(executable), str(apk), str(expected_size), expected_hash, '1' if expected else '0'])


ANYHOW_STUB = r'''
#[derive(Debug)] pub struct Error(String);
impl Error { pub fn msg(s: String) -> Self { Self(s) } }
impl std::fmt::Display for Error { fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { write!(f, "{}", self.0) } }
impl std::error::Error for Error {}
impl From<std::io::Error> for Error { fn from(e: std::io::Error) -> Self { Self(e.to_string()) } }
pub type Result<T> = std::result::Result<T, Error>;
#[macro_export] macro_rules! anyhow { ($($args:tt)*) => { $crate::Error::msg(format!($($args)*)) }; }
#[macro_export] macro_rules! ensure { ($cond:expr, $($args:tt)*) => { if !$cond { return Err($crate::anyhow!($($args)*)); } }; }
'''
SHA256_STUB = r'''
#[link(name = "crypto")]
extern "C" { fn SHA256(data: *const u8, len: usize, digest: *mut u8) -> *mut u8; }
pub fn digest<T: AsRef<[u8]>>(data: T) -> String {
    let input = data.as_ref();
    let mut out = [0u8; 32];
    let result = unsafe { SHA256(input.as_ptr(), input.len(), out.as_mut_ptr()) };
    assert!(!result.is_null());
    out.iter().map(|b| format!("{b:02x}")).collect()
}
'''
RUST_MAIN = r'''
#[path = SOURCE_PATH] mod apk_sign;
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 5 { std::process::exit(2); }
    let expected = args[4] == "1";
    let result = apk_sign::get_apk_signature(&args[1]);
    match result {
        Ok((size, hash)) if expected && size.to_string() == args[2] && hash == args[3] => (),
        Err(error) if !expected && error.to_string().contains("Unexpected v3 signature") => (),
        _ => { eprintln!("unexpected ksud parser outcome"); std::process::exit(1); }
    }
}
'''


def compile_ksud_probe(ksun: Path, directory: Path) -> Path:
    source = ksun / 'userspace/ksud/src/apk_sign.rs'
    checked_source(source, KSUD_PARSER_SHA256)
    anyhow = directory / 'anyhow.rs'
    sha = directory / 'sha256.rs'
    wrapper = directory / 'ksud-parser.rs'
    anyhow.write_text(ANYHOW_STUB)
    sha.write_text(SHA256_STUB)
    wrapper.write_text(RUST_MAIN.replace('SOURCE_PATH', json.dumps(str(source.resolve()))))
    run(['rustc', '--edition=2021', '--crate-name', 'anyhow', '--crate-type', 'rlib', str(anyhow), '-o', str(directory / 'libanyhow.rlib')])
    run(['rustc', '--edition=2021', '--crate-name', 'sha256', '--crate-type', 'rlib', str(sha), '-o', str(directory / 'libsha256.rlib')])
    output = directory / 'ksud-parser'
    run(['rustc', '--edition=2021', '--crate-name', 's40_ksud_probe', str(wrapper),
         '--extern', f'anyhow={directory / "libanyhow.rlib"}',
         '--extern', f'sha256={directory / "libsha256.rlib"}', '-o', str(output)])
    return output


def ksud_probe(executable: Path, apk: Path, certificate: bytes, expected: bool) -> None:
    run([str(executable), str(apk), str(len(certificate)), hashlib.sha256(certificate).hexdigest(),
         '1' if expected else '0'])


def verify_same_zip_payload(original: Path, signed: Path) -> None:
    """Check every decompressed entry; APK signing must not alter app payload."""
    with zipfile.ZipFile(original) as before, zipfile.ZipFile(signed) as after:
        names = before.namelist()
        if len(names) != len(set(names)) or set(names) != set(after.namelist()) or len(names) != len(after.namelist()):
            raise ValueError('Signing changed the APK entry set')
        for name in names:
            if before.getinfo(name).file_size != after.getinfo(name).file_size:
                raise ValueError(f'Signing changed APK entry size: {name}')
            hashes = []
            for archive in (before, after):
                digest = hashlib.sha256()
                with archive.open(name) as entry:
                    for block in iter(lambda: entry.read(1024 * 1024), b''):
                        digest.update(block)
                hashes.append(digest.digest())
            if hashes[0] != hashes[1]:
                raise ValueError(f'Signing changed APK payload: {name}')


def generate_and_probe(prepared: Path | None, ksun: Path, sdk: Path,
                       unsigned_manager: Path | None = None) -> dict:
    tools = sdk / 'build-tools/36.1.0'
    aapt, align, signer = (tools / name for name in ('aapt', 'zipalign', 'apksigner'))
    android_jar = sdk / 'platforms/android-36/android.jar'
    keytool = shutil.which('keytool')
    if not keytool or any(not p.is_file() for p in (aapt, align, signer, android_jar)):
        raise ValueError('Required Java keytool or Android 36 build tools not found')
    if not shutil.which('rustc') or not shutil.which('gcc'):
        raise ValueError('Rust and GCC are required for host-only parser probes')
    with tempfile.TemporaryDirectory(prefix='s40-disposable-signature-fixture-') as temp:
        work = Path(temp)
        env = os.environ.copy()
        env['S40_FIXTURE_PASSWORD'] = 'temporary-fixture-only'
        keystore, cert_file = work / 'temporary-fixture.p12', work / 'fixture-cert.der'
        aligned = work / 'aligned.apk'
        manager_static = None
        if unsigned_manager is not None:
            if not unsigned_manager.is_file() or unsigned_manager.is_symlink() or unsigned_manager.stat().st_size > MAX_APK:
                raise ValueError('Missing, symlinked or oversized unsigned Manager prototype')
            manager_static = manager_guard.verify(unsigned_manager)
            badging = run([str(aapt), 'dump', 'badging', str(unsigned_manager)]).stdout
            if not re.search(r"^package: name='net\.ember\.labs' versionCode='60002' versionName='5\.0\.1-uapi5-dev'", badging, re.M):
                raise ValueError('Unexpected Manager prototype package or version')
            run([str(align), '-c', '-P', '16', '4', str(unsigned_manager)])
            unsigned_result = run([str(signer), 'verify', str(unsigned_manager)], expect_success=False)
            if 'DOES NOT VERIFY' not in (unsigned_result.stdout + unsigned_result.stderr):
                raise ValueError('Manager prototype is not in the expected unsigned state')
            shutil.copyfile(unsigned_manager, aligned)
        else:
            manifest, unsigned = work / 'AndroidManifest.xml', work / 'unsigned.apk'
            manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="net.invalid.s40sigfixture">
  <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="36" />
  <application android:label="TEMPORARY SIGNATURE TEST ONLY" android:hasCode="false" />
</manifest>\n''')
            run([str(aapt), 'package', '-f', '-M', str(manifest), '-I', str(android_jar), '-F', str(unsigned)])
            run([str(align), '-f', '4', str(unsigned), str(aligned)])
        run([keytool, '-genkeypair', '-alias', 'fixture', '-keyalg', 'RSA', '-keysize', '4096',
             '-sigalg', 'SHA256withRSA', '-validity', '1', '-dname',
             'CN=Temporary Signature Fixture Only,OU=No Production Key,O=S40 Test,L=Test,ST=Test,C=US',
             '-keystore', str(keystore), '-storetype', 'PKCS12', '-storepass:env', 'S40_FIXTURE_PASSWORD',
             '-keypass:env', 'S40_FIXTURE_PASSWORD', '-noprompt'], env=env)
        run([keytool, '-exportcert', '-alias', 'fixture', '-keystore', str(keystore),
             '-storepass:env', 'S40_FIXTURE_PASSWORD', '-file', str(cert_file)], env=env)
        certificate = cert_file.read_bytes()
        if not 1024 < len(certificate) <= 2048 or hashlib.sha256(certificate).hexdigest() == s40.CERT_HASH:
            raise ValueError('Fixture certificate must exercise the enlarged cap and not be the production identity')
        fixtures = {}
        for name, v3 in (('v2-only', False), ('v2-v3', True)):
            apk = work / (name + '.apk')
            run([str(signer), 'sign', '--ks', str(keystore), '--ks-key-alias', 'fixture',
                 '--ks-pass', 'env:S40_FIXTURE_PASSWORD', '--key-pass', 'env:S40_FIXTURE_PASSWORD',
                 '--min-sdk-version', '26', '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'true',
                 '--v3-signing-enabled', 'true' if v3 else 'false', '--v4-signing-enabled', 'false',
                 '--out', str(apk), str(aligned)], env=env)
            output = run([str(signer), 'verify', '--verbose', '--print-certs', '--min-sdk-version', '26', str(apk)], env=env).stdout
            if not re.search(r'Verified using v2 scheme.*: true', output):
                raise ValueError('apksigner did not cryptographically verify fixture v2')
            if not re.search(r'Verified using v3 scheme.*: ' + ('true' if v3 else 'false'), output):
                raise ValueError('apksigner reported an unexpected v3 fixture state')
            if hashlib.sha256(certificate).hexdigest() not in output.lower():
                raise ValueError('apksigner fixture certificate digest differs')
            ids, parsed_cert = inspect_apk(apk)
            # The C policy recognizes only v2 plus optional verity padding.
            # Rule out an unrelated block as the reason it rejects v3.
            if (parsed_cert != certificate or ids.count(V2) != 1 or ids.count(V3) != int(v3) or
                    ids.count(PADDING) > 1 or set(ids) - {V2, V3, PADDING}):
                raise ValueError('Signed fixture block/certificate differs from intended schemes')
            verify_same_zip_payload(aligned, apk)
            if manager_static is not None:
                run([str(align), '-c', '-P', '16', '4', str(apk)])
            fixtures[name] = apk
        parser_source = prepared if prepared is not None else derive_prepared_parser(ksun, work)
        kernel_exe = compile_kernel_probe(parser_source, work)
        daemon_exe = compile_ksud_probe(ksun, work)
        kernel_probe(kernel_exe, fixtures['v2-only'], certificate, True)
        kernel_probe(kernel_exe, fixtures['v2-v3'], certificate, False)
        kernel_probe(kernel_exe, fixtures['v2-only'], certificate, False, digest='0' * 64)
        kernel_probe(kernel_exe, fixtures['v2-only'], certificate, False,
                     digest=s40.CERT_HASH, size=s40.CERT_SIZE)
        ksud_probe(daemon_exe, fixtures['v2-only'], certificate, True)
        ksud_probe(daemon_exe, fixtures['v2-v3'], certificate, False)

        # The host kernel parser reads a certificate; it does not verify the
        # APK's content signature. Android/apksigner must do that separately.
        tampered = bytearray(fixtures['v2-only'].read_bytes())
        with zipfile.ZipFile(fixtures['v2-only']) as z:
            entry = z.getinfo('AndroidManifest.xml')
        offset = entry.header_offset
        if tampered[offset:offset + 4] != b'PK\x03\x04' or entry.compress_size < 4:
            raise ValueError('Unexpected fixture ZIP local entry')
        name_len, extra_len = struct.unpack_from('<HH', tampered, offset + 26)
        content_offset = offset + 30 + name_len + extra_len
        tampered[content_offset + entry.compress_size // 2] ^= 1
        damaged = work / 'tampered-DO-NOT-INSTALL.apk'
        damaged.write_bytes(tampered)
        rejected = run([str(signer), 'verify', '--min-sdk-version', '26', str(damaged)], env=env, expect_success=False)
        if 'DOES NOT VERIFY' not in (rejected.stdout + rejected.stderr):
            raise ValueError('Tampered fixture failed for an unexpected reason')
        kernel_probe(kernel_exe, damaged, certificate, True)
        report = {
            'kind': ('TEMPORARY_SIGNED_MANAGER_PROTOTYPE_HOST_TEST_ONLY' if manager_static is not None
                     else 'TEMPORARY_SIGNING_FIXTURE_HOST_TEST_ONLY'),
            'prepared_kernel_parser_sha256': PREPARED_PARSER_SHA256,
            'upstream_ksud_parser_sha256': KSUD_PARSER_SHA256,
            'fixture_cert_bytes': len(certificate),
            'production_key_used': False,
            'fixture_installed': False,
            'v2_only_and_v2_v3_verified_by_apksigner': True,
            'all_zip_entry_payloads_unchanged_by_signing': True,
            'host_prepared_kernel_parser_accepts_v2_only_with_temporary_cert_pin': True,
            'host_prepared_kernel_parser_rejects_v2_v3': True,
            'host_prepared_kernel_parser_rejects_wrong_cert_hash': True,
            'host_parser_rejects_temporary_cert_with_production_kernel_pin': True,
            'host_ksud_parser_accepts_v2_only': True,
            'host_ksud_parser_rejects_v2_v3': True,
            'modified_fixture_rejected_by_apksigner': True,
            'kernel_cert_parser_does_not_verify_apk_content_signature': True,
            'android_update_or_kernel_runtime_tested': False,
            'flashable_or_release': False,
        }
        if manager_static is not None:
            report.update({
                'input_unsigned_manager_sha256': manager_static['apk_sha256'],
                'pinned_ksud_sha256': manager_static['ksud_sha256'],
                'manager_16k_alignment_preserved': True,
            })
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--prepared', type=Path, help='Full prepared kernel tree')
    source.add_argument('--derive-from-ksun', action='store_true',
                        help='Recreate and pin-check only the host parser from the upstream KSUN source')
    parser.add_argument('--ksun', required=True, type=Path)
    parser.add_argument('--android-sdk', required=True, type=Path)
    parser.add_argument('--unsigned-manager', type=Path,
                        help='Verified unsigned UAPI-5 development prototype; never exported or installed')
    args = parser.parse_args()
    print(json.dumps(generate_and_probe(args.prepared, args.ksun, args.android_sdk, args.unsigned_manager), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, struct.error, zipfile.BadZipFile) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
