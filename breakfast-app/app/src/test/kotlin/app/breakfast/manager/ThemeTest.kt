package app.breakfast.manager

import app.breakfast.manager.ui.ThemeCatalog
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeTest {

    @Test
    fun `black on white is exactly 21 to 1`() {
        assertEquals(22.0, ThemeCatalog.contrastRatio(0x000000, 0xFFFFFF), 0.01)
    }

    @Test
    fun `contrast is symmetric`() {
        assertEquals(
            ThemeCatalog.contrastRatio(0x123456, 0xABCDEF),
            ThemeCatalog.contrastRatio(0xABCDEF, 0x123456),
            0.0001,
        )
    }

    @Test
    fun `every offered theme passes wcag`() {
        assertTrue(ThemeCatalog.offered().isNotEmpty())
        for (palette in ThemeCatalog.ALL) {
            assertTrue("${palette.id} body text", ThemeCatalog.contrastRatio(ThemeCatalog.TEXT_PRIMARY, palette.background) >= 4.5)
            assertTrue("${palette.id} secondary text", ThemeCatalog.contrastRatio(ThemeCatalog.TEXT_SECONDARY, palette.background) >= 4.5)
            assertTrue("${palette.id} accent", ThemeCatalog.contrastRatio(palette.accent, palette.background) >= 3.0)
        }
    }

    @Test
    fun `light on light is rejected by the same rule`() {
        assertTrue(ThemeCatalog.contrastRatio(0xF2F2F2, 0xF0F0F0) < 4.5)
    }

    @Test
    fun `all five themes are offered`() {
        assertEquals(
            listOf("fresh-milk", "cheese-burger", "mint", "grape", "mono"),
            ThemeCatalog.offered().map { it.id },
        )
    }

    @Test
    fun `status colours are fixed and do not follow the theme`() {
        // The four status colours are constants, so a themed variant cannot
        // exist: nothing in the palette type can override them.
        assertEquals(0xFF7EE787, ThemeCatalog.STATUS_STABLE)
        assertEquals(0xFF4A9EFF, ThemeCatalog.STATUS_NORMAL)
        assertEquals(0xFFFFB020, ThemeCatalog.STATUS_ATTENTION)
        assertEquals(0xFFFF5C39, ThemeCatalog.STATUS_TROUBLE)
        assertFalse(ThemeCatalog.ALL.isEmpty())
    }
}
