"""Host regressions for Manager 5.0 presentation and 4.0 security boundary."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_40_pixel as old
import build_manager_50_multitheme as app
import build_multitheme50_preview as preview

ASSETS = app.ASSETS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MultiThemeAssetTests(unittest.TestCase):
    def test_four_stable_styles_persist_without_changing_existing_settings(self):
        styles = (ASSETS / 'theme/VisualStyles.kt').read_text()
        theme = (ASSETS / 'theme/Theme.kt').read_text()
        controls = (ASSETS / 'theme/AppearanceControls.kt').read_text()
        for item in ('PIXEL("pixel")', 'CYBERPUNK("cyberpunk")', 'IOS_GLASS("ios_glass")', 'NEON("neon")'):
            self.assertIn(item, styles)
        for key in ('manager_visual_style', 'neon_accent', 'neon_motion', 'neon_theme', 'neon_glow', 'enable_amoled'):
            self.assertIn(key, theme)
        self.assertIn('ManagerStyle.fromId(prefs.getString("manager_visual_style", "pixel"))', theme)
        self.assertIn('putString("manager_visual_style", style.id).apply()', theme)
        self.assertIn('?: PIXEL', styles)
        self.assertIn('setManagerStyle(context, option.style.id)', controls)
        self.assertIn('Role.RadioButton', controls)
        self.assertIn('onThemeChanged(id)', controls)
        self.assertIn('shapesForStyle(style)', theme)
        self.assertIn('typographyForStyle(style)', theme)
        self.assertIn('accentForStyle(style, NeonAccentState.value, isDark)', theme)

    def test_animation_is_shared_and_stops_with_app_or_system(self):
        theme = (ASSETS / 'theme/Theme.kt').read_text()
        glass = (ASSETS / 'theme/Glass.kt').read_text()
        for marker in ('ValueAnimator.areAnimatorsEnabled()', 'Lifecycle.Event.ON_PAUSE', 'Lifecycle.Event.ON_RESUME',
                       'NeonMotionState.value && systemAllowsMotion && resumed',
                       'style != ManagerStyle.IOS_GLASS', 'LocalPixelMotionEnabled provides motionEnabled'):
            self.assertIn(marker, theme)
        self.assertEqual(theme.count('rememberInfiniteTransition('), 1)
        self.assertNotIn('rememberInfiniteTransition(', glass)
        self.assertIn('if (!glass.isAmoled)', glass)
        self.assertIn('without a live GPU backdrop blur', glass)
        self.assertIn('MANAGER 5.0', glass)
        self.assertNotIn('MANAGER 4.0', glass)
        self.assertIn('defaultMinSize(minHeight = 56.dp)', glass)

    def test_translations_match_without_duplicates(self):
        locales = []
        for locale in ('values', 'values-in-rID'):
            root = ET.parse(ASSETS / 'res' / locale / 'strings_manager50.xml').getroot()
            names = [e.get('name') for e in root]
            self.assertTrue(all(e.text for e in root))
            self.assertEqual(len(names), len(set(names)))
            locales.append(set(names))
        self.assertEqual(*locales)
        self.assertEqual(len(locales[0]), 10)


@unittest.skipUnless(os.environ.get('MULTITHEME50_SOURCE'), 'pinned source fixture not supplied')
class PreparedMultiThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='multitheme50-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        source = Path(os.environ['MULTITHEME50_SOURCE'])
        cls.old = Path(cls.tmp.name) / 'old'
        cls.new = Path(cls.tmp.name) / 'new'
        shutil.copytree(source, cls.old)
        shutil.copytree(source, cls.new)
        old.prepare_tree(cls.old)
        app.prepare_tree(cls.new)

    def test_all_non_presentation_source_bytes_match_40(self):
        oldfiles = {p.relative_to(self.old).as_posix() for p in self.old.rglob('*') if p.is_file()}
        newfiles = {p.relative_to(self.new).as_posix() for p in self.new.rglob('*') if p.is_file()}
        added = newfiles - oldfiles
        removed = oldfiles - newfiles
        self.assertEqual(removed, set())
        self.assertEqual(added, {
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/theme/VisualStyles.kt',
            'manager/app/src/main/res/values/strings_manager50.xml',
            'manager/app/src/main/res/values-in-rID/strings_manager50.xml',
        })
        allowed = {
            'manager/build.gradle.kts', 'manager/app/build.gradle.kts',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt',
            *(f'manager/app/src/main/java/com/rifsxd/ksunext/ui/theme/{x}'
              for x in ('Theme.kt', 'Glass.kt', 'AppearanceControls.kt')),
            *(f'manager/app/src/main/res/{locale}/{name}'
              for locale in ('values', 'values-in-rID')
              for name in ('strings_synthetica.xml', 'strings_neon31.xml')),
        }
        changed = {p for p in oldfiles & newfiles if digest(self.old / p) != digest(self.new / p)}
        self.assertEqual(changed, allowed)
        before = (self.old / 'manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt').read_text()
        after = (self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt').read_text()
        after = after.replace('val dockShape = MaterialTheme.shapes.extraLarge', 'val dockShape = CutCornerShape(5.dp)')
        after = after.replace('val pillShape = MaterialTheme.shapes.medium', 'val pillShape = CutCornerShape(4.dp)')
        self.assertEqual(before, after)
        gradle = (self.new / 'manager/build.gradle.kts').read_text()
        self.assertIn('managerVersionCode by extra(60000)', gradle)
        self.assertIn('managerVersionName by extra("5.0.0")', gradle)
        app_gradle = (self.new / 'manager/app/build.gradle.kts').read_text()
        self.assertIn('applicationId = "net.ember.labs"', app_gradle)
        self.assertNotIn('signingConfig =', app_gradle)

    def test_preview_is_a_separate_package_without_root_payload(self):
        target = Path(self.tmp.name) / 'preview50'
        preview.prepare(target, Path(os.environ['MULTITHEME50_SOURCE']))
        main = target / 'app/src/main'
        self.assertIn('net.ember.labs.multitheme50preview', (target / 'app/build.gradle.kts').read_text())
        self.assertIn('android.permission.INTERNET" tools:node="remove"', (main / 'AndroidManifest.xml').read_text())
        for name in ('jniLibs', 'assets/synthetica-control40.sh', 'assets/synthetica-boost40.sh',
                     'java/com/rifsxd/ksunext/ui/util/PixelRootActions40.kt'):
            self.assertFalse((main / name).exists(), name)
        for file in ('Theme.kt', 'Glass.kt', 'AppearanceControls.kt', 'VisualStyles.kt'):
            self.assertEqual(digest(main / 'java/com/rifsxd/ksunext/ui/theme' / file),
                             digest(self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui/theme' / file))


if __name__ == '__main__':
    unittest.main()
