package com.rifsxd.ksunext.ui.theme

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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R

/** The same status and callbacks, arranged differently for each design. */
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
    val style = LocalManagerStyle.current
    val glass = LocalGlassStyle.current
    val panel = Modifier.fillMaxWidth().iosGlass(
        shape = if (style == ManagerStyle.PIXEL) RectangleShape else MaterialTheme.shapes.extraLarge,
        tintTop = glass.elevatedTintTop, tintBottom = glass.elevatedTintBottom, elevation = 8.dp,
    ).let { if (onClick != null) it.clickable(onClick = onClick) else it }
    when (style) {
        ManagerStyle.PIXEL -> Column(panel) {
            Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.primary.copy(alpha = .12f))
                .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                HeroEyebrow(eyebrow)
                Text("■ ■ ■", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically) {
                HeroEmblem(52.dp, RectangleShape)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) { HeroTitle(title); HeroKernel(kernelLine) }
            }
            HorizontalDivider(thickness = 1.dp, color = glass.divider)
            Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                HeroStatuses(statusPill, statusColor, modePill)
                Spacer(Modifier.height(8.dp))
                HeroMeta(metaLine)
            }
        }
        ManagerStyle.CYBERPUNK -> Column(panel.padding(horizontal = 18.dp, vertical = 16.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween) {
                HeroEyebrow(eyebrow)
                Text("///", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black,
                    color = MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { HeroTitle(title); HeroKernel(kernelLine) }
                Spacer(Modifier.width(12.dp))
                HeroEmblem(70.dp, MaterialTheme.shapes.large)
            }
            Spacer(Modifier.height(14.dp))
            Box(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.primary.copy(alpha = .12f))
                .padding(horizontal = 10.dp, vertical = 8.dp)) {
                HeroStatuses(statusPill, statusColor, modePill)
            }
            Spacer(Modifier.height(9.dp))
            HeroMeta(metaLine)
        }
        ManagerStyle.IOS_GLASS -> Column(panel.padding(horizontal = 22.dp, vertical = 21.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            HeroEyebrow(eyebrow)
            Spacer(Modifier.height(12.dp))
            HeroEmblem(68.dp, CircleShape)
            Spacer(Modifier.height(10.dp))
            HeroTitle(title, centered = true)
            HeroKernel(kernelLine, centered = true)
            Spacer(Modifier.height(12.dp))
            HeroStatuses(statusPill, statusColor, modePill, centered = true)
            Spacer(Modifier.height(12.dp))
            HorizontalDivider(thickness = .7.dp, color = glass.divider)
            Spacer(Modifier.height(8.dp))
            HeroMeta(metaLine, centered = true)
        }
        ManagerStyle.NEON -> Column(panel.padding(horizontal = 18.dp, vertical = 18.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                HeroEmblem(58.dp, MaterialTheme.shapes.large)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    HeroEyebrow(eyebrow)
                    Spacer(Modifier.height(5.dp))
                    HeroTitle(title)
                }
            }
            Spacer(Modifier.height(14.dp))
            HeroKernel(kernelLine)
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium)
                .background(Brush.horizontalGradient(listOf(MaterialTheme.colorScheme.primary.copy(alpha = .18f),
                    MaterialTheme.colorScheme.tertiary.copy(alpha = .08f))))
                .padding(horizontal = 10.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                HeroStatuses(statusPill, statusColor, modePill)
            }
            Spacer(Modifier.height(9.dp))
            HeroMeta(metaLine)
        }
    }
}

@Composable
private fun HeroEmblem(size: Dp, shape: Shape) {
    Image(painter = painterResource(R.drawable.ic_synthetica_emblem), contentDescription = null,
        contentScale = ContentScale.Crop, modifier = Modifier.size(size).clip(shape)
            .border(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = .70f), shape))
}

@Composable
private fun HeroEyebrow(value: String) {
    Text(value.uppercase(), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary, letterSpacing = 1.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
}

@Composable
private fun HeroTitle(value: String, centered: Boolean = false) {
    Text(value, modifier = if (centered) Modifier.fillMaxWidth() else Modifier,
        textAlign = if (centered) TextAlign.Center else TextAlign.Start,
        style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurface, maxLines = 2, overflow = TextOverflow.Ellipsis)
}

@Composable
private fun HeroKernel(value: String, centered: Boolean = false) {
    if (value.isNotBlank()) {
        Spacer(Modifier.height(4.dp))
        Text(value, modifier = if (centered) Modifier.fillMaxWidth() else Modifier,
            textAlign = if (centered) TextAlign.Center else TextAlign.Start,
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun HeroMeta(value: String, centered: Boolean = false) {
    Text(value, modifier = if (centered) Modifier.fillMaxWidth() else Modifier,
        textAlign = if (centered) TextAlign.Center else TextAlign.Start,
        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        maxLines = 2, overflow = TextOverflow.Ellipsis)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HeroStatuses(status: String, statusColor: Color, mode: String?, centered: Boolean = false) {
    FlowRow(modifier = if (centered) Modifier.fillMaxWidth() else Modifier,
        horizontalArrangement = if (centered) Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally) else Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp), maxItemsInEachRow = 2) {
        IosPill(text = status, color = statusColor)
        if (!mode.isNullOrBlank()) IosPill(text = mode, color = MaterialTheme.colorScheme.primary)
    }
}
