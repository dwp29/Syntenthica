#!/usr/bin/env python3
"""4.0 source-scope, disclosure, accessibility and opt-in safety tests."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_40_pixel as pixel40
import build_pixel40_preview as preview40

ASSETS = pixel40.ASSETS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Pixel40AssetTests(unittest.TestCase):
    def test_display_font_and_license_are_pinned(self):
        for name, expected in pixel40.FONT_HASHES.items():
            self.assertEqual(digest(ASSETS / name), expected)
        license_text = (ASSETS / 'assets/licenses/Silkscreen-OFL.txt').read_text()
        self.assertIn('SIL OPEN FONT LICENSE Version 1.1', license_text)
        typography = (ASSETS / 'theme/Type.kt').read_text()
        self.assertIn('R.font.silkscreen_regular', typography)
        self.assertIn('R.font.silkscreen_bold', typography)
        self.assertIn('FontFamily.SansSerif', typography)
        self.assertNotIn('NDot', typography)

    def test_one_motion_clock_respects_lifecycle_and_system(self):
        theme = (ASSETS / 'theme/Theme.kt').read_text()
        glass = (ASSETS / 'theme/Glass.kt').read_text()
        for fragment in ('ValueAnimator.areAnimatorsEnabled()', 'NeonMotionState.value && systemAllowsMotion && resumed',
                         'Lifecycle.Event.ON_PAUSE', 'Lifecycle.Event.ON_RESUME', 'LocalPixelMotionEnabled provides motionEnabled'):
            self.assertIn(fragment, theme)
        self.assertEqual(theme.count('rememberInfiniteTransition('), 1)
        self.assertNotIn('rememberInfiniteTransition(', glass)
        self.assertIn('if (!glass.isAmoled)', glass)
        self.assertIn('if (LocalPixelMotionEnabled.current)', glass)
        self.assertIn('EnterTransition.None', glass)
        self.assertIn('ExitTransition.None', glass)
        self.assertIn('defaultMinSize(minHeight = 56.dp)', glass)
        self.assertIn('PIXEL // MANAGER 4.0', glass)
        self.assertNotIn('NEON // MANAGER 3.1', glass)

    def test_catalog_is_grouped_safe_and_requires_explicit_external_open(self):
        source = (ASSETS / 'pixel/Sources40.kt').read_text()
        screen = (ASSETS / 'screen/PixelSources40Screen.kt').read_text()
        for group in ('directories', 'providers', 'frameworks', 'modules', 'xposed', 'channels'):
            self.assertIn(f'R.string.pixel40_sources_{group}', source)
        links = re.findall(r'PixelSource40\("([^"]+)", "(https://[^"]+)"', source)
        self.assertGreaterEqual(len(links), 20)
        self.assertEqual(len(links), len({url for _, url in links}))
        for _, url in links:
            parsed = urlsplit(url)
            self.assertEqual(parsed.scheme, 'https')
            self.assertIn(parsed.hostname, {'github.com', 'modules.kernelsu.org', 'modules.lsposed.org', 't.me'})
            self.assertIsNone(parsed.username)
        self.assertIn(('LSPosed', 'https://github.com/LSPosed/LSPosed/releases'), links)
        self.assertIn(('LSPosed · Telegram', 'https://t.me/LSPosed'), links)
        self.assertIn('AlertDialog(', source)
        self.assertIn('onOpen(source.url)', source)
        self.assertIn('uri.scheme == "https"', screen)
        self.assertIn('Intent.ACTION_VIEW', screen)
        for forbidden in ('Shell.', 'execKsud', 'download(', 'module install', 'FlashScreen'):
            self.assertNotIn(forbidden, source + screen)

    def test_diagnostics_are_honest_and_read_only(self):
        backend = (ASSETS / 'screen/PixelDiagnostics40Screen.kt').read_text()
        ui = (ASSETS / 'pixel/Diagnostics40.kt').read_text()
        for command in ('susfs support', 'susfs version', 'susfs variant', 'susfs features', 'module list', 'id -u'):
            self.assertIn(command, backend)
        for forbidden in ('susfs config', 'susfs add', 'susfs set', 'module install', 'setAppProfile', 'execKsud('):
            self.assertNotIn(forbidden, backend + ui)
        self.assertIn('query("$quoted susfs support") == "Supported"', backend)
        self.assertIn('providers: List<ProviderCandidate40>? = null', ui)
        self.assertIn('possibleProviderConflict40', ui)
        for needle in ('rezygisk', 'neozygisk', 'zygisknext'):
            self.assertIn(needle, ui)

    def test_controls_require_confirmation_and_helpers_are_restricted(self):
        page = (ASSETS / 'pixel/Actions40.kt').read_text()
        runner = (ASSETS / 'util/PixelRootActions40.kt').read_text()
        boost = (ASSETS / 'assets/synthetica-boost40.sh').read_text()
        control = (ASSETS / 'assets/synthetica-control40.sh').read_bytes()
        self.assertEqual(control, (ROOT / 'build-kit/ci/ksun-cyberbrutal/assets/synthetica-control.sh').read_bytes())
        self.assertIn('ActionConfirmation40', page)
        self.assertIn('onConfirm = { action -> pending = null; onAction(action) }', page)
        self.assertIn('BackHandler(enabled = busy)', page)
        self.assertIn('unset SP_SYSROOT SP_PROCSYS SP_STATE_DIR SP_SERVICE_DIR', runner)
        self.assertIn('allowed.matches(action)', runner)
        self.assertNotIn('boot_on', boost)
        self.assertNotIn('chmod 0755', boost)
        self.assertIn('changed externally; not overwritten', boost)
        self.assertIn('originals of 2.x/3.x scripts', boost)
        self.assertIn('No snapshots recorded for this boot', boost)

    def test_translations_have_exactly_matching_nonempty_keys_and_warnings(self):
        locales = []
        for locale in ('values', 'values-in-rID'):
            root = ET.parse(ASSETS / 'res' / locale / 'strings_pixel40.xml').getroot()
            names = [element.get('name') for element in root]
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(element.text for element in root))
            locales.append(set(names))
        self.assertEqual(*locales)
        english = (ASSETS / 'res/values/strings_pixel40.xml').read_text()
        for phrase in ('not audited', 'not malware scanning', 'do not prove hiding is active',
                       'not a global injection test', 'No snapshots'):
            if phrase != 'No snapshots':
                self.assertIn(phrase, english)

    def test_original_pixel_icon_is_a_valid_small_png(self):
        for image in (ASSETS / 'branding').glob('*.png'):
            self.assertTrue(image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertLess(image.stat().st_size, 10_000)


@unittest.skipUnless(os.environ.get('PIXEL40_SOURCE'), 'PIXEL40_SOURCE pinned source fixture not supplied')
class PreparedPixel40Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='pixel40-source-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        original = Path(os.environ['PIXEL40_SOURCE'])
        cls.old, cls.new = Path(cls.tmp.name) / 'old', Path(cls.tmp.name) / 'new'
        shutil.copytree(original, cls.old)
        shutil.copytree(original, cls.new)
        pixel40.neon31.prepare_tree(cls.old)
        pixel40.prepare_tree(cls.new)

    def test_critical_identity_security_and_preflight_sources_are_unchanged(self):
        paths = (
            'uapi/supercall.h', 'userspace/ksud/src/cli.rs', 'userspace/ksud/src/susfsd.rs',
            'manager/app/src/main/AndroidManifest.xml', 'manager/app/src/main/cpp/ksu.cc',
            'manager/app/src/main/cpp/jni.cc', 'manager/app/src/main/jniLibs/arm64-v8a/libksud.so',
            'manager/app/src/main/java/com/rifsxd/ksunext/Natives.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Settings.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/SuperUser.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Flash.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/FlashPreflight.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/util/KsuCli.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/preflight/PackagePreflight.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/preflight/ZipStructure.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/preflight/AndroidZipPreflight.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/device/DeviceCheck.kt',
        )
        for name in paths:
            with self.subTest(name=name):
                self.assertEqual(digest(self.old / name), digest(self.new / name))
        gradle = (self.new / 'manager/build.gradle.kts').read_text()
        self.assertIn('managerVersionCode by extra(50000)', gradle)
        self.assertIn('managerVersionName by extra("4.0.0")', gradle)
        app_gradle = (self.new / 'manager/app/build.gradle.kts').read_text()
        self.assertIn('applicationId = "net.ember.labs"', app_gradle)
        self.assertNotIn('signingConfig =', app_gradle)

    def test_root_confirmation_cannot_grant_until_confirmed(self):
        profile = (self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/AppProfile.kt').read_text()
        self.assertIn('if (enabled && !isRootGranted) confirmRootGrant = true', profile)
        self.assertIn('onProfileChange(profile.copy(allowSu = true))', profile)
        self.assertIn('else onProfileChange(profile.copy(allowSu = enabled))', profile)
        self.assertIn('Natives.setAppProfile(it)', profile)
        self.assertIn('appInfo.uid < 2000', profile)

    def test_routes_motion_and_susfs_disclosure_are_connected(self):
        ui = self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui'
        home = (ui / 'screen/Home.kt').read_text()
        repo = (ui / 'screen/ModuleRepo.kt').read_text()
        main = (ui / 'MainActivity.kt').read_text()
        self.assertIn('navigator.navigate(PixelControl40ScreenDestination)', home)
        self.assertIn('navigator.navigate(PixelDiagnostics40ScreenDestination)', home)
        self.assertIn('navigator.navigate(DeviceCheckScreenDestination)', home)
        self.assertIn('navigator.navigate(PixelSources40ScreenDestination)', repo)
        self.assertIn('!pixelMotion -> EnterTransition.None', main)
        self.assertIn('!pixelMotion -> ExitTransition.None', main)
        self.assertIn('Not reported in Manager', home)
        self.assertIn('pixel40_unavailable_short', home)
        for locale in ('values', 'values-in-rID'):
            strings = (self.new / 'manager/app/src/main/res' / locale / 'strings_synthetica.xml').read_text()
            self.assertNotIn('Conceals root mounts', strings)
            self.assertNotIn('Menyembunyikan mount', strings)

    def test_separate_preview_has_no_privileged_implementation(self):
        target = Path(self.tmp.name) / 'preview'
        preview40.prepare(target, Path(os.environ['PIXEL40_SOURCE']))
        main = target / 'app/src/main'
        self.assertFalse((main / 'assets/synthetica-control40.sh').exists())
        self.assertFalse((main / 'assets/synthetica-boost40.sh').exists())
        self.assertFalse((main / 'jniLibs').exists())
        self.assertFalse((main / 'java/com/rifsxd/ksunext/ui/util/PixelRootActions40.kt').exists())
        manifest = (main / 'AndroidManifest.xml').read_text()
        self.assertRegex(manifest, r'android:name="android.permission.INTERNET" tools:node="remove"')
        self.assertIn('net.ember.labs.pixel40preview', (target / 'app/build.gradle.kts').read_text())


if __name__ == '__main__':
    unittest.main()
