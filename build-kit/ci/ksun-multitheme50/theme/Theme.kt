package com.rifsxd.ksunext.ui.theme

import android.animation.ValueAnimator
import android.content.Context
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.annotation.StringRes
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.rifsxd.ksunext.R

@Immutable
data class GlassStyle(
    val isDark: Boolean,
    val isAmoled: Boolean,
    val canvasBase: Color,
    val cardTintTop: Color,
    val cardTintBottom: Color,
    val elevatedTintTop: Color,
    val elevatedTintBottom: Color,
    val barTintTop: Color,
    val barTintBottom: Color,
    val dockTintTop: Color,
    val dockTintBottom: Color,
    val dockActivePill: Color,
    val innerHighlight: Color,
    val borderHighlight: Color,
    val borderMid: Color,
    val borderShadow: Color,
    val divider: Color,
    val shadowColor: Color,
    val blurRadius: Dp,
    val dockBlurRadius: Dp,
)

// Opaque, quiet plates keep important text readable on light, dark and AMOLED.
val DarkGlassStyle = GlassStyle(
    isDark = true, isAmoled = false,
    canvasBase = DarkCanvasBase,
    cardTintTop = Color(0xFF1C1C1A), cardTintBottom = Color(0xFF1C1C1A),
    elevatedTintTop = Color(0xFF222220), elevatedTintBottom = Color(0xFF222220),
    barTintTop = Color(0xFF10100F), barTintBottom = Color(0xFF10100F),
    dockTintTop = Color(0xFF1B1B19), dockTintBottom = Color(0xFF1B1B19),
    dockActivePill = Color(0x55FF665E), innerHighlight = Color(0x22FFFFFF),
    borderHighlight = Color(0xFF494945), borderMid = Color(0xFF383835),
    borderShadow = Color(0xFF383835), divider = Color(0xFF41413D),
    shadowColor = Color.Transparent, blurRadius = 0.dp, dockBlurRadius = 0.dp,
)
val LightGlassStyle = GlassStyle(
    isDark = false, isAmoled = false,
    canvasBase = LightCanvasBase,
    cardTintTop = Color(0xFFFFFFFF), cardTintBottom = Color(0xFFFFFFFF),
    elevatedTintTop = Color(0xFFFFFFFF), elevatedTintBottom = Color(0xFFFFFFFF),
    barTintTop = Color(0xFFF2F1ED), barTintBottom = Color(0xFFF2F1ED),
    dockTintTop = Color(0xFFFFFFFF), dockTintBottom = Color(0xFFFFFFFF),
    dockActivePill = Color(0x33AD231D), innerHighlight = Color(0x22000000),
    borderHighlight = Color(0xFFCBCBC5), borderMid = Color(0xFFDEDED8),
    borderShadow = Color(0xFFCBCBC5), divider = Color(0xFFDFDFD9),
    shadowColor = Color.Transparent, blurRadius = 0.dp, dockBlurRadius = 0.dp,
)
val AmoledGlassStyle = DarkGlassStyle.copy(
    isAmoled = true, canvasBase = Color.Black,
    cardTintTop = Color(0xFF121212), cardTintBottom = Color(0xFF121212),
    barTintTop = Color.Black, barTintBottom = Color.Black,
)
val LocalGlassStyle = staticCompositionLocalOf { DarkGlassStyle }
val LocalNeonGlow = staticCompositionLocalOf { 1f }
// Page transitions use this as well as Compose's system animation-duration scale.
val LocalPixelMotionEnabled = staticCompositionLocalOf { false }

@Immutable
data class NeonAccentOption(val id: String, @StringRes val label: Int, val color: Color)
// Keep 3.x preference identifiers while mapping them to the new palette.
val NeonAccentOptions = listOf(
    NeonAccentOption("cyan", R.string.neon_accent_cyan, Color(0xFFFF665E)),
    NeonAccentOption("pink", R.string.neon_accent_pink, Color(0xFFF4F3ED)),
    NeonAccentOption("violet", R.string.neon_accent_violet, Color(0xFFFFC785)),
    NeonAccentOption("lime", R.string.neon_accent_lime, Color(0xFFAFE2C5)),
)
val NeonAccentState = mutableStateOf("cyan")
val NeonMotionState = mutableStateOf(true)
val NeonThemeState = mutableStateOf("system")
val NeonGlowState = mutableStateOf("bright")
val ManagerStyleState = mutableStateOf(ManagerStyle.PIXEL)
val LocalNeonPhase = staticCompositionLocalOf<State<Float>> { mutableFloatStateOf(0.5f) }
private var prefsInitialized = false

