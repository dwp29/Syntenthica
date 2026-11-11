package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Zip handling, including the one case that matters most: an archive that tries to
 * write outside the folder it was extracted into.
 */
class ArchiveTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun zip(name: String, entries: Map<String, String>): File {
        val f = File(temp.root, name)
        ZipOutputStream(f.outputStream()).use { out ->
            entries.forEach { (path, content) ->
                out.putNextEntry(ZipEntry(path))
                out.write(content.toByteArray())
                out.closeEntry()
            }
        }
        return f
    }

    @Test
    fun `listing reports names, folders and sizes without extracting`() {
        val archive = zip(
            "a.zip",
            mapOf("satu.txt" to "halo", "folder/dua.txt" to "dunia"),
        )

        val entries = Archive.list(archive.absolutePath).getOrThrow()

        assertEquals(2, entries.size)
        assertEquals("satu.txt", entries[0].name)
        assertEquals(5L, entries[0].bytes)
        assertTrue(entries.none { it.isDirectory })
    }

    @Test
    fun `extracting writes the tree and counts the files`() {
        val archive = zip("b.zip", mapOf("x.txt" to "abc", "sub/y.txt" to "def"))
        val out = temp.newFolder("out")

        val count = Archive.extract(archive.absolutePath, out.absolutePath).getOrThrow()

        assertEquals(2, count)
        assertEquals("abc", File(out, "x.txt").readText())
        assertEquals("def", File(out, "sub/y.txt").readText())
    }

    @Test
    fun `an archive that climbs out of the destination is refused`() {
        val archive = zip(
            "evil.zip",
            mapOf("../keluar.txt" to "tidak boleh", "aman.txt" to "boleh"),
        )
        val out = temp.newFolder("out")

        val result = Archive.extract(archive.absolutePath, out.absolutePath)

        // This is zip slip: the entry name would write into the parent folder.
        assertTrue(result.isFailure)
        assertFalse(File(temp.root, "keluar.txt").exists())
    }

    @Test
    fun `an absolute path inside the archive is refused`() {
        val archive = zip("abs.zip", mapOf("/data/local/x.txt" to "tidak"))
        val out = temp.newFolder("out")

        assertTrue(Archive.extract(archive.absolutePath, out.absolutePath).isFailure)
    }

    @Test
    fun `listing skips unsafe entries rather than showing what it will not extract`() {
        val archive = zip("mixed.zip", mapOf("../x.txt" to "a", "y.txt" to "b"))

        val entries = Archive.list(archive.absolutePath).getOrThrow()

        assertEquals(listOf("y.txt"), entries.map { it.name })
    }

    @Test
    fun `progress reaches the total`() {
        val archive = zip("c.zip", mapOf("a.txt" to "12345", "b.txt" to "67890"))
        val out = temp.newFolder("out")
        var lastDone = 0L
        var lastTotal = 0L

        Archive.extract(archive.absolutePath, out.absolutePath) { done, total, _ ->
            lastDone = done
            lastTotal = total
        }

        assertEquals(10L, lastTotal)
        assertEquals(10L, lastDone)
    }

    @Test
    fun `the default destination is the archive name without the extension`() {
        val archive = zip("Liburan 2024.zip", mapOf("a.txt" to "x"))
        val out = temp.newFolder("out")

        assertEquals(
            File(out, "Liburan 2024").absolutePath,
            Archive.destinationFor(archive.absolutePath, out.absolutePath),
        )
    }

    @Test
    fun `a second extraction gets its own folder instead of merging`() {
        val archive = zip("Laporan.zip", mapOf("a.txt" to "x"))
        val out = temp.newFolder("out")
        File(out, "Laporan").mkdirs()

        assertEquals(
            File(out, "Laporan (1)").absolutePath,
            Archive.destinationFor(archive.absolutePath, out.absolutePath),
        )
    }

    @Test
    fun `only zip is claimed`() {
        assertTrue(Archive.isZip("data.ZIP"))
        assertFalse(Archive.isZip("data.rar"))
        assertFalse(Archive.isZip("data.7z"))
    }
}
