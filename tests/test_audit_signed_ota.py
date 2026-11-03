"""Small synthetic archives and ephemeral keys only; no ROM or device access."""
import contextlib
import hashlib
import io
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
sys.path.insert(0, str(ROOT / 'tests'))
import audit_recovery_signature as recovery
import audit_signed_ota as gate
import build_ota_metadata_candidate as ota
from test_audit_recovery_signature import make_cert
from test_build_ota_metadata_candidate import configured, fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_reference(root, certificate):
    original, source = root / 'original.zip', root / 'candidate-02.zip'
    specs, contents = fixture(original)
    cert = certificate.read_bytes()
    rewrite_zip(original, source, {gate.OTACERT: cert})
    specs[gate.OTACERT] = {'name': gate.OTACERT, 'bytes': len(cert),
                            'sha256': hashlib.sha256(cert).hexdigest()}
    out = root / 'reference.zip'
    with configured(source, specs, contents[ota.previous.SCRIPT]), contextlib.redirect_stdout(io.StringIO()):
        ota.build(source, out, root / 'unused-test-lock')
    return out


def rewrite_zip(source, output, replacements=None, additions=()):
    replacements = replacements or {}
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(output, 'w', allowZip64=True) as zout:
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename in replacements:
                data = replacements[info.filename]
            zout.writestr(info, data)
        for name, data in additions:
            zout.writestr(name, data)
    return output


def sign_preserving(source, output, key, cert):
    data = source.read_bytes()
    assert data[-2:] == b'\0\0'
    with tempfile.TemporaryDirectory(prefix='sign-throwaway-', dir=output.parent) as work:
        root = Path(work)
        content, der = root / 'content', root / 'signature.der'
        content.write_bytes(data[:-2])
        subprocess.run(['openssl', 'cms', '-sign', '-binary', '-md', 'sha256',
                        '-in', str(content), '-signer', str(cert), '-inkey', str(key),
                        '-outform', 'DER', '-out', str(der), '-noattr'],
                       check=True, capture_output=True, timeout=30)
        block = der.read_bytes()
        message = b'synthetic test only\0'
        comment_size = len(message) + len(block) + 6
        comment = (message + block + struct.pack('<H', len(block) + 6) + b'\xff\xff'
                   + struct.pack('<H', comment_size))
        output.write_bytes(data[:-2] + struct.pack('<H', comment_size) + comment)
    return output


def checked(ref, signed, cert, pin):
    return gate.audit(ref, signed, cert, sha(ref), sha(signed), pin)


