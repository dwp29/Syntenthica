package com.rifsxd.ksunext.ui.theme

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.takeOrElse
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.BuildConfig
import kotlinx.coroutines.delay

private const val SOLARI_GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-:#+[]"

/**
 * Splits a string into UTF-16 safe units so emojis / surrogate pairs in app or module names
 * are never split mid-pair during Solari split-flap cycling.
 */
private fun splitSafeUnits(input: String): List<String> {
    if (input.isEmpty()) return emptyList()
    val out = ArrayList<String>(input.length)
    var i = 0
    while (i < input.length) {
        val c = input[i]
        if (Character.isHighSurrogate(c) && i + 1 < input.length && Character.isLowSurrogate(input[i + 1])) {
            out.add(input.substring(i, i + 2))
            i += 2
        } else {
            out.add(c.toString())
            i += 1
        }
    }
    return out
}

/**
 * Solari Airport Departure Board (Split-Flap) text animation.
 * Each character slot cycles rapidly through mechanical glyphs with an Acid-Volt split-flap
 * highlight wave from left to right before locking into its destination character.
 * Once settled, renders a static Text with zero ongoing CPU/GPU cost.
 */
@Composable
fun DepartureBoardText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = LocalTextStyle.current,
    color: Color = Color.Unspecified,
    fontSize: TextUnit = TextUnit.Unspecified,
    fontWeight: FontWeight? = null,
    fontFamily: FontFamily? = null,
    lineHeight: TextUnit = TextUnit.Unspecified,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textDecoration: TextDecoration? = null,
    delayMillis: Int = 0,
    charStaggerMs: Int = 20,
    flapDurationMs: Int = 195,
    triggerKey: Any? = Unit,
) {
    val animEnabled = SyntheticaDepartureAnimState.value
    val units = remember(text) { splitSafeUnits(text) }

    val resolvedColor = color.takeOrElse {
        style.color.takeOrElse { LocalContentColor.current }
    }
    val flapAccent = MaterialTheme.colorScheme.primary
    val flapOnAccent = MaterialTheme.colorScheme.onPrimary

    var elapsedMs by remember(text, triggerKey, animEnabled) {
        mutableIntStateOf(if (!animEnabled || units.isEmpty()) Int.MAX_VALUE else -1)
    }
    var settled by remember(text, triggerKey, animEnabled) {
        mutableStateOf(!animEnabled || units.isEmpty())
    }

    // Cap effective stagger index so even long strings finish crisply in ~620ms
    val effectiveSlots = units.size.coerceIn(1, 24)
    val totalAnimMs = (effectiveSlots - 1) * charStaggerMs + flapDurationMs

    LaunchedEffect(text, triggerKey, animEnabled) {
        if (!animEnabled || units.isEmpty()) {
            settled = true
            return@LaunchedEffect
        }
        settled = false
        elapsedMs = -1
        if (delayMillis > 0) {
            delay(delayMillis.toLong())
        }
        val startFrame = withFrameMillis { it }
        while (true) {
            val now = withFrameMillis { it }
            val dt = (now - startFrame).toInt()
            if (dt >= totalAnimMs) {
                settled = true
                break
            }
            // ~30Hz mechanical split-flap cadence: authentic Solari rhythm + minimal recompositions
            val quantized = (dt / 32) * 32
            if (quantized != elapsedMs) {
                elapsedMs = quantized
            }
        }
    }

    if (settled || units.isEmpty()) {
        Text(
            text = text,
            modifier = modifier,
            style = style,
            color = resolvedColor,
            fontSize = fontSize,
            fontWeight = fontWeight,
            fontFamily = fontFamily,
            lineHeight = lineHeight,
            maxLines = maxLines,
            overflow = overflow,
            textDecoration = textDecoration,
        )
        return
    }

    val tick = elapsedMs
    val display: AnnotatedString = remember(text, tick, resolvedColor, flapAccent, flapOnAccent) {
        buildAnnotatedString {
            val slotScale = if (units.size > 24) 24f / units.size.toFloat() else 1f
            for (i in units.indices) {
                val targetUnit = units[i]
                if (targetUnit == " " || targetUnit == "\n") {
                    append(targetUnit)
                    continue
                }
                val startAt = (i * slotScale * charStaggerMs).toInt()
                val localElapsed = tick - startAt
                when {
                    tick < 0 || localElapsed < 0 -> {
                        withStyle(
                            SpanStyle(
                                color = resolvedColor.copy(alpha = 0.24f),
                                fontFamily = FontFamily.Monospace
                            )
                        ) {
                            append("▪")
                        }
                    }
                    localElapsed >= flapDurationMs -> {
                        withStyle(SpanStyle(color = resolvedColor)) {
                            append(targetUnit)
                        }
                    }
                    else -> {
                        val step = localElapsed / 32
                        val glyphIdx = ((i * 11) + (step * 7) + targetUnit.hashCode().ushr(1)) % SOLARI_GLYPHS.length
                        val flapChar = SOLARI_GLYPHS[if (glyphIdx < 0) -glyphIdx else glyphIdx]
                        withStyle(
                            SpanStyle(
                                color = flapOnAccent,
                                background = flapAccent,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Black,
                            )
                        ) {
                            append(flapChar)
                        }
                    }
                }
            }
        }
    }

    Text(
        text = display,
        modifier = modifier,
        style = style,
        fontSize = fontSize,
        fontWeight = fontWeight,
        fontFamily = fontFamily,
        lineHeight = lineHeight,
        maxLines = maxLines,
        overflow = overflow,
        textDecoration = textDecoration,
    )
}

