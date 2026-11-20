package app.breakfast.manager.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.ui.PulseReadings
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.Chip
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.PulseRing
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.Sparkline
import app.breakfast.manager.ui.components.StatTile
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors
import app.breakfast.manager.ui.theme.NumericStyle

/**
 * PULSE - the dashboard.
 *
 * Layout follows design/breakfast/preview/01-pulse-fresh-milk.jpg: title block
 * with the kernel variant as a pill, the temperature ring, a four-across stat
 * row, then the three sixty-second graphs. The difference from the design sheet
 * is that every number here is read from the device on a timer; nothing is
 * mocked, and anything unreadable shows a dash.
 */
@Composable
fun PulseScreen(
    variantLabel: String,
    variantPaired: Boolean,
    readings: PulseReadings,
    uptimeText: String,
    auditAgeText: String,
    modifier: Modifier = Modifier,
    onOpenAudit: () -> Unit,
    onOpenSettings: () -> Unit = {},
    onRequestRoot: () -> Unit = {},
    rootMessage: String? = null,
) {
    val c = LocalBreakfastColors.current
    val tempColor = when {
        readings.temperatureC == null -> c.textTertiary
        readings.temperatureC < 45f -> c.statusStable
        readings.temperatureC < 60f -> c.statusAttention
        else -> c.statusTrouble
    }

    LazyColumn(
        modifier = modifier.fillMaxWidth().background(c.background),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 104.dp),
    ) {
        item {
            Row(
                Modifier.fillMaxWidth().padding(top = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        text = "BREAKFAST",
                        style = MaterialTheme.typography.headlineMedium,
                        color = c.textPrimary,
                    )
                    Text(
                        text = "Kernel Manager",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                }
                // Settings is administrative, not device state, so the design
                // puts it here rather than in the dock.
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(c.surface)
                        .border(1.dp, c.hairline, CircleShape)
                        .clickable { onOpenSettings() },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(text = "⚙", fontSize = 16.sp, color = c.textSecondary)
                }
            }
            Spacer(Modifier.height(10.dp))
            Chip(
                text = variantLabel,
                color = if (variantPaired) c.accent else c.statusAttention,
                filled = true,
            )
            Spacer(Modifier.height(18.dp))
        }

        if (!readings.hasRoot) {
            item {
                // The dashboard cannot show half its numbers without root, and on
                // the reporting device it simply showed dashes. Asking out loud,
                // with the reason and a button, is the difference between "this
                // app is broken" and "this app needs a permission".
                SurfaceCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Chip("tanpa root", c.statusAttention, filled = true)
                    }
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = rootMessage
                            ?: "Suhu, zram, audit, dan skor stabilitas butuh root. Tanpa itu semuanya tampil \"—\".",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textPrimary,
                    )
                    Spacer(Modifier.height(12.dp))
                    AccentButton("BERI ROOT", onRequestRoot)
                }
                Spacer(Modifier.height(12.dp))
            }
        }

        item {
            SurfaceCard(padding = 8.dp) {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    PulseRing(
                        value = readings.temperatureC,
                        max = 90f,
                        label = "CPU",
                        caption = readings.thermalLabel,
                        color = tempColor,
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                StatTile(
                    glyph = "▦",
                    label = "ZRAM",
                    value = readings.zramPercent?.let { "${it.toInt()}%" } ?: "—",
                    valueColor = c.textPrimary,
                    modifier = Modifier.weight(1f),
                )
                StatTile(
                    glyph = "◷",
                    label = "UPTIME",
                    value = uptimeText,
                    valueColor = c.textPrimary,
                    modifier = Modifier.weight(1f),
                )
                StatTile(
                    glyph = "❧",
                    label = "MGLRU",
                    // Same wording as the STATUS row: absent is a fact about the
                    // kernel, not a failed read, so both say TIDAK ADA.
                    value = when (readings.mglruEnabled) {
                        true -> "ON"
                        false -> "OFF"
                        null -> "N/A"
                    },
                    valueColor = when (readings.mglruEnabled) {
                        true -> c.statusStable
                        false -> c.statusAttention
                        null -> c.statusAttention
                    },
                    modifier = Modifier.weight(1f),
                )
                StatTile(
                    glyph = "✓",
                    label = "STABILITY",
                    value = readings.stabilityScore?.toString() ?: "—",
                    valueColor = when {
                        readings.stabilityScore == null -> c.textTertiary
                        readings.stabilityScore >= 90 -> c.statusStable
                        readings.stabilityScore >= 70 -> c.statusNormal
                        readings.stabilityScore >= 40 -> c.statusAttention
                        else -> c.statusTrouble
                    },
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.height(20.dp))
        }

        item {
            Text(
                text = "System Overview",
                style = MaterialTheme.typography.titleMedium,
                color = c.textPrimary,
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                text = "60 detik terakhir · diperbarui tiap 2 detik",
                fontSize = 11.sp,
                color = c.textTertiary,
            )
            Spacer(Modifier.height(10.dp))
        }

        item {
            GraphCard(
                title = "CPU Load",
                subtitle = readings.cpuLoadReason
                    ?: readings.governor
                    ?: "governor tidak terbaca",
                value = readings.cpuUsagePercent?.let { "${it.toInt()}%" } ?: "—",
                valueColor = c.accent,
                series = readings.cpuLoadHistory,
                color = c.accent,
                normalise = false,
            )
            Spacer(Modifier.height(10.dp))
        }

        item {
            GraphCard(
                title = "Memory",
                subtitle = if (readings.memoryUsedGb != null && readings.memoryTotalGb != null) {
                    "%.1f GB / %.0f GB".format(readings.memoryUsedGb, readings.memoryTotalGb)
                } else {
                    "tidak terbaca"
                },
                value = readings.memoryHistory.lastOrNull()?.let { "${it.toInt()}%" } ?: "—",
                valueColor = c.textPrimary,
                series = readings.memoryHistory,
                color = c.statusNormal,
                normalise = false,
                // Percentages have a meaningful ceiling; auto-scaling made a flat
                // 62% look like a flat 0%.
                fixedMax = 100f,
            )
            Spacer(Modifier.height(10.dp))
        }

        item {
            GraphCard(
                title = "Thermals",
                subtitle = when (readings.temperatureC) {
                    null -> "suhu tidak tersedia"
                    else -> readings.thermalLabel
                },
                value = readings.temperatureC?.let { "${it.toInt()}°C" } ?: "—",
                valueColor = tempColor,
                series = readings.thermalHistory,
                color = tempColor,
                normalise = false,
            )
            Spacer(Modifier.height(18.dp))
        }

        item {
            SectionLabel("status")
            SurfaceCard {
                DataRow(
                    label = "Stability Ledger",
                    value = readings.stabilityScore?.toString() ?: "—",
                    valueColor = c.textPrimary,
                    mono = true,
                    note = if (readings.stabilityScore == null) {
                        "dmesg tidak terbaca: skor tidak dikarang"
                    } else {
                        "dihitung sejak boot, bukan sejak aplikasi dibuka"
                    },
                )
                DataRow(
                    label = "MGLRU",
                    value = readings.mglruRaw?.trim()?.takeIf { it.isNotEmpty() } ?: "TIDAK ADA",
                    // MGLRU absent is a kernel fact, not a read failure, so it is
                    // labelled TIDAK ADA rather than an em dash. The tile above
                    // uses the same rule now; before, one said "—" and the other
                    // "TIDAK ADA" for the same node.
                    valueColor = if (readings.mglruRaw.isNullOrBlank()) c.statusAttention else c.textPrimary,
                    mono = true,
                    note = "nilai mentah dari kernel, bukan tafsiran",
                )
                DataRow(
                    label = "Audit terakhir",
                    // This row used to print uptime, which was simply the wrong
                    // fact under that label.
                    value = auditAgeText,
                    valueColor = c.textSecondary,
                    note = "buka LAB untuk melihat 16 node yang diperiksa",
                )
            }
        }
    }
}

@Composable
private fun GraphCard(
    title: String,
    subtitle: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color,
    series: List<Float>,
    color: androidx.compose.ui.graphics.Color,
    normalise: Boolean,
    fixedMax: Float? = null,
) {
    val c = LocalBreakfastColors.current
    SurfaceCard(padding = 14.dp) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = c.textPrimary,
                )
                Text(text = subtitle, fontSize = 11.sp, color = c.textTertiary)
            }
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium.merge(NumericStyle),
                fontWeight = FontWeight.Bold,
                color = valueColor,
                textAlign = TextAlign.End,
            )
        }
        Spacer(Modifier.height(8.dp))
        Sparkline(
            series = series,
            color = color,
            height = 46.dp,
            normalise = normalise,
            fixedMax = fixedMax,
        )
    }
}
