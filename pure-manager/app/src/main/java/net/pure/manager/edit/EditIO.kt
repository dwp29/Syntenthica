package net.pure.manager.edit

import android.content.Context
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import java.io.File
import java.io.IOException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction
import java.nio.ByteBuffer

/**
 * Reading and writing the file being edited.
 *
 * Two hard limits, both learned from what happens when a text editor is pointed at
 * the wrong file:
 *
 *  - Size. Opening a 200 MB video as text would read 200 MB into a String and take
 *    the app down. [MAX_BYTES] refuses instead, with a sentence saying why.
 *  - Encoding. A PNG has no text in it. Bytes that are not valid UTF-8 are reported
 *    as "not text" rather than shown as replacement characters, because a screen
 *    full of `????` looks like a bug in the editor.
 *
 * Writes go through one path for a real file and one for a SAF document, because
 * those are genuinely two different mechanisms, and a SAF write that goes to the
 * wrong one silently does nothing.
 */
object EditIO {

    /**
     * 8 MB of text is about four million characters: a lot, and still safe to hold.
     *
     * Typed `Int` on purpose. As an untyped `const val` the constant is a `Long`, and
     * every comparison against `ByteArray.size` or `File.length()` then needs a cast
     * in one direction or the other -- which is exactly the kind of detail that
     * compiles nowhere and only shows up in CI.
     */
    const val MAX_BYTES: Int = 8 * 1024 * 1024

    enum class Encoding(val label: String) {
        UTF8("UTF-8"),
        LATIN1("Latin-1"),
    }

    /**
     * The result of reading. [Encoding] is what the file turned out to be, so a save
     * writes it back the same way instead of flipping a Windows-1252 file to UTF-8
     * and mangling every accent in it.
     */
    data class Loaded(val text: String, val encoding: Encoding, val lineEnding: LineEnding)

    enum class LineEnding(val sequence: String) {
        LF("\n"),
        CRLF("\r\n"),
    }

    class NotText(message: String) : IOException(message)

    /**
     * Reads [path] as text.
     *
     * Throws [NotText] with an Indonesian message that the editor shows verbatim.
     * The messages name the limit in MB rather than in bytes: "8388608 byte" is not
     * something anyone can act on.
     */
    fun read(context: Context, path: String): Loaded {
        val bytes = readBytes(context, path)
        if (bytes.size > MAX_BYTES) {
            throw NotText(
                "Berkas ini ${formatMb(bytes.size)} MB, lebih besar dari batas " +
                    "${MAX_BYTES / (1024 * 1024)} MB untuk editor. Buka dengan aplikasi lain."
            )
        }
        if (bytes.any { it == 0.toByte() }) {
            throw NotText("Berkas ini berisi data biner, bukan teks. Tidak bisa diedit di sini.")
        }
        val (text, encoding) = decode(bytes)
        val lineEnding = if (text.contains("\r\n")) LineEnding.CRLF else LineEnding.LF
        return Loaded(text.replace("\r\n", "\n"), encoding, lineEnding)
    }

    /**
     * UTF-8 first, then Latin-1, then refuse.
     *
     * Latin-1 accepts every byte sequence, so it must come last: trying it first
     * would "succeed" on a PNG and turn it into mojibake. Bytes that produce control
     * characters other than tab and newline are treated as binary, which is what
     * catches a ZIP or an APK that happens to be valid UTF-8 by accident.
     */
    private fun decode(bytes: ByteArray): Pair<String, Encoding> {
        // A BOM is not text either. Strip it so the first line is not invisible to
        // search and the cursor does not start one column in.
        val body = if (bytes.size >= 3 && bytes[0] == 0xEF.toByte() &&
            bytes[1] == 0xBB.toByte() && bytes[2] == 0xBF.toByte()
        ) bytes.copyOfRange(3, bytes.size) else bytes
        runCatching {
            val decoder = Charsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
            val text = decoder.decode(ByteBuffer.wrap(body)).toString()
            if (hasControlNoise(text)) throw NotText("Berkas ini berisi data biner, bukan teks.")
            return text to Encoding.UTF8
        }
        val latin = String(body, Charsets.ISO_8859_1)
        if (hasControlNoise(latin)) {
            throw NotText("Berkas ini berisi data biner, bukan teks. Tidak bisa diedit di sini.")
        }
        return latin to Encoding.LATIN1
    }

    private fun hasControlNoise(text: String): Boolean =
        text.any { it.code < 32 && it != '\n' && it != '\r' && it != '\t' } ||
            text.count { it == '\u0000' } > 0

