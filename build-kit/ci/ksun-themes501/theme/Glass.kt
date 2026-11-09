package com.rifsxd.ksunext.ui.theme

import android.os.Build
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBackIos
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlurEffect
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.layer.GraphicsLayer
import androidx.compose.ui.graphics.layer.drawLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlinx.coroutines.delay

/**
 * Synthetica 5.0.1 Multi-Theme Surface & Glass Tokens.
 */
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
    canvasBase = Color(0xFFF3F2EC),
    cardTintTop = Color(0xFFFFFFFF),
    cardTintBottom = Color(0xFFFFFFFF),
    elevatedTintTop = Color(0xFFFFFFFF),
    elevatedTintBottom = Color(0xFFFFFFFF),
    barTintTop = Color(0xFFF3F2EC),
    barTintBottom = Color(0xFFF3F2EC),
    dockTintTop = Color(0xFFFFFFFF),
    dockTintBottom = Color(0xFFFFFFFF),
    dockActivePill = Color(0xFFE7E6DF),
    borderHighlight = Color(0xFF8C8B84),
    borderMid = Color(0xFFBCBBB4),
    borderShadow = Color(0xFF8C8B84),
    divider = Color(0xFFD5D4CC),
    shadowColor = Color.Transparent,
    blurRadius = 0.dp,
    dockBlurRadius = 0.dp,
)

val DarkGlassStyle = GlassStyle(
    isDark = true,
    isAmoled = false,
    canvasBase = Color(0xFF101010),
    cardTintTop = Color(0xFF1C1C1A),
    cardTintBottom = Color(0xFF1C1C1A),
    elevatedTintTop = Color(0xFF252523),
    elevatedTintBottom = Color(0xFF252523),
    barTintTop = Color(0xFF101010),
    barTintBottom = Color(0xFF101010),
    dockTintTop = Color(0xFF1C1C1A),
    dockTintBottom = Color(0xFF1C1C1A),
    dockActivePill = Color(0xFF2E2E2B),
    borderHighlight = Color(0xFF565650),
    borderMid = Color(0xFF393935),
    borderShadow = Color(0xFF393935),
    divider = Color(0xFF363632),
    shadowColor = Color.Transparent,
    blurRadius = 0.dp,
    dockBlurRadius = 0.dp,
)

val AmoledGlassStyle = DarkGlassStyle.copy(
    isAmoled = true,
    canvasBase = Color.Black,
    cardTintTop = Color(0xFF121211),
    cardTintBottom = Color(0xFF121211),
    elevatedTintTop = Color(0xFF191917),
    elevatedTintBottom = Color(0xFF191917),
    barTintTop = Color.Black,
    barTintBottom = Color.Black,
    dockTintTop = Color(0xFF141413),
    dockTintBottom = Color(0xFF141413),
    borderHighlight = Color(0xFF565650),
    borderMid = Color(0xFF30302C),
    borderShadow = Color(0xFF30302C),
    divider = Color(0xFF2E2E2A),
    shadowColor = Color.Transparent,
)

val LocalGlassStyle = compositionLocalOf { DarkGlassStyle }

/**
 * Live GPU RenderNode layers for real-time iOS backdrop blur:
 * - [LocalGlassWallpaperLayer]: captures the animated aurora [GlassBackground] for cards & headers.
 * - [LocalGlassContentLayer]: captures [GlassBackground] + screen body for floating overlays (dock).
 */
val LocalGlassWallpaperLayer = compositionLocalOf<GraphicsLayer?> { null }
val LocalGlassContentLayer = compositionLocalOf<GraphicsLayer?> { null }

/**
 * Distinct live wallpapers for all 4 themes, with a truly black canvas in AMOLED mode.
 */
