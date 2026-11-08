package com.rifsxd.ksunext.ui.theme

import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R

/** Styles share one set of screens and one root backend; these are presentation only. */
enum class ManagerStyle(val id: String) {
    PIXEL("pixel"), CYBERPUNK("cyberpunk"), IOS_GLASS("ios_glass"), NEON("neon");

    companion object {
        fun fromId(id: String?): ManagerStyle = entries.firstOrNull { it.id == id } ?: PIXEL
    }
}

val LocalManagerStyle = staticCompositionLocalOf { ManagerStyle.PIXEL }

private val CyberShapes = Shapes(
    extraSmall = CutCornerShape(topStart = 0.dp, topEnd = 5.dp, bottomEnd = 0.dp, bottomStart = 5.dp),
    small = CutCornerShape(topStart = 0.dp, topEnd = 8.dp, bottomEnd = 0.dp, bottomStart = 8.dp),
    medium = CutCornerShape(topStart = 0.dp, topEnd = 14.dp, bottomEnd = 0.dp, bottomStart = 14.dp),
    large = CutCornerShape(topStart = 0.dp, topEnd = 18.dp, bottomEnd = 0.dp, bottomStart = 18.dp),
    extraLarge = CutCornerShape(topStart = 0.dp, topEnd = 22.dp, bottomEnd = 0.dp, bottomStart = 22.dp),
)
private val IosShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp), small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
)
private val NeonShapes = Shapes(
    extraSmall = RoundedCornerShape(5.dp), small = RoundedCornerShape(9.dp),
    medium = RoundedCornerShape(12.dp), large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(20.dp),
)

fun shapesForStyle(style: ManagerStyle): Shapes = when (style) {
    ManagerStyle.PIXEL -> GlassShapes
    ManagerStyle.CYBERPUNK -> CyberShapes
    ManagerStyle.IOS_GLASS -> IosShapes
    ManagerStyle.NEON -> NeonShapes
}

// Keep body text in the system font; only short headings vary across designs.
private val NeonDisplay = FontFamily(Font(R.font.oxanium, FontWeight.Normal))
private fun headings(font: FontFamily): Typography = Typography.copy(
    displaySmall = Typography.displaySmall.copy(fontFamily = font, fontSize = 27.sp),
    headlineMedium = Typography.headlineMedium.copy(fontFamily = font, fontSize = 23.sp),
    headlineSmall = Typography.headlineSmall.copy(fontFamily = font, fontSize = 20.sp),
    titleLarge = Typography.titleLarge.copy(fontFamily = font, fontSize = 18.sp),
)
private val CyberTypography = headings(FontFamily.Monospace)
private val IosTypography = headings(FontFamily.SansSerif)
private val NeonTypography = headings(NeonDisplay)

fun typographyForStyle(style: ManagerStyle): Typography = when (style) {
    ManagerStyle.PIXEL -> Typography
    ManagerStyle.CYBERPUNK -> CyberTypography
    ManagerStyle.IOS_GLASS -> IosTypography
    ManagerStyle.NEON -> NeonTypography
}

/** The legacy accent IDs are retained so existing 3.x/4.0 settings migrate. */
fun accentForStyle(style: ManagerStyle, id: String, dark: Boolean): Color = when (style) {
    ManagerStyle.PIXEL -> if (dark) when (id) {
        "pink" -> Color(0xFFF4F3ED); "violet" -> Color(0xFFFFC785); "lime" -> Color(0xFFAFE2C5); else -> Color(0xFFFF665E)
    } else when (id) {
        "pink" -> Color(0xFF292927); "violet" -> Color(0xFF865000); "lime" -> Color(0xFF176145); else -> Color(0xFFAD231D)
    }
    ManagerStyle.CYBERPUNK -> if (dark) when (id) {
        "pink" -> Color(0xFFFF809A); "violet" -> Color(0xFF82DDFF); "lime" -> Color(0xFFB8FF8C); else -> Color(0xFFD4FF00)
    } else when (id) {
        "pink" -> Color(0xFFA0003D); "violet" -> Color(0xFF005F78); "lime" -> Color(0xFF315D0D); else -> Color(0xFF434E00)
    }
    ManagerStyle.IOS_GLASS -> if (dark) when (id) {
        "pink" -> Color(0xFFFF8DAE); "violet" -> Color(0xFFC2A7FF); "lime" -> Color(0xFF80DDBD); else -> Color(0xFF80BDFF)
    } else when (id) {
        "pink" -> Color(0xFFAD1352); "violet" -> Color(0xFF6332A9); "lime" -> Color(0xFF076A4D); else -> Color(0xFF0057B4)
    }
    ManagerStyle.NEON -> if (dark) when (id) {
        "pink" -> Color(0xFFFF86D8); "violet" -> Color(0xFFD4A7FF); "lime" -> Color(0xFFBAFF87); else -> Color(0xFF5AEFFF)
    } else when (id) {
        "pink" -> Color(0xFF9C0063); "violet" -> Color(0xFF6631A1); "lime" -> Color(0xFF2D6515); else -> Color(0xFF006078)
    }
}

@Immutable
data class StylePalette(val glass: GlassStyle, val scheme: ColorScheme)

