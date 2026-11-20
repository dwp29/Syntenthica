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
import app.breakfast.manager.data.FileRead
import app.breakfast.manager.data.ModuleScan
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.Chip
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors

/**
 * Installed KernelSU modules, from /data/adb/modules.
 *
 * The page used to read /proc/modules instead: *.ko objects, not the modules
 * people install. That file is also unreadable to an app process on this kernel,
 * so the page reported "tidak terbaca" no matter what was installed. The directory
 * it was actually asking about is read now, and the kernel-object list stays
 * below as a separate fact with its own sentence.
 */
@Composable
fun ModulesScreen(
    installed: ModuleScan.Installed?,
    scan: ModuleScan.Result?,
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
        SectionLabel("modul terpasang")
        SurfaceCard {
            when (installed) {
                null -> Text(
                    text = "Sedang membaca ${ModuleScan.INSTALLED_DIR}…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textSecondary,
                )
                else -> {
                    val (headline, detail) = ModuleScan.describeInstalled(installed)
                    val failed = installed !is ModuleScan.Installed.Listed
                    if (failed) {
                        Chip("tidak terbaca", c.statusAttention, filled = true)
                        Spacer(Modifier.height(10.dp))
                    }
                    Text(
                        text = headline,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (failed) c.statusAttention else c.textPrimary,
                    )
                    if (detail != null) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = detail,
                            fontSize = 11.sp,
                            lineHeight = 16.sp,
                            color = c.textTertiary,
                        )
                    }
                    if (installed is ModuleScan.Installed.Listed && installed.modules.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        for (module in installed.modules) {
                            val state = when {
                                module.removePending -> "akan dihapus"
                                module.updatePending -> "menunggu update"
                                !module.enabled -> "dinonaktifkan"
                                else -> "aktif"
                            }
                            DataRow(
                                label = module.id,
                                value = module.version ?: state,
                                valueColor = if (module.enabled) c.textPrimary else c.textTertiary,
                                mono = true,
                                note = listOfNotNull(
                                    module.description,
                                    if (module.enabled) null else state,
                                ).joinToString(" · ").ifEmpty { null },
                            )
                        }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            AccentButton("PERIKSA ULANG", onRefresh, modifier = Modifier.fillMaxWidth())
        }

        Spacer(Modifier.height(16.dp))
        SectionLabel("modul kernel termuat")
        SurfaceCard {
            when (scan) {
                null -> Text(
                    text = "Sedang membaca /proc/modules…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = c.textSecondary,
                )
                else -> {
                    val (headline, detail) = ModuleScan.describe(scan)
                    val readFailed = scan !is ModuleScan.Result.Loaded
                    if (readFailed) {
                        Chip("tidak terbaca", c.statusAttention, filled = true)
                        Spacer(Modifier.height(10.dp))
                    }
                    Text(
                        text = headline,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (readFailed) c.statusAttention else c.textPrimary,
                    )
                    if (detail != null) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = detail,
                            fontSize = 11.sp,
                            lineHeight = 16.sp,
                            color = c.textTertiary,
                        )
                    }
                    if (scan is ModuleScan.Result.Loaded && scan.modules.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        for (module in scan.modules) {
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
            }
        }

        Spacer(Modifier.height(14.dp))
        SectionLabel("berkas yang dibaca")
        SurfaceCard {
            // The paths and their exact state, so every claim above can be audited.
            DataRow(
                label = ModuleScan.INSTALLED_DIR,
                value = when (installed) {
                    null -> "belum dibaca"
                    is ModuleScan.Installed.Listed -> "terbaca"
                    is ModuleScan.Installed.Unreadable -> when (val r = installed.read) {
                        FileRead.Denied -> "izin ditolak"
                        FileRead.Missing -> "tidak ada"
                        FileRead.NotAFile -> "bukan direktori"
                        is FileRead.Failed -> "gagal (${r.reason})"
                        is FileRead.Ok -> "terbaca"
                    }
                    ModuleScan.Installed.NoDirectory -> "tidak ada"
                },
                valueColor = c.textSecondary,
                mono = true,
            )
            DataRow(
                label = "/proc/modules",
                value = when (scan) {
                    null -> "belum dibaca"
                    is ModuleScan.Result.Loaded -> "terbaca"
                    is ModuleScan.Result.Unreadable -> when (val read = scan.read) {
                        FileRead.Denied -> "izin ditolak"
                        FileRead.Missing -> "tidak ada"
                        FileRead.NotAFile -> "bukan berkas"
                        is FileRead.Failed -> "gagal (${read.reason})"
                        is FileRead.Ok -> "terbaca"
                    }
                    ModuleScan.Result.NoProcModules -> "tidak ada"
                },
                valueColor = c.textSecondary,
                mono = true,
            )
            Text(
                text = "Membaca /proc/modules tidak membutuhkan root. Kalau hasilnya " +
                    "\"izin ditolak\", itu kebijakan kernel atau SELinux untuk proses ini. " +
                    "Isi /data/adb/modules biasanya hanya terbaca dengan root, jadi baris " +
                    "itu yang menentukan apakah daftar modul benar-benar bisa dipercaya.",
                fontSize = 11.sp,
                lineHeight = 15.sp,
                color = c.textTertiary,
            )
        }

        Spacer(Modifier.height(14.dp))
        Text(
            text = "Mengaktifkan atau menonaktifkan modul belum ada di build ini: itu butuh " +
                "modprobe dengan root dan jalur pemulihan, dan mengubah modul bisa membuat " +
                "perangkat tidak bisa boot.",
            fontSize = 11.sp,
            lineHeight = 16.sp,
            color = c.textTertiary,
        )
    }
}