@Composable
fun GlassBackground(
    modifier: Modifier = Modifier,
    wallpaperLayer: GraphicsLayer? = LocalGlassWallpaperLayer.current,
) {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val phase by rememberStylePhase()
    val accent = MaterialTheme.colorScheme.primary
    Canvas(modifier = modifier.fillMaxSize().drawWithContent {
        if (wallpaperLayer != null) {
            wallpaperLayer.record { this@drawWithContent.drawContent() }
            drawLayer(wallpaperLayer)
        } else drawContent()
    }) {
        drawRect(glass.canvasBase)
        if (!glass.isAmoled) when (style) {
            ManagerStyle.PIXEL -> {
                // Full-screen Nothing OS / Pixel dot-matrix grid + animated stepped LED equalizer
                val gridPitch = 20.dp.toPx()
                val baseDot = 1.8.dp.toPx()
                val gridInk = if (glass.isDark) Color.White.copy(alpha = 0.055f) else Color.Black.copy(alpha = 0.055f)
                var gx = gridPitch
                while (gx < size.width - gridPitch * 0.5f) {
                    var gy = gridPitch
                    while (gy < size.height - gridPitch * 0.5f) {
                        drawRect(gridInk, topLeft = Offset(gx, gy), size = Size(baseDot, baseDot))
                        gy += gridPitch
                    }
                    gx += gridPitch
                }
                // Stepped LED matrix cluster in top-right & bottom-left
                val pitch = 8.dp.toPx()
                val dot = 3.dp.toPx()
                val startX = size.width - pitch * 14f
                val startY = 18.dp.toPx()
                val activeStep = (phase * 12f).roundToInt().coerceIn(0, 12)
                for (row in 0 until 8) for (col in 0 until 13) {
                    val wave = (col + activeStep) % 7
                    val lit = row >= (7 - wave.coerceAtMost(6))
                    val ink = if (lit) accent.copy(alpha = if (glass.isDark) 0.52f else 0.40f)
                    else if (glass.isDark) Color.White.copy(alpha = 0.09f) else Color.Black.copy(alpha = 0.09f)
                    drawRect(ink, topLeft = Offset(startX + col * pitch, startY + row * pitch), size = Size(dot, dot))
                }
            }
            ManagerStyle.CYBERPUNK -> {
                // Synthetica 2.1 CyberBrutalBackdrop: architectural grid + sector crosshairs + sweeping horizontal laser scanline
                val pitch = 28.dp.toPx()
                val gridAlpha = if (glass.isDark) 0.065f else 0.08f
                val crossLen = 4.dp.toPx()
                var x = 0f
                var col = 0
                while (x <= size.width) {
                    drawLine(accent.copy(alpha = gridAlpha), Offset(x, 0f), Offset(x, size.height), 1.dp.toPx())
                    var y = 0f
                    var row = 0
                    while (y <= size.height) {
                        if (col == 0) {
                            drawLine(accent.copy(alpha = gridAlpha), Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
                        }
                        if (col % 4 == 0 && row % 4 == 0) {
                            drawLine(accent.copy(alpha = gridAlpha * 2.4f), Offset(x - crossLen, y), Offset(x + crossLen, y), 1.2.dp.toPx())
                            drawLine(accent.copy(alpha = gridAlpha * 2.4f), Offset(x, y - crossLen), Offset(x, y + crossLen), 1.2.dp.toPx())
                        }
                        y += pitch
                        row++
                    }
                    x += pitch
                    col++
                }
                // Sweeping horizontal telemetry scanline beam
                val scanY = size.height * phase
                val bandH = 54.dp.toPx()
                drawRect(
                    brush = Brush.verticalGradient(
                        colors = listOf(Color.Transparent, accent.copy(alpha = 0.09f), Color(0xFF00F0FF).copy(alpha = 0.06f), Color.Transparent),
                        startY = (scanY - bandH).coerceAtLeast(0f),
                        endY = (scanY + bandH).coerceAtMost(size.height),
                    ),
                    topLeft = Offset(0f, (scanY - bandH).coerceAtLeast(0f)),
                    size = Size(size.width, bandH * 2f),
                )
                drawLine(
                    color = accent.copy(alpha = 0.42f),
                    start = Offset(0f, scanY),
                    end = Offset(size.width, scanY),
                    strokeWidth = 1.4.dp.toPx(),
                )
                // Top-right industrial hazard slashes
                val gap = 11.dp.toPx()
                val activeSlash = (phase * 7f).roundToInt()
                for (i in 0..7) {
                    val px = size.width - (20 + i * 11).dp.toPx()
                    drawLine(
                        color = accent.copy(alpha = if (i == activeSlash) 0.65f else 0.20f),
                        start = Offset(px, 16.dp.toPx()),
                        end = Offset(px - gap * 1.5f, 16.dp.toPx() + gap * 1.5f),
                        strokeWidth = 2.2.dp.toPx(),
                    )
                }
            }
            ManagerStyle.IOS_GLASS -> {
                // Orbiting 2.0 iOS Liquid Glass aurora blooms that refract through blurred cards
                val angle = phase * (2f * Math.PI.toFloat())
                val radius = size.width * 0.88f
                val first = Offset(
                    x = size.width * (0.76f + 0.14f * cos(angle)),
                    y = size.height * (0.18f + 0.08f * sin(angle)),
                )
                val second = Offset(
                    x = size.width * (0.20f - 0.12f * cos(angle)),
                    y = size.height * (0.68f + 0.10f * sin(angle * 0.8f)),
                )
                val third = Offset(
                    x = size.width * (0.52f + 0.18f * sin(angle)),
                    y = size.height * (0.44f - 0.09f * cos(angle)),
                )
                drawCircle(
                    brush = Brush.radialGradient(listOf(accent.copy(alpha = if (glass.isDark) 0.34f else 0.24f), Color.Transparent), first, radius),
                    radius = radius,
                    center = first,
                )
                drawCircle(
                    brush = Brush.radialGradient(listOf(Color(0xFFAF83FF).copy(alpha = if (glass.isDark) 0.22f else 0.16f), Color.Transparent), second, radius),
                    radius = radius,
                    center = second,
                )
                drawCircle(
                    brush = Brush.radialGradient(listOf(Color(0xFF00E5FF).copy(alpha = if (glass.isDark) 0.18f else 0.12f), Color.Transparent), third, radius * 0.72f),
                    radius = radius * 0.72f,
                    center = third,
                )
            }
            ManagerStyle.NEON -> {
                // 3.1 Cyberpunk Neon Overdrive: orbiting cyan/magenta plasma blooms + perspective horizon grid + vertical laser rail
                val angle = phase * (2f * Math.PI.toFloat())
                val magenta = Color(0xFFFF4DCD)
                val radius = size.width * 0.82f
                val first = Offset(
                    x = size.width * (0.85f + 0.10f * cos(angle)),
                    y = size.height * (0.16f + 0.07f * sin(angle)),
                )
                val second = Offset(
                    x = size.width * (0.14f - 0.09f * sin(angle)),
                    y = size.height * (0.76f + 0.08f * cos(angle)),
                )
                drawCircle(Brush.radialGradient(listOf(accent.copy(alpha = 0.28f), Color.Transparent), first, radius), radius = radius, center = first)
                drawCircle(Brush.radialGradient(listOf(magenta.copy(alpha = 0.18f), Color.Transparent), second, radius), radius = radius, center = second)
                // Perspective cyber grid in lower third
                val horizonY = size.height * 0.68f
                val gridRows = 6
                for (r in 0..gridRows) {
                    val frac = ((r.toFloat() / gridRows) + phase * 0.25f) % 1f
                    val y = horizonY + (size.height - horizonY) * (frac * frac)
                    drawLine(
                        color = accent.copy(alpha = 0.05f + 0.10f * frac),
                        start = Offset(0f, y),
                        end = Offset(size.width, y),
                        strokeWidth = 1.dp.toPx(),
                    )
                }
                val railY = 24.dp.toPx() + (size.height * 0.45f) * phase
                drawLine(
                    brush = Brush.verticalGradient(listOf(Color.Transparent, accent.copy(alpha = 0.55f), magenta.copy(alpha = 0.45f), Color.Transparent)),
                    start = Offset(size.width - 4.dp.toPx(), railY),
                    end = Offset(size.width - 4.dp.toPx(), railY + 110.dp.toPx()),
                    strokeWidth = 3.dp.toPx(),
                )
            }
        }
    }
}

/** Theme geometry, live card animations, and genuine backdrop blur for iOS on Android 12+. */
fun Modifier.iosGlass(
    shape: Shape = RoundedCornerShape(22.dp),
    blurRadius: Dp = Dp.Unspecified,
    tintTop: Color = Color.Unspecified,
    tintBottom: Color = Color.Unspecified,
    borderWidth: Dp = 1.dp,
    elevation: Dp = 6.dp,
    blurContent: Boolean = false,
): Modifier = composed {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val phase by rememberStylePhase()
    val accent = MaterialTheme.colorScheme.primary
    val intensity = LocalNeonGlow.current
    val top = if (tintTop != Color.Unspecified) tintTop else glass.cardTintTop
    val bottom = if (tintBottom != Color.Unspecified) tintBottom else glass.cardTintBottom
    val panelShape = if (shape == RectangleShape) RectangleShape else when (style) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> if (shape is CutCornerShape) shape
        else CutCornerShape(topStart = 0.dp, topEnd = 18.dp, bottomEnd = 0.dp, bottomStart = 18.dp)
        ManagerStyle.IOS_GLASS, ManagerStyle.NEON -> shape
    }
    if (style == ManagerStyle.IOS_GLASS) {
        val wallpaper = LocalGlassWallpaperLayer.current
        val content = LocalGlassContentLayer.current
        val sampleLayer = rememberGraphicsLayer()
        var posInRoot by remember { mutableStateOf(Offset.Zero) }
        val resolvedBlur = if (blurRadius != Dp.Unspecified) blurRadius else glass.blurRadius
        this.onGloballyPositioned { posInRoot = it.positionInRoot() }
            .let {
                if (elevation > 0.dp && shape != RectangleShape) {
                    it.shadow(elevation.coerceAtMost(6.dp), panelShape, ambientColor = glass.shadowColor, spotColor = glass.shadowColor)
                } else it
            }
            .clip(panelShape)
            .drawWithCache {
                val blurPx = resolvedBlur.toPx()
                val pad = blurPx.roundToInt().coerceIn(0, 64)
                val src = if (blurContent) (content ?: wallpaper) else wallpaper
                val canBlur = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && src != null && !glass.isAmoled && blurPx > .5f
                val alpha = if (canBlur) if (glass.isDark) .87f else .83f else 1f
                val iosTop = if (top.alpha < 1f) top.compositeOver(glass.cardTintTop) else top
                val iosBottom = if (bottom.alpha < 1f) bottom.compositeOver(glass.cardTintBottom) else bottom
                val tint = Brush.verticalGradient(listOf(iosTop.copy(alpha = alpha), iosBottom.copy(alpha = alpha)))
                val sheen = Brush.verticalGradient(
                    0f to Color.White.copy(alpha = if (glass.isDark) .12f else .50f),
                    .34f to Color.Transparent,
                )
                onDrawBehind {
                    val w = size.width.roundToInt()
                    val h = size.height.roundToInt()
                    if (canBlur && src != null && w > 0 && h > 0) {
                        sampleLayer.renderEffect = BlurEffect(blurPx, blurPx, TileMode.Clamp)
                        sampleLayer.record(size = IntSize((w + pad * 2).coerceAtLeast(1), (h + pad * 2).coerceAtLeast(1))) {
                            translate(left = -posInRoot.x + pad, top = -posInRoot.y + pad) { drawLayer(src) }
                        }
                        translate(left = -pad.toFloat(), top = -pad.toFloat()) { drawLayer(sampleLayer) }
                    }
                    drawRect(tint)
                    drawRect(sheen)
                }
            }
            .let {
                if (borderWidth > 0.dp) {
                    it.border(borderWidth, Brush.linearGradient(listOf(glass.borderHighlight, glass.borderMid, glass.borderShadow)), panelShape)
                } else it
            }
    } else {
        val border = when (style) {
            ManagerStyle.NEON -> Brush.linearGradient(
                listOf(accent.copy(alpha = .84f), glass.borderMid, Color(0xFFE75DDE).copy(alpha = .65f))
            )
            ManagerStyle.CYBERPUNK -> Brush.linearGradient(
                listOf(accent.copy(alpha = .72f), glass.borderHighlight, glass.borderMid)
            )
            else -> Brush.linearGradient(listOf(glass.borderHighlight, glass.borderHighlight))
        }
        this.clip(panelShape)
            .background(Brush.verticalGradient(listOf(top, bottom)))
            .let { if (borderWidth > 0.dp) it.border(borderWidth, border, panelShape) else it }
            .drawBehind {
                if (shape != RectangleShape && size.width > 110.dp.toPx() && size.height > 38.dp.toPx()) {
                    when (style) {
                        ManagerStyle.PIXEL -> {
                            val unit = 3.5.dp.toPx()
                            val gap = 3.dp.toPx()
                            val start = size.width - 28.dp.toPx()
                            val lit = (phase * 4f).roundToInt().coerceIn(0, 4)
                            for (i in 0..4) {
                                val alpha = if (i == lit) .85f else (.18f * intensity).coerceAtMost(.38f)
                                drawRect(
                                    color = accent.copy(alpha = alpha),
                                    topLeft = Offset(start + i * (unit + gap), 5.dp.toPx()),
                                    size = Size(unit, unit),
                                )
                            }
                        }
                        ManagerStyle.CYBERPUNK -> {
                            // Left vertical acid-volt signal rail + animated top laser registration sweep
                            drawRect(
                                color = accent.copy(alpha = .85f),
                                topLeft = Offset(0f, 10.dp.toPx()),
                                size = Size(4.dp.toPx(), (size.height - 20.dp.toPx()).coerceAtLeast(16.dp.toPx())),
                            )
                            val sweepW = 36.dp.toPx()
                            val sweepX = 12.dp.toPx() + (size.width - 64.dp.toPx()).coerceAtLeast(1f) * phase
                            drawLine(
                                color = accent.copy(alpha = .62f),
                                start = Offset(sweepX, 1.5.dp.toPx()),
                                end = Offset(sweepX + sweepW, 1.5.dp.toPx()),
                                strokeWidth = 2.dp.toPx(),
                            )
                        }
                        ManagerStyle.NEON -> {
                            val magenta = Color(0xFFFF4FD8)
                            val beamW = 68.dp.toPx()
                            val beamX = 14.dp.toPx() + (size.width - 96.dp.toPx()).coerceAtLeast(1f) * phase
                            drawLine(
                                brush = Brush.horizontalGradient(listOf(Color.Transparent, accent.copy(alpha = (.68f * intensity).coerceAtMost(.88f)), magenta.copy(alpha = .65f), Color.Transparent)),
                                start = Offset(beamX, 1.5.dp.toPx()),
                                end = Offset(beamX + beamW, 1.5.dp.toPx()),
                                strokeWidth = 3.dp.toPx(),
                            )
                        }
                        ManagerStyle.IOS_GLASS -> Unit
                    }
                }
            }
    }
}

