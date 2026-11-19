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

    private const val MAX_VALUE_CHARS = 80

    fun run(
        fs: Fs,
        runningRelease: String,
        nowMs: Long,
        specs: List<Pair<String, List<String>>> = DeviceAudit.NODE_SPECS,
        readOnlyPaths: Set<String> = DeviceAudit.READ_ONLY_PATHS,
    ): DeviceAudit.Report {
        val nodes = mutableListOf<DeviceAudit.Node>()
        for ((group, paths) in specs) {
            for (path in paths) {
                nodes += inspect(group, path, fs, readOnlyPaths)
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
    ): DeviceAudit.Node {
        if (!fs.exists(path)) {
            return DeviceAudit.Node(
                group = group,
                path = path,
                support = DeviceAudit.Support.ABSENT,
                nodePermissions = null,
                readable = false,
                value = null,
            )
        }

        val permissions = fs.permissions(path)
        val readable = fs.readable(path)
        val raw = if (readable) fs.read(path) else null

        // A node that exists but cannot be read is recorded as absent *for
        // reading*, with the reason. Reporting it as supported would make TUNING
        // offer a control whose current value we cannot show.
        val support = when {
            raw == null -> DeviceAudit.Support.ABSENT
            readOnlyPaths.contains(path) -> DeviceAudit.Support.READ_ONLY
            !fs.writable(path) -> DeviceAudit.Support.READ_ONLY
            else -> DeviceAudit.Support.SUPPORTED
        }

        val note = when {
            raw == null && !readable && permissions != null -> "tidak bisa dibaca ($permissions)"
            raw == null -> "tidak bisa dibaca"
            readOnlyPaths.contains(path) -> "hanya dibaca, tidak pernah ditulis"
            support == DeviceAudit.Support.READ_ONLY -> "kernel menyediakan tapi menolak penulisan"
            else -> null
        }

        return DeviceAudit.Node(
            group = group,
            path = path,
            support = support,
            nodePermissions = permissions,
            readable = raw != null,
            value = raw?.trim()?.take(MAX_VALUE_CHARS),
            note = note,
        )
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
