package app.breakfast.manager.data

import java.io.File

/**
 * Performs the audit described by DeviceAudit.NODE_SPECS.
 *
 * Read-only by construction: the only operations available to it are exists,
 * canRead, readable and the permission string. There is no write path here, so
 * "the audit does not modify anything" is a property of the type, not a promise
 * in a comment.
 */
object AuditRunner {

    /** Minimal seam so the runner can be exercised without a device. */
    interface Fs {
        fun exists(path: String): Boolean
        fun readable(path: String): Boolean
        fun writable(path: String): Boolean
        fun read(path: String): String?
        fun permissions(path: String): String?
    }

    /**
     * What the kernel actually showed us for one node.
     *
     * `value` is what was read, `readable` is whether the read worked, and
     * `writable` is the kernel's own answer to canWrite. Keeping these three
     * separate is what lets a node be "exists and reads fine" while also being
     * honest that a non-root manager cannot write to it.
     */
    data class Observation(
        val value: String?,
        val readable: Boolean,
        val writable: Boolean,
        val permissions: String?,
    )

    private const val MAX_VALUE_CHARS = 80

    fun run(
        fs: Fs,
        runningRelease: String,
        nowMs: Long,
        specs: List<Pair<String, List<String>>> = DeviceAudit.NODE_SPECS,
        readOnlyPaths: Set<String> = DeviceAudit.READ_ONLY_PATHS,
        hasRoot: Boolean = false,
    ): DeviceAudit.Report {
        val nodes = mutableListOf<DeviceAudit.Node>()
        for ((group, paths) in specs) {
            for (path in paths) {
                nodes += inspect(group, path, fs, readOnlyPaths, hasRoot)
            }
        }
        return DeviceAudit.Report(
            kernelRelease = runningRelease,
            timestampMs = nowMs,
            nodes = nodes,
        )
    }

    private fun inspect(
        group: String,
        path: String,
        fs: Fs,
        readOnlyPaths: Set<String>,
        hasRoot: Boolean,
    ): DeviceAudit.Node {
        val observation = observe(fs, path, readOnlyPaths)
        return DeviceAudit.Node(
            group = group,
            path = path,
            support = classify(observation, readOnlyPaths.contains(path)),
            nodePermissions = observation.permissions,
            readable = observation.readable,
            value = observation.value?.trim()?.take(MAX_VALUE_CHARS),
            note = noteFor(observation, readOnlyPaths.contains(path), hasRoot),
        )
    }

    fun observe(fs: Fs, path: String, readOnlyPaths: Set<String> = emptySet()): Observation {
        if (!fs.exists(path)) {
            return Observation(null, readable = false, writable = false, permissions = null)
        }
        val permissions = fs.permissions(path)
        val readable = fs.readable(path)
        val value = if (readable) fs.read(path) else null
        // canWrite is asked even when the node is absent, because "exists but
        // not writable" and "does not exist" are different facts.
        val writable = if (value != null) fs.writable(path) else false
        return Observation(value, readable && value != null, writable, permissions)
    }

    /**
     * Turns one observation into a support level.
     *
     * A node that can be read but not written is READ_ONLY, not ABSENT. The
     * distinction is the whole point of the audit: on a stock, non-root install
     * every readable node is unwritable, and reporting that as "0 supported"
     * hides the nodes that are physically present.
     */
    fun classify(observation: Observation, declaredReadOnly: Boolean): DeviceAudit.Support = when {
        !observation.readable || observation.value == null -> DeviceAudit.Support.ABSENT
        declaredReadOnly -> DeviceAudit.Support.READ_ONLY
        !observation.writable -> DeviceAudit.Support.READ_ONLY
        else -> DeviceAudit.Support.SUPPORTED
    }

    /**
     * Explains the classification in the user's terms. A read-only node found on
     * a manager without root says so; telling the user "kernel refused writes"
     * when the truth is "this app was not granted root" would send them looking
     * for a kernel problem that does not exist.
     */
    fun noteFor(
        observation: Observation,
        declaredReadOnly: Boolean,
        hasRoot: Boolean = false,
    ): String? {
        if (!observation.readable || observation.value == null) {
            return when {
                observation.permissions == null -> "tidak bisa dibaca"
                else -> "tidak bisa dibaca (${observation.permissions})"
            }
        }
        if (declaredReadOnly) return "hanya dibaca, tidak pernah ditulis"
        if (!observation.writable) {
            return if (hasRoot) {
                "kernel menyediakan tapi menolak penulisan"
            } else {
                "perlu root untuk menulis"
            }
        }
        return null
    }

    /** Summary that separates "not there" from "there but not writable by us". */
    fun describe(report: DeviceAudit.Report, hasRoot: Boolean): String {
        val suffix = if (hasRoot) "" else " (tanpa root: node hanya bisa dibaca)"
        return report.summary() + suffix
    }

    /** Real filesystem access. `permissions` uses `stat`, the same tool a user would. */
    object SystemFs : Fs {
        override fun exists(path: String) = File(path).exists()
        override fun readable(path: String) = File(path).canRead()
        override fun writable(path: String) = File(path).canWrite()
        override fun read(path: String): String? = try {
            File(path).readText()
        } catch (e: Exception) {
            null
        }

        override fun permissions(path: String): String? = try {
            val process = ProcessBuilder("stat", "-c", "%A %U:%G", path).start()
            val text = process.inputStream.bufferedReader().use { it.readText() }.trim()
            if (process.waitFor() == 0) text.takeIf { it.isNotEmpty() } else null
        } catch (e: Exception) {
            null
        }
    }
}
