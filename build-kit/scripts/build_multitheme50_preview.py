#!/usr/bin/env python3
"""Build a separate non-root 5.0 theme preview for emulator testing only."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_pixel40_preview as old
import build_manager_50_multitheme as app50


def prepare(target: Path, source: Path) -> None:
    old.prepare(target, source)
    main = target / 'app/src/main'
    gradle = target / 'app/build.gradle.kts'
    old.replace_once(gradle, 'applicationId = "net.ember.labs.pixel40preview"',
                     'applicationId = "net.ember.labs.multitheme50preview"')
    old.replace_once(gradle, 'versionCode = 50000', 'versionCode = 60000')
    old.replace_once(gradle, 'versionName = "4.0.0-preview"', 'versionName = "5.0.0-preview"')
    old.replace_once(main / 'AndroidManifest.xml', 'Synthetica 4.0 Pixel Preview', 'Synthetica 5.0 Theme Preview')
    activity = main / 'java/com/rifsxd/ksunext/PreviewActivity.kt'
    old.replace_once(activity, '4.0.0 • PREVIEW ONLY', '5.0.0 • PREVIEW ONLY')
    app50.copy_theme(main)
    strings = main / 'res/values/strings.xml'
    for key, value in {'neon_accent_cyan': 'Theme default', 'neon_accent_pink': 'Alternative A',
                       'neon_accent_violet': 'Alternative B', 'neon_accent_lime': 'Alternative C'}.items():
        app50.replace_string(strings, key, value)
    strings = main / 'res/values/strings_preview31.xml'
    for key, value in {'neon_accent_group': 'Accent', 'neon_motion_title': 'Appearance motion',
                       'neon_motion_subtitle': 'Animated accents and navigation; respects system animation settings'}.items():
        app50.replace_string(strings, key, value)
    app50.replace_string(main / 'res/values/strings_neon31.xml', 'neon31_glow_title', 'Accent intensity')
    tests = target / 'app/src/test/java/com/rifsxd/ksunext/ui/theme'
    tests.mkdir(parents=True, exist_ok=True)
    shutil.copy2(app50.ASSETS / 'preview/ThemeLogic50Test.kt', tests / 'ThemeLogic50Test.kt')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetica-multitheme50-preview-') as temp:
        target = Path(temp) / 'project'
        prepare(target, args.source)
        if args.verify_only:
            print('5.0 preview prepared; no APK built')
            return
        subprocess.run([str(target / 'gradlew'), ':app:testDebugUnitTest', ':app:assembleDebug',
                        '--no-daemon', '--stacktrace'], cwd=target, check=True)
        apks = list((target / 'app/build/outputs/apk/debug').glob('*.apk'))
        if len(apks) != 1:
            raise RuntimeError('Expected exactly one debug-signed preview APK')
        output = Path(os.environ['MULTITHEME50_PREVIEW_OUTPUT'])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise RuntimeError('Refusing to overwrite existing preview output')
        shutil.copy2(apks[0], output)
        print('Preview only (not Manager):', output, hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
