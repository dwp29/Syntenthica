package app.breakfast.manager

import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.ClockSource
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.TuningVisibility
import app.breakfast.manager.data.TuningWhitelist
import app.breakfast.manager.data.Uptime
import app.breakfast.manager.ui.PulseReader
import app.breakfast.manager.ui.components.graphBounds
import app.breakfast.manager.ui.components.cpuUsageFromDelta
import app.breakfast.manager.ui.components.graphScale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Every case here is a defect that was visible on a real device screenshot. */
private class FakeClock(private val ms: Long) : ClockSource {
    override fun elapsedRealtimeMs(): Long = ms
}

class DeviceRegressionTest {

    // --- "0 C - Normal" in green ------------------------------------------

    @Test
    fun `zero degrees is not a temperature`() {
        // The reporting device's thermal zone returned 0. It was rendered as
        // "0 C / Normal" in green, which is a fabricated healthy reading.
        assertFalse(PulseReader.isPlausibleTemperature(0f))
        assertFalse(PulseReader.isPlausibleTemperature(0.0f))
    }

    @Test
    fun `real and implausible temperatures are told apart`() {
        assertTrue(PulseReader.isPlausibleTemperature(38f))
        assertTrue(PulseReader.isPlausibleTemperature(72.5f))
        assertFalse(PulseReader.isPlausibleTemperature(-5f))
        assertFalse(PulseReader.isPlausibleTemperature(250f))
        assertFalse(PulseReader.isPlausibleTemperature(null))
    }

    // --- UPTIME showed a dash on a device where it is always available -----

    @Test
    fun `uptime comes from the monotonic clock`() {
        val hours = Uptime.hours(FakeClock(4L * 86_400_000L + 7L * 3_600_000L))
        assertEquals(103.0, hours!!, 0.001)
    }

    @Test
    fun `uptime formats days and hours`() {
        assertEquals("4d 2h", Uptime.format(98.4))
        assertEquals("7j", Uptime.format(7.9))
        assertEquals("—", Uptime.format(null))
    }

    @Test
    fun `a clock reading zero is not uptime either`() {
        assertNull(Uptime.hours(FakeClock(0L)))
    }

    // --- four states, so LAB and TUNING cannot contradict each other -------

    @Test
    fun `exists but unreadable is its own state`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = "-rw-r--r-- root:root",
        )
        assertEquals(DeviceAudit.Support.UNREADABLE, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `verified missing node is absent, not unreadable`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = null,
            // Absence is a claim that needs this evidence; without it the honest
            // answer is UNKNOWN, which the next test covers.
            presence = AuditRunner.Presence.VERIFIED_ABSENT,
        )
        assertEquals(DeviceAudit.Support.ABSENT, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `a node we never saw is never called absent`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = null,
            presence = AuditRunner.Presence.UNKNOWN,
        )
        assertEquals(DeviceAudit.Support.UNKNOWN, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `summary counts the buckets in a way that adds up`() {
        fun node(support: DeviceAudit.Support) = DeviceAudit.Node(
            group = "g", path = "/p/${support.name}", support = support,
            nodePermissions = null, readable = false, value = null,
        )
        val report = DeviceAudit.Report(
            "k", 0L,
            listOf(
                node(DeviceAudit.Support.SUPPORTED),
                node(DeviceAudit.Support.READ_ONLY),
                node(DeviceAudit.Support.UNREADABLE),
                node(DeviceAudit.Support.ABSENT),
            ),
        )
        assertEquals(
            4,
            report.supported + report.readOnly + report.unreadable + report.unknown + report.absent,
        )
        assertTrue(report.summary().contains("1 tidak bisa dibaca"))
        assertEquals(1, report.unreadableNodes().size)
    }

    @Test
    fun `a clean audit does not mention the unreadable bucket`() {
        val report = DeviceAudit.Report("k", 0L, emptyList())
        assertEquals("Audit selesai: 0 didukung, 0 baca-saja, 0 tidak ada.", report.summary())
    }
}

/** Audit's honesty about existence, and the numbers the device got wrong. */
class Run17RegressionTest {

    private fun obs(
        presence: AuditRunner.Presence,
        value: String? = null,
        permissions: String? = null,
    ) = AuditRunner.Observation(
        value = value,
        readable = value != null,
        writable = false,
        permissions = permissions,
        presence = presence,
    )

    @Test
    fun `cannot look is not the same as not there`() {
        // Ten nodes the kernel demonstrably has were reported "tidak ada".
        assertEquals(
            DeviceAudit.Support.UNKNOWN,
            AuditRunner.classify(obs(AuditRunner.Presence.UNKNOWN), declaredReadOnly = false),
        )
        assertEquals(
            DeviceAudit.Support.ABSENT,
            AuditRunner.classify(obs(AuditRunner.Presence.VERIFIED_ABSENT), declaredReadOnly = false),
        )
    }

    @Test
    fun `an unverified node is never counted as absent`() {
        val node = DeviceAudit.Node(
            group = "GPU", path = "/sys/class/kgsl/kgsl-3d0/gpuclk",
            support = DeviceAudit.Support.UNKNOWN, nodePermissions = null,
            readable = false, value = null,
        )
        val report = DeviceAudit.Report("k", 0L, listOf(node))
        assertEquals(0, report.absent)
        assertEquals(1, report.unknown)
        assertFalse(report.isComplete)
        assertTrue(report.summary().contains("1 tidak bisa dipastikan"))
    }

    @Test
    fun `one unreadable file does not make a fake absence`() {
        assertEquals(
            "tidak ada (direktori induk sudah diperiksa)",
            AuditRunner.noteFor(obs(AuditRunner.Presence.VERIFIED_ABSENT), declaredReadOnly = false),
        )
        val unknownNote = AuditRunner.noteFor(obs(AuditRunner.Presence.UNKNOWN), declaredReadOnly = false)!!
        assertTrue(unknownNote.contains("tidak bisa dipastikan"))
    }

