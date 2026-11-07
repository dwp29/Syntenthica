#!/usr/bin/env python3
"""Build Synthetica 3.1 UI/Device Check on the pinned UAPI-4 Manager.

This builds an UNSIGNED APK. The package, native code, daemon, permissions and
root-facing scripts remain the 3.0 baseline; signing is a separate local step.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_30_neon as previous

ASSETS = ROOT / 'build-kit/ci/ksun-neon31'
sys.path.insert(0, str(ASSETS))
import preflight_patch as zip_patch
VERSION_NAME = '3.1.0'
VERSION_CODE = 41000
APP_ID = previous.APP_ID
FONT_SHA256 = '2ce01d946e1e1ffc8d7eecfffbda8623bedd63eaf811a20488c4b69af45babb0'
FONT_LICENSE_SHA256 = 'fe17c0f2581d71b4e1ea7e636e7f4877c29223e11bb1dd1a871e8c3f2a86336b'


def patch_home(path: Path) -> None:
    previous.patch_file(path, [
        ('import com.ramcosta.composedestinations.generated.destinations.BoostScreenDestination\n',
         'import com.ramcosta.composedestinations.generated.destinations.BoostScreenDestination\n'
         'import com.ramcosta.composedestinations.generated.destinations.DeviceCheckScreenDestination\n',
         'Device Check route import', 1),
        ('''            IosGroup(title = stringResource(R.string.ios_quick_utilities)) {
                IosRow(
                    icon = Icons.Rounded.Bolt,''',
         '''            IosGroup(title = stringResource(R.string.ios_quick_utilities)) {
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.device31_title),
                    subtitle = stringResource(R.string.device31_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(DeviceCheckScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Bolt,''', 'Device Check quick access', 1),
    ])


def patch_customization(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = previous.replace_exact(
        text, 'import com.rifsxd.ksunext.ui.theme.GlassTopBar\n',
        'import com.rifsxd.ksunext.ui.theme.GlassTopBar\n'
        'import com.rifsxd.ksunext.ui.theme.NeonAppearanceControls\n', 'appearance controls import')
    text = previous.replace_exact(
        text, '''    var enableAmoled by rememberSaveable {
        mutableStateOf(prefs.getBoolean("enable_amoled", false))
    }
''', '', 'old AMOLED switch state')
    start_anchor = '''                IosGroupDivider()
                IosSwitchRow(
                    icon = Icons.Rounded.AutoAwesome,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.neon_motion_title),'''
    end_anchor = '''            IosGroup(title = stringResource(R.string.synthetica_custom_layout_group)) {'''
    if text.count(start_anchor) != 1 or text.count(end_anchor) != 1:
        raise RuntimeError('Expected exactly one 3.0 appearance section')
    start, end = text.index(start_anchor), text.index(end_anchor)
    if start >= end:
        raise RuntimeError('Appearance section anchors are out of order')
    text = text[:start] + '''            }

            NeonAppearanceControls(onThemeChanged = { choice ->
                // Keep the legacy flag in sync for unchanged screens.
                activity?.setAmoledMode(choice == "amoled")
            })

''' + text[end:]
    path.write_text(text, encoding='utf-8')


def patch_theme_aware_banner(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = previous.replace_exact(text, 'import androidx.compose.foundation.isSystemInDarkTheme\n',
                                  'import com.rifsxd.ksunext.ui.theme.LocalGlassStyle\n',
                                  f'{path.name} theme import')
    text = previous.replace_exact(text, 'val isDark = isSystemInDarkTheme()',
                                  'val isDark = LocalGlassStyle.current.isDark',
                                  f'{path.name} theme mode')
    old_pref = 'enable_amoled' if path.name == 'Module.kt' else 'amoled_mode'
    text = previous.replace_exact(
        text, f'''val amoledMode = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
                    .getBoolean("{old_pref}", false)''',
        'val amoledMode = LocalGlassStyle.current.isAmoled', f'{path.name} AMOLED mode')
    path.write_text(text, encoding='utf-8')


def patch_navigation_motion(path: Path) -> None:
    previous.patch_file(path, [
        ('import androidx.compose.animation.core.Spring\n',
         'import androidx.compose.animation.core.FastOutSlowInEasing\nimport androidx.compose.animation.core.Spring\n',
         'navigation easing import', 1),
        ('animationSpec = tween(280)', 'animationSpec = tween(300, easing = FastOutSlowInEasing)',
         'smooth navigation transitions', 7),
    ])


def copy_ui_assets(src: Path) -> None:
    app = src / 'manager/app/src/main'
    if hashlib.sha256((ASSETS / 'res/font/oxanium.ttf').read_bytes()).hexdigest() != FONT_SHA256:
        raise RuntimeError('Oxanium font checksum mismatch')
    if hashlib.sha256((ASSETS / 'assets/licenses/Oxanium-OFL.txt').read_bytes()).hexdigest() != FONT_LICENSE_SHA256:
        raise RuntimeError('Oxanium license checksum mismatch')
    theme = app / 'java/com/rifsxd/ksunext/ui/theme'
    for file in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt', 'AppearanceControls.kt'):
        shutil.copy2(ASSETS / 'theme' / file, theme / file)
    device = app / 'java/com/rifsxd/ksunext/ui/device'
    device.mkdir(parents=True, exist_ok=True)
    for file in ('DeviceCheck.kt', 'DeviceMath.kt', 'DeviceSummary.kt'):
        shutil.copy2(ASSETS / 'device' / file, device / file)
    preflight = app / 'java/com/rifsxd/ksunext/ui/preflight'
    preflight.mkdir(parents=True, exist_ok=True)
    for file in ('PackagePreflight.kt', 'AndroidZipPreflight.kt'):
        shutil.copy2(ASSETS / 'preflight' / file, preflight / file)
    shutil.copy2(ASSETS / 'screen/DeviceCheckScreen.kt', app / 'java/com/rifsxd/ksunext/ui/screen/DeviceCheckScreen.kt')
    shutil.copy2(ASSETS / 'screen/FlashPreflight.kt', app / 'java/com/rifsxd/ksunext/ui/screen/FlashPreflight.kt')
    shutil.copytree(ASSETS / 'res', app / 'res', dirs_exist_ok=True)
    shutil.copytree(ASSETS / 'assets', app / 'assets', dirs_exist_ok=True)


def prepare_tree(src: Path) -> None:
    previous.prepare_tree(src)
    previous.patch_file(src / 'manager/build.gradle.kts', [
        ('val managerVersionCode by extra(40000)', f'val managerVersionCode by extra({VERSION_CODE})', '3.1 version code', 1),
        ('val managerVersionName by extra("3.0.0")', f'val managerVersionName by extra("{VERSION_NAME}")', '3.1 version name', 1),
    ])
    previous.patch_file(src / 'manager/app/build.gradle.kts', [
        ('output.outputFileName = "Synthetica-3.0-Neon-$name.apk"',
         'output.outputFileName = "Synthetica-3.1-Neon-$name.apk"', '3.1 filename', 1),
    ])
    app = src / 'manager/app/src/main'
    java = app / 'java/com/rifsxd/ksunext/ui'
    copy_ui_assets(src)
    patch_home(java / 'screen/Home.kt')
    patch_customization(java / 'screen/Customization.kt')
    patch_navigation_motion(java / 'MainActivity.kt')
    for file in ('Module.kt', 'ModuleRepo.kt', 'MetaModule.kt'):
        patch_theme_aware_banner(java / 'screen' / file)
    zip_patch.patch_module(java / 'screen/Module.kt')
    zip_patch.patch_install(java / 'screen/Install.kt')
    zip_patch.patch_main(java / 'MainActivity.kt')
    zip_patch.patch_flash(java / 'screen/Flash.kt')
    zip_patch.patch_ksu_cli(java / 'util/KsuCli.kt')
    for locale in ('values', 'values-in-rID'):
        path = app / 'res' / locale / 'strings_synthetica.xml'
        text = path.read_text(encoding='utf-8')
        text = previous.replace_exact(text, 'Neon Manager 3.0, UAPI v4', 'Neon Manager 3.1, UAPI v4', f'{locale} about version')
        path.write_text(text, encoding='utf-8')
    daemon = app / 'jniLibs/arm64-v8a/libksud.so'
    if hashlib.sha256(daemon.read_bytes()).hexdigest() != previous.EXPECTED_KSUD:
        raise RuntimeError('The prepared daemon differs from the pinned 3.0 daemon')
    print(f'[neon31] {APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI 4; unsigned build', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-patches-only', action='store_true')
    parser.add_argument('--source', type=Path, help='pinned, extracted source tree for patch-only verification')
    args = parser.parse_args()
    if args.verify_patches_only:
        if args.source is None or not args.source.is_dir():
            parser.error('--source must point to an extracted pinned source tree')
        with tempfile.TemporaryDirectory(prefix='synthetica-neon31-patch-') as tmp:
            src = Path(tmp) / 'source'
            shutil.copytree(args.source, src)
            prepare_tree(src)
        print('[done] Patch verification only; no APK built')
        return 0
    if args.source is not None:
        parser.error('--source is only supported for --verify-patches-only')
    work = previous.base.WORK_DIR.resolve()
    if work == Path('/') or work == Path.home() or work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise RuntimeError('Refusing unsafe Manager working directory')
    src = previous.base.prepare_source()
    prepare_tree(src)
    previous.base.zipalign_apk(previous.base.build_gradle(src))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
