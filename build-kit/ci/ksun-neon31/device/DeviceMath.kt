package com.rifsxd.ksunext.ui.device

/** Small, Android-independent validation helpers. Unknown data stays unknown. */
internal fun checkedPercent(level: Int?, scale: Int?): Int? {
    if (level == null || scale == null || scale <= 0 || level < 0 || level > scale) return null
    return ((level.toLong() * 100L + scale / 2L) / scale).toInt()
}

internal fun parseCpuFrequencyKHz(value: String?): Long? {
    val frequency = value?.trim()?.toLongOrNull() ?: return null
    return frequency.takeIf { it in 1L..10_000_000L }
}

internal fun checkedUsedBytes(total: Long, available: Long): Long? =
    if (total > 0 && available in 0..total) total - available else null

internal fun validBatteryTemperatureTenths(value: Int?): Double? =
    value?.takeIf { it in -400..1500 }?.div(10.0)

/** Kernel sysfs devfreq and KGSL clock values are reported in hertz. */
internal fun parseGpuFrequencyHz(value: String?): Long? =
    value?.trim()?.toLongOrNull()?.takeIf { it in 1L..10_000_000_000L }

/** /proc/loadavg is a runnable-load average, never a CPU percentage. */
internal fun parseLoadAverages(value: String?): List<Double>? {
    val fields = value?.trim()?.split(Regex("\\s+")) ?: return null
    if (fields.size < 3) return null
    val values = fields.take(3).map { it.toDoubleOrNull() }
    if (values.any { it == null || !it.isFinite() || it < 0.0 }) return null
    return values.filterNotNull()
}

/** Linux zram mm_stat starts with original and compressed data sizes in bytes. */
internal fun parseZramData(value: String?): Pair<Long, Long>? {
    val fields = value?.trim()?.split(Regex("\\s+")) ?: return null
    if (fields.size < 2) return null
    val original = fields[0].toLongOrNull()?.takeIf { it >= 0 } ?: return null
    val compressed = fields[1].toLongOrNull()?.takeIf { it >= 0 } ?: return null
    return original to compressed
}

/** PSI 'some avg10' is the percentage of time at least one task was stalled. */
internal fun parsePressureAvg10(value: String?): Double? {
    val fields = value?.trim()?.split(Regex("\\s+")) ?: return null
    if (fields.firstOrNull() != "some") return null
    val raw = fields.firstOrNull { it.startsWith("avg10=") }?.substringAfter('=') ?: return null
    val result = raw.toDoubleOrNull() ?: return null
    return result.takeIf { it.isFinite() && it in 0.0..100.0 }
}

internal fun parseNonNegativeBytes(value: String?): Long? =
    value?.trim()?.toLongOrNull()?.takeIf { it >= 0 }

internal fun parseGovernor(value: String?): String? =
    value?.trim()?.takeIf { it.matches(Regex("[A-Za-z0-9_.-]{1,48}")) }