@Composable
private fun TopBarStyleEmblem(style: ManagerStyle, phase: Float) {
    val accent = MaterialTheme.colorScheme.primary
    val emblemRes = emblemResForStyle(style)
    when (style) {
        ManagerStyle.PIXEL -> {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .background(Color(0xFF101010))
                    .border(1.2.dp, accent, RectangleShape)
                    .padding(2.dp),
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
        ManagerStyle.CYBERPUNK -> {
            val cutShape = CutCornerShape(topStart = 2.dp, topEnd = 9.dp, bottomEnd = 2.dp, bottomStart = 9.dp)
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(cutShape)
                    .background(Color(0xFF0A0D12))
                    .border(1.2.dp, accent, cutShape)
                    .padding(2.dp),
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize().clip(cutShape),
                )
            }
        }
        ManagerStyle.IOS_GLASS -> {
            val badgeShape = RoundedCornerShape(11.dp)
            Image(
                painter = painterResource(emblemRes),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(36.dp)
                    .shadow(6.dp, badgeShape, ambientColor = accent.copy(alpha = 0.45f))
                    .clip(badgeShape)
                    .border(1.dp, Color.White.copy(alpha = 0.60f), badgeShape),
            )
        }
        ManagerStyle.NEON -> {
            val badgeShape = RoundedCornerShape(10.dp)
            val magenta = Color(0xFFFF4FD8)
            val pulse = 0.7f + 0.3f * abs(sin(phase * Math.PI.toFloat()))
            Image(
                painter = painterResource(emblemRes),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(36.dp)
                    .clip(badgeShape)
                    .border(
                        width = 1.4.dp,
                        brush = Brush.linearGradient(listOf(accent.copy(alpha = pulse), magenta.copy(alpha = pulse))),
                        shape = badgeShape,
                    ),
            )
        }
    }
}

/**
 * Theme-adaptive Top Navigation Bar: changes layout, header telemetry strip, PNG emblem and divider per style.
 */
