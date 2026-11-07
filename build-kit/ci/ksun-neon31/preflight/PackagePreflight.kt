package com.rifsxd.ksunext.ui.preflight

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest
import java.util.Locale
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/** A bounded structural inspection, not a malware scan or authenticity check. */
internal enum class PackageKind { MODULE, ANYKERNEL }
internal enum class PreflightProblem {
    UNREADABLE, TOO_LARGE, TOO_MANY_ENTRIES, UNSAFE_PATH, DUPLICATE_PATH,
    INVALID_ZIP, UNSUPPORTED_ZIP, UNKNOWN_TYPE, AMBIGUOUS_TYPE, MISSING_INSTALLER, INVALID_METADATA,
}
internal class PreflightException(val problem: PreflightProblem) : IOException(problem.name)
internal data class PackageReport(
    val file: File,
    val displayName: String,
    val size: Long,
    val sha256: String,
    val kind: PackageKind,
    val metadata: Map<String, String>,
)

internal object PackagePreflight {
    const val MAX_ARCHIVE_BYTES = 512L * 1024L * 1024L
    const val MAX_ENTRIES = 10_000
    private const val MAX_METADATA_BYTES = 64 * 1024

    /** Write a private temporary copy, then inspect it without executing it. */
    fun stageAndInspect(
        input: InputStream,
        destination: File,
        fileName: String,
        maxBytes: Long = MAX_ARCHIVE_BYTES,
        maxEntries: Int = MAX_ENTRIES,
    ): PackageReport {
        try {
            if (maxBytes <= 0 || maxEntries <= 0) throw PreflightException(PreflightProblem.INVALID_ZIP)
            val digest = MessageDigest.getInstance("SHA-256")
            var size = 0L
            try {
                input.use { source ->
                    destination.outputStream().buffered().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val read = source.read(buffer)
                            if (read < 0) break
                            if (read == 0) continue
                            if (read.toLong() > maxBytes - size) throw PreflightException(PreflightProblem.TOO_LARGE)
                            output.write(buffer, 0, read)
                            digest.update(buffer, 0, read)
                            size += read.toLong()
                        }
                    }
                }
            } catch (error: PreflightException) {
                throw error
            } catch (_: IOException) {
                throw PreflightException(PreflightProblem.UNREADABLE)
            } catch (_: SecurityException) {
                throw PreflightException(PreflightProblem.UNREADABLE)
            }
            if (size == 0L) throw PreflightException(PreflightProblem.INVALID_ZIP)
            val (kind, metadata) = inspectZip(destination, maxEntries)
            return PackageReport(destination, safeLabel(fileName).ifBlank { "unknown.zip" }, size,
                digest.digest().toHex(), kind, metadata)
        } catch (error: Exception) {
            destination.delete()
            throw error
        }
    }

    private fun inspectZip(file: File, maxEntries: Int): Pair<PackageKind, Map<String, String>> {
        try {
            val expectedEntries = ZipStructure.validate(file, maxEntries)
            ZipFile(file).use { zip ->
                val names = mutableSetOf<String>()
                var module: ZipEntry? = null
                var anyKernel: ZipEntry? = null
                var installer: ZipEntry? = null
                var count = 0
                val entries = zip.entries()
                while (entries.hasMoreElements()) {
                    val entry = entries.nextElement()
                    count++
                    if (count > maxEntries) throw PreflightException(PreflightProblem.TOO_MANY_ENTRIES)
                    val path = normalizedPath(entry.name)
                    if (path.isEmpty()) continue
                    if (!names.add(path)) throw PreflightException(PreflightProblem.DUPLICATE_PATH)
                    if (!entry.isDirectory) {
                        when (path) {
                            "module.prop" -> module = entry
                            "anykernel.sh" -> anyKernel = entry
                            "META-INF/com/google/android/update-binary" -> installer = entry
                        }
                    }
                }
                if (count != expectedEntries) throw PreflightException(PreflightProblem.INVALID_ZIP)
                if (module != null && anyKernel != null) throw PreflightException(PreflightProblem.AMBIGUOUS_TYPE)
                if (module != null) return PackageKind.MODULE to readProperties(zip, module)
                if (anyKernel != null) {
                    if (installer == null || installer.size <= 0 || anyKernel.size <= 0) {
                        throw PreflightException(PreflightProblem.MISSING_INSTALLER)
                    }
                    // Verify marker streams can be opened, but never run their contents.
                    zip.getInputStream(anyKernel).use { if (it.read() < 0) throw PreflightException(PreflightProblem.INVALID_ZIP) }
                    zip.getInputStream(installer).use { if (it.read() < 0) throw PreflightException(PreflightProblem.INVALID_ZIP) }
                    return PackageKind.ANYKERNEL to emptyMap()
                }
                throw PreflightException(PreflightProblem.UNKNOWN_TYPE)
            }
        } catch (error: PreflightException) {
            throw error
        } catch (_: IOException) {
            throw PreflightException(PreflightProblem.INVALID_ZIP)
        } catch (_: IllegalArgumentException) {
            throw PreflightException(PreflightProblem.INVALID_ZIP)
        }
    }

    private fun normalizedPath(name: String): String {
        if (name.length > 1024 || name.startsWith('/') || name.startsWith('\\') ||
            name.contains('\\') || name.any { it.isISOControl() } || Regex("^[A-Za-z]:").containsMatchIn(name)) {
            throw PreflightException(PreflightProblem.UNSAFE_PATH)
        }
        val segments = name.split('/')
        if (segments.any { it == ".." }) throw PreflightException(PreflightProblem.UNSAFE_PATH)
        return segments.filter { it.isNotEmpty() && it != "." }.joinToString("/")
    }

    private fun readProperties(zip: ZipFile, entry: ZipEntry): Map<String, String> {
        if (entry.size < 0 || entry.size > MAX_METADATA_BYTES) throw PreflightException(PreflightProblem.INVALID_METADATA)
        val bytes = ByteArrayOutputStream()
        zip.getInputStream(entry).use { input ->
            val buffer = ByteArray(4096)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count == 0) continue
                if (bytes.size() + count > MAX_METADATA_BYTES) throw PreflightException(PreflightProblem.INVALID_METADATA)
                bytes.write(buffer, 0, count)
            }
        }
        val raw = bytes.toByteArray()
        val crc = CRC32().apply { update(raw) }.value
        if (entry.size != raw.size.toLong() || entry.crc != crc) throw PreflightException(PreflightProblem.INVALID_METADATA)
        val result = mutableMapOf<String, String>()
        raw.toString(Charsets.UTF_8).lineSequence().forEach { line ->
            val trimmed = line.trim()
            if (!trimmed.startsWith('#') && '=' in trimmed) {
                val (key, value) = trimmed.split('=', limit = 2)
                if (key.trim() in setOf("id", "name", "version", "author")) {
                    result[key.trim()] = safeLabel(value)
                }
            }
        }
        if (result["id"].isNullOrBlank()) throw PreflightException(PreflightProblem.INVALID_METADATA)
        return result
    }

    private fun safeLabel(value: String): String = value
        .map { if (it.isISOControl() || Character.getType(it) == Character.FORMAT.toInt()) ' ' else it }
        .joinToString("").trim().take(120)

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }

    /** Check the exact private copy immediately before the existing installer runs. */
    fun matchesSha256(file: File, expected: String): Boolean {
        if (!expected.matches(Regex("[0-9a-f]{64}"))) return false
        return runCatching {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().buffered().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (count > 0) digest.update(buffer, 0, count)
                }
            }
            MessageDigest.isEqual(digest.digest(), expected.chunked(2).map { it.toInt(16).toByte() }.toByteArray())
        }.getOrDefault(false)
    }
}
