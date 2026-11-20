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
import app.breakfast.manager.data.ModuleScan
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors

/**
 * Loaded kernel modules, read from /proc/modules.
 *
 * The page previously said the module list "belum ada di build ini", which was
 * false: /proc/modules is world-readable and the device has modules. This lists
 * what is loaded, and says so plainly when the file itself cannot be read.
 */
@Composable
fun ModulesScreen(
    modules: List<ModuleScan.Module>?,
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
        SectionLabel("modul termuat")
        SurfaceCard {
            when {
                modules == null -> {
                    Text(
                        text = "Daftar modul tidak bisa dibaca. /proc/modules tidak terbuka, " +
                            "jadi ini bukan pernyataan bahwa tidak ada modul.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.statusAttention,
                    )
                }
                modules.isEmpty() -> {
                    Text(
                        text = "Kernel ini tidak memuat modul apa pun yang terdaftar di " +
                            "/proc/modules. Banyak kernel OpenELA membangun driver secara " +
                            "statis, jadi daftar kosong adalah fakta kernel, bukan kesalahan.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                }
                else -> {
                    Text(
                        text = "${modules.size} modul termuat",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                    Spacer(Modifier.height(6.dp))
                    for (module in modules) {
                        DataRow(
                            label = module.name,
                            value = "${module.sizeBytes / 1024} KiB",
                            valueColor = c.textPrimary,
                            mono = true,
                            note = if (module.usedBy.isEmpty()) null else "dipakai: ${module.usedBy}",
                        )
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            AccentButton("PERIKSA ULANG", onRefresh, modifier = Modifier.fillMaxWidth())
        }

        Spacer(Modifier.height(14.dp))
        Text(
            // Says what is NOT built, so the empty part of the feature is not a mystery.
            text = "Mengaktifkan atau menonaktifkan modul belum ada di build ini: itu butuh " +
                "modprobe dengan root dan rollback, dan mengubah modul bisa membuat perangkat " +
                "tidak bisa boot. Saya tidak akan menambahkannya tanpa jalur pemulihan.",
            fontSize = 11.sp,
            lineHeight = 16.sp,
            color = c.textTertiary,
        )
    }
}