/**
 * Smooth staggered text fade-in + subtle upward mechanical settle.
 * Ideal for descriptions, package names, authors, and setting summaries.
 */
@Composable
fun FadeInText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = LocalTextStyle.current,
    color: Color = Color.Unspecified,
    fontSize: TextUnit = TextUnit.Unspecified,
    fontWeight: FontWeight? = null,
    fontFamily: FontFamily? = null,
    lineHeight: TextUnit = TextUnit.Unspecified,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textDecoration: TextDecoration? = null,
    delayMillis: Int = 75,
    durationMillis: Int = 320,
    triggerKey: Any? = Unit,
) {
    val progress = remember(text, triggerKey) { Animatable(0f) }
    LaunchedEffect(text, triggerKey) {
        progress.snapTo(0f)
        if (delayMillis > 0) delay(delayMillis.toLong())
        progress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = durationMillis, easing = FastOutSlowInEasing)
        )
    }
    val p = progress.value
    Text(
        text = text,
        modifier = modifier.graphicsLayer {
            alpha = p
            translationY = (1f - p) * 12f
        },
        style = style,
        color = color,
        fontSize = fontSize,
        fontWeight = fontWeight,
        fontFamily = fontFamily,
        lineHeight = lineHeight,
        maxLines = maxLines,
        overflow = overflow,
        textDecoration = textDecoration,
    )
}

/**
 * Staggered Cyberbrutalist card / row entrance with a top-edge Acid-Volt laser scan wipe.
 */
@Composable
fun BrutalStaggerItem(
    index: Int,
    modifier: Modifier = Modifier,
    triggerKey: Any? = Unit,
    content: @Composable () -> Unit,
) {
    val progress = remember(triggerKey) { Animatable(0f) }
    val clampedIndex = index.coerceIn(0, 10)
    val scanColor = MaterialTheme.colorScheme.primary

    LaunchedEffect(triggerKey) {
        progress.snapTo(0f)
        val waitMs = clampedIndex * 38
        if (waitMs > 0) delay(waitMs.toLong())
        progress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 320, easing = FastOutSlowInEasing)
        )
    }

    val p = progress.value
    Box(
        modifier = modifier
            .graphicsLayer {
                alpha = p
                translationY = (1f - p) * 24f
                val s = 0.985f + (0.015f * p)
                scaleX = s
                scaleY = s
            }
            .drawWithContent {
                drawContent()
                if (p in 0.03f..0.97f) {
                    val beamW = size.width * 0.36f
                    val xStart = (size.width + beamW) * p - beamW
                    val left = xStart.coerceAtLeast(0f)
                    val right = (xStart + beamW).coerceAtMost(size.width)
                    if (right > left) {
                        drawLine(
                            color = scanColor.copy(alpha = (1f - p) * 0.95f),
                            start = Offset(left, 1.dp.toPx()),
                            end = Offset(right, 1.dp.toPx()),
                            strokeWidth = 2.dp.toPx()
                        )
                    }
                }
            }
    ) {
        content()
    }
}

/**
 * Industrial Cyberbrutalist frame decorator:
 * - 1.dp exposed structural border
 * - Corner L-bracket registration ticks (top-left & bottom-right)
 * - Optional 3.5.dp active signal rail on the leading edge
 */
