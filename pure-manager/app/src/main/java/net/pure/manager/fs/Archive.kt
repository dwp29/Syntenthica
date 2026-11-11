package net.pure.manager.fs

import java.io.File
import java.io.IOException
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * Reading and extracting ZIP archives.
 *
 * A file manager that lets you copy a zip but not look inside it is a file manager
 * that makes you install another one. This is deliberately only zip: it is the
 * format Android itself produces and the only one in `java.util.zip`, so it adds
 * nothing to the APK. RAR and 7z need a native library and wait for the stage that
 * can afford one; saying so is better than an "open" that fails.
 */
object Archive {

    /** One row in the list. Sizes come from the central directory, so this is cheap. */
    data class Entry(
        val name: String,
        val isDirectory: Boolean,
        val bytes: Long,
    )

    fun isZip(name: String): Boolean = name.substringAfterLast('.', "").lowercase() == "zip"

    /**
     * Lists an archive without extracting anything.
     *
     * Rejects entries that climb out of the archive. A zip containing
     * `../../../../data/...` is a document that writes wherever it likes, and
     * "extract here" must not be the moment that happens.
     */
    fun list(archivePath: String): Result<List<Entry>> = runCatching {
        val file = File(archivePath)
        if (!file.isFile) throw IOException("Berkas arsip tidak ditemukan")
        ZipFile(file).use { zip ->
            zip.entries().asSequence()
                .filterNot { it.isUnsafe() }
                .map { e -> Entry(e.name, e.isDirectory, if (e.isDirectory) 0L else e.size) }
                .toList()
        }
    }

    /**
     * Extracts into [destinationDir], creating it if needed.
     *
     * @param onProgress called with (bytesDone, bytesTotal, currentName) on the worker
     *   thread; the caller is responsible for getting back to the main thread.
     * @param cancelled polled per entry; a cancelled extraction removes what it wrote.
     */
    fun extract(
        archivePath: String,
        destinationDir: String,
        cancelled: () -> Boolean = { false },
        onProgress: (Long, Long, String) -> Unit = { _, _, _ -> },
    ): Result<Int> = runCatching {
        val file = File(archivePath)
        if (!file.isFile) throw IOException("Berkas arsip tidak ditemukan")
        val root = File(destinationDir)
        if (!root.isDirectory && !root.mkdirs()) throw IOException("Folder tujuan tidak bisa dibuat")

        ZipFile(file).use { zip ->
            val all = zip.entries().toList()
            // Refusing the archive beats skipping entries. Skipping would return a
            // success with files missing, which is the kind of quiet damage the user
            // only notices when they need the missing file.
            if (all.any { it.isUnsafe() }) {
                throw IOException("Arsip berisi jalur yang keluar dari folder tujuan")
            }
            val entries = all
            val total = entries.filterNot { it.isDirectory }.sumOf { it.size.coerceAtLeast(0L) }
            var done = 0L
            var written = 0
            entries.forEach { entry ->
                if (cancelled()) throw CopyEngine.Cancelled()
                // resolve() collapses any ".." that survived; then compare against the
                // destination so an entry cannot write outside the folder it was
                // extracted into. This is the zip-slip check, and it runs per entry.
                val target = File(root, entry.name).canonicalFile
                if (!Support.isInside(target.absolutePath, root.canonicalFile.absolutePath)) {
                    throw IOException("Arsip berisi jalur yang keluar dari folder tujuan")
                }
                if (entry.isDirectory) {
                    if (!target.isDirectory && !target.mkdirs()) {
                        throw IOException("Folder ${entry.name} tidak bisa dibuat")
                    }
                } else {
                    target.parentFile?.mkdirs()
                    zip.getInputStream(entry).use { input ->
                        target.outputStream().use { output ->
                            val buffer = ByteArray(64 * 1024)
                            while (true) {
                                if (cancelled()) {
                                    target.delete()
                                    throw CopyEngine.Cancelled()
                                }
                                val read = input.read(buffer)
                                if (read <= 0) break
                                output.write(buffer, 0, read)
                                done += read
                                onProgress(done, total, entry.name)
                            }
                        }
                    }
                    written += 1
                }
            }
            written
        }
    }

    /** A name that would escape the destination, or is absolute. */
    private fun ZipEntry.isUnsafe(): Boolean {
        if (name.startsWith("/") || name.startsWith("\\")) return true
        if (name.length > 1 && name[1] == ':') return true
        val parts = name.replace('\\', '/').split('/')
        return parts.any { it == ".." }
    }

    /** Where "extract here" puts things: a folder named after the archive. */
    fun destinationFor(archivePath: String, parentDir: String): String {
        val stem = File(archivePath).name.substringBeforeLast('.', "")
        val base = if (stem.isEmpty()) "Arsip" else stem
        return File(parentDir, net.pure.manager.fs.uniqueName(base, File(parentDir).list()?.toSet().orEmpty(), true))
            .absolutePath
    }
}
