package net.pure.manager.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.os.Build
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
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
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun GridCell(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: String,
    onClick: () -> Unit,
    onLongClick: (() -> Unit)? = null,
    selected: Boolean = false,
    thumbnailOf: String? = null,
) {
    val p = spec.palette
    Column(
        Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(
                if (selected) spec.palette.accent.copy(alpha = 0.16f) else Color.Transparent,
            )
            .combinedClickable(
                onClick = onClick,
                onLongClick = onLongClick,
            )
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
                val thumb = if (thumbnailOf != null) rememberThumbnail(thumbnailOf, 160) else null
                if (thumb != null) {
                    Image(
                        bitmap = thumb.asImageBitmap(),
                        contentDescription = title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxWidth().height(70.dp),
                    )
                } else {
                    Text(
                        glyph,
                        style = MaterialTheme.typography.titleLarge,
                        color = p.accent,
                    )
                }
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


/**
 * A small bitmap for an image or video, or null while it loads or if it cannot.
 *
 * Two things make this worth writing carefully:
 *
 *  - Decoding at full resolution throws a 12 MP photo into memory to draw 70 dp.
 *    `inSampleSize` is computed from the target size first, which is the difference
 *    between a smooth grid and an app that dies on a folder of camera photos.
 *  - A SAF document is not a `File`, so it goes through `ContentResolver`, which can
 *    make a sized thumbnail from Android 10 up. Below that and for anything the
 *    resolver cannot render, the answer is null and the glyph shows: a missing
 *    thumbnail is a smaller lie than a broken image.
 */
@Composable
private fun rememberThumbnail(path: String, targetPx: Int): Bitmap? {
    val context = LocalContext.current
    var bitmap by remember(path, targetPx) { mutableStateOf<Bitmap?>(null) }

    LaunchedEffect(path, targetPx) {
        bitmap = withContext(Dispatchers.IO) {
            runCatching { loadThumbnail(context, path, targetPx) }.getOrNull()
        }
    }
    return bitmap
}

private fun loadThumbnail(
    context: android.content.Context,
    path: String,
    targetPx: Int,
): Bitmap? {
    if (path.startsWith("content://")) {
        // SAF documents: the content resolver can produce a thumbnail for images and
        // audio on Android 10+, honouring the requested size. Decoding the stream
        // directly would pull a full-resolution photo into memory to fill 70 dp.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        return runCatching {
            context.contentResolver.loadThumbnail(
                android.net.Uri.parse(path),
                android.util.Size(targetPx, targetPx),
                null,
            )
        }.getOrNull()
    }

    val file = java.io.File(path)
    if (!file.isFile) return null

    // Video: a frame from one second in, which is usually past the black start.
    if (net.pure.manager.fs.Support.mimeFor(file.name).startsWith("video/")) {
        return runCatching {
            val retriever = MediaMetadataRetriever()
            try {
                retriever.setDataSource(file.absolutePath)
                retriever.getFrameAtTime(1_000_000, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
            } finally {
                retriever.release()
            }
        }.getOrNull()
    }

    // Image: decode bounds only, then decode again at a sample size that lands near
    // the target. A 12 MP photo is about 36 MB as a full bitmap.
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.absolutePath, bounds)
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
    var sample = 1
    while (bounds.outWidth / (sample * 2) >= targetPx && bounds.outHeight / (sample * 2) >= targetPx) {
        sample *= 2
    }
    val opts = BitmapFactory.Options().apply { inSampleSize = sample }
    return BitmapFactory.decodeFile(file.absolutePath, opts)
}

/** The single-column list from the reference's list view: icon, name, chevron. */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun ListRow(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: String,
    showChevron: Boolean,
    onClick: () -> Unit,
    onLongClick: (() -> Unit)? = null,
    selected: Boolean = false,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .background(
                if (selected) p.accent.copy(alpha = 0.16f) else Color.Transparent,
            )
            .combinedClickable(
                onClick = onClick,
                onLongClick = onLongClick,
            )
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