@Composable
fun GlassTopBar(
    title: String,
    subtitle: String? = null,
    leading: (@Composable () -> Unit)? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
) {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val phase by rememberStylePhase()
    val accent = MaterialTheme.colorScheme.primary

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RectangleShape,
                blurRadius = glass.dockBlurRadius,
                tintTop = glass.barTintTop,
                tintBottom = glass.barTintBottom,
                borderWidth = 0.dp,
                elevation = 0.dp,
                blurContent = false,
            )
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)),
    ) {
        // Style-specific micro header strip for PIXEL, CYBERPUNK, and NEON
        when (style) {
            ManagerStyle.PIXEL -> {
                val litDot = (phase * 4f).roundToInt().coerceIn(0, 4)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(accent.copy(alpha = 0.10f))
                        .padding(horizontal = 14.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = "■ PIXEL.OS // MATRIX",
                        style = MaterialTheme.typography.labelSmall,
                        color = accent,
                        letterSpacing = 1.2.sp,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                        for (i in 0..4) {
                            Box(
                                modifier = Modifier
                                    .size(4.dp)
                                    .background(accent.copy(alpha = if (i == litDot) 0.90f else 0.24f)),
                            )
                        }
                    }
                }
            }
            ManagerStyle.CYBERPUNK -> {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(accent.copy(alpha = 0.12f))
                        .padding(horizontal = 14.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = "/// SEC.GRID // CYBERBRUTAL",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = accent,
                        letterSpacing = 1.1.sp,
                    )
                    Text(
                        text = "[5.0.1]",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF00F0FF),
                    )
                }
            }
            ManagerStyle.NEON -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(2.dp)
                        .background(
                            Brush.horizontalGradient(
                                listOf(accent, Color(0xFFFF4FD8), accent.copy(alpha = 0.25f))
                            )
                        ),
                )
            }
            ManagerStyle.IOS_GLASS -> Unit
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 58.dp)
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                val backShape = when (style) {
                    ManagerStyle.PIXEL -> RectangleShape
                    ManagerStyle.CYBERPUNK -> CutCornerShape(topStart = 0.dp, topEnd = 8.dp, bottomEnd = 0.dp, bottomStart = 8.dp)
                    ManagerStyle.IOS_GLASS -> CircleShape
                    ManagerStyle.NEON -> RoundedCornerShape(10.dp)
                }
                IconButton(
                    onClick = onBack,
                    modifier = Modifier
                        .size(42.dp)
                        .clip(backShape)
                        .background(accent.copy(alpha = 0.12f))
                        .border(1.dp, accent.copy(alpha = 0.40f), backShape),
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Rounded.ArrowBackIos,
                        contentDescription = stringResource(R.string.neon_back),
                        tint = accent,
                        modifier = Modifier.size(18.dp),
                    )
                }
                Spacer(Modifier.width(8.dp))
            } else if (leading != null) {
                // Render the active theme's PNG emblem instead of the static 4.0 Pixel drawable
                TopBarStyleEmblem(style = style, phase = phase)
                Spacer(Modifier.width(10.dp))
            } else {
                Spacer(Modifier.width(4.dp))
            }

            Column(modifier = Modifier.weight(1f)) {
                if (style == ManagerStyle.CYBERPUNK) {
                    DepartureBoardText(
                        text = title,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                    )
                } else {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (style == ManagerStyle.NEON || style == ManagerStyle.CYBERPUNK) accent else MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                // The transparent Scaffold otherwise leaves action icons black on dark themes.
                CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
                    actions()
                }
            }
        }
        HorizontalDivider(
            thickness = if (style == ManagerStyle.PIXEL || style == ManagerStyle.CYBERPUNK) 1.2.dp else 0.75.dp,
            color = when (style) {
                ManagerStyle.PIXEL, ManagerStyle.CYBERPUNK, ManagerStyle.NEON -> accent.copy(alpha = 0.42f)
                ManagerStyle.IOS_GLASS -> glass.borderHighlight.copy(alpha = if (glass.isDark) 0.22f else 0.65f)
            },
        )
    }
}

/** Group structure changes with the selected design, not just its colors. */
@Composable
fun IosGroup(
    title: String? = null,
    footer: String? = null,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val style = LocalManagerStyle.current
    val phase by rememberStylePhase()
    val accent = MaterialTheme.colorScheme.primary
    Column(modifier = modifier.fillMaxWidth()) {
        if (!title.isNullOrBlank() && (style == ManagerStyle.IOS_GLASS || style == ManagerStyle.NEON)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 7.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (style == ManagerStyle.NEON) {
                    Box(
                        modifier = Modifier
                            .width(18.dp)
                            .height(2.5.dp)
                            .background(Brush.horizontalGradient(listOf(accent, Color(0xFFFF4FD8)))),
                    )
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    text = if (style == ManagerStyle.IOS_GLASS) title else title.uppercase(),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = if (style == ManagerStyle.IOS_GLASS) MaterialTheme.colorScheme.onSurfaceVariant else accent,
                    letterSpacing = if (style == ManagerStyle.IOS_GLASS) .3.sp else 1.1.sp,
                )
            }
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .iosGlass(shape = if (style == ManagerStyle.PIXEL) RectangleShape else MaterialTheme.shapes.large),
        ) {
            if (!title.isNullOrBlank() && (style == ManagerStyle.PIXEL || style == ManagerStyle.CYBERPUNK)) {
                val litDot = (phase * 3f).roundToInt().coerceIn(0, 3)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(accent.copy(alpha = if (style == ManagerStyle.PIXEL) .12f else .16f))
                        .padding(horizontal = 14.dp, vertical = if (style == ManagerStyle.PIXEL) 8.dp else 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (style == ManagerStyle.CYBERPUNK) {
                        Box(Modifier.width(4.dp).height(14.dp).background(accent))
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(
                        text = title.uppercase(),
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = accent,
                        letterSpacing = 1.1.sp,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.width(8.dp))
                    if (style == ManagerStyle.PIXEL) {
                        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                            for (i in 0..3) {
                                Box(Modifier.size(4.dp).background(accent.copy(alpha = if (i == litDot) 0.9f else 0.25f)))
                            }
                        }
                    } else {
                        Text(
                            text = "/// SEC",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Black,
                            color = accent,
                        )
                    }
                }
                HorizontalDivider(thickness = 1.dp, color = LocalGlassStyle.current.divider)
            }
            content()
        }
        if (!footer.isNullOrBlank()) {
            Text(
                text = footer,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = .85f),
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp),
            )
        }
    }
}

@Composable
fun IosGroupDivider() {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val start = when (style) {
        ManagerStyle.PIXEL -> 0.dp
        ManagerStyle.CYBERPUNK -> 14.dp
        ManagerStyle.IOS_GLASS -> 58.dp
        ManagerStyle.NEON -> 18.dp
    }
    HorizontalDivider(
        modifier = Modifier.padding(start = start, end = if (style == ManagerStyle.PIXEL) 0.dp else 16.dp),
        thickness = if (style == ManagerStyle.PIXEL) 1.dp else .65.dp,
        color = glass.divider,
    )
}

