package app.breakfast.manager.ui

/**
 * Themes and their contrast rule.
 *
 * A theme that fails the WCAG check is not offered in the picker. The numbers
 * in ThemeCatalog are computed by contrastRatio() at runtime, not typed in, so a
 * colour edit that breaks readability fails the unit test instead of shipping.
 *
 * Status colours (green / amber / orange / red) deliberately do NOT follow the
 * theme: red must mean danger in every theme. Monochrome adds a pattern so that
 * status is still distinguishable without hue.
 */
object ThemeCatalog {

    data class Palette(
        val id: String,
        val displayName: String,
        val background: Long,
        val accent: Long,
        val accentSecondary: Long,
        val surface: Long,
        val cornerDp: Int,
        val animationMs: Int,
    )

    const val TEXT_PRIMARY = 0xFFF2F2F2
    const val TEXT_SECONDARY = 0xFF9A9A9A

    /** Fixed semantics - never themed. */
    const val STATUS_STABLE = 0xFF7EE787
    const val STATUS_NORMAL = 0xFF4A9EFF
    const val STATUS_ATTENTION = 0xFFFFB020
    const val STATUS_TROUBLE = 0xFFFF5C39

    private const val MIN_BODY = 4.5
    private const val MIN_NON_TEXT = 3.0

    val ALL: List<Palette> = listOf(
        Palette(
            id = "fresh-milk",
            displayName = "Fresh-Milk",
            background = 0xFF0D1117,
            accent = 0xFF4A9EFF,
            accentSecondary = 0xFF7EE787,
            surface = 0xFF161B22,
            cornerDp = 16,
            animationMs = 320,
        ),
        Palette(
            id = "cheese-burger",
            displayName = "CHEESE-BURGER",
            background = 0xFF0A0A0C,
            accent = 0xFFFFB020,
            accentSecondary = 0xFFFF5C39,
            surface = 0xFF14141A,
            cornerDp = 12,
            animationMs = 200,
        ),
        Palette(
            id = "mint",
            displayName = "Mint",
            background = 0xFF0B1512,
            accent = 0xFF3DDC97,
            accentSecondary = 0xFF8AE6C0,
            surface = 0xFF12201B,
            cornerDp = 16,
            animationMs = 280,
        ),
        Palette(
            id = "grape",
            displayName = "Grape",
            background = 0xFF120D18,
            accent = 0xFFA56BFF,
            accentSecondary = 0xFFD3B4FF,
            surface = 0xFF1C1524,
            cornerDp = 16,
            animationMs = 280,
        ),
        Palette(
            id = "mono",
            displayName = "Monochrome",
            background = 0xFF0C0C0C,
            accent = 0xFFD6D6D6,
            accentSecondary = 0xFF8A8A8A,
            surface = 0xFF171717,
            cornerDp = 16,
            animationMs = 240,
        ),
    )

    /** WCAG 2.1 relative luminance for an 0xAARRGGBB colour. */
    fun luminance(color: Long): Double {
        fun channel(value: Long): Double {
            val c = (value and 0xFF) / 255.0
            return if (c <= 0.03928) c / 12.92 else Math.pow((c + 0.055) / 1.055, 2.4)
        }
        val r = channel((color shr 16) and 0xFF)
        val g = channel((color shr 8) and 0xFF)
        val b = channel(color and 0xFF)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }

    /** WCAG 2.1 contrast ratio, always >= 1. */
    fun contrastRatio(a: Long, b: Long): Double {
        val la = luminance(a)
        val lb = luminance(b)
        val light = maxOf(la, lb)
        val dark = minOf(la, lb)
        return (light + 0.05) / (dark + 0.05)
    }

    /** Body text must reach 4.5:1; the accent is a non-text element, 3:1. */
    fun passes(palette: Palette): Boolean =
        contrastRatio(TEXT_PRIMARY, palette.background) >= MIN_BODY &&
            contrastRatio(TEXT_SECONDARY, palette.background) >= MIN_BODY &&
            contrastRatio(palette.accent, palette.background) >= MIN_NON_TEXT

    fun offered(): List<Palette> = ALL.filter(::passes)

    fun byId(id: String): Palette? = ALL.firstOrNull { it.id == id }
}
