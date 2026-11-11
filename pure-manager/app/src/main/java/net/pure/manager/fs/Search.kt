package net.pure.manager.fs

import java.io.File

/**
 * Device-wide search.
 *
 * The browser can only filter the folder that is open, which is useless for the
 * question the owner actually asks ("where is that APK"), so this walks the
 * storage volume and matches names and extensions.
 *
 * Four rules keep it from becoming a way to hang the phone:
 *
 *  - **A depth limit.** `Android/data` and `Android/obb` nest forever and are
 *    unreadable anyway on Android 11+; eight levels reaches every file a person
 *    put there and stops before the walk turns into a minute of I/O.
 *  - **A result limit.** Stopping after [MAX_RESULTS] means the sheet renders a
 *    bounded list instead of building a hundred thousand rows to show fifty.
 *  - **A cancellation check**, polled per directory, so closing the sheet stops
 *    the walk instead of leaving a thread reading the SD card.
 *  - **Skipping other apps' private trees.** Reading `Android/data` needs a grant
 *    this app does not have; crawling it produces exceptions and no results.
 *
 * It is a plain function over `java.io.File` on purpose: that is what the JVM tests
 * can drive, and a search that only exists inside a composable is a search nobody
 * has ever run before the owner runs it.
 */
object Search {

    const val MAX_RESULTS: Int = 200
    const val MAX_DEPTH: Int = 8

    /**
     * Directories that never hold user files, or that cannot be read at all.
     *
     * Matched on the full SUFFIX, not the folder's own name: a folder called
     * `data` inside `Documents` is the user's and must be searched, while the one
     * under `Android` is another app's private storage. Matching on the name alone
     * silently hides real files.
     */
    private val skippedSuffixes = setOf(
        "/Android/data",
        "/Android/obb",
        "/Android/media",
    )

    /**
     * Finds files whose name contains [query], case-insensitively.
     *
     * @param roots where to start; usually every storage volume.
     * @param cancelled polled before each directory, so a dismissed sheet stops.
     */
    fun find(
        roots: List<String>,
        query: String,
        showHidden: Boolean = false,
        cancelled: () -> Boolean = { false },
        limit: Int = MAX_RESULTS,
    ): List<FileEntry> {
        val needle = query.trim().lowercase()
        if (needle.isEmpty()) return emptyList()

        val found = mutableListOf<FileEntry>()
        for (root in roots) {
            val base = File(root)
            if (!base.isDirectory) continue
            walk(base, needle, showHidden, cancelled, limit, found)
            if (found.size >= limit || cancelled()) break
        }
        return found
            .sortedWith(compareBy<FileEntry>({ it.name.lowercase() }, { it.path }))
            .take(limit)
    }

    private fun walk(
        dir: File,
        needle: String,
        showHidden: Boolean,
        cancelled: () -> Boolean,
        limit: Int,
        out: MutableList<FileEntry>,
    ) {
        val stack = ArrayDeque<Pair<File, Int>>()
        stack.addLast(dir to 0)
        while (stack.isNotEmpty()) {
            if (cancelled() || out.size >= limit) return
            val (current, depth) = stack.removeLast()
            val children = runCatching { current.listFiles() }.getOrNull() ?: continue
            for (f in children) {
                val name = f.name
                if (!showHidden && name.startsWith(".")) continue
                if (isSkipped(f)) continue
                if (f.isDirectory) {
                    if (depth + 1 < MAX_DEPTH) stack.addLast(f to depth + 1)
                } else if (name.lowercase().contains(needle)) {
                    out += FileEntry(
                        path = f.absolutePath,
                        name = name,
                        isDirectory = false,
                        sizeBytes = f.length(),
                        lastModified = f.lastModified(),
                        isHidden = name.startsWith("."),
                        canRead = f.canRead(),
                    )
                    if (out.size >= limit) return
                }
            }
        }
    }

    /**
     * True for the trees that are either unreadable or a trap.
     *
     * The check is on the absolute path suffix rather than the name alone, because
     * a folder called `data` inside `Documents` is the user's and must be searched.
     */
    internal fun isSkipped(f: File): Boolean {
        if (!f.isDirectory) return false
        return skippedSuffixes.any { f.path.endsWith(it) }
    }
}