    /**
     * Writes [text] back to [path].
     *
     * The line ending is restored, not normalised: a file that came in with CRLF was
     * last touched by something else (Windows, a build script), and silently
     * rewriting every line of it shows up as a whole-file diff.
     */
    fun write(context: Context, path: String, text: String, encoding: Encoding, lineEnding: LineEnding) {
        val out = if (lineEnding == LineEnding.CRLF) text.replace("\n", "\r\n") else text
        val charset: Charset = when (encoding) {
            Encoding.UTF8 -> Charsets.UTF_8
            Encoding.LATIN1 -> Charsets.ISO_8859_1
        }
        val bytes = out.toByteArray(charset)
        if (bytes.any { it == 0.toByte() }) throw IOException("Teks mengandung karakter yang tidak bisa disimpan")
        if (PathKind.of(path) == PathKind.DOCUMENT) {
            val uri = Uri.parse(path)
            val resolver = context.contentResolver
            // "wt" truncates. Without it the write appends over the old content and a
            // shorter file keeps the tail of the longer one.
            val stream = resolver.openOutputStream(uri, "wt")
                ?: throw IOException("Tidak bisa menulis ke berkas ini")
            stream.use { it.write(bytes) }
        } else {
            val target = File(path)
            // Write to a sibling and rename, so a crash mid-write cannot leave the
            // owner with half a file. The temp name is hidden from the browser by the
            // dot prefix and is removed on failure.
            val temp = File(target.parentFile, ".${target.name}.tmp")
            try {
                temp.writeBytes(bytes)
                if (!temp.renameTo(target)) {
                    // renameTo fails across a mount or when the target is busy; a
                    // direct write is still better than losing the edit.
                    target.writeBytes(bytes)
                    temp.delete()
                }
            } finally {
                if (temp.exists()) temp.delete()
            }
        }
    }

    private fun readBytes(context: Context, path: String): ByteArray =
        if (PathKind.of(path) == PathKind.DOCUMENT) {
            val uri = Uri.parse(path)
            val resolver = context.contentResolver
            // Ask the provider for the size first. A 500 MB file is refused before it
            // is read, not after -- the point of the limit is to not read it.
            val declared = runCatching {
                resolver.openAssetFileDescriptor(uri, "r")?.use { it.length }
            }.getOrNull() ?: -1L
            if (declared > MAX_BYTES) throw NotText(bigMessage(declared))
            val stream = resolver.openInputStream(uri)
                ?: throw IOException("Berkas tidak bisa dibuka")
            stream.use { readCapped(it, MAX_BYTES) }
        } else {
            val f = File(path)
            if (!f.exists()) throw IOException("Berkas tidak ada")
            if (f.length() > MAX_BYTES) throw NotText(bigMessage(f.length()))
            f.readBytes()
        }

    private fun bigMessage(bytes: Long): String =
        "Berkas ini ${formatMb(bytes)} MB, lebih besar dari batas " +
            "${MAX_BYTES / (1024 * 1024)} MB untuk editor. Buka dengan aplikasi lain."

    private fun formatMb(bytes: Long): String = String.format(java.util.Locale.US, "%.1f", bytes / (1024.0 * 1024))

    /**
     * Reads at most [cap] bytes, then refuses.
     *
     * A provider that lies about its length (many do, returning -1 or 0) would
     * otherwise stream an unbounded file into memory. This is the guard that actually
     * holds when the declared size is useless.
     */
    private fun readCapped(stream: java.io.InputStream, cap: Int): ByteArray {
        val buffer = java.io.ByteArrayOutputStream(minOf(cap, 64 * 1024))
        val chunk = ByteArray(64 * 1024)
        var total = 0
        while (true) {
            val n = stream.read(chunk)
            if (n < 0) break
            total += n
            if (total > cap) throw NotText(bigMessage(total.toLong()))
            buffer.write(chunk, 0, n)
        }
        return buffer.toByteArray()
    }

    /** True when the file looks like something the editor should offer to open. */
    fun isLikelyText(name: String): Boolean = Language.forFileName(name) != Language.PLAIN ||
        name.substringAfterLast('.', "").lowercase() in setOf("txt", "text", "log", "csv", "tsv", "lst", "md", "yaml", "yml", "sql", "bat", "ps1", "gitignore")

    /** Reads a document URI's display name, used in the title bar. */
    fun displayName(context: Context, path: String): String =
        if (PathKind.of(path) == PathKind.DOCUMENT) {
            runCatching { DocumentFile.fromSingleUri(context, Uri.parse(path))?.name }
                .getOrNull() ?: File(path).name.ifEmpty { path }
        } else {
            File(path).name.ifEmpty { path }
        }
}

/**
 * Whether a path is a real file or a SAF document.
 *
 * A top-level enum rather than a nested one: `PathKind.of(path)` has to read the same
 * way inside [EditIO]'s own methods, and a nested declaration shadows the outer name.
 * It mirrors `Storage.isTreePath` on purpose, but lives here so the editor does not
 * have to depend on the browser.
 */
enum class PathKind {
    FILE,
    DOCUMENT,
    ;

    companion object {
        fun of(path: String): PathKind = if (path.startsWith("content://")) DOCUMENT else FILE
    }
}
