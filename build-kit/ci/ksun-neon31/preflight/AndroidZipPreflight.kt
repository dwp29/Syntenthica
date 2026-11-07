package com.rifsxd.ksunext.ui.preflight

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File

/** Staging is app-private and is deleted on cancel/completion; nothing executes here. */
internal object AndroidZipPreflight {
    private const val DIRECTORY = "neon31-preflight"
    private const val PREFIX = "pkg31-"
    private const val STALE_MILLIS = 7L * 24L * 60L * 60L * 1000L
    const val MAX_BATCH = 16
    const val MAX_BATCH_BYTES = PackagePreflight.MAX_ARCHIVE_BYTES

    private fun stageDirectory(context: Context): File {
        val directory = File(context.cacheDir, DIRECTORY)
        if (!directory.isDirectory && !directory.mkdirs()) throw PreflightException(PreflightProblem.UNREADABLE)
        return directory
    }

    fun inspect(context: Context, uri: Uri, maxBytes: Long = PackagePreflight.MAX_ARCHIVE_BYTES): PackageReport {
        val root = stageDirectory(context)
        val file = runCatching { File.createTempFile(PREFIX, ".zip", root) }
            .getOrElse { throw PreflightException(PreflightProblem.UNREADABLE) }
        try {
            val name = displayName(context, uri)
            val input = context.contentResolver.openInputStream(uri) ?: throw PreflightException(PreflightProblem.UNREADABLE)
            return PackagePreflight.stageAndInspect(input, file, name, maxBytes)
        } catch (error: PreflightException) {
            file.delete()
            throw error
        } catch (_: Exception) {
            file.delete()
            throw PreflightException(PreflightProblem.UNREADABLE)
        }
    }

    private fun displayName(context: Context, uri: Uri): String = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index >= 0 && cursor.moveToFirst()) cursor.getString(index) else null
        }
    }.getOrNull()?.takeIf { it.isNotBlank() } ?: (uri.lastPathSegment ?: "unknown.zip")

    /** Only an app-private staged URI can reach the existing installer. */
    fun copyVerified(context: Context, uri: Uri, destination: File, expectedSha256: String): Boolean {
        fun fail(): Boolean { destination.delete(); return false }
        val root = runCatching { stageDirectory(context).canonicalFile }.getOrNull() ?: return fail()
        val path = uri.path ?: return fail()
        val source = runCatching { if (uri.scheme == "file") File(path).canonicalFile else null }
            .getOrNull() ?: return fail()
        val destinationCanonical = runCatching { destination.canonicalFile }.getOrNull() ?: return fail()
        if (source == destinationCanonical) return false // Never delete the source itself.
        if (source.parentFile != root || !source.name.startsWith(PREFIX) || !source.name.endsWith(".zip")) return fail()
        val copied = runCatching {
            val input = context.contentResolver.openInputStream(uri) ?: error("staged ZIP unavailable")
            var size = 0L
            input.use {
                destination.outputStream().buffered().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val count = it.read(buffer)
                        if (count < 0) break
                        if (count == 0) continue
                        if (count.toLong() > PackagePreflight.MAX_ARCHIVE_BYTES - size) error("staged ZIP too large")
                        output.write(buffer, 0, count)
                        size += count.toLong()
                    }
                }
            }
            PackagePreflight.matchesSha256(destination, expectedSha256)
        }.getOrDefault(false)
        if (!copied) destination.delete()
        return copied
    }

    fun deleteReports(context: Context, reports: List<PackageReport>) =
        deleteStagedUris(context, reports.map { Uri.fromFile(it.file) })

    fun deleteStagedUris(context: Context, uris: List<Uri>) {
        val root = runCatching { stageDirectory(context).canonicalFile }.getOrNull() ?: return
        uris.filter { it.scheme == "file" }.forEach { uri ->
            runCatching {
                val file = File(uri.path ?: return@runCatching).canonicalFile
                if (file.parentFile == root && file.name.startsWith(PREFIX) && file.name.endsWith(".zip")) file.delete()
            }
        }
    }

    fun pruneStale(context: Context) {
        val now = System.currentTimeMillis()
        val cutoff = now - STALE_MILLIS
        runCatching {
            stageDirectory(context).listFiles()?.forEach { file ->
                if (file.name.startsWith(PREFIX) && file.name.endsWith(".zip") && file.isFile &&
                    file.lastModified() in 1L until cutoff) file.delete()
            }
        }
    }
}
