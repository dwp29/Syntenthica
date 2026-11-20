package app.breakfast.manager.data

import android.os.SystemClock

/**
 * Uptime without asking the kernel for permission.
 *
 * /proc/uptime was returning nothing on the reporting device, which made the
 * UPTIME tile show a dash for a value Android already knows. elapsedRealtime()
 * is monotonic, includes deep sleep, and needs no root - it is exactly "how long
 * has this boot been running".
 *
 * Kept behind an interface so the rest of the code can be tested without
 * Android's clock.
 */
interface ClockSource {
    fun elapsedRealtimeMs(): Long
}

object AndroidClock : ClockSource {
    override fun elapsedRealtimeMs(): Long = SystemClock.elapsedRealtime()
}

object Uptime {
    /** Hours since boot, or null if the clock itself is unusable. */
    fun hours(clock: ClockSource): Double? {
        val ms = try {
            clock.elapsedRealtimeMs()
        } catch (e: Exception) {
            return null
        }
        if (ms <= 0L) return null
        return ms / 3_600_000.0
    }

    fun format(hours: Double?): String {
        if (hours == null) return "—"
        val total = hours.toInt()
        val days = total / 24
        val rest = total % 24
        return if (days > 0) "${days}d ${rest}h" else "${rest}j"
    }
}
