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

        /**
         * Names in the parent directory, or null when it cannot be listed.
         *
         * Only a listing can prove absence. exists() == false is not proof: it
         * also happens when a parent directory is not traversable, which is the
         * normal case for a sandboxed app looking at /data/adb.
         */
        fun listing(path: String): List<String>? = null

        /**
         * True when the parent directory itself does not exist.
         *
         * Distinguishes "zram is not loaded, so /sys/block/zram0 is missing" from
         * "we may not read /sys/block/zram0". The first is proof of absence; the
         * second is not, and calling it absence is what produced 'tidak ada' for
         * nodes the kernel has.
         */
        fun parentMissing(path: String): Boolean = false
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
    /** What we managed to establish about a node's existence. */
    enum class Presence {
        /** exists() returned true. */
        PRESENT,
        /** The parent directory was listed and the name was not in it. */
        VERIFIED_ABSENT,
        /** No permission to look; existence is genuinely unknown. */
        UNKNOWN,
    }

    data class Observation(
        val value: String?,
        val readable: Boolean,
        val writable: Boolean,
        val permissions: String?,
        val presence: Presence = Presence.PRESENT,
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
            // exists() is not evidence of absence. Only a directory listing is.
            val listing = fs.listing(path)
            if (listing == null) {
                // No listing AND no parent: the directory leading to this node
                // does not exist at all (zram inactive, MGLRU not compiled in), so
                // the node cannot exist either. That is proof, not ignorance.
                val parentMissing = fs.parentMissing(path)
                if (parentMissing) {
                    return Observation(null, readable = false, writable = false, permissions = null,
                        presence = Presence.VERIFIED_ABSENT)
                }
                // Cannot even look: the only honest answer is "cannot tell".
                return Observation(null, readable = false, writable = false, permissions = null,
                    presence = Presence.UNKNOWN)
            }
            val name = path.substringAfterLast('/')
            if (name !in listing) {
                // Named in the listing but still invisible is a policy block, not
                // absence; a name that is not in the listing is gone.
                return Observation(null, readable = false, writable = false, permissions = null,
                    presence = Presence.VERIFIED_ABSENT)
            }
            // The name IS in the listing but exists() said no: a policy is
            // blocking this process, so the node is there but closed.
            return Observation(null, readable = false, writable = false,
                permissions = fs.permissions(path), presence = Presence.PRESENT)
        }
        val permissions = fs.permissions(path)
        val canRead = fs.readable(path)
        val value = if (canRead) fs.read(path) else null
        // `readable` means "we obtained the contents", not just "canRead said
        // yes": a node holding "0" is readable and its value is "0", while a node
        // that opened but yielded nothing is not readable. The writable probe is
        // only meaningful once the node can actually be seen.
        val gotValue = canRead && value != null
        val writable = if (gotValue) fs.writable(path) else false
        return Observation(value, gotValue, writable, permissions,
            presence = Presence.PRESENT)
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
        // Verified: the directory was listed and the name was not in it.
        observation.presence == Presence.VERIFIED_ABSENT -> DeviceAudit.Support.ABSENT
        // We were not allowed to look. Saying "tidak ada" here is how ten nodes
        // that the kernel does have were reported as missing.
        observation.presence == Presence.UNKNOWN -> DeviceAudit.Support.UNKNOWN
        // The file is there but the read did not produce a value. That is a
        // permission or a policy problem, not an absence, and saying "tidak ada"
        // here is what made LAB contradict TUNING on the same screen.
        !observation.readable || observation.value == null -> DeviceAudit.Support.UNREADABLE
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
            return when (observation.presence) {
                Presence.UNKNOWN ->
                    "tidak bisa dipastikan: direktori induk tidak bisa dibaca, jadi ada atau tidaknya node ini tidak diketahui"
                Presence.VERIFIED_ABSENT -> "tidak ada (direktori induk sudah diperiksa)"
                Presence.PRESENT ->
                    if (observation.permissions != null) {
                        "tidak bisa dibaca (${observation.permissions})"
                    } else {
                        "tidak bisa dibaca tanpa root"
                    }
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
        /**
         * Names in the parent directory, or null when it cannot be listed.
         *
         * This is the only evidence that may turn into "tidak ada". File.exists()
         * returning false proves nothing, because it also happens when the app
         * may not traverse a parent directory.
         */
        override fun listing(path: String): List<String>? = try {
            File(path).parentFile?.list()?.toList()
        } catch (e: Exception) {
            null
        }

        override fun parentMissing(path: String): Boolean = try {
            val parent = File(path).parentFile
            // exists() false while the grandparent lists the parent name would be
            // a policy block; but a parent that is neither visible nor listed in
            // its own parent is genuinely gone.
            parent != null && !parent.exists() &&
                (parent.parentFile?.list()?.contains(parent.name) != true)
        } catch (e: Exception) {
            false
        }

        override fun exists(path: String) = File(path).exists()
        override fun readable(path: String) = File(path).canRead()
        override fun writable(path: String) = File(path).canWrite()
        override fun read(path: String): String? = try {
            File(path).readText()
        } catch (e: Exception) {
            null
        }

        override fun permissions(path: String): String? = try {
            // stat is available on most images but not guaranteed; when it is
            // missing the audit must still record the node's presence, so the
            // readability flags are used as a weaker but honest signal.
            val process = ProcessBuilder("stat", "-c", "%A %U:%G", path).start()
            val text = process.inputStream.bufferedReader().use { it.readText() }.trim()
            if (process.waitFor() == 0) text.takeIf { it.isNotEmpty() } else null
        } catch (e: Exception) {
            null
        }
    }
}
