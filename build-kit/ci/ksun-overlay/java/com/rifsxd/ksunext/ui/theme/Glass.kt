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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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

/**
 * Living iOS 18 Liquid Glass aurora wallpaper.
 * Softly breathing sapphire, cyan, indigo, and teal light blooms give real glass surfaces
 * rich optical depth and refraction as cards scroll over them.
 */
@Composable
fun GlassBackground(
    modifier: Modifier = Modifier,
    wallpaperLayer: GraphicsLayer? = LocalGlassWallpaperLayer.current,
) {
    val glass = LocalGlassStyle.current
    val infinite = rememberInfiniteTransition(label = "synthetica-aurora")
    val phase by infinite.animateFloat(
        initialValue = 0f,
        targetValue = (Math.PI * 2.0).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 16000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "aurora-phase",
    )

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .drawWithContent {
                if (wallpaperLayer != null) {
                    wallpaperLayer.record {
                        this@drawWithContent.drawContent()
                    }
                    drawLayer(wallpaperLayer)
                } else {
                    drawContent()
                }
            }
    ) {
        val w = size.width
        val h = size.height
        val dx = cos(phase) * w * 0.06f
        val dy = sin(phase) * h * 0.04f

        if (!glass.isDark) {
            drawRect(
                brush = Brush.verticalGradient(
                    0.0f to Color(0xFFE5F0FF),
                    0.48f to Color(0xFFEEF5FD),
                    1.0f to Color(0xFFE3EDFB),
                )
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF69B7FF).copy(alpha = 0.52f), Color.Transparent),
                    center = Offset(w * 0.16f + dx, h * 0.12f + dy),
                    radius = w * 0.78f,
                ),
                radius = w * 0.78f,
                center = Offset(w * 0.16f + dx, h * 0.12f + dy),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF3CE0D0).copy(alpha = 0.36f), Color.Transparent),
                    center = Offset(w * 0.88f - dx, h * 0.28f + dy * 0.6f),
                    radius = w * 0.70f,
                ),
                radius = w * 0.70f,
                center = Offset(w * 0.88f - dx, h * 0.28f + dy * 0.6f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF9185FF).copy(alpha = 0.32f), Color.Transparent),
                    center = Offset(w * 0.76f + dx * 0.5f, h * 0.74f - dy),
                    radius = w * 0.82f,
                ),
                radius = w * 0.82f,
                center = Offset(w * 0.76f + dx * 0.5f, h * 0.74f - dy),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF5CC8FF).copy(alpha = 0.38f), Color.Transparent),
                    center = Offset(w * 0.18f - dx * 0.4f, h * 0.88f + dy * 0.5f),
                    radius = w * 0.72f,
                ),
                radius = w * 0.72f,
                center = Offset(w * 0.18f - dx * 0.4f, h * 0.88f + dy * 0.5f),
            )
        } else {
            val baseTop = if (glass.isAmoled) Color(0xFF000000) else Color(0xFF040B1A)
            val baseMid = if (glass.isAmoled) Color(0xFF01040B) else Color(0xFF07142B)
            val baseBot = if (glass.isAmoled) Color(0xFF000000) else Color(0xFF040A17)
            val orbScale = if (glass.isAmoled) 0.72f else 1.0f

            drawRect(
                brush = Brush.verticalGradient(
                    0.0f to baseTop,
                    0.52f to baseMid,
                    1.0f to baseBot,
                )
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF0A6CFF).copy(alpha = 0.42f * orbScale), Color.Transparent),
                    center = Offset(w * 0.18f + dx, h * 0.11f + dy),
                    radius = w * 0.80f,
                ),
                radius = w * 0.80f,
                center = Offset(w * 0.18f + dx, h * 0.11f + dy),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF00D2D3).copy(alpha = 0.28f * orbScale), Color.Transparent),
                    center = Offset(w * 0.86f - dx, h * 0.26f + dy * 0.6f),
                    radius = w * 0.68f,
                ),
                radius = w * 0.68f,
                center = Offset(w * 0.86f - dx, h * 0.26f + dy * 0.6f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF5E5CE6).copy(alpha = 0.30f * orbScale), Color.Transparent),
                    center = Offset(w * 0.78f + dx * 0.5f, h * 0.72f - dy),
                    radius = w * 0.82f,
                ),
                radius = w * 0.82f,
                center = Offset(w * 0.78f + dx * 0.5f, h * 0.72f - dy),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF0984E3).copy(alpha = 0.30f * orbScale), Color.Transparent),
                    center = Offset(w * 0.16f - dx * 0.4f, h * 0.88f + dy * 0.5f),
                    radius = w * 0.74f,
                ),
                radius = w * 0.74f,
                center = Offset(w * 0.16f - dx * 0.4f, h * 0.88f + dy * 0.5f),
            )
        }
    }
}

