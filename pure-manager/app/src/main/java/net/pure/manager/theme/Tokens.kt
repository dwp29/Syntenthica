package net.pure.manager.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Design tokens.
 *
 * The whole point of this file is that **no composable may branch on which theme
 * is active**. Screens read tokens; [PureThemeSpec] decides what those tokens are.
 * That is what lets Windows get a left rail and Cyberpunk get a command bar
 * without either theme's rules leaking into shared UI code.
 */

/** How the shell is laid out. Not decoration: it is a different navigation model. */
enum class NavModel {
    /** Bottom tab bar, title on top. iOS and Pixel. */
    TAB_BAR,

    /** Left rail plus a columned table. Fluent / Explorer. */
    RAIL,

    /** Bottom command bar with F-key affordances. Cyberpunk. */
    COMMAND_BAR,
}

enum class AppMode { LIGHT, DARK, AMOLED }

/** Motion is a token, not a hardcoded duration in each composable. */
data class MotionSpec(
    /** Press feedback scale. 1f disables the effect entirely. */
    val pressScale: Float,
    val shortMs: Int,
    val longMs: Int,
    /** Expressive themes overshoot; dense productivity themes do not. */
    val overshoot: Boolean,
)

data class Palette(
    val background: Color,
    val surface: Color,
    val surfaceVariant: Color,
    val onBackground: Color,
    val onSurfaceVariant: Color,
    val accent: Color,
    val onAccent: Color,
    /** AMOLED relies on this because tonal elevation is invisible on pure black. */
    val outline: Color,
    val useShadow: Boolean,
    /** Hairline between list rows. Unspecified falls back to [outline]. */
    val separator: Color = Color.Unspecified,
)

/** How the bars above and below the content are drawn. */
enum class ChromeStyle {
    /** Opaque surface with a hairline edge. */
    SOLID,

    /** Translucent, blurred copy of whatever scrolls underneath. */
    GLASS,
}

data class PureThemeSpec(
    val id: String,
    val label: String,
    val nav: NavModel,
    val palette: Palette,
    val cornerDp: Int,
    val rowHeightDp: Int,
    val contentPaddingDp: Int,
    val fontFamily: FontFamily,
    val motion: MotionSpec,
    /** Compact themes show the size column inline; roomy ones use a subtitle. */
    val compactRows: Boolean,
    val chrome: ChromeStyle = ChromeStyle.SOLID,
    /** Blur strength for [ChromeStyle.GLASS]. Ignored when SOLID. */
    val blurDp: Int = 0,
    /**
     * Tint laid over the blur. Glass is not "transparent grey": iOS uses a white
     * veil in light mode and a thin white one on dark, otherwise text loses
     * contrast against whatever is scrolling behind it.
     */
    val glassTint: Color = Color.Unspecified,
    /** Large title above the content, collapsing as it scrolls. */
    val useLargeTitle: Boolean = false,
    /** Folder grid rather than a row list when the browser opens. */
    val defaultGrid: Boolean = false,
    /** Floating action button instead of a toolbar button. */
    val floatingAction: Boolean = false,
)

/** The tint iOS puts over its blurred bars, per mode. */
private fun iosGlassTint(mode: AppMode): Color = when (mode) {
    AppMode.LIGHT -> Color(0xCCFFFFFF)
    AppMode.DARK -> Color(0x991C1C1E)
    AppMode.AMOLED -> Color(0xE6000000)
}

// ------------------------------------------------------------------ palettes
// AMOLED is deliberately not "dark but darker". On pure black a tonal surface is
// invisible, so these palettes switch to outlines to separate layers.

private fun ios(mode: AppMode, accent: Color) = when (mode) {
    AppMode.LIGHT -> Palette(
        Color(0xFFF2F2F7), Color(0xFFFFFFFF), Color(0xFFE4E4EA),
        Color(0xFF1C1C1E), Color(0xFF8E8E93), accent, Color.White,
        Color.Transparent, useShadow = true, separator = Color(0x593C3C43),
    )
    AppMode.DARK -> Palette(
        Color(0xFF000000), Color(0xFF1C1C1E), Color(0xFF2C2C2E),
        Color(0xFFFFFFFF), Color(0xFF98989F), accent, Color.White,
        Color.Transparent, useShadow = false, separator = Color(0x9948485A),
    )
    AppMode.AMOLED -> Palette(
        Color(0xFF000000), Color(0xFF0E0E10), Color(0xFF1A1A1C),
        Color(0xFFFFFFFF), Color(0xFF98989F), accent, Color.White,
        Color(0xFF2A2A2E), useShadow = false, separator = Color(0xFF2C2C2E),
    )
}

