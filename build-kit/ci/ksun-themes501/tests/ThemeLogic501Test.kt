package com.rifsxd.ksunext.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeLogic501Test {
    @Test fun dockGeometryIsActuallyDifferentForEachDesign() {
        val specs = ManagerStyle.entries.associateWith(::managerDockSpec)
        assertEquals(4, specs.values.map { it.containerShape }.toSet().size)
        assertEquals(RectangleShape, specs.getValue(ManagerStyle.PIXEL).containerShape)
        assertEquals(0.dp, specs.getValue(ManagerStyle.PIXEL).horizontalMargin)
        assertEquals(28.dp, specs.getValue(ManagerStyle.IOS_GLASS).horizontalMargin)
        assertTrue(specs.getValue(ManagerStyle.CYBERPUNK).uppercaseLabels)
        assertNotEquals(specs.getValue(ManagerStyle.CYBERPUNK).height, specs.getValue(ManagerStyle.NEON).height)
    }

    @Test fun glassUsesRealBlurOnlyWhenSupportedAndAmoledCanvasStaysBlack() {
        for (dark in listOf(false, true)) {
            val palette = paletteForStyle(ManagerStyle.IOS_GLASS, dark, false,
                if (dark) darkColorScheme() else lightColorScheme())
            assertTrue(palette.glass.blurRadius > 0.dp)
            assertTrue(palette.glass.dockBlurRadius > palette.glass.blurRadius)
        }
        for (style in ManagerStyle.entries) {
            val palette = paletteForStyle(style, true, true, darkColorScheme())
            assertEquals(Color.Black, palette.glass.canvasBase)
            assertTrue(palette.glass.isAmoled)
        }
    }

    @Test fun splashTagAndPreviewTickAreDistinctPerDesign() {
        val tags = ManagerStyle.entries.map(::splashTagForStyle)
        assertEquals(4, tags.toSet().size)
        tags.forEach { assertTrue(it.endsWith(" // MANAGER 5.0.1")) }
        val before = SplashPreviewTickState.intValue
        triggerThemeSplashPreview()
        assertEquals(before + 1, SplashPreviewTickState.intValue)
    }
}
