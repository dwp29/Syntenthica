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
    /** Whether the readings were taken with root; drives the permission banner. */
    val hasRoot: Boolean = false,
    /** Why CPU load is unavailable, when it is. Never a bare dash. */
    val cpuLoadReason: String? = null,
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

    /**
     * Plausible temperature range, in Celsius.
     *
     * A thermal zone that reports 0 is present but not measuring: some kernels
     * expose zones that are never clamped to a real sensor. Treating that as a
     * reading is how the app once showed "0 C - Normal" in green, which is worse
     * than showing nothing, because it looks like a healthy measurement.
     */
    private const val MIN_PLAUSIBLE_C = 5f
    private const val MAX_PLAUSIBLE_C = 125f

    fun isPlausibleTemperature(celsius: Float?): Boolean =
        celsius != null && celsius > MIN_PLAUSIBLE_C && celsius < MAX_PLAUSIBLE_C

    private fun cpuTemps(): List<Float> =
        (0 until 16).mapNotNull { zone ->
            val type = read("/sys/class/thermal/thermal_zone$zone/type") ?: return@mapNotNull null
            if (!type.contains("cpu", ignoreCase = true) &&
                !type.contains("soc", ignoreCase = true) &&
                !type.contains("gpu", ignoreCase = true)
            ) {
                return@mapNotNull null
            }
            val raw = read("/sys/class/thermal/thermal_zone$zone/temp")?.toFloatOrNull()
                ?: return@mapNotNull null
            // Kernels disagree on the unit: most report millidegrees, a few
            // report whole degrees. A value under 200 cannot be a real
            // millidegree reading above freezing, so it is taken as Celsius.
            val celsius = if (raw > 200f) raw / 1000f else raw
            celsius.takeIf { isPlausibleTemperature(it) }
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

    /**
     * Alternative load source: the idle delta from /proc/stat.
     *
     * Used when /proc/loadavg cannot be read, because "no load average" should
     * not be reported as "no CPU data" when the counters are available.
     */
    private var lastStat: Pair<Long, Long>? = null


    fun cpuUsageFromStat(): Float? {
        val line = read("/proc/stat")?.lineSequence()?.firstOrNull { it.startsWith("cpu ") }
            ?: return null
        val parts = line.trim().split(Regex("\\s+")).drop(1).mapNotNull { it.toLongOrNull() }
        if (parts.size < 4) return null
        val idle = parts[3] + (parts.getOrNull(4) ?: 0L)
        val total = parts.sum()
        val previous = lastStat
        lastStat = total to idle
        if (previous == null) return null
        val totalDelta = total - previous.first
        val idleDelta = idle - previous.second
        // A /proc/stat line has jiffies that can fail to advance between two
        // 2-second samples on a throttled kernel. A delta of a few ticks is not
        // a load measurement, so it is reported as "not measurable" rather than
        // as 0% or 100%.
        return app.breakfast.manager.ui.components.statDeltaForTest(totalDelta, idleDelta)
    }

    /**
     * Uptime from the platform clock first.
     *
     * The kernel file is the fallback, not the source: /proc/uptime was empty on
     * a device where the UPTIME tile should never have shown a dash, and
     * elapsedRealtime needs no permission at all.
     */
    private fun uptimeHours(clock: app.breakfast.manager.data.ClockSource): Double? =
        app.breakfast.manager.data.Uptime.hours(clock)
            ?: read("/proc/uptime")?.split(' ')?.firstOrNull()?.toDoubleOrNull()?.div(3600.0)

    private fun zramPercent(): Float? {
        val disksize = read("/sys/block/zram0/disksize")?.toLongOrNull() ?: return null
        if (disksize <= 0L) return null
        val used = read("/sys/block/zram0/mm_stat")?.split(Regex("\\s+"))
            ?.firstOrNull()?.toLongOrNull() ?: return null
        return ((used.toFloat() / disksize.toFloat()) * 100f).coerceIn(0f, 100f)
    }

    fun sample(
        stability: StabilityLedger.Score?,
        hasRoot: Boolean = false,
        clock: app.breakfast.manager.data.ClockSource = app.breakfast.manager.data.AndroidClock,
    ): PulseReadings {
        val temps = cpuTemps()
        val temp = temps.maxOrNull()
        val (usedGb, totalGb) = memory()
        val loadRaw = cpuLoad()
        val load = loadRaw ?: cpuUsageFromStat()
        val loadReason = when {
            loadRaw != null || load != null -> null
            // Say which of the two sources failed, because the fix differs:
            // an unreadable /proc/loadavg wants root, a missing delta does not.
            else -> if (read("/proc/loadavg") == null) {
                "load average tidak terbaca tanpa root, dan /proc/stat belum memberi delta"
            } else {
                "load average kosong, dan /proc/stat belum memberi delta"
            }
        }
        val uptime = uptimeHours(clock)
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
            hasRoot = hasRoot,
            cpuLoadReason = loadReason,
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

    fun formatUptime(hours: Double?): String =
        app.breakfast.manager.data.Uptime.format(hours)

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