/**
 * Core real-time GPU backdrop blur modifier.
 * Samples either [LocalGlassContentLayer] (for floating bars) or [LocalGlassWallpaperLayer] (for cards)
 * via a dedicated hardware RenderNode [GraphicsLayer] with [BlurEffect], plus multi-stop frosted tint,
 * optical inner highlight, and diagonal specular border.
 */
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
    val wallpaperLayer = LocalGlassWallpaperLayer.current
    val contentLayer = LocalGlassContentLayer.current
    val sampleBlurLayer = rememberGraphicsLayer()
    var posInRoot by remember { mutableStateOf(Offset.Zero) }

    val resolvedBlur = if (blurRadius != Dp.Unspecified) blurRadius else glass.blurRadius
    val resolvedTop = if (tintTop != Color.Unspecified) tintTop else glass.cardTintTop
    val resolvedBottom = if (tintBottom != Color.Unspecified) tintBottom else glass.cardTintBottom

    this
        .onGloballyPositioned { coords ->
            posInRoot = coords.positionInRoot()
        }
        .let { mod ->
            if (elevation > 0.dp) {
                mod.shadow(
                    elevation = elevation,
                    shape = shape,
                    ambientColor = glass.shadowColor,
                    spotColor = glass.shadowColor,
                )
            } else mod
        }
        .clip(shape)
        .drawWithCache {
            val blurPx = resolvedBlur.toPx()
            val pad = blurPx.roundToInt().coerceIn(0, 96)
            val tintBrush = Brush.verticalGradient(listOf(resolvedTop, resolvedBottom))
            val lusterBrush = Brush.verticalGradient(
                0.0f to glass.innerHighlight,
                0.35f to Color.Transparent,
            )
            onDrawBehind {
                val src = if (blurContent) (contentLayer ?: wallpaperLayer) else wallpaperLayer
                val w = size.width.roundToInt()
                val h = size.height.roundToInt()
                if (src != null && w > 0 && h > 0) {
                    sampleBlurLayer.renderEffect =
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && blurPx > 0.5f) {
                            BlurEffect(blurPx, blurPx, TileMode.Clamp)
                        } else {
                            null
                        }
                    sampleBlurLayer.record(
                        size = IntSize((w + pad * 2).coerceAtLeast(1), (h + pad * 2).coerceAtLeast(1))
                    ) {
                        translate(left = -posInRoot.x + pad, top = -posInRoot.y + pad) {
                            drawLayer(src)
                        }
                    }
                    translate(left = -pad.toFloat(), top = -pad.toFloat()) {
                        drawLayer(sampleBlurLayer)
                    }
                }
                drawRect(brush = tintBrush)
                drawRect(brush = lusterBrush)
            }
        }
        .let { mod ->
            if (borderWidth > 0.dp) {
                mod.border(
                    width = borderWidth,
                    brush = Brush.linearGradient(
                        colors = listOf(glass.borderHighlight, glass.borderMid, glass.borderShadow),
                        start = Offset.Zero,
                        end = Offset.Infinite,
                    ),
                    shape = shape,
                )
            } else mod
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
                    modifier = Modifier.size(38.dp),
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Rounded.ArrowBackIos,
                        contentDescription = null,
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
                content = actions,
            )
        }
        HorizontalDivider(
            thickness = 0.75.dp,
            color = glass.borderHighlight.copy(alpha = if (glass.isDark) 0.22f else 0.65f),
        )
    }
}

/**
 * Grouped frosted iOS Settings / Control-Center section card.
 */
@Composable
fun IosGroup(
    title: String? = null,
    footer: String? = null,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        if (!title.isNullOrBlank()) {
            Text(
                text = title.uppercase(),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                letterSpacing = 0.8.sp,
                modifier = Modifier.padding(start = 16.dp, bottom = 7.dp),
            )
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .iosGlass(shape = RoundedCornerShape(22.dp)),
            content = content,
        )
        if (!footer.isNullOrBlank()) {
            Text(
                text = footer,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.85f),
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp),
            )
        }
    }
}

@Composable
fun IosGroupDivider() {
    val glass = LocalGlassStyle.current
    HorizontalDivider(
        modifier = Modifier.padding(start = 58.dp, end = 16.dp),
        thickness = 0.65.dp,
        color = glass.divider,
    )
}

/**
 * Glossy iOS squircle icon badge.
 */
