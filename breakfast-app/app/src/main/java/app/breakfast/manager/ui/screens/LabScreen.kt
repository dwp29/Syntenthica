package app.breakfast.manager.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.Chip
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors

/**
 * LAB - diagnostics: the device audit and the stability ledger.
 *
 * The audit is the only place the app inspects sysfs in bulk, and it is
 * read-only. Each node is shown with what the kernel said, including the ones
 * that are not there: an audit that lists only successes is a checklist, not an
 * audit.
 */
@Composable
fun LabScreen(
    report: DeviceAudit.Report,
    hasRoot: Boolean,
    ledger: StabilityLedger.Score?,
    ledgerReason: String?,
    auditing: Boolean,
    modifier: Modifier = Modifier,
    onAudit: () -> Unit,
) {
    val c = LocalBreakfastColors.current

    LazyColumn(
        modifier = modifier.fillMaxWidth().background(c.background),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 116.dp),
    ) {
        item {
            Text("LAB", style = MaterialTheme.typography.headlineMedium, color = c.textPrimary)
            Text(
                text = "Diagnostik. Audit hanya membaca, tidak mengubah apa pun.",
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )
            Spacer(Modifier.height(16.dp))
        }

        item {
            SectionLabel("stability ledger")
            SurfaceCard {
                val score = ledger
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = score?.value?.toString() ?: "—",
                        style = MaterialTheme.typography.displayLarge,
                        color = when {
                            score == null -> c.textTertiary
                            score.value >= 90 -> c.statusStable
                            score.value >= 70 -> c.statusNormal
                            score.value >= 40 -> c.statusAttention
                            else -> c.statusTrouble
                        },
                    )
                    Spacer(Modifier.height(0.dp))
                    Column(Modifier.padding(start = 14.dp)) {
                        Chip(
                            text = score?.let { it.band.name.lowercase() } ?: "tidak terbaca",
                            color = if (score == null) c.statusAttention else c.statusStable,
                            filled = true,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = score?.let { "beban ${it.burden} · %.1f jam".format(it.uptimeHours) }
                                ?: "dmesg tidak terbaca",
                            fontSize = 11.sp,
                            color = c.textTertiary,
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                if (score != null) {
                    DataRow("Oops", "${score.counts[StabilityLedger.Event.OOPS] ?: 0}", c.textPrimary, mono = true, note = "bobot 10")
                    DataRow("BUG", "${score.counts[StabilityLedger.Event.BUG] ?: 0}", c.textPrimary, mono = true, note = "bobot 8")
                    DataRow("WARN", "${score.counts[StabilityLedger.Event.WARN] ?: 0}", c.textPrimary, mono = true, note = "bobot 3")
                } else {
                    Text(
                        text = ledgerReason ?: "Skor tidak dikarang. Angka nol di sini akan menyesatkan.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Skor dihitung sejak boot, bukan sejak aplikasi dibuka, dan direset oleh reboot.",
                    fontSize = 11.sp,
                    color = c.textTertiary,
                )
            }
            Spacer(Modifier.height(14.dp))
        }

        item {
            SectionLabel("audit perangkat")
            SurfaceCard {
                if (report.nodes.isEmpty()) {
                    Text(
                        text = "Belum pernah diaudit.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.statusAttention,
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Audit memeriksa ${DeviceAudit.totalNodeCount()} node: ada atau tidak, izin, dan nilai sekarang.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                } else {
                    DataRow("Kernel", report.kernelRelease, c.textPrimary, mono = true)
                    DataRow(
                        label = "Hasil",
                        value = "${report.supported} / ${report.readOnly} / ${report.unreadable} / ${report.absent}",
                        valueColor = c.textPrimary,
                        mono = true,
                        note = "didukung / baca-saja / tidak bisa dibaca / tidak ada",
                    )
                    DataRow(
                        label = "Root",
                        value = if (hasRoot) "diberikan" else "belum",
                        valueColor = if (hasRoot) c.statusStable else c.statusAttention,
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
        }

        items(count = DeviceAudit.NODE_SPECS.size) { index ->
            val (group, _) = DeviceAudit.NODE_SPECS[index]
            val nodes = report.nodes.filter { it.group == group }
            if (nodes.isNotEmpty()) {
                SectionLabel(group.lowercase())
                SurfaceCard(padding = 12.dp) {
                    for (node in nodes) {
                        DataRow(
                            label = node.name,
                            value = when (node.support) {
                                DeviceAudit.Support.SUPPORTED -> node.value ?: "—"
                                DeviceAudit.Support.READ_ONLY -> node.value ?: "baca-saja"
                                // Exists but will not open: a different problem
                                // from a node that is not there, and until now it
                                // was reported as "tidak ada" in this list while
                                // TUNING called the same node "tidak bisa dibaca".
                                DeviceAudit.Support.UNREADABLE -> "tidak bisa dibaca"
                                DeviceAudit.Support.ABSENT -> "tidak ada"
                            },
                            valueColor = when (node.support) {
                                DeviceAudit.Support.SUPPORTED -> c.statusStable
                                DeviceAudit.Support.READ_ONLY -> c.statusNormal
                                DeviceAudit.Support.UNREADABLE -> c.statusAttention
                                DeviceAudit.Support.ABSENT -> c.textTertiary
                            },
                            mono = true,
                            note = node.note ?: if (node.support == DeviceAudit.Support.ABSENT) {
                                "node tidak ada di kernel ini"
                            } else {
                                null
                            },
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
            }
        }

        item {
            Text(
                text = "Ringkasan: " + AuditRunner.describe(report, hasRoot),
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )
            Spacer(Modifier.height(12.dp))
            AccentButton(
                text = if (auditing) "MEMERIKSA…" else "AUDIT SEKARANG",
                enabled = !auditing,
                onClick = onAudit,
            )
            Spacer(Modifier.height(10.dp))
            Text(
                text = "Jeda audit manual 30 detik. Audit otomatis berjalan saat aplikasi dibuka " +
                    "dan saat uname -r berubah.",
                fontSize = 11.sp,
                color = c.textTertiary,
            )
        }
    }
}
