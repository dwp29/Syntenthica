#!/usr/bin/env python3
"""Build the UAPI-4 Manager with Synthetica's 3.0 neon UI, unsigned.

Root-facing native code, the daemon and package ID remain the 2.0 baseline.
The original private signing key is not available to this builder: an unsigned
APK is not installable and cannot replace the Manager recognized by the kernel.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build-kit/scripts"))
import build_manager_source as base

NEON = ROOT / "build-kit/ci/ksun-neon"
BRANDING = ROOT / "build-kit/ci/branding-neon"
VERSION_NAME = "3.0.0"
VERSION_CODE = 40000
APP_ID = "net.ember.labs"
EXPECTED_DONOR = "d0aeef4c85cf1cfb720ddef8e7b7c0a2eefb6db1f4be4cb943b5ac017baad5aa"
EXPECTED_KSUD = "c305965796afb55ae8dad3a122935c995a818e07c637a9ef4c3e375202e4a427"


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchor(s), found {count}")
    return text.replace(old, new)


def patch_file(path: Path, changes: list[tuple[str, str, str, int]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new, label, expected in changes:
        text = replace_exact(text, old, new, label, expected)
    path.write_text(text, encoding="utf-8")


def check_baseline() -> None:
    if hashlib.sha256(base.BASE_APK.read_bytes()).hexdigest() != EXPECTED_DONOR:
        raise RuntimeError("The pinned UAPI-4 ksud donor APK has changed")
    with zipfile.ZipFile(base.BASE_APK) as donor:
        daemon = donor.read("lib/arm64-v8a/libksud.so")
    if hashlib.sha256(daemon).hexdigest() != EXPECTED_KSUD:
        raise RuntimeError("The pinned UAPI-4 daemon has changed")


def patch_versions(src: Path) -> None:
    root_gradle = src / "manager/build.gradle.kts"
    patch_file(root_gradle, [
        ('val managerVersionCode by extra(10000)', f'val managerVersionCode by extra({VERSION_CODE})', 'version code', 1),
        ('val managerVersionName by extra("2.0")', f'val managerVersionName by extra("{VERSION_NAME}")', 'version name', 1),
    ])
    app_gradle = src / "manager/app/build.gradle.kts"
    patch_file(app_gradle, [
        ('output.outputFileName = "Synthetica-2.0-$name.apk"',
         'output.outputFileName = "Synthetica-3.0-Neon-$name.apk"', 'APK filename', 1),
    ])
    text = app_gradle.read_text()
    if f'applicationId = "{APP_ID}"' not in text or "apksign {" in text or "signingConfig =" in text:
        raise RuntimeError("Wrong application ID or signing enabled in the unsigned build")


def patch_home(path: Path) -> None:
    seccomp_read = '''    val managerSeccompMode = remember {
        // PR_GET_SECCOMP is per-thread; this measures the Manager's UI thread only.
        runCatching { Os.prctl(21, 0, 0, 0, 0) }.getOrDefault(-1)
    }
    val managerSeccompLabel = stringResource(when (managerSeccompMode) {
        0 -> R.string.neon_seccomp_disabled
        1 -> R.string.neon_seccomp_strict
        2 -> R.string.neon_seccomp_filter
        -1 -> R.string.neon_seccomp_unavailable
        else -> R.string.neon_seccomp_unknown
    })
'''
    seccomp_row = '''                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Security,
                    badgeColor = if (managerSeccompMode == 2) IosGreenDark else IosOrangeDark,
                    title = stringResource(R.string.neon_seccomp_title),
                    subtitle = stringResource(R.string.neon_seccomp_subtitle),
                    value = managerSeccompLabel,
                )
'''
    patch_file(path, [
        ('import com.rifsxd.ksunext.Natives\n', 'import com.rifsxd.ksunext.BuildConfig\nimport com.rifsxd.ksunext.Natives\n', 'BuildConfig import', 1),
        ('val managerVerName: String = "2.0"', 'val managerVerName: String = BuildConfig.VERSION_NAME', 'default version name', 1),
        ('val managerVerCode: Long = 10000L', 'val managerVerCode: Long = BuildConfig.VERSION_CODE.toLong()', 'default version code', 1),
        ('getOrDefault("2.0" to 10000L)', 'getOrDefault(BuildConfig.VERSION_NAME to BuildConfig.VERSION_CODE.toLong())', 'version fallback', 2),
        ('packageInfo.versionName ?: "2.0"', 'packageInfo.versionName ?: BuildConfig.VERSION_NAME', 'package version fallback', 1),
        ('subtitle = "2.0  •  UAPI v$managerUAPIVersion"', 'subtitle = "${BuildConfig.VERSION_NAME}  •  UAPI v$managerUAPIVersion"', 'header version', 1),
        ('title = if (isManager) "Synthetica 2.0" else stringResource(R.string.home_not_installed)',
         'title = if (isManager) stringResource(R.string.neon_manager_title) else stringResource(R.string.home_not_installed)', 'honest hero title', 1),
        ('    val selinuxText = getSELinuxStatus()\n', '    val selinuxText = getSELinuxStatus()\n' + seccomp_read, 'per-thread seccomp read', 1),
        ('            // 3. APK 1.16 2x2 Control-Center Menu Grid\n',
         '            Text(text = stringResource(R.string.neon_quick_actions), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)\n\n            // Quick action menu; routing and root checks are unchanged.\n', 'quick actions section', 1),
        ('''                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.VisibilityOff,''',
         seccomp_row + '''                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.VisibilityOff,''', 'per-thread seccomp row', 1),
    ])


def patch_navigation(path: Path) -> None:
    patch_file(path, [
        ('import androidx.compose.foundation.layout.width\n', 'import androidx.compose.foundation.layout.width\nimport androidx.compose.foundation.selection.selectable\nimport androidx.compose.foundation.shape.CutCornerShape\n', 'navigation imports', 1),
        ('import androidx.compose.ui.graphics.Color\n', 'import androidx.compose.ui.graphics.Brush\nimport androidx.compose.ui.graphics.Color\n', 'gradient import', 1),
        ('import androidx.compose.ui.res.stringResource\n', 'import androidx.compose.ui.res.stringResource\nimport androidx.compose.ui.semantics.Role\n', 'tab semantics', 1),
        ('val dockShape = RoundedCornerShape(30.dp)', 'val dockShape = CutCornerShape(topStart = 8.dp, topEnd = 22.dp, bottomEnd = 8.dp, bottomStart = 22.dp)', 'dock outline', 1),
        ('val pillShape = RoundedCornerShape(24.dp)', 'val pillShape = CutCornerShape(topStart = 6.dp, topEnd = 14.dp, bottomEnd = 6.dp, bottomStart = 14.dp)', 'tab outline', 1),
        ('''                    .background(glass.dockActivePill)
                    .border(
                        width = 0.85.dp,
                        color = glass.borderHighlight.copy(alpha = if (glass.isDark) 0.42f else 0.90f),
                        shape = pillShape,
                    )''',
         '''                    .background(Brush.linearGradient(listOf(
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.25f),
                        MaterialTheme.colorScheme.secondary.copy(alpha = 0.12f),
                    )))
                    .border(
                        width = 1.dp,
                        brush = Brush.linearGradient(listOf(MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.secondary)),
                        shape = pillShape,
                    )''', 'glowing active tab', 1),
        ('''                            .clickable(
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null,
                            ) { navigateToIndex(index) },''',
         '''                            .selectable(
                                selected = isSelected,
                                role = Role.Tab,
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null,
                                onClick = { navigateToIndex(index) },
                            ),''', 'accessible tab selection', 1),
    ])


def patch_customization(path: Path) -> None:
    motion_row = '''                IosGroupDivider()
                IosSwitchRow(
                    icon = Icons.Rounded.AutoAwesome,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.neon_motion_title),
                    subtitle = stringResource(R.string.neon_motion_subtitle),
                    checked = NeonMotionState.value,
                    onCheckedChange = { setNeonMotion(context, it) },
                )
'''
    accent_group = '''            IosGroup(title = stringResource(R.string.neon_accent_group)) {
                NeonAccentOptions.forEachIndexed { index, option ->
                    if (index > 0) IosGroupDivider()
                    val selected = NeonAccentState.value == option.id
                    Row(
                        modifier = Modifier.fillMaxWidth().selectable(
                            selected = selected,
                            role = Role.RadioButton,
                            onClick = { setNeonAccent(context, option.id) },
                        ).padding(horizontal = 15.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        IosBadgeIcon(icon = Icons.Rounded.Palette, color = option.color)
                        Spacer(Modifier.width(13.dp))
                        Text(text = stringResource(option.label), modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                        RadioButton(selected = selected, onClick = null)
                    }
                }
            }

'''
    patch_file(path, [
        ('import androidx.compose.foundation.isSystemInDarkTheme\n', 'import androidx.compose.foundation.selection.selectable\n', 'radio semantics import', 1),
        ('import androidx.compose.foundation.layout.padding\n', 'import androidx.compose.foundation.layout.padding\nimport androidx.compose.foundation.layout.width\n', 'row width import', 1),
        ('import androidx.compose.material.icons.rounded.Contrast\n', 'import androidx.compose.material.icons.rounded.AutoAwesome\nimport androidx.compose.material.icons.rounded.Contrast\nimport androidx.compose.material.icons.rounded.Palette\n', 'motion and accent icons', 1),
        ('import androidx.compose.material3.Scaffold\n', 'import androidx.compose.material3.RadioButton\nimport androidx.compose.material3.Scaffold\n', 'radio button import', 1),
        ('import androidx.compose.ui.res.stringResource\n', 'import androidx.compose.ui.res.stringResource\nimport androidx.compose.ui.semantics.Role\n', 'radio role import', 1),
        ('import com.rifsxd.ksunext.ui.theme.GlassTopBar\n',
         'import com.rifsxd.ksunext.ui.theme.GlassTopBar\nimport com.rifsxd.ksunext.ui.theme.IosBadgeIcon\nimport com.rifsxd.ksunext.ui.theme.IosPinkDark\nimport com.rifsxd.ksunext.ui.theme.NeonAccentOptions\nimport com.rifsxd.ksunext.ui.theme.NeonAccentState\nimport com.rifsxd.ksunext.ui.theme.NeonMotionState\nimport com.rifsxd.ksunext.ui.theme.setNeonAccent\nimport com.rifsxd.ksunext.ui.theme.setNeonMotion\n', 'theme settings imports', 1),
        ('                if (isSystemInDarkTheme()) {\n', motion_row + '                run {\n', 'motion toggle and AMOLED setting', 1),
        ('            IosGroup(title = stringResource(R.string.synthetica_custom_layout_group)) {',
         accent_group + '            IosGroup(title = stringResource(R.string.synthetica_custom_layout_group)) {', 'accent selector', 1),
    ])


def patch_strings(res: Path) -> None:
    locales = {
        'values': {
            'ios_customization_sub': 'Language, neon effects, AMOLED and navigation',
            'ios_about_sub': 'Neon Manager 3.0, UAPI v4 and open-source credits',
            'synthetica_custom_glass_group': 'Neon display',
            'synthetica_amoled_glass_title': 'AMOLED black',
            'synthetica_amoled_glass_sub': 'Use a black OLED background',
            'synthetica_about_tagline': 'Cyberpunk neon kernel &amp; root manager',
            'extra': '''
    <string name="neon_back">Back</string>
    <string name="neon_manager_title">Synthetica Manager</string>
    <string name="neon_quick_actions">QUICK ACCESS</string>
    <string name="neon_motion_title">Neon motion</string>
    <string name="neon_motion_subtitle">Animated glow and scan lines; respects system animation settings</string>
    <string name="neon_accent_group">Neon accent</string>
    <string name="neon_accent_cyan">Cyan</string>
    <string name="neon_accent_pink">Pink</string>
    <string name="neon_accent_violet">Violet</string>
    <string name="neon_accent_lime">Lime</string>
    <string name="neon_seccomp_title">SECCOMP (UI thread)</string>
    <string name="neon_seccomp_subtitle">This Manager thread only; not a global status</string>
    <string name="neon_seccomp_filter">Filter</string>
    <string name="neon_seccomp_strict">Strict</string>
    <string name="neon_seccomp_disabled">Disabled</string>
    <string name="neon_seccomp_unavailable">Unavailable</string>
    <string name="neon_seccomp_unknown">Unknown</string>
''',
        },
        'values-in-rID': {
            'ios_customization_sub': 'Bahasa, efek neon, AMOLED dan navigasi',
            'ios_about_sub': 'Neon Manager 3.0, UAPI v4 dan kredit sumber terbuka',
            'synthetica_custom_glass_group': 'Tampilan neon',
            'synthetica_amoled_glass_title': 'Hitam AMOLED',
            'synthetica_amoled_glass_sub': 'Gunakan latar OLED hitam',
            'synthetica_about_tagline': 'Manajer kernel &amp; root cyberpunk neon',
            'extra': '''
    <string name="neon_back">Kembali</string>
    <string name="neon_manager_title">Synthetica Manager</string>
    <string name="neon_quick_actions">AKSES CEPAT</string>
    <string name="neon_motion_title">Animasi neon</string>
    <string name="neon_motion_subtitle">Glow dan garis bergerak; mengikuti pengaturan animasi sistem</string>
    <string name="neon_accent_group">Aksen neon</string>
    <string name="neon_accent_cyan">Sian</string>
    <string name="neon_accent_pink">Merah muda</string>
    <string name="neon_accent_violet">Ungu</string>
    <string name="neon_accent_lime">Lime</string>
    <string name="neon_seccomp_title">SECCOMP (utas UI)</string>
    <string name="neon_seccomp_subtitle">Hanya utas Manager ini, bukan status global</string>
    <string name="neon_seccomp_filter">Filter</string>
    <string name="neon_seccomp_strict">Ketat</string>
    <string name="neon_seccomp_disabled">Nonaktif</string>
    <string name="neon_seccomp_unavailable">Tidak tersedia</string>
    <string name="neon_seccomp_unknown">Tidak diketahui</string>
''',
        },
    }
    import re
    for locale, values in locales.items():
        path = res / locale / 'strings_synthetica.xml'
        text = path.read_text(encoding='utf-8')
        for name, value in values.items():
            if name == 'extra':
                continue
            pattern = rf'(<string name="{name}">).*?(</string>)'
            text, count = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), text)
            if count != 1:
                raise RuntimeError(f'{locale}: unexpected resource {name}: {count}')
        text = replace_exact(text, '</resources>', values['extra'] + '</resources>', f'{locale} neon strings')
        path.write_text(text, encoding='utf-8')


def apply_neon_assets(res: Path) -> None:
    for density in ('mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'):
        mip = res / f'mipmap-{density}'
        drawable = res / f'drawable-{density}'
        for src_name, dest_name in (
            (f'ic_launcher-{density}.png', 'ic_launcher.png'),
            (f'ic_launcher-{density}.png', 'ic_launcher_round.png'),
            (f'ic_foreground-{density}.png', 'ic_launcher_foreground.png'),
            (f'ic_background-{density}.png', 'ic_launcher_background.png'),
        ):
            shutil.copy2(BRANDING / src_name, mip / dest_name)
        shutil.copy2(BRANDING / f'ic_mono-{density}.png', drawable / 'ic_launcher_monochrome.png')
    shutil.copy2(BRANDING / 'ic_synthetica_emblem.png', res / 'drawable-nodpi/ic_synthetica_emblem.png')


def prepare_tree(src: Path) -> None:
    check_baseline()
    if 'KERNEL_SU_UAPI_VERSION = 4;' not in (src / 'uapi/supercall.h').read_text():
        raise RuntimeError('Expected the pinned UAPI 4 Manager source')
    base.apply_synthetica_patch(src)
    patch_versions(src)
    java = src / 'manager/app/src/main/java/com/rifsxd/ksunext'
    theme = java / 'ui/theme'
    for name in ('Color.kt', 'Theme.kt', 'Glass.kt', 'Shapes.kt', 'Type.kt'):
        shutil.copy2(NEON / 'theme' / name, theme / name)
    patch_home(java / 'ui/screen/Home.kt')
    patch_navigation(java / 'ui/MainActivity.kt')
    patch_customization(java / 'ui/screen/Customization.kt')
    res = src / 'manager/app/src/main/res'
    patch_strings(res)
    apply_neon_assets(res)
    daemon = src / 'manager/app/src/main/jniLibs/arm64-v8a/libksud.so'
    if hashlib.sha256(daemon.read_bytes()).hexdigest() != EXPECTED_KSUD:
        raise RuntimeError('Prepared daemon differs from the pinned release')
    print(f'[neon] {APP_ID} {VERSION_NAME} ({VERSION_CODE}); UAPI 4; unsigned build', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-patches-only', action='store_true')
    parser.add_argument('--source', type=Path, help='pinned, extracted source tree for patch-only verification')
    args = parser.parse_args()
    if args.verify_patches_only:
        if args.source is None or not args.source.is_dir():
            parser.error('--source must point to an extracted pinned source tree')
        with tempfile.TemporaryDirectory(prefix='synthetica-neon-patch-') as tmp:
            src = Path(tmp) / 'source'
            shutil.copytree(args.source, src)
            prepare_tree(src)
        print('[done] Patch verification only; no APK built')
        return 0
    if args.source is not None:
        parser.error('--source is only supported for --verify-patches-only')
    work = base.WORK_DIR.resolve()
    if work == Path('/') or work == Path.home() or work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise RuntimeError('Refusing unsafe Manager working directory')
    src = base.prepare_source()
    prepare_tree(src)
    base.zipalign_apk(base.build_gradle(src))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
