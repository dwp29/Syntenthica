package com.rifsxd.ksunext.ui.theme

import android.os.Build
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.snap
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
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlurEffect
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.TileMode
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
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * Live GPU RenderNode layers for real-time iOS backdrop blur:
 * - [LocalGlassWallpaperLayer]: captures the animated aurora [GlassBackground] for cards & headers.
 * - [LocalGlassContentLayer]: captures [GlassBackground] + screen body for floating overlays (dock).
 */
val LocalGlassWallpaperLayer = compositionLocalOf<GraphicsLayer?> { null }
val LocalGlassContentLayer = compositionLocalOf<GraphicsLayer?> { null }

/** Distinct wallpapers, with a truly black canvas in AMOLED mode. */
@Composable
fun GlassBackground(
    modifier: Modifier = Modifier,
    wallpaperLayer: GraphicsLayer? = LocalGlassWallpaperLayer.current,
) {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val phase = LocalNeonPhase.current
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
                val pitch = 8.dp.toPx()
                val dot = 2.dp.toPx()
                val startX = size.width - pitch * 13f
                val startY = 18.dp.toPx()
                val active = (phase.value * 10f).roundToInt().coerceIn(0, 10)
                for (row in 0 until 7) for (col in 0 until 12) {
                    val selected = (col + row * 2) % 11 == active
                    val ink = if (selected) accent.copy(alpha = if (glass.isDark) .45f else .35f)
                        else if (glass.isDark) Color.White.copy(alpha = .07f) else Color.Black.copy(alpha = .07f)
                    drawRect(ink, topLeft = Offset(startX + col * pitch, startY + row * pitch),
                        size = androidx.compose.ui.geometry.Size(dot, dot))
                }
            }
            ManagerStyle.CYBERPUNK -> {
                // Architectural grid and industrial corner marks, static except for one indicator.
                val pitch = 32.dp.toPx()
                var x = 0f
                while (x < size.width) {
                    drawLine(accent.copy(alpha = .045f), Offset(x, 0f), Offset(x, size.height), 1.dp.toPx())
                    x += pitch
                }
                var y = 0f
                while (y < size.height) {
                    drawLine(accent.copy(alpha = .045f), Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
                    y += pitch
                }
                val gap = 11.dp.toPx()
                for (i in 0..7) {
                    val px = size.width - (20 + i * 11).dp.toPx()
                    drawLine(accent.copy(alpha = if (i == (phase.value * 7f).roundToInt()) .4f else .16f),
                        Offset(px, 18.dp.toPx()), Offset(px - gap * 1.5f, 18.dp.toPx() + gap * 1.5f), 2.dp.toPx())
                }
            }
            ManagerStyle.IOS_GLASS -> {
                val radius = size.width * .9f
                val first = Offset(size.width * .83f, size.height * .14f)
                val second = Offset(size.width * .12f, size.height * .70f)
                drawCircle(Brush.radialGradient(listOf(accent.copy(alpha = if (glass.isDark) .28f else .20f), Color.Transparent), first, radius),
                    radius = radius, center = first)
                drawCircle(Brush.radialGradient(listOf(Color(0xFFAF83FF).copy(alpha = if (glass.isDark) .16f else .13f), Color.Transparent), second, radius),
                    radius = radius, center = second)
            }
            ManagerStyle.NEON -> {
                val radius = size.width * .8f
                val first = Offset(size.width * .90f, size.height * .15f)
                val second = Offset(size.width * .08f, size.height * .78f)
                drawCircle(Brush.radialGradient(listOf(accent.copy(alpha = .24f), Color.Transparent), first, radius), radius = radius, center = first)
                drawCircle(Brush.radialGradient(listOf(Color(0xFFFF4DCD).copy(alpha = .13f), Color.Transparent), second, radius), radius = radius, center = second)
                drawLine(accent.copy(alpha = .24f), Offset(size.width - 4.dp.toPx(), 24.dp.toPx()),
                    Offset(size.width - 4.dp.toPx(), 130.dp.toPx()), 3.dp.toPx())
            }
        }
    }
}

