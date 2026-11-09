"""Host-only tests for throwaway APK signing-policy probes."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import probe_s40_apk_signing as probe
import test_s40_apk_guard as guard


class SigningFixtureHelperTests(unittest.TestCase):
    def test_reference_has_real_v2_certificate_and_v3_block(self):
        ids, cert = probe.inspect_apk(ROOT / 'release/Synthetica-2.0.apk')
        self.assertIn(probe.V2, ids)
        self.assertIn(probe.V3, ids)
        self.assertEqual(len(cert), 1381)
        self.assertEqual(hashlib.sha256(cert).hexdigest(), probe.s40.CERT_HASH)

    def test_broken_signing_pair_and_symlink_are_rejected(self):
        data = bytearray((ROOT / 'release/Synthetica-2.0.apk').read_bytes())
        _, _, head, _ = guard.apk_parts(data)
        struct.pack_into('<Q', data, head + 8, (1 << 64) - 1)
        with tempfile.TemporaryDirectory() as temp:
            apk = Path(temp) / 'bad.apk'
            apk.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'pair size'):
                probe.inspect_apk(apk)
            link = Path(temp) / 'link.apk'
            link.symlink_to(apk)
            with self.assertRaisesRegex(ValueError, 'symlinked'):
                probe.inspect_apk(link)

    def test_failure_exit_expectations_are_explicit(self):
        probe.run(['/bin/true'])
        probe.run(['/bin/false'], expect_success=False)
        with self.assertRaisesRegex(RuntimeError, 'returned'):
            probe.run(['/bin/false'])

    def test_source_hash_and_symlink_are_required(self):
        with tempfile.TemporaryDirectory(prefix='s40-source-guard-') as temp:
            source = Path(temp) / 'parser.c'
            source.write_text('safe fixture\n')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(probe.checked_source(source, digest), 'safe fixture\n')
            source.write_text('modified\n')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                probe.checked_source(source, digest)
            link = Path(temp) / 'link.c'
            link.symlink_to(source)
            with self.assertRaisesRegex(ValueError, 'symlinked'):
                probe.checked_source(link, digest)

    def test_derived_parser_rejects_unpinned_upstream(self):
        with tempfile.TemporaryDirectory(prefix='s40-source-derive-bad-') as temp:
            root = Path(temp)
            upstream = root / 'ksun/kernel/manager/apk_sign.c'
            upstream.parent.mkdir(parents=True)
            upstream.write_text('not the pinned source')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                probe.derive_prepared_parser(root / 'ksun', root)
            self.assertFalse((root / 'derived-prepared-parser').exists())

    def test_signing_payload_comparison_detects_changed_entries(self):
        with tempfile.TemporaryDirectory(prefix='s40-zip-payload-test-') as temp:
            before, after = Path(temp) / 'before.zip', Path(temp) / 'after.zip'
            def write(path, files):
                with zipfile.ZipFile(path, 'w') as archive:
                    for name, data in files:
                        archive.writestr(name, data)
            files = [('AndroidManifest.xml', b'original'), ('classes.dex', b'code')]
            write(before, files)
            write(after, files)
            probe.verify_same_zip_payload(before, after)
            write(after, [('AndroidManifest.xml', b'modified'), ('classes.dex', b'code')])
            with self.assertRaisesRegex(ValueError, 'changed APK payload'):
                probe.verify_same_zip_payload(before, after)
            write(after, files + [('extra', b'x')])
            with self.assertRaisesRegex(ValueError, 'entry set'):
                probe.verify_same_zip_payload(before, after)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                write(after, files + [('classes.dex', b'code')])
            with self.assertRaisesRegex(ValueError, 'entry set'):
                probe.verify_same_zip_payload(before, after)

    def test_derived_parser_matches_real_prepared_source(self):
        ksun = os.environ.get('S40_TEST_KSUN')
        if not ksun:
            self.skipTest('S40_TEST_KSUN required')
        with tempfile.TemporaryDirectory(prefix='s40-source-derive-') as temp:
            root = probe.derive_prepared_parser(Path(ksun), Path(temp))
            signer = root / 'drivers/kernelsu/manager/apk_sign.c'
            self.assertEqual(hashlib.sha256(signer.read_bytes()).hexdigest(), probe.PREPARED_PARSER_SHA256)
            prepared = os.environ.get('S40_TEST_PREPARED')
            if prepared:
                self.assertEqual(signer.read_bytes(),
                                 (Path(prepared) / 'drivers/kernelsu/manager/apk_sign.c').read_bytes())


@unittest.skipUnless(shutil.which('gcc'), 'gcc required')
class RealPreparedParserTests(unittest.TestCase):
    def test_host_parser_uses_real_sha256_on_reference_layout(self):
        prepared = os.environ.get('S40_TEST_PREPARED')
        if not prepared:
            self.skipTest('S40_TEST_PREPARED required')
        data = (ROOT / 'release/Synthetica-2.0.apk').read_bytes()
        _, _, _, pairs = guard.apk_parts(data)
        v2 = [value for kind, value in pairs if kind == probe.V2]
        self.assertEqual(len(v2), 1)
        # This altered fixture is cryptographically invalid; never install it.
        v2_only = guard.fixture_with_pairs(data, v2)
        _, cert = probe.inspect_apk(ROOT / 'release/Synthetica-2.0.apk')
        with tempfile.TemporaryDirectory(prefix='s40-real-sha-test-') as temp:
            work = Path(temp)
            altered = work / 'NOT-A-VALID-APK'
            altered.write_bytes(v2_only)
            exe = probe.compile_kernel_probe(Path(prepared), work)
            probe.kernel_probe(exe, altered, cert, True)
            probe.kernel_probe(exe, altered, cert, False, digest='0' * 64)
            probe.kernel_probe(exe, altered, cert, False, size=len(cert) + 1)
            probe.kernel_probe(exe, ROOT / 'release/Synthetica-2.0.apk', cert, False)


@unittest.skipUnless(shutil.which('rustc'), 'rustc required')
class RealKsudParserTests(unittest.TestCase):
    def test_host_ksud_rejects_v3_and_extracts_v2(self):
        ksun = os.environ.get('S40_TEST_KSUN')
        if not ksun:
            self.skipTest('S40_TEST_KSUN required')
        data = (ROOT / 'release/Synthetica-2.0.apk').read_bytes()
        _, _, _, pairs = guard.apk_parts(data)
        v2 = [value for kind, value in pairs if kind == probe.V2]
        self.assertEqual(len(v2), 1)
        # Structural test only: removing the original v3 block invalidates the
        # APK's signature and is never evidence that it can be installed.
        altered_data = guard.fixture_with_pairs(data, v2)
        _, cert = probe.inspect_apk(ROOT / 'release/Synthetica-2.0.apk')
        with tempfile.TemporaryDirectory(prefix='s40-real-ksud-test-') as temp:
            work = Path(temp)
            altered = work / 'NOT-A-VALID-APK'
            altered.write_bytes(altered_data)
            exe = probe.compile_ksud_probe(Path(ksun), work)
            probe.ksud_probe(exe, altered, cert, True)
            probe.ksud_probe(exe, ROOT / 'release/Synthetica-2.0.apk', cert, False)
            with self.assertRaisesRegex(RuntimeError, 'returned'):
                probe.ksud_probe(exe, altered, b'incorrect certificate', True)


if __name__ == '__main__':
    unittest.main()
