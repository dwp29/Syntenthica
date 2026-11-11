package net.pure.manager.fs

import java.io.File

/**
 * How much space each folder in one directory is using.
 *
 * "Storage is full" is the question a file manager exists to answer, and the old
 * app could not answer it: every row showed the size of the folder itself, which
 * is 4 KB on Linux regardless of contents. This walks each child once and returns
 * the totals, largest first.
 *
 * Deliberately not recursive into a tree the UI draws: one level is what the user
 * needs to find the folder to open. Open it and the analysis runs again on what is
 * inside. That keeps a scan of a huge folder to one pass instead of a tree.
 */
object Usage {

    /** One child and how many bytes are underneath it. */
    data class Tally(val path: String, val name: String, val isDirectory: Boolean, val bytes: Long)

    /**
     * Measures [dir]'s children, largest first, capped at [limit] results.
     *
     * The cap matters: a folder with 20,000 files would otherwise build a list
     * nobody reads, and the UI only has room for the biggest offenders.
     */
    fun scan(dir: String, showHidden: Boolean, limit: Int = 40): Result<List<Tally>> = runCatching {
        val root = File(dir)
        if (!root.isDirectory) return@runCatching emptyList()
        val children = root.listFiles() ?: return@runCatching emptyList()
        children.asSequence()
            .filter { showHidden || !it.name.startsWith(".") }
            .map { child ->
                Tally(
                    path = child.absolutePath,
                    name = child.name,
                    isDirectory = child.isDirectory,
                    bytes = sizeOf(child),
                )
            }
            .sortedByDescending { it.bytes }
            .take(limit)
            .toList()
    }

    /** Bytes underneath one file or folder. Symlinks are not followed. */
    fun sizeOf(f: File): Long {
        if (f.isFile) return f.length()
        if (!f.isDirectory) return 0L
        // walkTopDown does not follow symlinks, which is what stops a link loop from
        // making this run forever.
        return f.walkTopDown()
            .filter { it.isFile }
            .sumOf { it.length() }
    }

    /**
     * The share of the parent each row represents, as 0f..1f.
     *
     * Returned separately from the bytes so the bar is drawn from a value the UI
     * cannot divide by zero: an empty folder is 0, not NaN.
     */
    fun shares(tallies: List<Tally>): List<Float> {
        val total = tallies.sumOf { it.bytes }
        if (total <= 0L) return tallies.map { 0f }
        return tallies.map { (it.bytes.toDouble() / total).toFloat() }
    }
}