/** Theme geometry, including genuine backdrop blur for iOS on Android 12+. */
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
    val phase = LocalNeonPhase.current
    val accent = MaterialTheme.colorScheme.primary
    val intensity = LocalNeonGlow.current
    val top = if (tintTop != Color.Unspecified) tintTop else glass.cardTintTop
    val bottom = if (tintBottom != Color.Unspecified) tintBottom else glass.cardTintBottom
    val panelShape = if (shape == RectangleShape) RectangleShape else when (style) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> if (shape is androidx.compose.foundation.shape.CutCornerShape) shape
            else androidx.compose.foundation.shape.CutCornerShape(topStart = 0.dp, topEnd = 18.dp, bottomEnd = 0.dp, bottomStart = 18.dp)
        ManagerStyle.IOS_GLASS, ManagerStyle.NEON -> shape
    }
    if (style == ManagerStyle.IOS_GLASS) {
        val wallpaper = LocalGlassWallpaperLayer.current
        val content = LocalGlassContentLayer.current
        val sampleLayer = rememberGraphicsLayer()
        var posInRoot by remember { mutableStateOf(Offset.Zero) }
        val resolvedBlur = if (blurRadius != Dp.Unspecified) blurRadius else glass.blurRadius
        this.onGloballyPositioned { posInRoot = it.positionInRoot() }
            .let { if (elevation > 0.dp && shape != RectangleShape) it.shadow(elevation.coerceAtMost(6.dp), panelShape,
                ambientColor = glass.shadowColor, spotColor = glass.shadowColor) else it }
            .clip(panelShape)
            .drawWithCache {
                val blurPx = resolvedBlur.toPx()
                val pad = blurPx.roundToInt().coerceIn(0, 64)
                val src = if (blurContent) (content ?: wallpaper) else wallpaper
                val canBlur = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && src != null && !glass.isAmoled && blurPx > .5f
                val alpha = if (canBlur) if (glass.isDark) .87f else .83f else 1f
                // Warning/status tints may themselves be translucent; preserve their semantic color.
                val iosTop = if (top.alpha < 1f) top.compositeOver(glass.cardTintTop) else top
                val iosBottom = if (bottom.alpha < 1f) bottom.compositeOver(glass.cardTintBottom) else bottom
                val tint = Brush.verticalGradient(listOf(iosTop.copy(alpha = alpha), iosBottom.copy(alpha = alpha)))
                val sheen = Brush.verticalGradient(0f to Color.White.copy(alpha = if (glass.isDark) .10f else .48f),
                    .32f to Color.Transparent)
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
            .let { if (borderWidth > 0.dp) it.border(borderWidth,
                Brush.linearGradient(listOf(glass.borderHighlight, glass.borderMid, glass.borderShadow)), panelShape) else it }
    } else {
        val border = when (style) {
            ManagerStyle.NEON -> Brush.linearGradient(listOf(accent.copy(alpha = .78f), glass.borderMid,
                Color(0xFFE75DDE).copy(alpha = .55f)))
            else -> Brush.linearGradient(listOf(glass.borderHighlight, glass.borderHighlight))
        }
        this.clip(panelShape).background(Brush.verticalGradient(listOf(top, bottom)))
            .let { if (borderWidth > 0.dp) it.border(borderWidth, border, panelShape) else it }
            .drawBehind {
                if (shape != RectangleShape && size.width > 120.dp.toPx() && size.height > 40.dp.toPx()) {
                    when (style) {
                        ManagerStyle.PIXEL -> {
                            val unit = 3.dp.toPx(); val gap = 3.dp.toPx(); val start = size.width - 24.dp.toPx()
                            val lit = (phase.value * 3f).roundToInt().coerceIn(0, 3)
                            for (i in 0..3) {
                                val alpha = if (i == lit) .75f else (.16f * intensity).coerceAtMost(.35f)
                                drawRect(accent.copy(alpha = alpha), Offset(start + i * (unit + gap), 5.dp.toPx()),
                                    androidx.compose.ui.geometry.Size(unit, unit))
                            }
                        }
                        ManagerStyle.CYBERPUNK -> {
                            drawRect(accent.copy(alpha = .75f), Offset(0f, 12.dp.toPx()),
                                androidx.compose.ui.geometry.Size(4.dp.toPx(), 24.dp.toPx()))
                            drawLine(accent.copy(alpha = .4f), Offset(size.width - 50.dp.toPx(), 1.dp.toPx()),
                                Offset(size.width - 24.dp.toPx(), 1.dp.toPx()), 2.dp.toPx())
                        }
                        ManagerStyle.NEON -> {
                            drawLine(accent.copy(alpha = (.50f * intensity).coerceAtMost(.75f)),
                                Offset(18.dp.toPx(), 1.dp.toPx()), Offset(80.dp.toPx(), 1.dp.toPx()), 3.dp.toPx())
                        }
                        ManagerStyle.IOS_GLASS -> Unit
                    }
                }
            }
    }
}

