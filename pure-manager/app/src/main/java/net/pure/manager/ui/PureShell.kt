package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import net.pure.manager.theme.AccentChoices
import net.pure.manager.theme.AppMode
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.LocalSystemInsets
import net.pure.manager.theme.NavModel
import net.pure.manager.theme.PureThemeSpec
import net.pure.manager.theme.ThemeCatalog
import net.pure.manager.theme.ThemePrefs

/**
 * Shell = the part of the screen that changes shape between themes.
 *
 * Three navigation models live here, and all three are driven by the same tokens.
 * The four screens below are shared by all three models, which is the whole
 * argument for putting the navigation model in the token set: switching from
 * iOS to Cyberpunk changes the frame, not the content.
 *
 * Every text size comes from MaterialTheme.typography, which [PureThemeSpec]
 * scales. Nothing in this file names an sp value, so the density control in the
 * Customisation tab actually moves the UI.
 */

/** Which of the four screens is showing. Saved across rotation. */
private enum class Screen(val label: String, val glyph: String) {
    FILES("Berkas", "\u25A4"),
    THEME("Tema", "\u25C8"),
    MODULES("Modul", "\u2726"),
    SETTINGS("Setelan", "\u2699"),
}

@Composable
fun PureShell(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    val insets = LocalSystemInsets.current
    var screen by rememberSaveable { mutableStateOf(Screen.FILES) }

    Box(Modifier.fillMaxSize().background(p.background)) {
        when (spec.nav) {
            NavModel.RAIL -> Row(Modifier.fillMaxSize()) {
                LeftRail(spec, screen, onSelect = { screen = it })
                Box(Modifier.weight(1f)) {
                    ScreenBody(screen, prefs, onPrefs, compact = spec.compactRows)
                }
            }
            NavModel.COMMAND_BAR -> Column(
                Modifier
                    .fillMaxSize()
                    .padding(top = insets.top, bottom = insets.bottom)
            ) {
                Box(Modifier.weight(1f)) {
                    ScreenBody(screen, prefs, onPrefs, compact = spec.compactRows)
                }
                CommandBar(spec, screen, onSelect = { screen = it })
            }
            NavModel.TAB_BAR -> Column(
                Modifier
                    .fillMaxSize()
                    .padding(top = insets.top, bottom = insets.bottom)
            ) {
                Box(Modifier.weight(1f)) {
                    ScreenBody(screen, prefs, onPrefs, compact = spec.compactRows)
                }
                TabBar(spec, screen, onSelect = { screen = it })
            }
        }
    }
}

// ------------------------------------------------------------------ navigation

