package com.rifsxd.ksunext.ui.theme

import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

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

val LightGlassStyle = GlassStyle(
    isDark = false,
    isAmoled = false,
    canvasBase = LightCanvasBase,
    cardTintTop = Color.White.copy(alpha = 0.62f),
    cardTintBottom = Color(0xFFF3F8FF).copy(alpha = 0.46f),
    elevatedTintTop = Color.White.copy(alpha = 0.74f),
    elevatedTintBottom = Color(0xFFEEF5FF).copy(alpha = 0.58f),
    barTintTop = Color.White.copy(alpha = 0.68f),
    barTintBottom = Color(0xFFF2F7FF).copy(alpha = 0.52f),
    dockTintTop = Color.White.copy(alpha = 0.66f),
    dockTintBottom = Color(0xFFEAF3FF).copy(alpha = 0.50f),
    dockActivePill = Color.White.copy(alpha = 0.85f),
    innerHighlight = Color.White.copy(alpha = 0.42f),
    borderHighlight = Color.White.copy(alpha = 0.92f),
    borderMid = Color.White.copy(alpha = 0.42f),
    borderShadow = Color(0xFF9AB8E0).copy(alpha = 0.28f),
    divider = Color(0xFF0E2240).copy(alpha = 0.08f),
    shadowColor = Color(0xFF0A2548).copy(alpha = 0.10f),
    blurRadius = 26.dp,
    dockBlurRadius = 32.dp,
)

val DarkGlassStyle = GlassStyle(
    isDark = true,
    isAmoled = false,
    canvasBase = DarkCanvasBase,
    cardTintTop = Color(0xFF162642).copy(alpha = 0.56f),
    cardTintBottom = Color(0xFF0C1628).copy(alpha = 0.44f),
    elevatedTintTop = Color(0xFF1C3052).copy(alpha = 0.68f),
    elevatedTintBottom = Color(0xFF101C33).copy(alpha = 0.54f),
    barTintTop = Color(0xFF0D192E).copy(alpha = 0.68f),
    barTintBottom = Color(0xFF091222).copy(alpha = 0.54f),
    dockTintTop = Color(0xFF162744).copy(alpha = 0.64f),
    dockTintBottom = Color(0xFF0B1526).copy(alpha = 0.52f),
    dockActivePill = Color(0xFF2997FF).copy(alpha = 0.24f),
    innerHighlight = Color(0xFFA8D4FF).copy(alpha = 0.16f),
    borderHighlight = Color(0xFFD6ECFF).copy(alpha = 0.36f),
    borderMid = Color(0xFF6CA8E8).copy(alpha = 0.14f),
    borderShadow = Color(0xFF040A14).copy(alpha = 0.40f),
    divider = Color.White.copy(alpha = 0.08f),
    shadowColor = Color.Black.copy(alpha = 0.38f),
    blurRadius = 28.dp,
    dockBlurRadius = 34.dp,
)

val AmoledGlassStyle = DarkGlassStyle.copy(
    isAmoled = true,
    canvasBase = AMOLED_BLACK,
    cardTintTop = Color(0xFF111C30).copy(alpha = 0.52f),
    cardTintBottom = Color(0xFF070C17).copy(alpha = 0.42f),
    barTintTop = Color(0xFF070D19).copy(alpha = 0.72f),
    barTintBottom = Color(0xFF03060C).copy(alpha = 0.58f),
    dockTintTop = Color(0xFF121F36).copy(alpha = 0.66f),
    dockTintBottom = Color(0xFF060B14).copy(alpha = 0.54f),
)

val LocalGlassStyle = staticCompositionLocalOf { LightGlassStyle }

private val LightGlassColorScheme = lightColorScheme(
    primary = IosBlueLight,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6EAFF).copy(alpha = 0.78f),
    onPrimaryContainer = Color(0xFF00326A),
    secondary = IosIndigoLight,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3ECFA).copy(alpha = 0.76f),
    onSecondaryContainer = LightInkPrimary,
    tertiary = IosTeal,
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD2F7F4).copy(alpha = 0.78f),
    onTertiaryContainer = Color(0xFF003B38),
    background = Color.Transparent,
    onBackground = LightInkPrimary,
    surface = Color.White.copy(alpha = 0.68f),
    onSurface = LightInkPrimary,
    surfaceVariant = Color(0xFFE5EEF9).copy(alpha = 0.72f),
    onSurfaceVariant = LightInkSecondary,
    surfaceContainerLowest = Color.White.copy(alpha = 0.52f),
    surfaceContainerLow = Color.White.copy(alpha = 0.64f),
    surfaceContainer = Color.White.copy(alpha = 0.72f),
    surfaceContainerHigh = Color(0xFFF5F9FF).copy(alpha = 0.88f),
    surfaceContainerHighest = Color.White.copy(alpha = 0.68f),
    outline = Color(0xFF8BA2C4).copy(alpha = 0.38f),
    outlineVariant = Color(0xFF0E2240).copy(alpha = 0.09f),
    error = IosRedLight,
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6).copy(alpha = 0.82f),
    onErrorContainer = Color(0xFF540003),
)

