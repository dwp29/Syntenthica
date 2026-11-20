package app.breakfast.manager.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.breakfast.manager.ui.theme.BreakfastColors
import app.breakfast.manager.ui.theme.LocalBreakfastColors
import app.breakfast.manager.ui.theme.NumericStyle
import app.breakfast.manager.ui.theme.cardShape
import app.breakfast.manager.ui.theme.chipShape
import kotlin.math.cos
import kotlin.math.sin

/** A section label in small caps, the way the design sheets use them. */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    val c = LocalBreakfastColors.current
    Text(
        text = text.uppercase(),
        style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
        color = c.textSecondary,
        modifier = modifier.padding(top = if (c.isDense) 18.dp else 24.dp, bottom = 10.dp),
    )
}

/**
 * The pulse ring: a temperature gauge, not decoration.
 *
 * The arc length encodes the reading, and the number in the middle is the value
 * itself. When the sensor cannot be read the ring shows an em dash and the arc
 * is not drawn at all, because a partial arc would imply a measurement.
 */
@Composable
fun PulseRing(
    value: Float?,
    max: Float,
    label: String,
    caption: String,
    color: Color,
    valueText: String = value?.let { "${it.toInt()}°" } ?: "—",
    size: Dp = 240.dp,
) {
    val c = LocalBreakfastColors.current
    val target = if (value == null) 0f else (value / max).coerceIn(0f, 1f)
    val progress by animateFloatAsState(
        targetValue = target,
        animationSpec = tween(durationMillis = c.motionMs * 2),
        label = "ring",
    )
    val idleAlpha by animateFloatAsState(
        targetValue = if (value == null) 0.25f else 1f,
        animationSpec = tween(c.motionMs),
        label = "ringAlpha",
    )

    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(size)) {
        Canvas(Modifier.size(size)) {
            val stroke = 14.dp.toPx()
            val inset = stroke / 2 + 6.dp.toPx()
            val arcSize = Size(this.size.width - inset * 2, this.size.height - inset * 2)
            val topLeft = Offset(inset, inset)

            // Track.
            drawArc(
                color = c.hairline,
                startAngle = 135f,
                sweepAngle = 270f,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
            // Value null means "not measured". Drawing a zero-length arc would
            // still paint the round cap as a dot, which reads as a data point.
            if (value != null && target > 0f) {
                drawArc(
                    brush = Brush.sweepGradient(
                        listOf(color.copy(alpha = 0.35f), color, color.copy(alpha = 0.55f)),
                        center = Offset(this.size.width / 2, this.size.height / 2),
                    ),
                    startAngle = 135f,
                    sweepAngle = 270f * progress,
                    useCenter = false,
                    topLeft = topLeft,
                    size = arcSize,
                    style = Stroke(width = stroke, cap = StrokeCap.Round),
                )
                // Tick marks around the gap at the bottom, as on the design sheet.
                val radius = (this.size.width - inset * 2) / 2
                for (i in 0..36) {
                    val angle = Math.toRadians((135.0 + 270.0 * i / 36))
                    val inner = radius - stroke / 2 - 8.dp.toPx()
                    val outer = radius - stroke / 2 - 3.dp.toPx()
                    val cx = this.size.width / 2
                    val cy = this.size.height / 2
                    drawLine(
                        color = c.textTertiary,
                        start = Offset(cx + (inner * cos(angle)).toFloat(), cy + (inner * sin(angle)).toFloat()),
                        end = Offset(cx + (outer * cos(angle)).toFloat(), cy + (outer * sin(angle)).toFloat()),
                        strokeWidth = 1.dp.toPx(),
                    )
                }
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = label.uppercase(),
                style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
                color = c.textSecondary,
            )
            Text(
                text = value?.let { "${it.toInt()}°" } ?: "—",
                style = androidx.compose.material3.MaterialTheme.typography.displayLarge.merge(NumericStyle),
                color = if (value == null) c.textTertiary else c.textPrimary,
            )
            Text(
                text = caption,
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
                color = color.copy(alpha = idleAlpha),
            )
        }
    }
}

/**
 * A card with a very subtle vertical gradient, so stacked cards read as surfaces
 * rather than as one flat block. The hairline border is what defines the edge -
 * no drop shadows, which look muddy on near-black.
 */
@Composable
fun SurfaceCard(
    modifier: Modifier = Modifier,
    padding: Dp = 16.dp,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
) {
    val c = LocalBreakfastColors.current
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(c.cardShape)
            .background(
                Brush.verticalGradient(
                    listOf(c.surfaceElevated, c.surface),
                )
            )
            .border(1.dp, c.hairline, c.cardShape)
            .padding(padding),
        content = content,
    )
}