/** The iOS design restores colorful rounded badges; other styles stay technical. */
@Composable
fun IosBadgeIcon(
    icon: ImageVector,
    color: Color,
    size: Dp = 32.dp,
    iconSize: Dp = 18.dp,
) {
    val style = LocalManagerStyle.current
    val shape = when (style) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> MaterialTheme.shapes.small
        ManagerStyle.IOS_GLASS -> RoundedCornerShape(10.dp)
        ManagerStyle.NEON -> RoundedCornerShape(8.dp)
    }
    val semanticColor = if (style == ManagerStyle.IOS_GLASS) when (color) {
        IosBlueDark -> Color(0xFF007AFF)
        IosCyanDark -> Color(0xFF00A8D6)
        IosIndigoDark -> Color(0xFF5856D6)
        IosPurpleDark -> Color(0xFFAF52DE)
        IosTeal -> Color(0xFF00B5AC)
        IosGreenDark -> Color(0xFF30C95D)
        IosOrangeDark -> Color(0xFFFFA000)
        IosRedDark -> Color(0xFFFF453A)
        else -> color
    } else color
    val brightness = semanticColor.red * .2126f + semanticColor.green * .7152f + semanticColor.blue * .0722f
    val iconTint = if (style == ManagerStyle.IOS_GLASS) {
        if (brightness > .58f) Color(0xFF101824) else Color.White
    } else if (brightness < .6f) semanticColor.blend(Color.White, .55f) else semanticColor
    val background = when (style) {
        ManagerStyle.IOS_GLASS -> semanticColor
        ManagerStyle.CYBERPUNK -> Color(0xFF141923)
        ManagerStyle.NEON -> Color(0xFF101A32)
        ManagerStyle.PIXEL -> Color(0xFF252523)
    }
    Box(
        modifier = Modifier
            .size(size)
            .clip(shape)
            .background(background)
            .border(
                width = if (style == ManagerStyle.NEON || style == ManagerStyle.CYBERPUNK) 1.4.dp else 1.dp,
                color = if (style == ManagerStyle.IOS_GLASS) Color.White.copy(alpha = .28f) else iconTint.copy(alpha = .65f),
                shape = shape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(imageVector = icon, contentDescription = null, tint = iconTint, modifier = Modifier.size(iconSize))
    }
}

/**
 * Theme-adaptive status pill: rectangular bracket box in PIXEL, chamfered tag in CYBERPUNK,
 * frosted capsule in IOS_GLASS, and glowing badge in NEON.
 */
@Composable
fun IosPill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val bgAlpha = if (glass.isDark) 0.22f else 0.16f
    val borderAlpha = if (glass.isDark) 0.50f else 0.36f
    val textColor = if (glass.isDark) color.blend(Color.White, 0.28f) else color.blend(Color(0xFF101B2D), 0.76f)
    val shape = when (style) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> CutCornerShape(topStart = 0.dp, topEnd = 7.dp, bottomEnd = 0.dp, bottomStart = 7.dp)
        ManagerStyle.IOS_GLASS -> CircleShape
        ManagerStyle.NEON -> RoundedCornerShape(8.dp)
    }
    Box(
        modifier = modifier
            .clip(shape)
            .background(color.copy(alpha = bgAlpha))
            .border(if (style == ManagerStyle.PIXEL || style == ManagerStyle.CYBERPUNK) 1.dp else 0.85.dp, color.copy(alpha = borderAlpha), shape)
            .padding(horizontal = 9.dp, vertical = 3.5.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            color = textColor,
        )
    }
}

/**
 * Theme-adaptive toggle switch: square hardware slider in PIXEL, chamfered mechanical toggle in CYBERPUNK,
 * spring capsule in IOS_GLASS, and neon-bordered switch in NEON.
 */
@Composable
fun IosSwitch(
    checked: Boolean,
    onCheckedChange: ((Boolean) -> Unit)?,
    enabled: Boolean = true,
) {
    val glass = LocalGlassStyle.current
    val design = LocalManagerStyle.current
    val trackShape = when (design) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> CutCornerShape(7.dp)
        ManagerStyle.IOS_GLASS, ManagerStyle.NEON -> CircleShape
    }
    val thumbShape = when (design) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> CutCornerShape(5.dp)
        ManagerStyle.IOS_GLASS, ManagerStyle.NEON -> CircleShape
    }
    val activeColor = MaterialTheme.colorScheme.primary
    val inactiveColor = if (glass.isDark) Color.White.copy(alpha = 0.18f) else Color(0xFF0E2240).copy(alpha = 0.14f)
    val trackColor by animateColorAsState(
        targetValue = if (checked) activeColor else inactiveColor,
        animationSpec = if (LocalPixelMotionEnabled.current) tween(durationMillis = 200) else snap(),
        label = "pixel-switch-track",
    )
    val thumbOffset by animateDpAsState(
        targetValue = if (checked) 20.dp else 2.dp,
        animationSpec = if (LocalPixelMotionEnabled.current) spring(stiffness = Spring.StiffnessMediumLow, dampingRatio = 0.78f) else snap(),
        label = "pixel-switch-thumb",
    )

    Box(
        modifier = Modifier
            .width(48.dp)
            .height(28.dp)
            .alpha(if (enabled) 1f else 0.42f)
            .clip(trackShape)
            .background(trackColor)
            .border(
                width = if (design == ManagerStyle.PIXEL || design == ManagerStyle.CYBERPUNK) 1.dp else 0.75.dp,
                color = if (checked) activeColor.blend(Color.White, 0.35f) else Color.White.copy(alpha = 0.22f),
                shape = trackShape,
            )
            .let { mod ->
                if (onCheckedChange != null && enabled) {
                    mod.clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                    ) { onCheckedChange(!checked) }
                } else mod
            },
        contentAlignment = Alignment.CenterStart,
    ) {
        Box(
            modifier = Modifier
                .offset(x = thumbOffset)
                .size(24.dp)
                .shadow(3.dp, thumbShape, clip = false)
                .clip(thumbShape)
                .background(if (checked) MaterialTheme.colorScheme.onPrimary else Color.White),
            contentAlignment = Alignment.Center,
        ) {
            if (design == ManagerStyle.PIXEL || design == ManagerStyle.CYBERPUNK) {
                Box(
                    modifier = Modifier
                        .width(3.dp)
                        .height(10.dp)
                        .background(if (checked) activeColor else Color(0xFF565650)),
                )
            }
        }
    }
}

/**
 * Theme-adaptive row inside an [IosGroup].
 */
