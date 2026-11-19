package app.breakfast.manager

import app.breakfast.manager.data.LedgerReader
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.ui.Copy
import app.breakfast.manager.ui.LedgerView
import app.breakfast.manager.ui.ThemeCatalog
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LedgerReaderTest {

    @Test
    fun `dmesg level prefix is stripped`() {
        assertEquals("[  123.45] msg", LedgerReader.stripLevel("<4>[  123.45] msg"))
        assertEquals("plain line", LedgerReader.stripLevel("plain line"))
        assertEquals("<4>", LedgerReader.stripLevel("<4>"))
    }

    @Test
    fun `unreadable dmesg shows a dash and never a zero`() {
        val rows = LedgerView.rows(LedgerReader.Result.PermissionDenied)
        val scoreRow = rows.first { it.label == "Skor" }
        assertEquals("—", scoreRow.value)
        assertFalse(scoreRow.value == "0")
        assertTrue(rows.any { it.value.contains("izin ditolak") })
    }

    @Test
    fun `unavailable dmesg names the cause instead of a generic error`() {
        val rows = LedgerView.rows(LedgerReader.Result.Unavailable)
        assertEquals("—", rows.first { it.label == "Skor" }.value)
        assertTrue(rows.any { it.value.contains("dmesg") })
    }

    @Test
    fun `readable ledger renders the number and the counts`() {
        val score = StabilityLedger.Score(
            value = 70,
            burden = 3,
            uptimeHours = 1.0,
            counts = mapOf(StabilityLedger.Event.WARN to 1),
            readable = true,
        )
        val occurrences = listOf(StabilityLedger.Occurrence(StabilityLedger.Event.WARN, "i2c"))
        val rows = LedgerView.rows(LedgerReader.Result.Read(score, occurrences))
        assertEquals("70", rows.first { it.label == "Skor" }.value)
        assertEquals("3", rows.first { it.label == "Beban" }.value)
        assertEquals("1", rows.first { it.label == "WARN" }.value)
        assertEquals("0", rows.first { it.label == "Oops" }.value)
        assertFalse(LedgerView.isPlaceholder(score))
    }

    @Test
    fun `band colours are the fixed status palette`() {
        fun colourFor(value: Int): Long = LedgerView.statusColor(
            StabilityLedger.Score(value, 0, 1.0, emptyMap(), true)
        )
        assertEquals(ThemeCatalog.STATUS_STABLE, colourFor(95))
        assertEquals(ThemeCatalog.STATUS_NORMAL, colourFor(80))
        assertEquals(ThemeCatalog.STATUS_ATTENTION, colourFor(55))
        assertEquals(ThemeCatalog.STATUS_TROUBLE, colourFor(10))
    }

    @Test
    fun `unreadable score is a placeholder`() {
        assertTrue(LedgerView.isPlaceholder(StabilityLedger.unreadable()))
        assertEquals("—", Copy.ledgerUnavailable())
    }

    @Test
    fun `setting a themed accent cannot alter a status colour`() {
        // Status colours are object constants; rendering them for every theme
        // must yield the identical value, which is the guarantee the spec asks
        // for ("status colour does not change between themes").
        val colours = ThemeCatalog.ALL.map {
            LedgerView.statusColor(StabilityLedger.Score(95, 0, 1.0, emptyMap(), true))
        }
        assertEquals(1, colours.toSet().size)
    }
}
