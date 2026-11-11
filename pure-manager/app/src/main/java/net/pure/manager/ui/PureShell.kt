package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.pure.manager.theme.AccentChoices
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.NavModel
import net.pure.manager.theme.ThemePrefs

/**
 * Shell = the part of the screen that changes shape between themes.
 *
 * Three navigation models live here, and all three are driven by the same tokens.
 * Screens are passed in; none of them knows which model is active.
 */
@Composable
fun PureShell(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Box(Modifier.fillMaxSize().background(p.background)) {
        when (spec.nav) {
            NavModel.RAIL -> Row(Modifier.fillMaxSize()) {
                LeftRail(spec)
                Box(Modifier.weight(1f)) { ContentColumn(prefs, onPrefs, compact = spec.compactRows) }
            }
            NavModel.COMMAND_BAR -> Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f)) { ContentColumn(prefs, onPrefs, compact = spec.compactRows) }
                CommandBar(spec)
            }
            NavModel.TAB_BAR -> Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f)) { ContentColumn(prefs, onPrefs, compact = spec.compactRows) }
                TabBar(spec)
            }
        }
    }
}

@Composable
private fun LeftRail(spec: net.pure.manager.theme.PureThemeSpec) {
    val p = spec.palette
    Column(
        Modifier
            .width(52.dp)
            .fillMaxHeight()
            .background(p.surfaceVariant)
            .border(0.5.dp, p.outline)
            .padding(top = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(22.dp),
    ) {
        Text("▤", color = p.accent, fontSize = 15.sp)
        Text("◈", color = p.onSurfaceVariant, fontSize = 15.sp)
        Text("✦", color = p.onSurfaceVariant, fontSize = 15.sp)
        Text("⚙", color = p.onSurfaceVariant, fontSize = 15.sp)
    }
}

@Composable
private fun CommandBar(spec: net.pure.manager.theme.PureThemeSpec) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .background(p.surface)
            .border(0.5.dp, p.outline)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("[F1] FILES", color = p.accent, fontSize = 9.sp, fontWeight = FontWeight.Bold)
        Text("[F2] TEMA", color = p.onSurfaceVariant, fontSize = 9.sp)
        Text("[F3] MODUL", color = p.onSurfaceVariant, fontSize = 9.sp)
        Text("[F4] SET", color = p.onSurfaceVariant, fontSize = 9.sp)
    }
}

@Composable
private fun TabBar(spec: net.pure.manager.theme.PureThemeSpec) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .background(p.surface)
            .border(0.5.dp, p.outline)
            .padding(top = 8.dp, bottom = 18.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        listOf("▤" to "Berkas", "◈" to "Tema", "✦" to "Modul", "⚙" to "Setelan")
            .forEachIndexed { i, (glyph, label) ->
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    if (i == 1 && spec.id == "pixel") {
                        // M3 pill indicator, drawn as a token-driven shape rather
                        // than a Material component so the radius follows the theme.
                        Box(
                            Modifier
                                .clip(RoundedCornerShape(spec.cornerDp.dp))
                                .background(p.accent.copy(alpha = 0.22f))
                                .padding(horizontal = 14.dp, vertical = 2.dp),
                        ) { Text(glyph, color = p.accent, fontSize = 12.sp) }
                    } else {
                        Text(
                            glyph,
                            color = if (i == 0) p.accent else p.onSurfaceVariant,
                            fontSize = 12.sp,
                        )
                    }
                    Spacer(Modifier.height(2.dp))
                    Text(
                        label,
                        color = if (i == 0) p.accent else p.onSurfaceVariant,
                        fontSize = 8.5.sp,
                    )
                }
            }
    }
}

@Composable
private fun ContentColumn(
    prefs: ThemePrefs,
    onPrefs: (ThemePrefs) -> Unit,
    compact: Boolean,
) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Column(
        Modifier
            .fillMaxSize()
            .padding(horizontal = spec.contentPaddingDp.dp)
            .padding(top = 44.dp),
    ) {
        if (spec.nav != NavModel.RAIL) {
            Text("Berkas", color = p.onBackground, fontSize = 22.sp,
                fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))
        }
        SampleList(spec, compact)
        Spacer(Modifier.height(12.dp))
        ColourStrip(prefs, onPrefs)
    }
}

@Composable
private fun ColourStrip(prefs: ThemePrefs, onPrefs: (ThemePrefs) -> Unit) {
    // Interim control so the token wiring can be seen working on-device before the
    // full Customisation tab is built in the next slice.
    val spec = LocalPureSpec.current
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        AccentChoices.forEachIndexed { i, (_, colour) ->
            Box(
                Modifier
                    .size(26.dp)
                    .clip(CircleShape)
                    .background(colour)
                    .border(
                        width = if (prefs.accentIndex == i) 2.dp else 0.dp,
                        color = spec.palette.onBackground,
                        shape = CircleShape,
                    ),
            )
        }
    }
}

private data class DemoFile(val letter: String, val name: String, val size: String)

@Composable
private fun SampleList(spec: net.pure.manager.theme.PureThemeSpec, compact: Boolean) {
    val p = spec.palette
    val files = listOf(
        DemoFile("R", "Retro-Arcade.apk", "24.1 MB"),
        DemoFile("Z", "Manager-6.1.zip", "18.7 MB"),
        DemoFile("P", "banner-review.png", "640 KB"),
        DemoFile("T", "theme-signing.key", "3.4 KB"),
        DemoFile("A", "voice-note.m4a", "2.1 MB"),
    )
    Column(verticalArrangement = Arrangement.spacedBy(if (compact) 2.dp else 10.dp)) {
        files.forEach { f ->
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
                    .padding(horizontal = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Box(
                    Modifier
                        .size(26.dp)
                        .clip(RoundedCornerShape((spec.cornerDp * 0.55f).dp))
                        .background(p.accent),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(f.letter, color = p.onAccent, fontSize = 10.sp,
                        fontWeight = FontWeight.Bold)
                }
                Column(Modifier.weight(1f)) {
                    Text(f.name, color = p.onBackground, fontSize = 12.sp,
                        fontWeight = FontWeight.Medium)
                    if (!compact) {
                        Text(f.size, color = p.onSurfaceVariant, fontSize = 10.sp)
                    }
                }
                if (compact) {
                    Text(f.size, color = p.onSurfaceVariant, fontSize = 10.sp)
                } else {
                    Text("›", color = p.onSurfaceVariant, fontSize = 15.sp)
                }
            }
        }
    }
}
