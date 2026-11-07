"""Offline source, compatibility, privacy and presentation guards for Manager 3.1.

These tests are not an Android runtime, device, installation or root test.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manager_neon31', ROOT / 'build-kit/scripts/build_manager_31_neon.py')
assert spec and spec.loader
neon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(neon)
preview_spec = importlib.util.spec_from_file_location('preview_neon31', ROOT / 'build-kit/scripts/build_neon31_preview.py')
assert preview_spec and preview_spec.loader
preview = importlib.util.module_from_spec(preview_spec)
preview_spec.loader.exec_module(preview)
ASSETS = neon.ASSETS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contrast(a: str, b: str) -> float:
    def luminance(rgb: str) -> float:
        channels = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class Neon31Tests(unittest.TestCase):
    def test_identity_and_licensed_offline_font(self):
        self.assertEqual((neon.APP_ID, neon.VERSION_NAME, neon.VERSION_CODE), ('net.ember.labs', '3.1.0', 41000))
        self.assertGreater(neon.VERSION_CODE, neon.previous.VERSION_CODE)
        font = ASSETS / 'res/font/oxanium.ttf'
        self.assertEqual(digest(font), neon.FONT_SHA256)
        self.assertEqual(font.read_bytes()[:4], b'\x00\x01\x00\x00')
        license_file = ASSETS / 'assets/licenses/Oxanium-OFL.txt'
        self.assertEqual(digest(license_file), neon.FONT_LICENSE_SHA256)
        self.assertIn('SIL OPEN FONT LICENSE', license_file.read_text())
        typography = (ASSETS / 'theme/Type.kt').read_text()
        self.assertIn('Font(R.font.oxanium', typography)
        self.assertIn('bodyMedium = TextStyle(\n        fontFamily = FontFamily.SansSerif', typography)

    def test_real_light_palette_is_contrasted_for_all_accents(self):
        theme = (ASSETS / 'theme/Theme.kt').read_text()
        colors = (ASSETS / 'theme/Color.kt').read_text()
        self.assertIn('val LightGlassStyle = GlassStyle(', theme)
        self.assertIn('val NeonLightScheme = lightColorScheme(', theme)
        self.assertNotIn('val LightGlassStyle = DarkGlassStyle', theme)
        self.assertIn('LightCanvasBase = Color(0xFFF1F5FF)', colors)
        for accent in ('006078', '9C0063', '6631A1', '2D6515'):
            self.assertIn(f'Color(0xFF{accent})', theme)
            for background in ('F8FBFF', 'F1F5FF', 'FFFFFF'):
                with self.subTest(accent=accent, background=background):
                    self.assertGreaterEqual(contrast(accent, background), 4.5)
        for ink in ('15213B', '42516A'):
            self.assertGreaterEqual(contrast(ink, 'F1F5FF'), 4.5)
        for choice in ('system', 'light', 'dark', 'amoled'):
            self.assertIn(f'"{choice}"', theme)
        self.assertIn('prefs.getBoolean("enable_amoled", false)', theme)
        self.assertIn('SystemBarStyle.light', theme)

    def test_glow_and_motion_are_persisted_lifecycle_aware_and_shared(self):
        theme = (ASSETS / 'theme/Theme.kt').read_text()
        glass = (ASSETS / 'theme/Glass.kt').read_text()
        self.assertEqual(theme.count('rememberInfiniteTransition('), 1)
        self.assertNotIn('rememberInfiniteTransition(', glass)
        for marker in ('Lifecycle.Event.ON_RESUME', 'Lifecycle.Event.ON_PAUSE',
                       'ValueAnimator.areAnimatorsEnabled()', 'NeonMotionState.value && systemAllowsMotion && resumed',
                       'putString("neon_theme", resolved)', 'putString("neon_glow", resolved)',
                       'putString("neon_accent", resolved)', 'putBoolean("neon_motion", enabled)'):
            self.assertIn(marker, theme)
        self.assertIn('LocalNeonGlow provides glow', theme)
        self.assertIn('LocalNeonGlow.current', glass)
        self.assertIn('phase.value', glass)
        self.assertRegex(glass, r'drawRect\(glass.canvasBase\)\s*//[^\n]*\n\s*//[^\n]*\n\s*if \(!glass.isAmoled\)')
        self.assertIn('NEON // MANAGER 3.1', glass)

    def test_device_check_is_read_only_and_does_not_request_permissions(self):
        device = (ASSETS / 'device/DeviceCheck.kt').read_text()
        math = (ASSETS / 'device/DeviceMath.kt').read_text()
        for forbidden in ('execKsud', 'Natives.', 'ProcessBuilder', 'Runtime.getRuntime().exec',
                          'Shell.', '/data/adb/', 'Manifest.permission', 'requestPermissions',
                          'openCamera(', 'registerListener(', 'FileOutputStream', '.writeText(', 'setprop'):
            self.assertNotIn(forbidden, device + math)
        for expected in ('repeatOnLifecycle(Lifecycle.State.RESUMED)', 'delay(3_000L)',
                         'Dispatchers.IO', 'readBattery(', 'CameraCharacteristics',
                         'getSensorList(Sensor.TYPE_ALL)', '/sys/devices/system/cpu/',
                         'device31_unavailable', 'Int.MIN_VALUE'):
            self.assertIn(expected, device)
        self.assertIn('?: return null', math)
        self.assertIn('level > scale', math)
        self.assertIn('available in 0..total', math)
        self.assertIn('cores = Runtime.getRuntime().availableProcessors(),', device)
        self.assertIn('hardware.cores.coerceIn(1, 64)', device)  # bound I/O, not the displayed count
        self.assertIn('stat.availableBytes to stat.totalBytes', device)
        for locale in ('values', 'values-in-rID'):
            strings = ET.parse(ASSETS / f'res/{locale}/strings_neon31.xml').getroot()
            storage_label = next(x.text for x in strings if x.get('name') == 'device31_storage_used')
            self.assertIn('available' if locale == 'values' else 'tersedia', storage_label.lower())

    def test_performance_is_read_only_and_clipboard_is_explicit(self):
        device = (ASSETS / 'device/DeviceCheck.kt').read_text()
        math = (ASSETS / 'device/DeviceMath.kt').read_text()
        summary = (ASSETS / 'device/DeviceSummary.kt').read_text()
        for marker in ('/proc/loadavg', '/proc/pressure/', '/sys/block/zram0/',
                       '/sys/class/kgsl/', '/sys/class/devfreq', 'readPerformance(hardware.gpuNodes)'):
            self.assertIn(marker, device)
        for marker in ('parseGpuFrequencyHz', 'parseLoadAverages', 'parseZramData', 'parsePressureAvg10'):
            self.assertIn(marker, math)
        self.assertIn('mutableStateOf(emptySet<String>())', device)
        self.assertIn('renderSelectedSummary(title, sections, selected)', device)
        self.assertIn('TextButton(enabled = preview.isNotEmpty(), onClick = {', device)
        self.assertEqual(device.count('clipboard.setPrimaryClip(clip)'), 1)
        self.assertIn('EXTRA_IS_SENSITIVE', device)
        self.assertIn('sections.filter { it.id in selected }', summary)
        for forbidden in ('Build.SERIAL', 'getSerial(', 'TelephonyManager', 'ANDROID_ID', 'Manifest.permission'):
            self.assertNotIn(forbidden, device + summary)

    def test_zip_preflight_is_bounded_and_not_a_security_scanner(self):
        engine = (ASSETS / 'preflight/PackagePreflight.kt').read_text()
        android = (ASSETS / 'preflight/AndroidZipPreflight.kt').read_text()
        headers = (ASSETS / 'preflight/ZipStructure.kt').read_text()
        flow = (ASSETS / 'screen/FlashPreflight.kt').read_text()
        for marker in ('512L * 1024L * 1024L', 'MAX_ENTRIES = 10_000', 'MAX_METADATA_BYTES = 64 * 1024',
                       'PreflightProblem.UNSAFE_PATH', 'PreflightProblem.DUPLICATE_PATH',
                       'PreflightProblem.AMBIGUOUS_TYPE', 'PreflightProblem.UNKNOWN_TYPE', 'SHA-256', 'ZipFile(file)'):
            self.assertIn(marker, engine)
        for marker in ('centralName.contentEquals(localName)', 'PreflightProblem.UNSUPPORTED_ZIP',
                       'PreflightProblem.UNSAFE_PATH', 'sorted[index].first < sorted[index - 1].second',
                       'u32(descriptor, base) != crc'):
            self.assertIn(marker, headers)
        for marker in ('MAX_BATCH = 16', 'MAX_BATCH_BYTES = PackagePreflight.MAX_ARCHIVE_BYTES',
                       'source.parentFile != root', 'PackagePreflight.matchesSha256(destination, expectedSha256)',
                       'file.parentFile == root', 'STALE_MILLIS'):
            self.assertIn(marker, android)
        for marker in ('Dispatchers.IO', 'NonCancellable', 'AndroidZipPreflight.deleteReports',
                       'reports.add(AndroidZipPreflight.inspect', 'dialog.awaitConfirm',
                       'reports.map { it.sha256 }', '!request.allowAnyKernel', 'zip31_kernel_batch'):
            self.assertIn(marker, flow)
        for forbidden in ('Runtime.getRuntime().exec', 'ProcessBuilder', 'Shell.', 'execKsud', 'Natives.'):
            self.assertNotIn(forbidden, engine + android + flow)
        en = (ASSETS / 'res/values/strings_neon31.xml').read_text()
        self.assertIn('not an antivirus, signature verification, or compatibility test', en)
        self.assertIn('earlier modules remain installed', en)

    def test_translations_match_and_do_not_duplicate_keys(self):
        locales = []
        for locale in ('values', 'values-in-rID'):
            root = ET.parse(ASSETS / f'res/{locale}/strings_neon31.xml').getroot()
            names = [element.get('name') for element in root]
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(element.text for element in root))
            locales.append(set(names))
        self.assertEqual(*locales)


@unittest.skipUnless(os.environ.get('NEON_SOURCE'), 'NEON_SOURCE pinned source fixture not supplied')
class ActualPreparedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='neon31-source-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        original = Path(os.environ['NEON_SOURCE'])
        cls.old, cls.new = Path(cls.tmp.name) / 'old', Path(cls.tmp.name) / 'new'
        shutil.copytree(original, cls.old)
        shutil.copytree(original, cls.new)
        neon.previous.prepare_tree(cls.old)
        neon.prepare_tree(cls.new)

    def test_exact_patch_scope_and_sensitive_files_preserved(self):
        old = {p.relative_to(self.old): digest(p) for p in self.old.rglob('*') if p.is_file()}
        new = {p.relative_to(self.new): digest(p) for p in self.new.rglob('*') if p.is_file()}
        changes = {str(p) for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
        expected = {
            'manager/build.gradle.kts', 'manager/app/build.gradle.kts',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt',
            *(f'manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/{name}' for name in (
                'Home.kt', 'Customization.kt', 'Module.kt', 'ModuleRepo.kt', 'MetaModule.kt', 'DeviceCheckScreen.kt',
                'Install.kt', 'Flash.kt', 'FlashPreflight.kt')),
            *(f'manager/app/src/main/java/com/rifsxd/ksunext/ui/theme/{name}' for name in (
                'Color.kt', 'Glass.kt', 'Theme.kt', 'Type.kt', 'AppearanceControls.kt')),
            *(f'manager/app/src/main/java/com/rifsxd/ksunext/ui/device/{name}' for name in ('DeviceCheck.kt', 'DeviceMath.kt', 'DeviceSummary.kt')),
            *(f'manager/app/src/main/java/com/rifsxd/ksunext/ui/preflight/{name}' for name in ('PackagePreflight.kt', 'ZipStructure.kt', 'AndroidZipPreflight.kt')),
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/util/KsuCli.kt',
            'manager/app/src/main/java/com/rifsxd/ksunext/ui/component/Dialog.kt',
            'manager/app/src/main/res/font/oxanium.ttf',
            'manager/app/src/main/res/values/strings_neon31.xml',
            'manager/app/src/main/res/values-in-rID/strings_neon31.xml',
            'manager/app/src/main/res/values/strings_synthetica.xml',
            'manager/app/src/main/res/values-in-rID/strings_synthetica.xml',
            'manager/app/src/main/assets/licenses/Oxanium-OFL.txt',
        }
        self.assertEqual(changes, expected)
        for path in ('AndroidManifest.xml', 'java/com/rifsxd/ksunext/Natives.kt',
                     'java/com/rifsxd/ksunext/ui/screen/SuperUser.kt',
                     'java/com/rifsxd/ksunext/ui/screen/Settings.kt',
                     'java/com/rifsxd/ksunext/ui/screen/Boost.kt',
                     'jniLibs/arm64-v8a/libksud.so'):
            with self.subTest(path=path):
                self.assertEqual(digest(self.old / 'manager/app/src/main' / path),
                                 digest(self.new / 'manager/app/src/main' / path))

    def test_home_accessible_without_root_and_appearance_has_one_control(self):
        ui = self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui'
        home = (ui / 'screen/Home.kt').read_text()
        custom = (ui / 'screen/Customization.kt').read_text()
        self.assertIn('navigator.navigate(DeviceCheckScreenDestination)', home)
        self.assertIn('NeonAppearanceControls(onThemeChanged', custom)
        self.assertNotIn('var enableAmoled', custom)
        for file in ('Module.kt', 'ModuleRepo.kt', 'MetaModule.kt'):
            text = (ui / 'screen' / file).read_text()
            self.assertIn('LocalGlassStyle.current.isDark', text)
            self.assertIn('LocalGlassStyle.current.isAmoled', text)
            self.assertNotIn('isSystemInDarkTheme()', text)

    def test_all_zip_paths_are_preflighted_and_existing_commands_are_guarded(self):
        ui = self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui'
        main = (ui / 'MainActivity.kt').read_text()
        install = (ui / 'screen/Install.kt').read_text()
        module = (ui / 'screen/Module.kt').read_text()
        flash = (ui / 'screen/Flash.kt').read_text()
        cli = (ui / 'util/KsuCli.kt').read_text()
        for source in (main, install, module, flash):
            self.assertNotIn('ZipUtils.isAnyKernel3Zip(', source)
        self.assertIn('allowAnyKernel = uris.size == 1', main)
        self.assertIn('endsWith("FlashAnyKernel") == true && uris.size == 1', main)
        self.assertIn('allowAnyKernel = uris.size == 1', module)
        self.assertIn('prepareZipInstall(context, flashIt, confirmDialog)', flash)
        self.assertIn('pendingFlashIt = approved', flash)
        self.assertIn('flashModulesSequentially(flashIt.uris, flashIt.approvedHashes', flash)
        self.assertIn('flashIt.approvedHash,', flash)
        self.assertIn('deleteApprovedZipStages(context, approved)', flash)
        self.assertIn('resolvedFlashIt is FlashIt.FlashAnyKernel', flash)
        self.assertIn('uris.size != approvedHashes.size', flash)
        module_func = cli.split('fun flashModule(', 1)[1].split('fun runModuleAction(', 1)[0]
        kernel_func = cli.split('fun flashAnyKernelZip(', 1)[1].split('fun rootAvailable(', 1)[0]
        self.assertLess(module_func.index('copyVerified('), module_func.index('module install ${file.absolutePath}'))
        self.assertIn('flashWithIO("${getKsuDaemonPath()} $cmd", onStdout, onStderr)', module_func)
        self.assertLess(kernel_func.index('copyVerified('), kernel_func.index('val cmd ='))
        self.assertLess(kernel_func.index('sha256sum -c -'), kernel_func.index('$BUSYBOX unzip -p'))
        self.assertLess(kernel_func.index('$BUSYBOX unzip -p'), kernel_func.index('$BUSYBOX ash'))
        self.assertNotIn('|| true', kernel_func)
        self.assertEqual(flash.count('flashAnyKernelZip('), 1)
        self.assertEqual(flash.count('flashModule('), 1)
        dialog = (ui / 'component/Dialog.kt').read_text()
        self.assertIn('Modifier.heightIn(max = 390.dp).verticalScroll(rememberScrollState())', dialog)
        result_flow = dialog.split('.onEach { result ->', 1)[1].split('.collect(resultCollector)', 1)[0]
        self.assertLess(result_flow.index('visible.value = false'), result_flow.index('it.resume(result)'))

    def test_pinned_busybox_sha256_check_fails_closed(self):
        arm = self.old / 'userspace/ksud/bin/aarch64/busybox'
        self.assertIn(b'sha256sum', arm.read_bytes())
        if platform.machine() not in ('x86_64', 'amd64'):
            self.skipTest('x86-64 host required to execute the pinned test BusyBox')
        with tempfile.TemporaryDirectory(prefix='neon31-busybox-test-') as temp:
            directory = Path(temp)
            busybox = directory / 'busybox'
            shutil.copy2(self.old / 'userspace/ksud/bin/x86_64/busybox', busybox)
            busybox.chmod(0o755)
            sample = directory / 'sample.zip'
            sample.write_bytes(b'synthetic data; no installer runs')
            good = hashlib.sha256(sample.read_bytes()).hexdigest()
            def verify(checksum: str):
                return subprocess.run([str(busybox), 'sha256sum', '-c', '-'],
                                      input=f'{checksum}  {sample}\n', text=True, capture_output=True)
            self.assertEqual(verify(good).returncode, 0)
            self.assertNotEqual(verify('0' * 64).returncode, 0)

    def test_preview_is_separate_and_shares_actual_ui_and_device_check(self):
        with tempfile.TemporaryDirectory(prefix='neon31-preview-test-') as temp:
            target = Path(temp) / 'preview'
            preview.prepare(target, Path(os.environ['NEON_SOURCE']))
            gradle = (target / 'app/build.gradle.kts').read_text()
            self.assertIn('applicationId = "net.ember.labs.neon31preview"', gradle)
            self.assertNotIn('applicationId = "net.ember.labs"', gradle)
            for name in ('DeviceCheck.kt', 'DeviceMath.kt', 'DeviceSummary.kt'):
                self.assertEqual((target / 'app/src/main/java/com/rifsxd/ksunext/ui/device' / name).read_bytes(),
                                 (ASSETS / 'device' / name).read_bytes())
            self.assertEqual((target / 'app/src/main/java/com/rifsxd/ksunext/ui/screen/FlashPreflight.kt').read_bytes(),
                             (ASSETS / 'screen/FlashPreflight.kt').read_bytes())
            self.assertEqual((target / 'app/src/main/java/com/rifsxd/ksunext/ui/component/Dialog.kt').read_bytes(),
                             (self.new / 'manager/app/src/main/java/com/rifsxd/ksunext/ui/component/Dialog.kt').read_bytes())
            for name in ('PackagePreflight.kt', 'ZipStructure.kt', 'AndroidZipPreflight.kt'):
                self.assertEqual((target / 'app/src/main/java/com/rifsxd/ksunext/ui/preflight' / name).read_bytes(),
                                 (ASSETS / 'preflight' / name).read_bytes())
            for name in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt', 'AppearanceControls.kt'):
                self.assertEqual((target / 'app/src/main/java/com/rifsxd/ksunext/ui/theme' / name).read_bytes(),
                                 (ASSETS / 'theme' / name).read_bytes())
            self.assertFalse(list(target.rglob('*.so')))
            manifest = ET.parse(target / 'app/src/main/AndroidManifest.xml').getroot()
            for permission in manifest.findall('uses-permission'):
                self.assertEqual(permission.get('{http://schemas.android.com/tools}node'), 'remove')


if __name__ == '__main__':
    unittest.main()