fun Modifier.brutalPlate(
    active: Boolean = false,
    accent: Color? = null,
): Modifier = composed {
    val borderColor = MaterialTheme.colorScheme.outline
    val railColor = accent ?: MaterialTheme.colorScheme.primary
    val cornerSecondary = MaterialTheme.colorScheme.secondary

    this.drawWithContent {
        drawContent()
        val stroke = 1.dp.toPx()
        val w = size.width
        val h = size.height

        // Structural perimeter line
        drawRect(
            color = if (active) railColor.copy(alpha = 0.55f) else borderColor.copy(alpha = 0.78f),
            style = Stroke(width = stroke)
        )

        // Active left signal rail
        if (active) {
            val railW = 3.5.dp.toPx()
            drawRect(
                color = railColor,
                topLeft = Offset(0f, 0f),
                size = Size(railW, h)
            )
        }

        // Precision corner L-brackets
        val arm = 9.dp.toPx()
        val thick = 1.8.dp.toPx()
        val inset = 3.dp.toPx()
        // Top-left L
        drawLine(railColor, Offset(inset, inset), Offset(inset + arm, inset), strokeWidth = thick)
        drawLine(railColor, Offset(inset, inset), Offset(inset, inset + arm), strokeWidth = thick)
        // Bottom-right L
        drawLine(cornerSecondary, Offset(w - inset - arm, h - inset), Offset(w - inset, h - inset), strokeWidth = thick)
        drawLine(cornerSecondary, Offset(w - inset, h - inset - arm), Offset(w - inset, h - inset), strokeWidth = thick)
    }
}

/**
 * Fullscreen architectural Cyberbrutalist backdrop behind all screens:
 * - Precision 28.dp technical grid + 112.dp sector crosshairs (+)
 * - Calm drifting telemetry scanline beam
 * - Adapts automatically to Obsidian Dark, AMOLED Black, and Daylight Industrial modes
 */
@Composable
fun CyberBrutalBackdrop(modifier: Modifier = Modifier) {
    val bg = MaterialTheme.colorScheme.background
    val isDark = bg.luminance() < 0.4f
    val isAmoled = bg == Color.Black

    val transition = rememberInfiniteTransition(label = "cyberBrutalBackdrop")
    val scanProgress by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 9500, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "brutalScan"
    )

    val topGrad = when {
        isAmoled -> Color.Black
        isDark -> BRUTAL_BG_DARK
        else -> BRUTAL_BG_LIGHT
    }
    val botGrad = when {
        isAmoled -> Color(0xFF040608)
        isDark -> BRUTAL_BG_DARK_ALT
        else -> BRUTAL_BG_LIGHT_ALT
    }
    val minorGrid = when {
        isAmoled -> Color(0xFF10141D)
        isDark -> Color(0xFF151923)
        else -> Color(0xFFDAD8CE)
    }
    val majorGrid = when {
        isAmoled -> Color(0xFF1A2130)
        isDark -> Color(0xFF202736)
        else -> Color(0xFFC8C5B8)
    }
    val accent = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(topGrad, botGrad)))
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            val step = 28.dp.toPx()
            val stroke = 1.dp.toPx()

            var colIdx = 0
            var x = 0f
            while (x <= w) {
                drawLine(
                    color = if (colIdx % 4 == 0) majorGrid else minorGrid,
                    start = Offset(x, 0f),
                    end = Offset(x, h),
                    strokeWidth = stroke
                )
                x += step
                colIdx++
            }

            var rowIdx = 0
            var y = 0f
            while (y <= h) {
                drawLine(
                    color = if (rowIdx % 4 == 0) majorGrid else minorGrid,
                    start = Offset(0f, y),
                    end = Offset(w, y),
                    strokeWidth = stroke
                )
                y += step
                rowIdx++
            }

            // Sector registration crosshairs (+) at major intersections
            val crossArm = 3.5.dp.toPx()
            var cx = step * 4
            while (cx < w) {
                var cy = step * 4
                while (cy < h) {
                    drawLine(accent.copy(alpha = 0.22f), Offset(cx - crossArm, cy), Offset(cx + crossArm, cy), strokeWidth = stroke)
                    drawLine(accent.copy(alpha = 0.22f), Offset(cx, cy - crossArm), Offset(cx, cy + crossArm), strokeWidth = stroke)
                    cy += step * 4
                }
                cx += step * 4
            }

            // Drifting horizontal telemetry scanline + soft trail
            val scanY = h * scanProgress
            val trailH = 84.dp.toPx()
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(Color.Transparent, accent.copy(alpha = if (isDark) 0.06f else 0.05f), accent.copy(alpha = 0.16f)),
                    startY = (scanY - trailH).coerceAtLeast(0f),
                    endY = scanY
                ),
                topLeft = Offset(0f, (scanY - trailH).coerceAtLeast(0f)),
                size = Size(w, trailH.coerceAtMost(scanY))
            )
            drawLine(
                color = accent.copy(alpha = 0.35f),
                start = Offset(0f, scanY),
                end = Offset(w, scanY),
                strokeWidth = 1.2.dp.toPx()
            )

            // Subtle corner diagonal accent in top-right
            val diag = 72.dp.toPx()
            drawLine(secondary.copy(alpha = 0.18f), Offset(w - diag, 0f), Offset(w, diag), strokeWidth = 1.5.dp.toPx())
        }
    }
}

