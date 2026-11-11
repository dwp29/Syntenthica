package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.concurrent.atomic.AtomicInteger

/**
 * The copy engine, tested where it can hurt.
 *
 * Each of these corresponds to something a file manager gets wrong in public: a
 * folder copied into itself until the disk fills, a cancel that leaves a half-written
 * file looking like a real one, and a progress bar that reaches 100% before the work
 * is finished.
 */
class CopyEngineTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun file(dir: File, name: String, bytes: Int): File {
        val f = File(dir, name)
        f.writeBytes(ByteArray(bytes) { 7 })
        return f
    }

    // ------------------------------------------------------------------ copy

    @Test
    fun `a file is copied and the original is untouched`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        val original = file(src, "a.txt", 1024)

        val results = CopyEngine.copy(listOf(original.absolutePath), dst.absolutePath, { false }) {}

        assertTrue(results.single().isSuccess)
        assertTrue(File(dst, "a.txt").exists())
        assertTrue(original.exists())
        assertEquals(original.length(), File(dst, "a.txt").length())
    }

    @Test
    fun `an existing name gets a suffix instead of being overwritten`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        val original = file(src, "a.txt", 10)
        file(dst, "a.txt", 5)

        CopyEngine.copy(listOf(original.absolutePath), dst.absolutePath, { false }) {}

        // The pre-existing file must survive: a copy that silently replaces is the
        // worst thing this app could do.
        assertEquals(5L, File(dst, "a.txt").length())
        assertTrue(File(dst, "a (1).txt").exists())
    }

    @Test
    fun `a folder is copied with its tree`() {
        val src = temp.newFolder("src")
        val nested = File(src, "inner").apply { mkdirs() }
        file(src, "top.txt", 8)
        file(nested, "deep.txt", 8)
        val dst = temp.newFolder("dst")

        CopyEngine.copy(listOf(src.absolutePath), dst.absolutePath, { false }) {}

        assertTrue(File(dst, "src/top.txt").exists())
        assertTrue(File(dst, "src/inner/deep.txt").exists())
    }

    @Test
    fun `a folder cannot be copied into itself`() {
        val src = temp.newFolder("src")
        file(src, "a.txt", 8)

        val result = CopyEngine.copy(listOf(src.absolutePath), src.absolutePath, { false }) {}

        assertTrue(result.single().isFailure)
        assertTrue(result.single().exceptionOrNull()!!.message!!.contains("dirinya sendiri"))
    }

    // -------------------------------------------------------------- progress

    @Test
    fun `progress reaches one whole and never overshoots`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        file(src, "a.bin", 2 * 1024 * 1024) // 2 MB = four chunks of 512 KB

        val seen = mutableListOf<CopyEngine.Progress>()
        CopyEngine.copy(listOf(File(src, "a.bin").absolutePath), dst.absolutePath, { false }) {
            seen += it
        }

        assertTrue("nothing was reported", seen.isNotEmpty())
        assertTrue("progress went past the total", seen.all { it.bytesDone <= it.bytesTotal })
        assertEquals(1f, seen.last().fraction, 0.0001f)
        assertEquals(seen.last().bytesTotal, seen.last().bytesDone)
    }

    @Test
    fun `progress of an empty folder is one, not NaN`() {
        val src = temp.newFolder("empty")
        val dst = temp.newFolder("dst")

        val seen = mutableListOf<CopyEngine.Progress>()
        CopyEngine.copy(listOf(src.absolutePath), dst.absolutePath, { false }) { seen += it }

        // A zero total divides to NaN, and a NaN progress bar draws as nothing at
        // all -- indistinguishable from a frozen app.
        assertFalse(seen.any { it.fraction.isNaN() })
    }

    // ----------------------------------------------------------- cancellation

    @Test
    fun `cancelling stops the copy and leaves no half-written file`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        file(src, "big.bin", 4 * 1024 * 1024)

        // Ask to cancel after the first report, which arrives on the first chunk.
        val calls = AtomicInteger(0)
        val results = CopyEngine.copy(
            listOf(File(src, "big.bin").absolutePath),
            dst.absolutePath,
            cancelled = { calls.incrementAndGet() > 1 },
        ) {}

        assertTrue(results.single().isFailure)
        assertTrue(results.single().exceptionOrNull() is CopyEngine.Cancelled)
        // Debris is worse than nothing: a partial file looks like a real file.
        assertEquals(0, dst.listFiles()?.size ?: 0)
    }

    @Test
    fun `a cancelled job reports every remaining source as cancelled`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        file(src, "a.txt", 8)
        file(src, "b.txt", 8)

        val results = CopyEngine.copy(
            listOf(File(src, "a.txt").absolutePath, File(src, "b.txt").absolutePath),
            dst.absolutePath,
            cancelled = { true },
        ) {}

        assertEquals(2, results.size)
        assertTrue(results.all { it.isFailure })
    }

    // ------------------------------------------------------------------ move

    @Test
    fun `a move leaves nothing behind at the source`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        val original = file(src, "a.txt", 100)

        val results = CopyEngine.move(listOf(original.absolutePath), dst.absolutePath, { false }) {}

        assertTrue(results.single().isSuccess)
        assertTrue(File(dst, "a.txt").exists())
        assertFalse(original.exists())
    }

    @Test
    fun `a move into a folder that does not exist fails per source, not silently`() {
        val src = temp.newFolder("src")
        val original = file(src, "a.txt", 10)

        val results = CopyEngine.move(
            listOf(original.absolutePath), File(src, "tidak-ada").absolutePath, { false },
        ) {}

        assertTrue(results.single().isFailure)
        assertTrue(original.exists())
    }

    // ------------------------------------------------------------- edge cases

    @Test
    fun `a missing source fails without touching the destination`() {
        val dst = temp.newFolder("dst")

        val results = CopyEngine.copy(listOf("/tidak/ada/berkas.txt"), dst.absolutePath, { false }) {}

        assertTrue(results.single().isFailure)
        assertEquals(0, dst.listFiles()?.size ?: 0)
    }

    @Test
    fun `one failure does not stop the rest of a batch`() {
        val src = temp.newFolder("src")
        val dst = temp.newFolder("dst")
        val good = file(src, "good.txt", 8)

        val results = CopyEngine.copy(
            listOf("/tidak/ada", good.absolutePath), dst.absolutePath, { false },
        ) {}

        assertEquals(2, results.size)
        assertTrue(results[0].isFailure)
        assertTrue(results[1].isSuccess)
        assertTrue(File(dst, "good.txt").exists())
    }
}
