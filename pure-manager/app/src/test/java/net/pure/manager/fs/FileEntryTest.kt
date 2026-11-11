package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The only part of this app that CI can actually exercise.
 *
 * No Android framework here on purpose: sorting, formatting and name validation
 * are pure Kotlin, so `testReleaseUnitTest` runs them on the JVM inside the build.
 * Everything that touches the real file system is verified by the owner on a
 * device, because this sandbox has none.
 */
class FileEntryTest {

    private fun entry(
        name: String,
        dir: Boolean = false,
        size: Long = 0,
        modified: Long = 0,
    ) = FileEntry(
        path = "/sdcard/$name",
        name = name,
        isDirectory = dir,
        sizeBytes = size,
        lastModified = modified,
        isHidden = name.startsWith("."),
        canRead = true,
    )

    @Test
    fun `folders stay on top in both directions`() {
        val items = listOf(entry("a.txt"), entry("Zeta", dir = true), entry("b.txt"))
        for (descending in listOf(false, true)) {
            val sorted = items.sortedWith(comparatorFor(SortOrder(SortKey.NAME, descending)))
            assertTrue("folder must lead when descending=$descending", sorted.first().isDirectory)
        }
    }

    @Test
    fun `names sort case-insensitively`() {
        val items = listOf(entry("banana.txt"), entry("Apple.txt"), entry("cherry.txt"))
        val sorted = items.sortedWith(comparatorFor(SortOrder(SortKey.NAME, false))).map { it.name }
        assertEquals(listOf("Apple.txt", "banana.txt", "cherry.txt"), sorted)
    }

    @Test
    fun `descending reverses the files but not the folders`() {
        val items = listOf(entry("a.txt", size = 10), entry("b.txt", size = 20), entry("dir", dir = true))
        val sorted = items.sortedWith(comparatorFor(SortOrder(SortKey.SIZE, true)))
        assertEquals("dir", sorted.first().name)
        assertEquals(listOf("b.txt", "a.txt"), sorted.drop(1).map { it.name })
    }

    @Test
    fun `sizes use binary units and folders say folder`() {
        assertEquals("Folder", formatSize(0, isDirectory = true))
        assertEquals("512 B", formatSize(512, false))
        assertEquals("1 KB", formatSize(1024, false))
        assertEquals("1.5 MB", formatSize((1.5 * 1024 * 1024).toLong(), false))
        assertEquals("2.00 GB", formatSize(2L * 1024 * 1024 * 1024, false))
    }

    @Test
    fun `dates collapse to time today and month this year`() {
        val now = 1_760_000_000_000L // fixed clock, so the assertion is stable
        assertEquals("\u2014", formatDate(0, now))
        val sameDay = formatDate(now - 60_000, now)
        assertTrue("today should be a clock time, was $sameDay", sameDay.contains(":"))
        val thisYear = formatDate(now - 1000L * 60 * 60 * 24 * 40, now)
        assertTrue("should omit the year, was $thisYear", !thisYear.contains("2026"))
    }

    @Test
    fun `name validation rejects the characters a file name cannot hold`() {
        assertNull(validateName("laporan.pdf"))
        assertNull(validateName("catatan 2026"))
        assertTrue(validateName("")!!.contains("kosong"))
        assertTrue(validateName("   ")!!.contains("kosong"))
        assertTrue(validateName("a/b")!!.contains("/"))
        assertTrue(validateName("..")!!.isNotEmpty())
        assertTrue(validateName("x".repeat(300))!!.contains("panjang"))
        assertTrue(validateName("nama ")!!.contains("spasi"))
        for (bad in listOf("a\\b", "a:b", "a*b", "a?b", "a\"b", "a<b", "a>b", "a|b")) {
            assertTrue("$bad should be rejected", validateName(bad) != null)
        }
    }

    @Test
    fun `duplicate names get a suffix before the extension`() {
        assertEquals("baru.txt", uniqueName("baru.txt", emptySet(), false))
        assertEquals("baru (1).txt", uniqueName("baru.txt", setOf("baru.txt"), false))
        assertEquals("baru (2).txt", uniqueName("baru.txt", setOf("baru.txt", "baru (1).txt"), false))
        assertEquals("Folder (1)", uniqueName("Folder", setOf("folder"), true))
    }