/**
 * Cyberbrutalist mechanical startup splash:
 * - Chamfered geometric reticle with precision telemetry arcs
 * - Solari Airport Departure Board flip for SYNTHETICA + CYBERBRUTAL // 2.1
 * - Segmented boot progress bar & staggered fade-in kernel link lines
 */
@Composable
fun BrutalSplash(
    progress: Float = 0f,
    modifier: Modifier = Modifier,
) {
    val volt = MaterialTheme.colorScheme.primary
    val cyan = MaterialTheme.colorScheme.secondary
    val dim = MaterialTheme.colorScheme.onSurfaceVariant

    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Geometric Chamfered Emblem + Reticle
            Canvas(modifier = Modifier.size(138.dp)) {
                val w = size.width
                val h = size.height
                val cut = 22.dp.toPx()
                val pad = 10.dp.toPx()

                val frame = Path().apply {
                    moveTo(pad, pad)
                    lineTo(w - pad - cut, pad)
                    lineTo(w - pad, pad + cut)
                    lineTo(w - pad, h - pad)
                    lineTo(pad + cut, h - pad)
                    lineTo(pad, h - pad - cut)
                    close()
                }
                drawPath(frame, color = volt.copy(alpha = 0.10f))
                drawPath(frame, color = volt, style = Stroke(width = 2.dp.toPx()))

                // Inner chamfered 'S' bars
                val barH = 12.dp.toPx()
                val left = w * 0.30f
                val right = w * 0.70f
                val topY = h * 0.28f
                val midY = h * 0.46f
                val botY = h * 0.64f

                drawRect(volt, topLeft = Offset(left, topY), size = Size(right - left, barH))
                drawRect(volt, topLeft = Offset(left, topY), size = Size(barH, midY - topY + barH))
                drawRect(volt, topLeft = Offset(left, midY), size = Size(right - left, barH))
                drawRect(volt, topLeft = Offset(right - barH, midY), size = Size(barH, botY - midY + barH))
                drawRect(volt, topLeft = Offset(left, botY), size = Size(right - left, barH))

                // Cyan registration ticks driven by splash progress
                val sweep = (progress.coerceIn(0f, 1f)) * (w - pad * 2)
                drawLine(
                    color = cyan,
                    start = Offset(pad, h - pad + 6.dp.toPx()),
                    end = Offset(pad + sweep, h - pad + 6.dp.toPx()),
                    strokeWidth = 3.dp.toPx()
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            DepartureBoardText(
                text = "SYNTHETICA",
                style = MaterialTheme.typography.displaySmall,
                color = MaterialTheme.colorScheme.onBackground,
                charStaggerMs = 30,
                flapDurationMs = 240,
            )

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Box(
                    modifier = Modifier
                        .background(volt)
                        .padding(horizontal = 8.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = "v${BuildConfig.VERSION_NAME}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onPrimary,
                        fontWeight = FontWeight.Black
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                DepartureBoardText(
                    text = "CYBERBRUTAL // EDITION",
                    style = MaterialTheme.typography.labelMedium,
                    color = cyan,
                    delayMillis = 120,
                    charStaggerMs = 16,
                )
            }

            Spacer(modifier = Modifier.height(22.dp))

            // Segmented industrial progress bar [##########..]
            val totalBlocks = 16
            val litBlocks = (progress.coerceIn(0f, 1f) * totalBlocks).toInt()
            Row(
                modifier = Modifier
                    .border(1.dp, MaterialTheme.colorScheme.outline)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                for (b in 0 until totalBlocks) {
                    Box(
                        modifier = Modifier
                            .width(10.dp)
                            .height(6.dp)
                            .background(if (b < litBlocks) volt else dim.copy(alpha = 0.18f))
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            FadeInText(
                text = "SYS.NODE // JOYEUSE :: KERNELSU-NEXT + SUSFS",
                style = MaterialTheme.typography.labelSmall,
                color = dim,
                delayMillis = 160
            )
            FadeInText(
                text = "SEC.LINK // CERT_0x565 :: READY",
                style = MaterialTheme.typography.labelSmall,
                color = dim.copy(alpha = 0.78f),
                delayMillis = 300
            )
        }
    }
}
