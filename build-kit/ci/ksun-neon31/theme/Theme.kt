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

val DarkGlassStyle = GlassStyle(
    isDark = true, isAmoled = false,
    canvasBase = DarkCanvasBase,
    cardTintTop = Color(0xF2111930), cardTintBottom = Color(0xF20A0D20),
    elevatedTintTop = Color(0xF6192040), elevatedTintBottom = Color(0xF2090D22),
    barTintTop = Color(0xF2070B1D), barTintBottom = Color(0xF20A0E22),
    dockTintTop = Color(0xF2131B32), dockTintBottom = Color(0xF5080B1D),
    dockActivePill = Color(0x665AEFFF), innerHighlight = Color(0x335AEFFF),
    borderHighlight = Color(0xAA5AEFFF), borderMid = Color(0x667D81FF),
    borderShadow = Color(0x88FF66CE), divider = Color(0x334EA5D0),
    shadowColor = Color(0x995AEFFF), blurRadius = 0.dp, dockBlurRadius = 0.dp,
)

// Light mode has its own opaque plates and dark ink; it is not a dark palette
// with a white background. Contrast remains readable for every accent.
val LightGlassStyle = GlassStyle(
    isDark = false, isAmoled = false,
    canvasBase = LightCanvasBase,
    cardTintTop = Color(0xFFFDFEFF), cardTintBottom = Color(0xFFF1F5FF),
    elevatedTintTop = Color(0xFFFFFFFF), elevatedTintBottom = Color(0xFFF0F4FF),
    barTintTop = Color(0xFFF8FBFF), barTintBottom = Color(0xFFF0F5FF),
    dockTintTop = Color(0xFFFDFEFF), dockTintBottom = Color(0xFFF0F4FF),
    dockActivePill = Color(0x33006078), innerHighlight = Color(0x22006078),
    borderHighlight = Color(0xAA006078), borderMid = Color(0x77563F9C),
    borderShadow = Color(0x668E275F), divider = Color(0x33506580),
    shadowColor = Color(0x44006078), blurRadius = 0.dp, dockBlurRadius = 0.dp,
)
val AmoledGlassStyle = DarkGlassStyle.copy(
    isAmoled = true, canvasBase = Color.Black,
    cardTintTop = Color(0xF20D1224), cardTintBottom = Color(0xF2050612),
    barTintTop = Color(0xF2000000), barTintBottom = Color(0xF2080A18),
)
val LocalGlassStyle = staticCompositionLocalOf { DarkGlassStyle }
val LocalNeonGlow = staticCompositionLocalOf { 1.55f }

@Immutable
data class NeonAccentOption(val id: String, @StringRes val label: Int, val color: Color)
val NeonAccentOptions = listOf(
    NeonAccentOption("cyan", R.string.neon_accent_cyan, Color(0xFF5AEFFF)),
    NeonAccentOption("pink", R.string.neon_accent_pink, Color(0xFFFF86D8)),
    NeonAccentOption("violet", R.string.neon_accent_violet, Color(0xFFD4A7FF)),
    NeonAccentOption("lime", R.string.neon_accent_lime, Color(0xFFBAFF87)),
)
val NeonAccentState = mutableStateOf("cyan")
val NeonMotionState = mutableStateOf(true)
val NeonThemeState = mutableStateOf("system")
val NeonGlowState = mutableStateOf("bright")
val LocalNeonPhase = staticCompositionLocalOf<State<Float>> { mutableFloatStateOf(0.5f) }
private var prefsInitialized = false

private fun resolveAccent(id: String?): NeonAccentOption =
    NeonAccentOptions.firstOrNull { it.id == id } ?: NeonAccentOptions.first()

private fun resolveTheme(id: String?): String =
    if (id in listOf("system", "light", "dark", "amoled")) id!! else "system"

private fun resolveGlow(id: String?): String =
    if (id in listOf("subtle", "normal", "bright")) id!! else "bright"

private fun lightAccent(id: String): Color = when (id) {
    "pink" -> Color(0xFF9C0063)
    "violet" -> Color(0xFF6631A1)
    "lime" -> Color(0xFF2D6515)
    else -> Color(0xFF006078)
}

