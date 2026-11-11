package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
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

/** Marks a container whose contents [GlassBar] may blur. */
@Composable
fun Modifier.glassSource(spec: PureThemeSpec, state: HazeState): Modifier =
    if (spec.chrome == ChromeStyle.GLASS) this.haze(state) else this

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

    if (spec.chrome == ChromeStyle.GLASS) {
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
        Box(
            base
                .background(p.surface)
                .border(
                    width = 0.5.dp,
                    color = if (edge) p.separator else p.separator.copy(alpha = 0.6f),
                    shape = shape,
                ),
            content = content,
        )
    }
}
