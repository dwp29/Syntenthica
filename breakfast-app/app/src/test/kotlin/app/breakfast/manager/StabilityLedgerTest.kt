package app.breakfast.manager

import app.breakfast.manager.data.StabilityLedger
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StabilityLedgerTest {

    @Test
    fun `worked examples from the specification`() {
        assertEquals(100, StabilityLedger.score(0, 99.0))
        assertEquals(70, StabilityLedger.score(3, 1.0))
        assertEquals(97, StabilityLedger.score(3, 10.0))
        assertEquals(80, StabilityLedger.score(10, 5.0))
        assertEquals(0, StabilityLedger.score(23, 2.0))
    }

    @Test
    fun `uptime under one hour is not rewarded`() {
        assertEquals(StabilityLedger.score(10, 1.0), StabilityLedger.score(10, 0.2))
        assertEquals(StabilityLedger.score(10, 1.0), StabilityLedger.score(10, 0.0))
    }

    @Test
    fun `score clamps at both ends`() {
        assertEquals(0, StabilityLedger.score(1_000, 1.0))
        assertEquals(100, StabilityLedger.score(0, 1_000.0))
    }

    @Test
    fun `bands follow the documented thresholds`() {
        assertEquals(StabilityLedger.Band.STABLE, StabilityLedger.Band.of(90))
        assertEquals(StabilityLedger.Band.NORMAL, StabilityLedger.Band.of(89))
        assertEquals(StabilityLedger.Band.NORMAL, StabilityLedger.Band.of(70))
        assertEquals(StabilityLedger.Band.ATTENTION, StabilityLedger.Band.of(69))
        assertEquals(StabilityLedger.Band.ATTENTION, StabilityLedger.Band.of(40))
        assertEquals(StabilityLedger.Band.TROUBLE, StabilityLedger.Band.of(39))
    }

    @Test
    fun `counts real events`() {
        assertEquals(StabilityLedger.Event.OOPS, StabilityLedger.classify("Internal error: Oops - BUG: 96000004"))
        assertEquals(StabilityLedger.Event.OOPS, StabilityLedger.classify("Unable to handle kernel paging request"))
        assertEquals(StabilityLedger.Event.BUG, StabilityLedger.classify("kernel BUG at mm/vmscan.c:1234!"))
        assertEquals(StabilityLedger.Event.WARN, StabilityLedger.classify("WARNING: CPU: 3 PID: 99 at kernel/sched/core.c:1"))
    }

    @Test
    fun `ignores recoverable noise`() {
        assertNull(StabilityLedger.classify("Call trace:"))
        assertNull(StabilityLedger.classify("---[ end trace 1a2b3c ]---"))
        assertNull(StabilityLedger.classify("i2c_geni f9920000.i2c: i2c error -107"))
    }

    @Test
    fun `unreadable dmesg never invents a score`() {
        val score = StabilityLedger.unreadable()
        assertFalse(score.readable)
    }

    @Test
    fun `burden weights sum per event`() {
        val occurrences = listOf(
            StabilityLedger.Occurrence(StabilityLedger.Event.OOPS, "gpu"),
            StabilityLedger.Occurrence(StabilityLedger.Event.OOPS, "gpu"),
            StabilityLedger.Occurrence(StabilityLedger.Event.WARN, "i2c"),
        )
        assertEquals(23, StabilityLedger.burden(occurrences))
        assertEquals(listOf("gpu" to 2, "i2c" to 1), StabilityLedger.perTag(occurrences))
        assertTrue(StabilityLedger.compute(occurrences, 2.0).readable)
    }
}
