package app.breakfast.manager.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.data.RootStatus
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.Chip
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors

/**
 * The ROOT page.
 *
 * It was a placeholder with one button and the sentence "halamannya belum
 * dibuat", which is why it looked unfinished. It now reports the facts the app
 * actually depends on, each of them checked rather than assumed.
 */
@Composable
fun RootScreen(
    snapshot: RootStatus.Snapshot?,
    message: String?,
    onRequestRoot: () -> Unit,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val c = LocalBreakfastColors.current
    Column(
        modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 16.dp),
    ) {
        SectionLabel("status root")
        SurfaceCard {
            if (snapshot == null) {
                Text(
                    text = "Belum diperiksa.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textSecondary,
                )
            } else {
                for ((label, value) in snapshot.lines()) {
                    val colour = when {
                        label == "root" && snapshot.granted -> c.statusStable
                        label == "root" -> c.statusAttention
                        value.startsWith("tidak") -> c.statusAttention
                        else -> c.textPrimary
                    }
                    DataRow(
                        label = label,
                        value = value,
                        valueColor = colour,
                        // Paths and uid are machine text; prose is not.
                        mono = label in setOf("su", "uid proses", "pengelola root"),
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            AccentButton(
                text = if (snapshot?.granted == true) "PERIKSA ULANG" else "BERI ROOT",
                onClick = if (snapshot?.granted == true) onRefresh else onRequestRoot,
                modifier = Modifier.fillMaxWidth(),
            )
            if (message != null) {
                Spacer(Modifier.height(10.dp))
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textSecondary,
                )
            }
        }

        Spacer(Modifier.height(16.dp))
        SectionLabel("yang dibutuhkan root")
        SurfaceCard {
            // Explains why the app keeps asking, and what each grant unlocks.
            for ((what, why) in listOf(
                "dmesg" to "skor Stability Ledger; tanpa izin ini skornya \"—\", bukan nol",
                "menulis node" to "TUNING hanya bisa menerapkan nilai kalau kernel mengizinkan tulis",
                "zram dan termal" to "sebagian node hanya bisa dibaca dengan uid 0",
            )) {
                Text(
                    text = what,
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textPrimary,
                )
                Text(
                    text = why,
                    fontSize = 11.sp,
                    lineHeight = 15.sp,
                    color = c.textTertiary,
                )
                Spacer(Modifier.height(10.dp))
            }
        }

        Spacer(Modifier.height(16.dp))
        if (snapshot != null && snapshot.manager == null) {
            Chip("tanpa pengelola root", c.statusAttention, filled = true)
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Tidak ada penanda KernelSU, Magisk, atau APatch yang terbaca. " +
                    "Kalau perangkat ini sebenarnya ber-root, kemungkinan besar aplikasi " +
                    "tidak diizinkan melihat /data/adb.",
                fontSize = 11.sp,
                lineHeight = 15.sp,
                color = c.textTertiary,
            )
        }
    }
}