private fun resolveAccent(id: String?): NeonAccentOption =
    NeonAccentOptions.firstOrNull { it.id == id } ?: NeonAccentOptions.first()

private fun resolveTheme(id: String?): String =
    if (id in listOf("system", "light", "dark", "amoled")) id!! else "system"

private fun resolveGlow(id: String?): String =
    if (id in listOf("subtle", "normal", "bright")) id!! else "bright"

private fun syncNeonPrefs(context: Context) {
    if (prefsInitialized) return
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    NeonAccentState.value = resolveAccent(prefs.getString("neon_accent", "cyan")).id
    NeonMotionState.value = prefs.getBoolean("neon_motion", true)
    // Preserve an existing AMOLED choice when upgrading the old Manager.
    val legacyTheme = if (prefs.getBoolean("enable_amoled", false)) "amoled" else "system"
    NeonThemeState.value = resolveTheme(prefs.getString("neon_theme", legacyTheme))
    NeonGlowState.value = resolveGlow(prefs.getString("neon_glow", "bright"))
    // Existing installs keep Pixel until a design is explicitly selected.
    ManagerStyleState.value = ManagerStyle.fromId(prefs.getString("manager_visual_style", "pixel"))
    prefsInitialized = true
}

fun setManagerStyle(context: Context, id: String) {
    val style = ManagerStyle.fromId(id)
    ManagerStyleState.value = style
    context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        .edit().putString("manager_visual_style", style.id).apply()
}

fun setNeonAccent(context: Context, id: String) {
    val resolved = resolveAccent(id).id
    NeonAccentState.value = resolved
    context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        .edit().putString("neon_accent", resolved).apply()
}
fun setNeonMotion(context: Context, enabled: Boolean) {
    NeonMotionState.value = enabled
    context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        .edit().putBoolean("neon_motion", enabled).apply()
}
fun setNeonTheme(context: Context, id: String) {
    val resolved = resolveTheme(id)
    NeonThemeState.value = resolved
    context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        .edit().putString("neon_theme", resolved).apply()
}
fun setNeonGlow(context: Context, id: String) {
    val resolved = resolveGlow(id)
    NeonGlowState.value = resolved
    context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        .edit().putString("neon_glow", resolved).apply()
}

private fun systemAnimationsEnabled(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.O || ValueAnimator.areAnimatorsEnabled()

fun Color.blend(other: Color, ratio: Float): Color {
    val inverse = 1f - ratio
    return Color(red * inverse + other.red * ratio, green * inverse + other.green * ratio,
        blue * inverse + other.blue * ratio, alpha)
}

private val NeonDarkScheme = darkColorScheme(
    primary = PRIMARY, onPrimary = Color(0xFF1A0605),
    primaryContainer = Color(0xFF54231F), onPrimaryContainer = Color(0xFFFFE3DF),
    secondary = Color(0xFFDADAD4), onSecondary = Color(0xFF1B1B19),
    tertiary = Color(0xFFFFC785), onTertiary = Color(0xFF2B1A00),
    background = DarkCanvasBase, onBackground = DarkInkPrimary,
    surface = Color(0xFF1C1C1A), onSurface = DarkInkPrimary,
    surfaceVariant = Color(0xFF292927), onSurfaceVariant = DarkInkSecondary,
    surfaceContainerLowest = Color(0xFF0D0D0C), surfaceContainerLow = Color(0xFF171716),
    surfaceContainer = Color(0xFF1C1C1A), surfaceContainerHigh = Color(0xFF252523),
    surfaceContainerHighest = Color(0xFF30302D), outline = Color(0xFF999992),
    outlineVariant = Color(0xFF494945), error = Color(0xFFFF746C),
    onError = Color(0xFF3B0906), errorContainer = Color(0xFF5A1915),
    onErrorContainer = Color(0xFFFFDAD6),
)
private val NeonLightScheme = lightColorScheme(
    primary = Color(0xFFAD231D), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFDAD6), onPrimaryContainer = Color(0xFF410400),
    secondary = Color(0xFF41413D), onSecondary = Color.White,
    tertiary = Color(0xFF865000), onTertiary = Color.White,
    background = LightCanvasBase, onBackground = LightInkPrimary,
    surface = Color.White, onSurface = LightInkPrimary,
    surfaceVariant = Color(0xFFE8E7E1), onSurfaceVariant = LightInkSecondary,
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFFAF9F5),
    surfaceContainer = Color(0xFFF2F1ED), surfaceContainerHigh = Color(0xFFECEBE5),
    surfaceContainerHighest = Color(0xFFE3E2DC), outline = Color(0xFF666660),
    outlineVariant = Color(0xFFCACAC3), error = Color(0xFFB3261E),
    onError = Color.White, errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
)