private fun syncNeonPrefs(context: Context) {
    if (prefsInitialized) return
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    NeonAccentState.value = resolveAccent(prefs.getString("neon_accent", "cyan")).id
    NeonMotionState.value = prefs.getBoolean("neon_motion", true)
    // Preserve an existing AMOLED choice when upgrading the old Manager.
    val legacyTheme = if (prefs.getBoolean("enable_amoled", false)) "amoled" else "system"
    NeonThemeState.value = resolveTheme(prefs.getString("neon_theme", legacyTheme))
    NeonGlowState.value = resolveGlow(prefs.getString("neon_glow", "bright"))
    prefsInitialized = true
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
    primary = IosBlueDark, onPrimary = Color(0xFF061018),
    primaryContainer = Color(0xFF103346), onPrimaryContainer = Color(0xFFD3FAFF),
    secondary = IosPinkDark, onSecondary = Color(0xFF24051B),
    tertiary = IosPurpleDark, onTertiary = Color(0xFF210E39),
    background = DarkCanvasBase, onBackground = DarkInkPrimary,
    surface = Color(0xF20C1022), onSurface = DarkInkPrimary,
    surfaceVariant = Color(0xFF151B31), onSurfaceVariant = DarkInkSecondary,
    surfaceContainerLowest = Color(0xFF050714), surfaceContainerLow = Color(0xFF0D1123),
    surfaceContainer = Color(0xFF11172A), surfaceContainerHigh = Color(0xFF182039),
    surfaceContainerHighest = Color(0xFF202A45), outline = Color(0xFF64869F),
    outlineVariant = Color(0xFF26394E), error = IosRedDark,
    onError = Color(0xFF340A13), errorContainer = Color(0xFF4E1425),
    onErrorContainer = Color(0xFFFFDAE1),
)
private val NeonLightScheme = lightColorScheme(
    primary = Color(0xFF006078), onPrimary = Color.White,
    primaryContainer = Color(0xFFC7F0FA), onPrimaryContainer = Color(0xFF002E3C),
    secondary = Color(0xFF9C0063), onSecondary = Color.White,
    tertiary = Color(0xFF6631A1), onTertiary = Color.White,
    background = LightCanvasBase, onBackground = LightInkPrimary,
    surface = Color(0xFFF8FBFF), onSurface = LightInkPrimary,
    surfaceVariant = Color(0xFFE6EDF7), onSurfaceVariant = LightInkSecondary,
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF8FBFF),
    surfaceContainer = Color(0xFFF1F5FF), surfaceContainerHigh = Color(0xFFE9EFFA),
    surfaceContainerHighest = Color(0xFFE0E8F4), outline = Color(0xFF506580),
    outlineVariant = Color(0xFFBBC8D8), error = Color(0xFFB3261E),
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
    val phase: State<Float> = if (NeonMotionState.value && systemAllowsMotion && resumed) {
        val motion = rememberInfiniteTransition(label = "neon-ambient")
        motion.animateFloat(
            initialValue = 0f, targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(4400, easing = FastOutSlowInEasing), RepeatMode.Reverse),
            label = "neon-pulse",
        )
    } else remember { mutableFloatStateOf(0.5f) }

    val themeChoice = NeonThemeState.value
    val isDark = when (themeChoice) {
        "light" -> false
        "dark", "amoled" -> true
        else -> darkTheme
    }
    val isAmoled = themeChoice == "amoled"
    val accent = if (isDark) resolveAccent(NeonAccentState.value).color else lightAccent(NeonAccentState.value)
    val base = if (isDark) NeonDarkScheme else NeonLightScheme
    val scheme = base.copy(
        primary = accent,
        onPrimary = if (isDark) Color(0xFF061018) else Color.White,
        primaryContainer = if (isDark) accent.blend(Color(0xFF070C19), 0.80f) else accent.blend(Color.White, 0.84f),
        onPrimaryContainer = if (isDark) accent.blend(Color.White, 0.25f) else Color(0xFF142037),
        surfaceTint = accent,
        background = if (isAmoled) Color.Black else base.background,
    )
    val glass = when { isAmoled -> AmoledGlassStyle; isDark -> DarkGlassStyle; else -> LightGlassStyle }
    val glow = when (NeonGlowState.value) { "subtle" -> 0.65f; "normal" -> 1f; else -> 1.55f }
    val activity = context as? ComponentActivity
    SideEffect {
        val transparent = Color.Transparent.toArgb()
        val bars = if (isDark) SystemBarStyle.dark(transparent) else SystemBarStyle.light(transparent, transparent)
        activity?.enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
    }
    CompositionLocalProvider(LocalGlassStyle provides glass, LocalNeonPhase provides phase, LocalNeonGlow provides glow) {
        MaterialTheme(colorScheme = scheme, typography = Typography, shapes = GlassShapes, content = content)
    }
}