@Composable
fun IosRow(
    icon: ImageVector,
    badgeColor: Color,
    title: String,
    subtitle: String? = null,
    value: String? = null,
    pill: String? = null,
    pillText: String? = pill,
    pillColor: Color = IosGreenDark,
    showChevron: Boolean = false,
    enabled: Boolean = true,
    onClick: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    val style = LocalManagerStyle.current
    val accent = MaterialTheme.colorScheme.primary
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(if (enabled) 1f else 0.48f)
            .defaultMinSize(minHeight = 56.dp)
            .let { mod ->
                if (onClick != null && enabled) mod.clickable(onClick = onClick) else mod
            }
            .padding(horizontal = 15.dp, vertical = 12.5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (style == ManagerStyle.CYBERPUNK) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height(28.dp)
                    .background(badgeColor.copy(alpha = 0.85f)),
            )
            Spacer(Modifier.width(8.dp))
        }
        IosBadgeIcon(icon = icon, color = badgeColor)
        Spacer(Modifier.width(13.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (!subtitle.isNullOrBlank()) {
                Spacer(Modifier.height(1.5.dp))
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.width(8.dp))
        if (pillText != null) {
            IosPill(text = pillText, color = pillColor)
            if (value != null || showChevron) Spacer(Modifier.width(6.dp))
        }
        if (value != null) {
            Text(
                text = if (style == ManagerStyle.PIXEL) "[$value]" else value,
                style = MaterialTheme.typography.bodyMedium,
                color = if (style == ManagerStyle.CYBERPUNK || style == ManagerStyle.NEON) accent else MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (showChevron) Spacer(Modifier.width(4.dp))
        }
        if (trailing != null) {
            trailing()
        } else if (showChevron) {
            Icon(
                imageVector = Icons.AutoMirrored.Rounded.KeyboardArrowRight,
                contentDescription = null,
                tint = if (style == ManagerStyle.CYBERPUNK || style == ManagerStyle.NEON) accent.copy(alpha = 0.80f)
                else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

/**
 * Standard switch row inside an [IosGroup].
 */
@Composable
fun IosSwitchRow(
    icon: ImageVector,
    badgeColor: Color,
    title: String,
    subtitle: String? = null,
    checked: Boolean,
    enabled: Boolean = true,
    onCheckedChange: (Boolean) -> Unit,
) {
    val style = LocalManagerStyle.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(if (enabled) 1f else 0.48f)
            .defaultMinSize(minHeight = 56.dp)
            .let { mod ->
                if (enabled) {
                    mod.toggleable(
                        value = checked,
                        role = Role.Switch,
                        onValueChange = onCheckedChange,
                    )
                } else mod
            }
            .padding(horizontal = 15.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (style == ManagerStyle.CYBERPUNK) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height(28.dp)
                    .background(if (checked) MaterialTheme.colorScheme.primary else badgeColor.copy(alpha = 0.5f)),
            )
            Spacer(Modifier.width(8.dp))
        }
        IosBadgeIcon(icon = icon, color = badgeColor)
        Spacer(Modifier.width(13.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            if (!subtitle.isNullOrBlank()) {
                Spacer(Modifier.height(1.5.dp))
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.width(10.dp))
        IosSwitch(checked = checked, onCheckedChange = null, enabled = enabled)
    }
}

/**
 * 2x2 Quick-Action Menu Tile on HomeScreen: changes card structure & layout for each of the 4 themes.
 */
@Composable
fun IosTile(
    icon: ImageVector,
    badgeColor: Color,
    title: String,
    subtitle: String,
    pill: String? = null,
    badgeText: String? = pill,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val style = LocalManagerStyle.current
    val accent = MaterialTheme.colorScheme.primary
    when (style) {
        ManagerStyle.PIXEL -> {
            // Hardware Dot-Matrix Module Card: top LED header strip + right-mounted square icon
            Column(
                modifier = modifier
                    .iosGlass(shape = RectangleShape)
                    .clickable(onClick = onClick),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(accent.copy(alpha = 0.12f))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "■ SYS.MOD",
                        style = MaterialTheme.typography.labelSmall,
                        color = accent,
                    )
                    if (!badgeText.isNullOrBlank()) {
                        Text(
                            text = "[$badgeText]",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = accent,
                        )
                    }
                }
                Column(modifier = Modifier.padding(horizontal = 13.dp, vertical = 12.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = title,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Spacer(Modifier.height(2.dp))
                            Text(
                                text = subtitle,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        Spacer(Modifier.width(8.dp))
                        IosBadgeIcon(icon = icon, color = badgeColor, size = 34.dp, iconSize = 19.dp)
                    }
                }
            }
        }
        ManagerStyle.CYBERPUNK -> {
            // Chamfered Cyberbrutal Plate: left volt bar + top telemetry tag + bottom title
            val cutShape = CutCornerShape(topStart = 2.dp, topEnd = 16.dp, bottomEnd = 2.dp, bottomStart = 12.dp)
            Column(
                modifier = modifier
                    .iosGlass(shape = cutShape)
                    .clickable(onClick = onClick)
                    .padding(horizontal = 14.dp, vertical = 13.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (!badgeText.isNullOrBlank()) {
                        IosPill(text = badgeText, color = accent)
                    } else {
                        Text(
                            text = "/// ACT",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Black,
                            color = accent,
                        )
                    }
                    IosBadgeIcon(icon = icon, color = badgeColor, size = 34.dp, iconSize = 19.dp)
                }
                Spacer(Modifier.height(12.dp))
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        ManagerStyle.IOS_GLASS -> {
            // Classic iOS 18 Control-Center Frosted Bento Tile
            Column(
                modifier = modifier
                    .iosGlass(shape = RoundedCornerShape(24.dp))
                    .clickable(onClick = onClick)
                    .padding(horizontal = 15.dp, vertical = 15.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IosBadgeIcon(icon = icon, color = badgeColor, size = 36.dp, iconSize = 20.dp)
                    if (!badgeText.isNullOrBlank()) {
                        IosPill(text = badgeText, color = badgeColor)
                    } else {
                        Icon(
                            imageVector = Icons.AutoMirrored.Rounded.KeyboardArrowRight,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.50f),
                            modifier = Modifier.size(19.dp),
                        )
                    }
                }
                Spacer(Modifier.height(14.dp))
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        ManagerStyle.NEON -> {
            // Cyberpunk Neon Deck Card with glowing bottom laser bar
            val magenta = Color(0xFFFF4FD8)
            Column(
                modifier = modifier
                    .iosGlass(shape = RoundedCornerShape(16.dp))
                    .clickable(onClick = onClick)
                    .padding(horizontal = 14.dp, vertical = 13.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IosBadgeIcon(icon = icon, color = badgeColor, size = 35.dp, iconSize = 19.dp)
                    if (!badgeText.isNullOrBlank()) {
                        IosPill(text = badgeText, color = accent)
                    } else {
                        Icon(
                            imageVector = Icons.AutoMirrored.Rounded.KeyboardArrowRight,
                            contentDescription = null,
                            tint = accent,
                            modifier = Modifier.size(19.dp),
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(8.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(2.dp)
                            .background(Brush.horizontalGradient(listOf(accent, magenta, Color.Transparent))),
                    )
                }
            }
        }
    }
}

/** Shared entry point keeps the real Manager data and click behavior unchanged. */
@Composable
fun IosHeroCard(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    onClick: (() -> Unit)? = null,
) {
    DistinctManagerHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, onClick)
}

/**
 * Multi-theme boot & live theme-switch splash screen:
 * Renders 4 completely distinct splash screens with each theme's authentic PNG emblem,
 * animations, and layout on cold start AND when switching themes / previewing in Customization.
 */
@Composable
fun GlassSplash(visible: Boolean, modifier: Modifier = Modifier) {
    val phase by rememberStylePhase()
    val style = LocalManagerStyle.current
    val motionEnabled = LocalPixelMotionEnabled.current

    var previewVisible by remember { mutableStateOf(false) }
    val previewTick = SplashPreviewTickState.intValue
    LaunchedEffect(previewTick) {
        if (previewTick > 0) {
            previewVisible = true
            delay(680L)
            previewVisible = false
        }
    }

    val effectiveVisible = visible || previewVisible
    AnimatedVisibility(
        visible = effectiveVisible,
        enter = if (motionEnabled) fadeIn(tween(150)) else EnterTransition.None,
        exit = if (motionEnabled) fadeOut(tween(180)) else ExitTransition.None,
        modifier = modifier,
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background),
            contentAlignment = Alignment.Center,
        ) {
            GlassBackground(wallpaperLayer = null)
            when (style) {
                ManagerStyle.PIXEL -> PixelMatrixSplash(phase = phase)
                ManagerStyle.CYBERPUNK -> CyberBrutalSplash(phase = phase)
                ManagerStyle.IOS_GLASS -> IosLiquidGlassSplash(phase = phase)
                ManagerStyle.NEON -> NeonCyberSplash(phase = phase)
            }
        }
    }
}

@Composable
private fun PixelMatrixSplash(phase: Float) {
    val accent = MaterialTheme.colorScheme.primary
    val onBg = MaterialTheme.colorScheme.onBackground
    val step = (phase * 12f).roundToInt()

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 32.dp),
    ) {
        // Animated 14x4 Nothing OS / Pixel LED Dot-Matrix Equalizer Array
        Canvas(modifier = Modifier.width(164.dp).height(28.dp)) {
            val cols = 14
            val rows = 4
            val dot = 4.dp.toPx()
            val gapX = (size.width - cols * dot) / (cols - 1).coerceAtLeast(1)
            val gapY = (size.height - rows * dot) / (rows - 1).coerceAtLeast(1)
            for (c in 0 until cols) {
                val activeRows = ((c + step) % rows) + 1
                for (r in 0 until rows) {
                    val lit = (rows - 1 - r) < activeRows
                    drawRect(
                        color = accent.copy(alpha = if (lit) 0.90f else 0.16f),
                        topLeft = Offset(c * (dot + gapX), r * (dot + gapY)),
                        size = Size(dot, dot),
                    )
                }
            }
        }

        Spacer(Modifier.height(20.dp))

        // Square Double-Walled Hardware Frame with Pixel S PNG Emblem
        Box(
            modifier = Modifier
                .size(136.dp)
                .background(Color(0xFF0E0E0E))
                .border(2.dp, accent, RectangleShape)
                .padding(8.dp),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.ic_emblem_pixel),
                contentDescription = "Synthetica",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxSize()
                    .border(1.dp, onBg.copy(alpha = 0.25f), RectangleShape),
            )
            Canvas(modifier = Modifier.fillMaxSize()) {
                val corner = 5.dp.toPx()
                drawRect(accent, Offset.Zero, Size(corner, corner))
                drawRect(accent, Offset(size.width - corner, 0f), Size(corner, corner))
                drawRect(accent, Offset(0f, size.height - corner), Size(corner, corner))
                drawRect(accent, Offset(size.width - corner, size.height - corner), Size(corner, corner))
            }
        }

        Spacer(Modifier.height(22.dp))

        Text(
            text = "SYNTHETICA",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Black,
            color = onBg,
            letterSpacing = 2.4.sp,
        )

        Spacer(Modifier.height(8.dp))

        Box(
            modifier = Modifier
                .border(1.dp, accent, RectangleShape)
                .background(accent.copy(alpha = 0.14f))
                .padding(horizontal = 12.dp, vertical = 4.dp),
        ) {
            Text(
                text = splashTagForStyle(ManagerStyle.PIXEL),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = accent,
                letterSpacing = 1.6.sp,
            )
        }

        Spacer(Modifier.height(24.dp))

        // 12-Segment Stepped Square LED Progress Array
        val litBlocks = ((0.25f + 0.75f * phase) * 12f).roundToInt().coerceIn(2, 12)
        Row(
            modifier = Modifier
                .border(1.dp, onBg.copy(alpha = 0.30f), RectangleShape)
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            for (b in 0 until 12) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .background(if (b < litBlocks) accent else onBg.copy(alpha = 0.14f)),
                )
            }
        }

        Spacer(Modifier.height(10.dp))
        Text(
            text = "DOT_MATRIX_OS // UAPI_V4 :: READY",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            letterSpacing = 1.2.sp,
        )
    }
}

