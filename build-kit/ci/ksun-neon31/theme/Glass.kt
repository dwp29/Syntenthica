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

/**
 * Animated cyberpunk grid and accent-colored light blooms.
 */
@Composable
fun GlassBackground(
    modifier: Modifier = Modifier,
    wallpaperLayer: GraphicsLayer? = LocalGlassWallpaperLayer.current,
) {
    val glass = LocalGlassStyle.current
    val phase = LocalNeonPhase.current
    val glow = LocalNeonGlow.current
    val cyan = MaterialTheme.colorScheme.primary
    val pink = MaterialTheme.colorScheme.secondary
    Canvas(
        modifier = modifier.fillMaxSize().drawWithContent {
            if (wallpaperLayer != null) {
                wallpaperLayer.record { this@drawWithContent.drawContent() }
                drawLayer(wallpaperLayer)
            } else drawContent()
        }
    ) {
        drawRect(glass.canvasBase)
        // AMOLED means an actually black canvas, not a black base obscured by
        // full-screen gradients and grid lines. Neon remains on the controls.
        if (!glass.isAmoled) {
            val p = phase.value
            val haloStrength = glow * if (glass.isDark) 1f else 0.50f
            val w = size.width
            val h = size.height
            val left = Offset(w * (0.12f + p * 0.08f), h * 0.10f)
            val right = Offset(w * (0.88f - p * 0.06f), h * 0.38f)
            drawCircle(
                brush = Brush.radialGradient(listOf(cyan.copy(alpha = (0.17f * haloStrength).coerceIn(0f, 1f)), Color.Transparent), left, w * 0.84f),
                radius = w * 0.84f, center = left,
            )
            drawCircle(
                brush = Brush.radialGradient(listOf(pink.copy(alpha = (0.16f * haloStrength).coerceIn(0f, 1f)), Color.Transparent), right, w * 0.78f),
                radius = w * 0.78f, center = right,
            )
            val step = 48.dp.toPx()
            var x = 0f
            while (x < w) {
                drawLine(cyan.copy(alpha = 0.045f), Offset(x, 0f), Offset(x, h), strokeWidth = 0.6.dp.toPx())
                x += step
            }
            var y = 0f
            while (y < h) {
                drawLine(cyan.copy(alpha = 0.035f), Offset(0f, y), Offset(w, y), strokeWidth = 0.6.dp.toPx())
                y += step
            }
            // One shared animated scan line; text and controls remain motionless/readable.
            val sweep = h * (0.12f + 0.76f * p)
            drawRect(
                brush = Brush.verticalGradient(
                    0f to Color.Transparent,
                    0.5f to cyan.copy(alpha = 0.05f),
                    1f to Color.Transparent,
                    startY = sweep - 18.dp.toPx(), endY = sweep + 18.dp.toPx(),
                ),
                topLeft = Offset(0f, sweep - 18.dp.toPx()),
                size = androidx.compose.ui.geometry.Size(w, 36.dp.toPx()),
            )
        }
    }
}

/**
 * Neon panel with gradient border, shared animated halo and no per-card GPU blur.
 */
