package net.pure.manager.fs

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class SearchTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun file(dir: File, name: String, bytes: Int = 3): File {
        val f = File(dir, name)
        f.parentFile?.mkdirs()
        f.writeBytes(ByteArray(bytes))
        return f
    }

    @Test
    fun finds_by_partial_name_regardless_of_case() {
        val root = tmp.root
        file(root, "Laporan Tahunan.pdf")
        file(root, "catatan.txt")

        val hits = Search.find(listOf(root.absolutePath), "lapo")

        assertEquals(1, hits.size)
        assertEquals("Laporan Tahunan.pdf", hits[0].name)
    }

    @Test
    fun searches_inside_subfolders_not_only_the_top() {
        val root = tmp.root
        val deep = File(root, "a/b/c").apply { mkdirs() }
        file(deep, "dokumen-penting.docx")

        val hits = Search.find(listOf(root.absolutePath), "penting")

        assertEquals(1, hits.size)
        assertTrue(hits[0].path.endsWith("dokumen-penting.docx"))
    }

    @Test
    fun an_empty_query_returns_nothing_instead_of_everything() {
        val root = tmp.root
        file(root, "apa-saja.txt")

        // Searching for nothing would otherwise list the whole device and take a
        // minute to do it.
        assertEquals(emptyList<FileEntry>(), Search.find(listOf(root.absolutePath), "   "))
    }

    @Test
    fun hidden_files_are_skipped_unless_asked_for() {
        val root = tmp.root
        file(root, ".rahasia.txt")
        file(root, "terbuka.txt")

        assertEquals(1, Search.find(listOf(root.absolutePath), "txt").size)
        assertEquals(2, Search.find(listOf(root.absolutePath), "txt", showHidden = true).size)
    }

    @Test
    fun cancellation_stops_the_walk() {
        val root = tmp.root
        repeat(30) { i -> file(File(root, "dir$i").apply { mkdirs() }, "berkas$i.txt") }

        // Cancelled before the first directory: nothing may be returned even
        // though matches exist, otherwise closing the sheet keeps the walk alive.
        val hits = Search.find(listOf(root.absolutePath), "berkas", cancelled = { true })

        assertEquals(emptyList<FileEntry>(), hits)
    }

    @Test
    fun results_are_capped_and_sorted_by_name() {
        val root = tmp.root
        repeat(10) { i -> file(root, "sama-$i.txt") }

        val hits = Search.find(listOf(root.absolutePath), "sama", limit = 4)

        assertEquals(4, hits.size)
        assertEquals(hits.map { it.name }.sorted(), hits.map { it.name })
    }

    @Test
    fun the_depth_limit_stops_a_runaway_tree() {
        val root = tmp.root
        var deep = root
        repeat(Search.MAX_DEPTH + 2) { i ->
            deep = File(deep, "l$i").apply { mkdirs() }
        }
        file(deep, "terlalu-dalam.txt")

        val hits = Search.find(listOf(root.absolutePath), "terlalu")

        // Deeper than the limit, so it must not be found: a walk without a bound
        // is how a file manager freezes on a folder of node_modules.
        assertEquals(0, hits.size)
    }

    @Test
    fun a_folder_named_data_outside_android_is_still_searched() {
        val root = tmp.root
        val mine = File(root, "Documents/data").apply { mkdirs() }
        file(mine, "catatan-kerja.txt")

        val hits = Search.find(listOf(root.absolutePath), "kerja")

        assertEquals(1, hits.size)
    }

    @Test
    fun android_data_is_not_crawled() {
        val root = tmp.root
        // The real layout is /storage/emulated/0/Android/data, so the fixture has
        // to be an absolute path ending in /Android/data for the skip rule to see
        // what it sees on a phone.
        val volume = File(root, "storage").apply { mkdirs() }
        val private = File(volume, "Android/data/com.contoh/files").apply { mkdirs() }
        file(private, "database-rahasia.txt")

        val hits = Search.find(listOf(volume.absolutePath), "database")

        // Android 11+ refuses to list this without a grant; walking it produces
        // exceptions and no results, so it is skipped by design.
        assertEquals(0, hits.size)
    }

    @Test
    fun a_missing_root_is_skipped_not_thrown() {
        val hits = Search.find(listOf("/tidak-ada-folder-ini"), "apa")
        assertEquals(emptyList<FileEntry>(), hits)
    }

    @Test
    fun every_hit_is_a_file_and_readable_metadata_is_filled_in() {
        val root = tmp.root
        val f = file(root, "ukuran.bin", bytes = 12)

        val hits = Search.find(listOf(root.absolutePath), "ukuran")

        assertEquals(1, hits.size)
        assertFalse(hits[0].isDirectory)
        assertEquals(12L, hits[0].sizeBytes)
        assertEquals(f.absolutePath, hits[0].path)
        assertTrue(hits[0].lastModified > 0)
    }

    @Test
    fun files_attributes_helper_is_not_needed_for_a_plain_walk() {
        // Guards against someone "optimising" the walk into a Files.walk that
        // throws UncheckedIOException on the first unreadable folder -- which is
        // exactly what every Android device has in /storage/emulated/0/Android.
        assertTrue(Files.exists(tmp.root.toPath()))
        assertFalse(Search.isSkipped(tmp.root))
        val volume = File(tmp.root, "volume").apply { mkdirs() }
        assertTrue(Search.isSkipped(File(volume, "Android/data").apply { mkdirs() }))
    }
}
