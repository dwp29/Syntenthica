"""Host-side design, accessibility and root-compatibility guards for Neon Manager.

These tests do not run Android, inspect an installed app, or prove root behavior.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manager_neon', ROOT / 'build-kit/scripts/build_manager_30_neon.py')
assert spec and spec.loader
neon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(neon)
THEME = ROOT / 'build-kit/ci/ksun-neon/theme'


def contrast(a: str, b: str) -> float:
    def luminance(rgb: str) -> float:
        channels = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignSourceTests(unittest.TestCase):
    def test_version_advances_and_keeps_real_package_and_uapi4_daemon(self):
        self.assertGreater(neon.VERSION_CODE, 30004)
        self.assertEqual(neon.VERSION_NAME, '3.0.0')
        self.assertEqual(neon.APP_ID, 'net.ember.labs')
        neon.check_baseline()
        self.assertEqual(neon.EXPECTED_KSUD, 'c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427')

    def test_accents_have_readable_contrast_and_consistent_identity(self):
        theme = (THEME / 'Theme.kt').read_text()
        choices = re.findall(r'NeonAccentOption\("(\w+)", R.string.neon_accent_\w+, Color\(0xFF([0-9A-F]{6})\)\)', theme)
        self.assertEqual([item[0] for item in choices], ['cyan', 'pink', 'violet', 'lime'])
        for label, color in choices:
            with self.subTest(accent=label):
                self.assertGreaterEqual(contrast(color, '182039'), 4.5)
                self.assertGreaterEqual(contrast(color, '061018'), 4.5)
        self.assertIn('?: NeonAccentOptions.first()', theme)
        self.assertIn('putString("neon_accent", resolved)', theme)
        self.assertIn('surfaceTint = accent', theme)

    def test_animation_is_shared_persisted_and_respects_system_reduced_motion(self):
        theme = (THEME / 'Theme.kt').read_text()
        glass = (THEME / 'Glass.kt').read_text()
        self.assertEqual(theme.count('rememberInfiniteTransition('), 1)
        self.assertNotIn('rememberInfiniteTransition(', glass)
        self.assertIn('NeonMotionState.value && systemAllowsMotion', theme)
        self.assertIn('ValueAnimator.areAnimatorsEnabled()', theme)
        self.assertIn('Lifecycle.Event.ON_RESUME', theme)
        self.assertIn('putBoolean("neon_motion", enabled)', theme)
        self.assertIn('LocalNeonPhase provides phase', theme)
        self.assertIn('phase.value', glass)
        self.assertIn('size(48.dp)', glass)
        self.assertIn('stringResource(R.string.neon_back)', glass)

    def test_branding_pngs_have_correct_android_density_sizes(self):
        def dimensions(path: Path) -> tuple[int, int]:
            data = path.read_bytes()[:24]
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            return struct.unpack('>II', data[16:24])
        for density, multiplier in {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}.items():
            for prefix, base in [('ic_launcher', 48), ('ic_foreground', 108), ('ic_background', 108), ('ic_mono', 108)]:
                expected = int(base * multiplier)
                with self.subTest(density=density, prefix=prefix):
                    self.assertEqual(dimensions(neon.BRANDING / f'{prefix}-{density}.png'), (expected, expected))

    def test_unique_source_anchors_fail_closed(self):
        for value in ('missing', 'needle needle'):
            with self.assertRaises(RuntimeError):
                neon.replace_exact(value, 'needle', 'changed', 'test')
        self.assertEqual(neon.replace_exact('before needle after', 'needle', 'changed', 'test'), 'before changed after')


@unittest.skipUnless(os.environ.get('NEON_SOURCE'), 'NEON_SOURCE pinned source fixture not supplied')
class ActualSourcePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neon-tests-')
        cls.addClassCleanup(cls.temp.cleanup)
        original = Path(os.environ['NEON_SOURCE'])
        cls.old, cls.new = Path(cls.temp.name) / 'old', Path(cls.temp.name) / 'new'
        shutil.copytree(original, cls.old)
        shutil.copytree(original, cls.new)
        neon.base.apply_synthetica_patch(cls.old)
        neon.prepare_tree(cls.new)

    def test_only_ui_resources_version_and_branding_changed(self):
        old_files = {p.relative_to(self.old): digest(p) for p in self.old.rglob('*') if p.is_file()}
        new_files = {p.relative_to(self.new): digest(p) for p in self.new.rglob('*') if p.is_file()}
        changes = {str(p) for p in old_files.keys() | new_files.keys() if old_files.get(p) != new_files.get(p)}
        self.assertTrue(changes)
        for path in changes:
            allowed = (
                path in {'manager/build.gradle.kts', 'manager/app/build.gradle.kts'} or
                path in {
                    'manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt',
                    'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Home.kt',
                    'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Customization.kt',
                } or
                path.startswith('manager/app/src/main/java/com/rifsxd/ksunext/ui/theme/') or
                path.startswith('manager/app/src/main/res/mipmap-') or
                path.startswith('manager/app/src/main/res/drawable-') or
                path in {
                    'manager/app/src/main/res/values/strings_synthetica.xml',
                    'manager/app/src/main/res/values-in-rID/strings_synthetica.xml',
                }
            )
            with self.subTest(path=path):
                self.assertTrue(allowed, f'unexpected non-UI source change: {path}')
        for sensitive in ('Natives.kt', 'ui/screen/SuperUser.kt', 'ui/screen/Settings.kt', 'ui/screen/Boost.kt'):
            relative = 'manager/app/src/main/java/com/rifsxd/ksunext/' + sensitive
            self.assertNotIn(relative, changes)

    def test_navigation_semantics_and_real_seccomp_read(self):
        java = self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui'
        home = (java / 'screen/Home.kt').read_text()
        main = (java / 'MainActivity.kt').read_text()
        custom = (java / 'screen/Customization.kt').read_text()
        self.assertIn('Os.prctl(21, 0, 0, 0, 0)', home)
        self.assertIn('R.string.neon_seccomp_unavailable', home)
        self.assertIn('R.string.neon_seccomp_subtitle', home)
        self.assertIn('BuildConfig.VERSION_NAME', home)
        self.assertNotIn('"Synthetica 2.0"', home)
        self.assertIn('selected = isSelected', main)
        self.assertIn('role = Role.Tab', main)
        self.assertIn('role = Role.RadioButton', custom)
        self.assertIn('setNeonAccent(context, option.id)', custom)
        self.assertIn('setNeonMotion(context, it)', custom)
        for locale in ('values', 'values-in-rID'):
            path = self.new / f'manager/app/src/main/res/{locale}/strings_synthetica.xml'
            strings = {e.get('name'): e.text for e in ET.parse(path).getroot()}
            for key in ('neon_back', 'neon_seccomp_title', 'neon_seccomp_subtitle', 'neon_motion_title', 'neon_accent_cyan'):
                self.assertTrue(strings[key])


if __name__ == '__main__':
    unittest.main()
