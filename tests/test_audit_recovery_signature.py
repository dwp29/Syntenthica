"""All keys and ZIPs below are synthetic, generated in a temporary directory."""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_recovery_signature as audit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(*args, cwd):
    return subprocess.run(list(args), cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=30)


def make_cert(root, name, algorithm='rsa:2048'):
    key, cert = root / f'{name}.key', root / f'{name}.pem'
    args = ['openssl', 'req', '-x509', '-newkey', algorithm, '-sha256', '-nodes',
            '-keyout', str(key), '-out', str(cert), '-subj', f'/CN={name}', '-days', '1']
    if algorithm == 'ec':
        args.extend(['-pkeyopt', 'ec_paramgen_curve:prime256v1'])
    run(*args, cwd=root)
    os.chmod(key, 0o600)
    _, spki, _, _ = audit._certificate(cert)
    return key, cert, sha(spki)


def make_signed(root, key, cert, *, noattr=True, digest='sha256', zip64=False):
    unsigned = root / 'unsigned.zip'
    package = root / 'signed.zip'
    with mock.patch.object(zipfile, 'ZIP64_LIMIT', 128 if zip64 else zipfile.ZIP64_LIMIT):
        with zipfile.ZipFile(unsigned, 'w', allowZip64=True) as z:
            z.writestr('payload.bin', bytes(range(256)))
            z.writestr('metadata', b'test only')
    data = unsigned.read_bytes()
    assert data[-2:] == b'\x00\x00'
    content = root / 'content.bin'
    der = root / 'signature.der'
    content.write_bytes(data[:-2])
    args = ['openssl', 'cms', '-sign', '-binary', '-md', digest,
            '-in', str(content), '-signer', str(cert), '-inkey', str(key),
            '-outform', 'DER', '-out', str(der)]
    if noattr:
        args.append('-noattr')
    run(*args, cwd=root)
    block = der.read_bytes()
    message = b'signed by synthetic test\0'
    comment_size = len(message) + len(block) + 6
    signature_start = len(block) + 6
    comment = message + block + struct.pack('<H', signature_start) + b'\xff\xff' + struct.pack('<H', comment_size)
    package.write_bytes(data[:-2] + struct.pack('<H', comment_size) + comment)
    return package


def checked(path, cert, key_pin):
    return audit.audit(path, cert, sha(path.read_bytes()), key_pin)


