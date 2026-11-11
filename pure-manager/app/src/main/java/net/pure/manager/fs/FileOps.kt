package net.pure.manager.fs

import java.io.File
import java.io.IOException
import java.nio.file.Files

/**
 * Every operation that changes something on disk.
 *
 * Centralised for one reason: destructive behaviour has to be readable in one
 * place. Each function returns [Result] instead of throwing, because a file
 * manager that crashes on a permission error is worse than one that reports it,
 * and the caller always has something useful to show.
 *
 * Nothing here is clever. No background service, no queue: an operation either
 * finished when it returns or it failed with a message. Long copies are a stage-3
 * concern, together with progress and cancellation.
 */
object FileOps {

    private const val CHUNK = 64 * 1024

    fun rename(entry: FileEntry, newName: String): Result<File> = runCatching {
        validateName(newName)?.let { throw IOException(it) }
        val source = File(entry.path)
        val target = File(source.parentFile, newName.trim())
        if (target.exists()) throw IOException("Sudah ada berkas bernama itu")
        if (!source.renameTo(target)) {
            // renameTo fails across volumes; a copy-and-delete is the honest
            // fallback and preserves the failure if either half breaks.
            if (source.isDirectory) throw IOException("Tidak bisa memindahkan folder itu")
            copyFile(source, target)
            if (!source.delete()) throw IOException("Tersalin, tapi yang lama tidak terhapus")
        }
        target
    }

    fun createFolder(parent: String, name: String): Result<File> = runCatching {
        validateName(name)?.let { throw IOException(it) }
        val dir = File(parent, name.trim())
        if (dir.exists()) throw IOException("Folder itu sudah ada")
        if (!dir.mkdirs()) throw IOException("Folder tidak bisa dibuat di sini")
        dir
    }

    fun createFile(parent: String, name: String): Result<File> = runCatching {
        validateName(name)?.let { throw IOException(it) }
        val f = File(parent, name.trim())
        if (f.exists()) throw IOException("Berkas itu sudah ada")
        if (!f.createNewFile()) throw IOException("Berkas tidak bisa dibuat di sini")
        f
    }

    /**
     * Copies a file or folder. Refuses to copy a folder into itself, which would
     * otherwise recurse until the disk fills.
     */
    fun copy(source: String, destinationDir: String): Result<File> = runCatching {
        val src = File(source)
        val dir = File(destinationDir)
        if (!src.exists()) throw IOException("Sumber tidak ditemukan")
        if (!dir.isDirectory) throw IOException("Tujuan bukan folder")
        // Two cases, and the first one is the dangerous one: copying a folder
        // into ITSELF recurses until the disk is full. The original guard only
        // rejected a destination *inside* the source, so src == dir slipped
        // through and the JVM test caught it.
        if (src.isDirectory && dir.absolutePath == src.absolutePath) {
            throw IOException("Tidak bisa menyalin folder ke dalam dirinya sendiri")
        }
        if (src.isDirectory && dir.absolutePath.startsWith(src.absolutePath + File.separator)) {
            throw IOException("Tidak bisa menyalin folder ke dalam dirinya sendiri")
        }
        val taken = dir.list()?.toSet().orEmpty()
        val name = uniqueName(src.name, taken, src.isDirectory)
        val target = File(dir, name)
        if (src.isDirectory) copyDirectory(src, target) else copyFile(src, target)
        target
    }

    /** Moves by renaming when possible, copying only across volumes. */
    fun move(source: String, destinationDir: String): Result<File> = runCatching {
        val src = File(source)
        val dir = File(destinationDir)
        if (!src.exists()) throw IOException("Sumber tidak ditemukan")
        if (!dir.isDirectory) throw IOException("Tujuan bukan folder")
        if (src.isDirectory && src.absolutePath == dir.absolutePath) {
            throw IOException("Tidak bisa memindahkan folder ke dalam dirinya sendiri")
        }
        if (src.absolutePath == dir.absolutePath) throw IOException("Sudah di folder ini")
        if (src.isDirectory && dir.absolutePath.startsWith(src.absolutePath + File.separator)) {
            throw IOException("Tidak bisa memindahkan folder ke dalam dirinya sendiri")
        }
        val taken = dir.list()?.toSet().orEmpty()
        val target = File(dir, uniqueName(src.name, taken, src.isDirectory))
        if (src.renameTo(target)) return@runCatching target
        if (src.isDirectory) copyDirectory(src, target) else copyFile(src, target)
        if (!deleteRecursively(src)) throw IOException("Tersalin, tapi sumber tidak terhapus")
        target
    }

    fun delete(entry: FileEntry): Result<Unit> = runCatching {
        val f = File(entry.path)
        if (!f.exists()) throw IOException("Sudah tidak ada")
        if (!deleteRecursively(f)) throw IOException("Sebagian tidak bisa dihapus")
    }

    /** Total bytes and file count, for the confirmation dialog on a delete. */
    fun measure(entry: FileEntry): Pair<Long, Int> {
        val f = File(entry.path)
        if (!f.exists()) return 0L to 0
        if (f.isFile) return f.length() to 1
        var bytes = 0L
        var files = 0
        f.walkTopDown().forEach { if (it.isFile) { bytes += it.length(); files++ } }
        return bytes to files
    }

    private fun copyFile(src: File, target: File) {
        src.inputStream().use { input ->
            target.outputStream().use { output ->
                val buffer = ByteArray(CHUNK)
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    output.write(buffer, 0, read)
                }
            }
        }
        target.setLastModified(src.lastModified())
    }

    private fun copyDirectory(src: File, target: File) {
        if (!target.mkdirs()) throw IOException("Folder tujuan tidak bisa dibuat")
        src.listFiles()?.forEach { child ->
            val childTarget = File(target, child.name)
            if (child.isDirectory) copyDirectory(child, childTarget) else copyFile(child, childTarget)
        }
    }

    private fun deleteRecursively(f: File): Boolean {
        if (f.isDirectory) {
            f.listFiles()?.forEach { child -> if (!deleteRecursively(child)) return false }
        }
        // Files.deleteIfExists throws on failure where File.delete returns false,
        // so the two cover each other. Success is re-checked at the end.
        runCatching { Files.deleteIfExists(f.toPath()) }
        if (f.exists()) f.delete()
        return !f.exists()
    }
}
