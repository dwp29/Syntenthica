"""Regression guards for production designs and the deliberately simulated UI fixture."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_50_multitheme as old
import build_manager_501_themes as app
import build_manager_501_fixture as fixture
import fetch_gradle_501 as gradle_fetch


class Theme501SourceTests(unittest.TestCase):
    def test_new_layouts_are_real_screen_components(self):
        glass = (app.ASSETS / 'theme/Glass.kt').read_text()
        hero = (app.ASSETS / 'theme/ThemedHero.kt').read_text()
        styles = (app.ASSETS / 'theme/VisualStyles.kt').read_text()
        selector = (app.ASSETS / 'theme/AppearanceControls.kt').read_text()
        self.assertIn('DistinctManagerHero(', glass)
        for style in ('PIXEL', 'CYBERPUNK', 'IOS_GLASS', 'NEON'):
            self.assertIn(f'ManagerStyle.{style} ->', hero)
            self.assertIn(f'ManagerStyle.{style} ->', styles)
        self.assertIn('managerDockSpec', styles)
        self.assertIn('StyleThumbnail', selector)
        self.assertIn('LocalGlassWallpaperLayer', glass)
        self.assertIn('LocalGlassContentLayer', glass)
        self.assertIn('Build.VERSION_CODES.S', glass)
        self.assertIn('BlurEffect(', glass)
        self.assertIn('!glass.isAmoled', glass)
        self.assertIn('LocalContentColor provides MaterialTheme.colorScheme.onSurface', glass)
        self.assertIn('FlowRow(', hero)  # statuses can wrap on small/large-font screens
        self.assertIn('role = Role.RadioButton', selector)
        self.assertEqual(app.VERSION_CODE, 60001)
        self.assertEqual(app.APP_ID, 'net.ember.labs')

    def test_no_secret_or_signing_material(self):
        for path in app.ASSETS.rglob('*'):
            if path.is_file():
                self.assertNotIn(path.suffix.lower(), {'.jks', '.p12', '.keystore', '.pem', '.key'})

    def test_gradle_distribution_is_exactly_pinned_and_unknown_wrapper_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrapper = root / 'manager/gradle/wrapper/gradle-wrapper.properties'
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text('distributionUrl=https\\://services.gradle.org/distributions/gradle-9.2.0-bin.zip\nnetworkTimeout=10000\n')
            with mock.patch.dict(os.environ, {'SYNTHETICA_GRADLE_ZIP': ''}):
                app.pin_gradle_distribution(root)
            text = wrapper.read_text()
            self.assertIn('downloads.gradle.org/distributions/gradle-9.2.0-bin.zip', text)
            self.assertIn('networkTimeout=120000', text)
            self.assertIn('distributionSha256Sum=' + app.GRADLE_SHA256, text)
            with self.assertRaises(ValueError):
                app.pin_gradle_distribution(root)

    def test_gradle_ranges_and_local_checksum_fail_closed(self):
        gradle_fetch.validate_response('HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 3-6/20\r\n', 4, 3, 6, 20)
        for header, size in (('Content-Range: bytes 0-3/20\r\n', 4), ('Content-Range: bytes 3-6/20\r\n', 3), ('', 4)):
            with self.assertRaises(ValueError):
                gradle_fetch.validate_response(header, size, 3, 6, 20)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrapper = root / 'manager/gradle/wrapper/gradle-wrapper.properties'
            wrapper.parent.mkdir(parents=True)
            original = 'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.2.0-bin.zip\nnetworkTimeout=10000\n'
            wrapper.write_text(original)
            zip_file = root / 'local.zip'
            zip_file.write_bytes(b'not-the-pinned-gradle')
            with mock.patch.dict(os.environ, {'SYNTHETICA_GRADLE_ZIP': str(zip_file)}), self.assertRaisesRegex(ValueError, 'SHA-256'):
                app.pin_gradle_distribution(root)
            self.assertEqual(wrapper.read_text(), original)
            fake_digest = hashlib.sha256(zip_file.read_bytes()).hexdigest()
            with mock.patch.dict(os.environ, {'SYNTHETICA_GRADLE_ZIP': str(zip_file)}), mock.patch.object(app, 'GRADLE_SHA256', fake_digest):
                app.pin_gradle_distribution(root)
            self.assertIn('distributionUrl=file\\://', wrapper.read_text())
            self.assertIn('distributionSha256Sum=' + fake_digest, wrapper.read_text())

    @unittest.skipUnless(shutil.which('curl'), 'curl is required for the range downloader')
    def test_gradle_downloader_assembles_only_verified_ranges(self):
        data = bytes(range(251)) * 40

        class RangeHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                match = re.fullmatch(r'bytes=(\d+)-(\d+)', self.headers.get('Range', ''))
                if not match:
                    self.send_error(400)
                    return
                start, end = map(int, match.groups())
                payload = data[start:end + 1]
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = HTTPServer(('127.0.0.1', 0), RangeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.multiple(
            gradle_fetch, URL=f'http://127.0.0.1:{server.server_port}/gradle.zip',
            TOTAL=len(data), PART=1024, GRADLE_SHA256=hashlib.sha256(data).hexdigest(),
        ):
            out = Path(tmp) / 'gradle.zip'
            gradle_fetch.fetch(out)
            self.assertEqual(out.read_bytes(), data)
            with self.assertRaises(FileExistsError):
                gradle_fetch.fetch(out)


@unittest.skipUnless(os.environ.get('MULTITHEME50_SOURCE'), 'pinned upstream source not provided')
class PreparedTrees501Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='test-synthetica501-')
        root = Path(cls.temp.name)
        source = Path(os.environ['MULTITHEME50_SOURCE'])
        cls.a = root / 'manager50'
        cls.b = root / 'manager501'
        cls.f = root / 'fixture501'
        cls.fb = root / 'fixture50'
        for target in (cls.a, cls.b, cls.f, cls.fb): shutil.copytree(source, target)
        old.prepare_tree(cls.a)
        app.prepare_tree(cls.b)
        fixture.prepare(cls.f)
        fixture.prepare(cls.fb, baseline50=True)
        cls.amain = cls.a / 'manager/app/src/main'
        cls.bmain = cls.b / 'manager/app/src/main'
        cls.fmain = cls.f / 'manager/app/src/main'
        cls.pkg = Path('java/com/rifsxd/ksunext')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_root_backend_and_screen_logic_are_unchanged(self):
        pkg = self.pkg
        for name in ('Natives.kt', 'KernelSUApplication.kt', 'ui/screen/Home.kt', 'ui/screen/Settings.kt',
                     'ui/screen/Customization.kt', 'ui/util/KsuCli.kt', 'ui/util/PixelRootActions40.kt',
                     'ui/viewmodel/ModuleViewModel.kt'):
            with self.subTest(name=name):
                self.assertEqual((self.amain / pkg / name).read_bytes(), (self.bmain / pkg / name).read_bytes())
        self.assertEqual((self.amain / 'AndroidManifest.xml').read_bytes(), (self.bmain / 'AndroidManifest.xml').read_bytes())
        self.assertEqual((self.amain / 'jniLibs/arm64-v8a/libksud.so').read_bytes(),
                         (self.bmain / 'jniLibs/arm64-v8a/libksud.so').read_bytes())
        self.assertEqual((self.amain / pkg / 'ui/theme/Theme.kt').read_bytes(),
                         (self.bmain / pkg / 'ui/theme/Theme.kt').read_bytes())  # old preference keys retained
        activity = (self.bmain / pkg / 'ui/MainActivity.kt').read_text()
        self.assertIn('managerDockSpec(LocalManagerStyle.current)', activity)
        self.assertIn('if (Natives.isManager) install()', activity)  # unchanged real backend startup
        self.assertIn('val dockShape = dockSpec.containerShape', activity)
        self.assertIn('val pillShape = dockSpec.selectedShape', activity)
        self.assertIn('LaunchedEffect(currentRoute) { isScrollingDown.value = false }', activity)
        self.assertIn('val wrapDockLabels = maxWidth < 320.dp || density.fontScale > 1.2f', activity)
        self.assertIn('height(adaptiveDockHeight)', activity)
        self.assertIn('maxLines = if (wrapDockLabels) 2 else 1', activity)

    def test_fixture_runs_production_screen_compositions_but_never_the_real_backend(self):
        pkg = self.pkg
        for name in ('ui/screen/Settings.kt', 'ui/screen/Customization.kt', 'ui/theme/Glass.kt',
                     'ui/theme/VisualStyles.kt', 'ui/theme/ThemedHero.kt'):
            self.assertEqual((self.bmain / pkg / name).read_bytes(), (self.fmain / pkg / name).read_bytes())
        actual_home = (self.bmain / pkg / 'ui/screen/Home.kt').read_text()
        fixture_home = (self.fmain / pkg / 'ui/screen/Home.kt').read_text()
        self.assertEqual(actual_home.replace('subtitle = "${BuildConfig.VERSION_NAME}  •  UAPI v$managerUAPIVersion",',
                                             'subtitle = "SIMULATED UI  •  NO ROOT",'), fixture_home)
        activity = (self.fmain / pkg / 'ui/MainActivity.kt').read_text()
        self.assertIn('managerDockSpec(LocalManagerStyle.current)', activity)
        for absent in ('superUserViewModel.fetchAppList()', 'moduleViewModel.fetchModuleList()', 'if (Natives.isManager) install()'):
            self.assertNotIn(absent, activity)
        natives = (self.fmain / pkg / 'Natives.kt').read_text()
        cli = (self.fmain / pkg / 'ui/util/KsuCli.kt').read_text()
        self.assertNotIn('external fun', natives)
        self.assertNotIn('external get', natives)
        self.assertNotIn('System.loadLibrary', natives)
        for prohibited in ('Shell.cmd(', 'ShellUtils.fastCmd', 'Shell.Builder.create(', 'debug su'):
            self.assertNotIn(prohibited, cli)
        self.assertIn('UI fixture: privileged backend disabled', cli)
        self.assertFalse((self.fmain / 'jniLibs').exists())
        self.assertFalse(list((self.fmain / 'assets').glob('*.sh')))
        manifest = (self.fmain / 'AndroidManifest.xml').read_text()
        self.assertIn('tools:node="remove"', manifest)
        self.assertIn('SIMULATED UI TEST — NOT MANAGER', manifest)
        self.assertEqual(fixture.FIXTURE_ID, 'net.ember.labs.fixture501')


if __name__ == '__main__':
    unittest.main()
