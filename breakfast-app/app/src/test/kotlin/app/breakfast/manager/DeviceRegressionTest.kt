package app.breakfast.manager

import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.ClockSource
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.Uptime
import app.breakfast.manager.ui.PulseReader
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
    fun `missing node is absent, not unreadable`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = null,
        )
        assertEquals(DeviceAudit.Support.ABSENT, AuditRunner.classify(observation, declaredReadOnly = false))
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
        assertEquals(4, report.supported + report.readOnly + report.unreadable + report.absent)
        assertTrue(report.summary().contains("1 tidak bisa dibaca"))
        assertEquals(1, report.unreadableNodes().size)
    }

    @Test
    fun `a clean audit does not mention the unreadable bucket`() {
        val report = DeviceAudit.Report("k", 0L, emptyList())
        assertEquals("Audit selesai: 0 didukung, 0 baca-saja, 0 tidak ada.", report.summary())
    }
}