/**
 * Edge-to-edge blurred iOS Top Navigation Bar with hairline specular bottom divider.
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
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 58.dp)
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                IconButton(
                    onClick = onBack,
                    modifier = Modifier.size(48.dp),
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Rounded.ArrowBackIos,
                        contentDescription = stringResource(R.string.neon_back),
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp),
                    )
                }
                Spacer(Modifier.width(4.dp))
            } else if (leading != null) {
                leading()
                Spacer(Modifier.width(10.dp))
            } else {
                Spacer(Modifier.width(4.dp))
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
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
            thickness = 0.75.dp,
            color = glass.borderHighlight.copy(alpha = if (glass.isDark) 0.22f else 0.65f),
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
    Column(modifier = modifier.fillMaxWidth()) {
        if (!title.isNullOrBlank() && (style == ManagerStyle.IOS_GLASS || style == ManagerStyle.NEON)) {
            Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 7.dp),
                verticalAlignment = Alignment.CenterVertically) {
                if (style == ManagerStyle.NEON) {
                    Box(Modifier.width(18.dp).height(2.dp).background(MaterialTheme.colorScheme.primary))
                    Spacer(Modifier.width(8.dp))
                }
                Text(text = if (style == ManagerStyle.IOS_GLASS) title else title.uppercase(),
                    style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold,
                    color = if (style == ManagerStyle.IOS_GLASS) MaterialTheme.colorScheme.onSurfaceVariant
                            else MaterialTheme.colorScheme.primary, letterSpacing = if (style == ManagerStyle.IOS_GLASS) .3.sp else 1.1.sp)
            }
        }
        Column(modifier = Modifier.fillMaxWidth().iosGlass(
            shape = if (style == ManagerStyle.PIXEL) RectangleShape else MaterialTheme.shapes.large)) {
            if (!title.isNullOrBlank() && (style == ManagerStyle.PIXEL || style == ManagerStyle.CYBERPUNK)) {
                Row(modifier = Modifier.fillMaxWidth()
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = if (style == ManagerStyle.PIXEL) .10f else .14f))
                    .padding(horizontal = 14.dp, vertical = if (style == ManagerStyle.PIXEL) 8.dp else 10.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text(text = title.uppercase(), modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary, letterSpacing = 1.1.sp,
                        maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.width(8.dp))
                    Text(text = if (style == ManagerStyle.PIXEL) "■ ■" else "///",
                        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                }
                HorizontalDivider(thickness = 1.dp, color = LocalGlassStyle.current.divider)
            }
            content()
        }
        if (!footer.isNullOrBlank()) {
            Text(text = footer, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = .85f),
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp))
        }
    }
}

@Composable
fun IosGroupDivider() {
    val glass = LocalGlassStyle.current
    val style = LocalManagerStyle.current
    val start = when (style) {
        ManagerStyle.PIXEL -> 0.dp; ManagerStyle.CYBERPUNK -> 14.dp
        ManagerStyle.IOS_GLASS -> 58.dp; ManagerStyle.NEON -> 18.dp
    }
    HorizontalDivider(modifier = Modifier.padding(start = start, end = if (style == ManagerStyle.PIXEL) 0.dp else 16.dp),
        thickness = if (style == ManagerStyle.PIXEL) 1.dp else .65.dp, color = glass.divider)
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
    val background = if (style == ManagerStyle.IOS_GLASS) semanticColor else Color(0xFF252523)
    Box(modifier = Modifier.size(size).clip(shape).background(background)
        .border(if (style == ManagerStyle.NEON) 1.5.dp else 1.dp,
            if (style == ManagerStyle.IOS_GLASS) Color.White.copy(alpha = .22f) else iconTint.copy(alpha = .55f), shape),
        contentAlignment = Alignment.Center) {
        Icon(imageVector = icon, contentDescription = null, tint = iconTint, modifier = Modifier.size(iconSize))
    }
}

/**
 * Translucent iOS status capsule pill.
 */