@Suppress("UNUSED_PARAMETER")
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
    val phase = LocalNeonPhase.current
    val glow = LocalNeonGlow.current
    val accent = MaterialTheme.colorScheme.primary
    val pink = MaterialTheme.colorScheme.secondary
    val resolvedTop = if (tintTop != Color.Unspecified) tintTop else glass.cardTintTop
    val resolvedBottom = if (tintBottom != Color.Unspecified) tintBottom else glass.cardTintBottom

    this
        .let { mod ->
            if (elevation > 0.dp) mod.shadow(
                elevation = elevation.coerceAtMost(12.dp),
                shape = shape,
                ambientColor = accent.copy(alpha = (0.22f * glow).coerceIn(0f, 1f)),
                spotColor = pink.copy(alpha = (0.20f * glow).coerceIn(0f, 1f)),
            ) else mod
        }
        .clip(shape)
        .drawWithCache {
            val plate = Brush.verticalGradient(listOf(resolvedTop, resolvedBottom))
            val edge = Brush.horizontalGradient(listOf(accent.copy(alpha = (0.75f * glow).coerceIn(0f, 1f)), pink.copy(alpha = (0.60f * glow).coerceIn(0f, 1f)), Color.Transparent))
            onDrawBehind {
                drawRect(plate)
                val center = Offset(size.width * 0.90f, size.height * 0.06f)
                val radius = size.width.coerceAtLeast(size.height) * 0.7f
                drawCircle(
                    brush = Brush.radialGradient(
                        listOf(accent.copy(alpha = ((0.06f + 0.07f * phase.value) * glow * if (glass.isDark) 1f else 0.55f).coerceIn(0f, 1f)), Color.Transparent),
                        center = center, radius = radius,
                    ),
                    radius = radius, center = center,
                )
                drawLine(edge, Offset(0f, 0f), Offset(size.width, 0f), strokeWidth = 1.2.dp.toPx())
            }
        }
        .let { mod ->
            if (borderWidth > 0.dp) mod.border(
                width = borderWidth,
                brush = Brush.linearGradient(
                    listOf(accent.copy(alpha = (0.62f * glow).coerceIn(0f, 1f)), Color(0xFF5864A5).copy(alpha = 0.28f), pink.copy(alpha = (0.45f * glow).coerceIn(0f, 1f)))
                ),
                shape = shape,
            ) else mod
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
                color = MaterialTheme.colorScheme.primary,
                letterSpacing = 1.1.sp,
                modifier = Modifier.padding(start = 16.dp, bottom = 7.dp),
            )
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .iosGlass(shape = MaterialTheme.shapes.large),
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
    val phase = LocalNeonPhase.current
    val shape = androidx.compose.foundation.shape.CutCornerShape(7.dp)
    Box(
        modifier = Modifier
            .size(size)
            .shadow(7.dp, shape, ambientColor = color.copy(alpha = 0.45f), spotColor = color.copy(alpha = 0.45f))
            .clip(shape)
            .background(Color(0xFF0C1122))
            .drawBehind {
                val radius = this.size.minDimension * 0.75f
                drawCircle(
                    brush = Brush.radialGradient(listOf(color.copy(alpha = 0.15f + 0.10f * phase.value), Color.Transparent), radius = radius),
                    radius = radius,
                )
            }
            .border(1.dp, color.copy(alpha = 0.75f), shape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(imageVector = icon, contentDescription = null, tint = color, modifier = Modifier.size(iconSize))
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
    val activeColor = MaterialTheme.colorScheme.primary
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
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = MaterialTheme.shapes.extraLarge,
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                elevation = 10.dp,
            )
            .let { mod -> if (onClick != null) mod.clickable(onClick = onClick) else mod }
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Text(
            text = eyebrow.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.3.sp,
        )
        Spacer(Modifier.height(15.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Image(
                painter = painterResource(R.drawable.ic_synthetica_emblem),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(54.dp)
                    .clip(MaterialTheme.shapes.medium)
                    .border(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.6f), MaterialTheme.shapes.medium),
            )
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = kernelLine,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            IosPill(text = statusPill, color = statusColor)
            if (!modePill.isNullOrBlank()) IosPill(text = modePill, color = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(14.dp))
        HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.primary.copy(alpha = 0.22f))
        Spacer(Modifier.height(10.dp))
        Text(
            text = metaLine,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Neon boot screen. This is cosmetic only; it does not assert root or device status. */
@Composable
fun GlassSplash(visible: Boolean, modifier: Modifier = Modifier) {
    val phase = LocalNeonPhase.current
    val accent = MaterialTheme.colorScheme.primary
    val pink = MaterialTheme.colorScheme.secondary
    AnimatedVisibility(visible = visible, enter = fadeIn(tween(180)), exit = fadeOut(tween(260)), modifier = modifier) {
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
                Text("NEON // MANAGER 3.1", style = MaterialTheme.typography.labelMedium, color = accent, letterSpacing = 1.5.sp)
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