@unittest.skipUnless(audit.cms and shutil.which('openssl'), 'asn1crypto and OpenSSL required')
class RecoverySignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='synthetic-recovery-signature-')
        cls.root = Path(cls.workspace.name)
        cls.key, cls.cert, cls.key_pin = make_cert(cls.root, 'first')
        cls.other_key, cls.other_cert, cls.other_pin = make_cert(cls.root, 'other')
        cls.ec_key, cls.ec_cert, cls.ec_pin = make_cert(cls.root, 'ec', 'ec')

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-package-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_rsa_signature_matches_explicit_reference_but_not_device_trust(self):
        p = make_signed(self.work, self.key, self.cert)
        before = sha(p.read_bytes())
        result = checked(p, self.cert, self.key_pin)
        self.assertTrue(result['signature_matches_reference_public_key'])
        self.assertFalse(result['recovery_certificate_trust_or_settings_verified'])
        self.assertFalse(result['target_recovery_implementation_executed'])
        self.assertFalse(result['zip_members_or_ota_offsets_validated'])
        self.assertFalse(result['device_avb_rollback_or_boot_verified'])
        self.assertEqual(result['package_sha256'], before)
        self.assertEqual(result['reference_public_key_spki_sha256'], self.key_pin)
        self.assertEqual(result['public_key_type'], 'rsa')
        self.assertEqual(before, sha(p.read_bytes()))
        with zipfile.ZipFile(p) as z:
            self.assertEqual(z.read('metadata'), b'test only')

    def test_ec_and_zip64_synthetic_signatures(self):
        for zip64 in (False, True):
            p = make_signed(self.work, self.ec_key, self.ec_cert, zip64=zip64)
            result = checked(p, self.ec_cert, self.ec_pin)
            self.assertEqual(result['public_key_type'], 'ec')
            self.assertEqual(result['public_key_bits'], 256)
            self.assertTrue(result['signature_matches_reference_public_key'])

    def test_unsigned_and_malformed_footer_are_refused(self):
        p = self.work / 'unsigned.zip'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('a', 'b')
        with self.assertRaises(audit.RecoverySignatureError):
            checked(p, self.cert, self.key_pin)
        p = make_signed(self.work, self.key, self.cert)
        data = bytearray(p.read_bytes())
        data[-4] = 0
        p.write_bytes(data)
        with self.assertRaises(audit.RecoverySignatureError):
            checked(p, self.cert, self.key_pin)

    def test_tamper_rejected_even_when_new_archive_pin_is_supplied(self):
        p = make_signed(self.work, self.key, self.cert)
        data = bytearray(p.read_bytes())
        data[32] ^= 1
        p.write_bytes(data)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'does not match the specified public key'):
            checked(p, self.cert, self.key_pin)

    def test_wrong_reference_key_and_pins_are_refused(self):
        p = make_signed(self.work, self.key, self.cert)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'independent pin'):
            audit.audit(p, self.cert, sha(p.read_bytes()), '0' * 64)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'Package SHA-256'):
            audit.audit(p, self.cert, '0' * 64, self.key_pin)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'does not match the specified public key'):
            checked(p, self.other_cert, self.other_pin)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'lowercase SHA-256'):
            audit.audit(p, self.cert, 'not-a-digest', self.key_pin)

    def test_embedded_certificate_does_not_replace_explicit_reference(self):
        p = make_signed(self.work, self.key, self.cert)
        with p.open('rb') as f:
            _, der, _ = audit._footer(f, p.stat().st_size)
        signed = audit.cms.ContentInfo.load(der)['content']
        self.assertGreaterEqual(len(signed['certificates']), 1)
        # Embedded signer cert is ignored; the different explicitly pinned key must fail.
        with self.assertRaises(audit.RecoverySignatureError):
            checked(p, self.other_cert, self.other_pin)

    def test_signed_attributes_and_sha1_are_refused_not_called_valid(self):
        p = make_signed(self.work, self.key, self.cert, noattr=False)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'Signed attributes'):
            checked(p, self.cert, self.key_pin)
        p = make_signed(self.work, self.key, self.cert, digest='sha1')
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'SHA-256'):
            checked(p, self.cert, self.key_pin)

    def test_spurious_eocd_is_refused(self):
        p = make_signed(self.work, self.key, self.cert)
        data = bytearray(p.read_bytes())
        start = data.index(b'signed by synthetic test')
        data[start:start + 4] = audit.EOCD
        p.write_bytes(data)
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'Ambiguous'):
            checked(p, self.cert, self.key_pin)

    def test_small_rsa_and_sha1_certificate_are_refused(self):
        for bits, digest, expected in ((1024, 'sha256', 'RSA public key'), (2048, 'sha1', 'must identify SHA-256')):
            key, cert = self.work / f'{bits}-{digest}.key', self.work / f'{bits}-{digest}.pem'
            run('openssl', 'req', '-x509', '-newkey', f'rsa:{bits}', '-' + digest, '-nodes',
                '-keyout', str(key), '-out', str(cert), '-subj', '/CN=fixture', '-days', '1', cwd=self.work)
            with self.assertRaisesRegex(audit.RecoverySignatureError, expected):
                audit._certificate(cert)

    def test_symlink_and_multi_certificate_inputs_are_refused(self):
        p = make_signed(self.work, self.key, self.cert)
        link = self.work / 'link.zip'
        link.symlink_to(p)
        with self.assertRaises(audit.RecoverySignatureError):
            audit.audit(link, self.cert, sha(p.read_bytes()), self.key_pin)
        certs = self.work / 'two.pem'
        certs.write_bytes(self.cert.read_bytes() + self.other_cert.read_bytes())
        with self.assertRaisesRegex(audit.RecoverySignatureError, 'exactly one'):
            audit.audit(p, certs, sha(p.read_bytes()), self.key_pin)

    def test_candidate_change_is_detected_even_after_a_valid_signature(self):
        p = make_signed(self.work, self.key, self.cert)
        actual_verify = audit._verify_with_openssl
        def mutate(*args):
            result = actual_verify(*args)
            with p.open('ab') as f:
                f.write(b'x')
            return result
        with mock.patch.object(audit, '_verify_with_openssl', side_effect=mutate):
            with self.assertRaisesRegex(audit.RecoverySignatureError, 'changed during'):
                checked(p, self.cert, self.key_pin)

    def test_no_metadata_or_device_verdict_in_result(self):
        p = make_signed(self.work, self.key, self.cert)
        result = checked(p, self.cert, self.key_pin)
        self.assertEqual(result['status'], 'signature_matches_explicit_reference_key_only_not_flash_approval')
        self.assertTrue(any('not the installed recovery verifier' in x for x in result['limitations']))
        self.assertTrue(any('No private key' in x for x in result['limitations']))


if __name__ == '__main__':
    unittest.main()
