import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('joyeuse_signed_modules', ROOT / 'synthetica-project/build_joyeuse_signed_modules.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
FRAGMENT = ROOT / 'build-kit/ci/rollercoaster/profiles/joyeuse-builtins-experimental.config'


class SignedModulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        p = Path(cls.temp.name)
        def run(*args):
            subprocess.run(args, cwd=p, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run('openssl', 'req', '-new', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-subj', '/CN=Joyetest temporary key/', '-keyout', 'key.pem', '-out', 'cert.pem')
        run('openssl', 'x509', '-in', 'cert.pem', '-outform', 'DER', '-out', 'cert.der')
        asm = '''.section .modinfo,"a"
.asciz "name=rmnet_perf"
.asciz "vermagic=4.14.357-test SMP preempt mod_unload modversions aarch64"
.asciz "depends="
.section __versions,"a"
.quad 0x12345678
.asciz "module_layout"
.zero 42
.quad 0x00abcdef
.asciz "some_symbol"
.zero 44
'''
        (p / 'module.s').write_text(asm)
        run('gcc', '-c', 'module.s', '-o', 'module.o')
        payload = bytearray((p / 'module.o').read_bytes())
        # Test fixture: use a synthetic ET_REL object with the ARM64 header.
        # We never execute it or claim its machine code targets the device.
        struct.pack_into('<H', payload, 18, 183)
        (p / 'module.o').write_bytes(payload)
        run('openssl', 'cms', '-sign', '-binary', '-md', 'sha512', '-noattr', '-nosmimecap', '-nocerts',
            '-in', 'module.o', '-signer', 'cert.pem', '-inkey', 'key.pem', '-outform', 'DER', '-out', 'sig.der')
        signature = (p / 'sig.der').read_bytes()
        cls.payload = bytes(payload)
        cls.signed = cls.payload + signature + struct.pack('>8BI', 0, 0, 2, 0, 0, 0, 0, 0, len(signature)) + mod.SIG_MAGIC
        cls.cert = (p / 'cert.der').read_bytes()
        cls.kernel = b'synthetic-kernel' + cls.cert + b'end'
        cls.symvers = {'module_layout': 0x12345678, 'some_symbol': 0x00abcdef}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def verify(self, data=None, **overrides):
        kwargs = dict(name='rmnet_perf', release='4.14.357-test', certificate_der=self.cert,
                      raw_kernel=self.kernel, symvers=self.symvers)
        kwargs.update(overrides)
        return mod.verify_module(self.signed if data is None else data, **kwargs)

    def test_preparation_builds_and_signs_modules_without_changing_original(self):
        before = {name: mod.base.digest(ROOT / 'build-kit' / name) for name in mod.base.PINNED_INPUTS}
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'kit'
            mod.prepare(ROOT / 'build-kit', target, FRAGMENT)
            script = (target / 'ci/rollercoaster/build-rollercoaster.sh').read_text()
            self.assertIn('"${MO[@]}" modules\n', script)
            self.assertIn('INSTALL_MOD_PATH="$OUT/joyeuse-modules" modules_install', script)
            for sym, value in mod.CONFIG.items():
                self.assertIn(f"CONFIG_{sym}={value}", script)
            self.assertNotIn('# --- kemas AnyKernel3', script)
            self.assertIn('CONFIG_MSM_11AD=m', (target / 'ci/rollercoaster/profiles/synthetica.config').read_text())
        self.assertEqual(before, {name: mod.base.digest(ROOT / 'build-kit' / name) for name in mod.base.PINNED_INPUTS})

    def test_real_signature_and_matching_versions_are_checked(self):
        result = self.verify()
        self.assertEqual(result['version_records_verified'], 2)
        self.assertTrue(result['signature_math_verified_with_embedded_certificate'])
        self.assertEqual(result['dependencies'], [])

    def test_rejects_mismatch_tampering_and_missing_signature(self):
        changed = bytearray(self.signed); changed[100] ^= 1
        for case, args in (
            ('altered', {'data': bytes(changed)}),
            ('unsigned', {'data': self.payload}),
            ('wrong certificate', {'raw_kernel': b'not the certificate'}),
            ('different CRC', {'symvers': {'module_layout': 0x12345678, 'some_symbol': 0}}),
            ('missing CRC', {'symvers': {'module_layout': 0x12345678}}),
            ('different release', {'release': 'wrong'}),
            ('different name', {'name': 'rmnet_shs'}),
        ):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.verify(**args)

    def test_rejects_duplicate_and_malformed_symbol_versions(self):
        valid = struct.pack('<Q', 1) + b'module_layout\0' + bytes(42)
        self.assertEqual(mod.version_records(valid), {'module_layout': 1})
        for bad in (valid + valid, valid[:-1], bytes(64)):
            with self.subTest(bad=bad), self.assertRaises(ValueError): mod.version_records(bad)
        with self.assertRaises(ValueError): mod.symvers_records('0x1234 x vmlinux\n')
        with self.assertRaises(ValueError):
            mod.symvers_records('0x1 module_layout vmlinux\n0x2 module_layout vmlinux\n')

    def test_finish_rejects_missing_required_network_module(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / '.config').write_text('CONFIG_RMNET_PERF=m\nCONFIG_RMNET_SHS=m\n# CONFIG_MSM_11AD is not set\n')
            with self.assertRaisesRegex(ValueError, 'MSM_11AD'):
                mod.finish(out, out, ROOT/'artifacts/generated.config.txt', out/'result')


if __name__ == '__main__': unittest.main()
