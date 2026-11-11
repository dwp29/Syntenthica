package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeStyle
import dev.chrisbanes.haze.HazeTint
import dev.chrisbanes.haze.haze
import dev.chrisbanes.haze.hazeChild
import net.pure.manager.theme.ChromeStyle
import net.pure.manager.theme.PureThemeSpec

/**
 * Bar chrome that is either solid or genuinely blurred.
 *
 * The blur is real: Haze renders the content underneath into a graphics layer and
 * blurs it. On Android 12+ that is a RenderEffect; below 12 Haze falls back to a
 * translucent scrim, which is the honest ceiling there and why the tint matters
 * as much as the blur radius.
 *
 * Everything here reads tokens. A theme that says [ChromeStyle.SOLID] never
 * enters the blur branch at all, so Windows and Cyberpunk stay crisp and cheap.
 */

/**
 * Whether blur is allowed on this run.
 *
 * Everything in the app reads this, so the setting is honoured in one place
 * instead of at each of the two bars.
 */
val LocalBlurEnabled = androidx.compose.runtime.staticCompositionLocalOf { true }

/**
 * Whether Haze can actually blur here.
 *
 * Haze returns no effect below API 31, and on some devices
 * `RenderEffect.createBlurEffect` rejects the radius outright and Haze rethrows
 * it -- which kills the process from inside a draw pass. A theme must never be
 * able to crash the app, so the decision is made once, from the SDK level, and
 * the tinted fallback is used everywhere else.
 */
val blurSupported: Boolean
    get() = android.os.Build.VERSION.SDK_INT >= 31

/**
 * Structural rule, enforced by a test: the composable carrying this modifier must
 * not contain a [GlassBar]. Haze throws outright if one is a descendant of the
 * other, and it throws from inside the draw pass, which kills the process on the
 * first frame rather than degrading.
 *
 * 0.1.2 did exactly that and force-closed on launch on a Redmi Note 9 Pro running
 * Android 16.
 */

/** Marks a container whose contents [GlassBar] may blur. */
@Composable
fun Modifier.glassSource(spec: PureThemeSpec, state: HazeState): Modifier =
    if (spec.chrome == ChromeStyle.GLASS && LocalBlurEnabled.current && blurSupported) {
        this.haze(state)
    } else {
        this
    }

/**
 * The bar itself.
 *
 * @param edge which side carries the hairline: `true` for a bar attached to the
 * top of the content, `false` for one attached to the bottom.
 */
@Composable
fun GlassBar(
    spec: PureThemeSpec,
    state: HazeState,
    edge: Boolean,
    modifier: Modifier = Modifier,
    shape: Shape = RoundedCornerShape(0.dp),
    content: @Composable BoxScope.() -> Unit,
) {
    val p = spec.palette
    val base = modifier.fillMaxWidth()

    if (spec.chrome == ChromeStyle.GLASS && LocalBlurEnabled.current && blurSupported) {
        val style = HazeStyle(
            backgroundColor = Color.Transparent,
            tints = listOf(HazeTint(spec.glassTint)),
            blurRadius = spec.blurDp.dp,
            noiseFactor = 0.08f,
        )
        Box(
            base
                .hazeChild(state = state, shape = shape, style = style)
                .border(
                    width = 0.5.dp,
                    color = if (edge) p.separator else p.separator.copy(alpha = 0.6f),
                    shape = shape,
                ),
            content = content,
        )
    } else {
        // Either a genuinely solid theme, or glass on a device where blur is not
        // available. In the second case the tint stands in for it, which is what
        // Haze itself does below API 31.
        val fallback = if (spec.chrome == ChromeStyle.GLASS) {
            if (spec.glassTint == Color.Unspecified) p.surface else spec.glassTint
        } else {
            p.surface
        }
        Box(
            base
                .background(fallback)
                .border(
                    width = 0.5.dp,
                    color = if (edge) p.separator else p.separator.copy(alpha = 0.6f),
                    shape = shape,
                ),
            content = content,
        )
    }
}
