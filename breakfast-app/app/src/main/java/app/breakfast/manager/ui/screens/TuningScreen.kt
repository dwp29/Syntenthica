package app.breakfast.manager.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.TuningSession
import app.breakfast.manager.data.TuningWhitelist
import app.breakfast.manager.ui.components.AccentButton
import app.breakfast.manager.ui.components.Chip
import app.breakfast.manager.ui.components.ChoiceChip
import app.breakfast.manager.ui.components.DataRow
import app.breakfast.manager.ui.components.GhostButton
import app.breakfast.manager.ui.components.PathRow
import app.breakfast.manager.ui.components.SectionLabel
import app.breakfast.manager.ui.components.SurfaceCard
import app.breakfast.manager.ui.theme.LocalBreakfastColors
import app.breakfast.manager.ui.theme.NumericStyle
import app.breakfast.manager.ui.theme.chipShape

/**
 * TUNING - the screen the design sheet draws with sliders.
 *
 * Only parameters that the audit found AND that the kernel will accept are
 * shown as controls. Everything else is listed with a lock and a reason, which
 * is rule 4 of the design brief: what cannot be changed is marked, not hidden.
 *
 * The sliders here edit *pending* values only. Nothing is written until
 * "TERAPKAN" is pressed and the confirmation is accepted; "KEMBALIKAN" appears
 * only when a previous apply captured originals to restore.
 */
@Composable
fun TuningScreen(
    report: DeviceAudit.Report,
    tuningEnabled: Boolean,
    tuningReason: String,
    hasRoot: Boolean,
    canReset: Boolean,
    modifier: Modifier = Modifier,
    onApply: (List<TuningSession.Proposal>) -> Unit,
    onReset: () -> Unit,
    onAudit: () -> Unit,
) {
    val c = LocalBreakfastColors.current
    // Numeric parameters store their slider value; the compressor choice
    // stores the option name, because a hash would collide and lose which
    // string the kernel actually offered.
    val pending = remember { mutableStateMapOf<String, Float>() }
    val pendingChoice = remember { mutableStateMapOf<String, String>() }

    LazyColumn(
        modifier = modifier.fillMaxWidth().background(c.background),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 116.dp),
    ) {
        item {
            Text(
                text = "TUNING",
                style = MaterialTheme.typography.headlineMedium,
                color = c.textPrimary,
            )
            Text(
                text = "Hanya parameter yang terbukti ada di kernel ini.",
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )
            Spacer(Modifier.height(14.dp))
        }

        if (!tuningEnabled) {
            item {
                SurfaceCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Chip("nonaktif", c.statusAttention, filled = true)
                    }
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = "Kernel ini tidak ada di tabel pairing, jadi tidak ada parameter yang ditampilkan.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textPrimary,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = tuningReason,
                        fontSize = 11.sp,
                        color = c.textTertiary,
                    )
                    Spacer(Modifier.height(14.dp))
                    Text(
                        text = "Aplikasi menolak menebak tata letak sysfs kernel yang tidak dikenalnya. " +
                            "Menampilkan slider untuk node yang belum dipastikan berarti menawarkan " +
                            "tombol yang tidak melakukan apa pun.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                    Spacer(Modifier.height(14.dp))
                    GhostButton("AUDIT ULANG", onAudit, Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(14.dp))
            }
            return@LazyColumn
        }

        // ZRAM group.
        item {
            SectionLabel("zram")
            SurfaceCard {
                ZramControl(
                    report = report,
                    pending = pending,
                    pendingChoice = pendingChoice,
                )
            }
            Spacer(Modifier.height(12.dp))
        }

        // schedutil group.
        item {
            SectionLabel("schedutil")
            SurfaceCard {
                val sched = listOf(
                    "schedutil_up_rate" to "up_rate_limit_us",
                    "schedutil_down_rate" to "down_rate_limit_us",
                    "schedutil_iowait" to "iowait_boost_enable",
                )
                var shown = 0
                for ((key, label) in sched) {
                    val node = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == key }
                    val usable = node != null &&
                        (node.support == DeviceAudit.Support.SUPPORTED ||
                            node.support == DeviceAudit.Support.READ_ONLY)
                    if (usable) {
                        shown++
                        DataRow(
                            label = label,
                            value = node.value ?: "—",
                            valueColor = if (node.support == DeviceAudit.Support.SUPPORTED) {
                                c.textPrimary
                            } else {
                                c.statusAttention
                            },
                            mono = true,
                            note = if (node.support == DeviceAudit.Support.SUPPORTED) null else node.note,
                        )
                    }
                }
                if (shown == 0) {
                    Text(
                        text = "Tidak ada atribut schedutil di kernel ini. Itu fakta kernel, bukan kesalahan.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = c.textSecondary,
                    )
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Status: perlu audit sampai terbukti berperilaku di perangkat.",
                    fontSize = 11.sp,
                    color = c.textTertiary,
                )
            }
            Spacer(Modifier.height(14.dp))
        }

        // Parameters with no row of their own: marked, never hidden, never
        // repeated. The list is derived from what the groups above actually draw.
        item {
            // Derived, not guessed: a hardcoded list hid iowait_boost_enable from
            // both its group and this list, on a kernel that has the node.
            val locked = app.breakfast.manager.data.TuningVisibility.missingKeys(report)
            if (locked.isNotEmpty()) {
                SectionLabel("tidak tersedia")
                SurfaceCard {
                    for (parameter in locked) {
                        val node = report.nodes.firstOrNull {
                            DeviceAudit.nodeToKey(it.path) == parameter.key
                        }
                        PathRow(
                            label = "🔒 ${parameter.key} · ${node?.support?.label ?: "tidak di audit"}",
                            path = parameter.path,
                        )
                    }
                }
                Spacer(Modifier.height(14.dp))
            }
        }

        item {
            val numeric = pending.map { (key, value) -> TuningSession.Proposal(key, value.toInt().toString()) }
            val choices = pendingChoice.map { (key, value) -> TuningSession.Proposal(key, value) }
            val proposals = numeric + choices
            AccentButton(
                text = if (proposals.isEmpty()) "PILIH NILAI DULU" else "TERAPKAN (${proposals.size})",
                enabled = proposals.isNotEmpty() && hasRoot,
                onClick = { onApply(proposals) },
            )
            Spacer(Modifier.height(8.dp))
            if (!hasRoot) {
                Text(
                    text = "Root belum diberikan. Penulisan akan gagal dengan izin ditolak.",
                    fontSize = 11.sp,
                    color = c.statusAttention,
                )
                Spacer(Modifier.height(8.dp))
            }
            if (canReset) {
                GhostButton("KEMBALIKAN KE NILAI AWAL", onReset, Modifier.fillMaxWidth())
            }
            Spacer(Modifier.height(10.dp))
            Text(
                text = "Penulisan dibaca balik. Kalau kernel mengabaikan nilainya, itu dilaporkan gagal, bukan berhasil.",
                fontSize = 11.sp,
                color = c.textTertiary,
            )
        }
    }
}

