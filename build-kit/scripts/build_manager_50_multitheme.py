#!/usr/bin/env python3
"""Prepare/build one unsigned Manager 5.0 with selectable presentation styles.

Uses the pinned Manager 4.0 pipeline and leaves its native authorization,
permissions, daemon, helpers, ZIP preflight and root-facing screens intact.
Signing with the original key is a separate local, explicitly authorized step.
"""
from __future__ import annotations

import argparse
import hashlib
import html
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_40_pixel as previous

ASSETS = ROOT / 'build-kit/ci/ksun-multitheme50'
VERSION_NAME = '5.0.0'
VERSION_CODE = 60000
APP_ID = previous.neon31.APP_ID


def replace_string(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r'(<string name="' + re.escape(key) + r'">)([^<]*)(</string>)')
    if len(pattern.findall(text)) != 1:
        raise RuntimeError(f'Expected one string {key} in {path}')
    text = pattern.sub(lambda m: m.group(1) + html.escape(value, quote=False) + m.group(3), text, count=1)
    path.write_text(text, encoding='utf-8')


def copy_theme(main: Path) -> None:
    theme = main / 'java/com/rifsxd/ksunext/ui/theme'
    for name in ('Theme.kt', 'Glass.kt', 'AppearanceControls.kt', 'VisualStyles.kt'):
        shutil.copy2(ASSETS / 'theme' / name, theme / name)
    shutil.copytree(ASSETS / 'res', main / 'res', dirs_exist_ok=True)


def patch_labels(main: Path) -> None:
    res = main / 'res'
    labels = {
        'values': {
            'ios_customization_sub': 'Language, themes, AMOLED and navigation',
            'ios_about_sub': 'Manager 5.0, UAPI v4 and open-source credits',
            'synthetica_custom_glass_group': 'Appearance',
            'synthetica_about_tagline': 'Multi-theme kernel & root manager',
            'neon_motion_title': 'Appearance motion',
            'neon_motion_subtitle': 'Animated accents and navigation; respects system animation settings',
            'neon_accent_group': 'Accent',
            'neon_accent_cyan': 'Theme default', 'neon_accent_pink': 'Alternative A',
            'neon_accent_violet': 'Alternative B', 'neon_accent_lime': 'Alternative C',
        },
        'values-in-rID': {
            'ios_customization_sub': 'Bahasa, tema, AMOLED dan navigasi',
            'ios_about_sub': 'Manager 5.0, UAPI v4 dan kredit sumber terbuka',
            'synthetica_custom_glass_group': 'Tampilan',
            'synthetica_about_tagline': 'Manajer kernel & root dengan banyak tema',
            'neon_motion_title': 'Animasi tampilan',
            'neon_motion_subtitle': 'Animasi aksen dan navigasi; mengikuti pengaturan sistem',
            'neon_accent_group': 'Aksen',
            'neon_accent_cyan': 'Bawaan tema', 'neon_accent_pink': 'Alternatif A',
            'neon_accent_violet': 'Alternatif B', 'neon_accent_lime': 'Alternatif C',
        },
    }
    for locale, items in labels.items():
        path = res / locale / 'strings_synthetica.xml'
        for key, value in items.items():
            replace_string(path, key, value)
        replace_string(res / locale / 'strings_neon31.xml', 'neon31_glow_title',
                       'Accent intensity' if locale == 'values' else 'Intensitas aksen')


def prepare_tree(src: Path) -> None:
    previous.prepare_tree(src)
    patch = previous.previous.patch_file
    patch(src / 'manager/build.gradle.kts', [
        ('val managerVersionCode by extra(50000)', f'val managerVersionCode by extra({VERSION_CODE})', '5.0 version code', 1),
        ('val managerVersionName by extra("4.0.0")', f'val managerVersionName by extra("{VERSION_NAME}")', '5.0 version name', 1),
    ])
    patch(src / 'manager/app/build.gradle.kts', [
        ('output.outputFileName = "Synthetica-4.0-Pixel-$name.apk"',
         'output.outputFileName = "Synthetica-5.0-MultiTheme-$name.apk"', '5.0 output name', 1),
    ])
    main = src / 'manager/app/src/main'
    copy_theme(main)
    patch_labels(main)
    activity = main / 'java/com/rifsxd/ksunext/ui/MainActivity.kt'
    patch(activity, [
        ('val dockShape = CutCornerShape(5.dp)', 'val dockShape = MaterialTheme.shapes.extraLarge', 'theme-aware dock', 1),
        ('val pillShape = CutCornerShape(4.dp)', 'val pillShape = MaterialTheme.shapes.medium', 'theme-aware dock selection', 1),
    ])
    daemon = main / 'jniLibs/arm64-v8a/libksud.so'
    if hashlib.sha256(daemon.read_bytes()).hexdigest() != previous.previous.EXPECTED_KSUD:
        raise RuntimeError('The root daemon differs from the pinned 4.0 baseline')
    print(f'[multitheme50] {APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI 4; unsigned', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-patches-only', action='store_true')
    parser.add_argument('--source', type=Path, help='extracted pinned source for patch-only verification')
    args = parser.parse_args()
    if args.verify_patches_only:
        if args.source is None or not args.source.is_dir():
            parser.error('--source must point to an extracted pinned source tree')
        with tempfile.TemporaryDirectory(prefix='synthetica-multitheme50-patch-') as temp:
            source = Path(temp) / 'source'
            shutil.copytree(args.source, source)
            prepare_tree(source)
        print('[done] 5.0 patch verification only; no APK built')
        return 0
    if args.source is not None:
        parser.error('--source is only supported for --verify-patches-only')
    base = previous.previous.base
    work = base.WORK_DIR.resolve()
    if work == Path('/') or work == Path.home() or work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise RuntimeError('Refusing unsafe Manager working directory')
    source = base.prepare_source()
    prepare_tree(source)
    base.zipalign_apk(base.build_gradle(source))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
