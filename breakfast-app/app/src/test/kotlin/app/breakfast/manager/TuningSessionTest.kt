package app.breakfast.manager

import app.breakfast.manager.data.TuningEngine
import app.breakfast.manager.data.TuningSession
import app.breakfast.manager.data.TuningWhitelist
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private class MemFiles(
    val nodes: MutableMap<String, String>,
    var writable: Boolean = true,
) : TuningEngine.Files {
    val writes = mutableListOf<Pair<String, String>>()
    override fun exists(path: String) = nodes.containsKey(path)
    override fun read(path: String) = nodes[path]
    override fun write(path: String, value: String): Boolean {
        if (!writable) return false
        writes += path to value
        nodes[path] = value
        return true
    }
}

class TuningSessionTest {

    private val mem = "/sys/block/zram0/mem_limit"
    private val comp = "/sys/block/zram0/comp_algorithm"
    private val disk = "/sys/block/zram0/disksize"
    private val sched = "/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us"

    @Test
    fun `plan captures originals before anything is written`() {
        val files = MemFiles(mutableMapOf(mem to "0\n"))
        val plan = TuningSession.plan(files, listOf(TuningSession.Proposal("zram_mem_limit", "1024")))
        assertEquals(1, plan.count)
        assertEquals("0", plan.originals["zram_mem_limit"])
        assertTrue("planning must not write", files.writes.isEmpty())
    }

    @Test
    fun `invalid proposals never reach apply`() {
        val files = MemFiles(mutableMapOf(mem to "0"))
        val plan = TuningSession.plan(
            files,
            listOf(
                TuningSession.Proposal("zram_mem_limit", "999999999999999"),
                TuningSession.Proposal("scaling_max_freq", "2800000"),
                TuningSession.Proposal("zram_mem_limit", "512"),
            ),
        )
        assertEquals(1, plan.count)
        assertEquals(2, plan.rejected.size)
        assertTrue(plan.rejected.any { it.first.key == "scaling_max_freq" })
    }

    @Test
    fun `missing node is rejected rather than planned with an invented original`() {
        val files = MemFiles(mutableMapOf())
        val plan = TuningSession.plan(files, listOf(TuningSession.Proposal("zram_mem_limit", "1024")))
        assertTrue(plan.isEmpty)
        assertEquals(TuningWhitelist.Reason.EMPTY, plan.rejected.single().second)
        assertFalse(plan.originals.containsKey("zram_mem_limit"))
    }

    @Test
    fun `needs-reboot parameter is marked pending, not applied live`() {
        val files = MemFiles(mutableMapOf(disk to "1073741824"))
        val plan = TuningSession.plan(files, listOf(TuningSession.Proposal("zram_disksize", "2147483648")))
        assertEquals(listOf("zram_disksize"), plan.needsReboot)
        val result = TuningSession.apply(files, plan)
        assertTrue(result.applied.single().pendingReboot)
        assertTrue(result.summary().contains("berlaku setelah reboot"))
    }

    @Test
    fun `permission denied is reported per parameter, not rolled up`() {
        val files = MemFiles(mutableMapOf(mem to "0", comp to "lz4 [lz4kd] zstd"), writable = false)
        val plan = TuningSession.plan(
            files,
            listOf(
                TuningSession.Proposal("zram_mem_limit", "1024"),
                TuningSession.Proposal("zram_comp_algorithm", "zstd"),
            ),
        )
        val result = TuningSession.apply(files, plan)
        assertEquals(0, result.applied.size)
        assertEquals(2, result.failed.size)
        assertTrue(result.failed.all { it.outcome == TuningEngine.Outcome.PermissionDenied })
        assertFalse(result.fullyApplied)
    }

    @Test
    fun `reset restores the captured originals`() {
        val files = MemFiles(mutableMapOf(mem to "0", sched to "5000"))
        val plan = TuningSession.plan(
            files,
            listOf(
                TuningSession.Proposal("zram_mem_limit", "2048"),
                TuningSession.Proposal("schedutil_up_rate", "10000"),
            ),
        )
        TuningSession.apply(files, plan)
        assertEquals("2048", files.nodes[mem])
        assertEquals("10000", files.nodes[sched])

        val reset = TuningSession.reset(files, plan)
        assertTrue(reset.fullyApplied)
        assertEquals("0", files.nodes[mem])
        assertEquals("5000", files.nodes[sched])
    }

    @Test
    fun `applied count reflects reality when one write fails midway`() {
        val files = MemFiles(mutableMapOf(mem to "0", comp to "lz4 [lz4kd] zstd"))
        val plan = TuningSession.plan(
            files,
            listOf(
                TuningSession.Proposal("zram_mem_limit", "1024"),
                TuningSession.Proposal("zram_comp_algorithm", "zstd"),
            ),
        )
        files.writable = false
        val result = TuningSession.apply(files, plan)
        assertTrue(result.applied.isEmpty())
        assertEquals(2, result.failed.size)
        assertTrue(result.summary().contains("2 gagal"))
        assertFalse(result.fullyApplied)
    }

    @Test
    fun `empty plan says nothing changed`() {
        val files = MemFiles(mutableMapOf(mem to "0"))
        val result = TuningSession.apply(files, TuningSession.plan(files, emptyList()))
        assertEquals("Tidak ada perubahan.", result.summary())
        assertTrue(files.writes.isEmpty())
    }
}
