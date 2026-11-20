package app.breakfast.manager.ui

import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.data.TuningWhitelist
import java.io.File

/**
 * Live readings for the PULSE dashboard.
 *
 * Every field is nullable and means "could not be read", never zero. The screen
 * decides how to show a gap (an em dash, or TIDAK ADA when absence is itself a
 * kernel fact, such as MGLRU being compiled out).
 */
data class PulseReadings(
    val temperatureC: Float?,
    val thermalLabel: String,
    val zramPercent: Float?,
    val uptimeHours: Double?,
    val mglruEnabled: Boolean?,
    val mglruRaw: String?,
    val stabilityScore: Int?,
    val cpuLoadHistory: List<Float>,
    val memoryHistory: List<Float>,
    val thermalHistory: List<Float>,
    val cpuUsagePercent: Float?,
    val memoryUsedGb: Float?,
    val memoryTotalGb: Float?,
    val governor: String?,
) {
    companion object {
        /** A device with nothing readable yet. */
        fun empty() = PulseReadings(
            temperatureC = null,
            thermalLabel = "—",
            zramPercent = null,
            uptimeHours = null,
            mglruEnabled = null,
            mglruRaw = null,
            stabilityScore = null,
            cpuLoadHistory = emptyList(),
            memoryHistory = emptyList(),
            thermalHistory = emptyList(),
            cpuUsagePercent = null,
            memoryUsedGb = null,
            memoryTotalGb = null,
            governor = null,
        )
    }
}

/**
 * Reads the dashboard values straight from sysfs and /proc.
 *
 * This object never fabricates: a missing node yields null and the UI shows a
 * dash. It also keeps a 60-sample history in memory so the sparklines have
 * something to draw; the first sample after launch is a single point, which
 * renders as a baseline rather than an invented curve.
 */
object PulseReader {

    private const val HISTORY = 60
    private val cpu = ArrayDeque<Float>()
    private val mem = ArrayDeque<Float>()
    private val thermal = ArrayDeque<Float>()

    private fun read(path: String): String? = try {
        File(path).readText().trim()
    } catch (e: Exception) {
        null
    }

    private fun cpuTemps(): List<Float> =
        (0 until 12).mapNotNull { zone ->
            val type = read("/sys/class/thermal/thermal_zone$zone/type") ?: return@mapNotNull null
            if (!type.contains("cpu", ignoreCase = true) && !type.contains("soc", ignoreCase = true)) {
                return@mapNotNull null
            }
            read("/sys/class/thermal/thermal_zone$zone/temp")?.toFloatOrNull()?.let { it / 1000f }
        }

    private fun memory(): Pair<Float?, Float?> {
        val info = read("/proc/meminfo") ?: return null to null
        fun kb(key: String): Float? = info.lineSequence()
            .firstOrNull { it.startsWith("$key:") }
            ?.split(Regex("\\s+"))
            ?.getOrNull(1)
            ?.toFloatOrNull()
        val totalKb = kb("MemTotal") ?: return null to null
        val availableKb = kb("MemAvailable") ?: kb("MemFree") ?: return null to null
        val totalGb = totalKb / 1024f / 1024f
        val usedGb = (totalKb - availableKb) / 1024f / 1024f
        return usedGb to totalGb
    }

    /** Load average normalised by core count, as a 0..1 fraction. */
    private fun cpuLoad(): Float? {
        val load = read("/proc/loadavg")?.split(' ')?.firstOrNull()?.toFloatOrNull() ?: return null
        val cores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
        return (load / cores).coerceIn(0f, 1f)
    }

    private fun uptimeHours(): Double? =
        read("/proc/uptime")?.split(' ')?.firstOrNull()?.toDoubleOrNull()?.div(3600.0)

    private fun zramPercent(): Float? {
        val disksize = read("/sys/block/zram0/disksize")?.toLongOrNull() ?: return null
        if (disksize <= 0L) return null
        val used = read("/sys/block/zram0/mm_stat")?.split(Regex("\\s+"))
            ?.firstOrNull()?.toLongOrNull() ?: return null
        return ((used.toFloat() / disksize.toFloat()) * 100f).coerceIn(0f, 100f)
    }

    fun sample(stability: StabilityLedger.Score?): PulseReadings {
        val temps = cpuTemps()
        val temp = temps.maxOrNull()
        val (usedGb, totalGb) = memory()
        val load = cpuLoad()
        val uptime = uptimeHours()
        val zram = zramPercent()
        val mglruRaw = read("/sys/kernel/mm/lru_gen/enabled")

        temp?.let { push(thermal, it) }
        load?.let { push(cpu, it * 100f) }
        usedGb?.let { used ->
            val total = totalGb ?: 0f
            if (total > 0f) push(mem, (used / total) * 100f)
        }

        return PulseReadings(
            temperatureC = temp,
            thermalLabel = when {
                temp == null -> "suhu tidak tersedia"
                temp < 45f -> "Normal"
                temp < 60f -> "Hangat"
                else -> "Panas"
            },
            zramPercent = zram,
            uptimeHours = uptime,
            mglruEnabled = mglruRaw?.let { it.trim() != "0" && it.isNotEmpty() },
            mglruRaw = mglruRaw,
            stabilityScore = stability?.takeIf { it.readable }?.value,
            cpuLoadHistory = cpu.toList(),
            memoryHistory = mem.toList(),
            thermalHistory = thermal.toList(),
            cpuUsagePercent = load?.times(100f),
            memoryUsedGb = usedGb,
            memoryTotalGb = totalGb,
            governor = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        )
    }

    private fun push(target: ArrayDeque<Float>, value: Float) {
        if (target.size >= HISTORY) target.removeFirst()
        target.addLast(value)
    }

    /** Resets the history; used when switching to a different kernel. */
    fun reset() {
        cpu.clear()
        mem.clear()
        thermal.clear()
    }

    fun formatUptime(hours: Double?): String {
        if (hours == null) return "—"
        val totalHours = hours.toInt()
        val days = totalHours / 24
        val rest = totalHours % 24
        return if (days > 0) "${days}d ${rest}h" else "${rest}j"
    }

    fun stabilityLabel(score: Int?): String = when {
        score == null -> "—"
        score >= 90 -> "Stabil"
        score >= 70 -> "Normal"
        score >= 40 -> "Perhatian"
        else -> "Bermasalah"
    }

    fun auditValue(report: DeviceAudit.Report, key: String): String? =
        report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == key }?.value

    fun compAlgorithm(report: DeviceAudit.Report): String? =
        auditValue(report, "zram_comp_algorithm")?.let {
            TuningWhitelist.parseActive(it) ?: it.trim()
        }
}
