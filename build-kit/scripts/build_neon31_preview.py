#!/usr/bin/env python3
"""Build a separate, debug-signed 3.1 preview: not the Manager and no root backend."""
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
import build_neon_preview as old_preview
import build_manager_31_neon as neon31

ASSETS = neon31.ASSETS


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    path.write_text(neon31.previous.replace_exact(text, old, new, str(path)), encoding='utf-8')


def prepare(target: Path, source: Path) -> None:
    old_preview.prepare(target, source)
    main = target / 'app/src/main'
    gradle = target / 'app/build.gradle.kts'
    replace_once(gradle, 'applicationId = "net.ember.labs.neonpreview"',
                 'applicationId = "net.ember.labs.neon31preview"')
    replace_once(gradle, 'versionCode = 40000', 'versionCode = 41000')
    replace_once(gradle, 'versionName = "3.0.0-preview"', 'versionName = "3.1.0-preview"')
    replace_once(gradle, 'dependencies {\n', 'dependencies {\n    testImplementation("junit:junit:4.13.2")\n')
    replace_once(main / 'AndroidManifest.xml', 'Synthetica Neon Preview', 'Synthetica 3.1 Neon Preview')
    shutil.copy2(ASSETS / 'preview/PreviewActivity.kt', main / 'java/com/rifsxd/ksunext/PreviewActivity.kt')
    theme = main / 'java/com/rifsxd/ksunext/ui/theme'
    for file in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt', 'AppearanceControls.kt'):
        shutil.copy2(ASSETS / 'theme' / file, theme / file)
    device = main / 'java/com/rifsxd/ksunext/ui/device'
    device.mkdir(parents=True)
    for file in ('DeviceCheck.kt', 'DeviceMath.kt'):
        shutil.copy2(ASSETS / 'device' / file, device / file)
    shutil.copytree(ASSETS / 'res', main / 'res', dirs_exist_ok=True)
    shutil.copytree(ASSETS / 'assets', main / 'assets', dirs_exist_ok=True)
    (main / 'res/values/strings_preview31.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="neon_accent_group">Neon accent</string>
    <string name="neon_motion_title">Neon motion</string>
    <string name="neon_motion_subtitle">Animated glow; respects system animation settings</string>
</resources>
''', encoding='utf-8')
    tests = target / 'app/src/test/java/com/rifsxd/ksunext/ui/device'
    tests.mkdir(parents=True)
    shutil.copy2(ASSETS / 'preview/DeviceMathTest.kt', tests / 'DeviceMathTest.kt')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetica-neon31-preview-') as temp:
        target = Path(temp) / 'project'
        prepare(target, args.source)
        if args.verify_only:
            print('3.1 preview prepared; no APK built')
            return
        subprocess.run([str(target / 'gradlew'), ':app:testDebugUnitTest', ':app:assembleDebug',
                        '--no-daemon', '--stacktrace'], cwd=target, check=True)
        apks = list((target / 'app/build/outputs/apk/debug').glob('*.apk'))
        if len(apks) != 1:
            raise RuntimeError('Expected exactly one debug-signed preview APK')
        output = Path(os.environ['NEON31_PREVIEW_OUTPUT'])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise RuntimeError('Refusing to overwrite preview output')
        shutil.copy2(apks[0], output)
        print('Preview only (not Manager):', output, hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
