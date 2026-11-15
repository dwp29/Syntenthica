package com.rifsxd.ksunext.ui.theme

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Text
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R
import kotlinx.coroutines.delay

/** Styles share one set of screens and one root backend; these are presentation only. */
enum class ManagerStyle(val id: String) {
    PIXEL("pixel"), CYBERPUNK("cyberpunk"), IOS_GLASS("ios_glass"), NEON("neon"),
    RETRO_ARCADE("retro_arcade");

    companion object {
        fun fromId(id: String?): ManagerStyle = entries.firstOrNull { it.id == id } ?: PIXEL
    }
}

val LocalManagerStyle = staticCompositionLocalOf { ManagerStyle.PIXEL }

/** Triggers a live boot-splash transition when the user switches themes or taps Preview Splash. */
val SplashPreviewTickState = mutableIntStateOf(0)
val ManagerAnimSpeedState = mutableStateOf("normal")

fun triggerThemeSplashPreview() {
    SplashPreviewTickState.intValue += 1
}

fun setManagerAnimSpeed(context: android.content.Context, speed: String) {
    val valid = if (speed in setOf("normal", "turbo", "reduced")) speed else "normal"
    ManagerAnimSpeedState.value = valid
    runCatching {
        context.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE)
            .edit().putString("manager_anim_speed", valid).apply()
    }
}

fun exportManagerConfigJson(context: android.content.Context): String {
    val prefs = context.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE)
    return org.json.JSONObject().apply {
        put("schema", "synthetica-manager-6.5.0")
        put("manager_visual_style", prefs.getString("manager_visual_style", ManagerStyleState.value.id))
        put("neon_theme_mode", prefs.getString("neon_theme_mode", NeonThemeState.value))
        put("neon_accent", prefs.getString("neon_accent", NeonAccentState.value))
        put("neon_glow_intensity", prefs.getString("neon_glow_intensity", NeonGlowState.value))
        put("neon_motion", prefs.getBoolean("neon_motion", NeonMotionState.value))
        put("manager_anim_speed", prefs.getString("manager_anim_speed", ManagerAnimSpeedState.value))
    }.toString(2)
}

fun importManagerConfigJson(context: android.content.Context, rawJson: String): Boolean = runCatching {
    val obj = org.json.JSONObject(rawJson)
    obj.optString("manager_visual_style").takeIf { it.isNotBlank() }?.let { setManagerStyle(context, it) }
    obj.optString("neon_theme_mode").takeIf { it.isNotBlank() }?.let { setNeonTheme(context, it) }
    obj.optString("neon_accent").takeIf { it.isNotBlank() }?.let { setNeonAccent(context, it) }
    obj.optString("neon_glow_intensity").takeIf { it.isNotBlank() }?.let { setNeonGlow(context, it) }
    if (obj.has("neon_motion")) setNeonMotion(context, obj.optBoolean("neon_motion", true))
    obj.optString("manager_anim_speed").takeIf { it.isNotBlank() }?.let { setManagerAnimSpeed(context, it) }
    true
}.getOrDefault(false)

/** Distinct PNG emblem resource for each of the 4 visual designs. */
fun emblemResForStyle(style: ManagerStyle): Int = when (style) {
    ManagerStyle.PIXEL -> R.drawable.ic_emblem_pixel
    ManagerStyle.CYBERPUNK -> R.drawable.ic_emblem_cyberpunk
    ManagerStyle.IOS_GLASS -> R.drawable.ic_emblem_ios_glass
    ManagerStyle.NEON -> R.drawable.ic_emblem_neon
    ManagerStyle.RETRO_ARCADE -> R.drawable.ic_emblem_retro
}

/** Distinct splash edition label per theme (preserves the ' // MANAGER 6.5' marker). */
fun splashTagForStyle(style: ManagerStyle): String = when (style) {
    ManagerStyle.PIXEL -> "PIXEL // MANAGER 6.5"
    ManagerStyle.CYBERPUNK -> "CYBERPUNK // MANAGER 6.5"
    ManagerStyle.IOS_GLASS -> "GLASS // MANAGER 6.5"
    ManagerStyle.NEON -> "NEON // MANAGER 6.5"
    ManagerStyle.RETRO_ARCADE -> "RETRO ARCADE // MANAGER 6.5"
}

