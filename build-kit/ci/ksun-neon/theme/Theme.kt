package com.rifsxd.ksunext.ui.theme

import android.animation.ValueAnimator
import android.content.Context
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.annotation.StringRes
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
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
    isDark = true,
    isAmoled = false,
    canvasBase = DarkCanvasBase,
    cardTintTop = Color(0xF2111930),
    cardTintBottom = Color(0xF20A0D20),
    elevatedTintTop = Color(0xF6192040),
    elevatedTintBottom = Color(0xF2090D22),
    barTintTop = Color(0xF2070B1D),
    barTintBottom = Color(0xF20A0E22),
    dockTintTop = Color(0xF2131B32),
    dockTintBottom = Color(0xF5080B1D),
    dockActivePill = Color(0x665AEFFF),
    innerHighlight = Color(0x335AEFFF),
    borderHighlight = Color(0xAA5AEFFF),
    borderMid = Color(0x667D81FF),
    borderShadow = Color(0x88FF66CE),
    divider = Color(0x334EA5D0),
    shadowColor = Color(0x995AEFFF),
    // Neon plates don't use a per-card blur; halos are cheap gradients instead.
    blurRadius = 0.dp,
    dockBlurRadius = 0.dp,
)
val LightGlassStyle = DarkGlassStyle
val AmoledGlassStyle = DarkGlassStyle.copy(
    isAmoled = true,
    canvasBase = Color.Black,
    cardTintTop = Color(0xF20D1224),
    cardTintBottom = Color(0xF2050612),
    barTintTop = Color(0xF2000000),
    barTintBottom = Color(0xF2080A18),
)
val LocalGlassStyle = staticCompositionLocalOf { DarkGlassStyle }

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
val LocalNeonPhase = staticCompositionLocalOf<State<Float>> { mutableFloatStateOf(0.5f) }
private var prefsInitialized = false

private fun resolveAccent(id: String?): NeonAccentOption =
    NeonAccentOptions.firstOrNull { it.id == id } ?: NeonAccentOptions.first()

private fun syncNeonPrefs(context: Context) {
    if (prefsInitialized) return
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    NeonAccentState.value = resolveAccent(prefs.getString("neon_accent", "cyan")).id
    NeonMotionState.value = prefs.getBoolean("neon_motion", true)
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

private fun systemAnimationsEnabled(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.O || ValueAnimator.areAnimatorsEnabled()

fun Color.blend(other: Color, ratio: Float): Color {
    val inverse = 1f - ratio
    return Color(
        red = red * inverse + other.red * ratio,
        green = green * inverse + other.green * ratio,
        blue = blue * inverse + other.blue * ratio,
        alpha = alpha,
    )
}

private val NeonColorScheme = darkColorScheme(
    primary = IosBlueDark,
    onPrimary = Color(0xFF061018),
    primaryContainer = Color(0xFF103346),
    onPrimaryContainer = Color(0xFFD3FAFF),
    secondary = IosPinkDark,
    onSecondary = Color(0xFF24051B),
    secondaryContainer = Color(0xFF3F1639),
    onSecondaryContainer = Color(0xFFFFD8F3),
    tertiary = IosPurpleDark,
    onTertiary = Color(0xFF210E39),
    tertiaryContainer = Color(0xFF2D1C4A),
    onTertiaryContainer = Color(0xFFF0DDFF),
    background = Color(0xFF060819),
    onBackground = DarkInkPrimary,
    surface = Color(0xF20C1022),
    onSurface = DarkInkPrimary,
    surfaceVariant = Color(0xFF151B31),
    onSurfaceVariant = DarkInkSecondary,
    surfaceContainerLowest = Color(0xFF050714),
    surfaceContainerLow = Color(0xFF0D1123),
    surfaceContainer = Color(0xFF11172A),
    surfaceContainerHigh = Color(0xFF182039),
    surfaceContainerHighest = Color(0xFF202A45),
    outline = Color(0xFF64869F),
    outlineVariant = Color(0xFF26394E),
    error = IosRedDark,
    onError = Color(0xFF340A13),
    errorContainer = Color(0xFF4E1425),
    onErrorContainer = Color(0xFFFFDAE1),
)

/** Shared, draw-phase pulse avoids starting a separate infinite animation on each card. */
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
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) systemAllowsMotion = systemAnimationsEnabled()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Removing the transition entirely also stops frame work when reduced motion is requested.
    val phase: State<Float> = if (NeonMotionState.value && systemAllowsMotion) {
        val motion = rememberInfiniteTransition(label = "neon-ambient")
        motion.animateFloat(
            initialValue = 0f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(5000, easing = LinearEasing), RepeatMode.Reverse),
            label = "neon-pulse",
        )
    } else {
        remember { mutableFloatStateOf(0.5f) }
    }

    val accent = resolveAccent(NeonAccentState.value).color
    val scheme = NeonColorScheme.copy(
        primary = accent,
        onPrimary = Color(0xFF061018),
        primaryContainer = accent.blend(Color(0xFF070C19), 0.80f),
        onPrimaryContainer = accent.blend(Color.White, 0.25f),
        surfaceTint = accent,
        background = if (amoledMode) Color.Black else NeonColorScheme.background,
    )
    val glass = if (amoledMode) AmoledGlassStyle else DarkGlassStyle
    val activity = context as? ComponentActivity
    SideEffect {
        activity?.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.Transparent.toArgb()),
            navigationBarStyle = SystemBarStyle.dark(Color.Transparent.toArgb()),
        )
    }

    CompositionLocalProvider(LocalGlassStyle provides glass, LocalNeonPhase provides phase) {
        MaterialTheme(colorScheme = scheme, typography = Typography, shapes = GlassShapes, content = content)
    }
}
