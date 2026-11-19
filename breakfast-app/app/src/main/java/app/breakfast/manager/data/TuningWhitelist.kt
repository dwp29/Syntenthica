package app.breakfast.manager.data

/**
 * The only sysfs nodes this app will ever write.
 *
 * This is an allow-list, not a deny-list: a parameter that is not here cannot
 * be written, full stop. Everything else - thermal trip points, raw
 * scaling_max_freq, scaling_governor, vm.swappiness, kernel.sched_*, anything
 * under /proc/sys/kernel - is excluded because it either risks hardware, can
 * disable schedutil and invalidate every other tuning, or conflicts with what
 * the Android framework already manages.
 */
object TuningWhitelist {

    enum class WriteMode {
        /** Writable at any time. */
        LIVE,

        /** Only effective before zram is initialised; the app must say so. */
        NEEDS_REBOOT,
    }

    /** Operator used to decide whether a value is inside its allowed range. */
    enum class Kind {
        /** Continuous or integer within [min, max]. */
        NUMBER,
        /** One of [options], read from the kernel node at runtime when possible. */
        CHOICE,
    }

    data class Parameter(
        val key: String,
        val path: String,
        val kind: Kind,
        val mode: WriteMode,
        val min: Long = 0,
        val max: Long = 0,
        val options: List<String> = emptyList(),
        val optionsNode: String? = null,
    )

    private const val ZRAM = "/sys/block/zram0"

    val PARAMETERS: List<Parameter> = listOf(
        Parameter(
            key = "zram_comp_algorithm",
            path = "$ZRAM/comp_algorithm",
            kind = Kind.CHOICE,
            mode = WriteMode.LIVE,
            options = listOf("lz4", "lz4kd", "zstd"),
            // Read the offered list from the node itself; never trust a
            // hardcoded list when the kernel can tell us the truth.
            optionsNode = "$ZRAM/comp_algorithm",
        ),
        Parameter(
            key = "zram_disksize",
            path = "$ZRAM/disksize",
            kind = Kind.NUMBER,
            mode = WriteMode.NEEDS_REBOOT,
            min = 1,
            max = 8L * 1024 * 1024 * 1024,
        ),
        Parameter(
            key = "zram_mem_limit",
            path = "$ZRAM/mem_limit",
            kind = Kind.NUMBER,
            mode = WriteMode.LIVE,
            min = 0,
            max = 8L * 1024 * 1024 * 1024,
        ),
        Parameter(
            key = "schedutil_up_rate",
            path = "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
            kind = Kind.NUMBER,
            mode = WriteMode.LIVE,
            min = 0,
            max = 50_000,
        ),
        Parameter(
            key = "schedutil_down_rate",
            path = "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/down_rate_limit_us",
            kind = Kind.NUMBER,
            mode = WriteMode.LIVE,
            min = 0,
            max = 50_000,
        ),
        Parameter(
            key = "schedutil_iowait",
            path = "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/iowait_boost_enable",
            kind = Kind.NUMBER,
            mode = WriteMode.LIVE,
            min = 0,
            max = 1,
        ),
    )

    fun byKey(key: String): Parameter? = PARAMETERS.firstOrNull { it.key == key }

    sealed interface Validation {
        data object Ok : Validation
        data class Rejected(val reason: Reason) : Validation
    }

    enum class Reason { NOT_WHITELISTED, NOT_A_CHOICE, OUT_OF_RANGE, NOT_A_NUMBER, EMPTY }

    /**
     * Validates before anything reaches the filesystem. The app refuses first;
     * the kernel is the second line of defence, not the first.
     */
    fun validate(key: String, rawValue: String, offered: List<String>? = null): Validation {
        val parameter = byKey(key) ?: return Validation.Rejected(Reason.NOT_WHITELISTED)
        val value = rawValue.trim()
        if (value.isEmpty()) return Validation.Rejected(Reason.EMPTY)

        return when (parameter.kind) {
            Kind.CHOICE -> {
                val allowed = offered?.takeIf { it.isNotEmpty() } ?: parameter.options
                if (value in allowed) Validation.Ok else Validation.Rejected(Reason.NOT_A_CHOICE)
            }
            Kind.NUMBER -> {
                val number = value.toLongOrNull() ?: return Validation.Rejected(Reason.NOT_A_NUMBER)
                if (number in parameter.min..parameter.max) Validation.Ok
                else Validation.Rejected(Reason.OUT_OF_RANGE)
            }
        }
    }

    /**
     * Some nodes (notably comp_algorithm) print the active choice in brackets,
     * e.g. "lz4 [lz4kd] zstd". Parse it rather than guessing.
     */
    fun parseOffered(raw: String): List<String> =
        raw.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }.map { it.removeSurrounding("[", "]") }

    fun parseActive(raw: String): String? =
        Regex("\\[([^]]+)]").find(raw)?.groupValues?.get(1)
}