/** One shared draw-phase pulse; stopped whenever the app is not resumed. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun KernelSUTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    amoledMode: Boolean = false,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    LaunchedEffect(context) { syncNeonPrefs(context) }
    val lifecycleOwner = LocalLifecycleOwner.current
    var systemAllowsMotion by remember { mutableStateOf(systemAnimationsEnabled()) }
    var resumed by remember(lifecycleOwner) {
        mutableStateOf(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED))
    }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                systemAllowsMotion = systemAnimationsEnabled()
                resumed = true
            } else if (event == Lifecycle.Event.ON_PAUSE) {
                resumed = false
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    val motionEnabled = NeonMotionState.value && systemAllowsMotion && resumed
    val style = ManagerStyleState.value
    // The glass style has no animated background; skip the decorative clock.
    val phase: State<Float> = if (motionEnabled && style != ManagerStyle.IOS_GLASS) {
        val motion = rememberInfiniteTransition(label = "pixel-signal")
        motion.animateFloat(
            initialValue = 0f, targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(3200, easing = FastOutSlowInEasing), RepeatMode.Reverse),
            label = "pixel-pulse",
        )
    } else remember { mutableFloatStateOf(0.5f) }

    val themeChoice = NeonThemeState.value
    val isDark = when (themeChoice) {
        "light" -> false
        "dark", "amoled" -> true
        else -> darkTheme
    }
    val isAmoled = themeChoice == "amoled"
    val accent = accentForStyle(style, NeonAccentState.value, isDark)
    val base = if (isDark) NeonDarkScheme else NeonLightScheme
    val palette = paletteForStyle(style, isDark, isAmoled, base)
    val scheme = palette.scheme.copy(
        primary = accent,
        onPrimary = if (isDark) Color(0xFF101118) else Color.White,
        primaryContainer = if (isDark) accent.blend(Color(0xFF161923), 0.80f) else accent.blend(Color.White, 0.84f),
        onPrimaryContainer = if (isDark) accent.blend(Color.White, 0.25f) else Color(0xFF161923),
        surfaceTint = accent,
    )
    val glass = palette.glass
    val glow = when (NeonGlowState.value) { "subtle" -> 0.65f; "normal" -> 1f; else -> 1.55f }
    val activity = context as? ComponentActivity
    SideEffect {
        val transparent = Color.Transparent.toArgb()
        val bars = if (isDark) SystemBarStyle.dark(transparent) else SystemBarStyle.light(transparent, transparent)
        activity?.enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
    }
    CompositionLocalProvider(
        LocalGlassStyle provides glass, LocalNeonPhase provides phase, LocalNeonGlow provides glow,
        LocalPixelMotionEnabled provides motionEnabled, LocalManagerStyle provides style,
    ) {
        MaterialTheme(colorScheme = scheme, typography = typographyForStyle(style),
            shapes = shapesForStyle(style), content = content)
    }
}