/**
 * Theme-specific motion.
 *
 * Every theme used to share one linear 0..1 sweep with identical easing, so however
 * different the artwork was, everything on screen moved in the same rhythm and read as
 * the same animation recoloured. Each theme now gets the motion its own subject implies:
 *
 *  - PIXEL       discrete 12-step LED tick, no interpolation (a dot matrix has no in-between)
 *  - CYBERPUNK   slow linear scanline pass, then a short hold, then again
 *  - IOS_GLASS   long eased drift; nothing ever snaps, because glass does not
 *  - NEON        fast linear neon pulse on a triangle wave, rising and falling evenly
 *  - RETRO_ARCADE a ball that falls fast and rises slow, like gravity
 *
 * [ThemeMotion.PERIOD_MS] is the nominal cycle; "turbo"/"reduced" in settings scale all of
 * them by the same factor so the speed control still means something across themes.
 */
enum class ThemeMotion { PIXEL, CYBERPUNK, IOS_GLASS, NEON, RETRO_ARCADE }

fun motionForStyle(style: ManagerStyle): ThemeMotion = when (style) {
    ManagerStyle.PIXEL -> ThemeMotion.PIXEL
    ManagerStyle.CYBERPUNK -> ThemeMotion.CYBERPUNK
    ManagerStyle.IOS_GLASS -> ThemeMotion.IOS_GLASS
    ManagerStyle.NEON -> ThemeMotion.NEON
    ManagerStyle.RETRO_ARCADE -> ThemeMotion.RETRO_ARCADE
}

/** Nominal cycle length per theme, in milliseconds, before the speed setting is applied. */
fun basePeriodMsForMotion(motion: ThemeMotion): Int = when (motion) {
    ThemeMotion.PIXEL -> 1400        // a 12-step tick: one step every ~117 ms
    ThemeMotion.CYBERPUNK -> 4200    // slow sweep with a pause
    ThemeMotion.IOS_GLASS -> 9000    // barely moving, which is the point
    ThemeMotion.NEON -> 1800         // brisk electrical pulse
    ThemeMotion.RETRO_ARCADE -> 2600 // one bounce
}

private fun speedFactorFromSettings(): Float = when (ManagerAnimSpeedState.value) {
    "turbo" -> 1f / 1.8f
    "reduced" -> 1f / 0.5f
    else -> 1f
}

/** Shapes the raw 0..1 sweep into the motion the given theme should actually perform. */
fun shapePhaseForMotion(motion: ThemeMotion, raw: Float): Float {
    val t = raw.coerceIn(0f, 1f)
    return when (motion) {
        // No interpolation: the LED steps.
        ThemeMotion.PIXEL -> kotlin.math.floor(t * 12f) / 12f
        // Sweep in the first 80% of the cycle, then hold still (the beam parks off-screen).
        ThemeMotion.CYBERPUNK -> (t / 0.8f).coerceAtMost(1f)
        // Smoothstep: starts and ends at rest, never snaps.
        ThemeMotion.IOS_GLASS -> t * t * (3f - 2f * t)
        // Triangle wave: out and back, evenly, like a pulsing tube.
        ThemeMotion.NEON -> if (t <= 0.5f) t * 2f else (1f - t) * 2f
        // Bounce: falls fast (ease-in), rises slow (ease-out), like gravity.
        ThemeMotion.RETRO_ARCADE -> if (t <= 0.5f) {
            val u = t * 2f
            u * u
        } else {
            val u = (t - 0.5f) * 2f
            1f - (1f - u) * (1f - u)
        }
    }
}

@Composable
fun rememberStylePhase(): State<Float> {
    val context = LocalContext.current
    remember(context) {
        runCatching {
            val prefs = context.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE)
            ManagerStyleState.value = ManagerStyle.fromId(prefs.getString("manager_visual_style", ManagerStyle.PIXEL.id))
            ManagerAnimSpeedState.value = prefs.getString("manager_anim_speed", "normal") ?: "normal"
        }
        true
    }
    val motionEnabled = LocalPixelMotionEnabled.current
    val motion = motionForStyle(ManagerStyleState.value)
    val durationMs = (basePeriodMsForMotion(motion) * speedFactorFromSettings()).toInt().coerceAtLeast(240)
    val raw: State<Float> = if (motionEnabled) {
        val transition = rememberInfiniteTransition(label = "synthetica-65-motion")
        transition.animateFloat(
            initialValue = 0f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = durationMs, easing = LinearEasing),
                repeatMode = RepeatMode.Restart,
            ),
            label = "synthetica-65-raw",
        )
    } else {
        remember { mutableFloatStateOf(0.5f) }
    }
    val rawValue = raw.value
    return remember(motion, rawValue, motionEnabled) {
        // When motion is off the value is a constant, so hold the mid-point rather than
        // the shaped zero, which would park every theme at the top of its cycle.
        mutableFloatStateOf(if (motionEnabled) shapePhaseForMotion(motion, rawValue) else 0.5f)
    }
}