@Composable
fun IosPill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    val glass = LocalGlassStyle.current
    val bgAlpha = if (glass.isDark) 0.22f else 0.16f
    val borderAlpha = if (glass.isDark) 0.45f else 0.32f
    val textColor = if (glass.isDark) color.blend(Color.White, 0.28f) else color.blend(Color(0xFF101B2D), 0.76f)
    val shape = MaterialTheme.shapes.small
    Box(
        modifier = modifier
            .clip(shape)
            .background(color.copy(alpha = bgAlpha))
            .border(0.75.dp, color.copy(alpha = borderAlpha), shape)
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
 * Authentic spring-animated iOS capsule toggle switch.
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
        ManagerStyle.CYBERPUNK -> androidx.compose.foundation.shape.CutCornerShape(7.dp)
        ManagerStyle.IOS_GLASS, ManagerStyle.NEON -> CircleShape
    }
    val thumbShape = when (design) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> androidx.compose.foundation.shape.CutCornerShape(5.dp)
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
                width = 0.65.dp,
                color = Color.White.copy(alpha = if (checked) 0.30f else 0.18f),
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
                .background(if (checked) MaterialTheme.colorScheme.onPrimary else Color.White)
        )
    }
}

/**
 * Standard iOS row inside an [IosGroup].
 */
@Composable
fun IosRow(
    icon: ImageVector,
    badgeColor: Color,
    title: String,
    subtitle: String? = null,
    value: String? = null,
    pillText: String? = null,
    pillColor: Color = IosGreenDark,
    showChevron: Boolean = false,
    enabled: Boolean = true,
    onClick: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
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
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

/**
 * Standard iOS switch row inside an [IosGroup].
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
 * 2x2 iOS Control-Center frosted menu tile (APK 1.16 menu layout).
 */
@Composable
fun IosTile(
    icon: ImageVector,
    badgeColor: Color,
    title: String,
    subtitle: String,
    badgeText: String? = null,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Column(
        modifier = modifier
            .iosGlass(shape = MaterialTheme.shapes.large)
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

/** Neon boot screen. This is cosmetic only; it does not assert root or device status. */
@Composable
fun GlassSplash(visible: Boolean, modifier: Modifier = Modifier) {
    val phase = LocalNeonPhase.current
    val accent = MaterialTheme.colorScheme.primary
    val pink = MaterialTheme.colorScheme.secondary
    AnimatedVisibility(
        visible = visible,
        enter = if (LocalPixelMotionEnabled.current) fadeIn(tween(180)) else androidx.compose.animation.EnterTransition.None,
        exit = if (LocalPixelMotionEnabled.current) fadeOut(tween(260)) else androidx.compose.animation.ExitTransition.None,
        modifier = modifier,
    ) {
        Box(modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.Center) {
            GlassBackground(wallpaperLayer = null)
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 32.dp)) {
                val shape = MaterialTheme.shapes.extraLarge
                Image(
                    painter = painterResource(R.drawable.ic_synthetica_emblem),
                    contentDescription = "Synthetica",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(132.dp)
                        .shadow(20.dp, shape, ambientColor = accent.copy(alpha = 0.6f), spotColor = pink.copy(alpha = 0.6f))
                        .clip(shape)
                        .border(1.dp, accent.copy(alpha = 0.8f), shape),
                )
                Spacer(Modifier.height(24.dp))
                Text("SYNTHETICA", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Black, color = MaterialTheme.colorScheme.onBackground, letterSpacing = 2.sp)
                Spacer(Modifier.height(6.dp))
                val styleName = when (LocalManagerStyle.current) {
                    ManagerStyle.PIXEL -> "PIXEL"; ManagerStyle.CYBERPUNK -> "CYBERPUNK"
                    ManagerStyle.IOS_GLASS -> "GLASS"; ManagerStyle.NEON -> "NEON"
                }
                Text("$styleName // MANAGER 5.0.1", style = MaterialTheme.typography.labelMedium, color = accent, letterSpacing = 1.5.sp)
                Spacer(Modifier.height(28.dp))
                Box(
                    modifier = Modifier.width(128.dp).height(3.dp).background(MaterialTheme.colorScheme.onBackground.copy(alpha = 0.12f)).drawBehind {
                        val length = size.width * (0.35f + phase.value * 0.40f)
                        drawLine(Brush.horizontalGradient(listOf(accent, pink)), Offset.Zero, Offset(length, 0f), strokeWidth = size.height)
                    }
                )
            }
        }
    }
}
