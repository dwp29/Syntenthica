package app.breakfast.manager.data

/**
 * Device audit: what this kernel actually exposes, recorded read-only.
 *
 * The audit never writes. It exists so that every slider and every message in
 * TUNING can say "yes, this node exists on your device" instead of assuming
 * that a kernel tree implies a running sysfs layout.
 *
 * Two rules shape the data model:
 *
 *  - Absence is a result. `ABSENT` is recorded with the same weight as
 *    `SUPPORTED`, because "this kernel does not have schedutil attributes" is
 *    just as useful as having them.
 *  - A report is stamped with `uname -r`. After a flash the old report is
 *    discarded entirely rather than partially updated, since mixing two kernels
 *    would produce an audit that describes neither.
 */
object DeviceAudit {

    /**
     * Four states, because three could not tell the truth.
     *
     * UNREADABLE was previously folded into ABSENT, which made LAB say "tidak
     * ada" for a node that exists and TUNING say "tidak bisa dibaca" for the
     * same node on the same screen. Existing-but-unreadable is its own fact:
     * the kernel has the node, this app was not allowed to look inside it.
     */
    enum class Support(val label: String) {
        SUPPORTED("didukung"),
        READ_ONLY("baca-saja"),
        UNREADABLE("tidak bisa dibaca"),
        /** Verified missing: the parent directory could be listed and it was not there. */
        ABSENT("tidak ada"),
        /**
         * Cannot tell whether it exists.
         *
         * The previous build reported ten nodes as "tidak ada" on a device whose
         * own kernel source contains them, because `File.exists()` returns false
         * when the app may not traverse the directory. Claiming absence from a
         * lack of permission is the same sin as claiming a temperature of zero:
         * it states a fact the app never established.
         */
        UNKNOWN("tidak bisa dipastikan"),
    }

    data class Node(
        val group: String,
        val path: String,
        val support: Support,
        val nodePermissions: String?,
        val readable: Boolean,
        val value: String?,
        val note: String? = null,
    ) {
        val name: String get() = path.substringAfterLast('/')
    }

    data class Report(
        val kernelRelease: String,
        val timestampMs: Long,
        val nodes: List<Node>,
    ) {
        val supported: Int get() = nodes.count { it.support == Support.SUPPORTED }
        val readOnly: Int get() = nodes.count { it.support == Support.READ_ONLY }
        val unreadable: Int get() = nodes.count { it.support == Support.UNREADABLE }
        val absent: Int get() = nodes.count { it.support == Support.ABSENT }
        val unknown: Int get() = nodes.count { it.support == Support.UNKNOWN }

        /** True when every node's fate was established either way. */
        val isComplete: Boolean get() = unknown == 0

        /**
         * The counts line shown in LAB.
         *
         * Generated from the same fields the legend names, so the row and its
         * explanation can never disagree again. On the device this line read
         * "0 / 6 / 3 / 1" - four numbers, three labels, and a tenth node that
         * belonged to no bucket at all.
         */
        fun countsLine(): String = listOf(supported, readOnly, unreadable, unknown, absent)
            .joinToString(" / ")

        /** Legend for [countsLine], in the same order. */
        fun countsLegend(): String =
            "didukung / baca-saja / tidak bisa dibaca / tidak bisa dipastikan / tidak ada"

        /** Total nodes represented by [countsLine]; must equal nodes.size. */
        fun counted(): Int = supported + readOnly + unreadable + unknown + absent

        fun summary(): String = buildString {
            append("Audit selesai: $supported didukung, $readOnly baca-saja")
            // Only mention the unreadable bucket when it is non-empty, so a
            // normal rooted audit stays short.
            if (unreadable > 0) append(", $unreadable tidak bisa dibaca")
            if (unknown > 0) append(", $unknown tidak bisa dipastikan")
            append(", $absent tidak ada.")
        }

        /** Values that can back a TUNING control, keyed by whitelist key. */
        fun supportedValues(): Map<String, String> = nodes
            .filter { it.support == Support.SUPPORTED && it.readable && it.value != null }
            .associate { nodeToKey(it.path) to it.value!! }

        fun isPresent(path: String): Boolean =
            nodes.any { it.path == path && it.support != Support.ABSENT && it.support != Support.UNKNOWN }

        /** Nodes the kernel has but will not let us read; usually a root problem. */
        fun unreadableNodes(): List<Node> = nodes.filter { it.support == Support.UNREADABLE }
    }

    /** Manual audits are rate-limited; automatic ones are not. */
    const val COOLDOWN_MS = 30_000L