@Composable
private fun CyberBrutalSplash(phase: Float) {
    val volt = MaterialTheme.colorScheme.primary
    val cyan = Color(0xFF00F0FF)
    val onBg = MaterialTheme.colorScheme.onBackground
    val dim = MaterialTheme.colorScheme.onSurfaceVariant
    val cutShape = CutCornerShape(topStart = 4.dp, topEnd = 24.dp, bottomEnd = 4.dp, bottomStart = 24.dp)

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 32.dp),
    ) {
        // Chamfered Industrial Reticle Frame + Cyberbrutal S PNG Emblem
        Box(
            modifier = Modifier.size(144.dp),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.ic_emblem_cyberpunk),
                contentDescription = "Synthetica",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(128.dp)
                    .clip(cutShape)
                    .border(2.dp, volt, cutShape),
            )
            Canvas(modifier = Modifier.fillMaxSize()) {
                val w = size.width
                val h = size.height
                val cut = 22.dp.toPx()
                val frame = Path().apply {
                    moveTo(0f, 0f)
                    lineTo(w - cut, 0f)
                    lineTo(w, cut)
                    lineTo(w, h)
                    lineTo(cut, h)
                    lineTo(0f, h - cut)
                    close()
                }
                drawPath(frame, color = volt.copy(alpha = 0.65f), style = Stroke(width = 1.5.dp.toPx()))
                val sweep = (0.25f + 0.75f * phase) * w
                drawLine(
                    color = cyan,
                    start = Offset(0f, h + 6.dp.toPx()),
                    end = Offset(sweep, h + 6.dp.toPx()),
                    strokeWidth = 3.dp.toPx(),
                )
            }
        }

        Spacer(Modifier.height(24.dp))

        // Authentic 2.1 Solari Split-Flap DepartureBoardText
        DepartureBoardText(
            text = "SYNTHETICA",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Black,
            color = onBg,
        )

        Spacer(Modifier.height(8.dp))

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Box(
                modifier = Modifier
                    .background(volt)
                    .padding(horizontal = 8.dp, vertical = 2.dp),
            ) {
                Text(
                    text = "v5.0.1",
                    style = MaterialTheme.typography.labelMedium,
                    color = Color(0xFF090B0E),
                    fontWeight = FontWeight.Black,
                )
            }
            Spacer(Modifier.width(8.dp))
            DepartureBoardText(
                text = splashTagForStyle(ManagerStyle.CYBERPUNK),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = cyan,
                delayMillis = 60,
            )
        }

        Spacer(Modifier.height(22.dp))

        // 16-Block Segmented Industrial Progress Bar [##########..]
        val totalBlocks = 16
        val litBlocks = ((0.30f + 0.70f * phase) * totalBlocks).roundToInt().coerceIn(3, totalBlocks)
        Row(
            modifier = Modifier
                .border(1.dp, volt.copy(alpha = 0.65f))
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            for (b in 0 until totalBlocks) {
                Box(
                    modifier = Modifier
                        .width(9.dp)
                        .height(6.dp)
                        .background(if (b < litBlocks) volt else dim.copy(alpha = 0.20f)),
                )
            }
        }

        Spacer(Modifier.height(12.dp))
        Text(
            text = "SYS.NODE // KERNELSU-NEXT :: UAPI_V4",
            style = MaterialTheme.typography.labelSmall,
            color = dim,
            letterSpacing = 1.1.sp,
        )
    }
}

