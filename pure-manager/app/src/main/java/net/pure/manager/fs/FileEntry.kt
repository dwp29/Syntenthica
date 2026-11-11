package net.pure.manager.fs

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * One row in the browser.
 *
 * Plain data with no Android types, so the sorting and formatting rules below are
 * exercised by JVM tests in `src/test` on every build. That matters here: this
 * sandbox cannot run the app, so any logic that lives in a composable is logic
 * nobody checks.
 */
data class FileEntry(
    val path: String,
    val name: String,
    val isDirectory: Boolean,
    val sizeBytes: Long,
    val lastModified: Long,
    val isHidden: Boolean,
    val canRead: Boolean,
    val childCount: Int = -1,
) {
    val extension: String
        get() = if (isDirectory) "" else name.substringAfterLast('.', "").lowercase(Locale.US)

    fun toFile(): File = File(path)
}

/** How the list is ordered. */
enum class SortKey { NAME, SIZE, DATE, TYPE }

data class SortOrder(val key: SortKey = SortKey.NAME, val descending: Boolean = false)

/**
 * Comparator for a directory listing.
 *
 * Folders always come first regardless of key, and descending order intentionally
 * does not invert that: iOS, Explorer and every file manager the owner showed
 * keep folders on top. Reversing it would look like a bug.
 */
fun comparatorFor(order: SortOrder): Comparator<FileEntry> {
    val byKey: Comparator<FileEntry> = when (order.key) {
        SortKey.NAME -> compareBy<FileEntry, String>(String.CASE_INSENSITIVE_ORDER) { it.name }
        SortKey.SIZE -> compareBy<FileEntry> { it.sizeBytes }
        SortKey.DATE -> compareBy<FileEntry> { it.lastModified }
        SortKey.TYPE -> compareBy<FileEntry, String>(String.CASE_INSENSITIVE_ORDER) { it.extension }
            .thenBy(String.CASE_INSENSITIVE_ORDER) { it.name }
    }
    val directed = if (order.descending) byKey.reversed() else byKey
    return compareByDescending<FileEntry> { it.isDirectory }.then(directed)
}

/** Human size. Binary units, because a file manager should match the file system. */
fun formatSize(bytes: Long, isDirectory: Boolean): String = when {
    isDirectory -> "Folder"
    bytes < 1024 -> "$bytes B"
    bytes < 1024L * 1024 -> "${bytes / 1024} KB"
    bytes < 1024L * 1024 * 1024 -> String.format(Locale.US, "%.1f MB", bytes / (1024.0 * 1024))
    else -> String.format(Locale.US, "%.2f GB", bytes / (1024.0 * 1024 * 1024))
}

/**
 * Date in the reference screenshots' style: time for today, day and month for
 * this year, full date before that. One date format per row, never a raw epoch.
 */
fun formatDate(epochMillis: Long, now: Long = System.currentTimeMillis()): String {
    if (epochMillis <= 0L) return "\u2014"
    val then = Date(epochMillis)
    val today = SimpleDateFormat("yyyyMMdd", Locale.US).format(Date(now))
    val that = SimpleDateFormat("yyyyMMdd", Locale.US).format(then)
    return when {
        that == today -> SimpleDateFormat("HH:mm", Locale.US).format(then)
        that.substring(0, 4) == today.substring(0, 4) ->
            SimpleDateFormat("d MMM", Locale("in", "ID")).format(then)
        else -> SimpleDateFormat("d MMM yyyy", Locale("in", "ID")).format(then)
    }
}

/**
 * Rejects names that cannot be a file name, and says why.
 *
 * Returns null when the name is fine. The message is shown verbatim, so it is in
 * Indonesian and names the offending character instead of failing silently.
 */
fun validateName(name: String): String? {
    val trimmed = name.trim()
    if (trimmed.isEmpty()) return "Nama tidak boleh kosong"
    if (trimmed == "." || trimmed == "..") return "Nama itu tidak bisa dipakai"
    if (trimmed.length > 255) return "Nama terlalu panjang (maks 255)"
    val forbidden = charArrayOf('/', '\\', ':', '*', '?', '"', '<', '>', '|', '\u0000')
    trimmed.forEach { c ->
        if (c in forbidden) return "Nama tidak boleh mengandung $c"
        if (c.code < 32) return "Nama mengandung karakter kontrol"
    }
    if (trimmed.endsWith(" ")) return "Nama tidak boleh berakhir dengan spasi"
    return null
}

/** Cleans a name so it can be created, used when a duplicate needs a suffix. */
fun uniqueName(base: String, taken: Set<String>, isDirectory: Boolean): String {
    if (base.lowercase(Locale.US) !in taken.map { it.lowercase(Locale.US) }.toSet()) return base
    val stem: String
    val suffix: String
    if (isDirectory) {
        stem = base
        suffix = ""
    } else {
        val dot = base.lastIndexOf('.')
        if (dot > 0) {
            stem = base.substring(0, dot)
            suffix = base.substring(dot)
        } else {
            stem = base
            suffix = ""
        }
    }
    var n = 1
    while (true) {
        val candidate = "$stem ($n)$suffix"
        if (candidate.lowercase(Locale.US) !in taken.map { it.lowercase(Locale.US) }.toSet()) {
            return candidate
        }
        n++
    }
}