    fun cooldownRemainingMs(lastAuditMs: Long?, nowMs: Long): Long {
        if (lastAuditMs == null) return 0
        val elapsed = nowMs - lastAuditMs
        if (elapsed < 0) return COOLDOWN_MS
        return (COOLDOWN_MS - elapsed).coerceAtLeast(0)
    }

    sealed interface Resolution {
        /** A report produced against the running kernel. */
        data class Fresh(val report: Report) : Resolution

        /** The new audit failed; the previous report for the same kernel still stands. */
        data class KeptStale(val report: Report, val ageMs: Long, val failure: String) : Resolution

        /** Nothing usable: either no audit has run, or the kernel changed and the new one failed. */
        data class None(val reason: String) : Resolution
    }

    /**
     * Decides which report the UI may show after an attempt.
     *
     * - same kernel, new report ok      -> Fresh
     * - same kernel, new report failed  -> KeptStale (old result, flagged)
     * - kernel changed, new report ok   -> Fresh (old one discarded, not merged)
     * - kernel changed, new report failed -> None (old report describes another kernel)
     */
    fun resolve(
        previous: Report?,
        newReport: Report?,
        runningRelease: String,
        nowMs: Long,
        failure: String = "tidak diketahui",
    ): Resolution {
        if (previous != null && previous.kernelRelease != runningRelease) {
            return if (newReport != null) {
                Resolution.Fresh(newReport)
            } else {
                Resolution.None("hasil lama dibuang: uname -r berubah, audit baru gagal")
            }
        }
        if (newReport != null) return Resolution.Fresh(newReport)
        return if (previous != null) {
            Resolution.KeptStale(previous, (nowMs - previous.timestampMs).coerceAtLeast(0), failure)
        } else {
            Resolution.None(failure)
        }
    }

    /** Maps an audited sysfs path onto the TUNING whitelist key it backs, if any. */
    fun nodeToKey(path: String): String = when {
        path.endsWith("/zram0/comp_algorithm") -> "zram_comp_algorithm"
        path.endsWith("/zram0/disksize") -> "zram_disksize"
        path.endsWith("/zram0/mem_limit") -> "zram_mem_limit"
        path.endsWith("up_rate_limit_us") -> "schedutil_up_rate"
        path.endsWith("down_rate_limit_us") -> "schedutil_down_rate"
        path.endsWith("iowait_boost_enable") -> "schedutil_iowait"
        else -> path
    }

    /** Human-readable age for the "hasil lama, %s lalu" label. */
    fun ageLabel(ageMs: Long): String {
        val seconds = ageMs / 1000
        return when {
            seconds < 60 -> "${seconds} detik"
            seconds < 3600 -> "${seconds / 60} menit"
            seconds < 86_400 -> "${seconds / 3600} jam"
            else -> "${seconds / 86_400} hari"
        }
    }

    /**
     * Nodes the audit asks about. The list is fixed and lives here rather than in
     * the runner, so a path can never come from user input or from a file.
     */
    val NODE_SPECS: List<Pair<String, List<String>>> = listOf(
        "CPU freq" to listOf(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq",
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors",
        ),
        "Governor attr" to listOf(
            "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
            "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/down_rate_limit_us",
            "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/iowait_boost_enable",
        ),
        "ZRAM" to listOf(
            "/sys/block/zram0/comp_algorithm",
            "/sys/block/zram0/disksize",
            "/sys/block/zram0/mem_limit",
        ),
        "MGLRU" to listOf(
            "/sys/kernel/mm/lru_gen/enabled",
            "/sys/kernel/mm/lru_gen/min_ttl_ms",
        ),
        "Thermal" to listOf(
            "/sys/class/thermal/thermal_zone0/type",
            "/sys/class/thermal/thermal_zone0/trip_point_0_temp",
        ),
        "GPU" to listOf(
            "/sys/class/kgsl/kgsl-3d0/gpuclk",
            "/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq",
        ),
        "SuSFS" to listOf(
            "/sys/kernel/susfs/version",
        ),
        "KernelSU" to listOf(
            "/sys/kernel/ksu/version",
        ),
    )

    /** Nodes the audit only reads, even when they are writable. */
    val READ_ONLY_PATHS: Set<String> = setOf(
        "/sys/class/thermal/thermal_zone0/type",
        "/sys/class/thermal/thermal_zone0/trip_point_0_temp",
    )

    fun totalNodeCount(): Int = NODE_SPECS.sumOf { it.second.size }
}
