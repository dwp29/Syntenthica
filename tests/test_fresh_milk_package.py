"""Packaging checks for the Fresh-Milk / CHEESE-BURGER recovery ZIP.

The packager must only ever wrap compile evidence that matches the variant
exactly. These tests build a synthetic but self-consistent evidence directory
and prove both directions: a good build is packaged, a tampered one is refused.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build-kit/scripts/package_fresh_milk.py'
RELEASE = '4.14.357-openela-Fresh-Milk-14.03'


def load():
    spec = importlib.util.spec_from_file_location('fresh_milk_package_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_evidence(root: Path, module, release: str = RELEASE) -> None:
    """A synthetic but internally consistent result directory."""
    root.mkdir(parents=True)
    config = ('CONFIG_LOCALVERSION="%s"\nCONFIG_KSU=y\n' % release.split('openela')[1]).encode()
    raw = (b'\x00' * 8192
           + ('Linux version %s (builder@host) #1 SMP\n' % release).encode()
           + b'KernelSU net.ember.labs ' + module.s2x.MANAGER_CERT_SHA.encode() + b'\n'
           + b'IKCFG_ST' + gzip.compress(config) + b'IKCFG_ED')
    image = gzip.compress(raw)
    cert = b'-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n'
    (root / 'Image.gz.DO-NOT-FLASH').write_bytes(image)
    (root / 'generated.config.txt').write_bytes(config)
    (root / 'module-signing-public-cert.x509').write_bytes(cert)
    (root / 'STATUS.json').write_text(json.dumps({
        'kind': module.build.STATUS_KIND,
        'uname_release': release,
        'image_sha256': sha(image),
        'config_sha256': sha(config),
        'base_source': module.V3.SOURCE,
        'compiler': {'kind': 'neutron',
                     'neutron_archive_sha256': module.s2x.NEUTRON_SHA},
        'mglru': {'variant': 'on', 'enabled_by_default': True, 'runtime_tested': False},
        'installer_created': False,
        'private_key_exported': False,
        'manager': {'package': 'net.ember.labs',
                    'cert_sha256': module.s2x.MANAGER_CERT_SHA},
        'module_public_cert_sha256': sha(cert),
    }))


class Packaging(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.tmp = Path(tempfile.mkdtemp())
        self.result = self.tmp / 'result'
        build_evidence(self.result, self.m)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_zip_contains_a_complete_installer(self):
        out = self.tmp / 'fm.zip'
        self.m.package(self.result, 'fresh-milk', out)
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            for required in ('Image.gz', 'anykernel.sh', 'tools/prepare-boot.sh',
                             'tools/busybox', 'tools/magiskboot', 'LICENSE',
                             'META-INF/com/google/android/update-binary',
                             'META-INF/com/google/android/updater-script'):
                self.assertIn(required, names, required)

    def test_installer_pins_the_exact_image(self):
        out = self.tmp / 'fm.zip'
        self.m.package(self.result, 'fresh-milk', out)
        image_sha = sha((self.result / 'Image.gz.DO-NOT-FLASH').read_bytes())
        with zipfile.ZipFile(out) as z:
            entry = z.read('anykernel.sh').decode()
        self.assertIn(image_sha, entry)
        # The template's own pinned digest must be gone.
        self.assertNotIn(self.m.TEMPLATE_IMAGE_SHA256, entry)

    def test_banner_names_the_variant(self):
        out = self.tmp / 'fm.zip'
        self.m.package(self.result, 'fresh-milk', out)
        with zipfile.ZipFile(out) as z:
            entry = z.read('anykernel.sh').decode()
        self.assertIn('Fresh-Milk 14.03', entry)
        self.assertIn(RELEASE, entry)

    def test_no_private_key_or_debug_archive_is_shipped(self):
        out = self.tmp / 'fm.zip'
        self.m.package(self.result, 'fresh-milk', out)
        with zipfile.ZipFile(out) as z:
            for name in z.namelist():
                lowered = name.lower()
                self.assertNotIn('.key', lowered)
                self.assertNotIn('private', lowered)
            backend = z.read('META-INF/com/google/android/update-binary')
            self.assertIn(b'no persistent debug archive', backend)

    def test_metadata_states_the_limits(self):
        out = self.tmp / 'fm.zip'
        self.m.package(self.result, 'fresh-milk', out)
        with zipfile.ZipFile(out) as z:
            meta = json.loads(z.read('BUILD-INFO.json'))
        self.assertEqual(meta['physical_boot_test_this_image'], 'NOT RUN')
        self.assertEqual(meta['auto_backup'], False)
        self.assertEqual(meta['writes'], ['boot partition only, after runtime checks'])
        self.assertIn('ksud', meta['does_not_write'])

    def test_refuses_a_tampered_image(self):
        (self.result / 'Image.gz.DO-NOT-FLASH').write_bytes(b'not the audited image')
        with self.assertRaises(ValueError):
            self.m.collect(self.result, 'fresh-milk')

    def test_refuses_another_variants_evidence(self):
        build_evidence(self.tmp / 'other', self.m,
                       release='4.14.357-openela-CHEESE-BURGER-11.08')
        with self.assertRaises(ValueError):
            self.m.collect(self.tmp / 'other', 'fresh-milk')

    def test_refuses_when_a_limit_flag_is_wrong(self):
        status = json.loads((self.result / 'STATUS.json').read_text())
        for key, value in (('installer_created', True),
                           ('private_key_exported', True),
                           ('mglru', {'variant': 'on', 'enabled_by_default': True,
                                      'runtime_tested': True})):
            mutated = dict(status, **{key: value})
            (self.result / 'STATUS.json').write_text(json.dumps(mutated))
            with self.assertRaises(ValueError, msg=key):
                self.m.collect(self.result, 'fresh-milk')

    def test_refuses_to_overwrite(self):
        out = self.tmp / 'fm.zip'
        out.write_bytes(b'existing')
        with self.assertRaises(ValueError):
            self.m.package(self.result, 'fresh-milk', out)


if __name__ == '__main__':
    unittest.main()