private fun pixel(mode: AppMode, accent: Color) = when (mode) {
    AppMode.LIGHT -> Palette(
        Color(0xFFFFFBFE), Color(0xFFF3EDF7), Color(0xFFE8DEF8),
        Color(0xFF1C1B1F), Color(0xFF79747E), accent, Color(0xFF2B1D4A),
        Color.Transparent, useShadow = false,
    )
    AppMode.DARK -> Palette(
        Color(0xFF141218), Color(0xFF211F26), Color(0xFF2B2930),
        Color(0xFFE6E0E9), Color(0xFF938F99), accent, Color(0xFF2B1D4A),
        Color.Transparent, useShadow = false,
    )
    AppMode.AMOLED -> Palette(
        Color(0xFF000000), Color(0xFF101014), Color(0xFF1C1B20),
        Color(0xFFE6E0E9), Color(0xFF938F99), accent, Color(0xFF2B1D4A),
        Color(0xFF2B2930), useShadow = false,
    )
}

private fun windows(mode: AppMode, accent: Color) = when (mode) {
    AppMode.LIGHT -> Palette(
        Color(0xFFF3F3F3), Color(0xFFFFFFFF), Color(0xFFEAEAEA),
        Color(0xFF1A1A1A), Color(0xFF5D5D5D), accent, Color(0xFF00232E),
        Color(0xFFD6D6D6), useShadow = false,
    )
    AppMode.DARK -> Palette(
        Color(0xFF202020), Color(0xFF2B2B2B), Color(0xFF333333),
        Color(0xFFFFFFFF), Color(0xFFA6A6A6), accent, Color(0xFF00232E),
        Color(0xFF3D3D3D), useShadow = false,
    )
    AppMode.AMOLED -> Palette(
        Color(0xFF000000), Color(0xFF141414), Color(0xFF1E1E1E),
        Color(0xFFFFFFFF), Color(0xFFA6A6A6), accent, Color(0xFF00232E),
        Color(0xFF2E2E2E), useShadow = false,
    )
}

private fun cyber(mode: AppMode, accent: Color) = when (mode) {
    AppMode.LIGHT -> Palette(
        Color(0xFFF4F0FF), Color(0xFFFFFFFF), Color(0xFFE9E0FF),
        Color(0xFF12081F), Color(0xFF6B5B85), accent, Color.White,
        Color(0xFFD5C2FF), useShadow = false,
    )
    AppMode.DARK -> Palette(
        Color(0xFF08000F), Color(0xFF12081F), Color(0xFF1B0E2E),
        Color(0xFFE8FFFB), Color(0xFF7A6B8F), accent, Color(0xFF00181C),
        Color(0xFFFF2E97), useShadow = false,
    )
    AppMode.AMOLED -> Palette(
        Color(0xFF000000), Color(0xFF07000D), Color(0xFF12081F),
        Color(0xFFE8FFFB), Color(0xFF7A6B8F), accent, Color(0xFF00181C),
        Color(0xFF00F0FF), useShadow = false,
    )
}

/**
 * The themes the Customisation tab offers, in display order.
 *
 * Screens read this list; they never compare `themeId` against a string. That is
 * the same rule the rest of the token system follows, and it is why adding a
 * fifth theme later touches this file and nothing else.
 */
data class ThemeRef(
    val id: String,
    val label: String,
    val nav: NavModel,
    /** Shown in the picker: the theme's accent-on-surface, not its background. */
    val swatch: Color,
    val note: String,
)

val ThemeCatalog: List<ThemeRef> = listOf(
    ThemeRef("ios", "iOS", NavModel.TAB_BAR, Color(0xFF007AFF),
        "Tab bar bawah, sudut membulat, baris lega"),
    ThemeRef("pixel", "Pixel", NavModel.TAB_BAR, Color(0xFF8B5CF6),
        "Material 3, pil indikator, sudut besar"),
    ThemeRef("windows", "Windows", NavModel.RAIL, Color(0xFF00A4EF),
        "Rail kiri, baris rapat, sudut nyaris tegak"),
    ThemeRef("cyber", "Cyberpunk", NavModel.COMMAND_BAR, Color(0xFFFF2E97),
        "Command bar F1–F4, monospace, garis neon"),
)

/** Accent choices offered by the Customisation tab. */
val AccentChoices: List<Pair<String, Color>> = listOf(
    "Biru" to Color(0xFF007AFF),
    "Ungu" to Color(0xFF8B5CF6),
    "Hijau" to Color(0xFF10B981),
    "Amber" to Color(0xFFF59E0B),
    "Merah" to Color(0xFFEF4444),
    "Pink" to Color(0xFFEC4899),
    "Cyan" to Color(0xFF00F0FF),
)

