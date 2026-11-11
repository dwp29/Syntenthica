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
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeState
import net.pure.manager.PureCrash
import net.pure.manager.theme.AccentChoices
import net.pure.manager.theme.AppMode
import net.pure.manager.theme.ChromeStyle
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.LocalSystemInsets
import net.pure.manager.theme.NavModel
import net.pure.manager.theme.PureThemeSpec
import net.pure.manager.theme.ThemeCatalog
import net.pure.manager.theme.ThemePrefs

/**
 * Shell = the part of the screen that changes shape between themes.
 *
 * Layout follows the reference the owner supplied (iCloud Drive): grey page,
 * white grouped cards, a large title that becomes a blurred bar when you scroll,
 * a toolbar with sort and view toggles, and a rounded floating button.
 *
 * Three navigation models are still driven by the same tokens, and every text
 * size comes from MaterialTheme.typography. Nothing here names an sp value or
 * compares a theme id against a literal except the Pixel pill, which is a
 * navigation-model detail rather than a screen concern.
 */

private enum class Screen(val label: String, val glyph: String) {
    FILES("Berkas", "\u25A4"),
    THEME("Tema", "\u25C8"),
    MODULES("Modul", "\u2726"),
    SETTINGS("Setelan", "\u2699"),
}

@Composable
fun PureShell(
    prefs: ThemePrefs,
    onPrefs: (ThemePrefs) -> Unit,
    recoveredFromCrash: Boolean = false,
) {
    val spec = LocalPureSpec.current
    val insets = LocalSystemInsets.current
    var screen by rememberSaveable { mutableStateOf(Screen.FILES) }
    // Selection mode is a browser concept but its on/off control sits in the top
    // bar, so the state lives here and is passed to both.
    var selectionMode by rememberSaveable { mutableStateOf(false) }
    var selectedCount by remember { mutableStateOf(0) }
    // One state shared by the blurred chrome: content registers as the source,
    // the bars draw the blur of it.
    val haze = remember { HazeState() }

    Box(Modifier.fillMaxSize().background(spec.palette.background)) {
        when (spec.nav) {
            NavModel.RAIL -> Row(Modifier.fillMaxSize()) {
                LeftRail(spec, screen, onSelect = { screen = it })
                Box(Modifier.weight(1f)) {
                    ScreenBody(
                        screen, prefs, onPrefs, spec, haze, recoveredFromCrash,
                        selectionMode, { selectionMode = it }, { selectedCount = it },
                    )
                }
            }
            NavModel.COMMAND_BAR -> Column(
                Modifier.fillMaxSize().padding(top = insets.top, bottom = insets.bottom)
            ) {
                Box(Modifier.weight(1f)) {
                    ScreenBody(
                        screen, prefs, onPrefs, spec, haze, recoveredFromCrash,
                        selectionMode, { selectionMode = it }, { selectedCount = it },
                    )
                }
                CommandBar(spec, screen, onSelect = { screen = it })
            }
            NavModel.TAB_BAR -> Box(Modifier.fillMaxSize()) {
                // Content runs full-height underneath both bars so the blur has
                // something to work with; each screen pads its own content.
                ScreenBody(
                        screen, prefs, onPrefs, spec, haze, recoveredFromCrash,
                        selectionMode, { selectionMode = it }, { selectedCount = it },
                    )
                Column(Modifier.fillMaxSize()) {
                    Spacer(Modifier.weight(1f))
                    TabBar(spec, screen, haze, onSelect = { screen = it })
                }
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
    haze: HazeState,
    onSelect: (Screen) -> Unit,
) {
    val p = spec.palette
    val insets = LocalSystemInsets.current
    GlassBar(
        spec = spec,
        state = haze,
        edge = true,
        modifier = Modifier.padding(bottom = insets.bottom),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp),
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
                        Box(
                            Modifier
                                .clip(RoundedCornerShape(spec.cornerDp.dp))
                                .background(p.accent.copy(alpha = 0.22f))
                                .padding(horizontal = 16.dp, vertical = 2.dp),
                        ) {
                            Text(
                                s.glyph,
                                style = MaterialTheme.typography.titleMedium,
                                color = p.accent,
                            )
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
}

// ---------------------------------------------------------------------- screens

@Composable
private fun ScreenBody(
    screen: Screen,
    prefs: ThemePrefs,
    onPrefs: (ThemePrefs) -> Unit,
    spec: PureThemeSpec,
    haze: HazeState,
    recoveredFromCrash: Boolean,
    selectionMode: Boolean,
    onSelectionModeChange: (Boolean) -> Unit,
    onSelectedCount: (Int) -> Unit,
) {
    val insets = LocalSystemInsets.current
    val scroll = rememberScrollState()
    var showRecoveryBanner by rememberSaveable { mutableStateOf(recoveredFromCrash) }
    // The large title collapses once the content has moved, which is when the
    // blurred top bar takes over and the small title appears in it.
    val collapsed = scroll.value > 40

    // Haze refuses a haze source that CONTAINS a hazeChild:
    //   "Layout nodes using Modifier.haze and Modifier.hazeChild can not be
    //    descendants of each other"
    // So the scrolling content is a sibling of the bars, both children of this
    // Box. `glassSource` therefore goes on the content column, never on a wrapper
    // that also holds a bar.
    Box(Modifier.fillMaxSize()) {
        Column(
            Modifier
                .fillMaxSize()
                .glassSource(spec, haze)
                .verticalScroll(scroll)
                .padding(
                    start = insets.start,
                    end = insets.end,
                )
                .padding(
                    start = spec.contentPaddingDp.dp,
                    end = spec.contentPaddingDp.dp,
                ),
        ) {
            // Space for the bar that floats above this content.
            Spacer(Modifier.height(insets.top + 58.dp))
            Column(Modifier.padding(bottom = 96.dp)) {
                when (screen) {
                    Screen.FILES -> {
                if (showRecoveryBanner) {
                    // Visible, dismissible, and it is the first thing on the
                    // screen: the point of safe mode is that the owner knows why
                    // the app looks different and where the report is.
                    Banner(
                        text = "Aplikasi sempat berhenti. Blur dimatikan dan tampilan " +
                            "dikembalikan ke awal. Laporan ada di Setelan.",
                        onDismiss = { showRecoveryBanner = false },
                    )
                    Spacer(Modifier.height(12.dp))
                }
                BrowserScreen(
                    spec = spec,
                    selectionMode = selectionMode,
                    onSelectionModeChange = onSelectionModeChange,
                    onSelectedCount = onSelectedCount,
                )
            }
                    Screen.THEME -> ThemeScreen(prefs, onPrefs)
                    Screen.MODULES -> ModulesScreen(spec)
                    Screen.SETTINGS -> SettingsScreen(prefs, onPrefs, spec)
                }
            }
        }

        // The bar is drawn last so it sits above the scrolling content, which is
        // also what its blur needs.
        TopBar(
            screen = screen,
            spec = spec,
            haze = haze,
            collapsed = collapsed,
            selectionActive = selectionMode,
            // TopBar only reports the tap. `selectionMode` is a val parameter of
            // ScreenBody, so assigning it is illegal -- my first "fix" wrapped the
            // same illegal assignment in a local val and would have failed again.
            // The state changes through the callbacks ScreenBody already receives.
            onToggleSelection = {
                val next = !selectionMode
                onSelectionModeChange(next)
                if (!next) onSelectedCount(0)
            },
        )
    }
}

@Composable
private fun TopBar(
    screen: Screen,
    spec: PureThemeSpec,
    haze: HazeState,
    collapsed: Boolean,
    selectionActive: Boolean,
    onToggleSelection: () -> Unit,
) {
    val p = spec.palette
    val insets = LocalSystemInsets.current
    GlassBar(
        spec = spec,
        state = haze,
        edge = false,
        modifier = Modifier.padding(top = insets.top),
    ) {
        Column(Modifier.padding(horizontal = spec.contentPaddingDp.dp)) {
            Row(
                Modifier.fillMaxWidth().height(48.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // The small title appears only once the large one has collapsed --
                // that is the iOS idiom. Drawing both at rest put "Berkas" twice on
                // the screen and made the glass bar tall enough to cover the search
                // field, which is what the owner's screenshot showed.
                if (!spec.useLargeTitle || collapsed) {
                    Text(
                        screen.label,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = p.onBackground,
                    )
                }
                Spacer(Modifier.weight(1f))
                if (screen == Screen.FILES) {
                    Text(
                        if (selectionActive) "Batal" else "Pilih",
                        style = MaterialTheme.typography.bodyLarge,
                        color = p.accent,
                        modifier = Modifier
                            .clip(RoundedCornerShape(spec.cornerDp.dp))
                            .clickable(onClick = onToggleSelection)
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                }
            }
            // The big title only exists while the page is at the top; that is the
            // whole iOS idiom and it needs no animation to read correctly.
            if (spec.useLargeTitle && !collapsed) {
                Text(
                    screen.label,
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                    color = p.onBackground,
                    modifier = Modifier.padding(top = 4.dp, bottom = 10.dp),
                )
            }
        }
    }
}

@Composable
private fun ThemeScreen(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette

    SectionLabel("TEMA")
    GroupCard(spec) {
        ThemeCatalog.forEach { t ->
            val selected = prefs.themeId == t.id
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable { onPrefs(prefs.copy(themeId = t.id)) }
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape((spec.cornerDp * 0.6f).dp))
                        .background(t.swatch),
                )
                Column(Modifier.weight(1f)) {
                    Text(
                        t.label,
                        style = MaterialTheme.typography.bodyLarge,
                        color = p.onBackground,
                    )
                    Text(
                        t.note,
                        style = MaterialTheme.typography.bodySmall,
                        color = p.onSurfaceVariant,
                    )
                }
                if (selected) {
                    Text(
                        "\u2713",
                        style = MaterialTheme.typography.titleLarge,
                        color = p.accent,
                    )
                }
            }
            Box(
                Modifier
                    .fillMaxWidth()
                    .padding(start = 54.dp)
                    .height(0.5.dp)
                    .background(p.separator),
            )
        }
    }

    SectionLabel("MODE")
    GroupCard(spec) {
        AppMode.entries.forEach { m ->
            ChoiceRow(
                spec = spec,
                label = when (m) {
                    AppMode.LIGHT -> "Terang"
                    AppMode.DARK -> "Gelap"
                    AppMode.AMOLED -> "AMOLED hitam total"
                },
                selected = prefs.mode == m,
                onClick = { onPrefs(prefs.copy(mode = m)) },
            )
        }
    }

    SectionLabel("AKSEN")
    GroupCard(spec) {
        Row(
            Modifier.fillMaxWidth().padding(14.dp),
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
    }

    SectionLabel("BENTUK & KEPADATAN")
    GroupCard(spec) {
        StepRow(
            title = "Sudut",
            value = "x${"%.1f".format(prefs.cornerScale)}",
            onLess = {
                onPrefs(prefs.copy(cornerScale = (prefs.cornerScale - 0.25f).coerceIn(0f, 2f)))
            },
            onMore = {
                onPrefs(prefs.copy(cornerScale = (prefs.cornerScale + 0.25f).coerceIn(0f, 2f)))
            },
        )
        StepRow(
            title = "Ukuran teks",
            value = "${(prefs.densityScale * 100).toInt()}%",
            onLess = {
                onPrefs(prefs.copy(densityScale = (prefs.densityScale - 0.05f).coerceIn(0.8f, 1.4f)))
            },
            onMore = {
                onPrefs(prefs.copy(densityScale = (prefs.densityScale + 0.05f).coerceIn(0.8f, 1.4f)))
            },
        )
        ChoiceRow(
            spec = spec,
            label = "Animasi",
            selected = prefs.animations,
            onClick = { onPrefs(prefs.copy(animations = !prefs.animations)) },
        )
    }
}

@Composable
private fun ChoiceRow(
    spec: PureThemeSpec,
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyLarge,
            color = p.onBackground,
            modifier = Modifier.weight(1f),
        )
        if (selected) {
            Text(
                "\u2713",
                style = MaterialTheme.typography.titleLarge,
                color = p.accent,
            )
        }
    }
}

@Composable
private fun ModulesScreen(spec: PureThemeSpec) {
    val p = spec.palette
    GroupCard(spec) {
        listOf(
            "Terminal" to "Belum tersedia \u2014 tahap 3",
            "Editor kode" to "Belum tersedia \u2014 tahap 6",
            "PDF & Office" to "Belum tersedia \u2014 tahap 5",
            "AI" to "Ditahan atas permintaan",
        ).forEach { (name, state) ->
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 13.dp)
            ) {
                Text(
                    name,
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onBackground,
                )
                Text(
                    state,
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
            Box(
                Modifier.fillMaxWidth().padding(start = 14.dp).height(0.5.dp).background(p.separator)
            )
        }
    }
    Spacer(Modifier.height(12.dp))
    Text(
        "Modul diunduh dari GitHub Releases pada tahap 4. Tidak ada modul yang " +
            "bisa dipasang sekarang, jadi tidak ada yang ditampilkan seolah bisa.",
        style = MaterialTheme.typography.bodySmall,
        color = p.onSurfaceVariant,
    )
}

@Composable
private fun SettingsScreen(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit, spec: PureThemeSpec) {
    val p = spec.palette
    val context = androidx.compose.ui.platform.LocalContext.current
    var crash by remember { mutableStateOf(PureCrash.read(context)) }
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    GroupCard(spec) {
        listOf(
            "Versi" to "0.3.0",
            "Tahap" to "T2 \u2014 peramban berkas",
            "Paket" to "net.pure.manager",
            "Android" to "10\u201316",
            "Tema" to spec.label,
            "Blur" to if (spec.chrome == ChromeStyle.GLASS) "Aktif (${spec.blurDp} dp)" else "Mati",
        ).forEach { (label, value) ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    label,
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onBackground,
                    modifier = Modifier.width(96.dp),
                )
                Text(
                    value,
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onSurfaceVariant,
                )
            }
            Box(
                Modifier.fillMaxWidth().padding(start = 14.dp).height(0.5.dp).background(p.separator)
            )
        }
    }
    if (spec.chrome == ChromeStyle.GLASS) {
        Spacer(Modifier.height(16.dp))
        SectionLabel("EFEK KACA")
        GroupCard(spec) {
            ChoiceRow(
                spec = spec,
                label = "Blur di balik bar",
                selected = prefs.blur,
                onClick = { onPrefs(prefs.copy(blur = !prefs.blur)) },
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            if (!blurSupported) {
                "Perangkat ini (Android ${android.os.Build.VERSION.SDK_INT}) belum mendukung " +
                    "blur RenderEffect. Yang tampil adalah lapisan tembus pandang, " +
                    "bukan kegagalan."
            } else {
                "Matikan kalau tampilan terasa berat atau bermasalah. " +
                    "Bar akan memakai lapisan tembus pandang, bukan kabur."
            },
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )
    }

    Spacer(Modifier.height(16.dp))
    SectionLabel("LAPORAN CRASH")
    if (crash == null) {
        Text(
            "Belum ada crash tercatat sejak aplikasi ini dipasang.",
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )
    } else {
        GroupCard(spec) {
            Text(
                crash!!,
                style = MaterialTheme.typography.bodySmall,
                color = p.onBackground,
                modifier = Modifier.padding(14.dp),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PillButton("Salin") {
                clipboard.setText(androidx.compose.ui.text.AnnotatedString(crash!!))
            }
            PillButton("Hapus") {
                PureCrash.clear(context)
                crash = null
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "Tidak dikirim ke mana pun. Tekan Salin, lalu tempel di chat.",
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )
    }

    Spacer(Modifier.height(16.dp))
    GroupCard(spec) {
        ChoiceRow(
            spec = spec,
            label = "Setel ulang tampilan",
            selected = false,
            onClick = { onPrefs(ThemePrefs()) },
        )
    }
    Spacer(Modifier.height(12.dp))
    Text(
        "Kembali ke iOS, gelap, aksen biru, ukuran 100%.",
        style = MaterialTheme.typography.bodySmall,
        color = p.onSurfaceVariant,
    )
}

// ------------------------------------------------------------------- components

@Composable
private fun Banner(text: String, onDismiss: () -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(p.accent.copy(alpha = 0.14f))
            .border(0.75.dp, p.accent, RoundedCornerShape(spec.cornerDp.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            text,
            style = MaterialTheme.typography.bodySmall,
            color = p.onBackground,
            modifier = Modifier.weight(1f),
        )
        Box(
            Modifier
                .clip(RoundedCornerShape(spec.cornerDp.dp))
                .clickable(onClick = onDismiss)
                .padding(6.dp),
        ) {
            Text("OK", style = MaterialTheme.typography.labelMedium, color = p.accent)
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    val p = LocalPureSpec.current.palette
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.SemiBold,
        color = p.onSurfaceVariant,
        modifier = Modifier.padding(top = 18.dp, bottom = 6.dp, start = 4.dp),
    )
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
        StepButton("\u2212", p.onBackground, onLess)
        Spacer(Modifier.width(8.dp))
        StepButton("+", p.onAccent, onMore, filled = true)
    }
    Box(Modifier.fillMaxWidth().padding(start = 14.dp).height(0.5.dp).background(p.separator))
}

@Composable
private fun PillButton(label: String, onClick: () -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Box(
        Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(p.surface)
            .border(0.75.dp, p.separator, RoundedCornerShape(spec.cornerDp.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 18.dp, vertical = 10.dp),
    ) {
        Text(label, style = MaterialTheme.typography.bodyLarge, color = p.accent)
    }
}

@Composable
private fun StepButton(
    label: String,
    contentColor: Color,
    onClick: () -> Unit,
    filled: Boolean = false,
) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Box(
        Modifier
            .size(34.dp)
            .clip(CircleShape)
            .background(if (filled) p.accent else p.surfaceVariant)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium, color = contentColor)
    }
}