@Composable
fun IosBadgeIcon(
    icon: ImageVector,
    color: Color,
    size: Dp = 32.dp,
    iconSize: Dp = 18.dp,
) {
    val shape = RoundedCornerShape((size.value * 0.28f).dp)
    Box(
        modifier = Modifier
            .size(size)
            .clip(shape)
            .background(
                Brush.verticalGradient(
                    listOf(
                        color.blend(Color.White, 0.20f),
                        color,
                    )
                )
            )
            .border(
                width = 0.75.dp,
                color = Color.White.copy(alpha = 0.35f),
                shape = shape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White,
            modifier = Modifier.size(iconSize),
        )
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
    val textColor = if (glass.isDark) color.blend(Color.White, 0.28f) else color.blend(Color.Black, 0.18f)
    Box(
        modifier = modifier
            .clip(CircleShape)
            .background(color.copy(alpha = bgAlpha))
            .border(0.75.dp, color.copy(alpha = borderAlpha), CircleShape)
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
    val activeColor = if (glass.isDark) IosGreenDark else IosGreenLight
    val inactiveColor = if (glass.isDark) Color.White.copy(alpha = 0.18f) else Color(0xFF0E2240).copy(alpha = 0.14f)
    val trackColor by animateColorAsState(
        targetValue = if (checked) activeColor else inactiveColor,
        animationSpec = tween(durationMillis = 200),
        label = "ios-switch-track",
    )
    val thumbOffset by animateDpAsState(
        targetValue = if (checked) 20.dp else 2.dp,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow, dampingRatio = 0.78f),
        label = "ios-switch-thumb",
    )

    Box(
        modifier = Modifier
            .width(48.dp)
            .height(28.dp)
            .alpha(if (enabled) 1f else 0.42f)
            .clip(CircleShape)
            .background(trackColor)
            .border(
                width = 0.65.dp,
                color = Color.White.copy(alpha = if (checked) 0.30f else 0.18f),
                shape = CircleShape,
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
                .shadow(3.dp, CircleShape, clip = false)
                .clip(CircleShape)
                .background(Color.White)
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
                maxLines = 1,
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
            .iosGlass(shape = RoundedCornerShape(22.dp))
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

/**
 * Flagship Synthetica 2.0 frosted hero status card on Home screen.
 */
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
    val glass = LocalGlassStyle.current
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RoundedCornerShape(26.dp),
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                elevation = 10.dp,
            )
            .drawBehind {
                // Soft internal sapphire/emerald ambient refraction glow
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(statusColor.copy(alpha = if (glass.isDark) 0.24f else 0.18f), Color.Transparent),
                        center = Offset(size.width * 0.88f, size.height * 0.22f),
                        radius = size.width * 0.58f,
                    ),
                    radius = size.width * 0.58f,
                    center = Offset(size.width * 0.88f, size.height * 0.22f),
                )
            }
            .let { mod -> if (onClick != null) mod.clickable(onClick = onClick) else mod }
            .padding(horizontal = 20.dp, vertical = 20.dp)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = eyebrow.uppercase(),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    letterSpacing = 0.9.sp,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (!modePill.isNullOrBlank()) {
                        IosPill(text = modePill, color = MaterialTheme.colorScheme.primary)
                    }
                    IosPill(text = statusPill, color = statusColor)
                }
            }

            Spacer(Modifier.height(10.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                Image(
                    painter = painterResource(R.drawable.ic_synthetica_emblem),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(46.dp)
                        .clip(RoundedCornerShape(13.dp))
                        .border(
                            0.75.dp,
                            Color.White.copy(alpha = 0.45f),
                            RoundedCornerShape(13.dp),
                        ),
                )
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = kernelLine,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            Spacer(Modifier.height(12.dp))

            HorizontalDivider(thickness = 0.65.dp, color = glass.divider)

            Spacer(Modifier.height(10.dp))

            Text(
                text = metaLine,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/**
 * Redesigned Synthetica 2.0 3D Liquid Glass Splash Screen.
 * Showcases the crystal ribbon emblem inside a frosted glass squircle pedestal
 * with diagonal specular sheen, breathing sapphire-cyan aurora, and shimmer bar.
 */
@Composable
fun GlassSplash(
    visible: Boolean,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(tween(180)),
        exit = fadeOut(tween(420, easing = FastOutSlowInEasing)),
        modifier = modifier,
    ) {
        var entered by remember { mutableStateOf(false) }
        LaunchedEffect(Unit) { entered = true }

        val cardScale by animateFloatAsState(
            targetValue = if (entered) 1f else 0.86f,
            animationSpec = spring(dampingRatio = 0.74f, stiffness = Spring.StiffnessLow),
            label = "splash-scale",
        )
        val contentAlpha by animateFloatAsState(
            targetValue = if (entered) 1f else 0f,
            animationSpec = tween(420, easing = FastOutSlowInEasing),
            label = "splash-alpha",
        )

        val infinite = rememberInfiniteTransition(label = "splash-shimmer")
        val sheenProgress by infinite.animateFloat(
            initialValue = -0.4f,
            targetValue = 1.4f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 1500, easing = FastOutSlowInEasing),
                repeatMode = RepeatMode.Restart,
            ),
            label = "splash-sheen",
        )
        val haloPulse by infinite.animateFloat(
            initialValue = 0.90f,
            targetValue = 1.10f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 1800, easing = FastOutSlowInEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "splash-halo",
        )

        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0.0f to Color(0xFF030A1A),
                        0.45f to Color(0xFF071B3D),
                        1.0f to Color(0xFF030915),
                    )
                ),
            contentAlignment = Alignment.Center,
        ) {
            // Ambient sapphire & cyan aurora blooms behind pedestal
            Canvas(modifier = Modifier.fillMaxSize()) {
                val cx = size.width * 0.5f
                val cy = size.height * 0.44f
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(Color(0xFF0A84FF).copy(alpha = 0.42f), Color.Transparent),
                        center = Offset(cx, cy),
                        radius = size.minDimension * 0.54f * haloPulse,
                    ),
                    radius = size.minDimension * 0.54f * haloPulse,
                    center = Offset(cx, cy),
                )
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(Color(0xFF00E5FF).copy(alpha = 0.22f), Color.Transparent),
                        center = Offset(cx * 1.15f, cy * 0.82f),
                        radius = size.minDimension * 0.38f,
                    ),
                    radius = size.minDimension * 0.38f,
                    center = Offset(cx * 1.15f, cy * 0.82f),
                )
            }

            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .scale(cardScale)
                    .alpha(contentAlpha)
                    .padding(horizontal = 32.dp),
            ) {
                val pedestalShape = RoundedCornerShape(34.dp)
                Box(
                    modifier = Modifier
                        .size(132.dp)
                        .shadow(
                            elevation = 28.dp,
                            shape = pedestalShape,
                            ambientColor = Color(0xFF0099FF).copy(alpha = 0.55f),
                            spotColor = Color(0xFF0099FF).copy(alpha = 0.65f),
                        )
                        .clip(pedestalShape)
                        .background(
                            Brush.linearGradient(
                                colors = listOf(
                                    Color.White.copy(alpha = 0.22f),
                                    Color(0xFF5AC8FA).copy(alpha = 0.10f),
                                    Color(0xFF081834).copy(alpha = 0.48f),
                                )
                            )
                        )
                        .border(
                            width = 1.4.dp,
                            brush = Brush.linearGradient(
                                colors = listOf(
                                    Color.White.copy(alpha = 0.78f),
                                    Color(0xFF64D2FF).copy(alpha = 0.36f),
                                    Color.White.copy(alpha = 0.14f),
                                )
                            ),
                            shape = pedestalShape,
                        )
                        .padding(8.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Image(
                        painter = painterResource(R.drawable.ic_synthetica_emblem),
                        contentDescription = "Synthetica",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .fillMaxSize()
                            .clip(RoundedCornerShape(27.dp))
                            .drawWithContent {
                                drawContent()
                                val sx = size.width * sheenProgress
                                drawRect(
                                    brush = Brush.linearGradient(
                                        colors = listOf(
                                            Color.Transparent,
                                            Color.White.copy(alpha = 0.26f),
                                            Color.Transparent,
                                        ),
                                        start = Offset(sx - size.width * 0.35f, 0f),
                                        end = Offset(sx + size.width * 0.15f, size.height),
                                    )
                                )
                            },
                    )
                }

                Spacer(Modifier.height(26.dp))

                Text(
                    text = "Synthetica",
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                    letterSpacing = (-0.5).sp,
                )

                Spacer(Modifier.height(8.dp))

                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.10f))
                        .border(0.8.dp, Color(0xFF64D2FF).copy(alpha = 0.36f), CircleShape)
                        .padding(horizontal = 14.dp, vertical = 5.dp),
                ) {
                    Text(
                        text = "2.0  •  LIQUID GLASS MANAGER",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFFB8E4FF),
                        letterSpacing = 1.1.sp,
                    )
                }

                Spacer(Modifier.height(34.dp))

                // Sleek liquid-glass shimmer progress pill
                Box(
                    modifier = Modifier
                        .width(116.dp)
                        .height(4.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.14f))
                        .drawWithContent {
                            drawContent()
                            val px = size.width * sheenProgress
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
}
