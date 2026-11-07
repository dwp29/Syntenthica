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
