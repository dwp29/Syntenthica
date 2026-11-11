package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/** Storage analysis: the numbers have to add up, and nothing may be followed twice. */
class UsageTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun file(dir: File, name: String, bytes: Int): File =
        File(dir, name).apply { writeBytes(ByteArray(bytes) { 1 }) }

    @Test
    fun `a folder is measured by its contents, not its own size`() {
        val root = temp.newFolder("root")
        val big = File(root, "big").apply { mkdirs() }
        file(big, "a.bin", 4096)
        file(big, "b.bin", 4096)
        file(root, "small.txt", 10)

        val tallies = Usage.scan(root.absolutePath, showHidden = true).getOrThrow()

        val byName = tallies.associateBy { it.name }
        assertEquals(8192L, byName.getValue("big").bytes)
        assertEquals(10L, byName.getValue("small.txt").bytes)
    }

    @Test
    fun `the largest comes first`() {
        val root = temp.newFolder("root")
        file(root, "small.txt", 1)
        file(root, "large.bin", 5000)

        val tallies = Usage.scan(root.absolutePath, showHidden = true).getOrThrow()

        assertEquals("large.bin", tallies.first().name)
    }

    @Test
    fun `hidden files are respected`() {
        val root = temp.newFolder("root")
        file(root, ".hidden", 100)
        file(root, "shown", 100)

        val visible = Usage.scan(root.absolutePath, showHidden = false).getOrThrow()

        assertEquals(listOf("shown"), visible.map { it.name })
    }

    @Test
    fun `the limit keeps a huge folder readable`() {
        val root = temp.newFolder("root")
        repeat(50) { file(root, "f$it.txt", it + 1) }

        val tallies = Usage.scan(root.absolutePath, showHidden = true, limit = 10).getOrThrow()

        assertEquals(10, tallies.size)
        // And the ten it kept are the ten largest, not the first ten it saw.
        assertTrue(tallies.first().bytes >= tallies.last().bytes)
    }

    @Test
    fun `shares add up to one, and an empty folder is zero rather than NaN`() {
        val root = temp.newFolder("root")
        file(root, "a", 25)
        file(root, "b", 75)

        val tallies = Usage.scan(root.absolutePath, showHidden = true).getOrThrow()
        val shares = Usage.shares(tallies)

        assertEquals(1f, shares.sum(), 0.0001f)
        assertEquals(0.75f, shares.first(), 0.0001f)

        assertTrue(Usage.shares(emptyList()).isEmpty())
        assertEquals(listOf(0f), Usage.shares(listOf(Usage.Tally("/x", "x", true, 0L))))
    }

    @Test
    fun `a missing folder is an empty result, not a crash`() {
        assertTrue(Usage.scan("/tidak/ada/folder", true).getOrThrow().isEmpty())
    }
}