private val DarkGlassColorScheme = darkColorScheme(
    primary = IosBlueDark,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF113561).copy(alpha = 0.78f),
    onPrimaryContainer = Color(0xFFD4E9FF),
    secondary = IosCyanDark,
    onSecondary = Color(0xFF002638),
    secondaryContainer = Color(0xFF172A46).copy(alpha = 0.76f),
    onSecondaryContainer = DarkInkPrimary,
    tertiary = IosTeal,
    onTertiary = Color(0xFF002B29),
    tertiaryContainer = Color(0xFF0D3D42).copy(alpha = 0.78f),
    onTertiaryContainer = Color(0xFFB5F7F2),
    background = Color.Transparent,
    onBackground = DarkInkPrimary,
    surface = Color(0xFF111D33).copy(alpha = 0.68f),
    onSurface = DarkInkPrimary,
    surfaceVariant = Color(0xFF192944).copy(alpha = 0.72f),
    onSurfaceVariant = DarkInkSecondary,
    surfaceContainerLowest = Color(0xFF0B1424).copy(alpha = 0.56f),
    surfaceContainerLow = Color(0xFF111E35).copy(alpha = 0.64f),
    surfaceContainer = Color(0xFF152540).copy(alpha = 0.72f),
    surfaceContainerHigh = Color(0xFF182946).copy(alpha = 0.90f),
    surfaceContainerHighest = Color(0xFF14223B).copy(alpha = 0.68f),
    outline = Color(0xFF8AB8F0).copy(alpha = 0.28f),
    outlineVariant = Color.White.copy(alpha = 0.09f),
    error = IosRedDark,
    onError = Color.White,
    errorContainer = Color(0xFF5C1414).copy(alpha = 0.80f),
    onErrorContainer = Color(0xFFFFDAD6),
)

fun Color.blend(other: Color, ratio: Float): Color {
    val inverse = 1f - ratio
    return Color(
        red = red * inverse + other.red * ratio,
        green = green * inverse + other.green * ratio,
        blue = blue * inverse + other.blue * ratio,
        alpha = alpha,
    )
}

@Composable
fun KernelSUTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    amoledMode: Boolean = false,
    content: @Composable () -> Unit,
) {
    val glassStyle = when {
        darkTheme && amoledMode -> AmoledGlassStyle
        darkTheme -> DarkGlassStyle
        else -> LightGlassStyle
    }

    val colorScheme = when {
        darkTheme && amoledMode -> DarkGlassColorScheme.copy(
            surface = Color(0xFF0A1220).copy(alpha = 0.70f),
            surfaceContainerHigh = Color(0xFF0F1A2E).copy(alpha = 0.92f),
            surfaceContainerHighest = Color(0xFF0D1729).copy(alpha = 0.66f),
        )
        darkTheme -> DarkGlassColorScheme
        else -> LightGlassColorScheme
    }

    SystemBarStyle(darkMode = darkTheme)

    CompositionLocalProvider(LocalGlassStyle provides glassStyle) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = Typography,
            shapes = GlassShapes,
            content = content,
        )
    }
}

@Composable
private fun SystemBarStyle(
    darkMode: Boolean,
    statusBarScrim: Color = Color.Transparent,
    navigationBarScrim: Color = Color.Transparent,
) {
    val context = LocalContext.current
    val activity = context as? ComponentActivity ?: return
    SideEffect {
        activity.enableEdgeToEdge(
            statusBarStyle = if (darkMode) {
                SystemBarStyle.dark(statusBarScrim.toArgb())
            } else {
                SystemBarStyle.light(statusBarScrim.toArgb(), statusBarScrim.toArgb())
            },
            navigationBarStyle = if (darkMode) {
                SystemBarStyle.dark(navigationBarScrim.toArgb())
            } else {
                SystemBarStyle.light(navigationBarScrim.toArgb(), navigationBarScrim.toArgb())
            },
        )
    }
}
