package net.pure.manager.theme

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.calculateEndPadding
import androidx.compose.foundation.layout.calculateStartPadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.statusBars
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * System-bar padding, published once by [PureTheme].
 *
 * `enableEdgeToEdge()` makes the window draw behind the status bar and the
 * gesture bar, which is correct for a full-bleed background but means every
 * screen has to inset its own content. Exposing it here keeps the shell from
 * importing WindowInsets in six places, and lets a future "hide system bars"
 * setting zero it out centrally.
 */
data class SystemInsets(val top: Dp = 0.dp, val bottom: Dp = 0.dp, val start: Dp = 0.dp, val end: Dp = 0.dp)

val LocalSystemInsets = staticCompositionLocalOf { SystemInsets() }

/**
 * The active token set, readable from any composable without passing parameters
 * down the tree. Screens read `LocalPureSpec.current`; they never read [themeId].
 */
val LocalPureSpec = staticCompositionLocalOf {
    specFor("ios", AppMode.DARK, AccentChoices[0].second)
}

/** User-tunable overrides from the Customisation tab. */
data class ThemePrefs(
    val themeId: String = "ios",
    val mode: AppMode = AppMode.DARK,
    val accentIndex: Int = 0,
    /** Global radius multiplier, 0.5x to 2x. */
    val cornerScale: Float = 1f,
    /** 0.85 (compact) to 1.15 (roomy) for font and row density. */
    val densityScale: Float = 1f,
    /** Honours the system "remove animations" setting when false. */
    val animations: Boolean = true,
) {
    fun spec(): PureThemeSpec {
        val base = specFor(themeId, mode, AccentChoices[accentIndex].second)
        return base.copy(
            cornerDp = (base.cornerDp * cornerScale).toInt().coerceAtLeast(0),
            rowHeightDp = (base.rowHeightDp * densityScale).toInt().coerceIn(28, 96),
            motion = if (animations) base.motion
            else base.motion.copy(pressScale = 1f, shortMs = 0, longMs = 0, overshoot = false),
        )
    }
}

@Composable
fun PureTheme(prefs: ThemePrefs, content: @Composable () -> Unit) {
    val spec = prefs.spec()
    val p = spec.palette

    val scheme = if (prefs.mode == AppMode.LIGHT) {
        lightColorScheme(
            primary = p.accent, onPrimary = p.onAccent,
            background = p.background, onBackground = p.onBackground,
            surface = p.surface, onSurface = p.onBackground,
            surfaceVariant = p.surfaceVariant, onSurfaceVariant = p.onSurfaceVariant,
            outline = if (p.outline == androidx.compose.ui.graphics.Color.Transparent)
                p.surfaceVariant else p.outline,
        )
    } else {
        darkColorScheme(
            primary = p.accent, onPrimary = p.onAccent,
            background = p.background, onBackground = p.onBackground,
            surface = p.surface, onSurface = p.onBackground,
            surfaceVariant = p.surfaceVariant, onSurfaceVariant = p.onSurfaceVariant,
            outline = if (p.outline == androidx.compose.ui.graphics.Color.Transparent)
                p.surfaceVariant else p.outline,
        )
    }

    // Android 15+ draws edge-to-edge by force; reading the insets at runtime is
    // the only approach that is correct on every version from 10 to 17.
    val layout = LocalLayoutDirection.current
    val status = WindowInsets.statusBars.asPaddingValues()
    val nav = WindowInsets.navigationBars.asPaddingValues()
    val insets = SystemInsets(
        top = status.calculateTopPadding(),
        bottom = nav.calculateBottomPadding(),
        start = nav.calculateStartPadding(layout),
        end = nav.calculateEndPadding(layout),
    )

    CompositionLocalProvider(LocalPureSpec provides spec, LocalSystemInsets provides insets) {
        MaterialTheme(
            colorScheme = scheme,
            typography = typographyFor(spec, prefs.densityScale),
            // Typography is scaled by densityScale so the "ukuran teks" control
            // actually changes text size; early builds hardcoded every sp value
            // and the control did nothing.
            shapes = shapesFor(spec),
            content = content,
        )
    }
}
