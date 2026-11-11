package net.pure.manager.fs

import java.io.File

/**
 * The small decisions that sit between the UI and the operating system.
 *
 * They live here, with no Android types, for the same reason the sorting rules do:
 * they are the parts that are easy to get subtly wrong, and they are the only parts
 * a JVM test can exercise on every build. The Android side (Storage) collects the
 * inputs and calls in; it does not decide.
 */
object Support {

    /** True when the path is a SAF document URI rather than a file path. */
    fun isDocumentUri(path: String): Boolean = path.startsWith("content://")

    /**
     * Where the up button goes, or null at the wall.
     *
     * Null is what hides the button, and hiding it is the honest thing to do: an up
     * button that silently does nothing reads as a broken app. The previous version
     * returned SAF paths unchanged, so on a granted folder the button was visible
     * and did nothing at all.
     *
     * A tree document URI ends in `/document/<document id>`; the id is
     * `primary:Folder/Sub`, so walking up is trimming the last segment and encoding
     * the result the same way it arrived. No Android types are needed for that, which
     * is why it is here and not in Storage.
     */
    fun parentOf(path: String): String? {
        if (path.isEmpty()) return null
        if (!isDocumentUri(path)) return File(path).parentFile?.absolutePath

        val marker = path.lastIndexOf("/document/")
        if (marker < 0) return null
        val encodedId = path.substring(marker + "/document/".length)
        val docId = percentDecode(encodedId)
        val parentId = when {
            docId.contains('/') -> docId.substringBeforeLast('/')
            // "primary:" is the volume itself; there is nothing above it.
            else -> null
        } ?: return null
        if (parentId.isEmpty() || parentId == docId) return null
        return path.substring(0, marker) + "/document/" + percentEncode(parentId)
    }

    /** True when [child] is [parent] or somewhere underneath it. */
    fun isInside(child: String, parent: String): Boolean {
        if (parent.isEmpty() || child.isEmpty()) return false
        val trimmed = parent.trimEnd('/')
        return child == trimmed || child.startsWith("$trimmed/")
    }

    /**
     * Why a copy or a move to this destination is not allowed, or null if it is.
     *
     * Copying a folder into itself recurses until the disk fills, and copying it
     * into its own parent is a no-op with extra steps. Both are refusals, not
     * warnings: by the time the dialog says "this will take a while" the user has
     * already agreed to the wrong thing.
     */
    fun invalidDestination(source: String, destination: String): String? = when {
        source == destination -> "Tujuan sama dengan sumber"
        isInside(destination, source) -> "Tidak bisa menyalin folder ke dalam dirinya sendiri"
        else -> null
    }

    /**
     * The places shown in the app: internal storage, every external volume, and the
     * folders the user granted through SAF.
     *
     * Volumes arrive as (label, path, readable) triples so this stays testable; the
     * Android side collects them from StorageManager and hands them over.
     */
    fun places(
        internalPath: String,
        volumes: List<Triple<String, String, Boolean>>,
        trees: List<Pair<String, String>>,
    ): List<Location> {
        val out = mutableListOf<Location>()
        if (internalPath.isNotEmpty()) {
            out += Location("Internal", internalPath, "Penyimpanan dalam perangkat")
        }
        volumes.forEach { (label, path, readable) ->
            out += Location(label, path, if (readable) "Kartu SD" else "Tidak terpasang")
        }
        trees.forEach { (label, uri) ->
            out += Location(label, uri, "Folder pilihan")
        }
        return out
    }

    /**
     * The count line under a folder listing.
     *
     * Pulled out as a function because the empty case was wrong: an empty list has
     * zero folders and zero files, so the line read "0 folder \u00b7 0 berkas", which
     * looks like a failed load rather than an empty folder.
     */
    fun countLabel(entries: List<FileEntry>): String {
        if (entries.isEmpty()) return "Kosong"
        val folders = entries.count { it.isDirectory }
        val files = entries.size - folders
        val parts = mutableListOf<String>()
        if (folders > 0) parts += "$folders folder"
        if (files > 0) parts += "$files berkas"
        return parts.joinToString(" \u00b7 ")
    }

    /**
     * The MIME type to hand the system when opening a file.
     *
     * Guessing wrong is the difference between "Buka dengan" showing a text editor
     * and showing nothing at all, so the common types are listed explicitly and
     * everything else gets the generic binary type rather than an empty one:
     * an empty type matches no app.
     */
    fun mimeFor(name: String): String {
        val ext = name.substringAfterLast('.', "").lowercase()
        return when (ext) {
            "txt", "log", "md", "ini", "conf", "csv", "json", "xml", "yml", "yaml" -> "text/plain"
            "htm", "html" -> "text/html"
            "pdf" -> "application/pdf"
            "png" -> "image/png"
            "jpg", "jpeg" -> "image/jpeg"
            "webp" -> "image/webp"
            "gif" -> "image/gif"
            "bmp" -> "image/bmp"
            "heic" -> "image/heic"
            "mp3" -> "audio/mpeg"
            "m4a", "aac" -> "audio/mp4"
            "wav" -> "audio/wav"
            "ogg", "opus" -> "audio/ogg"
            "flac" -> "audio/flac"
            "mp4", "m4v" -> "video/mp4"
            "mkv" -> "video/x-matroska"
            "webm" -> "video/webm"
            "avi" -> "video/x-msvideo"
            "mov" -> "video/quicktime"
            "3gp" -> "video/3gpp"
            "zip" -> "application/zip"
            "apk" -> "application/vnd.android.package-archive"
            "doc", "docx" -> "application/msword"
            "xls", "xlsx" -> "application/vnd.ms-excel"
            "ppt", "pptx" -> "application/vnd.ms-powerpoint"
            else -> "application/octet-stream"
        }
    }

    /** Percent-encodes everything that is not unreserved, which is what Uri.encode does. */
    fun percentEncode(value: String): String {
        val sb = StringBuilder()
        value.toByteArray(Charsets.UTF_8).forEach { b ->
            val c = b.toInt() and 0xFF
            val ch = c.toChar()
            if (ch.isLetterOrDigit() && c < 128 || ch in "-_.~") {
                sb.append(ch)
            } else {
                sb.append('%').append(HEX[c shr 4]).append(HEX[c and 0x0F])
            }
        }
        return sb.toString()
    }

    /**
     * Percent-decodes without treating `+` as a space.
     *
     * java.net.URLDecoder does treat it as a space, which would silently rename any
     * file that contains a plus sign. This is six lines and cannot make that mistake.
     */
    fun percentDecode(value: String): String {
        val bytes = java.io.ByteArrayOutputStream()
        var i = 0
        while (i < value.length) {
            val ch = value[i]
            if (ch == '%' && i + 2 < value.length) {
                val hex = value.substring(i + 1, i + 3).toIntOrNull(16)
                if (hex != null) {
                    bytes.write(hex)
                    i += 3
                    continue
                }
            }
            bytes.write(ch.toString().toByteArray(Charsets.UTF_8))
            i += 1
        }
        return String(bytes.toByteArray(), Charsets.UTF_8)
    }

    private val HEX = "0123456789ABCDEF".toCharArray()
}
