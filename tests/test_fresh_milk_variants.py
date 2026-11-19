"""Uji varian Fresh-Milk / CHEESE-BURGER tanpa kompilasi.

Memastikan:
- dua varian menghasilkan identitas rilis berbeda
- kunci config yang diizinkan cocok dengan isi fragment
- simbol wajib-hidup dan wajib-mati dideklarasikan
- nama rilis muat di batas utsname 64 karakter
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build-kit/scripts/build_fresh_milk.py'
ASSETS = ROOT / 'build-kit/ci/fresh-milk'


def load():
    spec = importlib.util.spec_from_file_location('fresh_milk', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_fragment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('# CONFIG_') and line.endswith(' is not set'):
            values[line[2:-11]] = 'n'
        elif line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            values[key[len('CONFIG_'):]] = value
    return values


class VariantIdentity(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_two_distinct_releases(self):
        releases = {v['release'] for v in self.m.VARIANTS.values()}
        self.assertEqual(len(releases), 2, 'kedua varian harus punya rilis berbeda')

    def test_release_names_fit_utsname(self):
        # release = "4.14.357" + EXTRAVERSION "-openela" + LOCALVERSION
        for name, spec in self.m.VARIANTS.items():
            full = spec['release']
            self.assertLessEqual(len(full), 64, f'{name}: {full} melebihi batas utsname')

    def test_localversion_matches_release(self):
        for name, spec in self.m.VARIANTS.items():
            local = spec['localversion'].strip('"')
            self.assertTrue(spec['release'].endswith(local),
                            f'{name}: release tidak berakhiran localversion')

    def test_capitalisation_is_preserved(self):
        self.assertEqual(self.m.VARIANTS['fresh-milk']['localversion'], '"-Fresh-Milk-14.03"')
        self.assertEqual(self.m.VARIANTS['cheese-burger']['localversion'],
                         '"-CHEESE-BURGER-11.08"')


class ConfigFragments(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_common_fragment_matches_allowed(self):
        actual = read_fragment(ASSETS / 'common.config')
        expected = {k: after for k, (_before, after) in self.m.ALLOWED.items()}
        self.assertEqual(actual, expected,
                         'fragment bersama dan daftar izin harus sama isinya')

    def test_variant_fragment_only_sets_localversion(self):
        for name, spec in self.m.VARIANTS.items():
            values = read_fragment(spec['fragment'])
            self.assertEqual(set(values), {'LOCALVERSION'},
                             f'{name}: fragment varian hanya boleh menyetel LOCALVERSION')
            self.assertEqual(values['LOCALVERSION'], spec['localversion'])

    def test_must_stay_off_has_reasons(self):
        for key, reason in self.m.MUST_STAY_OFF.items():
            self.assertTrue(reason.strip(), f'{key}: alasan tidak boleh kosong')

    def test_try_umount_stays_off_with_reason(self):
        # Dibuktikan dari source: v2.3.0 maupun v2.4.0 tidak membawa fungsinya.
        self.assertIn('KSU_SUSFS_TRY_UMOUNT', self.m.MUST_STAY_OFF)
        self.assertIn('susfs_try_umount', self.m.MUST_STAY_OFF['KSU_SUSFS_TRY_UMOUNT'])

    def test_required_features_non_empty(self):
        self.assertGreaterEqual(len(self.m.MUST_STAY_ON), 15)
        for feature in ('KSU', 'KSU_SUSFS', 'NOMOUNT', 'LRU_GEN', 'SCHED_TUNE'):
            self.assertIn(feature, self.m.MUST_STAY_ON)


class InstallerText(unittest.TestCase):
    def test_installer_is_english_and_plain(self):
        text = (ASSETS / 'anykernel/anykernel.sh').read_text(encoding='utf-8')
        lowered = text.lower()
        for forbidden in ('الْحَمْدُ', 'بِسْمِ', 'done. kernel installed.'):
            self.assertNotIn(forbidden, text, 'teks lama masih ada')
        self.assertIn('Kernel installed.', text)
        self.assertIn('Reboot when ready.', text)
        # progress bar sederhana
        self.assertIn('sp_bar', text)


if __name__ == '__main__':
    unittest.main()
