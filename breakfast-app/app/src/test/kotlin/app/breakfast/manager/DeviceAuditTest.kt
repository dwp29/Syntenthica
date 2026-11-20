package app.breakfast.manager

import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.DeviceAudit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private class FakeFs(
    private val nodes: Map<String, Triple<String, Boolean, Boolean>>, // value, readable, writable
) : AuditRunner.Fs {
    override fun exists(path: String) = nodes.containsKey(path)
    override fun readable(path: String) = nodes[path]?.second ?: false
    override fun writable(path: String) = nodes[path]?.third ?: false
    override fun read(path: String) = nodes[path]?.takeIf { it.second }?.first
    override fun permissions(path: String) = if (nodes.containsKey(path)) "-rw-r--r-- root:root" else null
}

class DeviceAuditTest {

    private val specs = listOf(
        "ZRAM" to listOf("/sys/block/zram0/mem_limit", "/sys/block/zram0/disksize"),
        "Thermal" to listOf("/sys/class/thermal/thermal_zone0/trip_point_0_temp"),
        "Governor attr" to listOf("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us"),
    )
    private val readOnly = setOf("/sys/class/thermal/thermal_zone0/trip_point_0_temp")

    @Test
    fun `absent node is recorded as a result, not skipped`() {
        val fs = FakeFs(mapOf("/sys/block/zram0/mem_limit" to Triple("0", true, true)))
        val report = AuditRunner.run(fs, "4.14.357-test", 1_000L, specs, readOnly)
        assertEquals(4, report.nodes.size)
        assertEquals(1, report.supported)
        assertEquals(3, report.absent)
        assertTrue(report.nodes.any { it.path.endsWith("disksize") && it.support == DeviceAudit.Support.ABSENT })
    }

    @Test
    fun `readable but unwritable node is read-only, never absent`() {
        // This is the bug the device screenshots exposed: a non-root manager can
        // read up_rate_limit_us but cannot write it, and the audit reported
        // "0 didukung" while the node was plainly there.
        val fs = FakeFs(mapOf("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us" to Triple("0", true, false)))
        val node = AuditRunner.run(fs, "k", 0L, specs, readOnly).nodes
            .first { it.path.endsWith("up_rate_limit_us") }
        assertEquals(DeviceAudit.Support.READ_ONLY, node.support)
        assertEquals("0", node.value)
    }

    @Test
    fun `read-only node found without root blames root, not the kernel`() {
        val fs = FakeFs(mapOf("/sys/block/zram0/mem_limit" to Triple("0", true, false)))
        val withoutRoot = AuditRunner.run(fs, "k", 0L, specs, readOnly, hasRoot = false)
            .nodes.first { it.path.endsWith("mem_limit") }
        val withRoot = AuditRunner.run(fs, "k", 0L, specs, readOnly, hasRoot = true)
            .nodes.first { it.path.endsWith("mem_limit") }
        assertEquals("perlu root untuk menulis", withoutRoot.note)
        assertEquals("kernel menyediakan tapi menolak penulisan", withRoot.note)
    }

    @Test
    fun `summary says when it ran without root`() {
        val report = DeviceAudit.Report("k", 0L, emptyList())
        assertEquals("Audit selesai: 0 didukung, 0 baca-saja, 0 tidak ada.", AuditRunner.describe(report, hasRoot = true))
        assertTrue(AuditRunner.describe(report, hasRoot = false).contains("tanpa root"))
    }

    @Test
    fun `writable node is supported and its value is kept`() {
        val fs = FakeFs(mapOf("/sys/block/zram0/mem_limit" to Triple("2048\n", true, true)))
        val node = AuditRunner.run(fs, "k", 0L, specs, readOnly).nodes.first { it.support == DeviceAudit.Support.SUPPORTED }
        assertEquals("2048", node.value)
        assertEquals("mem_limit", node.name)
    }

    @Test
    fun `read-only node is not offered as tunable`() {
        val fs = FakeFs(mapOf("/sys/class/thermal/thermal_zone0/trip_point_0_temp" to Triple("85000", true, true)))
        val report = AuditRunner.run(fs, "k", 0L, specs, readOnly)
        val thermal = report.nodes.first { it.path.contains("thermal_zone0") }
        assertEquals(DeviceAudit.Support.READ_ONLY, thermal.support)
        assertFalse(report.supportedValues().containsKey(thermal.path))
    }

