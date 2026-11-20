package app.breakfast.manager.ui.screens

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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.ui.ThemeCatalog
import app.breakfast.manager.ui.components.GhostButton
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.ui.theme.LocalBreakfastColors
import app.breakfast.manager.ui.theme.colorsFor

/**
 * Theme picker, overlaid rather than routed.
 *
 * Every palette shown here has already passed the WCAG contrast check in
 * ThemeCatalog, and the swatch preview uses the palette's own accent against its
 * own background, so what you pick is what the app will actually look like.
 */
@Composable
fun SettingsSheet(
    visible: Boolean,
    current: ThemeCatalog.Palette,
    onPick: (ThemeCatalog.Palette) -> Unit,
    onDismiss: () -> Unit,
    /** Ticker interval in seconds; the dashboard samples at this rate. */
    intervalSeconds: Int = 2,
    intervalOptions: List<Int> = listOf(1, 2, 5, 10),
    onIntervalPick: (Int) -> Unit = {},
    /** Audit cadence is fixed by design, but it is stated here where it belongs. */
    auditCooldownSeconds: Int = 30,
    kernelRelease: String = "—",
    variantName: String = "—",
    onRunAudit: () -> Unit = {},
    onResetSettings: () -> Unit = {},
) {
    if (!visible) return
    val c = LocalBreakfastColors.current

    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.55f))
            .clickable { onDismiss() },
        contentAlignment = Alignment.BottomCenter,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp))
                .background(c.surface)
                .border(1.dp, c.hairline, RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp))
                // Swallow taps inside the sheet so they do not dismiss it.
                .clickable(enabled = false) {}
                .padding(20.dp),
        ) {
            Text(
                text = "SETELAN",
                style = MaterialTheme.typography.headlineMedium,
                color = c.textPrimary,
            )
            Text(
                text = "Tampilan, laju pembaruan, dan diagnostik. Tidak ada yang dikirim keluar perangkat.",
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )

            Spacer(Modifier.height(14.dp))
            SectionLabel("laju pembaruan")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (option in intervalOptions) {
                    ChoiceChip(
                        label = "${option} detik",
                        selected = option == intervalSeconds,
                        onClick = { onIntervalPick(option) },
                    )
                }
            }
            Text(
                text = "Dashboard mengambil sampel tiap ${intervalSeconds} detik. " +
                    "Audit penuh punya jeda ${auditCooldownSeconds} detik karena " +
                    "membaca ${DeviceAudit.totalNodeCount()} node.",
                fontSize = 11.sp,
                lineHeight = 15.sp,
                color = c.textTertiary,
            )

            Spacer(Modifier.height(16.dp))
            SectionLabel("tema")
            Text(
                text = "Kelima tema lolos kontras WCAG. Warna status tidak ikut berubah.",
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )
            Spacer(Modifier.height(14.dp))

            for (palette in ThemeCatalog.offered()) {
                val preview = colorsFor(palette)
                val selected = palette.id == current.id
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(if (selected) c.accentSoft else Color.Transparent)
                        .border(
                            1.dp,
                            if (selected) c.accent else c.hairline,
                            RoundedCornerShape(14.dp),
                        )
                        .clickable { onPick(palette) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    // Live swatch: the palette's own background with its accent.
                    Box(
                        Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(preview.background)
                            .border(2.dp, preview.accent, CircleShape),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(text = "◉", fontSize = 13.sp, color = preview.accent)
                    }
                    Column(Modifier.weight(1f)) {
                        Text(
                            text = palette.displayName,
                            style = MaterialTheme.typography.titleMedium,
                            color = c.textPrimary,
                        )
                        Text(
                            text = if (preview.isDense) "padat · animasi cepat" else "lega · animasi halus",
                            fontSize = 11.sp,
                            color = c.textTertiary,
                        )
                    }
                    if (selected) {
                        Text(text = "AKTIF", fontSize = 10.sp, color = c.accent)
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            SectionLabel("tentang")
            SurfaceCard {
                DataRow("Kernel", kernelRelease, c.textPrimary, mono = true)
                DataRow("Varian", variantName, c.textPrimary)
                DataRow(
                    "Izin",
                    "tidak ada izin Android yang diminta",
                    c.textSecondary,
                    note = "semua pembacaan lewat file dan su, bukan API berizin",
                )
            }

            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                GhostButton("AUDIT SEKARANG", onRunAudit, modifier = Modifier.weight(1f))
                GhostButton("KEMBALIKAN", onResetSettings, modifier = Modifier.weight(1f))
            }
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Pilihan disimpan di perangkat ini saja. Tema tidak mengubah status merah/hijau.",
                fontSize = 11.sp,
                color = c.textTertiary,
            )
            Spacer(Modifier.height(8.dp))
        }
    }
}