/** Builds the full token set for one theme × mode × accent combination. */
fun specFor(themeId: String, mode: AppMode, accent: Color): PureThemeSpec =
    when (themeId) {
        "pixel" -> PureThemeSpec(
            id = "pixel", label = "Pixel", nav = NavModel.TAB_BAR,
            palette = pixel(mode, accent),
            cornerDp = 22, rowHeightDp = 62, contentPaddingDp = 16,
            fontFamily = FontFamily.SansSerif,
            motion = MotionSpec(pressScale = 0.96f, shortMs = 140, longMs = 320, overshoot = true),
            compactRows = false,
        )
        "windows" -> PureThemeSpec(
            id = "windows", label = "Windows", nav = NavModel.RAIL,
            palette = windows(mode, accent),
            cornerDp = 4, rowHeightDp = 36, contentPaddingDp = 8,
            fontFamily = FontFamily.SansSerif,
            motion = MotionSpec(pressScale = 0.98f, shortMs = 90, longMs = 200, overshoot = false),
            compactRows = true,
        )
        "cyber" -> PureThemeSpec(
            id = "cyber", label = "Cyberpunk", nav = NavModel.COMMAND_BAR,
            palette = cyber(mode, accent),
            cornerDp = 3, rowHeightDp = 32, contentPaddingDp = 10,
            fontFamily = FontFamily.Monospace,
            motion = MotionSpec(pressScale = 0.94f, shortMs = 110, longMs = 260, overshoot = true),
            compactRows = true,
        )
        else -> PureThemeSpec(
            id = "ios", label = "iOS", nav = NavModel.TAB_BAR,
            palette = ios(mode, accent),
            cornerDp = 16, rowHeightDp = 54, contentPaddingDp = 14,
            fontFamily = FontFamily.SansSerif,
            motion = MotionSpec(pressScale = 0.97f, shortMs = 160, longMs = 380, overshoot = true),
            compactRows = false,
            chrome = ChromeStyle.GLASS,
            blurDp = 28,
            glassTint = iosGlassTint(mode),
            useLargeTitle = true,
            defaultGrid = true,
            floatingAction = true,
        )
    }

fun shapesFor(spec: PureThemeSpec) = Shapes(
    extraSmall = RoundedCornerShape((spec.cornerDp / 2).dp),
    small = RoundedCornerShape((spec.cornerDp * 0.75f).dp),
    medium = RoundedCornerShape(spec.cornerDp.dp),
    large = RoundedCornerShape((spec.cornerDp * 1.4f).dp),
    extraLarge = RoundedCornerShape((spec.cornerDp * 1.8f).dp),
)

fun typographyFor(spec: PureThemeSpec, scale: Float = 1f) = Typography().let { base ->
    // Every role the UI uses is restated here, because the shell reads its text
    // sizes from MaterialTheme.typography rather than hardcoding sp values. That
    // is what makes the density slider in the Customisation tab mean anything --
    // the previous version set four roles that no composable ever read, so the
    // slider was decoration.
    val f = spec.fontFamily
    fun fixed(size: Float) = (size * scale).sp
    base.copy(
        headlineMedium = base.headlineMedium.copy(
            fontFamily = f, fontWeight = FontWeight.Bold,
            fontSize = fixed(26f), lineHeight = fixed(32f),
        ),
        titleLarge = base.titleLarge.copy(
            fontFamily = f, fontWeight = FontWeight.Bold,
            fontSize = fixed(19f), lineHeight = fixed(24f),
        ),
        titleMedium = base.titleMedium.copy(
            fontFamily = f, fontWeight = FontWeight.SemiBold,
            fontSize = fixed(16f), lineHeight = fixed(21f),
        ),
        bodyLarge = base.bodyLarge.copy(
            fontFamily = f, fontSize = fixed(15.5f), lineHeight = fixed(21f),
        ),
        bodyMedium = base.bodyMedium.copy(
            fontFamily = f, fontSize = fixed(14f), lineHeight = fixed(19f),
        ),
        bodySmall = base.bodySmall.copy(
            fontFamily = f, fontSize = fixed(12.5f), lineHeight = fixed(17f),
        ),
        labelMedium = base.labelMedium.copy(
            fontFamily = f, fontWeight = FontWeight.Medium,
            fontSize = fixed(11.5f), lineHeight = fixed(15f),
        ),
        labelSmall = base.labelSmall.copy(
            fontFamily = f, fontSize = fixed(10.5f), lineHeight = fixed(13f),
        ),
    )
}
