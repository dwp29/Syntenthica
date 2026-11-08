"""Host-side safety gates only; no ROM, physical boot or flash is exercised."""
import ast
import gzip
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('synthetica32_build_test', ROOT / 'build-kit/scripts/build_synthetica32.py')
s32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s32)
BASE = ROOT / 'artifacts/generated.config.txt'
SYMVERS = ROOT / 'artifacts/synthetica-3.0/Module.symvers.txt'
MANAGER = ROOT / 'build-kit/artifacts/manager/MANAGER.json'


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = s32.base.verified_baseline(BASE)
        cls.new = cls.old.replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                  'CONFIG_LOCALVERSION="-synthetica-3.2"')

    def test_exact_baseline_and_32_release(self):
        change = s32.check_config(self.old, self.new)
        self.assertEqual(change, {'LOCALVERSION': {'2.0': '"-Synthetica-2.0"',
                                                   '3.2': '"-synthetica-3.2"'}})
        self.assertGreater(len(s32.base.read_config(self.new)), 4900)

    def test_required_security_and_root_cannot_change(self):
        for symbol in ('MODULE_SIG_FORCE', 'MODULE_SIG', 'MODVERSIONS', 'SECURITY_SELINUX', 'DM_VERITY',
                       'KSU', 'KSU_MANUAL_HOOK', 'KSU_SUSFS', 'NOMOUNT'):
            bad = self.new.replace(f'CONFIG_{symbol}=y', f'# CONFIG_{symbol} is not set')
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                self.assertNotEqual(bad, self.new)
                s32.check_config(self.old, bad)

    def test_force_loading_experimental_features_and_duplicates_are_rejected(self):
        bad_configs = [self.new.replace('# CONFIG_MODULE_FORCE_LOAD is not set', 'CONFIG_MODULE_FORCE_LOAD=y'),
                       self.new + '\nCONFIG_LRU_GEN=y\n', self.new + '\nCONFIG_UCLAMP_TASK=y\n',
                       self.new + '\nCONFIG_UCLAMP_TASK_GROUP=y\n', self.new + '\nCONFIG_LOCALVERSION="-synthetica-3.2"\n',
                       self.new.replace('CONFIG_LOCALVERSION="-synthetica-3.2"', 'CONFIG_LOCALVERSION="-synthetica-3.1"')]
        for bad in bad_configs:
            with self.subTest(bad=bad[-100:]), self.assertRaises(ValueError):
                s32.check_config(self.old, bad)

    def test_release_and_identity_strings_are_checked(self):
        cfg = self.new.encode()
        mgr = {'package': 'test.manager', 'cert_sha256': 'abc123'}
        image = (b'Linux version ' + s32.RELEASE.encode() + b' build\nKernelSU\0test.manager\0abc123\0'
                 + b'IKCFG_ST' + gzip.compress(cfg) + b'IKCFG_ED')
        s32.verify_image(image, cfg, mgr)
        for bad, error in ((image.replace(b'synthetica-3.2', b'synthetica-3.1'), '3.2'),
                           (image.replace(b'test.manager', b'other-------'), 'manager'),
                           (image.replace(b'KernelSU', b'--------'), 'KernelSU')):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                s32.verify_image(bad, cfg, mgr)


class ABITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = SYMVERS.read_text().splitlines()

    def test_all_exported_records_and_module_layout(self):
        result = s32.compare_symvers(SYMVERS, SYMVERS)
        self.assertEqual(result['exported_records_compared'], 12236)
        self.assertEqual(result['builtin_records_compared'], 12227)
        self.assertEqual(result['module_records_compared'], 9)
        self.assertEqual(result['module_layout_crc'], '0x08efcbb0')
        self.assertEqual(result['missing_added_or_changed'], 0)
        self.assertEqual(result['canonical_records_sha256'],
                         '9abff338556ae6430e5c54b92d0fb548abee9f28c15e2d2154cf21ef281c8439')

    def run_generated(self, lines, *, okay=False):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'new.symvers'
            p.write_text('\n'.join(lines) + '\n')
            if okay:
                return s32.compare_symvers(SYMVERS, p)
            with self.assertRaises(ValueError):
                s32.compare_symvers(SYMVERS, p)

    def test_unrelated_export_changes_are_rejected_not_just_module_layout(self):
        # The first export is not module_layout; exercise every compared field.
        crc, name, owner, kind = self.lines[0].split()
        for replacement in (f'0xffffffff\t{name}\t{owner}\t{kind}',
                            f'{crc}\t{name}\tdrivers/other\t{kind}',
                            f'{crc}\t{name}\t{owner}\tEXPORT_SYMBOL_GPL',
                            f'{crc}\tother_new_name\t{owner}\t{kind}',
                            self.lines[0] + '\n' + self.lines[0],
                            '0x00000000\t' + name + '\t' + owner + '\t' + kind):
            with self.subTest(replacement=replacement[:50]):
                self.run_generated([replacement] + self.lines[1:])
        self.run_generated(self.lines[1:])
        self.run_generated(self.lines + ['0xffffffff\tnew_export\tvmlinux\tEXPORT_SYMBOL'])

    def test_order_is_irrelevant_but_invalid_records_are_not(self):
        self.run_generated(list(reversed(self.lines)), okay=True)
        for line in ('bogus', '0x1 bad vmlinux EXPORT_SYMBOL', '0x12345678 bad-name vmlinux EXPORT_SYMBOL',
                     '0x12345678 name vmlinux NOT_EXPORT'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                s32.parse_symvers(line)

    def test_reference_hash_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'fake'
            p.write_text(SYMVERS.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                s32.compare_symvers(p, SYMVERS)
            p.unlink()
            p.symlink_to(SYMVERS)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                s32.compare_symvers(p, SYMVERS)
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                s32.compare_symvers(SYMVERS, p)


class PrepareTests(unittest.TestCase):
    def test_isolated_pinned_recipe_retains_guards_and_has_no_installer(self):
        source = ROOT / 'build-kit'
        before = {name: s32.base.digest(source / name) for name in s32.base.PINNED_INPUTS}
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'kit'
            s32.prepare(source, dest, BASE)
            for name, sha in before.items():
                self.assertEqual(s32.base.digest(source / name), sha)
            builder = dest / 'ci/rollercoaster/build-rollercoaster.sh'
            driver = dest / 'scripts/build_chronicle_base.py'
            text = builder.read_text()
            self.assertIn('3.2 must keep the whole 2.0 config', text)
            self.assertIn('check-config --baseline "$S3_BASELINE"', text)
            self.assertIn('foreign vermagic bypass found', text)
            self.assertIn('make -j"$JOBS" "${MO[@]}" modules\n', text)
            self.assertIn('INSTALL_MOD_PATH="$OUT/synthetica3-modules" modules_install', text)
            self.assertNotIn('# --- kemas AnyKernel3 ', text)
            self.assertFalse((dest / 'ci/rollercoaster/patches/port-allow-foreign-vermagic.patch').exists())
            subprocess.run(['bash', '-n', str(builder)], check=True)
            ast.parse(driver.read_text())
            self.assertIn('Image compiled; 3.2 verification still required', driver.read_text())
            with self.assertRaisesRegex(ValueError, 'existing'):
                s32.prepare(source, dest, BASE)


class FinishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_temp = tempfile.TemporaryDirectory()
        p = Path(cls.cert_temp.name)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=Synthetic Test Only', '-keyout', str(p/'key.pem'),
                        '-out', str(p/'cert.pem')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.cert = subprocess.run(['openssl', 'x509', '-in', str(p/'cert.pem'), '-outform', 'DER'],
                                  check=True, stdout=subprocess.PIPE).stdout

    @classmethod
    def tearDownClass(cls):
        cls.cert_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.kit, self.out, self.result, self.tc = (root/n for n in ('kit', 'out', 'result', 'tc'))
        (self.kit/'artifacts/manager').mkdir(parents=True)
        (self.out/'certs').mkdir(parents=True)
        self.tc.mkdir()
        for name, version in (('clang', 'Ubuntu clang version 18.1.3'), ('ld.lld', 'Ubuntu LLD 18.1.3')):
            p = self.tc/name
            p.write_text('#!/bin/sh\necho "' + version + '"\n')
            p.chmod(0o700)
        shutil.copyfile(MANAGER, self.kit/'artifacts/manager/MANAGER.json')
        self.config = BASE.read_text().replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                               'CONFIG_LOCALVERSION="-synthetica-3.2"').encode()
        (self.out/'.config').write_bytes(self.config)
        (self.kit/'artifacts/generated.config.txt').write_bytes(self.config)
        mgr = json.loads(MANAGER.read_text())
        self.raw = (b'Linux version ' + s32.RELEASE.encode() + b' test\nKernelSU\0' + mgr['package'].encode()
                    + b'\0' + mgr['cert_sha256'].encode() + b'\0IKCFG_ST' + gzip.compress(self.config)
                    + b'IKCFG_ED\0' + self.cert)
        (self.kit/'artifacts/Image.gz').write_bytes(gzip.compress(self.raw))
        shutil.copyfile(SYMVERS, self.out/'Module.symvers')
        (self.out/'System.map').write_text('00000000 T example\n')
        (self.out/'certs/signing_key.x509').write_bytes(self.cert)

    def finish(self):
        names = ('tcp_bic', 'tcp_westwood', 'tcp_htcp', 'gspca_main', 'rmnet_perf', 'rmnet_shs')
        modules = {name: (b'synthetic ' + name.encode(), {'name': name}) for name in names}
        with mock.patch.object(s32.base, 'MIN_IMAGE_BYTES', 0), \
             mock.patch.object(s32.base, 'collect_module_evidence', return_value=modules):
            s32.finish(self.kit, self.out, BASE, ROOT/'artifacts/Image.gz', SYMVERS, self.tc, self.result)

    def test_finish_emits_only_reviewable_files_and_valid_checksums(self):
        self.finish()
        status = json.loads((self.result/'STATUS.json').read_text())
        self.assertEqual(status['status'], 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED')
        self.assertEqual(status['uname_release'], s32.RELEASE)
        self.assertEqual(status['export_abi_against_2_0_based_baseline']['exported_records_compared'], 12236)
        self.assertFalse(status['installer_or_boot_image_created'])
        self.assertFalse(status['private_signing_key_exported'])
        self.assertTrue(any('unknown ROM module signers' in line for line in status['checks_not_proofs']))
        self.assertFalse(any('is not the ROM module signer' in line for line in status['checks_not_proofs']))
        self.assertEqual(len(status['matching_source_modules']['modules']), 6)
        self.assertEqual(status['output_sha256'][s32.IMAGE_NAME], s32.base.digest(self.result/s32.IMAGE_NAME))
        self.assertFalse((self.result/'DO-NOT-FLASH-Synthetica-3.0-Image.gz').exists())
        self.assertFalse(any(p.suffix in ('.pem', '.key', '.zip') for p in self.result.rglob('*')))
        subprocess.run(['sha256sum', '-c', 'SHA256SUMS.txt'], cwd=self.result, check=True,
                       stdout=subprocess.DEVNULL)
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.finish()

    def test_wrong_toolchain_or_changed_export_fail_before_output(self):
        (self.tc/'clang').write_text('#!/bin/sh\necho "clang version 24.0.0"\n')
        with self.assertRaisesRegex(ValueError, 'toolchain'):
            self.finish()
        self.assertFalse(self.result.exists())
        (self.tc/'clang').write_text('#!/bin/sh\necho "clang version 18.1.3"\n')
        symvers = self.out/'Module.symvers'
        symvers.write_text(symvers.read_text().replace('0x1ec57692', '0xffffffff', 1))
        with self.assertRaisesRegex(ValueError, 'export ABI'):
            self.finish()
        self.assertFalse(self.result.exists())

    def test_mismatched_cert_or_manager_fail_before_output(self):
        (self.kit/'artifacts/Image.gz').write_bytes(gzip.compress(self.raw.replace(self.cert, b'not-the-cert')))
        with self.assertRaisesRegex(ValueError, 'certificate'):
            self.finish()
        self.assertFalse(self.result.exists())
        (self.kit/'artifacts/Image.gz').write_bytes(gzip.compress(self.raw))
        (self.kit/'artifacts/manager/MANAGER.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.finish()
        self.assertFalse(self.result.exists())


if __name__ == '__main__':
    unittest.main()
