#!/usr/bin/env python3
"""Cyberbrutalist UI patcher adapted from the Synthetica 2.1 source archive.

This file contains UI/build overlays only. Signing is performed locally and separately.
The caller pins KernelSU-Next to the UAPI v4 revision used by Synthetica 2.0.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "ci" / "ksun-cyberbrutal"
BRANDING = ROOT / "ci" / "branding-cyberbrutal"
OUT = ROOT / "artifacts" / "manager-cyberbrutal"
WORK = Path(os.environ.get("SP_WORK_DIR", "/tmp/sp-manager-cyberbrutal")).resolve()
VERSION = os.environ.get("SP_RELEASE_VERSION", "2.1")
OUT_NAME = os.environ.get("SP_APK_FILENAME", f"Synthetica-{VERSION}-Cyberbrutal.apk")
PKG = os.environ.get("SP_MANAGER_PKG", "net.ember.labs")

UPSTREAM = {
    "repo": "KernelSU-Next/KernelSU-Next",
    "commit": "ea51427ff700f73909e7e8c8717cc3241322ee1e",
}


def say(m: str) -> None:
    print(m, flush=True)


def run(cmd, cwd=None, env=None, check=True):
    say("$ " + " ".join(str(c) for c in cmd) + (f"  (cwd={cwd})" if cwd else ""))
    p = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    tail = "\n".join((p.stdout or "").splitlines()[-30:])
    if tail:
        say(tail)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd)}")
    return p


def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    assert old in text, f"[patch-miss] anchor not found for {label}"
    out = text.replace(old, new, count)
    assert out != text, f"[patch-noop] replacement produced no diff for {label}"
    return out


def fetch_source() -> Path:
    src = WORK / "ksun"
    if src.exists():
        shutil.rmtree(src)
    WORK.mkdir(parents=True, exist_ok=True)

    # Support offline / pre-bundled source directory in external Drive package
    local_dir = os.environ.get("SP_KSUN_SOURCE_DIR", "")
    if local_dir and Path(local_dir).is_dir():
        say(f"[source] copying pre-bundled source from {local_dir}")
        shutil.copytree(local_dir, src)
        return src

    tar = WORK / "ksun.tar.gz"
    local_tar = os.environ.get("SP_KSUN_TAR", "")
    if local_tar and Path(local_tar).is_file():
        shutil.copyfile(local_tar, tar)

    url = f"https://codeload.github.com/{UPSTREAM['repo']}/tar.gz/{UPSTREAM['commit']}"
    if not tar.exists():
        say(f"[fetch] {url}")
        with urllib.request.urlopen(url, timeout=900) as r, tar.open("wb") as f:
            shutil.copyfileobj(r, f)
    if tar.stat().st_size < 1_000_000:
        raise RuntimeError("source archive looks truncated")
    with tarfile.open(tar) as t:
        t.extractall(WORK)
    extracted = next(WORK.glob("KernelSU-Next-*"), None)
    if extracted is None:
        raise RuntimeError("unexpected archive layout")
    extracted.rename(src)
    return src


def apply_overlays(src: Path) -> None:
    app = src / "manager/app/src/main/java/com/rifsxd/ksunext"
    mapping = {
        OVERLAY / "theme/Color.kt": app / "ui/theme/Color.kt",
        OVERLAY / "theme/Shapes.kt": app / "ui/theme/Shapes.kt",
        OVERLAY / "theme/Type.kt": app / "ui/theme/Type.kt",
        OVERLAY / "theme/Theme.kt": app / "ui/theme/Theme.kt",
        OVERLAY / "theme/BrutalMotion.kt": app / "ui/theme/BrutalMotion.kt",
        OVERLAY / "screen/BottomBarDestination.kt": app / "ui/screen/BottomBarDestination.kt",
        OVERLAY / "screen/SyntheticaControl.kt": app / "ui/screen/SyntheticaControl.kt",
        OVERLAY / "screen/BoostLegacy.kt": app / "ui/screen/BoostLegacy.kt",
        OVERLAY / "component/AboutCard.kt": app / "ui/component/AboutCard.kt",
        OVERLAY / "component/SearchBar.kt": app / "ui/component/SearchBar.kt",
        OVERLAY / "component/SettingsItem.kt": app / "ui/component/SettingsItem.kt",
    }
    for s, d in mapping.items():
        assert s.is_file(), f"missing overlay source: {s}"
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
    say(f"[overlay] copied {len(mapping)} Cyberbrutalist Kotlin files (theme + motion + 5th Control tab + components)")


def patch_main_activity(src: Path) -> None:
    f = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt"
    s = f.read_text()

    # 1. Live CyberBrutalBackdrop inside KernelSUTheme so it reacts to Dark/Light/AMOLED switches
    s = must_replace(
        s,
        "            KernelSUTheme(amoledMode = amoledModeState.value) {",
        "            KernelSUTheme(amoledMode = amoledModeState.value) {\n"
        "                com.rifsxd.ksunext.ui.theme.CyberBrutalBackdrop()",
        "MainActivity backdrop",
    )

    # 2. Smoother splash -> main transition + BrutalSplash boot sequence
    s = must_replace(
        s,
        "                    transitionSpec = {\n"
        "                        fadeIn(animationSpec = tween(180)) togetherWith fadeOut(animationSpec = tween(180))\n"
        "                    },",
        "                    transitionSpec = {\n"
        "                        (fadeIn(animationSpec = tween(260)) + scaleIn(initialScale = 0.96f, animationSpec = tween(260))) togetherWith\n"
        "                            (fadeOut(animationSpec = tween(220)) + scaleOut(targetScale = 1.02f, animationSpec = tween(220)))\n"
        "                    },",
        "MainActivity splash transition",
    )

    old_splash_box = """                    if (isSplashVisible) {
                        Box(
                            modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Icon(
                                    painter = painterResource(R.drawable.ic_ksu_next),
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier
                                        .size(120.dp)
                                        .graphicsLayer { rotationZ = splashRotation }
                                )
                            }
                        }
                    }"""
    new_splash_box = """                    if (isSplashVisible) {
                        com.rifsxd.ksunext.ui.theme.BrutalSplash(
                            progress = (splashRotation / (360f * 6f)).coerceIn(0f, 1f)
                        )
                    }"""
    s = must_replace(s, old_splash_box, new_splash_box, "MainActivity BrutalSplash")

    # 3. Transparent root Scaffold so CyberBrutalBackdrop shines behind all screens
    s = must_replace(
        s,
        "                        Scaffold(\n"
        "                            contentWindowInsets = WindowInsets(0, 0, 0, 0)\n"
        "                        )",
        "                        Scaffold(\n"
        "                            containerColor = androidx.compose.ui.graphics.Color.Transparent,\n"
        "                            contentWindowInsets = WindowInsets(0, 0, 0, 0)\n"
        "                        )",
        "MainActivity transparent Scaffold",
    )

    # 4. Crisp slide + fade transitions across all NavHost destinations
    s = s.replace(
        "animationSpec = tween(300))",
        "animationSpec = tween(250)) + fadeIn(animationSpec = tween(210))",
    )
    # Fix exit transitions where fadeOut is required instead of fadeIn
    s = s.replace(
        "slideOutHorizontally(targetOffsetX = { it * offsetSign }, animationSpec = tween(250)) + fadeIn(animationSpec = tween(210))",
        "slideOutHorizontally(targetOffsetX = { it * offsetSign }, animationSpec = tween(250)) + fadeOut(animationSpec = tween(180))",
    )
    s = s.replace(
        "slideOutHorizontally(targetOffsetX = { -it * animationDirection }, animationSpec = tween(250)) + fadeIn(animationSpec = tween(210))",
        "slideOutHorizontally(targetOffsetX = { -it * animationDirection }, animationSpec = tween(250)) + fadeOut(animationSpec = tween(180))",
    )
    s = s.replace(
        "slideOutHorizontally(targetOffsetX = { it * animationDirection }, animationSpec = tween(250)) + fadeIn(animationSpec = tween(210))",
        "slideOutHorizontally(targetOffsetX = { it * animationDirection }, animationSpec = tween(250)) + fadeOut(animationSpec = tween(180))",
    )
    # Some UAPI-v4 detail routes use literal +/-it rather than offsetSign.
    s = re.sub(
        r'(slideOutHorizontally\([^\n]*?\)) \+ fadeIn\(animationSpec = tween\(210\)\)',
        r'\1 + fadeOut(animationSpec = tween(180))',
        s,
    )
    assert not re.search(r'slideOutHorizontally\([^\n]*\) \+ fadeIn\(', s), "exit transition has EnterTransition"
    assert "slideOutHorizontally" in s and "fadeOut(animationSpec = tween(180))" in s, "nav transition patch failed"

    # 5. Cyberbrutalist Chamfered 5-Tab BottomBar Dock with Acid-Volt active block
    old_dock = """            Surface(
                modifier = Modifier.wrapContentWidth(),
                shape = RoundedCornerShape(24.dp),
                tonalElevation = 3.dp,
                shadowElevation = 8.dp
            ) {
                val itemSize = 56.dp
                val itemSpacing = 4.dp
                val containerPadding = 7.dp"""
    new_dock = """            Surface(
                modifier = Modifier.wrapContentWidth(),
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.94f),
                border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                tonalElevation = 0.dp,
                shadowElevation = 10.dp
            ) {
                val itemSize = if (visibleDestinations.size >= 5) 50.dp else 56.dp
                val itemSpacing = 4.dp
                val containerPadding = 7.dp"""
    s = must_replace(s, old_dock, new_dock, "BottomBar Cyberbrutal Surface")

    s = must_replace(
        s,
        "                                        .background(\n"
        "                                            color = MaterialTheme.colorScheme.secondaryContainer,\n"
        "                                            shape = RoundedCornerShape(16.dp)\n"
        "                                        )",
        "                                        .background(\n"
        "                                            color = MaterialTheme.colorScheme.primary,\n"
        "                                            shape = MaterialTheme.shapes.small\n"
        "                                        )",
        "BottomBar Volt indicator",
    )

    s = must_replace(
        s,
        "                                        tint = if (isSelected) {\n"
        "                                            MaterialTheme.colorScheme.primary\n"
        "                                        } else {\n"
        "                                            MaterialTheme.colorScheme.onSurfaceVariant\n"
        "                                        }",
        "                                        tint = if (isSelected) {\n"
        "                                            MaterialTheme.colorScheme.onPrimary\n"
        "                                        } else {\n"
        "                                            MaterialTheme.colorScheme.onSurfaceVariant\n"
        "                                        }",
        "BottomBar selected icon contrast",
    )

    f.write_text(s)
    say("[patch] MainActivity: backdrop + BrutalSplash + transparent Scaffold + 5-tab Cyberbrutal dock")


def patch_home_screen(src: Path) -> None:
    f = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Home.kt"
    s = f.read_text()

    s = must_replace(
        s,
        "import com.ramcosta.composedestinations.generated.destinations.SuperUserScreenDestination",
        "import com.ramcosta.composedestinations.generated.destinations.SuperUserScreenDestination\n"
        "import com.ramcosta.composedestinations.generated.destinations.SyntheticaControlScreenDestination\n"
        "import com.rifsxd.ksunext.ui.theme.BrutalStaggerItem\n"
        "import com.rifsxd.ksunext.ui.theme.DepartureBoardText\n"
        "import com.rifsxd.ksunext.ui.theme.FadeInText\n"
        "import com.rifsxd.ksunext.ui.theme.brutalPlate",
        "Home imports",
    )

    s = must_replace(
        s,
        "    Scaffold(\n        topBar = {",
        "    Scaffold(\n        containerColor = Color.Transparent,\n        topBar = {",
        "Home transparent Scaffold",
    )

    # Stagger StatusCard + insert Synthetica Control Quick-Access Plate right on Home
    old_status_call = """            StatusCard(
                kernelVersion,
                ksuVersion,
                kernelUAPIVersion,
                lkmMode,
                ksuVersionTagParam = ksuVersionTag
            ) {
                navigator.navigate(InstallScreenDestination)
            }"""
    new_status_call = """            BrutalStaggerItem(index = 0) {
                StatusCard(
                    kernelVersion,
                    ksuVersion,
                    kernelUAPIVersion,
                    lkmMode,
                    ksuVersionTagParam = ksuVersionTag
                ) {
                    navigator.navigate(InstallScreenDestination)
                }
            }

            BrutalStaggerItem(index = 1) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(active = true)
                        .clickable {
                            navigator.navigate(SyntheticaControlScreenDestination) {
                                popUpTo(NavGraphs.root.startRoute) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 20.dp, vertical = 14.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            DepartureBoardText(
                                text = "SYNTHETICA // CONTROL HUB",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Black,
                                delayMillis = 60
                            )
                            FadeInText(
                                text = "Live CPU/GPU/ZRAM telemetry, daily/gaming profiles & install logs",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                delayMillis = 130
                            )
                        }
                        Icon(
                            imageVector = Icons.Filled.Tune,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }"""
    s = must_replace(s, old_status_call, new_status_call, "Home StatusCard + Control Hub banner")

    # Disable default upstream KernelSU-Next update nag so user doesn't overwrite paired Synthetica APK
    s = must_replace(
        s,
        '.getBoolean("check_update", true)',
        '.getBoolean("check_update", false)',
        "Home disable upstream update nag by default",
    )

    # Stagger InfoCard, IssueReportCard, ContributorsCard
    s = must_replace(
        s,
        "            InfoCard(autoExpand = developerOptionsEnabled)\n"
        "            IssueReportCard()\n"
        "            ContributorsCard()",
        "            BrutalStaggerItem(index = 3) { InfoCard(autoExpand = developerOptionsEnabled) }\n"
        "            BrutalStaggerItem(index = 4) { IssueReportCard() }\n"
        "            BrutalStaggerItem(index = 5) { ContributorsCard() }",
        "Home stagger cards",
    )

    # SuperuserCard & ModuleCard: brutalPlate + DepartureBoardText count + FadeInText label
    old_su_card = """    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        ),
        modifier = Modifier
            .height(IntrinsicSize.Min)
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(8.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = if (count <= 1) {
                        stringResource(R.string.home_superuser_count_singular)
                    } else {
                        stringResource(R.string.home_superuser_count_plural)
                    },
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    text = count.toString(),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }"""
    new_su_card = """    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .brutalPlate()
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(vertical = 14.dp, horizontal = 10.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                FadeInText(
                    text = (if (count <= 1) {
                        stringResource(R.string.home_superuser_count_singular)
                    } else {
                        stringResource(R.string.home_superuser_count_plural)
                    }).uppercase(),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    delayMillis = 60
                )
                Spacer(Modifier.height(4.dp))
                DepartureBoardText(
                    text = count.toString().padStart(2, '0'),
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Black,
                    delayMillis = 90
                )
            }
        }
    }"""
    s = must_replace(s, old_su_card, new_su_card, "Home SuperuserCard brutal")

    old_mod_card_head = """    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        ),
        modifier = Modifier
            .height(IntrinsicSize.Min)
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(8.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = if (count <= 1) {
                        stringResource(R.string.home_module_count_singular)
                    } else {
                        stringResource(R.string.home_module_count_plural)
                    },
                    style = MaterialTheme.typography.bodySmall
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = count.toString(),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )"""
    new_mod_card_head = """    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .brutalPlate()
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(vertical = 14.dp, horizontal = 10.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                FadeInText(
                    text = (if (count <= 1) {
                        stringResource(R.string.home_module_count_singular)
                    } else {
                        stringResource(R.string.home_module_count_plural)
                    }).uppercase(),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    delayMillis = 80
                )
                Spacer(Modifier.height(4.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    DepartureBoardText(
                        text = count.toString().padStart(2, '0'),
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Black,
                        delayMillis = 120
                    )"""
    s = must_replace(s, old_mod_card_head, new_mod_card_head, "Home ModuleCard brutal")

    # Home TopBar translucent + DepartureBoardText title
    s = must_replace(
        s,
        "    TopAppBar(\n        title = {",
        "    TopAppBar(\n"
        "        colors = TopAppBarDefaults.topAppBarColors(\n"
        "            containerColor = Color.Transparent,\n"
        "            scrolledContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)\n"
        "        ),\n"
        "        title = {",
        "Home TopBar translucent",
    )
    s = must_replace(
        s,
        "                Text(\n"
        "                    text = stringResource(R.string.app_name),\n"
        "                    style = MaterialTheme.typography.titleLarge,\n"
        "                    fontWeight = FontWeight.Black\n"
        "                )",
        "                DepartureBoardText(\n"
        "                    text = stringResource(R.string.app_name).uppercase() + \" // 2.1\",\n"
        "                    style = MaterialTheme.typography.titleLarge,\n"
        "                    fontWeight = FontWeight.Black,\n"
        "                    charStaggerMs = 24\n"
        "                )",
        "Home TopBar DepartureBoardText",
    )

    # StatusCard brutalPlate + DepartureBoardText on Working & version
    s = must_replace(
        s,
        "                        ) {\n"
        "                            Text(\n"
        "                                text = stringResource(id = R.string.home_working),\n"
        "                                style = MaterialTheme.typography.titleMedium,\n"
        "                                fontWeight = FontWeight.SemiBold\n"
        "                            )\n"
        "                        }",
        "                        ) {\n"
        "                            DepartureBoardText(\n"
        "                                text = stringResource(id = R.string.home_working).uppercase(),\n"
        "                                style = MaterialTheme.typography.titleLarge,\n"
        "                                fontWeight = FontWeight.Black\n"
        "                            )\n"
        "                        }",
        "Home StatusCard working DepartureBoardText",
    )
    s = must_replace(
        s,
        "                        Row(verticalAlignment = Alignment.CenterVertically) {\n"
        "                            Text(\n"
        "                                text = versionText,\n"
        "                                style = MaterialTheme.typography.bodySmall\n"
        "                            )",
        "                        Row(verticalAlignment = Alignment.CenterVertically) {\n"
        "                            FadeInText(\n"
        "                                text = versionText,\n"
        "                                style = MaterialTheme.typography.bodySmall,\n"
        "                                delayMillis = 110\n"
        "                            )",
        "Home StatusCard version FadeInText",
    )

    # InfoCard brutalPlate + DepartureBoardText values + FadeInText labels
    old_info_card = """    Card {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 24.dp, top = 24.dp, end = 24.dp, bottom = 24.dp)
        ) {
            @Composable
            fun InfoCardItem(label: String, content: String, icon: Any? = null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (icon != null) {
                        when (icon) {
                            is ImageVector -> Icon(
                                imageVector = icon,
                                contentDescription = null,
                                modifier = Modifier.padding(end = 20.dp)
                            )
                            is Painter -> Icon(
                                painter = icon,
                                contentDescription = null,
                                modifier = Modifier.padding(end = 20.dp)
                            )
                        }
                    }
                    Column {
                        Text(
                            text = label,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = content,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
            }"""
    new_info_card = """    Card(
        modifier = Modifier
            .fillMaxWidth()
            .brutalPlate(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 22.dp, top = 22.dp, end = 22.dp, bottom = 22.dp)
        ) {
            @Composable
            fun InfoCardItem(label: String, content: String, icon: Any? = null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (icon != null) {
                        when (icon) {
                            is ImageVector -> Icon(
                                imageVector = icon,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(end = 18.dp)
                            )
                            is Painter -> Icon(
                                painter = icon,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(end = 18.dp)
                            )
                        }
                    }
                    Column {
                        FadeInText(
                            text = label.uppercase(),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            delayMillis = 45
                        )
                        DepartureBoardText(
                            text = content,
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(top = 3.dp),
                            delayMillis = 90,
                            charStaggerMs = 15
                        )
                    }
                }
            }"""
    s = must_replace(s, old_info_card, new_info_card, "Home InfoCard DepartureBoardText + FadeInText")

    f.write_text(s)
    say("[patch] HomeScreen: Cyberbrutal plates + Control Hub card + DepartureBoardText + FadeInText")


def patch_module_screen(src: Path) -> None:
    f = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Module.kt"
    s = f.read_text()

    s = must_replace(
        s,
        "import androidx.compose.foundation.lazy.items",
        "import androidx.compose.foundation.lazy.items\n"
        "import androidx.compose.foundation.lazy.itemsIndexed\n"
        "import com.rifsxd.ksunext.ui.theme.BrutalStaggerItem\n"
        "import com.rifsxd.ksunext.ui.theme.DepartureBoardText\n"
        "import com.rifsxd.ksunext.ui.theme.FadeInText\n"
        "import com.rifsxd.ksunext.ui.theme.brutalPlate",
        "Module imports",
    )

    s = must_replace(
        s,
        "    Scaffold(\n        topBar = {\n            SearchAppBar(\n                title = {\n"
        "                    Text(\n"
        "                        text = stringResource(R.string.module),\n"
        "                        style = MaterialTheme.typography.titleLarge,\n"
        "                        fontWeight = FontWeight.Black,\n"
        "                    )\n"
        "                },",
        "    Scaffold(\n        containerColor = Color.Transparent,\n        topBar = {\n            SearchAppBar(\n                title = {\n"
        "                    DepartureBoardText(\n"
        "                        text = stringResource(R.string.module).uppercase(),\n"
        "                        style = MaterialTheme.typography.titleLarge,\n"
        "                        fontWeight = FontWeight.Black,\n"
        "                    )\n"
        "                },",
        "Module Scaffold + DepartureBoardText header",
    )

    # Staggered cascade + stable key on LazyColumn module items
    s = must_replace(
        s,
        "                else -> {\n"
        "                    items(viewModel.moduleList) { module ->",
        "                else -> {\n"
        "                    itemsIndexed(viewModel.moduleList, key = { _, m -> m.id }) { modIndex, module ->",
        "Module itemsIndexed",
    )

    s = must_replace(
        s,
        "                        ModuleItem(\n"
        "                            navigator = navigator,",
        "                        BrutalStaggerItem(index = modIndex, triggerKey = module.id) {\n"
        "                        ModuleItem(\n"
        "                            navigator = navigator,\n"
        "                            itemIndex = modIndex,",
        "Module BrutalStaggerItem open",
    )

    s = must_replace(
        s,
        "                        // fix last item shadow incomplete in LazyColumn\n"
        "                        Spacer(Modifier.height(1.dp))",
        "                        }\n"
        "                        // fix last item shadow incomplete in LazyColumn\n"
        "                        Spacer(Modifier.height(1.dp))",
        "Module BrutalStaggerItem close",
    )

    s = must_replace(
        s,
        "fun ModuleItem(\n"
        "    navigator: DestinationsNavigator,\n"
        "    module: ModuleViewModel.ModuleInfo,",
        "fun ModuleItem(\n"
        "    navigator: DestinationsNavigator,\n"
        "    itemIndex: Int = 0,\n"
        "    module: ModuleViewModel.ModuleInfo,",
        "ModuleItem signature itemIndex",
    )
    # The UAPI-v4 source also includes a positional @Preview invocation.
    s = must_replace(
        s,
        "    ModuleItem(\n        EmptyDestinationsNavigator,\n        module,",
        "    ModuleItem(\n        EmptyDestinationsNavigator,\n        0,\n        module,",
        "ModuleItem preview itemIndex",
    )

    old_mod_card = """    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .combinedClickable("""
    new_mod_card = """    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .brutalPlate(active = module.enabled && !module.remove)
            .combinedClickable("""
    s = must_replace(s, old_mod_card, new_mod_card, "ModuleItem brutalPlate")

    # Airport Departure Split-Flap on Module Name & Version + FadeInText on Author & Description
    old_mod_texts = """                            Text(
                                text = module.name,
                                fontSize = MaterialTheme.typography.titleMedium.fontSize,
                                fontWeight = FontWeight.SemiBold,
                                lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                                fontFamily = MaterialTheme.typography.titleMedium.fontFamily,
                                textDecoration = textDecoration
                            )

                            Text(
                                text = "$moduleVersion: ${module.version}",
                                fontSize = MaterialTheme.typography.bodySmall.fontSize,
                                lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                                fontFamily = MaterialTheme.typography.bodySmall.fontFamily,
                                textDecoration = textDecoration
                            )

                            Text(
                                text = "$moduleAuthor: ${module.author}",
                                fontSize = MaterialTheme.typography.bodySmall.fontSize,
                                lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                                fontFamily = MaterialTheme.typography.bodySmall.fontFamily,
                                textDecoration = textDecoration
                            )"""
    new_mod_texts = """                            val staggerBase = (itemIndex % 8) * 32
                            DepartureBoardText(
                                text = module.name,
                                fontSize = MaterialTheme.typography.titleMedium.fontSize,
                                fontWeight = FontWeight.Bold,
                                lineHeight = MaterialTheme.typography.titleMedium.lineHeight,
                                fontFamily = MaterialTheme.typography.titleMedium.fontFamily,
                                textDecoration = textDecoration,
                                delayMillis = staggerBase,
                                charStaggerMs = 20,
                                triggerKey = module.id
                            )

                            DepartureBoardText(
                                text = "$moduleVersion: ${module.version}",
                                fontSize = MaterialTheme.typography.labelMedium.fontSize,
                                lineHeight = MaterialTheme.typography.labelMedium.lineHeight,
                                fontFamily = MaterialTheme.typography.labelMedium.fontFamily,
                                color = MaterialTheme.colorScheme.primary,
                                textDecoration = textDecoration,
                                delayMillis = staggerBase + 65,
                                charStaggerMs = 14,
                                triggerKey = module.id
                            )

                            FadeInText(
                                text = "$moduleAuthor: ${module.author}",
                                fontSize = MaterialTheme.typography.bodySmall.fontSize,
                                lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                                fontFamily = MaterialTheme.typography.bodySmall.fontFamily,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textDecoration = textDecoration,
                                delayMillis = staggerBase + 115,
                                triggerKey = module.id
                            )"""
    s = must_replace(s, old_mod_texts, new_mod_texts, "ModuleItem DepartureBoardText + FadeInText")

    old_mod_desc = """                    Text(
                        text = module.description,
                        fontSize = MaterialTheme.typography.bodySmall.fontSize,
                        fontFamily = MaterialTheme.typography.bodySmall.fontFamily,
                        lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                        fontWeight = MaterialTheme.typography.bodySmall.fontWeight,
                        overflow = TextOverflow.Ellipsis,
                        maxLines = 3,
                        textDecoration = textDecoration
                    )"""
    new_mod_desc = """                    FadeInText(
                        text = module.description,
                        fontSize = MaterialTheme.typography.bodySmall.fontSize,
                        fontFamily = MaterialTheme.typography.bodySmall.fontFamily,
                        lineHeight = MaterialTheme.typography.bodySmall.lineHeight,
                        fontWeight = MaterialTheme.typography.bodySmall.fontWeight,
                        overflow = TextOverflow.Ellipsis,
                        maxLines = 3,
                        textDecoration = textDecoration,
                        delayMillis = ((itemIndex % 8) * 32) + 155,
                        triggerKey = module.id
                    )"""
    s = must_replace(s, old_mod_desc, new_mod_desc, "ModuleItem description FadeInText")

    f.write_text(s)
    say("[patch] ModuleScreen: airport split-flap on module title/version + staggered fade-in descriptions")


def patch_superuser_screen(src: Path) -> None:
    f = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/SuperUser.kt"
    s = f.read_text()

    s = must_replace(
        s,
        "import androidx.compose.foundation.lazy.items",
        "import androidx.compose.foundation.lazy.items\n"
        "import androidx.compose.foundation.lazy.itemsIndexed\n"
        "import com.rifsxd.ksunext.ui.theme.BrutalStaggerItem\n"
        "import com.rifsxd.ksunext.ui.theme.DepartureBoardText\n"
        "import com.rifsxd.ksunext.ui.theme.FadeInText\n"
        "import com.rifsxd.ksunext.ui.theme.brutalPlate",
        "SuperUser imports",
    )

    s = must_replace(
        s,
        "    Scaffold(\n        topBar = {\n            SearchAppBar(\n                title = {\n"
        "                    Text(\n"
        "                        text = stringResource(R.string.superuser),\n"
        "                        style = MaterialTheme.typography.titleLarge,\n"
        "                        fontWeight = FontWeight.Black,\n"
        "                    )\n"
        "                },",
        "    Scaffold(\n        containerColor = Color.Transparent,\n        topBar = {\n            SearchAppBar(\n                title = {\n"
        "                    DepartureBoardText(\n"
        "                        text = stringResource(R.string.superuser).uppercase(),\n"
        "                        style = MaterialTheme.typography.titleLarge,\n"
        "                        fontWeight = FontWeight.Black,\n"
        "                    )\n"
        "                },",
        "SuperUser Scaffold + DepartureBoardText header",
    )

    old_su_items = """                items(
                    viewModel.appList.filter { it.displayIdentifier != ksuApp.packageName },
                    key = { it.displayIdentifier + it.uid }
                ) { app ->
                    AppItem(app) {
                        navigator.navigate(AppProfileScreenDestination(app))
                    }
                }"""
    new_su_items = """                itemsIndexed(
                    viewModel.appList.filter { it.displayIdentifier != ksuApp.packageName },
                    key = { _, it -> it.displayIdentifier + it.uid }
                ) { appIndex, app ->
                    BrutalStaggerItem(index = appIndex, triggerKey = app.displayIdentifier) {
                        AppItem(app, appIndex) {
                            navigator.navigate(AppProfileScreenDestination(app))
                        }
                    }
                }"""
    s = must_replace(s, old_su_items, new_su_items, "SuperUser itemsIndexed + BrutalStaggerItem")

    old_app_item = """private fun AppItem(
    app: SuperUserViewModel.AppInfo,
    onClickListener: () -> Unit,
) {
    val context = LocalContext.current
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    val developerOptionsEnabled = prefs.getBoolean("enable_developer_options", false)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .clickable(onClick = onClickListener)
    ) {
        ListItem(
            modifier = Modifier.fillMaxWidth(),
            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
            headlineContent = {
                Text(
                    text = app.label,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            },
            supportingContent = {
                Column {
                    Text(
                        text = app.displayIdentifier,
                        style = MaterialTheme.typography.bodySmall
                    )"""
    new_app_item = """private fun AppItem(
    app: SuperUserViewModel.AppInfo,
    itemIndex: Int = 0,
    onClickListener: () -> Unit,
) {
    val context = LocalContext.current
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    val developerOptionsEnabled = prefs.getBoolean("enable_developer_options", false)
    val staggerBase = (itemIndex % 8) * 28

    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .brutalPlate(active = app.allowSu)
            .clickable(onClick = onClickListener)
    ) {
        ListItem(
            modifier = Modifier.fillMaxWidth(),
            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
            headlineContent = {
                DepartureBoardText(
                    text = app.label,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    delayMillis = staggerBase,
                    charStaggerMs = 19,
                    triggerKey = app.displayIdentifier
                )
            },
            supportingContent = {
                Column {
                    FadeInText(
                        text = app.displayIdentifier,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        delayMillis = staggerBase + 75,
                        triggerKey = app.displayIdentifier
                    )"""
    s = must_replace(s, old_app_item, new_app_item, "SuperUser AppItem DepartureBoardText + FadeInText")

    f.write_text(s)
    say("[patch] SuperUserScreen: airport split-flap on app names + fade-in package IDs + Cyberbrutal plates")


def patch_settings_and_customization(src: Path) -> None:
    f_set = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Settings.kt"
    s = f_set.read_text()

    s = must_replace(
        s,
        "import com.rifsxd.ksunext.ui.component.*",
        "import com.rifsxd.ksunext.ui.component.*\n"
        "import com.rifsxd.ksunext.ui.theme.BrutalStaggerItem\n"
        "import com.rifsxd.ksunext.ui.theme.DepartureBoardText\n"
        "import com.rifsxd.ksunext.ui.theme.brutalPlate",
        "Settings imports",
    )

    s = must_replace(
        s,
        "    Scaffold(\n        topBar = {",
        "    Scaffold(\n        containerColor = Color.Transparent,\n        topBar = {",
        "Settings transparent Scaffold",
    )

    old_set_cards = """                SecurityCard(
                    navigator = navigator,
                    loadingDialog = loadingDialog
                )
            }

            AppSettingsCard("""
    new_set_cards = """                BrutalStaggerItem(index = 1) {
                    SecurityCard(
                        navigator = navigator,
                        loadingDialog = loadingDialog
                    )
                }
            }

            BrutalStaggerItem(index = 2) {
            AppSettingsCard("""
    s = must_replace(s, old_set_cards, new_set_cards, "Settings stagger open")

    s = must_replace(
        s,
        "                isUnrooted = isUnrooted\n            )\n\n            Spacer(Modifier)",
        "                isUnrooted = isUnrooted\n            )\n            }\n\n            Spacer(Modifier)",
        "Settings stagger close",
    )

    s = must_replace(
        s,
        "    Card(modifier = Modifier.fillMaxWidth()) {",
        "    Card(\n"
        "        modifier = Modifier.fillMaxWidth().brutalPlate(),\n"
        "        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)\n"
        "    ) {",
        "Settings KernelFeaturesCard brutalPlate",
        count = 3,
    )

    s = must_replace(
        s,
        "    TopAppBar(\n"
        "        title = {\n"
        "            Text(\n"
        "                text = stringResource(R.string.settings),\n"
        "                style = MaterialTheme.typography.titleLarge,\n"
        "                fontWeight = FontWeight.Black,\n"
        "            )\n"
        "        },",
        "    TopAppBar(\n"
        "        colors = TopAppBarDefaults.topAppBarColors(\n"
        "            containerColor = Color.Transparent,\n"
        "            scrolledContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)\n"
        "        ),\n"
        "        title = {\n"
        "            DepartureBoardText(\n"
        "                text = stringResource(R.string.settings).uppercase(),\n"
        "                style = MaterialTheme.typography.titleLarge,\n"
        "                fontWeight = FontWeight.Black,\n"
        "            )\n"
        "        },",
        "Settings TopBar DepartureBoardText",
    )
    f_set.write_text(s)

    # CustomizationScreen
    f_cust = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/screen/Customization.kt"
    c = f_cust.read_text()
    c = must_replace(
        c,
        "import com.rifsxd.ksunext.ui.component.SwitchItem",
        "import androidx.compose.ui.graphics.Color\n"
        "import com.rifsxd.ksunext.ui.component.SwitchItem\n"
        "import com.rifsxd.ksunext.ui.theme.DepartureBoardText",
        "Customization imports",
    )
    c = must_replace(
        c,
        "    Scaffold(\n        topBar = {",
        "    Scaffold(\n        containerColor = Color.Transparent,\n        topBar = {",
        "Customization transparent Scaffold",
    )
    c = must_replace(
        c,
        "    TopAppBar(\n        title = { Text(\n"
        "                text = stringResource(R.string.customization),\n"
        "                style = MaterialTheme.typography.titleLarge,\n"
        "                fontWeight = FontWeight.Black,\n"
        "            ) },",
        "    TopAppBar(\n"
        "        colors = TopAppBarDefaults.topAppBarColors(\n"
        "            containerColor = Color.Transparent,\n"
        "            scrolledContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)\n"
        "        ),\n"
        "        title = { DepartureBoardText(\n"
        "                text = stringResource(R.string.customization).uppercase(),\n"
        "                style = MaterialTheme.typography.titleLarge,\n"
        "                fontWeight = FontWeight.Black,\n"
        "            ) },",
        "Customization TopBar DepartureBoardText",
    )
    f_cust.write_text(c)
    say("[patch] Settings + Customization: transparent Scaffolds + brutalPlates + DepartureBoardText headers")


def apply_package_label_and_resources(src: Path) -> None:
    app = src / "manager/app"
    gradle = app / "build.gradle.kts"
    g = gradle.read_text()
    if "applicationId" not in g:
        g = must_replace(
            g,
            "android {\n    namespace =",
            'android {\n    defaultConfig {\n        applicationId = "' + PKG + '"\n    }\n\n    namespace =',
            "build.gradle.kts applicationId",
        )
    # Remove apksign plugin so signing stays strictly controlled outside Gradle
    g = g.replace("    alias(libs.plugins.lsplugin.apksign)\n", "", 1)
    g = re.sub(r"\napksign \{[^}]*\}\n", "\n", g, count=1)
    assert "apksign {" not in g, "apksign block still present"
    gradle.write_text(g)

    # Strings: app_name -> Synthetica, add synthetica_control, clean user-facing KernelSU-Next mentions
    res = app / "src/main/res"
    en_strings = res / "values/strings.xml"
    t = en_strings.read_text()
    t = re.sub(r'(<string name="app_name"[^>]*>)[^<]*(</string>)', r"\g<1>Synthetica\g<2>", t)
    if 'name="synthetica_control"' not in t:
        t = t.replace("</resources>", '    <string name="synthetica_control">Control</string>\n</resources>')
    # Replace user-facing KernelSU-Next copy with Synthetica (keeping URLs intact)
    t = t.replace("KernelSU-Next manager", "Synthetica manager")
    t = t.replace("allow KernelSU-Next to restore", "allow Synthetica to restore")
    t = t.replace("uninstall KernelSU-Next", "uninstall Synthetica")
    t = t.replace("Uninstalling KernelSU-Next", "Uninstalling Synthetica")
    ET.fromstring(t)  # Assert valid XML
    en_strings.write_text(t)

    id_strings = res / "values-in-rID/strings.xml"
    if id_strings.exists():
        tid = id_strings.read_text()
        if 'name="synthetica_control"' not in tid:
            tid = tid.replace("</resources>", '  <string name="synthetica_control">Kontrol</string>\n</resources>')
        ET.fromstring(tid)
        id_strings.write_text(tid)

    # Cyberbrutalist icons
    count = 0
    for bucket in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        d = res / f"mipmap-{bucket}"
        if not d.exists():
            continue
        for target, source in (
            ("ic_launcher.png", f"ic_launcher-{bucket}.png"),
            ("ic_launcher_foreground.png", f"ic_foreground-{bucket}.png"),
        ):
            sp = BRANDING / source
            if sp.exists() and (d / target).exists():
                shutil.copyfile(sp, d / target)
                count += 1
        mono = d / "ic_launcher_monochrome.png"
        if mono.exists() and (BRANDING / "ic_mono-96.png").exists():
            shutil.copyfile(BRANDING / "ic_mono-96.png", mono)
            count += 1
    assert count > 0, "no Cyberbrutalist launcher icon was replaced"

    anydpi = res / "mipmap-anydpi"
    if anydpi.exists():
        ic_xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/ic_launcher_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
            "</adaptive-icon>\n"
        )
        ET.fromstring(ic_xml)
        (anydpi / "ic_launcher.xml").write_text(ic_xml)

    colors = res / "values/colors.xml"
    c = colors.read_text().replace("#FFFFFFFF", "#090A0D")
    ET.fromstring(c)
    colors.write_text(c)

    for theme_rel, win_hex in (("values/themes.xml", "#090A0D"), ("values-night/themes.xml", "#090A0D")):
        tf = res / theme_rel
        if tf.exists():
            tx = tf.read_text()
            if "windowSplashScreenBackground" not in tx:
                tx = tx.replace(
                    '<item name="android:windowLayoutInDisplayCutoutMode" tools:targetApi="o_mr1">shortEdges</item>',
                    '<item name="android:windowLayoutInDisplayCutoutMode" tools:targetApi="o_mr1">shortEdges</item>\n'
                    f'        <item name="android:windowSplashScreenBackground">{win_hex}</item>\n'
                    f'        <item name="android:windowBackground">{win_hex}</item>',
                )
            ET.fromstring(tx)
            tf.write_text(tx)

    say(f"[brand] package={PKG}, label=Synthetica, icons={count}, XML resources verified")


def sanity_check_kotlin_sources(src: Path) -> None:
    """Verify balanced braces/parens and package headers across all Cyberbrutalist UI Kotlin files."""
    kt_root = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui"
    targets = [
        "MainActivity.kt",
        "theme/Color.kt",
        "theme/Shapes.kt",
        "theme/Type.kt",
        "theme/Theme.kt",
        "theme/BrutalMotion.kt",
        "screen/BottomBarDestination.kt",
        "screen/SyntheticaControl.kt",
        "screen/BoostLegacy.kt",
        "screen/Home.kt",
        "screen/Module.kt",
        "screen/SuperUser.kt",
        "screen/Settings.kt",
        "screen/Customization.kt",
        "component/AboutCard.kt",
        "component/SearchBar.kt",
        "component/SettingsItem.kt",
    ]
    token_re = re.compile(
        r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*'
    )
    for rel in targets:
        kt = kt_root / rel
        assert kt.is_file(), f"missing expected Kotlin file: {kt}"
        txt = kt.read_text()
        assert txt.count("package com.rifsxd.ksunext") == 1, f"{rel}: bad package header"
        clean = token_re.sub("", txt)
        ob, cb = clean.count("{"), clean.count("}")
        op, cp = clean.count("("), clean.count(")")
        assert ob == cb, f"{rel}: unbalanced braces {{={ob} }}={cb}"
        assert op == cp, f"{rel}: unbalanced parens (={op} )={cp}"
    say(f"[sanity] verified {len(targets)} Cyberbrutalist Kotlin UI files (package headers + balanced braces/parens OK)")