@Composable
private fun LeftRail(
    spec: PureThemeSpec,
    current: Screen,
    onSelect: (Screen) -> Unit,
) {
    val p = spec.palette
    val insets = LocalSystemInsets.current
    Column(
        Modifier
            .width(64.dp)
            .fillMaxHeight()
            .background(p.surfaceVariant)
            .border(0.5.dp, p.outline)
            .padding(top = insets.top + 8.dp, bottom = insets.bottom + 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Screen.entries.forEach { s ->
            val selected = s == current
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable { onSelect(s) }
                    .padding(vertical = 10.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    s.glyph,
                    style = MaterialTheme.typography.titleMedium,
                    color = if (selected) p.accent else p.onSurfaceVariant,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    s.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (selected) p.accent else p.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun CommandBar(
    spec: PureThemeSpec,
    current: Screen,
    onSelect: (Screen) -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .background(p.surface)
            .border(0.5.dp, p.outline)
            .padding(horizontal = 8.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Screen.entries.forEachIndexed { i, s ->
            val selected = s == current
            Box(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable { onSelect(s) }
                    .background(if (selected) p.accent.copy(alpha = 0.18f) else Color.Transparent)
                    .padding(vertical = 8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "[F${i + 1}] ${s.label}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                    color = if (selected) p.accent else p.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun TabBar(
    spec: PureThemeSpec,
    current: Screen,
    onSelect: (Screen) -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .background(p.surface)
            .border(0.5.dp, p.outline)
            .padding(horizontal = 4.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        Screen.entries.forEach { s ->
            val selected = s == current
            Column(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable { onSelect(s) }
                    .padding(vertical = 6.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (selected && spec.id == "pixel") {
                    // M3 pill indicator, drawn from the theme's radius rather than
                    // dropped in as a Material component.
                    Box(
                        Modifier
                            .clip(RoundedCornerShape(spec.cornerDp.dp))
                            .background(p.accent.copy(alpha = 0.22f))
                            .padding(horizontal = 16.dp, vertical = 2.dp),
                    ) {
                        Text(s.glyph, style = MaterialTheme.typography.titleMedium, color = p.accent)
                    }
                } else {
                    Text(
                        s.glyph,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (selected) p.accent else p.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(2.dp))
                Text(
                    s.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (selected) p.accent else p.onSurfaceVariant,
                )
            }
        }
    }
}

// ---------------------------------------------------------------------- screens

@Composable
private fun ScreenBody(
    screen: Screen,
    prefs: ThemePrefs,
    onPrefs: (ThemePrefs) -> Unit,
    compact: Boolean,
) {
    val spec = LocalPureSpec.current
    val insets = LocalSystemInsets.current
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(
                start = spec.contentPaddingDp.dp + insets.start,
                end = spec.contentPaddingDp.dp + insets.end,
            )
            .padding(top = if (spec.nav == NavModel.RAIL) 12.dp else 16.dp, bottom = 20.dp),
    ) {
        Text(
            screen.label,
            style = MaterialTheme.typography.headlineMedium,
            color = spec.palette.onBackground,
        )
        Spacer(Modifier.height(12.dp))
        when (screen) {
            Screen.FILES -> FilesScreen(spec, compact)
            Screen.THEME -> ThemeScreen(prefs, onPrefs)
            Screen.MODULES -> ModulesScreen(spec)
            Screen.SETTINGS -> SettingsScreen(prefs, onPrefs, spec)
        }
    }
}

@Composable
private fun FilesScreen(spec: PureThemeSpec, compact: Boolean) {
    val p = spec.palette
    val files = listOf(
        "R" to ("Retro-Arcade.apk" to "24.1 MB"),
        "Z" to ("Manager-6.1.zip" to "18.7 MB"),
        "P" to ("banner-review.png" to "640 KB"),
        "T" to ("theme-signing.key" to "3.4 KB"),
        "A" to ("voice-note.m4a" to "2.1 MB"),
    )
    Column(verticalArrangement = Arrangement.spacedBy(if (compact) 4.dp else 10.dp)) {
        files.forEach { (letter, rest) ->
            val (name, size) = rest
            Row(
                Modifier
                    .fillMaxWidth()
                    .height(spec.rowHeightDp.dp)
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .background(p.surface)
                    .border(
                        width = if (p.outline == Color.Transparent) 0.dp else 0.75.dp,
                        color = p.outline,
                        shape = RoundedCornerShape(spec.cornerDp.dp),
                    )
                    .padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    Modifier
                        .size(spec.rowHeightDp.dp * 0.52f)
                        .clip(RoundedCornerShape((spec.cornerDp * 0.55f).dp))
                        .background(p.accent),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        letter,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = p.onAccent,
                    )
                }
                Column(Modifier.weight(1f)) {
                    Text(
                        name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        color = p.onBackground,
                    )
                    if (!compact) {
                        Text(
                            size,
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    }
                }
                if (compact) {
                    Text(
                        size,
                        style = MaterialTheme.typography.bodySmall,
                        color = p.onSurfaceVariant,
                    )
                } else {
                    Text(
                        "\u203A",
                        style = MaterialTheme.typography.titleLarge,
                        color = p.onSurfaceVariant,
                    )
                }
            }
        }
    }
    Spacer(Modifier.height(14.dp))
    Text(
        "Ini daftar contoh. Tahap 2 menggantinya dengan berkas asli di perangkat.",
        style = MaterialTheme.typography.bodySmall,
        color = p.onSurfaceVariant,
    )
}

@Composable
private fun ThemeScreen(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette

    SectionLabel("TEMA")
    ThemeCatalog.forEach { t ->
        val selected = prefs.themeId == t.id
        // Tapping applies the theme immediately. That is the whole point of the
        // token system, and it is what the previous build could not do at all.
        OptionRow(
            selected = selected,
            onClick = { onPrefs(prefs.copy(themeId = t.id)) },
            leading = {
                Box(
                    Modifier
                        .size(spec.rowHeightDp.dp * 0.5f)
                        .clip(RoundedCornerShape((spec.cornerDp * 0.5f).dp))
                        .background(t.swatch),
                )
            },
            title = t.label,
            subtitle = t.note,
        )
    }

    SectionLabel("MODE")
    AppMode.entries.forEach { m ->
        OptionRow(
            selected = prefs.mode == m,
            onClick = { onPrefs(prefs.copy(mode = m)) },
            title = when (m) {
                AppMode.LIGHT -> "Terang"
                AppMode.DARK -> "Gelap"
                AppMode.AMOLED -> "AMOLED hitam total"
            },
            subtitle = when (m) {
                AppMode.LIGHT -> null
                AppMode.DARK -> "Abu-abu gelap, elevasi terlihat"
                AppMode.AMOLED -> "Hemat daya OLED; pemisah pakai garis, bukan bayangan"
            },
        )
    }

    SectionLabel("AKSEN")
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        AccentChoices.forEachIndexed { i, (name, colour) ->
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable { onPrefs(prefs.copy(accentIndex = i)) }
                    .padding(4.dp),
            ) {
                Box(
                    Modifier
                        .size(34.dp)
                        .clip(CircleShape)
                        .background(colour)
                        .border(
                            width = if (prefs.accentIndex == i) 3.dp else 0.dp,
                            color = p.onBackground,
                            shape = CircleShape,
                        ),
                )
                Spacer(Modifier.height(3.dp))
                Text(
                    name,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (prefs.accentIndex == i) p.accent else p.onSurfaceVariant,
                )
            }
        }
    }

    SectionLabel("BENTUK & KEPADATAN")
    StepRow(
        title = "Sudut",
        value = "x${"%.1f".format(prefs.cornerScale)}",
        onLess = { onPrefs(prefs.copy(cornerScale = (prefs.cornerScale - 0.25f).coerceIn(0f, 2f))) },
        onMore = { onPrefs(prefs.copy(cornerScale = (prefs.cornerScale + 0.25f).coerceIn(0f, 2f))) },
    )
    StepRow(
        title = "Ukuran teks & baris",
        value = "${(prefs.densityScale * 100).toInt()}%",
        onLess = { onPrefs(prefs.copy(densityScale = (prefs.densityScale - 0.05f).coerceIn(0.8f, 1.4f))) },
        onMore = { onPrefs(prefs.copy(densityScale = (prefs.densityScale + 0.05f).coerceIn(0.8f, 1.4f))) },
    )
    OptionRow(
        selected = prefs.animations,
        onClick = { onPrefs(prefs.copy(animations = !prefs.animations)) },
        title = "Animasi",
        subtitle = if (prefs.animations) "Aktif" else "Mati",
    )
}

@Composable
private fun ModulesScreen(spec: PureThemeSpec) {
    val p = spec.palette
    // Honest placeholder. Stage 4 wires this to GitHub Releases; until then the
    // tab exists, is reachable, and says what it will do rather than showing
    // invented modules that cannot be installed.
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        listOf(
            "Terminal" to "Belum tersedia \u2014 tahap 3",
            "Editor kode" to "Belum tersedia \u2014 tahap 6",
            "PDF & Office" to "Belum tersedia \u2014 tahap 5",
            "AI" to "Ditahan atas permintaan",
        ).forEach { (name, state) ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .background(p.surface)
                    .border(0.75.dp, p.outline, RoundedCornerShape(spec.cornerDp.dp))
                    .padding(horizontal = 14.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        color = p.onBackground,
                    )
                    Text(
                        state,
                        style = MaterialTheme.typography.bodySmall,
                        color = p.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun SettingsScreen(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit, spec: PureThemeSpec) {
    val p = spec.palette
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        InfoRow("Versi", "0.1.1")
        InfoRow("Tahap", "T1 \u2014 tema dan kerangka")
        InfoRow("Paket", "net.pure.manager")
        InfoRow("Android", "10\u201316")
        Spacer(Modifier.height(4.dp))
        Text(
            "Setelan aplikasi yang sebenarnya (izin, bahasa, tema ikon) menyusul " +
                "bersama lapisan berkas di tahap 2. Yang bisa diubah sekarang ada di tab Tema.",
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        OptionRow(
            selected = false,
            onClick = { onPrefs(ThemePrefs()) },
            title = "Setel ulang tampilan",
            subtitle = "Kembali ke iOS, gelap, aksen biru, ukuran 100%",
        )
    }
}

// ------------------------------------------------------------------- components

@Composable
private fun SectionLabel(text: String) {
    val p = LocalPureSpec.current.palette
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.Bold,
        color = p.onSurfaceVariant,
        modifier = Modifier.padding(top = 18.dp, bottom = 6.dp),
    )
}

@Composable
private fun OptionRow(
    selected: Boolean,
    onClick: () -> Unit,
    title: String,
    subtitle: String? = null,
    leading: (@Composable () -> Unit)? = null,
) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(if (selected) p.accent.copy(alpha = 0.12f) else p.surface)
            .border(
                width = if (selected) 1.5.dp else 0.75.dp,
                color = if (selected) p.accent else p.outline,
                shape = RoundedCornerShape(spec.cornerDp.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        leading?.invoke()
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                color = p.onBackground,
            )
            if (subtitle != null) {
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        }
        Text(
            if (selected) "\u2713" else "",
            style = MaterialTheme.typography.titleLarge,
            color = p.accent,
        )
    }
}

@Composable
private fun StepRow(
    title: String,
    value: String,
    onLess: () -> Unit,
    onMore: () -> Unit,
) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(p.surface)
            .border(0.75.dp, p.outline, RoundedCornerShape(spec.cornerDp.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                color = p.onBackground,
            )
            Text(value, style = MaterialTheme.typography.bodySmall, color = p.onSurfaceVariant)
        }
        StepButton("\u2212", onLess)
        Spacer(Modifier.width(8.dp))
        StepButton("+", onMore)
    }
}

@Composable
private fun StepButton(label: String, onClick: () -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Box(
        Modifier
            .size(40.dp)
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(p.surfaceVariant)
            .border(0.75.dp, p.outline, RoundedCornerShape(spec.cornerDp.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = MaterialTheme.typography.titleLarge, color = p.onBackground)
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    val p = LocalPureSpec.current.palette
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = p.onSurfaceVariant,
            modifier = Modifier.width(96.dp),
        )
        Text(
            value,
            style = MaterialTheme.typography.bodyMedium,
            color = p.onBackground,
        )
    }
}
