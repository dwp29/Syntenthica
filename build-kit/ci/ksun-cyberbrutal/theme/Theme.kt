package com.rifsxd.ksunext.ui.theme

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext

// Appearance preferences are observable, so they update all themed screens immediately.
val SyntheticaThemeModeState = mutableStateOf("dark")   // "dark" | "light" | "amoled" | "auto"
val SyntheticaDepartureAnimState = mutableStateOf(true)
val SyntheticaAccentState = mutableStateOf("volt")

/** Contrasting variants for the same accent on dark and light surfaces. */
data class SyntheticaAccentOption(
    val id: String,
    val label: String,
    val darkColor: Color,
    val lightColor: Color,
)

// Five new choices in addition to the original Volt accent. These are not status colors.
val SyntheticaAccentOptions = listOf(
    SyntheticaAccentOption("volt", "VOLT", Color(0xFFD4FF00), Color(0xFF415B00)),
    SyntheticaAccentOption("cyan", "CYAN", Color(0xFF4BE5FF), Color(0xFF005A6B)),
    SyntheticaAccentOption("violet", "VIOLET", Color(0xFFC69CFF), Color(0xFF6735A1)),
    SyntheticaAccentOption("rose", "ROSE", Color(0xFFFF8AB8), Color(0xFF99204F)),
    SyntheticaAccentOption("amber", "AMBER", Color(0xFFFFB661), Color(0xFF803B00)),
    SyntheticaAccentOption("mint", "MINT", Color(0xFF76F5B0), Color(0xFF005C37)),
)

private fun resolveAccent(id: String?): SyntheticaAccentOption =
    SyntheticaAccentOptions.firstOrNull { it.id == id } ?: SyntheticaAccentOptions.first()

private var prefsInitialized = false

fun syncSyntheticaThemePrefs(context: Context) {
    if (prefsInitialized) return
    prefsInitialized = true
    runCatching {
        val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        SyntheticaThemeModeState.value = prefs.getString("synthetica_theme_mode", "dark") ?: "dark"
        SyntheticaDepartureAnimState.value = prefs.getBoolean("synthetica_departure_anim", true)
        SyntheticaAccentState.value = resolveAccent(prefs.getString("synthetica_accent", "volt")).id
    }
}

fun setSyntheticaThemeMode(context: Context, mode: String) {
    SyntheticaThemeModeState.value = mode
    runCatching {
        context.getSharedPreferences("settings", Context.MODE_PRIVATE)
            .edit()
            .putString("synthetica_theme_mode", mode)
            .apply()
    }
}

fun setSyntheticaDepartureAnim(context: Context, enabled: Boolean) {
    SyntheticaDepartureAnimState.value = enabled
    runCatching {
        context.getSharedPreferences("settings", Context.MODE_PRIVATE)
            .edit()
            .putBoolean("synthetica_departure_anim", enabled)
            .apply()
    }
}

fun setSyntheticaAccent(context: Context, id: String) {
    val resolved = resolveAccent(id).id
    SyntheticaAccentState.value = resolved
    runCatching {
        context.getSharedPreferences("settings", Context.MODE_PRIVATE)
            .edit()
            .putString("synthetica_accent", resolved)
            .apply()
    }
}

private val ObsidianCyberBrutalScheme = darkColorScheme(
    primary = BRUTAL_VOLT,
    onPrimary = BRUTAL_INK,
    primaryContainer = Color(0xFF232B05),
    onPrimaryContainer = BRUTAL_VOLT,
    secondary = BRUTAL_CYAN,
    onSecondary = BRUTAL_INK,
    secondaryContainer = Color(0xFF19212C),
    onSecondaryContainer = BRUTAL_VOLT,
    tertiary = BRUTAL_CYAN,
    onTertiary = BRUTAL_INK,
    tertiaryContainer = Color(0xFF0A2A33),
    onTertiaryContainer = BRUTAL_CYAN,
    background = BRUTAL_BG_DARK,
    onBackground = BRUTAL_BONE,
    surface = BRUTAL_SURFACE_DARK,
    onSurface = BRUTAL_BONE,
    surfaceVariant = BRUTAL_SURFACE_HIGH_DARK,
    onSurfaceVariant = BRUTAL_DIM_DARK,
    surfaceContainerLowest = Color(0xFF07080B),
    surfaceContainerLow = BRUTAL_SURFACE_DARK,
    surfaceContainer = BRUTAL_SURFACE_HIGH_DARK,
    surfaceContainerHigh = Color(0xFF212736),
    surfaceContainerHighest = Color(0xFF2A3142),
    outline = BRUTAL_BORDER_DARK,
    outlineVariant = Color(0xFF1E2430),
    error = BRUTAL_CRIMSON,
    onError = Color.White,
    errorContainer = Color(0xFF3B0A18),
    onErrorContainer = Color(0xFFFF8DA1),
    inverseSurface = BRUTAL_BONE,
    inverseOnSurface = BRUTAL_INK,
)

