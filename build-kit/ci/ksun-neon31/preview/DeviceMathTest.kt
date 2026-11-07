package com.rifsxd.ksunext.ui.device

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DeviceMathTest {
    @Test fun batteryPercentRejectsMissingAndOutOfRange() {
        assertNull(checkedPercent(null, 100))
        assertNull(checkedPercent(1, 0))
        assertNull(checkedPercent(-1, 100))
        assertNull(checkedPercent(101, 100))
        assertEquals(50, checkedPercent(1, 2))
        assertEquals(100, checkedPercent(100, 100))
        assertEquals(100, checkedPercent(Int.MAX_VALUE, Int.MAX_VALUE))
    }

    @Test fun frequencyNeverInventsAValue() {
        assertNull(parseCpuFrequencyKHz(null))
        assertNull(parseCpuFrequencyKHz("not a number"))
        assertNull(parseCpuFrequencyKHz("-1"))
        assertNull(parseCpuFrequencyKHz("0"))
        assertNull(parseCpuFrequencyKHz("10000001"))
        assertEquals(1_800_000L, parseCpuFrequencyKHz(" 1800000\n"))
    }

    @Test fun gpuLoadZramAndPsiRejectUnavailableOrMalformedData() {
        assertNull(parseGpuFrequencyHz(null))
        assertNull(parseGpuFrequencyHz("0"))
        assertNull(parseGpuFrequencyHz("10000000001"))
        assertEquals(305_000_000L, parseGpuFrequencyHz("305000000\n"))
        assertEquals(listOf(0.2, 0.5, 1.25), parseLoadAverages("0.20 0.50 1.25 2/100 1"))
        for (bad in listOf("", "0.1 0.2", "NaN 0.2 0.3", "-1 0 0")) assertNull(parseLoadAverages(bad))
        assertEquals(1000L to 250L, parseZramData("1000 250 500 0 0"))
        assertEquals(0L to 0L, parseZramData("0 0"))
        assertNull(parseZramData("-1 10"))
        assertNull(parseZramData("garbage"))
        assertEquals(0.25, parsePressureAvg10("some avg10=0.25 avg60=1.00 total=12")!!, 0.0001)
        assertNull(parsePressureAvg10("full avg10=0.25"))
        assertNull(parsePressureAvg10("some avg10=101"))
        assertNull(parsePressureAvg10("some avg10=NaN"))
        assertEquals(0L, parseNonNegativeBytes("0"))
        assertNull(parseNonNegativeBytes("-1"))
        assertEquals("msm-adreno-tz", parseGovernor("msm-adreno-tz\n"))
        assertNull(parseGovernor("not a valid governor"))
    }

    @Test fun onlyExplicitlySelectedSummarySectionsAreCopied() {
        val sections = listOf(
            SummarySection("device", "Device", listOf("Model" to "Example", "Codename" to "sample")),
            SummarySection("system", "System", listOf("Kernel" to "4.14")),
        )
        assertEquals("", renderSelectedSummary("Device Check", sections, emptySet()))
        val device = renderSelectedSummary("Device Check", sections, setOf("device"))
        assertEquals("Device Check\n\nDevice\nModel: Example\nCodename: sample", device)
        assertEquals(false, device.contains("Kernel"))
        val sanitized = renderSelectedSummary("Device Check", listOf(
            SummarySection("x", "Hello\u202E", listOf("Name" to "one\ntwo"))), setOf("x"))
        assertEquals(false, sanitized.contains('\u202E'))
        assertEquals(true, sanitized.contains("one two"))
    }

    @Test fun memoryAndTemperatureValidateDriverData() {
        assertNull(checkedUsedBytes(0, 0))
        assertNull(checkedUsedBytes(100, 101))
        assertNull(checkedUsedBytes(100, -1))
        assertEquals(75L, checkedUsedBytes(100, 25))
        assertEquals(36.5, validBatteryTemperatureTenths(365)!!, 0.0001)
        assertNull(validBatteryTemperatureTenths(Int.MIN_VALUE))
        assertNull(validBatteryTemperatureTenths(1501))
    }
}
