#!/usr/bin/env python3
"""Prepare/build the UNSIGNED 4.0 Pixel Manager on the verified UAPI-4 base.

3.1 remains independently reproducible. This layer changes UI and adds the
explicitly confirmed, opt-in helpers; it does not change native authorization,
UAPI, daemon, package ID, permissions, installer, or ZIP-preflight engine.
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
import build_manager_31_neon as neon31

previous = neon31.previous
ASSETS = ROOT / 'build-kit/ci/ksun-pixel40'
VERSION_NAME = '4.0.0'
VERSION_CODE = 50000
FONT_HASHES = {
    'res/font/silkscreen_regular.ttf': 'c845473330b94c2079ce9af01c51ac8ba2d99c24f4d14c039843bbb8e642ebd8',
    'res/font/silkscreen_bold.ttf': '768476aa712d4f5c3e18d3bce80f980a8bd3f72b7094d22ec5e768df3acfed61',
    'assets/licenses/Silkscreen-OFL.txt': '86c5e9c9382cdcc5948704fdfe60f2aa164a719746931219a42736ecd9cefbd3',
}


def copy_assets(src: Path) -> None:
    for name, expected in FONT_HASHES.items():
        if hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Pixel font/license checksum mismatch: {name}')
    app = src / 'manager/app/src/main'
    ui = app / 'java/com/rifsxd/ksunext/ui'
    for directory in ('theme', 'screen', 'util', 'pixel'):
        target = ui / directory
        target.mkdir(parents=True, exist_ok=True)
        for item in (ASSETS / directory).glob('*.kt'):
            shutil.copy2(item, target / item.name)
    shutil.copytree(ASSETS / 'res', app / 'res', dirs_exist_ok=True)
    shutil.copytree(ASSETS / 'assets', app / 'assets', dirs_exist_ok=True)
    for density in ('mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'):
        mipmap = app / f'res/mipmap-{density}'
        drawable = app / f'res/drawable-{density}'
        mipmap.mkdir(parents=True, exist_ok=True)
        drawable.mkdir(parents=True, exist_ok=True)
        for source, target in ((f'ic_launcher-{density}.png', 'ic_launcher.png'),
                               (f'ic_launcher-{density}.png', 'ic_launcher_round.png'),
                               (f'ic_foreground-{density}.png', 'ic_launcher_foreground.png'),
                               (f'ic_background-{density}.png', 'ic_launcher_background.png')):
            shutil.copy2(ASSETS / 'branding' / source, mipmap / target)
        shutil.copy2(ASSETS / 'branding' / f'ic_mono-{density}.png', drawable / 'ic_launcher_monochrome.png')
    shutil.copy2(ASSETS / 'branding/ic_synthetica_emblem.png', app / 'res/drawable-nodpi/ic_synthetica_emblem.png')


def patch_home(path: Path) -> None:
    previous.patch_file(path, [
        ('import com.ramcosta.composedestinations.generated.destinations.DeviceCheckScreenDestination\n',
         'import com.ramcosta.composedestinations.generated.destinations.DeviceCheckScreenDestination\n'
         'import com.ramcosta.composedestinations.generated.destinations.PixelDiagnostics40ScreenDestination\n'
         'import com.ramcosta.composedestinations.generated.destinations.PixelControl40ScreenDestination\n',
         '4.0 quick-tool routes', 1),
        ('import com.rifsxd.ksunext.ui.theme.GlassTopBar\n',
         'import com.rifsxd.ksunext.ui.theme.GlassTopBar\n'
         'import com.rifsxd.ksunext.ui.theme.LocalPixelMotionEnabled\n', 'home motion import', 1),
        ('val zygiskLabel: String = "Disabled"', 'val zygiskLabel: String = "Not reported in Manager"', 'zygisk default', 1),
        ('else -> "OverlayFS / Built-in"', 'else -> "Not reported"', 'unknown metamodule is not presumed', 1),
        ('zygiskOn -> "Enabled"\n                else -> "Disabled"',
         'zygiskOn -> "Reported in Manager"\n                else -> "Not reported in Manager"', 'zygisk flag scope', 1),
        ('envInfo.suSFSVersion.ifBlank { stringResource(R.string.ios_home_on) }',
         'envInfo.suSFSVersion.ifBlank { stringResource(R.string.pixel40_supported_short) }', 'SuSFS support pill', 1),
        ('stringResource(R.string.ios_home_off)\n            }\n\n            IosGroup(title = stringResource(R.string.ios_home_status))',
         'stringResource(R.string.pixel40_unavailable_short)\n            }\n\n            IosGroup(title = stringResource(R.string.ios_home_status))',
         'SuSFS unknown is not off', 1),
        ('''            IosGroup(title = stringResource(R.string.ios_quick_utilities)) {
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,''',
         '''            IosGroup(title = stringResource(R.string.ios_quick_utilities)) {
                IosRow(
                    icon = Icons.Rounded.Hub,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.pixel40_diagnostics_title),
                    subtitle = stringResource(R.string.pixel40_diagnostics_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(PixelDiagnostics40ScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Speed,
                    badgeColor = IosOrangeDark,
                    title = stringResource(R.string.pixel40_control_title),
                    subtitle = stringResource(R.string.pixel40_control_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(PixelControl40ScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,''', '4.0 quick tools', 1),
        ('import androidx.compose.material.icons.rounded.Security\n',
         'import androidx.compose.material.icons.rounded.Security\nimport androidx.compose.material.icons.rounded.Speed\n', 'control icon', 1),
        ('''                AnimatedVisibility(
                    visible = detailsExpanded,
                    enter = expandVertically() + fadeIn(),
                    exit = shrinkVertically() + fadeOut(),''',
         '''                val pixelMotion = LocalPixelMotionEnabled.current
                AnimatedVisibility(
                    visible = detailsExpanded,
                    enter = if (pixelMotion) expandVertically() + fadeIn() else androidx.compose.animation.EnterTransition.None,
                    exit = if (pixelMotion) shrinkVertically() + fadeOut() else androidx.compose.animation.ExitTransition.None,''',
         'home details motion', 1),
    ])


def patch_repo(path: Path) -> None:
    previous.patch_file(path, [
        ('import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination\n',
         'import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination\n'
         'import com.ramcosta.composedestinations.generated.destinations.PixelSources40ScreenDestination\n', 'sources route', 1),
        ('        topBar = {\n            SearchAppBar(', '        topBar = {\n            Column {\n            SearchAppBar(', 'source link container', 1),
        ('''                scrollBehavior = scrollBehavior
            )
        },
        snackbarHost = { SnackbarHost(snackBarHost, modifier = Modifier.padding(bottom = navBarPadding)) },''',
         '''                scrollBehavior = scrollBehavior
            )
            TextButton(
                modifier = Modifier.fillMaxWidth(),
                onClick = { navigator.navigate(PixelSources40ScreenDestination) },
            ) {
                Icon(Icons.Filled.Public, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.pixel40_sources_action))
            }
            }
        },
        snackbarHost = { SnackbarHost(snackBarHost, modifier = Modifier.padding(bottom = navBarPadding)) },''', 'visible curated-sources link', 1),
    ])


def patch_profile(path: Path) -> None:
    previous.patch_file(path, [
        ('''    val isRootGranted = profile.allowSu

    Column(modifier = modifier) {''',
         '''    val isRootGranted = profile.allowSu
    var confirmRootGrant by remember(packageName) { mutableStateOf(false) }
    if (confirmRootGrant) {
        AlertDialog(
            onDismissRequest = { confirmRootGrant = false },
            title = { Text(stringResource(R.string.pixel40_grant_title)) },
            text = { Text(stringResource(R.string.pixel40_grant_message, appLabel, packageName)) },
            confirmButton = {
                TextButton(onClick = { confirmRootGrant = false; onProfileChange(profile.copy(allowSu = true)) }) {
                    Text(stringResource(R.string.pixel40_grant_confirm))
                }
            },
            dismissButton = { TextButton(onClick = { confirmRootGrant = false }) { Text(stringResource(R.string.pixel40_action_cancel)) } },
        )
    }

    Column(modifier = modifier) {''', 'explicit root-grant confirmation', 1),
        ('onCheckedChange = { onProfileChange(profile.copy(allowSu = it)) },',
         'onCheckedChange = { enabled ->\n                if (enabled && !isRootGranted) confirmRootGrant = true\n                else onProfileChange(profile.copy(allowSu = enabled))\n            },',
         'confirm grant, immediate revoke', 1),
    ])


def patch_main_motion(path: Path) -> None:
    previous.patch_file(path, [
        ('import androidx.compose.animation.core.Spring\n', 'import androidx.compose.animation.core.Spring\nimport androidx.compose.animation.core.snap\n', 'snap import', 1),
        ('import com.rifsxd.ksunext.ui.theme.GlassSplash\n',
         'import com.rifsxd.ksunext.ui.theme.GlassSplash\nimport com.rifsxd.ksunext.ui.theme.LocalPixelMotionEnabled\n', 'pixel motion import', 1),
        ('KernelSUTheme(amoledMode = amoledModeState.value) {\n                val wallpaperLayer',
         'KernelSUTheme(amoledMode = amoledModeState.value) {\n                val pixelMotion = LocalPixelMotionEnabled.current\n                val wallpaperLayer', 'theme motion', 1),
        ('LaunchedEffect(appLockState.value) {\n                    if (!appLockState.value && showSplash) {\n                        delay(1150L)',
         'LaunchedEffect(appLockState.value, pixelMotion) {\n                    if (!appLockState.value && showSplash) {\n                        delay(if (pixelMotion) 650L else 0L)', 'motion-aware splash', 1),
        ('''                                            when {
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) 1 else -1''',
         '''                                            when {
                                                !pixelMotion -> EnterTransition.None
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) 1 else -1''', 'enter motion', 1),
        ('''                                            when {
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) -1 else 1''',
         '''                                            when {
                                                !pixelMotion -> ExitTransition.None
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) -1 else 1''', 'exit motion', 1),
        ('''                                            slideInHorizontally(initialOffsetX = { -it / 3 }, animationSpec = tween(300, easing = FastOutSlowInEasing)) + fadeIn(tween(220))
                                        }''',
         '''                                            if (!pixelMotion) EnterTransition.None else
                                                slideInHorizontally(initialOffsetX = { -it / 3 }, animationSpec = tween(300, easing = FastOutSlowInEasing)) + fadeIn(tween(220))
                                        }''', 'pop enter motion', 1),
        ('''                                            slideOutHorizontally(targetOffsetX = { it }, animationSpec = tween(300, easing = FastOutSlowInEasing)) + fadeOut(tween(200))
                                        }''',
         '''                                            if (!pixelMotion) ExitTransition.None else
                                                slideOutHorizontally(targetOffsetX = { it }, animationSpec = tween(300, easing = FastOutSlowInEasing)) + fadeOut(tween(200))
                                        }''', 'pop exit motion', 1),
        ('enter = slideInVertically(initialOffsetY = { it }) + fadeIn(tween(220)),',
         'enter = if (pixelMotion) slideInVertically(initialOffsetY = { it }) + fadeIn(tween(220)) else EnterTransition.None,', 'dock enter motion', 1),
        ('exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(tween(180)),',
         'exit = if (pixelMotion) slideOutVertically(targetOffsetY = { it }) + fadeOut(tween(180)) else ExitTransition.None,', 'dock exit motion', 1),
        ('    val glass = LocalGlassStyle.current\n    val navigator = navController.rememberDestinationsNavigator()',
         '    val glass = LocalGlassStyle.current\n    val pixelMotion = LocalPixelMotionEnabled.current\n    val navigator = navController.rememberDestinationsNavigator()', 'dock motion state', 1),
        ('animationSpec = if (isDraggingPill) {\n            spring(',
         'animationSpec = if (!pixelMotion) {\n            snap()\n        } else if (isDraggingPill) {\n            spring(', 'dock selected motion', 1),
        ('CutCornerShape(topStart = 8.dp, topEnd = 22.dp, bottomEnd = 8.dp, bottomStart = 22.dp)', 'CutCornerShape(5.dp)', 'pixel dock', 1),
        ('CutCornerShape(topStart = 6.dp, topEnd = 14.dp, bottomEnd = 6.dp, bottomStart = 14.dp)', 'CutCornerShape(4.dp)', 'pixel dock selection', 1),
    ])


def patch_labels(src: Path) -> None:
    res = src / 'manager/app/src/main/res'
    replacements = {
        'values': {
            'Root hiding (SuSFS)': 'SuSFS kernel support',
            'Conceals root mounts &amp; paths from apps': 'Reported features only; active hiding is unverified',
            'Language, neon effects, AMOLED and navigation': 'Language, pixel motion, AMOLED and navigation',
            'Neon Manager 3.1, UAPI v4': 'Pixel Manager 4.0, UAPI v4',
            'Neon display': 'Pixel display',
            'Cyberpunk neon kernel &amp; root manager': 'Pixel-inspired kernel &amp; root manager',
            'Applied safely in userspace via /data/adb/service.d/synthetica-boost.sh without kernel overclock or thermal changes.': 'Runtime tuning is optional and hardware-dependent.',
            'Default stock codec gain is 84. Values between 88 and 92 provide cleaner headroom without speaker clipping.': 'Mixer defaults vary by device. High gain can damage hearing.',
            'Neon motion': 'Pixel motion',
            'Animated glow and scan lines; respects system animation settings': 'Animated signal and navigation; respects system animation settings',
            'Neon accent': 'Signal accent',
            '>Cyan</string>': '>Signal red</string>',
            '>Pink</string>': '>Monochrome</string>',
            '>Violet</string>': '>Amber</string>',
            '>Lime</string>': '>Mint</string>',
        },
        'values-in-rID': {
            'Penyamaran (SuSFS)': 'Dukungan kernel SuSFS',
            'Menyembunyikan mount &amp; jejak root dari aplikasi': 'Hanya fitur yang dilaporkan; penyembunyian aktif belum diverifikasi',
            'Bahasa, efek neon, AMOLED dan navigasi': 'Bahasa, animasi pixel, AMOLED dan navigasi',
            'Neon Manager 3.1, UAPI v4': 'Pixel Manager 4.0, UAPI v4',
            'Tampilan neon': 'Tampilan pixel',
            'Manajer kernel &amp; root cyberpunk neon': 'Manajer kernel &amp; root bergaya pixel',
            'Diterapkan aman di userspace lewat /data/adb/service.d/synthetica-boost.sh tanpa overclock atau ubahan termal.': 'Tuning runtime opsional dan tergantung perangkat.',
            'Gain bawaan pabrik adalah 84. Nilai 88–92 memberi suara lebih lantang dan jernih tanpa distorsi speaker.': 'Gain bawaan berbeda tiap perangkat. Gain tinggi dapat merusak pendengaran.',
            'Animasi neon': 'Animasi pixel',
            'Glow dan garis bergerak; mengikuti pengaturan animasi sistem': 'Animasi sinyal dan navigasi; mengikuti pengaturan sistem',
            'Aksen neon': 'Aksen sinyal',
            '>Sian</string>': '>Merah sinyal</string>',
            '>Merah muda</string>': '>Monokrom</string>',
            '>Ungu</string>': '>Amber</string>',
            '>Lime</string>': '>Mint</string>',
        },
    }
    for locale, entries in replacements.items():
        file = res / locale / 'strings_synthetica.xml'
        text = file.read_text(encoding='utf-8')
        for old, new in entries.items():
            text = previous.replace_exact(text, old, new, f'{locale} {old}')
        file.write_text(text, encoding='utf-8')
        file = res / locale / 'strings_neon31.xml'
        text = file.read_text(encoding='utf-8')
        old = 'Neon glow' if locale == 'values' else 'Cahaya neon'
        new = 'Signal intensity' if locale == 'values' else 'Intensitas sinyal'
        file.write_text(previous.replace_exact(text, old, new, f'{locale} signal intensity'), encoding='utf-8')


def prepare_tree(src: Path) -> None:
    neon31.prepare_tree(src)
    previous.patch_file(src / 'manager/build.gradle.kts', [
        ('val managerVersionCode by extra(41000)', f'val managerVersionCode by extra({VERSION_CODE})', '4.0 version code', 1),
        ('val managerVersionName by extra("3.1.0")', f'val managerVersionName by extra("{VERSION_NAME}")', '4.0 version name', 1),
    ])
    previous.patch_file(src / 'manager/app/build.gradle.kts', [
        ('output.outputFileName = "Synthetica-3.1-Neon-$name.apk"',
         'output.outputFileName = "Synthetica-4.0-Pixel-$name.apk"', '4.0 filename', 1),
    ])
    copy_assets(src)
    ui = src / 'manager/app/src/main/java/com/rifsxd/ksunext/ui'
    patch_home(ui / 'screen/Home.kt')
    patch_repo(ui / 'screen/ModuleRepo.kt')
    patch_profile(ui / 'screen/AppProfile.kt')
    patch_main_motion(ui / 'MainActivity.kt')
    patch_labels(src)
    daemon = src / 'manager/app/src/main/jniLibs/arm64-v8a/libksud.so'
    if hashlib.sha256(daemon.read_bytes()).hexdigest() != previous.EXPECTED_KSUD:
        raise RuntimeError('Unexpected root daemon')
    print(f'[pixel40] {neon31.APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI 4; unsigned', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-patches-only', action='store_true')
    parser.add_argument('--source', type=Path, help='pinned extracted source for patch-only verification')
    args = parser.parse_args()
    if args.verify_patches_only:
        if args.source is None or not args.source.is_dir():
            parser.error('--source must point to an extracted pinned source tree')
        with tempfile.TemporaryDirectory(prefix='synthetica-pixel40-patch-') as temp:
            source = Path(temp) / 'source'
            shutil.copytree(args.source, source)
            prepare_tree(source)
        print('[done] 4.0 patch verification only; no APK built')
        return 0
    if args.source is not None:
        parser.error('--source is only supported for --verify-patches-only')
    work = previous.base.WORK_DIR.resolve()
    if work == Path('/') or work == Path.home() or work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise RuntimeError('Refusing unsafe Manager working directory')
    source = previous.base.prepare_source()
    prepare_tree(source)
    previous.base.zipalign_apk(previous.base.build_gradle(source))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
