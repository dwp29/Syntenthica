"""Offline safeguards for the isolated, non-root visual demo."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preview_builder', ROOT / 'build-kit/scripts/build_neon_preview.py')
assert spec and spec.loader
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class PreviewIsolationTests(unittest.TestCase):
    def test_demo_package_is_separate_and_never_calls_root_or_network(self):
        gradle = (preview.PROJECT / 'app/build.gradle.kts').read_text()
        activity = (preview.PROJECT / 'app/src/main/java/com/rifsxd/ksunext/PreviewActivity.kt').read_text()
        manifest_path = preview.PROJECT / 'app/src/main/AndroidManifest.xml'
        manifest = ET.parse(manifest_path).getroot()
        self.assertIn('applicationId = "net.ember.labs.neonpreview"', gradle)
        self.assertNotIn('applicationId = "net.ember.labs"', gradle)
        for dangerous in ('Natives', 'execKsud', '/data/adb/', 'Runtime.getRuntime', 'ProcessBuilder', 'Shell.'):
            self.assertNotIn(dangerous, activity)
        self.assertIn('PRATINJAU SAJA — bukan Manager root', activity)
        self.assertIn('data di bawah adalah contoh', activity)
        self.assertIn('Role.Tab', activity)
        self.assertIn('Role.RadioButton', activity)
        permissions = manifest.findall('uses-permission')
        self.assertEqual(len(permissions), 2)
        for permission in permissions:
            self.assertEqual(permission.get('{http://schemas.android.com/tools}node'), 'remove')
        self.assertFalse(list(preview.PROJECT.rglob('*.so')))

    @unittest.skipUnless(os.environ.get('NEON_SOURCE'), 'NEON_SOURCE pinned wrapper fixture not supplied')
    def test_prepared_demo_shares_exact_theme_and_pinned_wrapper(self):
        with tempfile.TemporaryDirectory(prefix='preview-test-') as temp:
            project = Path(temp) / 'project'
            preview.prepare(project, Path(os.environ['NEON_SOURCE']))
            for file in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt'):
                self.assertEqual((project / 'app/src/main/java/com/rifsxd/ksunext/ui/theme' / file).read_bytes(),
                                 (preview.THEME / file).read_bytes())
            self.assertTrue((project / 'gradlew').is_file())
            self.assertTrue((project / 'app/src/main/res/drawable-nodpi/ic_synthetica_emblem.png').is_file())
            with self.assertRaises(ValueError):
                preview.prepare(project, Path(os.environ['NEON_SOURCE']))


if __name__ == '__main__':
    unittest.main()
