package app.breakfast.manager.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.ui.ThemeCatalog

/**
 * Design tokens, taken from design/breakfast/README.md.
 *
 * Two faces, one system: Fresh-Milk is calm blue on #0D1117, CHEESE-BURGER is
 * sharp amber on #0A0A0C with tighter corners and faster motion. Everything
 * else - grid, type scale, navigation, component shapes - is shared, which is
 * what keeps them looking like one product.
 *
 * Status colours are constants here on purpose: red must mean danger in every
 * skin, and the unit tests assert that no skin can override them.
 */
data class BreakfastColors(
    val background: Color,
    val surface: Color,
    val surfaceElevated: Color,
    val hairline: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textTertiary: Color,
    val accent: Color,
    val accentSoft: Color,
    val statusStable: Color,
    val statusNormal: Color,
    val statusAttention: Color,
    val statusTrouble: Color,
    val cardCorner: androidx.compose.ui.unit.Dp,
    val chipCorner: androidx.compose.ui.unit.Dp,
    val motionMs: Int,
    val isDense: Boolean,
)

private fun hex(argb: Long): Color = Color(argb.toInt())

fun colorsFor(palette: ThemeCatalog.Palette): BreakfastColors {
    val dense = palette.id == "cheese-burger"
    return BreakfastColors(
        background = hex(palette.background),
        surface = hex(palette.surface),
        // One step lighter than the card, for rows inside a card.
        surfaceElevated = hex(palette.surface + 0x080808L),
        hairline = Color.White.copy(alpha = if (dense) 0.10f else 0.06f),
        textPrimary = hex(ThemeCatalog.TEXT_PRIMARY),
        textSecondary = hex(ThemeCatalog.TEXT_SECONDARY),
        textTertiary = Color.White.copy(alpha = 0.38f),
        accent = hex(palette.accent),
        accentSoft = hex(palette.accent).copy(alpha = 0.16f),
        statusStable = hex(ThemeCatalog.STATUS_STABLE.toLong()),
        statusNormal = hex(ThemeCatalog.STATUS_NORMAL.toLong()),
        statusAttention = hex(ThemeCatalog.STATUS_ATTENTION.toLong()),
        statusTrouble = hex(ThemeCatalog.STATUS_TROUBLE.toLong()),
        cardCorner = if (dense) 12.dp else 16.dp,
        chipCorner = 999.dp,
        motionMs = palette.animationMs,
        isDense = dense,
    )
}

val LocalBreakfastColors = staticCompositionLocalOf { colorsFor(ThemeCatalog.ALL.first()) }

/** Monospace for every number, so digits do not jump as values change. */
val NumericStyle = TextStyle(fontFamily = FontFamily.Monospace)

private fun typeScale(): Typography {
    val base = Typography()
    return base.copy(
        displayLarge = TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Medium,
            fontSize = 44.sp,
            letterSpacing = (-1).sp,
        ),
        headlineMedium = TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Bold,
            fontSize = 26.sp,
            letterSpacing = 1.5.sp,
        ),
        titleMedium = TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.SemiBold,
            fontSize = 16.sp,
        ),
        bodyMedium = TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Normal,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        ),
        labelSmall = TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.SemiBold,
            fontSize = 11.sp,
            letterSpacing = 1.2.sp,
        ),
    )
}

@Composable
fun BreakfastTheme(palette: ThemeCatalog.Palette, content: @Composable () -> Unit) {
    val colors = colorsFor(palette)
    val scheme = darkColorScheme(
        primary = colors.accent,
        onPrimary = Color.Black,
        background = colors.background,
        onBackground = colors.textPrimary,
        surface = colors.surface,
        onSurface = colors.textPrimary,
        surfaceVariant = colors.surfaceElevated,
        onSurfaceVariant = colors.textSecondary,
        outline = colors.hairline,
    )
    CompositionLocalProvider(LocalBreakfastColors provides colors) {
        MaterialTheme(colorScheme = scheme, typography = typeScale(), content = content)
    }
}

/** Shapes shared by every card and chip, derived from the active skin. */
val BreakfastColors.cardShape get() = RoundedCornerShape(cardCorner)
val BreakfastColors.chipShape get() = RoundedCornerShape(chipCorner)