    // --- Memory line drew a real 61% as a flat line at the bottom ----------

    @Test
    fun `a flat percentage series keeps its true height`() {
        // Same numbers as the device: 60.6..61.2 out of 100. Before the fix the
        // lowest of these was drawn ON the floor and the highest at the ceiling.
        val series = listOf(60.6f, 60.8f, 61.0f, 61.1f, 61.2f)
        val drawn = graphScale(series.first(), fixedMax = 100f) to
            graphScale(series.last(), fixedMax = 100f)
        assertTrue("memory must sit above the floor, was ${drawn.first}", drawn.first > 0.15f)
        assertTrue("memory must sit below the ceiling", drawn.second < 0.9f)
        assertTrue("61% must be visibly high, not pinned to the bottom", drawn.second > 0.2f)
    }

    @Test
    fun `a percentage series still shows its wobble`() {
        val calm = graphScale(60.6f, fixedMax = 100f)
        val high = graphScale(61.2f, fixedMax = 100f)
        // Visible, but not exaggerated to the full height of the chart.
        assertTrue("difference must be visible", high - calm > 0.0005f)
        assertTrue("difference must not be 100% of the chart", high - calm < 0.3f)
    }

    // --- uptime printed "0j" twenty minutes after boot ---------------------

    @Test
    fun `minutes are not rounded away to zero hours`() {
        // 20 minutes exactly.
        assertEquals("20m", Uptime.format(20.0 / 60.0))
        // 0.33 h is 19.8 minutes; truncation gives 19m, which is right - the point
        // is that it is not "0j".
        assertTrue(Uptime.format(0.33).endsWith("m"))
        assertEquals("2j", Uptime.format(2.5))
        assertEquals("1d 3h", Uptime.format(27.7))
    }

    // --- CPU Load: a delta too small to measure is not a measurement -------

    @Test
    fun `a stat delta below one tick window is rejected`() {
        assertNull(cpuUsageFromDelta(totalDelta = 4L, idleDelta = 1L))
        assertEquals(0.5f, cpuUsageFromDelta(totalDelta = 400L, idleDelta = 200L)!!, 0.001f)
    }
}


class TuningVisibilityTest {

    private fun node(keyPath: String, support: DeviceAudit.Support, value: String? = null) =
        DeviceAudit.Node(
            group = "g", path = keyPath, support = support,
            nodePermissions = null, readable = value != null, value = value,
        )

    private fun report(vararg nodes: DeviceAudit.Node) = DeviceAudit.Report("k", 0L, nodes.toList())

    @Test
    fun `a parameter with no row of its own is listed, not hidden`() {
        // The device bug: iowait_boost_enable exists in the kernel, but the screen
        // only draws schedutil nodes it can use, so the hardcoded dedupe list hid
        // it from both the group and the "tidak tersedia" list.
        val r = report(
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
                DeviceAudit.Support.READ_ONLY, "0"),
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/iowait_boost_enable",
                DeviceAudit.Support.UNKNOWN),
        )
        val missing = TuningVisibility.missingKeys(r).map { it.key }
        assertTrue("iowait_boost_enable must be listed", "schedutil_iowait" in missing)
    }

    @Test
    fun `a rendered parameter is not repeated in the missing list`() {
        val r = report(
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
                DeviceAudit.Support.READ_ONLY, "0"),
        )
        val missing = TuningVisibility.missingKeys(r).map { it.key }
        assertFalse("up_rate is drawn in its group", "schedutil_up_rate" in missing)
        // And its sibling, which has no value, must be named.
        assertTrue("down_rate must be listed", "schedutil_down_rate" in missing)
    }

    @Test
    fun `an empty audit lists every parameter rather than pretending they exist`() {
        val missing = TuningVisibility.missingKeys(report())
        assertEquals(TuningWhitelist.PARAMETERS.size, missing.size)
    }
}

/** Thermal zones: a throttle limit is not a thermometer. */
class ThermalZoneTest {

    private fun zone(name: String, celsius: Float) = PulseReader.ThermalZone(name, celsius)

    @Test
    fun `a zone named like a limit is not a sensor`() {
        // This is what produced a flat 81 then a flat 88: the maximum over every
        // zone whose name contains "cpu" picked a throttle threshold, and a
        // threshold does not move when the CPU heats up.
        val zones = listOf(
            zone("cpu-0-usr", 41.2f),
            zone("cpu-0-limit", 88.0f),
            zone("cpu-0-trip-point-0", 95.0f),
            zone("soc-thermal", 39.5f),
        )
        val sensors = zones.filter { PulseReader.isThermometerForTest(it) }
        assertEquals(listOf("cpu-0-usr", "soc-thermal"), sensors.map { it.name })
    }

    @Test
    fun `the hottest real sensor wins, not the hottest number`() {
        val zones = listOf(
            zone("cpu-1-usr", 44.0f),
            zone("cpu-0-usr", 41.0f),
            zone("cpu-0-stage", 99.0f),
        )
        val hottest = zones.filter { PulseReader.isThermometerForTest(it) }.maxByOrNull { it.celsius }
        assertEquals("cpu-1-usr", hottest?.name)
        assertEquals(44.0f, hottest!!.celsius, 0.01f)
    }

    @Test
    fun `an implausible zone is dropped before it can be shown`() {
        assertFalse(PulseReader.isPlausibleTemperature(0f))
        assertFalse(PulseReader.isPlausibleTemperature(999f))
        assertTrue(PulseReader.isPlausibleTemperature(41f))
    }
}
