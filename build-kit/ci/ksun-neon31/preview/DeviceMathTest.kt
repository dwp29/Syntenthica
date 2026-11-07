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