@Composable
private fun IosLiquidGlassSplash(phase: Float) {
    val accent = MaterialTheme.colorScheme.primary
    val haloPulse = 0.90f + 0.14f * sin(phase * 2f * Math.PI.toFloat())

    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        // Ambient sapphire & cyan aurora blooms behind pedestal (from Synthetica 2.0)
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width * 0.5f
            val cy = size.height * 0.44f
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF0A84FF).copy(alpha = 0.38f), Color.Transparent),
                    center = Offset(cx, cy),
                    radius = size.minDimension * 0.52f * haloPulse,
                ),
                radius = size.minDimension * 0.52f * haloPulse,
                center = Offset(cx, cy),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF00E5FF).copy(alpha = 0.22f), Color.Transparent),
                    center = Offset(cx * 1.14f, cy * 0.84f),
                    radius = size.minDimension * 0.36f,
                ),
                radius = size.minDimension * 0.36f,
                center = Offset(cx * 1.14f, cy * 0.84f),
            )
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(horizontal = 32.dp),
        ) {
            val pedestalShape = RoundedCornerShape(34.dp)
            Box(
                modifier = Modifier
                    .size(134.dp)
                    .shadow(
                        elevation = 24.dp,
                        shape = pedestalShape,
                        ambientColor = Color(0xFF0099FF).copy(alpha = 0.50f),
                        spotColor = Color(0xFF0099FF).copy(alpha = 0.60f),
                    )
                    .clip(pedestalShape)
                    .background(
                        Brush.linearGradient(
                            colors = listOf(
                                Color.White.copy(alpha = 0.24f),
                                Color(0xFF5AC8FA).copy(alpha = 0.12f),
                                Color(0xFF081834).copy(alpha = 0.48f),
                            )
                        )
                    )
                    .border(
                        width = 1.4.dp,
                        brush = Brush.linearGradient(
                            colors = listOf(
                                Color.White.copy(alpha = 0.80f),
                                Color(0xFF64D2FF).copy(alpha = 0.40f),
                                Color.White.copy(alpha = 0.16f),
                            )
                        ),
                        shape = pedestalShape,
                    )
                    .padding(8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(R.drawable.ic_emblem_ios_glass),
                    contentDescription = "Synthetica",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(RoundedCornerShape(27.dp))
                        .drawWithContent {
                            drawContent()
                            val sx = size.width * phase
                            drawRect(
                                brush = Brush.linearGradient(
                                    colors = listOf(
                                        Color.Transparent,
                                        Color.White.copy(alpha = 0.30f),
                                        Color.Transparent,
                                    ),
                                    start = Offset(sx - size.width * 0.35f, 0f),
                                    end = Offset(sx + size.width * 0.18f, size.height),
                                )
                            )
                        },
                )
            }

            Spacer(Modifier.height(24.dp))

            Text(
                text = "SYNTHETICA",
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground,
                letterSpacing = (-0.3).sp,
            )

            Spacer(Modifier.height(8.dp))

            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(accent.copy(alpha = 0.14f))
                    .border(0.9.dp, accent.copy(alpha = 0.42f), CircleShape)
                    .padding(horizontal = 14.dp, vertical = 5.dp),
            ) {
                Text(
                    text = splashTagForStyle(ManagerStyle.IOS_GLASS),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = accent,
                    letterSpacing = 1.2.sp,
                )
            }

            Spacer(Modifier.height(30.dp))

            // Shimmering Liquid-Glass Capsule Progress Bar
            Box(
                modifier = Modifier
                    .width(124.dp)
                    .height(4.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.onBackground.copy(alpha = 0.14f))
                    .drawWithContent {
                        drawContent()
                        val px = size.width * phase
                        drawRect(
                            brush = Brush.horizontalGradient(
                                colors = listOf(
                                    Color.Transparent,
                                    Color(0xFF5AC8FA),
                                    Color.White,
                                    Color(0xFF2997FF),
                                    Color.Transparent,
                                ),
                                startX = px - size.width * 0.45f,
                                endX = px + size.width * 0.45f,
                            )
                        )
                    }
            )
        }
    }
}

@Composable
private fun NeonCyberSplash(phase: Float) {
    val accent = MaterialTheme.colorScheme.primary
    val magenta = Color(0xFFFF4FD8)
    val onBg = MaterialTheme.colorScheme.onBackground
    val shape = RoundedCornerShape(26.dp)
    val pulse = 0.72f + 0.28f * abs(sin(phase * Math.PI.toFloat()))

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 32.dp),
    ) {
        // Dual-Ring Neon Halo + 3D Neon S PNG Emblem
        Box(
            modifier = Modifier
                .size(148.dp)
                .drawBehind {
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(accent.copy(alpha = 0.36f * pulse), magenta.copy(alpha = 0.22f * pulse), Color.Transparent),
                        ),
                        radius = size.minDimension * 0.56f,
                    )
                    drawCircle(
                        brush = Brush.sweepGradient(listOf(accent, magenta, accent)),
                        radius = size.minDimension * 0.48f,
                        style = Stroke(width = 2.dp.toPx()),
                    )
                },
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.ic_emblem_neon),
                contentDescription = "Synthetica",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(124.dp)
                    .shadow(20.dp, shape, ambientColor = accent.copy(alpha = 0.65f), spotColor = magenta.copy(alpha = 0.65f))
                    .clip(shape)
                    .border(2.dp, Brush.linearGradient(listOf(accent, magenta)), shape),
            )
        }

        Spacer(Modifier.height(22.dp))

        Text(
            text = "SYNTHETICA",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Black,
            color = onBg,
            letterSpacing = 2.6.sp,
        )

        Spacer(Modifier.height(8.dp))

        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(10.dp))
                .background(Brush.horizontalGradient(listOf(accent.copy(alpha = 0.18f), magenta.copy(alpha = 0.16f))))
                .border(1.dp, Brush.horizontalGradient(listOf(accent, magenta)), RoundedCornerShape(10.dp))
                .padding(horizontal = 14.dp, vertical = 4.dp),
        ) {
            Text(
                text = splashTagForStyle(ManagerStyle.NEON),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = accent,
                letterSpacing = 1.6.sp,
            )
        }

        Spacer(Modifier.height(26.dp))

        // Dual-Laser Cyan-to-Magenta Progress Bar
        Box(
            modifier = Modifier
                .width(136.dp)
                .height(4.dp)
                .clip(CircleShape)
                .background(onBg.copy(alpha = 0.14f))
                .drawBehind {
                    val length = size.width * (0.35f + phase * 0.55f)
                    drawLine(
                        brush = Brush.horizontalGradient(listOf(accent, magenta, accent)),
                        start = Offset.Zero,
                        end = Offset(length, 0f),
                        strokeWidth = size.height,
                    )
                }
        )

        Spacer(Modifier.height(10.dp))
        Text(
            text = "NEON OVERDRIVE // UAPI_V4 :: ONLINE",
            style = MaterialTheme.typography.labelSmall,
            color = magenta.copy(alpha = 0.85f),
            letterSpacing = 1.2.sp,
        )
    }
}