private val AmoledCyberBrutalScheme = ObsidianCyberBrutalScheme.copy(
    background = BRUTAL_BG_AMOLED,
    surface = BRUTAL_SURFACE_AMOLED,
    surfaceContainerLowest = Color.Black,
    surfaceContainerLow = BRUTAL_SURFACE_AMOLED,
    surfaceContainer = Color(0xFF10141C),
)

private val IndustrialLightBrutalScheme = lightColorScheme(
    primary = BRUTAL_INK,
    onPrimary = BRUTAL_VOLT,
    primaryContainer = BRUTAL_VOLT,
    onPrimaryContainer = BRUTAL_INK,
    secondary = BRUTAL_SIGNAL,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDFDDD2),
    onSecondaryContainer = BRUTAL_INK,
    tertiary = Color(0xFF005B66),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFC9F2F7),
    onTertiaryContainer = Color(0xFF002A30),
    background = BRUTAL_BG_LIGHT,
    onBackground = BRUTAL_INK,
    surface = BRUTAL_SURFACE_LIGHT,
    onSurface = BRUTAL_INK,
    surfaceVariant = BRUTAL_SURFACE_HIGH_LIGHT,
    onSurfaceVariant = BRUTAL_DIM_LIGHT,
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = BRUTAL_SURFACE_LIGHT,
    surfaceContainer = BRUTAL_SURFACE_HIGH_LIGHT,
    surfaceContainerHigh = Color(0xFFDAD8CD),
    surfaceContainerHighest = Color(0xFFCECCC0),
    outline = BRUTAL_BORDER_LIGHT,
    outlineVariant = Color(0xFFC5C3B7),
    error = Color(0xFFD9163E),
    onError = Color.White,
    errorContainer = Color(0xFFFFD9E0),
    onErrorContainer = Color(0xFF5C0014),
    inverseSurface = BRUTAL_INK,
    inverseOnSurface = BRUTAL_BONE,
)

fun Color.blend(other: Color, ratio: Float): Color {
    val inverse = 1f - ratio
    return Color(
        red = red * inverse + other.red * ratio,
        green = green * inverse + other.green * ratio,
        blue = blue * inverse + other.blue * ratio,
        alpha = alpha
    )
}

private fun ColorScheme.withAccent(option: SyntheticaAccentOption, dark: Boolean): ColorScheme {
    val accent = if (dark) option.darkColor else option.lightColor
    return copy(
        primary = accent,
        onPrimary = if (dark) BRUTAL_INK else Color.White,
        primaryContainer = accent.blend(if (dark) Color.Black else Color.White, 0.85f),
        onPrimaryContainer = accent,
        onSecondaryContainer = if (dark) accent else onSecondaryContainer,
        surfaceTint = accent,
        inversePrimary = if (dark) option.lightColor else option.darkColor,
    )
}

@Suppress("UNUSED_PARAMETER")
@Composable
fun KernelSUTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false, // Forced off so Android 12+ wallpaper never overrides Cyberbrutalism
    amoledMode: Boolean = false,
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    LaunchedEffect(context) {
        syncSyntheticaThemePrefs(context)
    }

    val mode = SyntheticaThemeModeState.value
    val effectiveDark = when (mode) {
        "light" -> false
        "dark", "amoled" -> true
        else -> darkTheme
    }
    val effectiveAmoled = amoledMode || mode == "amoled"

    val baseScheme = when {
        !effectiveDark -> IndustrialLightBrutalScheme
        effectiveAmoled -> AmoledCyberBrutalScheme
        else -> ObsidianCyberBrutalScheme
    }
    val scheme = baseScheme.withAccent(resolveAccent(SyntheticaAccentState.value), effectiveDark)

    BrutalSystemBarStyle(isDark = effectiveDark)

    MaterialTheme(
        colorScheme = scheme,
        typography = Typography,
        shapes = KernelSUThemeShapes,
        content = content
    )
}

@Composable
private fun BrutalSystemBarStyle(
    isDark: Boolean,
    statusBarScrim: Color = Color.Transparent,
    navigationBarScrim: Color = Color.Transparent,
) {
    val context = LocalContext.current
    val activity = context as? ComponentActivity ?: return

    SideEffect {
        if (isDark) {
            activity.enableEdgeToEdge(
                statusBarStyle = SystemBarStyle.dark(statusBarScrim.toArgb()),
                navigationBarStyle = SystemBarStyle.dark(navigationBarScrim.toArgb())
            )
        } else {
            activity.enableEdgeToEdge(
                statusBarStyle = SystemBarStyle.light(statusBarScrim.toArgb(), statusBarScrim.toArgb()),
                navigationBarStyle = SystemBarStyle.light(navigationBarScrim.toArgb(), navigationBarScrim.toArgb())
            )
        }
    }
}
