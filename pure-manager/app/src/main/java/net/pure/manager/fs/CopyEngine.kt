package net.pure.manager.fs

import java.io.File
import java.io.IOException
import java.nio.file.Files

/**
 * A copy that reports where it is and can be stopped.
 *
 * The previous copy was a loop of 64 KB reads with no way out. On a folder of two
 * gigabytes the screen simply went quiet: no percentage, no cancel, no evidence
 * that anything was happening. The owner called that "terasa macet" and was right.
 *
 * Cancellation is cooperative and checked between chunks, not between files, so a
 * single large file stops promptly too. A cancelled copy removes the work it has
 * already done -- a half-written file next to the real one reads as data loss, and
 * the user asked to stop, not to be left with debris.
 *
 * Progress is by bytes, not by files, because a folder of one video and nine text
 * files would otherwise show 90% at the start and then hang.
 */
object CopyEngine {

    /** 512 KB: few enough wake-ups to stay cheap, small enough to cancel quickly. */
    private const val CHUNK = 512 * 1024

    /** What the UI draws. Everything here is a plain value, so the UI has no logic. */
    data class Progress(
        val bytesDone: Long,
        val bytesTotal: Long,
        val filesDone: Int,
        val filesTotal: Int,
        val currentName: String,
    ) {
        /** 0f..1f, and never NaN: a zero total would divide by zero on an empty folder. */
        val fraction: Float
            get() = if (bytesTotal <= 0L) 1f else (bytesDone.toDouble() / bytesTotal).toFloat()
    }

    /**
     * Copies each source into [destinationDir], reporting through [onProgress].
     *
     * @param cancelled polled between chunks; the copy stops as soon as it says true.
     * @param onProgress called from the worker thread; the caller hops to the main
     *   thread itself, because this object has no business knowing about Android.
     * @return one Result per source, in the same order, so a partial failure can
     *   name which file failed instead of "gagal".
     */
    fun copy(
        sources: List<String>,
        destinationDir: String,
        cancelled: () -> Boolean,
        onProgress: (Progress) -> Unit,
    ): List<Result<File>> = copyOrMove(
        sources, destinationDir, move = false, cancelled = cancelled, onProgress = onProgress,
    )

    /** Same contract as [copy]; a move that has to cross volumes copies first. */
    fun move(
        sources: List<String>,
        destinationDir: String,
        cancelled: () -> Boolean,
        onProgress: (Progress) -> Unit,
    ): List<Result<File>> = copyOrMove(
        sources, destinationDir, move = true, cancelled = cancelled, onProgress = onProgress,
    )

    private fun copyOrMove(
        sources: List<String>,
        destinationDir: String,
        move: Boolean,
        cancelled: () -> Boolean,
        onProgress: (Progress) -> Unit,
    ): List<Result<File>> {
        val dir = File(destinationDir)
        if (!dir.isDirectory) {
            return sources.map { Result.failure(IOException("Tujuan bukan folder")) }
        }

        // Measure first. A progress bar that starts at an unknown total is a spinner,
        // and a spinner cannot answer "how long will this take".
        val sizes = sources.map { source -> runCatching { measure(File(source)) }.getOrDefault(0L) }
        val fileCounts = sources.map { source -> runCatching { countFiles(File(it)) }.getOrDefault(0) }
        val totalFiles = fileCounts.sum()
        val totalBytes = sizes.sum()
        var doneBytes = 0L
        var doneFiles = 0

        val results = mutableListOf<Result<File>>()
        sources.forEachIndexed { index, source ->
            if (cancelled()) {
                results += Result.failure(Cancelled())
                return@forEach
            }
            val src = File(source)
            val result = runCatching {
                if (!src.exists()) throw IOException("Sumber tidak ditemukan")
                Support.invalidDestination(src.absolutePath, dir.absolutePath)?.let {
                    throw IOException(it)
                }
                val taken = dir.list()?.toSet().orEmpty()
                val target = File(dir, uniqueName(src.name, taken, src.isDirectory))
                if (move && src.renameTo(target)) {
                    doneBytes += sizes[index]
                    doneFiles += fileCounts[index]
                    target
                } else {
                    copyTree(src, target, cancelled) { chunkBytes, name ->
                        doneBytes += chunkBytes
                        onProgress(
                            Progress(
                                bytesDone = doneBytes,
                                bytesTotal = totalBytes,
                                filesDone = doneFiles,
                                filesTotal = totalFiles,
                                currentName = name,
                            ),
                        )
                    }
                    if (cancelled()) {
                        runCatching { deleteTree(target) }
                        throw Cancelled()
                    }
                    if (move && !deleteTree(src)) {
                        throw IOException("Tersalin, tapi sumber tidak terhapus")
                    }
                    doneFiles += fileCounts[index]
                    onProgress(
                        Progress(doneBytes, totalBytes, doneFiles, totalFiles, src.name),
                    )
                    target
                }
            }
            results += result
        }
        return results
    }

    /** Thrown when the user stops the job. Its message is what the toast shows. */
    class Cancelled : IOException("Dibatalkan")

    /**
     * Copies one file or folder tree, reporting after every chunk.
     *
     * The callback receives the delta in bytes so the caller can accumulate, rather
     * than a running total that would have to be recomputed per nested call.
     */
    private fun copyTree(
        src: File,
        target: File,
        cancelled: () -> Boolean,
        onChunk: (Long, String) -> Unit,
    ) {
        if (src.isDirectory) {
            if (!target.mkdirs() && !target.isDirectory) {
                throw IOException("Folder tujuan tidak bisa dibuat")
            }
            src.listFiles()?.forEach { child ->
                if (cancelled()) throw Cancelled()
                copyTree(child, File(target, child.name), cancelled, onChunk)
            }
        } else {
            onChunk(0L, src.name)
            src.inputStream().use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(CHUNK)
                    while (true) {
                        if (cancelled()) throw Cancelled()
                        val read = input.read(buffer)
                        if (read <= 0) break
                        output.write(buffer, 0, read)
                        onChunk(read.toLong(), src.name)
                    }
                }
            }
            target.setLastModified(src.lastModified())
        }
    }

    private fun measure(f: File): Long =
        if (f.isFile) f.length() else f.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    private fun countFiles(f: File): Int =
        if (!f.exists()) 0
        else if (f.isFile) 1
        else f.walkTopDown().count { it.isFile }

    private fun deleteTree(f: File): Boolean {
        if (f.isDirectory) {
            f.listFiles()?.forEach { child -> if (!deleteTree(child)) return false }
        }
        runCatching { Files.deleteIfExists(f.toPath()) }
        if (f.exists()) f.delete()
        return !f.exists()
    }

    // Naming duplicates is not repeated here: `uniqueName` in FileEntry.kt already
    // does it case-insensitively, which matters on FAT32 where "Foto.jpg" and
    // "foto.jpg" are the same file. A second implementation would be the one that
    // drifts, and the two callers would disagree about what is taken.
}
