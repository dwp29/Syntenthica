package app.breakfast.manager.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.screens.LabScreen
import app.breakfast.manager.ui.screens.PulseScreen
import app.breakfast.manager.ui.screens.TuningScreen
import app.breakfast.manager.ui.theme.LocalBreakfastColors

/** The five destinations from design/breakfast/README.md. */
enum class Tab(val label: String, val glyph: String) {
    PULSE("PULSE", "◉"),
    ROOT("ROOT", "⛨"),
    MODULES("MODULES", "❐"),
    TUNING("TUNING", "⇅"),
    LAB("LAB", "⚗"),
}

/**
 * App shell: one Scaffold-like column with a floating dock.
 *
 * The dock is the only navigation; Settings lives behind a glyph in the future,
 * per the design brief, because administration is not device state. Tabs that
 * this build does not implement yet still exist and say so plainly instead of
 * being silently missing - an absent tab would leave the user wondering where
 * the feature went.
 */
@Composable
fun BreakfastApp(
    state: BreakfastUiState,
    modifier: Modifier = Modifier,
    onOpenSettings: () -> Unit = {},
) {
    val c = LocalBreakfastColors.current
    var tab by remember { mutableStateOf(Tab.PULSE) }

    Box(modifier.fillMaxSize().background(c.background)) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f)) {
                AnimatedContent(
                    targetState = tab,
                    transitionSpec = {
                        fadeIn(tween(c.motionMs)) togetherWith fadeOut(tween(c.motionMs / 2))
                    },
                    label = "tab",
                ) { target ->
                    when (target) {
                        Tab.PULSE -> PulseScreen(
                            variantLabel = state.variantLabel,
                            variantPaired = state.variantPaired,
                            readings = state.readings,
                            uptimeText = state.uptimeText,
                            auditAgeText = state.auditAgeText,
                            onOpenAudit = state.onAudit,
                            onOpenSettings = onOpenSettings,
                            onRequestRoot = state.onRequestRoot,
                            rootMessage = state.rootMessage,
                        )

                        Tab.TUNING -> TuningScreen(
                            report = state.report,
                            tuningEnabled = state.tuningEnabled,
                            tuningReason = state.tuningReason,
                            hasRoot = state.hasRoot,
                            canReset = state.canReset,
                            onApply = state.onApply,
                            onReset = state.onReset,
                            onAudit = state.onAudit,
                        )

                        Tab.LAB -> LabScreen(
                            report = state.report,
                            readings = state.readings,
                            hasRoot = state.hasRoot,
                            ledger = state.ledger,
                            ledgerReason = state.ledgerReason,
                            auditing = state.auditing,
                            onAudit = state.onAudit,
                        )

                        Tab.ROOT, Tab.MODULES -> ComingSoon(
                            tab = target,
                            state = state,
                            onAction = if (target == Tab.ROOT) state.onRequestRoot else state.onAudit,
                        )
                    }
                }
            }
            BottomDock(selected = tab, onSelect = { tab = it })
        }
    }
}

/**
 * A page that is not built yet, plus a way out.
 *
 * The empty-state rule in SPEC-LAYAR says an empty screen must carry one action,
 * because a screen with no button is a dead end. The first version of this page
 * broke that rule; it now offers the action that is actually useful here - grant
 * root, or re-run the audit.
 */
@Composable
private fun ComingSoon(tab: Tab, state: BreakfastUiState, onAction: () -> Unit) {
    val c = LocalBreakfastColors.current
    Column(
        Modifier.fillMaxSize().padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(80.dp))
        Text(
            text = tab.glyph,
            fontSize = 44.sp,
            color = c.accent.copy(alpha = 0.5f),
        )
        Spacer(Modifier.height(16.dp))
        Text(
            text = tab.label,
            style = MaterialTheme.typography.headlineMedium,
            color = c.textPrimary,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            text = when (tab) {
                Tab.ROOT -> "Daftar aplikasi superuser dan mode hook belum ada di build ini. " +
                    "Root tetap dipakai untuk dmesg dan sysfs; halamannya belum dibuat."
                Tab.MODULES -> "Daftar modul terpasang belum ada di build ini. " +
                    "Mengelola modul butuh antarmuka instalasi yang belum dibangun."
                else -> ""
            },
            style = MaterialTheme.typography.bodyMedium,
            color = c.textSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        AccentButton(
            text = if (tab == Tab.ROOT) "BERI ROOT" else "AUDIT ULANG",
            onClick = onAction,
            modifier = Modifier.fillMaxWidth(0.8f),
        )
        Spacer(Modifier.height(14.dp))
        Text(
            text = "Kernel ${state.kernelRelease}",
            fontSize = 11.sp,
            color = c.textTertiary,
        )
    }
}

/**
 * Floating dock. Selection is marked with a filled plate and the accent colour;
 * the plate is the only rounded-rectangle highlight in the bar, so the eye can
 * find the current tab without reading.
 */
@Composable
private fun BottomDock(selected: Tab, onSelect: (Tab) -> Unit) {
    val c = LocalBreakfastColors.current
    Box(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(24.dp))
                .background(c.surface.copy(alpha = 0.96f))
                .border(1.dp, c.hairline, RoundedCornerShape(24.dp))
                .padding(horizontal = 6.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            for (tab in Tab.entries) {
                val active = tab == selected
                Column(
                    modifier = Modifier
                        .clip(RoundedCornerShape(16.dp))
                        .clickable { onSelect(tab) }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Box(
                        Modifier
                            .size(28.dp)
                            .clip(CircleShape)
                            .background(if (active) c.accentSoft else Color.Transparent),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = tab.glyph,
                            fontSize = 13.sp,
                            color = if (active) c.accent else c.textTertiary,
                        )
                    }
                    Spacer(Modifier.height(3.dp))
                    Text(
                        text = tab.label,
                        fontSize = 9.sp,
                        letterSpacing = 0.8.sp,
                        color = if (active) c.accent else c.textTertiary,
                    )
                }
            }
        }
    }
}