/** Rounded pill used for the kernel variant and for statuses. */
@Composable
fun Chip(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    filled: Boolean = false,
) {
    val c = LocalBreakfastColors.current
    Box(
        modifier = modifier
            .clip(c.chipShape)
            .background(if (filled) color.copy(alpha = 0.18f) else Color.Transparent)
            .border(1.dp, color.copy(alpha = if (filled) 0f else 0.45f), c.chipShape)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(
            text = text.uppercase(),
            style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
            color = color,
        )
    }
}

/** Stat tile: icon glyph, label, value. Used in the 4-across row. */
@Composable
fun StatTile(
    glyph: String,
    label: String,
    value: String,
    valueColor: Color,
    modifier: Modifier = Modifier,
) {
    val c = LocalBreakfastColors.current
    Column(
        modifier = modifier
            .clip(c.cardShape)
            .background(Brush.verticalGradient(listOf(c.surfaceElevated, c.surface)))
            .border(1.dp, c.hairline, c.cardShape)
            .padding(vertical = if (c.isDense) 10.dp else 14.dp, horizontal = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text = glyph, fontSize = 16.sp, color = valueColor)
        Spacer(Modifier.height(6.dp))
        Text(
            text = label.uppercase(),
            style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
            color = c.textSecondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            text = value,
            style = androidx.compose.material3.MaterialTheme.typography.titleMedium.merge(NumericStyle),
            color = valueColor,
            maxLines = 1,
        )
    }
}

/**
 * Sparkline over a fixed window.
 *
 * `series` may be empty, in which case only the baseline is drawn - an empty
 * chart is honest about having no history, whereas a flat line at zero would
 * claim the value has been zero all along.
 */
/**
 * Vertical bounds for a sparkline.
 *
 * Percentages are not auto-scaled to their own minimum any more: a flat 61%
 * memory load drew as a line on the floor, which is arithmetically fine and
 * visually false. A percentage series keeps a real band (45..100) and only the
 * wobble matters inside it.
 */
internal fun graphBounds(series: List<Float>, normalise: Boolean, fixedMax: Float?): Pair<Float, Float> {
    if (series.isEmpty()) return 0f to 1f
    val dataMin = series.min()
    val dataMax = series.max()
    return if (normalise) {
        val lo = minOf(dataMin, 0f)
        val hi = maxOf(dataMax, lo + 1f)
        val pad = (hi - lo) * 0.08f
        (lo - pad) to (hi + pad)
    } else {
        val floor = fixedMax?.let { it * 0.45f } ?: 0f
        val ceiling = fixedMax ?: (dataMax.takeIf { it > 0f } ?: 1f)
        val pad = ((ceiling - floor) * 0.06f).coerceAtLeast(0.5f)
        (floor - pad).coerceAtLeast(0f) to (ceiling + pad).coerceAtMost(fixedMax ?: Float.MAX_VALUE)
    }
}

/** Where a value sits in a chart, 0 at the bottom and 1 at the top. */
internal fun graphScale(value: Float, fixedMax: Float?): Float {
    val (lo, hi) = graphBounds(listOf(value, value, fixedMax ?: value), normalise = false, fixedMax = fixedMax)
    val span = (hi - lo).takeIf { it > 0.0001f } ?: 1f
    return ((value - lo) / span).coerceIn(0f, 1f)
}

/** CPU usage from two /proc/stat samples, or null when the delta is too small. */
internal fun cpuUsageFromDelta(totalDelta: Long, idleDelta: Long): Float? {
    if (totalDelta < 20L || idleDelta < 0L) return null
    return ((totalDelta - idleDelta).toFloat() / totalDelta.toFloat()).coerceIn(0f, 1f)
}

@Composable
fun Sparkline(
    series: List<Float>,
    color: Color,
    modifier: Modifier = Modifier,
    height: Dp = 44.dp,
    normalise: Boolean = true,
    fixedMax: Float? = null,
) {
    val c = LocalBreakfastColors.current
    Canvas(modifier = modifier.fillMaxWidth().height(height)) {
        if (series.size < 2) {
            drawLine(
                color = c.hairline,
                start = Offset(0f, size.height / 2),
                end = Offset(size.width, size.height / 2),
                strokeWidth = 1.dp.toPx(),
            )
            return@Canvas
        }
        // Auto-scaling to the series minimum drew a constant 61% memory load as
        // a line glued to the floor: correct maths, false impression. When a
        // series sits inside a narrow band it is now expanded around its own mean
        // and clamped to the real axis, so the shape of the wobble is visible
        // while the value stays readable.
        val bounds = graphBounds(series, normalise, fixedMax)
        val min = bounds.first
        val max = bounds.second
        val span = (max - min).takeIf { it > 0.0001f } ?: 1f
        val stepX = size.width / (series.size - 1)

        fun pointAt(index: Int): Offset {
            val x = stepX * index
            val norm = (series[index] - min) / span
            val y = size.height - (norm * (size.height - 6.dp.toPx())) - 3.dp.toPx()
            return Offset(x, y)
        }

        val line = Path()
        val fill = Path()
        val first = pointAt(0)
        line.moveTo(first.x, first.y)
        fill.moveTo(first.x, size.height)
        fill.lineTo(first.x, first.y)
        for (i in 1 until series.size) {
            val p = pointAt(i)
            line.lineTo(p.x, p.y)
            fill.lineTo(p.x, p.y)
        }
        fill.lineTo(size.width, size.height)
        fill.close()

        drawPath(
            path = fill,
            brush = Brush.verticalGradient(
                listOf(color.copy(alpha = 0.28f), color.copy(alpha = 0.02f)),
            ),
        )
        drawPath(path = line, color = color, style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round))
        drawCircle(color = color, radius = 3.dp.toPx(), center = pointAt(series.size - 1))
    }
}

