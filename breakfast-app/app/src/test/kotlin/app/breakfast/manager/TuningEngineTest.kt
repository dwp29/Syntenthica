package app.breakfast.manager

import app.breakfast.manager.data.TuningEngine
import app.breakfast.manager.data.TuningWhitelist
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** In-memory fake: no device, no root, no filesystem. */
private class FakeFiles(
    private val nodes: MutableMap<String, String>,
    private val writable: Boolean = true,
    private val echo: ((String, String) -> String)? = null,
) : TuningEngine.Files {
    val writes = mutableListOf<Pair<String, String>>()
    override fun exists(path: String) = nodes.containsKey(path)
    override fun read(path: String) = nodes[path]
    override fun write(path: String, value: String): Boolean {
        if (!writable) return false
        writes += path to value
        nodes[path] = echo?.invoke(path, value) ?: value
        return true
    }
}

class TuningEngineTest {

    private val compPath = "/sys/block/zram0/comp_algorithm"
    private val memPath = "/sys/block/zram0/mem_limit"

    @Test
    fun `successful write is read back and confirmed`() {
        val files = FakeFiles(mutableMapOf(compPath to "lz4 [lz4kd] zstd"))
        val result = TuningEngine.apply(files, "zram_comp_algorithm", "zstd")
        assertTrue(result.ok)
        assertEquals(TuningEngine.Outcome.Applied("zstd"), result.outcome)
    }

    @Test
    fun `bracketed read back is not a false mismatch`() {
        // The kernel echoes "[zstd]" but we wrote "zstd".
        val files = FakeFiles(mutableMapOf(compPath to "lz4 lz4kd [zstd]"))
        assertTrue(TuningEngine.apply(files, "zram_comp_algorithm", "zstd").ok)
    }

    @Test
    fun `permission denied is reported as permission denied`() {
        val files = FakeFiles(mutableMapOf(memPath to "0"), writable = false)
        assertEquals(TuningEngine.Outcome.PermissionDenied, TuningEngine.apply(files, "zram_mem_limit", "1024").outcome)
    }

    @Test
    fun `non whitelisted parameter never reaches the filesystem`() {
        val files = FakeFiles(mutableMapOf("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq" to "1800000"))
        val result = TuningEngine.apply(files, "scaling_max_freq", "2800000")
        assertEquals(TuningEngine.Outcome.Rejected(TuningWhitelist.Reason.NOT_WHITELISTED), result.outcome)
        assertTrue(files.writes.isEmpty())
    }

    @Test
    fun `out of range is rejected before writing`() {
        val files = FakeFiles(mutableMapOf(memPath to "0"))
        val result = TuningEngine.apply(files, "zram_mem_limit", "999999999999")
        assertEquals(TuningEngine.Outcome.Rejected(TuningWhitelist.Reason.OUT_OF_RANGE), result.outcome)
        assertTrue(files.writes.isEmpty())
    }

    @Test
    fun `unknown choice is rejected and the offered list is honoured`() {
        assertFalse(TuningWhitelist.validate("zram_comp_algorithm", "lzo", listOf("lz4", "zstd")) is TuningWhitelist.Validation.Ok)
        assertTrue(TuningWhitelist.validate("zram_comp_algorithm", "zstd", listOf("lz4", "zstd")) is TuningWhitelist.Validation.Ok)
    }

    @Test
    fun `vanished node is distinguished from permission denial`() {
        val files = FakeFiles(mutableMapOf())
        assertEquals(TuningEngine.Outcome.Vanished("zram_mem_limit"), TuningEngine.apply(files, "zram_mem_limit", "0").outcome)
    }

    @Test
    fun `silently ignored write is a mismatch not a success`() {
        // Node accepts the write but keeps its old value.
        val files = FakeFiles(mutableMapOf(memPath to "0"), echo = { _, _ -> "0" })
        val result = TuningEngine.apply(files, "zram_mem_limit", "1024")
        assertFalse(result.ok)
        assertTrue(result.outcome is TuningEngine.Outcome.ReadBackMismatch)
    }

    @Test
    fun `disksize is marked needs reboot and applies live`() {
        assertTrue(TuningEngine.needsReboot("zram_disksize"))
        assertFalse(TuningEngine.needsReboot("zram_mem_limit"))
        assertFalse(TuningEngine.needsReboot("schedutil_up_rate"))
    }

    @Test
    fun `every whitelisted parameter is inside a known subtree`() {
        for (parameter in TuningWhitelist.PARAMETERS) {
            assertTrue(
                "unexpected path root: ${parameter.path}",
                parameter.path.startsWith("/sys/block/zram0/") ||
                    parameter.path.startsWith("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/"),
            )
        }
    }

    @Test
    fun `offered list parsing handles the active bracket`() {
        assertEquals(listOf("lz4", "lz4kd", "zstd"), TuningWhitelist.parseOffered("lz4 [lz4kd] zstd"))
        assertEquals("lz4kd", TuningWhitelist.parseActive("lz4 [lz4kd] zstd"))
    }
}