@unittest.skipUnless(recovery.cms and shutil.which('openssl'), 'asn1crypto and OpenSSL required')
class SignedOtaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='synthetic-signed-ota-keys-')
        cls.root = Path(cls.temp.name)
        cls.key, cls.cert, cls.pin = make_cert(cls.root, 'primary')
        cls.other_key, cls.other_cert, cls.other_pin = make_cert(cls.root, 'other')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_package = tempfile.TemporaryDirectory(prefix='synthetic-signed-ota-')
        self.addCleanup(self.temp_package.cleanup)
        self.work = Path(self.temp_package.name)
        self.reference = make_reference(self.work, self.cert)
        self.signed = sign_preserving(self.reference, self.work / 'signed.zip', self.key, self.cert)

    def test_pass_requires_all_checks_and_does_not_modify_inputs(self):
        before = (sha(self.reference), sha(self.signed))
        result = checked(self.reference, self.signed, self.cert, self.pin)
        self.assertIn('not_flash_approval', result['status'])
        self.assertTrue(result['signature']['signature_matches_reference_public_key'])
        self.assertTrue(result['embedded_otacert_public_key_matches_explicit_pin'])
        self.assertEqual(len(result['ota_metadata']['property_files']), 2)
        self.assertTrue(all(item['direct_range_matches'] for item in result['ota_metadata']['property_files']))
        names = {row['name'] for row in result['unchanged_uncompressed_members']}
        self.assertTrue({'super.img', 'boot.img', 'dtbo.img'} <= names)
        self.assertEqual(before, (sha(self.reference), sha(self.signed)))
        self.assertTrue(any('recovery trust' in text for text in result['limitations']))

    def test_signature_valid_but_stale_final_offsets_are_rejected(self):
        with zipfile.ZipFile(self.reference) as z:
            text, pb = z.read(ota.METADATA), z.read(ota.METADATA_PB)
        props, _ = ota.property_values(text, pb)
        values = {key: 'metadata:1:1,metadata.pb:1:1'.ljust(len(value)) for key, value in props.items()}
        stale = rewrite_zip(self.reference, self.work / 'stale.zip', {
            ota.METADATA: ota.rewrite_legacy(text, values),
            ota.METADATA_PB: ota.rewrite_proto(pb, values),
        })
        signed = sign_preserving(stale, self.work / 'stale-signed.zip', self.key, self.cert)
        self.assertTrue(recovery.audit(signed, self.cert, sha(signed), self.pin)['signature_matches_reference_public_key'])
        with self.assertRaisesRegex(gate.SignedOtaError, 'offset/size'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_changed_nonproperty_metadata_is_rejected(self):
        with zipfile.ZipFile(self.reference) as z:
            text = z.read(ota.METADATA)
        self.assertIn(b'post-sdk-level=35', text)
        altered = rewrite_zip(self.reference, self.work / 'nonproperty.zip', {
            ota.METADATA: text.replace(b'post-sdk-level=35', b'post-sdk-level=36'),
        })
        signed = sign_preserving(altered, self.work / 'nonproperty-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'non-property legacy'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_changed_nonproperty_protobuf_is_rejected(self):
        with zipfile.ZipFile(self.reference) as z:
            pb = z.read(ota.METADATA_PB)
        message = ota.parse_proto(pb)
        message.postcondition.sdk_level = '36'
        altered = rewrite_zip(self.reference, self.work / 'nonproperty-pb.zip', {
            ota.METADATA_PB: message.SerializeToString(deterministic=True),
        })
        signed = sign_preserving(altered, self.work / 'nonproperty-pb-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'non-property protobuf'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_changed_property_token_order_is_rejected(self):
        with zipfile.ZipFile(self.reference) as z:
            text, pb = z.read(ota.METADATA), z.read(ota.METADATA_PB)
        props, _ = ota.property_values(text, pb)
        values = {}
        for name, value in props.items():
            reverse = ','.join(reversed(value.strip().split(',')))
            values[name] = reverse.ljust(len(value))
        altered = rewrite_zip(self.reference, self.work / 'reordered.zip', {
            ota.METADATA: ota.rewrite_legacy(text, values),
            ota.METADATA_PB: ota.rewrite_proto(pb, values),
        })
        signed = sign_preserving(altered, self.work / 'reordered-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'property keys or referenced member order'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_compressed_property_file_is_rejected(self):
        altered = self.work / 'compressed.zip'
        with zipfile.ZipFile(self.reference) as zin, zipfile.ZipFile(altered, 'w') as zout:
            for info in zin.infolist():
                data = zin.read(info)
                if info.filename == ota.METADATA:
                    info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(info, data)
        signed = sign_preserving(altered, self.work / 'compressed-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'not directly readable STORED'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_synthetic_small_zip64_local_and_central_headers(self):
        work = self.work / 'zip64'
        work.mkdir()
        with mock.patch.object(zipfile, 'ZIP64_LIMIT', 128):
            reference = make_reference(work, self.cert)
        signed = sign_preserving(reference, work / 'signed-zip64.zip', self.key, self.cert)
        result = checked(reference, signed, self.cert, self.pin)
        self.assertIn('not_flash_approval', result['status'])
        self.assertEqual(len(result['ota_metadata']['property_files']), 2)

    def test_changed_image_is_rejected_even_if_signature_is_valid(self):
        altered = rewrite_zip(self.reference, self.work / 'changed.zip', {'boot.img': b'not boot'})
        signed = sign_preserving(altered, self.work / 'changed-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'member (length|content) changed'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_added_member_is_rejected(self):
        altered = rewrite_zip(self.reference, self.work / 'extra.zip', additions=[('extra.bin', b'extra')])
        signed = sign_preserving(altered, self.work / 'extra-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'member set changed'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_embedded_cert_does_not_override_reference_key(self):
        altered = rewrite_zip(self.reference, self.work / 'other-cert.zip', {gate.OTACERT: self.other_cert.read_bytes()})
        signed = sign_preserving(altered, self.work / 'other-cert-signed.zip', self.key, self.cert)
        with self.assertRaisesRegex(gate.SignedOtaError, 'otacert public key differs'):
            checked(self.reference, signed, self.cert, self.pin)

    def test_tamper_wrong_archive_pin_and_wrong_certificate_fail(self):
        with self.assertRaisesRegex(gate.SignedOtaError, 'Reference ZIP SHA-256'):
            gate.audit(self.reference, self.signed, self.cert, '0' * 64, sha(self.signed), self.pin)
        with self.assertRaises(recovery.RecoverySignatureError):
            gate.audit(self.reference, self.signed, self.other_cert, sha(self.reference), sha(self.signed), self.other_pin)
        tampered = self.work / 'tampered.zip'
        data = bytearray(self.signed.read_bytes())
        data[45] ^= 1
        tampered.write_bytes(data)
        with self.assertRaises(recovery.RecoverySignatureError):
            checked(self.reference, tampered, self.cert, self.pin)

    def test_duplicate_and_unsafe_names_fail_closed(self):
        for name in ('boot.img', '../escape'):
            with self.subTest(name=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                altered = rewrite_zip(self.reference, self.work / 'bad-names.zip', additions=[(name, b'x')])
                signed = sign_preserving(altered, self.work / 'bad-names-signed.zip', self.key, self.cert)
                with self.assertRaisesRegex(gate.SignedOtaError, 'Unsafe, truncated, or duplicate'):
                    checked(self.reference, signed, self.cert, self.pin)

    def test_detects_archive_change_during_checks(self):
        original = gate._metadata
        def changed(*args):
            result = original(*args)
            with self.signed.open('ab') as f:
                f.write(b'x')
            return result
        with mock.patch.object(gate, '_metadata', side_effect=changed):
            with self.assertRaisesRegex(gate.guard.AuditError, 'changed or was replaced'):
                checked(self.reference, self.signed, self.cert, self.pin)

    def test_archive_rename_between_signature_and_content_check_fails_hash(self):
        original = recovery.audit
        def swapped(*args, **kwargs):
            result = original(*args, **kwargs)
            self.signed.write_bytes(self.reference.read_bytes())
            return result
        with mock.patch.object(recovery, 'audit', side_effect=swapped):
            with self.assertRaisesRegex(gate.SignedOtaError, 'Signed ZIP SHA-256'):
                gate.audit(self.reference, self.signed, self.cert, sha(self.reference), sha(self.signed), self.pin)


if __name__ == '__main__':
    unittest.main()