/**
 * One row: label on the left, value on the right.
 *
 * Both sides are weighted AND bounded, which is the fix for two device bugs:
 *
 *  - A long value used to take unbounded width, squeezing the label column to a
 *    few pixels; the label then wrapped per character ("Ker nel") and the card
 *    grew taller than the screen.
 *  - The value itself must never wrap into a paragraph, so it is capped at two
 *    lines with an ellipsis and reports its full text through a tap target in
 *    the LAB list.
 *
 * Weighting 0.55/0.45 rather than 0.9/1.1 matters: labels are words, values can
 * be kernel paths, and the narrow side should always be the one that wraps.
 */
@Composable
fun DataRow(
    label: String,
    value: String,
    valueColor: Color,
    modifier: Modifier = Modifier,
    mono: Boolean = false,
    note: String? = null,
    maxValueLines: Int = 2,
    /**
     * Stack the value under the label instead of beside it.
     *
     * Used for values that are word lists ("userspace powersave performance
     * schedutil"). Even with bounded columns, a value like that next to a label
     * truncates to something unreadable, and the whole point of LAB is to read
     * the raw kernel value.
     */
    fullWidthValue: Boolean = false,
) {
    val c = LocalBreakfastColors.current
    if (fullWidthValue) {
        Column(modifier.fillMaxWidth().padding(vertical = 8.dp)) {
            Text(
                text = label,
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
            )
            Spacer(Modifier.height(3.dp))
            Text(
                text = value,
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium.let {
                    if (mono) it.merge(NumericStyle) else it
                },
                fontWeight = FontWeight.SemiBold,
                color = valueColor,
            )
            if (note != null) {
                Text(
                    text = note,
                    fontSize = 11.sp,
                    lineHeight = 15.sp,
                    color = c.textTertiary,
                )
            }
        }
        return
    }
    Row(
        modifier = modifier.fillMaxWidth().padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(0.52f)) {
            Text(
                text = label,
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
                color = c.textSecondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (note != null) {
                Text(
                    text = note,
                    fontSize = 11.sp,
                    lineHeight = 15.sp,
                    color = c.textTertiary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.width(14.dp))
        Text(
            text = value,
            style = androidx.compose.material3.MaterialTheme.typography.bodyMedium.let {
                if (mono) it.merge(NumericStyle) else it
            },
            fontWeight = FontWeight.SemiBold,
            color = valueColor,
            textAlign = TextAlign.End,
            maxLines = maxValueLines,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(0.48f),
        )
    }
}

/** A row whose value is allowed to wrap fully, used for long kernel paths. */
@Composable
fun PathRow(label: String, path: String, modifier: Modifier = Modifier) {
    val c = LocalBreakfastColors.current
    Column(modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Text(
            text = label,
            style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
            color = c.textSecondary,
        )
        Text(
            text = path,
            fontSize = 11.sp,
            lineHeight = 15.sp,
            color = c.textTertiary,
            style = NumericStyle,
        )
    }
}

/** Filled accent button, used once per screen at most. */
@Composable
fun AccentButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val c = LocalBreakfastColors.current
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp)
            .clip(c.chipShape)
            .background(if (enabled) c.accent else c.accent.copy(alpha = 0.25f))
            .clickable(enabled = enabled) { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text.uppercase(),
            style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
            color = Color.Black.copy(alpha = if (enabled) 0.92f else 0.4f),
            letterSpacing = 1.6.sp,
        )
    }
}

/** Outlined button for the secondary action next to an AccentButton. */
@Composable
fun GhostButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    color: Color? = null,
) {
    val c = LocalBreakfastColors.current
    Box(
        modifier = modifier
            .height(52.dp)
            .clip(c.chipShape)
            .border(1.dp, (color ?: c.textSecondary).copy(alpha = 0.4f), c.chipShape)
            .clickable { onClick() }
            .padding(horizontal = 18.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text.uppercase(),
            style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
            color = color ?: c.textSecondary,
        )
    }
}