@Composable
private fun ZramControl(
    report: DeviceAudit.Report,
    pending: MutableMap<String, Float>,
    pendingChoice: MutableMap<String, String>,
) {
    val c = LocalBreakfastColors.current
    val mem = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == "zram_mem_limit" }
    val disk = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == "zram_disksize" }
    val comp = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == "zram_comp_algorithm" }

    if (mem == null && disk == null && comp == null) {
        // "zram belum aktif" is a claim about the kernel, and the audit recorded
        // no verdict for any of these nodes, so the honest statement is that we
        // could not look. Verified absence is reported per node below, not here.
        Text(
            text = "Node zram tidak bisa dipastikan: tidak ada catatan audit untuk node ini, " +
                "jadi belum terbukti ada maupun tidak ada.",
            style = MaterialTheme.typography.bodyMedium,
            color = c.textSecondary,
        )
        return
    }

    val compUsable = comp != null &&
        (comp.support == DeviceAudit.Support.SUPPORTED ||
            comp.support == DeviceAudit.Support.READ_ONLY) &&
        !comp.value.isNullOrBlank()
    if (compUsable) {
        val offered = TuningWhitelist.parseOffered(comp.value ?: "")
        DataRow(
            label = "comp_algorithm",
            value = TuningWhitelist.parseActive(comp.value ?: "") ?: comp.value ?: "—",
            valueColor = c.textPrimary,
            mono = true,
            note = "pilihan kernel: ${offered.joinToString(", ")}",
        )
        // Only options the kernel itself advertises are offered; a compressor the
        // node does not list cannot be selected, so the choice cannot fail later.
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (option in offered) {
                ChoiceChip(
                    label = option,
                    selected = pendingChoice["zram_comp_algorithm"] == option,
                    onClick = { pendingChoice["zram_comp_algorithm"] = option },
                )
            }
        }
        Spacer(Modifier.height(10.dp))
    }

    if (mem != null && mem.support == DeviceAudit.Support.SUPPORTED) {
        val maxMb = (TuningWhitelist.byKey("zram_mem_limit")!!.max / (1024 * 1024)).toFloat()
        SliderRow(
            label = "mem_limit",
            value = pending["zram_mem_limit"] ?: 0f,
            range = 0f..maxMb.coerceAtMost(8192f),
            suffix = " MB",
            onChange = { pending["zram_mem_limit"] = it },
        )
    } else if (mem != null) {
        // Three different facts used to collapse into "node tidak ada di kernel
        // ini" (zram) or "tidak bisa dibaca" (schedutil). On the same device, for
        // nodes the kernel does have. The audit's verdict decides the wording now.
        val (value, why) = when (mem.support) {
            DeviceAudit.Support.UNREADABLE ->
                "—" to "node ada, isinya tidak bisa dibaca tanpa root"
            DeviceAudit.Support.ABSENT ->
                "tidak ada" to "terverifikasi: direktori induk terbaca dan node ini tidak ada di dalamnya"
            DeviceAudit.Support.UNKNOWN ->
                "tidak bisa dipastikan" to "direktori induk tidak bisa dibaca, jadi ada atau tidaknya node ini belum terbukti"
            DeviceAudit.Support.SUPPORTED, DeviceAudit.Support.READ_ONLY ->
                (mem.value ?: "—") to mem.note
        }
        DataRow("mem_limit", value, c.statusAttention, mono = true, note = why)
    }

    if (disk != null && disk.support == DeviceAudit.Support.SUPPORTED) {
        DataRow(
            label = "disksize",
            value = disk.value?.let { "%.0f MB".format(it.toLongOrNull()?.div(1024 * 1024)) } ?: "—",
            valueColor = c.textPrimary,
            mono = true,
            note = "perubahan perlu reboot",
        )
    }
}



@Composable
private fun SliderRow(
    label: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    suffix: String,
    onChange: (Float) -> Unit,
) {
    val c = LocalBreakfastColors.current
    Column {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "${value.toInt()}$suffix",
                style = MaterialTheme.typography.titleMedium.merge(NumericStyle),
                fontWeight = FontWeight.Bold,
                color = c.textPrimary,
            )
        }
        Slider(
            value = value,
            onValueChange = onChange,
            valueRange = range,
            colors = SliderDefaults.colors(
                thumbColor = c.textPrimary,
                activeTrackColor = c.accent,
                inactiveTrackColor = c.hairline,
            ),
        )
    }
}