    @Test
    fun `writable but not readable is unreadable, with its permissions shown`() {
        val fs = FakeFs(mapOf("/sys/block/zram0/mem_limit" to Triple("0", false, true)))
        val node = AuditRunner.run(fs, "k", 0L, specs, readOnly).nodes.first { it.path.endsWith("mem_limit") }
        // The file exists; we simply may not read it. Calling that "absent" is
        // what made LAB and TUNING disagree about the same node.
        assertEquals(DeviceAudit.Support.UNREADABLE, node.support)
        assertTrue(node.note!!.contains("tidak bisa dibaca"))
        assertFalse(node.readable)
    }

    @Test
    fun `summary counts all three groups`() {
        val fs = FakeFs(
            mapOf(
                "/sys/block/zram0/mem_limit" to Triple("0", true, true),
                "/sys/class/thermal/thermal_zone0/trip_point_0_temp" to Triple("85000", true, true),
            )
        )
        val report = AuditRunner.run(fs, "k", 0L, specs, readOnly)
        assertEquals("Audit selesai: 1 didukung, 1 baca-saja, 2 tidak ada.", report.summary())
    }

    @Test
    fun `cooldown is thirty seconds from the last audit`() {
        assertEquals(0L, DeviceAudit.cooldownRemainingMs(null, 100_000L))
        assertEquals(30_000L, DeviceAudit.cooldownRemainingMs(100_000L, 100_000L))
        assertEquals(10_000L, DeviceAudit.cooldownRemainingMs(100_000L, 120_000L))
        assertEquals(0L, DeviceAudit.cooldownRemainingMs(100_000L, 130_000L))
        assertEquals(0L, DeviceAudit.cooldownRemainingMs(100_000L, 999_000L))
    }

    @Test
    fun `clock going backwards does not unlock the cooldown`() {
        assertEquals(DeviceAudit.COOLDOWN_MS, DeviceAudit.cooldownRemainingMs(100_000L, 50_000L))
    }

    @Test
    fun `kernel change discards the old report instead of merging`() {
        val old = DeviceAudit.Report("4.14.357-old", 1_000L, emptyList())
        val fresh = DeviceAudit.Report("4.14.357-new", 5_000L, emptyList())
        val resolved = DeviceAudit.resolve(old, fresh, "4.14.357-new", 6_000L)
        assertTrue(resolved is DeviceAudit.Resolution.Fresh)
        assertEquals("4.14.357-new", (resolved as DeviceAudit.Resolution.Fresh).report.kernelRelease)
    }

    @Test
    fun `same kernel keeps the old report when the new audit fails`() {
        val old = DeviceAudit.Report("4.14.357-a", 1_000L, emptyList())
        val resolved = DeviceAudit.resolve(old, null, "4.14.357-a", 61_000L, "su ditolak")
        assertTrue(resolved is DeviceAudit.Resolution.KeptStale)
        assertEquals(60_000L, (resolved as DeviceAudit.Resolution.KeptStale).ageMs)
    }

    @Test
    fun `kernel change with a failed audit yields nothing usable`() {
        val old = DeviceAudit.Report("4.14.357-old", 1_000L, emptyList())
        val resolved = DeviceAudit.resolve(old, null, "4.14.357-new", 2_000L)
        assertTrue(resolved is DeviceAudit.Resolution.None)
        assertTrue((resolved as DeviceAudit.Resolution.None).reason.contains("uname -r berubah"))
    }

    @Test
    fun `no previous report and a failed audit says so`() {
        val resolved = DeviceAudit.resolve(null, null, "k", 0L, "izin ditolak")
        assertTrue(resolved is DeviceAudit.Resolution.None)
        assertEquals("izin ditolak", (resolved as DeviceAudit.Resolution.None).reason)
    }

    @Test
    fun `age labels are readable`() {
        assertEquals("45 detik", DeviceAudit.ageLabel(45_000L))
        assertEquals("5 menit", DeviceAudit.ageLabel(5 * 60_000L))
        assertEquals("2 jam", DeviceAudit.ageLabel(2 * 3_600_000L))
        assertEquals("3 hari", DeviceAudit.ageLabel(3 * 86_400_000L))
    }

    @Test
    fun `node paths map onto whitelist keys`() {
        assertEquals("zram_mem_limit", DeviceAudit.nodeToKey("/sys/block/zram0/mem_limit"))
        assertEquals("schedutil_up_rate", DeviceAudit.nodeToKey("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us"))
    }

    @Test
    fun `every audited whitelist path exists in the whitelist`() {
        for ((_, paths) in DeviceAudit.NODE_SPECS) {
            for (path in paths) {
                val key = DeviceAudit.nodeToKey(path)
                if (key != path) {
                    assertTrue("$path maps to unknown key $key", app.breakfast.manager.data.TuningWhitelist.byKey(key) != null)
                }
            }
        }
    }
}