private const val FLAP_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789//:#=[]"

/**
 * Solari Airport Split-Flap mechanical character cycling from Synthetica 2.1 Cyberbrutalist.
 * Settles deterministically to [text] and skips animation immediately when motion is disabled.
 */
@Composable
fun DepartureBoardText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = TextStyle.Default,
    color: Color = Color.Unspecified,
    fontWeight: FontWeight? = null,
    maxLines: Int = 1,
    overflow: TextOverflow = TextOverflow.Ellipsis,
    delayMillis: Int = 0,
    charStaggerMs: Int = 14,
    flapDurationMs: Int = 220,
) {
    val motionEnabled = LocalPixelMotionEnabled.current
    var displayed by remember(text, motionEnabled) { mutableStateOf(text) }

    LaunchedEffect(text, motionEnabled) {
        if (!motionEnabled || text.isEmpty()) {
            displayed = text
            return@LaunchedEffect
        }
        if (delayMillis > 0) delay(delayMillis.toLong())
        val stepMs = 28L
        val totalDuration = (text.length * charStaggerMs + flapDurationMs).coerceAtMost(480)
        var elapsed = 0
        while (elapsed < totalDuration) {
            val sb = StringBuilder(text.length)
            for (i in text.indices) {
                val c = text[i]
                val charStart = i * charStaggerMs
                val charEnd = charStart + flapDurationMs
                when {
                    c == ' ' || c == '\n' -> sb.append(c)
                    elapsed >= charEnd -> sb.append(c)
                    elapsed < charStart -> sb.append(FLAP_CHARS[(i * 5 + elapsed / 28) % FLAP_CHARS.length])
                    else -> {
                        val idx = (i * 11 + elapsed / 28) % FLAP_CHARS.length
                        sb.append(FLAP_CHARS[idx])
                    }
                }
            }
            displayed = sb.toString()
            delay(stepMs)
            elapsed += stepMs.toInt()
        }
        displayed = text
    }

    Text(
        text = displayed,
        modifier = modifier,
        style = style,
        color = color,
        fontWeight = fontWeight,
        maxLines = maxLines,
        overflow = overflow,
    )
}

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

// Chunky, toy-like bevels: everything is squarer than the glass themes but
// still softened, so the retro cabinet reads as furniture rather than paper.
private val RetroShapes = Shapes(
    extraSmall = RoundedCornerShape(3.dp), small = RoundedCornerShape(6.dp),
    medium = RoundedCornerShape(10.dp), large = RoundedCornerShape(14.dp),
    extraLarge = RoundedCornerShape(18.dp),
)
// Anime keeps large soft radii and a pill silhouette; the character comes from
// the colour ramp, the sticker borders and the motion, not from sharp corners.
// Blade-like: long cuts on opposite corners so panels read as heraldic plates.
fun shapesForStyle(style: ManagerStyle): Shapes = when (style) {
    ManagerStyle.PIXEL -> GlassShapes
    ManagerStyle.CYBERPUNK -> CyberShapes
    ManagerStyle.IOS_GLASS -> IosShapes
    ManagerStyle.NEON -> NeonShapes
    ManagerStyle.RETRO_ARCADE -> RetroShapes
}

/** Geometry is shared by the real Manager dock and the non-root UI fixture. */
@Immutable
data class ManagerDockSpec(
    val horizontalMargin: Dp,
    val verticalMargin: Dp,
    val height: Dp,
    val containerShape: Shape,
    val selectedShape: Shape,
    val uppercaseLabels: Boolean = false,
)