/** Low-overdraw opaque panels and gentle gradients; no root or settings writes. */
fun paletteForStyle(style: ManagerStyle, dark: Boolean, amoled: Boolean, base: ColorScheme): StylePalette {
    var glass = when (style) {
        ManagerStyle.PIXEL -> if (dark && amoled) AmoledGlassStyle else if (dark) DarkGlassStyle else LightGlassStyle
        ManagerStyle.CYBERPUNK -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF090A0D), cardTintTop = Color(0xFF12151D), cardTintBottom = Color(0xFF12151D),
            elevatedTintTop = Color(0xFF1A1F2B), elevatedTintBottom = Color(0xFF1A1F2B),
            barTintTop = Color(0xFF0E1117), barTintBottom = Color(0xFF0E1117),
            dockTintTop = Color(0xFF1A1F2B), dockTintBottom = Color(0xFF12151D),
            borderHighlight = Color(0xFF576474), borderMid = Color(0xFF303B4A), borderShadow = Color(0xFF303B4A),
            divider = Color(0xFF394351), shadowColor = Color.Transparent,
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFECEBE4), cardTintTop = Color(0xFFF8F7F2), cardTintBottom = Color(0xFFF8F7F2),
            elevatedTintTop = Color.White, elevatedTintBottom = Color(0xFFF8F7F2),
            barTintTop = Color(0xFFECEBE4), barTintBottom = Color(0xFFECEBE4),
            dockTintTop = Color(0xFFF8F7F2), dockTintBottom = Color(0xFFE5E3D9),
            borderHighlight = Color(0xFF59605F), borderMid = Color(0xFF8A908C), borderShadow = Color(0xFF59605F),
            divider = Color(0xFFB7B9B3), shadowColor = Color.Transparent,
        )
        ManagerStyle.IOS_GLASS -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF071120), cardTintTop = Color(0xFF1B2A40), cardTintBottom = Color(0xFF142137),
            elevatedTintTop = Color(0xFF243A55), elevatedTintBottom = Color(0xFF1B2B43),
            barTintTop = Color(0xFF112038), barTintBottom = Color(0xFF101D31),
            dockTintTop = Color(0xFF223750), dockTintBottom = Color(0xFF182A41),
            borderHighlight = Color(0xFF667F9B), borderMid = Color(0xFF455D78), borderShadow = Color(0xFF263C53),
            divider = Color(0xFF465B72), shadowColor = Color(0x55000000),
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFEAF2FC), cardTintTop = Color.White, cardTintBottom = Color(0xFFF2F7FE),
            elevatedTintTop = Color.White, elevatedTintBottom = Color(0xFFF5F9FF),
            barTintTop = Color(0xFFF8FBFF), barTintBottom = Color(0xFFF2F7FC),
            dockTintTop = Color.White, dockTintBottom = Color(0xFFEAF3FC),
            borderHighlight = Color(0xFFC0D2E5), borderMid = Color(0xFFD8E5F3), borderShadow = Color(0xFFB0C6DC),
            divider = Color(0xFFD1DDEA), shadowColor = Color(0x220B2849),
        )
        ManagerStyle.NEON -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF070B1B), cardTintTop = Color(0xFF111A30), cardTintBottom = Color(0xFF0A1025),
            elevatedTintTop = Color(0xFF192440), elevatedTintBottom = Color(0xFF101830),
            barTintTop = Color(0xFF080E20), barTintBottom = Color(0xFF0B1125),
            dockTintTop = Color(0xFF15243D), dockTintBottom = Color(0xFF0A1225),
            borderHighlight = Color(0xFF477B91), borderMid = Color(0xFF334F76), borderShadow = Color(0xFF44284F),
            divider = Color(0xFF304B60), shadowColor = Color.Transparent,
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFEDF4FC), cardTintTop = Color(0xFFFDFEFF), cardTintBottom = Color(0xFFF1F5FF),
            elevatedTintTop = Color.White, elevatedTintBottom = Color(0xFFF0F4FF),
            barTintTop = Color(0xFFF8FBFF), barTintBottom = Color(0xFFF0F5FF),
            dockTintTop = Color(0xFFFDFEFF), dockTintBottom = Color(0xFFF0F4FF),
            borderHighlight = Color(0xFF98C4D3), borderMid = Color(0xFFC3D9E9), borderShadow = Color(0xFFABC2D8),
            divider = Color(0xFFD1DDEA), shadowColor = Color.Transparent,
        )
    }
    if (dark && amoled) glass = glass.copy(
        isAmoled = true, canvasBase = Color.Black, barTintTop = Color.Black, barTintBottom = Color.Black,
    )
    if (style == ManagerStyle.PIXEL) return StylePalette(glass, base.copy(background = glass.canvasBase))
    val ink = if (dark) Color(0xFFF2F5FC) else Color(0xFF121D2A)
    val muted = if (dark) Color(0xFFB6C2D2) else Color(0xFF435263)
    val surface = glass.cardTintTop
    val scheme = base.copy(
        background = glass.canvasBase, onBackground = ink,
        surface = surface, onSurface = ink,
        surfaceVariant = glass.elevatedTintTop, onSurfaceVariant = muted,
        surfaceContainerLowest = glass.barTintTop, surfaceContainerLow = glass.cardTintBottom,
        surfaceContainer = surface, surfaceContainerHigh = glass.elevatedTintTop,
        surfaceContainerHighest = glass.elevatedTintTop, outline = glass.borderHighlight,
        outlineVariant = glass.borderMid,
        secondary = if (dark) Color(0xFFB8C9DA) else Color(0xFF405A70),
        onSecondary = if (dark) Color(0xFF102030) else Color.White,
    )
    return StylePalette(glass, scheme)
}
