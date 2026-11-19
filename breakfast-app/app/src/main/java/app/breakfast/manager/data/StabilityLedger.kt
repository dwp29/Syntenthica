package app.breakfast.manager.data

/**
 * Stability Ledger.
 *
 * The score measures *change* since boot, not absolute health. It is derived
 * only from three kinds of kernel log event; everything else is ignored on
 * purpose, because counting recoverable driver noise would make a healthy
 * device look broken forever.
 *
 * Pure data + pure function: no Android APIs here, so it is unit-testable on a
 * plain JVM and cannot accidentally read anything it was not given.
 */
object StabilityLedger {

    const val WEIGHT_OOPS = 10
    const val WEIGHT_BUG = 8
    const val WEIGHT_WARN = 3

    enum class Event(val weight: Int, val label: String) {
        OOPS(WEIGHT_OOPS, "Oops"),
        BUG(WEIGHT_BUG, "BUG"),
        WARN(WEIGHT_WARN, "WARN"),
    }

    /** One counted event, with the driver/tag it was attributed to when known. */
    data class Occurrence(val event: Event, val tag: String?)

    data class Score(
        val value: Int,
        val burden: Int,
        val uptimeHours: Double,
        val counts: Map<Event, Int>,
        val readable: Boolean,
    ) {
        val band: Band get() = Band.of(value)
    }

    enum class Band(val min: Int) {
        STABLE(90), NORMAL(70), ATTENTION(40), TROUBLE(0);

        companion object {
            fun of(score: Int): Band = when {
                score >= STABLE.min -> STABLE
                score >= NORMAL.min -> NORMAL
                score >= ATTENTION.min -> ATTENTION
                else -> TROUBLE
            }
        }
    }

    /**
     * Patterns are matched case-sensitively against kernel log lines.
     *
     * Deliberately absent: "Call trace:", "---[ end trace ]---", plain driver
     * `pr_err` output, and recoverable I2C/probe failures. Those accompany a
     * real event or are normal noise; counting them would double-count or
     * invent problems.
     */
    private val PATTERNS = listOf(
        Event.OOPS to Regex("Internal error: Oops|Unable to handle kernel"),
        Event.BUG to Regex("kernel BUG at|(^|\\s)BUG: "),
        Event.WARN to Regex("WARNING: CPU:|WARNING: at "),
    )

    fun classify(line: String): Event? =
        PATTERNS.firstOrNull { (_, pattern) -> pattern.containsMatchIn(line) }?.first

    /** Extracts a bracket tag such as `[  123.45] i2c-geni ...` when present. */
    fun tagOf(line: String): String? {
        val trimmed = line.trim()
        val withoutStamp = trimmed.replaceFirst(Regex("^\\[[^\\]]*]\\s*"), "")
        val first = withoutStamp.substringBefore(':').trim()
        return first.takeIf { it.isNotEmpty() && it.length <= 40 && !it.contains(' ') }
    }

    fun scan(lines: Sequence<String>): List<Occurrence> =
        lines.mapNotNull { line ->
            classify(line)?.let { Occurrence(it, tagOf(line)) }
        }.toList()

    /** burden = Σ weight × count */
    fun burden(occurrences: List<Occurrence>): Int =
        occurrences.sumOf { it.event.weight }

    /**
     * score = clamp(round(100 − (burden × 10) / max(uptimeHours, 1)), 0, 100)
     *
     * Uptime below one hour is treated as one hour so a device that crashed
     * one minute after boot is not rewarded for having "so little uptime".
     */
    fun score(burden: Int, uptimeHours: Double): Int {
        val hours = if (uptimeHours.isNaN() || uptimeHours < 1.0) 1.0 else uptimeHours
        val raw = 100.0 - (burden * 10.0) / hours
        // round(), not truncate: the spec says round, and truncating would
        // quietly shave a point off every fractional score.
        return Math.round(raw.coerceIn(0.0, 100.0)).toInt()
    }

    /** Unreadable dmesg must never become a fabricated number. */
    fun unreadable(): Score = Score(
        value = -1,
        burden = 0,
        uptimeHours = 0.0,
        counts = emptyMap(),
        readable = false,
    )

    fun compute(occurrences: List<Occurrence>, uptimeHours: Double): Score {
        val counts = occurrences.groupingBy { it.event }.eachCount()
        val total = burden(occurrences)
        return Score(
            value = score(total, uptimeHours),
            burden = total,
            uptimeHours = uptimeHours,
            counts = counts,
            readable = true,
        )
    }

    /** Events grouped per driver tag, biggest contributor first. */
    fun perTag(occurrences: List<Occurrence>): List<Pair<String, Int>> =
        occurrences.groupingBy { it.tag ?: "unknown" }
            .eachCount()
            .map { (tag, count) -> tag to count }
            .sortedWith(compareByDescending<Pair<String, Int>> { it.second }.thenBy { it.first })
}
