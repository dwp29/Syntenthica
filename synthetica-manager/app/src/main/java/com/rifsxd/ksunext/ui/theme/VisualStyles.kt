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
    RETRO_ARCADE("retro_arcade"), ANIME_WIBU("anime_wibu"), GOTHIC_CRIMSON("gothic_crimson");

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
        put("schema", "synthetica-manager-6.0.0")
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
    ManagerStyle.ANIME_WIBU -> R.drawable.ic_emblem_anime
    ManagerStyle.GOTHIC_CRIMSON -> R.drawable.ic_emblem_gothic
}

/** Distinct splash edition label per theme (preserves the ' // MANAGER 6.0.0' marker). */
fun splashTagForStyle(style: ManagerStyle): String = when (style) {
    ManagerStyle.PIXEL -> "PIXEL // MANAGER 6.0.0"
    ManagerStyle.CYBERPUNK -> "CYBERPUNK // MANAGER 6.0.0"
    ManagerStyle.IOS_GLASS -> "GLASS // MANAGER 6.0.0"
    ManagerStyle.NEON -> "NEON // MANAGER 6.0.0"
    ManagerStyle.RETRO_ARCADE -> "RETRO ARCADE // MANAGER 6.0.0"
    ManagerStyle.ANIME_WIBU -> "ANIME WIBU // MANAGER 6.0.0"
    ManagerStyle.GOTHIC_CRIMSON -> "GOTHIC CRIMSON // MANAGER 6.0.0"
}

/**
 * Synchronizes preferences on Frame 0 so cold-start splash immediately uses the saved theme,
 * and drives continuous 0..1 animations for all 4 styles (including IOS_GLASS) when motion is on.
 */
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
    val durationMs = when (ManagerAnimSpeedState.value) {
        "turbo" -> 1400
        "reduced" -> 4800
        else -> 2600
    }
    return if (motionEnabled) {
        val transition = rememberInfiniteTransition(label = "synthetica-501-motion")
        transition.animateFloat(
            initialValue = 0f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = durationMs, easing = LinearEasing),
                repeatMode = RepeatMode.Restart,
            ),
            label = "synthetica-501-phase",
        )
    } else {
        remember { mutableFloatStateOf(0.5f) }
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
private val AnimeShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp), small = RoundedCornerShape(16.dp),
    medium = RoundedCornerShape(24.dp), large = RoundedCornerShape(30.dp),
    extraLarge = RoundedCornerShape(36.dp),
)

// Blade-like: long cuts on opposite corners so panels read as heraldic plates.
private val GothicShapes = Shapes(
    extraSmall = CutCornerShape(topStart = 0.dp, topEnd = 4.dp, bottomEnd = 0.dp, bottomStart = 4.dp),
    small = CutCornerShape(topStart = 0.dp, topEnd = 8.dp, bottomEnd = 0.dp, bottomStart = 8.dp),
    medium = CutCornerShape(topStart = 2.dp, topEnd = 14.dp, bottomEnd = 2.dp, bottomStart = 14.dp),
    large = CutCornerShape(topStart = 4.dp, topEnd = 20.dp, bottomEnd = 4.dp, bottomStart = 20.dp),
    extraLarge = CutCornerShape(topStart = 6.dp, topEnd = 28.dp, bottomEnd = 6.dp, bottomStart = 28.dp),
)

