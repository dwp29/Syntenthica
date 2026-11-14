"""Regression guards for production designs and the deliberately simulated UI fixture."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_50_multitheme as old
import build_manager_501_themes as app
import build_manager_501_fixture as fixture


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
        # 6.1 adds three themes, but to the shipped 6.0.0 tree, NOT to the
        # frozen 5.0.1 tree these assets belong to. Assert the opposite here so
        # the ledger stays a record of what 5.0.1 actually contained.
        for style in ('RETRO_ARCADE',):
            self.assertNotIn(f'ManagerStyle.{style} ->', hero)
            self.assertNotIn(f'ManagerStyle.{style} ->', styles)
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
        for splash_fn in ('PixelMatrixSplash', 'CyberBrutalSplash', 'IosLiquidGlassSplash', 'NeonCyberSplash'):
            self.assertIn(splash_fn, glass)
        for emblem in ('ic_emblem_pixel.png', 'ic_emblem_cyberpunk.png', 'ic_emblem_ios_glass.png', 'ic_emblem_neon.png'):
            self.assertTrue((app.ASSETS / 'res/drawable-nodpi' / emblem).is_file(), emblem)
        self.assertEqual(app.VERSION_CODE, 60001)
        self.assertEqual(app.APP_ID, 'net.ember.labs')

    def test_no_secret_or_signing_material(self):
        for path in app.ASSETS.rglob('*'):
            if path.is_file():
                self.assertNotIn(path.suffix.lower(), {'.jks', '.p12', '.keystore', '.pem', '.key'})


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
