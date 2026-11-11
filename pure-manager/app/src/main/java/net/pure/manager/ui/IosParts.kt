package net.pure.manager.ui

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.PureThemeSpec

/**
 * The blue iOS folder shape from the reference screenshots, drawn as two paths.
 *
 * The stock Android folder icon is a Material glyph and reads as Android no matter
 * which palette is around it. This is deliberately not a Material icon: it is the
 * back tab plus the rounded body, filled with the theme accent, so a folder looks
 * like a folder in the gallery the owner pointed at.
 */
@Composable
fun IosFolder(
    size: Float,
    modifier: Modifier = Modifier,
    accent: Color = LocalPureSpec.current.palette.accent,
) {
    Box(
        modifier
            .size(size.dp)
            .drawBehind {
                val w = size.dp.toPx()
                val bodyTop = h(w, 0.26f)
                val radius = h(w, 0.11f)
                // Back tab, slightly darker so the two halves read as depth.
                drawRoundRect(
                    color = accent.copy(alpha = 0.78f),
                    topLeft = androidx.compose.ui.geometry.Offset(0f, h(w, 0.12f)),
                    size = Size(w * 0.46f, bodyTop - h(w, 0.02f)),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(radius * 0.8f),
                )
                // Body.
                drawRoundRect(
                    color = accent,
                    topLeft = androidx.compose.ui.geometry.Offset(0f, bodyTop),
                    size = Size(w, w - bodyTop),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(radius),
                )
            },
    )
}

private fun h(w: Float, fraction: Float) = w * fraction

/** A grid cell: folder or file, name underneath, item count in grey. */
@Composable
fun GridCell(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: String,
    onClick: () -> Unit,
) {
    val p = spec.palette
    Column(
        Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp, horizontal = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (isFolder) {
            IosFolder(size = 76f)
        } else {
            Box(
                Modifier
                    .size(70.dp)
                    .clip(RoundedCornerShape((spec.cornerDp * 0.8f).dp))
                    .background(p.surfaceVariant)
                    .border(0.5.dp, p.separator, RoundedCornerShape((spec.cornerDp * 0.8f).dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    glyph,
                    style = MaterialTheme.typography.titleLarge,
                    color = p.accent,
                )
            }
        }
        Spacer(Modifier.height(7.dp))
        Text(
            title,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Normal,
            color = p.onBackground,
            maxLines = 2,
        )
        if (subtitle != null) {
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = p.onSurfaceVariant,
            )
        }
    }
}

/** The single-column list from the reference's list view: icon, name, chevron. */
@Composable
fun ListRow(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: String,
    showChevron: Boolean,
    onClick: () -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (isFolder) {
            IosFolder(size = 32f)
        } else {
            Box(
                Modifier
                    .size(30.dp)
                    .clip(RoundedCornerShape((spec.cornerDp * 0.6f).dp))
                    .background(p.surfaceVariant),
                contentAlignment = Alignment.Center,
            ) {
                Text(glyph, style = MaterialTheme.typography.labelMedium, color = p.accent)
            }
        }
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                color = p.onBackground,
            )
            if (subtitle != null) {
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        }
        if (showChevron) {
            Text(
                "\u203A",
                style = MaterialTheme.typography.titleLarge,
                color = p.onSurfaceVariant,
            )
        }
    }
    // Hairline inset past the icon, the way iOS separates rows inside a card.
    Box(
        Modifier
            .fillMaxWidth()
            .padding(start = 58.dp, end = 14.dp)
            .height(0.5.dp)
            .background(spec.palette.separator),
    )
}

/** Rounded card that iOS groups rows into, on top of the grey page background. */
@Composable
fun GroupCard(spec: PureThemeSpec, content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp + 2).dp))
            .background(spec.palette.surface),
    ) { content() }
}

/** Grey search field, as in every one of the reference screenshots. */
@Composable
fun SearchField(
    spec: PureThemeSpec,
    value: String,
    onValueChange: (String) -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp * 0.7f).dp))
            .background(p.surfaceVariant)
            .padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("\u2315", style = MaterialTheme.typography.titleMedium, color = p.onSurfaceVariant)
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) {
                Text(
                    "Cari",
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onSurfaceVariant,
                )
            } else {
                Text(
                    value,
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onBackground,
                )
            }
        }
        if (value.isNotEmpty()) {
            Box(
                Modifier
                    .size(17.dp)
                    .clip(CircleShape)
                    .background(p.onSurfaceVariant.copy(alpha = 0.35f))
                    .clickable { onValueChange("") },
                contentAlignment = Alignment.Center,
            ) {
                Text("\u00D7", style = MaterialTheme.typography.labelSmall, color = p.surface)
            }
        }
    }
}

/** Circular toolbar button used for sort and view toggles. */
@Composable
fun ToolButton(glyph: String, active: Boolean, onClick: () -> Unit) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    Box(
        Modifier
            .size(38.dp)
            .clip(RoundedCornerShape((spec.cornerDp * 0.6f).dp))
            .background(if (active) p.accent else Color.Transparent)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            glyph,
            style = MaterialTheme.typography.titleMedium,
            color = if (active) p.onAccent else p.accent,
        )
    }
}
