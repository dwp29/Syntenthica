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
 * Every row carries its own confidence: a value read from the KernelSU library,
 * a value from a shell command, or a value from a filesystem probe. When the
 * probe was blind, the row says "tidak bisa dipastikan" and never "tidak ada",
 * because on this device the two were the same string and it was wrong.
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
                    text = "Sedang memeriksa…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textSecondary,
                )
            } else {
                for ((label, fact) in snapshot.lines()) {
                    val colour = when {
                        fact.sure == RootStatus.Sure.UNKNOWN -> c.statusAttention
                        label == "root" && snapshot.granted -> c.statusStable
                        label == "root" -> c.statusAttention
                        fact.value.startsWith("tidak") || fact.value == "belum diberikan" ->
                            c.statusAttention
                        else -> c.textPrimary
                    }
                    DataRow(
                        label = label,
                        value = fact.value,
                        valueColor = colour,
                        mono = label in setOf("su", "uid proses"),
                        note = fact.note,
                    )
                }

                val library = snapshot.libraryLines()
                if (library.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = "Dari libkernelsu.so",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                    for ((label, value) in library) {
                        DataRow(label, value, c.textPrimary, mono = true)
                    }
                }

                Spacer(Modifier.height(12.dp))
                Text(
                    text = snapshot.verdict(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textPrimary,
                )
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
        SectionLabel("cara aplikasi memeriksa")
        SurfaceCard {
            // The order matters and is the reason the answer changed: the library
            // cannot be spoofed by a file the sandbox cannot see.
            for ((step, detail) in listOf(
                "1. libkernelsu.so" to
                    "Ditanyakan lebih dulu. Hanya kernel KernelSU yang menjawab, dan " +
                    "jawabannya tidak bergantung pada izin berkas.",
                "2. perintah su" to
                    "Untuk uid dan untuk memastikan izin benar-benar diberikan, bukan " +
                    "hanya terpasang.",
                "3. jalur berkas" to
                    "Terakhir, dan hanya dipercaya kalau direktorinya memang bisa dibaca. " +
                    "Kalau tidak, hasilnya \"tidak bisa dipastikan\".",
            )) {
                Text(step, style = MaterialTheme.typography.bodyMedium, color = c.textPrimary)
                Text(detail, fontSize = 11.sp, lineHeight = 15.sp, color = c.textTertiary)
                Spacer(Modifier.height(10.dp))
            }
        }

        Spacer(Modifier.height(16.dp))
        SectionLabel("yang dibutuhkan root")
        SurfaceCard {
            for ((what, why) in listOf(
                "dmesg" to "skor Stability Ledger; tanpa izin ini skornya \"—\", bukan nol",
                "menulis node" to "TUNING hanya menerapkan nilai kalau kernel mengizinkan tulis",
                "zram dan termal" to "sebagian node hanya bisa dibaca dengan uid 0",
            )) {
                Text(what, style = MaterialTheme.typography.bodyMedium, color = c.textPrimary)
                Text(why, fontSize = 11.sp, lineHeight = 15.sp, color = c.textTertiary)
                Spacer(Modifier.height(10.dp))
            }
        }

        Spacer(Modifier.height(16.dp))
        if (snapshot != null && snapshot.manager.sure != RootStatus.Sure.UNKNOWN &&
            snapshot.manager.value == "tidak ditemukan"
        ) {
            Chip("tanpa pengelola root", c.statusAttention, filled = true)
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Direktori yang diperiksa bisa dibaca, dan tidak ada penanda KernelSU, " +
                    "Magisk, atau APatch di dalamnya. Itu kesimpulan, bukan tebakan.",
                fontSize = 11.sp,
                lineHeight = 15.sp,
                color = c.textTertiary,
            )
        }
    }
}