fun shapesForStyle(style: ManagerStyle): Shapes = when (style) {
    ManagerStyle.PIXEL -> GlassShapes
    ManagerStyle.CYBERPUNK -> CyberShapes
    ManagerStyle.IOS_GLASS -> IosShapes
    ManagerStyle.NEON -> NeonShapes
    ManagerStyle.RETRO_ARCADE -> RetroShapes
    ManagerStyle.ANIME_WIBU -> AnimeShapes
    ManagerStyle.GOTHIC_CRIMSON -> GothicShapes
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
    ManagerStyle.ANIME_WIBU -> ManagerDockSpec(34.dp, 16.dp, 70.dp, RoundedCornerShape(40.dp), RoundedCornerShape(30.dp))
    ManagerStyle.GOTHIC_CRIMSON -> ManagerDockSpec(10.dp, 8.dp, 72.dp, GothicShapes.extraLarge, GothicShapes.small, true)
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

private val AnimeRounded = FontFamily(Font(R.font.anime_zenmaru, FontWeight.Normal))
private val AnimeDisplay = FontFamily(Font(R.font.anime_rampart, FontWeight.Normal))

/**
 * Anime/wibu: a rounded gothic body face carries Japanese glyphs too, while the
 * display face is only ever used for Latin headings because it has no kana.
 */
private val AnimeTypography = Typography.copy(
    displaySmall = Typography.displaySmall.copy(fontFamily = AnimeDisplay, fontSize = 30.sp),
    headlineMedium = Typography.headlineMedium.copy(fontFamily = AnimeRounded, fontSize = 25.sp),
    headlineSmall = Typography.headlineSmall.copy(fontFamily = AnimeRounded, fontSize = 22.sp),
    titleLarge = Typography.titleLarge.copy(fontFamily = AnimeRounded, fontSize = 19.sp),
    titleMedium = Typography.titleMedium.copy(fontFamily = AnimeRounded, fontSize = 17.sp),
    bodyLarge = Typography.bodyLarge.copy(fontFamily = AnimeRounded),
    bodyMedium = Typography.bodyMedium.copy(fontFamily = AnimeRounded),
    bodySmall = Typography.bodySmall.copy(fontFamily = AnimeRounded),
    labelLarge = Typography.labelLarge.copy(fontFamily = AnimeRounded, letterSpacing = 0.2.sp),
    labelMedium = Typography.labelMedium.copy(fontFamily = AnimeRounded),
)

/**
 * Gothic crimson: a high-contrast serif stands in for blackletter. A real
 * fraktur face would be more faithful, but it needs its own subset and licence;
 * the serif keeps the heraldic tone without shipping another megabyte.
 */
private val GothicTypography = Typography.copy(
    displaySmall = Typography.displaySmall.copy(fontFamily = FontFamily.Serif, fontSize = 30.sp, letterSpacing = 0.5.sp),
    headlineMedium = Typography.headlineMedium.copy(fontFamily = FontFamily.Serif, fontSize = 24.sp, letterSpacing = 0.4.sp),
    headlineSmall = Typography.headlineSmall.copy(fontFamily = FontFamily.Serif, fontSize = 21.sp),
    titleLarge = Typography.titleLarge.copy(fontFamily = FontFamily.Serif, fontSize = 18.sp),
    labelLarge = Typography.labelLarge.copy(fontFamily = FontFamily.Serif, letterSpacing = 0.6.sp),
)

fun typographyForStyle(style: ManagerStyle): Typography = when (style) {
    ManagerStyle.PIXEL -> Typography
    ManagerStyle.CYBERPUNK -> CyberTypography
    ManagerStyle.IOS_GLASS -> IosTypography
    ManagerStyle.NEON -> NeonTypography
    ManagerStyle.RETRO_ARCADE -> RetroTypography
    ManagerStyle.ANIME_WIBU -> AnimeTypography
    ManagerStyle.GOTHIC_CRIMSON -> GothicTypography
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
    // Warm arcade CRT: amber as the default, with an orange "ball" and a mint
    // "1UP" reading as the other accents. Light mode darkens each for contrast.
    ManagerStyle.RETRO_ARCADE -> if (dark) when (id) {
        "pink" -> Color(0xFFFF9A6B); "violet" -> Color(0xFFFFD27A); "lime" -> Color(0xFF9BF0B4); else -> Color(0xFFFFB347)
    } else when (id) {
        "pink" -> Color(0xFF9E3B10); "violet" -> Color(0xFF8A5A00); "lime" -> Color(0xFF1C6B3A); else -> Color(0xFF8A4A00)
    }
    // Candy pop: strawberry as the default, then soda blue, matcha and grape.
    ManagerStyle.ANIME_WIBU -> if (dark) when (id) {
        "pink" -> Color(0xFFFF7FB2); "violet" -> Color(0xFFC9A3FF); "lime" -> Color(0xFF9FE8C0); else -> Color(0xFF7FD8FF)
    } else when (id) {
        "pink" -> Color(0xFFB3125A); "violet" -> Color(0xFF6A3BB8); "lime" -> Color(0xFF14764F); else -> Color(0xFF00697F)
    }
    // Blood crimson is the only loud colour; steel and bone are the rest.
    ManagerStyle.GOTHIC_CRIMSON -> if (dark) when (id) {
        "pink" -> Color(0xFFFF4D5E); "violet" -> Color(0xFFC9CBD4); "lime" -> Color(0xFF8FD9A8); else -> Color(0xFFE01B2E)
    } else when (id) {
        "pink" -> Color(0xFF9B1220); "violet" -> Color(0xFF4A4E59); "lime" -> Color(0xFF1F6B3A); else -> Color(0xFF8A0F1B)
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
        ManagerStyle.GOTHIC_CRIMSON -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF0A0708), cardTintTop = Color(0xFF15100F), cardTintBottom = Color(0xFF110D0C),
            elevatedTintTop = Color(0xFF1C1514), elevatedTintBottom = Color(0xFF15100F),
            barTintTop = Color(0xFF0D0908), barTintBottom = Color(0xFF0D0908),
            dockTintTop = Color(0xFF1A1211), dockTintBottom = Color(0xFF100B0A),
            borderHighlight = Color(0xFF8E1B24), borderMid = Color(0xFF4A1218), borderShadow = Color(0xFF280609),
            divider = Color(0xFF3A0E12), shadowColor = Color.Transparent,
            innerHighlight = Color(0xFFE8C9C9),
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFF3EDE8), cardTintTop = Color(0xFFFBF6F2), cardTintBottom = Color(0xFFF3E9E2),
            elevatedTintTop = Color(0xFFFFFBF8), elevatedTintBottom = Color(0xFFF3E9E2),
            barTintTop = Color(0xFFF7F0EA), barTintBottom = Color(0xFFF0E4DC),
            dockTintTop = Color(0xFFFBF6F2), dockTintBottom = Color(0xFFEDE0D7),
            borderHighlight = Color(0xFF6E1018), borderMid = Color(0xFFB08A7E), borderShadow = Color(0xFF6E1018),
            divider = Color(0xFFD3BDB0), shadowColor = Color(0x330A0708),
        )
        ManagerStyle.ANIME_WIBU -> if (dark) DarkGlassStyle.copy(
            canvasBase = Color(0xFF15102A), cardTintTop = Color(0xFF241A44), cardTintBottom = Color(0xFF1C1438),
            elevatedTintTop = Color(0xFF2F2258), elevatedTintBottom = Color(0xFF241A44),
            barTintTop = Color(0xFF191230), barTintBottom = Color(0xFF191230),
            dockTintTop = Color(0xFF2C2054), dockTintBottom = Color(0xFF1B1438),
            borderHighlight = Color(0xFFB08CFF), borderMid = Color(0xFF6B54A8), borderShadow = Color(0xFF3B2D6B),
            divider = Color(0xFF43346F), shadowColor = Color(0x66000000),
            blurRadius = 8.dp, dockBlurRadius = 12.dp,
        ) else LightGlassStyle.copy(
            canvasBase = Color(0xFFFDF1F8), cardTintTop = Color.White, cardTintBottom = Color(0xFFFFF5FB),
            elevatedTintTop = Color.White, elevatedTintBottom = Color(0xFFFFF7FC),
            barTintTop = Color(0xFFFFF9FD), barTintBottom = Color(0xFFFFF0F9),
            dockTintTop = Color.White, dockTintBottom = Color(0xFFFDE9F5),
            borderHighlight = Color(0xFFE39BC4), borderMid = Color(0xFFF2C9E0), borderShadow = Color(0xFFD98BB8),
            divider = Color(0xFFF4D7E8), shadowColor = Color(0x22B3125A),
            blurRadius = 8.dp, dockBlurRadius = 12.dp,
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
