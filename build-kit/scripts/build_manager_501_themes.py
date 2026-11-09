#!/usr/bin/env python3
"""Build an UNSIGNED 5.0.1 Manager with distinct production-screen designs.

Layered on the reproducible 5.0/4.0 Manager: package ID, UAPI, root backend,
permissions and preferences are not changed. Signing is a separate local step.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_50_multitheme as base50

ASSETS = ROOT / 'build-kit/ci/ksun-themes501'
VERSION_NAME = '5.0.1'
VERSION_CODE = 60001
APP_ID = base50.APP_ID


def copy_theme(main: Path) -> None:
    theme = main / 'java/com/rifsxd/ksunext/ui/theme'
    for asset in sorted((ASSETS / 'theme').glob('*.kt')):
        shutil.copy2(asset, theme / asset.name)
    shutil.copytree(ASSETS / 'res', main / 'res', dirs_exist_ok=True)


def patch_production_dock(activity: Path) -> None:
    patch = base50.previous.previous.patch_file
    patch(activity, [
        ('import com.rifsxd.ksunext.ui.theme.LocalGlassStyle\n',
         'import com.rifsxd.ksunext.ui.theme.LocalGlassStyle\n'
         'import com.rifsxd.ksunext.ui.theme.LocalManagerStyle\n'
         'import com.rifsxd.ksunext.ui.theme.managerDockSpec\n', '5.0.1 dock imports', 1),
        ('    val pixelMotion = LocalPixelMotionEnabled.current\n    val navigator = navController.rememberDestinationsNavigator()',
         '    val pixelMotion = LocalPixelMotionEnabled.current\n'
         '    val dockSpec = managerDockSpec(LocalManagerStyle.current)\n'
         '    val navigator = navController.rememberDestinationsNavigator()', '5.0.1 dock geometry', 1),
        ('                val lastValidNavbarSelection = remember { mutableStateOf(0) }\n',
         '                val lastValidNavbarSelection = remember { mutableStateOf(0) }\n'
         '                // Do not leave the dock hidden after returning from a scrolled screen.\n'
         '                LaunchedEffect(currentRoute) { isScrollingDown.value = false }\n',
         '5.0.1 restore dock on destination change', 1),
        ('.padding(horizontal = 18.dp, vertical = 12.dp),\n        contentAlignment = Alignment.Center,\n    ) {\n        val dockShape = MaterialTheme.shapes.extraLarge',
         '.padding(horizontal = dockSpec.horizontalMargin, vertical = dockSpec.verticalMargin),\n'
         '        contentAlignment = Alignment.Center,\n    ) {\n        val dockShape = dockSpec.containerShape',
         '5.0.1 dock margins and shape', 1),
        ('.width(dockWidth)\n                .height(68.dp)\n                .iosGlass(',
         '.width(dockWidth)\n                .height(dockSpec.height)\n                .iosGlass(', '5.0.1 dock height', 1),
        ('val pillShape = MaterialTheme.shapes.medium', 'val pillShape = dockSpec.selectedShape', '5.0.1 dock selection', 1),
        ('text = stringResource(destination.label),\n                            fontSize = 10.5.sp,',
         'text = stringResource(destination.label).let { if (dockSpec.uppercaseLabels) it.uppercase() else it },\n'
         '                            fontSize = 10.5.sp,', '5.0.1 dock labels', 1),
    ])


def patch_about(about: Path) -> None:
    patch = base50.previous.previous.patch_file
    patch(about, [
        ('import com.rifsxd.ksunext.ui.theme.GlassTopBar\n',
         'import com.rifsxd.ksunext.ui.theme.GlassTopBar\n'
         'import com.rifsxd.ksunext.ui.theme.LocalManagerStyle\n'
         'import com.rifsxd.ksunext.ui.theme.ManagerStyle\n'
         'import com.rifsxd.ksunext.ui.theme.emblemResForStyle\n', '5.0.1 about theme imports', 1),
        ('val iconShape = RoundedCornerShape(24.dp)\n                Image(\n                    painter = painterResource(R.drawable.ic_synthetica_emblem),',
         'val activeStyle = LocalManagerStyle.current\n                val iconShape = if (activeStyle == ManagerStyle.PIXEL) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.extraLarge\n                Image(\n                    painter = painterResource(emblemResForStyle(activeStyle)),',
         '5.0.1 about theme PNG emblem', 1),
    ])


def prepare_tree(src: Path) -> None:
    base50.prepare_tree(src)
    patch = base50.previous.previous.patch_file
    patch(src / 'manager/build.gradle.kts', [
        ('val managerVersionCode by extra(60000)', f'val managerVersionCode by extra({VERSION_CODE})', '5.0.1 version code', 1),
        ('val managerVersionName by extra("5.0.0")', f'val managerVersionName by extra("{VERSION_NAME}")', '5.0.1 version name', 1),
    ])
    patch(src / 'manager/app/build.gradle.kts', [
        ('output.outputFileName = "Synthetica-5.0-MultiTheme-$name.apk"',
         'output.outputFileName = "Synthetica-5.0.1-MultiTheme-$name.apk"', '5.0.1 output name', 1),
    ])
    main = src / 'manager/app/src/main'
    copy_theme(main)
    patch_production_dock(main / 'java/com/rifsxd/ksunext/ui/MainActivity.kt')
    patch_about(main / 'java/com/rifsxd/ksunext/ui/screen/About.kt')
    for locale, value in (
        ('values', 'Manager 5.0.1, UAPI v4 and open-source credits'),
        ('values-in-rID', 'Manager 5.0.1, UAPI v4 dan kredit sumber terbuka'),
    ):
        base50.replace_string(main / 'res' / locale / 'strings_synthetica.xml', 'ios_about_sub', value)
    daemon = main / 'jniLibs/arm64-v8a/libksud.so'
    if hashlib.sha256(daemon.read_bytes()).hexdigest() != base50.previous.previous.EXPECTED_KSUD:
        raise RuntimeError('Root daemon differs from the pinned 4.0/5.0 baseline')
    print(f'[themes501] {APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI 4; unsigned', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-patches-only', action='store_true')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if args.verify_patches_only:
        if args.source is None or not args.source.is_dir():
            parser.error('--source must point to an extracted pinned source tree')
        with tempfile.TemporaryDirectory(prefix='synthetica-501-patch-') as temp:
            source = Path(temp) / 'source'
            shutil.copytree(args.source, source)
            prepare_tree(source)
        print('[done] 5.0.1 patch verification only; no APK built')
        return 0
    if args.source is not None:
        parser.error('--source is only supported for --verify-patches-only')
    base = base50.previous.previous.base
    work = base.WORK_DIR.resolve()
    if work == Path('/') or work == Path.home() or work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise RuntimeError('Refusing unsafe Manager working directory')
    source = base.prepare_source()
    prepare_tree(source)
    base.zipalign_apk(base.build_gradle(source))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
