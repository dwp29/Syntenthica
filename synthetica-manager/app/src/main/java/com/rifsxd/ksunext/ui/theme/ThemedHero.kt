package com.rifsxd.ksunext.ui.theme

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * Distinct hero structures, PNG emblems and live animations per design.
 * Root/kernel data and callbacks come unchanged from HomeScreen.
 */
@Composable
internal fun DistinctManagerHero(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    onClick: (() -> Unit)?,
) {
    val phase by rememberStylePhase()
    val clickMod = if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier
    when (LocalManagerStyle.current) {
        ManagerStyle.PIXEL -> PixelMatrixHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, phase, clickMod)
        ManagerStyle.CYBERPUNK -> CyberpunkBrutalHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, phase, clickMod)
        ManagerStyle.IOS_GLASS -> IosLiquidGlassHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, phase, clickMod)
        ManagerStyle.NEON -> NeonCyberHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, phase, clickMod)
        ManagerStyle.RETRO_ARCADE -> RetroBannerHero(eyebrow, title, statusPill, statusColor, modePill, kernelLine, metaLine, phase, clickMod)
    }
}

@Composable
private fun HeroEmblem(
    style: ManagerStyle,
    size: Dp,
    shape: Shape,
    border: Color,
    phase: Float,
) {
    val emblemRes = emblemResForStyle(style)
    when (style) {
        ManagerStyle.PIXEL -> {
            Box(
                modifier = Modifier
                    .size(size)
                    .background(Color(0xFF101010))
                    .border(1.5.dp, border, RectangleShape)
                    .padding(4.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val dot = 3.dp.toPx()
                    drawRect(border, Offset.Zero, Size(dot, dot))
                    drawRect(border, Offset(this.size.width - dot, 0f), Size(dot, dot))
                    drawRect(border, Offset(0f, this.size.height - dot), Size(dot, dot))
                    drawRect(border, Offset(this.size.width - dot, this.size.height - dot), Size(dot, dot))
                }
            }
        }
        ManagerStyle.CYBERPUNK -> {
            val cutShape = CutCornerShape(topStart = 2.dp, topEnd = 14.dp, bottomEnd = 2.dp, bottomStart = 14.dp)
            Box(
                modifier = Modifier
                    .size(size)
                    .clip(cutShape)
                    .background(Color(0xFF0A0D12))
                    .border(1.5.dp, border, cutShape)
                    .padding(3.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(cutShape)
                        .drawWithContent {
                            drawContent()
                            val scanY = this.size.height * phase
                            drawLine(
                                color = border.copy(alpha = 0.65f),
                                start = Offset(0f, scanY),
                                end = Offset(this.size.width, scanY),
                                strokeWidth = 1.5.dp.toPx(),
                            )
                        },
                )
            }
        }
        ManagerStyle.IOS_GLASS -> {
            val pedestalShape = RoundedCornerShape(22.dp)
            Box(
                modifier = Modifier
                    .size(size)
                    .shadow(16.dp, pedestalShape, ambientColor = border.copy(alpha = 0.45f), spotColor = border.copy(alpha = 0.55f))
                    .clip(pedestalShape)
                    .background(
                        Brush.linearGradient(
                            colors = listOf(
                                Color.White.copy(alpha = 0.25f),
                                border.copy(alpha = 0.14f),
                                Color(0xFF07162C).copy(alpha = 0.45f),
                            )
                        )
                    )
                    .border(1.25.dp, Color.White.copy(alpha = 0.65f), pedestalShape)
                    .padding(4.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(RoundedCornerShape(18.dp))
                        .drawWithContent {
                            drawContent()
                            val sx = this.size.width * phase
                            drawRect(
                                brush = Brush.linearGradient(
                                    colors = listOf(
                                        Color.Transparent,
                                        Color.White.copy(alpha = 0.28f),
                                        Color.Transparent,
                                    ),
                                    start = Offset(sx - this.size.width * 0.35f, 0f),
                                    end = Offset(sx + this.size.width * 0.20f, this.size.height),
                                )
                            )
                        },
                )
            }
        }
        ManagerStyle.RETRO_ARCADE -> {
            // Flat cabinet plate: no blur, hard 2 dp edge, pixel emblem inset.
            Box(
                modifier = Modifier
                    .size(size)
                    .background(Color(0xFF17120C))
                    .border(2.dp, border, CutCornerShape(topStart = 3.dp, topEnd = 10.dp, bottomEnd = 3.dp, bottomStart = 10.dp))
                    .padding(5.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
        ManagerStyle.NEON -> {
            val magenta = Color(0xFFFF4FD8)
            Box(
                modifier = Modifier
                    .size(size + 8.dp)
                    .drawBehind {
                        val pulse = 0.72f + 0.28f * abs(sin(phase * Math.PI.toFloat()))
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(border.copy(alpha = 0.36f * pulse), magenta.copy(alpha = 0.18f * pulse), Color.Transparent),
                            ),
                            radius = this.size.minDimension * 0.54f,
                        )
                    },
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(emblemRes),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(size)
                        .clip(shape)
                        .border(
                            width = 1.5.dp,
                            brush = Brush.linearGradient(listOf(border, magenta, border)),
                            shape = shape,
                        ),
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PixelMatrixHero(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    phase: Float,
    clickMod: Modifier,
) {
    val accent = MaterialTheme.colorScheme.primary
    val glass = LocalGlassStyle.current
    val step = (phase * 8f).roundToInt()
    val cursorChar = if (step % 2 == 0) "■" else "□"

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RectangleShape,
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                borderWidth = 1.5.dp,
                elevation = 8.dp,
            )
            .then(clickMod),
    ) {
        // Hardware Dot-Matrix LED Strip Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(accent.copy(alpha = 0.14f))
                .padding(horizontal = 14.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "${eyebrow.uppercase()} $cursorChar",
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = accent,
                letterSpacing = 1.1.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.width(8.dp))
            Canvas(modifier = Modifier.width(68.dp).height(12.dp)) {
                val cols = 10
                val rows = 3
                val cell = 3.5.dp.toPx()
                val gap = 3.dp.toPx()
                for (c in 0 until cols) {
                    val activeRow = (c + step) % rows
                    for (r in 0 until rows) {
                        val lit = r >= activeRow
                        drawRect(
                            color = accent.copy(alpha = if (lit) 0.88f else 0.18f),
                            topLeft = Offset(c * (cell + gap), r * (cell + 1.5.dp.toPx())),
                            size = Size(cell, cell),
                        )
                    }
                }
            }
        }
        HorizontalDivider(thickness = 1.dp, color = glass.divider)

        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                HeroEmblem(
                    style = ManagerStyle.PIXEL,
                    size = 56.dp,
                    shape = RectangleShape,
                    border = accent,
                    phase = phase,
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
                    if (kernelLine.isNotBlank()) {
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
            }

            Spacer(Modifier.height(14.dp))

            // Boxed Pixel Readout Grid Cells
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.background.copy(alpha = 0.45f))
                    .border(1.dp, glass.divider, RectangleShape)
                    .padding(10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                maxItemsInEachRow = 2,
            ) {
                IosPill(text = statusPill, color = statusColor)
                if (!modePill.isNullOrBlank()) {
                    IosPill(text = modePill, color = accent)
                }
            }

            Spacer(Modifier.height(10.dp))
            HorizontalDivider(thickness = 1.dp, color = accent.copy(alpha = 0.26f))
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "■",
                    style = MaterialTheme.typography.labelSmall,
                    color = accent,
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = metaLine,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CyberpunkBrutalHero(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    phase: Float,
    clickMod: Modifier,
) {
    val accent = MaterialTheme.colorScheme.primary
    val cyan = Color(0xFF00F0FF)
    val glass = LocalGlassStyle.current
    val cardShape = CutCornerShape(topStart = 2.dp, topEnd = 22.dp, bottomEnd = 2.dp, bottomStart = 18.dp)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = cardShape,
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                borderWidth = 1.5.dp,
                elevation = 8.dp,
            )
            .then(clickMod),
    ) {
        // Top Cyberbrutal Telemetry Rail
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(accent.copy(alpha = 0.16f))
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .background(accent)
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            ) {
                Text(
                    text = "SYS.01",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Black,
                    color = Color(0xFF090B0E),
                )
            }
            Spacer(Modifier.width(8.dp))
            Text(
                text = eyebrow.uppercase(),
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = accent,
                letterSpacing = 1.1.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "///",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Black,
                color = cyan,
            )
        }
        HorizontalDivider(thickness = 1.dp, color = accent.copy(alpha = 0.45f))

        Column(modifier = Modifier.padding(16.dp)) {
            // Reversed Command Deck Layout: Title + Solari Split-Flap on Left, Chamfered PNG Emblem on Right
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    DepartureBoardText(
                        text = title,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 2,
                    )
                    if (kernelLine.isNotBlank()) {
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
                Spacer(Modifier.width(12.dp))
                HeroEmblem(
                    style = ManagerStyle.CYBERPUNK,
                    size = 66.dp,
                    shape = MaterialTheme.shapes.large,
                    border = accent,
                    phase = phase,
                )
            }

            Spacer(Modifier.height(14.dp))

            // Industrial Left-Railed Status Bay
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(accent.copy(alpha = 0.10f))
                    .border(1.dp, accent.copy(alpha = 0.38f), MaterialTheme.shapes.small)
                    .padding(horizontal = 12.dp, vertical = 9.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    modifier = Modifier
                        .width(4.dp)
                        .height(24.dp)
                        .background(accent),
                )
                Spacer(Modifier.width(10.dp))
                FlowRow(
                    modifier = Modifier.weight(1f),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                    maxItemsInEachRow = 2,
                ) {
                    IosPill(text = statusPill, color = statusColor)
                    if (!modePill.isNullOrBlank()) {
                        IosPill(text = modePill, color = accent)
                    }
                }
            }

            Spacer(Modifier.height(10.dp))
            // Animated horizontal laser telemetry bar
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(2.dp)
                    .background(glass.divider)
                    .drawBehind {
                        val barW = size.width * 0.28f
                        val startX = (size.width - barW) * phase
                        drawLine(
                            brush = Brush.horizontalGradient(listOf(Color.Transparent, accent, cyan, Color.Transparent)),
                            start = Offset(startX, size.height / 2f),
                            end = Offset(startX + barW, size.height / 2f),
                            strokeWidth = size.height,
                        )
                    }
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = metaLine,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun IosLiquidGlassHero(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    phase: Float,
    clickMod: Modifier,
) {
    val accent = MaterialTheme.colorScheme.primary
    val glass = LocalGlassStyle.current

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RoundedCornerShape(30.dp),
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                borderWidth = 1.1.dp,
                elevation = 8.dp,
            )
            .then(clickMod)
            .padding(horizontal = 22.dp, vertical = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = eyebrow.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
            color = accent,
            letterSpacing = 1.sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )

        Spacer(Modifier.height(10.dp))

        // Centered iOS 18 Liquid Glass Pedestal with 3D Refractive Knot PNG Emblem
        HeroEmblem(
            style = ManagerStyle.IOS_GLASS,
            size = 70.dp,
            shape = CircleShape,
            border = accent,
            phase = phase,
        )

        Spacer(Modifier.height(10.dp))

        Text(
            text = title,
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        if (kernelLine.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(
                text = kernelLine,
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }

        Spacer(Modifier.height(12.dp))

        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            maxItemsInEachRow = 2,
        ) {
            IosPill(text = statusPill, color = statusColor)
            if (!modePill.isNullOrBlank()) {
                IosPill(text = modePill, color = accent)
            }
        }

        Spacer(Modifier.height(12.dp))
        HorizontalDivider(thickness = 0.7.dp, color = glass.divider)
        Spacer(Modifier.height(8.dp))

        Text(
            text = metaLine,
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun NeonCyberHero(
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    phase: Float,
    clickMod: Modifier,
) {
    val accent = MaterialTheme.colorScheme.primary
    val magenta = Color(0xFFFF4FD8)
    val glass = LocalGlassStyle.current

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RoundedCornerShape(20.dp),
                tintTop = glass.elevatedTintTop,
                tintBottom = glass.elevatedTintBottom,
                borderWidth = 1.5.dp,
                elevation = 8.dp,
            )
            .then(clickMod)
            .padding(18.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            HeroEmblem(
                style = ManagerStyle.NEON,
                size = 58.dp,
                shape = MaterialTheme.shapes.large,
                border = accent,
                phase = phase,
            )
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(7.dp)
                            .clip(CircleShape)
                            .background(accent),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = eyebrow.uppercase(),
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = accent,
                        letterSpacing = 1.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Spacer(Modifier.height(5.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        if (kernelLine.isNotBlank()) {
            Spacer(Modifier.height(12.dp))
            Text(
                text = kernelLine,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }

        Spacer(Modifier.height(12.dp))

        // Neon Dual-Laser Status Bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(MaterialTheme.shapes.medium)
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            accent.copy(alpha = 0.20f),
                            magenta.copy(alpha = 0.12f),
                        )
                    )
                )
                .border(1.dp, Brush.horizontalGradient(listOf(accent.copy(alpha = 0.65f), magenta.copy(alpha = 0.45f))), MaterialTheme.shapes.medium)
                .padding(horizontal = 10.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
                maxItemsInEachRow = 2,
            ) {
                IosPill(text = statusPill, color = statusColor)
                if (!modePill.isNullOrBlank()) {
                    IosPill(text = modePill, color = accent)
                }
            }
        }

        Spacer(Modifier.height(10.dp))

        // Animated Neon Laser Pulse Divider
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(2.5.dp)
                .clip(CircleShape)
                .background(glass.divider)
                .drawBehind {
                    val pulseW = size.width * (0.35f + 0.50f * abs(sin(phase * Math.PI.toFloat())))
                    drawLine(
                        brush = Brush.horizontalGradient(listOf(accent, magenta)),
                        start = Offset(0f, size.height / 2f),
                        end = Offset(pulseW, size.height / 2f),
                        strokeWidth = size.height,
                    )
                }
        )

        Spacer(Modifier.height(8.dp))
        Text(
            text = metaLine,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}


/**
 * Shared banner geometry for the three illustrated themes.
 *
 * The illustration is the hero: a 16:9 picture, cropped to a fixed band, with
 * the live status, title and kernel data sitting directly on top of it. The
 * parallax slides only the background layer so the character in the foreground
 * stays put and stays sharp.
 */
@Composable
private fun IllustratedBannerHero(
    banner: Int,
    bannerFar: Int,
    eyebrow: String,
    title: String,
    statusPill: String,
    statusColor: Color,
    modePill: String?,
    kernelLine: String,
    metaLine: String,
    phase: Float,
    clickMod: Modifier,
    shape: Shape,
    bandHeight: Dp,
    titleStyle: TextStyle,
    titleColor: Color,
    bannerTint: Color,
    dataBackground: Color,
    dataInk: Color,
    parallax: Dp,
    pulse: Boolean = false,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(bandHeight)
            .clip(shape)
            .background(bannerTint)
            .then(clickMod),
    ) {
        // Far layer: the scenery, sliding slowly for parallax.
        Image(
            painter = painterResource(bannerFar),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .fillMaxSize()
                .offset(x = (-parallax + parallax * 2f * phase))
                .graphicsLayer { alpha = 0.55f },
        )
        // Near layer: the full illustration with the character.
        Image(
            painter = painterResource(banner),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer {
                    // A slow breathing zoom sells "animated" without moving the
                    // character far enough to look detached from the frame.
                    val grow = 1.02f + 0.015f * (if (pulse) abs(sin(phase * Math.PI.toFloat())) else phase)
                    scaleX = grow
                    scaleY = grow
                },
        )
        // Bottom gradient keeps white text readable over bright pixel art.
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(bandHeight * 0.62f)
                .align(Alignment.BottomCenter)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.62f)))),
        )
        // Status row, top end, over the scenery.
        Row(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (modePill != null) {
                Text(
                    text = modePill.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = dataInk,
                    maxLines = 1,
                    modifier = Modifier
                        .background(dataBackground.copy(alpha = 0.88f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 3.dp),
                )
                Spacer(Modifier.width(6.dp))
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .background(statusColor.copy(alpha = 0.92f), RoundedCornerShape(6.dp))
                    .padding(horizontal = 9.dp, vertical = 4.dp),
            ) {
                Box(Modifier.size(6.dp).background(Color.White, RoundedCornerShape(3.dp)))
                Spacer(Modifier.width(5.dp))
                Text(
                    text = statusPill.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White,
                    maxLines = 1,
                )
            }
        }
        // Emblem, bottom start, over the character's corner but small enough to
        // never hide the face.
        Image(
            painter = painterResource(emblemResForStyle(LocalManagerStyle.current)),
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(start = 12.dp, bottom = 52.dp)
                .size(44.dp),
        )
        // Title block, bottom, above the data strip.
        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .fillMaxWidth()
                .padding(start = 14.dp, end = 14.dp, bottom = 34.dp),
        ) {
            Text(
                text = title,
                style = titleStyle,
                color = titleColor,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.graphicsLayer {
                    // A hint of motion only; the banner already carries the animation.
                    translationX = sin(phase * 2f * Math.PI.toFloat()) * 0.6f
                },
            )
            Text(
                text = eyebrow,
                style = MaterialTheme.typography.labelSmall,
                color = titleColor.copy(alpha = 0.82f),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        // Data strip pinned to the very bottom, like the reference mock.
        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .background(dataBackground.copy(alpha = 0.90f))
                .padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = kernelLine,
                style = MaterialTheme.typography.labelSmall,
                color = dataInk,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f, fill = false),
            )
            Text(
                text = "  ·  ",
                style = MaterialTheme.typography.labelSmall,
                color = dataInk.copy(alpha = 0.55f),
            )
            Text(
                text = metaLine,
                style = MaterialTheme.typography.labelSmall,
                color = dataInk.copy(alpha = 0.80f),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** 16-bit amusement park: bright, chunky, all-ages. */
@Composable
private fun RetroBannerHero(
    eyebrow: String, title: String, statusPill: String, statusColor: Color, modePill: String?,
    kernelLine: String, metaLine: String, phase: Float, clickMod: Modifier,
) {
    IllustratedBannerHero(
        banner = R.drawable.theme_banner_retro,
        bannerFar = R.drawable.theme_banner_retro_far,
        eyebrow = eyebrow, title = title, statusPill = statusPill, statusColor = statusColor,
        modePill = modePill, kernelLine = kernelLine, metaLine = metaLine, phase = phase,
        clickMod = clickMod,
        shape = RoundedCornerShape(14.dp),
        bandHeight = 214.dp,
        titleStyle = MaterialTheme.typography.headlineMedium,
        titleColor = Color.White,
        bannerTint = Color(0xFF1FB6E8),
        dataBackground = Color(0xFF10214A),
        dataInk = Color(0xFFEAF6FF),
        parallax = 10.dp,
    )
}
