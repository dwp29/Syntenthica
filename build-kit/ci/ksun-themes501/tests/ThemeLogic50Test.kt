package com.rifsxd.ksunext.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import kotlin.math.pow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeLogic50Test {
    private fun luminance(c: Color): Double {
        fun channel(v: Float): Double = if (v <= 0.04045f) v / 12.92 else ((v + 0.055) / 1.055).pow(2.4)
        return .2126 * channel(c.red) + .7152 * channel(c.green) + .0722 * channel(c.blue)
    }
    private fun contrast(a: Color, b: Color): Double {
        val first = luminance(a)
        val second = luminance(b)
        return (maxOf(first, second) + .05) / (minOf(first, second) + .05)
    }

    @Test fun stableIdsAndFallback() {
        assertEquals(listOf("pixel", "cyberpunk", "ios_glass", "neon"), ManagerStyle.entries.map { it.id })
        ManagerStyle.entries.forEach { assertEquals(it, ManagerStyle.fromId(it.id)) }
        assertEquals(ManagerStyle.PIXEL, ManagerStyle.fromId(null))
        assertEquals(ManagerStyle.PIXEL, ManagerStyle.fromId("unexpected"))
    }

    @Test fun eachStyleHasDistinctDefaultAndGeometry() {
        assertEquals(4, ManagerStyle.entries.map { accentForStyle(it, "cyan", true) }.toSet().size)
        assertNotEquals(shapesForStyle(ManagerStyle.CYBERPUNK).large, shapesForStyle(ManagerStyle.IOS_GLASS).large)
        assertNotEquals(shapesForStyle(ManagerStyle.PIXEL).large, shapesForStyle(ManagerStyle.NEON).large)
    }

    @Test fun primaryButtonAccentsRemainReadableAcrossStyles() {
        for (style in ManagerStyle.entries) for (id in listOf("cyan", "pink", "violet", "lime")) {
            assertTrue("$style/$id light", contrast(accentForStyle(style, id, false), Color.White) >= 4.5)
            assertTrue("$style/$id dark", contrast(accentForStyle(style, id, true), Color(0xFF101118)) >= 4.5)
        }
    }

    @Test fun amoledCanvasIsBlackInEveryStyle() {
        for (style in ManagerStyle.entries) {
            val palette = paletteForStyle(style, dark = true, amoled = true, base = darkColorScheme())
            assertEquals(Color.Black, palette.glass.canvasBase)
            assertEquals(Color.Black, palette.scheme.background)
            assertTrue(palette.glass.isAmoled)
            val light = paletteForStyle(style, dark = false, amoled = false, base = lightColorScheme())
            assertTrue("$style light ink", contrast(light.scheme.onSurface, light.scheme.surface) >= 4.5)
        }
    }
}