    @Test
    fun `extension is lowercased and empty for folders`() {
        assertEquals("pdf", entry("Laporan.PDF").extension)
        assertEquals("", entry("Tanpa Titik").extension)
        assertEquals("", entry("folder", dir = true).extension)
    }

    // ---- FileOps against a real temporary directory -------------------------
    // These run on the JVM, so the copy/move/delete logic is exercised by CI
    // rather than trusted. Uses the system temp dir, not the device file system.

    private fun tempDir(): java.io.File = kotlin.io.path.createTempDirectory().toFile()

    @Test
    fun `copy duplicates a file and leaves the original`() {
        val root = tempDir()
        val src = java.io.File(root, "a.txt").apply { writeText("halo") }
        val target = java.io.File(root, "tujuan").apply { mkdirs() }
        val result = FileOps.copy(src.absolutePath, target.absolutePath)
        assertTrue(result.isSuccess)
        assertEquals("halo", java.io.File(target, "a.txt").readText())
        assertTrue("source must survive a copy", src.exists())
    }

    @Test
    fun `copy does not overwrite an existing name`() {
        val root = tempDir()
        val src = java.io.File(root, "a.txt").apply { writeText("baru") }
        val target = java.io.File(root, "tujuan").apply { mkdirs() }
        java.io.File(target, "a.txt").writeText("lama")
        FileOps.copy(src.absolutePath, target.absolutePath)
        assertEquals("lama", java.io.File(target, "a.txt").readText())
        assertEquals("baru", java.io.File(target, "a (1).txt").readText())
    }

    @Test
    fun `copying a folder into itself is refused`() {
        val root = tempDir()
        val folder = java.io.File(root, "dok").apply { mkdirs() }
        val result = FileOps.copy(folder.absolutePath, folder.absolutePath)
        assertTrue("must fail rather than recurse forever", result.isFailure)
        assertTrue(result.exceptionOrNull()!!.message!!.contains("dirinya sendiri"))
    }

    @Test
    fun `move removes the source`() {
        val root = tempDir()
        val src = java.io.File(root, "a.txt").apply { writeText("x") }
        val target = java.io.File(root, "tujuan").apply { mkdirs() }
        assertTrue(FileOps.move(src.absolutePath, target.absolutePath).isSuccess)
        assertTrue(!src.exists())
        assertTrue(java.io.File(target, "a.txt").exists())
    }

    @Test
    fun `delete removes a folder with contents`() {
        val root = tempDir()
        val folder = java.io.File(root, "dok").apply { mkdirs() }
        java.io.File(folder, "dalam.txt").writeText("x")
        val entry = FileEntry(folder.absolutePath, "dok", true, 0, 0, false, true)
        assertTrue(FileOps.delete(entry).isSuccess)
        assertTrue(!folder.exists())
    }

    @Test
    fun `rename rejects an existing name and a bad character`() {
        val root = tempDir()
        val a = java.io.File(root, "a.txt").apply { writeText("x") }
        java.io.File(root, "b.txt").writeText("y")
        val entry = FileEntry(a.absolutePath, "a.txt", false, 1, 0, false, true)
        assertTrue(FileOps.rename(entry, "b.txt").isFailure)
        assertTrue(FileOps.rename(entry, "a/b.txt").isFailure)
        assertTrue(FileOps.rename(entry, "c.txt").isSuccess)
        assertTrue(java.io.File(root, "c.txt").exists())
    }

    @Test
    fun `create folder respects existing names`() {
        val root = tempDir()
        assertTrue(FileOps.createFolder(root.absolutePath, "baru").isSuccess)
        assertTrue(FileOps.createFolder(root.absolutePath, "baru").isFailure)
        assertTrue(FileOps.createFolder(root.absolutePath, "a/b").isFailure)
    }

    @Test
    fun `measure counts nested bytes`() {
        val root = tempDir()
        val folder = java.io.File(root, "dok").apply { mkdirs() }
        java.io.File(folder, "a.txt").writeText("12345")
        java.io.File(folder, "b.txt").writeText("123")
        val entry = FileEntry(folder.absolutePath, "dok", true, 0, 0, false, true)
        val (bytes, files) = FileOps.measure(entry)
        assertEquals(8L, bytes)
        assertEquals(2, files)
    }

    @Test
    fun `saf paths are recognised as paths not files`() {
        assertTrue(Storage.isTreePath("content://com.android.externalstorage.documents/tree/primary"))
        assertTrue(!Storage.isTreePath("/sdcard/Download"))
    }
}
