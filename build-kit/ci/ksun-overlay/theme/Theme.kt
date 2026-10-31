package com.rifsxd.ksunext.ui.theme

import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext

// Synthetica 2.0: one fixed iOS-glass scheme, always light.
// `dynamicColor` is accepted for API compatibility but never used: upstream's Material You
// default repainted every screen from the wallpaper, which is why rebranding alone never
// changed the look. Cards sit on GLASS_SURFACE over the animated GlassBackground.

private val GlassColorScheme = lightColorScheme(
    primary = ACCENT_BLUE,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCEBFF),
    onPrimaryContainer = Color(0xFF003A75),
    secondary = ACCENT_MINT,
    onSecondary = Color(0xFF00332F),
    secondaryContainer = Color(0xFFD5F5F2),
    onSecondaryContainer = Color(0xFF00423D),
    tertiary = ACCENT_VIOLET,
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFF0DFFB),
    onTertiaryContainer = Color(0xFF4A1366),
    background = GLASS_BG_MID,
    onBackground = TEXT_MAIN,
    surface = GLASS_SURFACE,
    onSurface = TEXT_MAIN,
    surfaceVariant = GLASS_SURFACE_HIGH,
    onSurfaceVariant = TEXT_DIM,
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = GLASS_SURFACE,
    surfaceContainer = GLASS_SURFACE_HIGH,
    surfaceContainerHigh = Color(0xFFE7EEF6),
    surfaceContainerHighest = Color(0xFFDCE6F1),
    outline = HAIRLINE,
    outlineVariant = Color(0xFFE7EEF5),
    error = RED,
    onError = Color.White,
    errorContainer = Color(0xFFFFE3EA),
    onErrorContainer = Color(0xFF7A0C26),
    inverseSurface = INK,
    inverseOnSurface = Color.White,
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

@Suppress("UNUSED_PARAMETER")
@Composable
fun KernelSUTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Ignored on purpose: see the note above. Kept so call sites do not need changing.
    dynamicColor: Boolean = true,
    amoledMode: Boolean = false,
    content: @Composable () -> Unit
) {
    SystemBarStyle()

    MaterialTheme(
        colorScheme = GlassColorScheme,
        typography = Typography,
        shapes = KernelSUThemeShapes,
        content = content
    )
}

@Composable
private fun SystemBarStyle(
    statusBarScrim: Color = Color.Transparent,
    navigationBarScrim: Color = Color.Transparent,
) {
    val context = LocalContext.current
    val activity = context as ComponentActivity

    SideEffect {
        activity.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(statusBarScrim.toArgb(), statusBarScrim.toArgb()),
            navigationBarStyle = SystemBarStyle.light(navigationBarScrim.toArgb(), navigationBarScrim.toArgb())
        )
    }
}