fun managerDockSpec(style: ManagerStyle): ManagerDockSpec = when (style) {
    ManagerStyle.PIXEL -> ManagerDockSpec(0.dp, 4.dp, 64.dp, RectangleShape, RectangleShape)
    ManagerStyle.CYBERPUNK -> ManagerDockSpec(8.dp, 8.dp, 72.dp, CyberShapes.extraLarge, CyberShapes.medium, true)
    ManagerStyle.IOS_GLASS -> ManagerDockSpec(28.dp, 12.dp, 68.dp, RoundedCornerShape(36.dp), RoundedCornerShape(26.dp))
    ManagerStyle.NEON -> ManagerDockSpec(16.dp, 10.dp, 66.dp, RoundedCornerShape(18.dp), RoundedCornerShape(12.dp))
    // A real cabinet: near-full-width, tall, labels in the 8-bit face.
    ManagerStyle.RETRO_ARCADE -> ManagerDockSpec(6.dp, 10.dp, 76.dp, RoundedCornerShape(14.dp), RoundedCornerShape(9.dp), true)
    // Floating, narrow, very pill-shaped: the dock should feel like a sticker
    // strip rather than a bar.
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

// Subset builds of OFL faces; see res/font and docs/SYNTHETICA-MANAGER-THEMES-RETRO-ANIME.md.
private val RetroTerminal = FontFamily(Font(R.font.retro_vt323, FontWeight.Normal))
private val RetroPixel = FontFamily(Font(R.font.retro_pressstart, FontWeight.Normal))

/** 1980s arcade cabinet: VT323 terminal headings over an 8-bit label face. */
private val RetroTypography = Typography.copy(
    displaySmall = Typography.displaySmall.copy(fontFamily = RetroTerminal, fontSize = 40.sp),
    headlineMedium = Typography.headlineMedium.copy(fontFamily = RetroTerminal, fontSize = 30.sp),
    headlineSmall = Typography.headlineSmall.copy(fontFamily = RetroTerminal, fontSize = 26.sp),
    titleLarge = Typography.titleLarge.copy(fontFamily = RetroTerminal, fontSize = 23.sp),
    titleMedium = Typography.titleMedium.copy(fontFamily = RetroTerminal, fontSize = 20.sp),
    labelLarge = Typography.labelLarge.copy(fontFamily = RetroPixel, fontSize = 11.sp, letterSpacing = 0.5.sp),
    labelMedium = Typography.labelMedium.copy(fontFamily = RetroPixel, fontSize = 9.sp, letterSpacing = 0.4.sp),
    labelSmall = Typography.labelSmall.copy(fontFamily = RetroPixel, fontSize = 8.sp, letterSpacing = 0.3.sp),
)

fun typographyForStyle(style: ManagerStyle): Typography = when (style) {
    ManagerStyle.PIXEL -> Typography
    ManagerStyle.CYBERPUNK -> CyberTypography
    ManagerStyle.IOS_GLASS -> IosTypography
    ManagerStyle.NEON -> NeonTypography
    ManagerStyle.RETRO_ARCADE -> RetroTypography
}

/** The legacy accent IDs are retained so existing 3.x/4.0 settings migrate. */
/** The default (first) accent for each theme is the one that theme is recognised by. */
fun accentForStyle(style: ManagerStyle, id: String, dark: Boolean): Color =
    accentTierForStyle(style, id, dark)[0]

/**
 * Three saturated accents in the theme's own key, coldest to warmest.
 *
 * These replace the old single-colour accents, which were drawn at 5-30% opacity and
 * therefore read as a faint wash rather than a colour. The ids ("cyan", "pink",
 * "violet", "lime") are legacy keys kept only so existing 3.x/4.0 settings migrate;
 * they no longer describe the colour, so each theme maps them to its own tier.
 */
fun accentTierForStyle(style: ManagerStyle, id: String, dark: Boolean): List<Color> = when (style) {
    // Signal Red, Paper White, Cool Mint: the Nothing/Pixel palette, flat and confident.
    ManagerStyle.PIXEL -> if (dark) when (id) {
        "pink" -> listOf(Color(0xFFF7F6F2), Color(0xFFC9C8C2), Color(0xFF8E8D88))
        "violet" -> listOf(Color(0xFFFFC785), Color(0xFFFFA24D), Color(0xFFD97B1E))
        "lime" -> listOf(Color(0xFF7BE8B4), Color(0xFF35C98C), Color(0xFF1B8F62))
        else -> listOf(Color(0xFFFF5548), Color(0xFFFF8A3D), Color(0xFFFFC785))
    } else when (id) {
        "pink" -> listOf(Color(0xFF242424), Color(0xFF4A4A48), Color(0xFF6E6E6B))
        "violet" -> listOf(Color(0xFF9A5A00), Color(0xFFB96E00), Color(0xFF7A4400))
        "lime" -> listOf(Color(0xFF1B7A58), Color(0xFF0F5E44), Color(0xFF2E9E76))
        else -> listOf(Color(0xFFC1231C), Color(0xFF9A1A14), Color(0xFFE2552B))
    }
    // Acid Volt, Plasma Magenta, Warning Amber: the high-visibility end of a cyber deck.
    ManagerStyle.CYBERPUNK -> if (dark) when (id) {
        "pink" -> listOf(Color(0xFFFF2E88), Color(0xFFFF6FB1), Color(0xFFB8005C))
        "violet" -> listOf(Color(0xFF4BC8FF), Color(0xFF2E8BFF), Color(0xFF9AE4FF))
        "lime" -> listOf(Color(0xFFB8FF2E), Color(0xFF7CFF6B), Color(0xFF3DDC4B))
        else -> listOf(Color(0xFFD4FF00), Color(0xFF9CFF3B), Color(0xFFFBFF9E))
    } else when (id) {
        "pink" -> listOf(Color(0xFFC40056), Color(0xFF96003F), Color(0xFFE8177E))
        "violet" -> listOf(Color(0xFF0060C8), Color(0xFF004494), Color(0xFF0090E0))
        "lime" -> listOf(Color(0xFF3D6400), Color(0xFF2A4700), Color(0xFF5C8C00))
        else -> listOf(Color(0xFF5A6600), Color(0xFF3F4A00), Color(0xFF7E8C00))
    }
    // System Blue, Mint, Lilac: iOS tint colours, clear and unblended.
    ManagerStyle.IOS_GLASS -> if (dark) when (id) {
        "pink" -> listOf(Color(0xFFFF4F94), Color(0xFFFF7FB0), Color(0xFFD62C6E))
        "violet" -> listOf(Color(0xFFA97BFF), Color(0xFFC9A6FF), Color(0xFF7C4DFF))
        "lime" -> listOf(Color(0xFF30D9A7), Color(0xFF6BF0C8), Color(0xFF12B487))
        else -> listOf(Color(0xFF3E9BFF), Color(0xFF6FB8FF), Color(0xFF1E6FD9))
    } else when (id) {
        "pink" -> listOf(Color(0xFFC2186B), Color(0xFF9C0F55), Color(0xFFE03A88))
        "violet" -> listOf(Color(0xFF5A2EC4), Color(0xFF45219A), Color(0xFF7B51E0))
        "lime" -> listOf(Color(0xFF0A8567), Color(0xFF06684F), Color(0xFF14A583))
        else -> listOf(Color(0xFF0A6CD9), Color(0xFF0854AB), Color(0xFF2E8BE8))
    }
    // Cyan, Magenta, Lime: the three tubes a neon sign is actually built from.
    ManagerStyle.NEON -> if (dark) when (id) {
        "pink" -> listOf(Color(0xFFFF2BD6), Color(0xFFFF6BE4), Color(0xFFC81AA6))
        "violet" -> listOf(Color(0xFF9B4BFF), Color(0xFFBC7BFF), Color(0xFF6F1FD9))
        "lime" -> listOf(Color(0xFF7DFF3E), Color(0xFFA8FF7B), Color(0xFF4FCC19))
        else -> listOf(Color(0xFF00F0FF), Color(0xFF5BF6FF), Color(0xFF00B8CC))
    } else when (id) {
        "pink" -> listOf(Color(0xFFC1008F), Color(0xFF96006E), Color(0xFFD91FA6))
        "violet" -> listOf(Color(0xFF6A0FD0), Color(0xFF4E08A0), Color(0xFF8A34E8))
        "lime" -> listOf(Color(0xFF3E8A00), Color(0xFF2C6400), Color(0xFF56B000))
        else -> listOf(Color(0xFF00707E), Color(0xFF00545F), Color(0xFF0092A3))
    }
    // Warm arcade CRT phosphor: amber default, plus the orange "ball" and mint "1UP".
    ManagerStyle.RETRO_ARCADE -> if (dark) when (id) {
        "pink" -> listOf(Color(0xFFFF8B3D), Color(0xFFFFB06B), Color(0xFFD96A1E))
        "violet" -> listOf(Color(0xFFFFD24A), Color(0xFFFFE68C), Color(0xFFD9A81E))
        "lime" -> listOf(Color(0xFF7BF0A8), Color(0xFFA8FFC9), Color(0xFF3DCC70))
        else -> listOf(Color(0xFFFFB000), Color(0xFFFFCC4D), Color(0xFFD98E00))
    } else when (id) {
        "pink" -> listOf(Color(0xFF9E3B10), Color(0xFF7A2B08), Color(0xFFBE4F1E))
        "violet" -> listOf(Color(0xFF8A5A00), Color(0xFF6B4500), Color(0xFFAA7200))
        "lime" -> listOf(Color(0xFF1C6B3A), Color(0xFF12502A), Color(0xFF2A8A4C))
        else -> listOf(Color(0xFF8A4A00), Color(0xFF6B3900), Color(0xFFAA5F00))
    }
}

/**
 * A colour the theme is identified by, used for signature details (glow, emblem ring,
 * data strip) so a screen reads as "this theme" at a glance even before the accent is
 * noticed.
 */
fun signatureColorForStyle(style: ManagerStyle, dark: Boolean): Color = when (style) {
    ManagerStyle.PIXEL -> if (dark) Color(0xFFFF5548) else Color(0xFFC1231C)
    ManagerStyle.CYBERPUNK -> if (dark) Color(0xFFD4FF00) else Color(0xFF5A6600)
    ManagerStyle.IOS_GLASS -> if (dark) Color(0xFF3E9BFF) else Color(0xFF0A6CD9)
    ManagerStyle.NEON -> if (dark) Color(0xFFFF2BD6) else Color(0xFFC1008F)
    ManagerStyle.RETRO_ARCADE -> if (dark) Color(0xFF7BF0A8) else Color(0xFF1C6B3A)
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
            blurRadius = 10.dp, dockBlurRadius = 14.dp,
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFEAF2FC), cardTintTop = Color.White, cardTintBottom = Color(0xFFF2F7FE),
            elevatedTintTop = Color.White, elevatedTintBottom = Color(0xFFF5F9FF),
            barTintTop = Color(0xFFF8FBFF), barTintBottom = Color(0xFFF2F7FC),
            dockTintTop = Color.White, dockTintBottom = Color(0xFFEAF3FC),
            borderHighlight = Color(0xFFC0D2E5), borderMid = Color(0xFFD8E5F3), borderShadow = Color(0xFFB0C6DC),
            divider = Color(0xFFD1DDEA), shadowColor = Color(0x220B2849),
            blurRadius = 10.dp, dockBlurRadius = 14.dp,
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
        ManagerStyle.RETRO_ARCADE -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF17120C), cardTintTop = Color(0xFF241C13), cardTintBottom = Color(0xFF1E1710),
            elevatedTintTop = Color(0xFF2E2418), elevatedTintBottom = Color(0xFF241C13),
            barTintTop = Color(0xFF1B150E), barTintBottom = Color(0xFF1B150E),
            dockTintTop = Color(0xFF2A2015), dockTintBottom = Color(0xFF1C160F),
            borderHighlight = Color(0xFFB98A4E), borderMid = Color(0xFF6B4E2E), borderShadow = Color(0xFF3A2A19),
            divider = Color(0xFF4A3823), shadowColor = Color.Transparent,
            innerHighlight = Color(0xFFF0D9A8),
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFF3E7CF), cardTintTop = Color(0xFFFFF8EA), cardTintBottom = Color(0xFFF7EAD3),
            elevatedTintTop = Color(0xFFFFFBF2), elevatedTintBottom = Color(0xFFF7EAD3),
            barTintTop = Color(0xFFF3E7CF), barTintBottom = Color(0xFFEADCC2),
            dockTintTop = Color(0xFFFFF8EA), dockTintBottom = Color(0xFFE7D6B4),
            borderHighlight = Color(0xFF6B4E2E), borderMid = Color(0xFFA98A5E), borderShadow = Color(0xFF6B4E2E),
            divider = Color(0xFFC9B490), shadowColor = Color(0x3317120C),
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
