#!/usr/bin/env python3
"""Build an isolated, debug-signed 4.0 UI preview: not a Manager, no root."""
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
import build_neon31_preview as preview31
import build_manager_40_pixel as pixel40


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    path.write_text(pixel40.previous.replace_exact(text, old, new, str(path)), encoding='utf-8')


def prepare(target: Path, source: Path) -> None:
    preview31.prepare(target, source)
    main = target / 'app/src/main'
    gradle = target / 'app/build.gradle.kts'
    replace_once(gradle, 'applicationId = "net.ember.labs.neon31preview"', 'applicationId = "net.ember.labs.pixel40preview"')
    replace_once(gradle, 'versionCode = 41000', 'versionCode = 50000')
    replace_once(gradle, 'versionName = "3.1.0-preview"', 'versionName = "4.0.0-preview"')
    replace_once(main / 'AndroidManifest.xml', 'Synthetica 3.1 Neon Preview', 'Synthetica 4.0 Pixel Preview')
    shutil.copy2(pixel40.ASSETS / 'preview/PreviewActivity.kt', main / 'java/com/rifsxd/ksunext/PreviewActivity.kt')
    theme = main / 'java/com/rifsxd/ksunext/ui/theme'
    for item in (pixel40.ASSETS / 'theme').glob('*.kt'):
        shutil.copy2(item, theme / item.name)
    target_pixel = main / 'java/com/rifsxd/ksunext/ui/pixel'
    target_pixel.mkdir(parents=True, exist_ok=True)
    for item in (pixel40.ASSETS / 'pixel').glob('*.kt'):
        shutil.copy2(item, target_pixel / item.name)
    shutil.copytree(pixel40.ASSETS / 'res', main / 'res', dirs_exist_ok=True)
    shutil.copy2(pixel40.ASSETS / 'assets/licenses/Silkscreen-OFL.txt', main / 'assets/licenses/Silkscreen-OFL.txt')
    shutil.copy2(pixel40.ASSETS / 'branding/ic_synthetica_emblem.png', main / 'res/drawable-nodpi/ic_synthetica_emblem.png')
    (main / 'res/values/strings.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="neon_back">Back</string>
    <string name="neon_accent_cyan">Signal red</string>
    <string name="neon_accent_pink">Monochrome</string>
    <string name="neon_accent_violet">Amber</string>
    <string name="neon_accent_lime">Mint</string>
</resources>
''', encoding='utf-8')
    (main / 'res/values/strings_preview31.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="neon_accent_group">Signal accent</string>
    <string name="neon_motion_title">Pixel motion</string>
    <string name="neon_motion_subtitle">Animated signal and navigation; respects system animation settings</string>
</resources>
''', encoding='utf-8')
    replace_once(main / 'res/values/strings_neon31.xml', 'Neon glow', 'Signal intensity')
    tests = target / 'app/src/test/java/com/rifsxd/ksunext/ui/pixel'
    tests.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pixel40.ASSETS / 'preview/PixelLogic40Test.kt', tests / 'PixelLogic40Test.kt')
    # This project intentionally does NOT copy root helper assets or screen wrappers.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetica-pixel40-preview-') as temp:
        target = Path(temp) / 'project'
        prepare(target, args.source)
        if args.verify_only:
            print('4.0 preview prepared; no APK built')
            return
        subprocess.run([str(target / 'gradlew'), ':app:testDebugUnitTest', ':app:assembleDebug',
                        '--no-daemon', '--stacktrace'], cwd=target, check=True)
        apks = list((target / 'app/build/outputs/apk/debug').glob('*.apk'))
        if len(apks) != 1:
            raise RuntimeError('Expected exactly one debug-signed preview APK')
        output = Path(os.environ['PIXEL40_PREVIEW_OUTPUT'])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise RuntimeError('Refusing to overwrite existing preview output')
        shutil.copy2(apks[0], output)
        print('Preview only (not Manager):', output, hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
