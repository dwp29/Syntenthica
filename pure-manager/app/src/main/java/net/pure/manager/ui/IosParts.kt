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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.PureThemeSpec

/**
 * The blue iOS folder shape from the reference screenshots, drawn as two paths.
 *
 * The stock Android folder icon is a Material glyph and reads as Android no matter
 * which palette is around it. This is deliberately not a Material icon: it is the
 * back tab plus the rounded body, filled with the theme accent, so a folder looks
 * like a folder in the gallery the owner pointed at.
 *
 * [tint] exists because Apple's Files does not draw every folder in the app's
 * accent colour: each folder keeps a colour of its own, and that colour is the
 * dot next to its name. Passing null keeps the theme accent.
 */
@Composable
fun IosFolder(
    size: Float,
    modifier: Modifier = Modifier,
    accent: Color = LocalPureSpec.current.palette.accent,
    tint: Color? = null,
) {
    val fill = tint ?: accent
    Box(
        modifier
            .size(size.dp)
            .drawBehind {
                val w = size.dp.toPx()
                val bodyTop = w * 0.26f
                val radius = w * 0.11f
                // Back tab, slightly darker so the two halves read as depth.
                drawRoundRect(
                    color = fill.copy(alpha = 0.72f),
                    topLeft = Offset(0f, w * 0.10f),
                    size = Size(w * 0.48f, bodyTop - w * 0.02f),
                    cornerRadius = CornerRadius(radius * 0.8f),
                )
                // Body.
                drawRoundRect(
                    color = fill,
                    topLeft = Offset(0f, bodyTop),
                    size = Size(w, w - bodyTop),
                    cornerRadius = CornerRadius(radius),
                )
            },
    )
}

/**
 * Colour for a folder, chosen from its name so it never shuffles.
 *
 * In Files a folder's colour is set by the user. Here there is no per-folder
 * metadata to store yet, so the name picks from Apple's folder colours: the same
 * name always gives the same colour, and two folders side by side almost never
 * share one. Hashing the name means a rename recolours, which is the honest
 * trade against writing colour state to disk for every folder on the device.
 */
fun folderTint(name: String): Color {
    val palette = listOf(
        Color(0xFF1E88E5), // blue, the default in Files
        Color(0xFF30B0C7), // teal
        Color(0xFF34C759), // green
        Color(0xFFFFCC00), // yellow
        Color(0xFFFF9500), // orange
        Color(0xFFFF3B30), // red
        Color(0xFFAF52DE), // purple
        Color(0xFFFF2D55), // pink
    )
    var h = 7
    for (c in name) h = (h * 31 + c.code) and 0x7FFFFFF
    return palette[h % palette.size]
}

/**
 * A grid cell, laid out the way Files lays one out.
 *
 * Three details carry that resemblance, and none of them is a colour:
 *
 *  - The name sits under the icon and is centred, two lines maximum, with the
 *    size or item count in grey under it. A cell in a card would read as Android.
 *  - Folders get a colour dot before the name. It is the cheapest part of the
 *    look and the first thing that goes missing when someone copies the layout
 *    by eye.
 *  - The icon is square with a soft corner radius, not a circle and not a
 *    Material glyph tile.
 */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun GridCell(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: ImageVector,
    onClick: () -> Unit,
    onLongClick: (() -> Unit)? = null,
    selected: Boolean = false,
    thumbnailOf: String? = null,
) {
    val p = spec.palette
    val tint = if (isFolder) folderTint(title) else null
    Column(
        Modifier
            .clip(RoundedCornerShape((spec.cornerDp * 0.75f).dp))
            .background(
                if (selected) p.accent.copy(alpha = 0.16f) else Color.Transparent,
            )
            .combinedClickable(
                onClick = onClick,
                onLongClick = onLongClick,
            )
            .padding(vertical = 6.dp, horizontal = 2.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (isFolder) {
            IosFolder(size = 72f, tint = tint)
        } else {
            Box(
                Modifier
                    .size(72.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(p.surfaceVariant)
                    .border(0.5.dp, p.separator, RoundedCornerShape(12.dp)),
                contentAlignment = Alignment.Center,
            ) {
                val thumb = if (thumbnailOf != null) rememberThumbnail(thumbnailOf, 160) else null
                if (thumb != null) {
                    // Fill the tile and let the clip do the rounding: an Image
                    // with a fixed height inside a padded Box left gaps at the
                    // edges on some devices.
                    Image(
                        bitmap = thumb.asImageBitmap(),
                        contentDescription = title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                } else {
                    // The file's icon at 30 dp, in the type's accent. It used to be a
                    // text glyph in the body font, which put a hollow square where a
                    // picture belonged and an envelope where a gear belonged.
                    Icon(
                        imageVector = glyph,
                        contentDescription = null,
                        tint = p.accent,
                        modifier = Modifier.size(30.dp),
                    )
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            if (tint != null) {
                Box(
                    Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(tint),
                )
                Spacer(Modifier.size(4.dp))
            }
            Text(
                title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Normal,
                color = p.onBackground,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                textAlign = TextAlign.Center,
            )
        }
        if (subtitle != null) {
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = p.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/**
 * A small bitmap for an image or video, or null while it loads or if it cannot.
 *
 * Two things make this worth writing carefully:
 *
 *  - Decoding at full resolution throws a 12 MP photo into memory to draw 72 dp.
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
        // directly would pull a full-resolution photo into memory to fill 72 dp.
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

/**
 * A row in the list view: coloured folder, name, size, chevron.
 *
 * `flush` drops the trailing hairline for the last row of a group, because a line
 * hanging under the final row inside a rounded card is the single clearest sign
 * that a list was assembled without looking at the edges.
 */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun ListRow(
    spec: PureThemeSpec,
    title: String,
    subtitle: String?,
    isFolder: Boolean,
    glyph: ImageVector,
    showChevron: Boolean,
    onClick: () -> Unit,
    onLongClick: (() -> Unit)? = null,
    selected: Boolean = false,
    flush: Boolean = false,
    thumbnailOf: String? = null,
) {
    val p = spec.palette
    val tint = if (isFolder) folderTint(title) else null
    Column(Modifier.fillMaxWidth()) {
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
                .padding(horizontal = 14.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val thumb = if (thumbnailOf != null) rememberThumbnail(thumbnailOf, 120) else null
            when {
                isFolder -> IosFolder(size = 34f, tint = tint)
                thumb != null -> Image(
                    bitmap = thumb.asImageBitmap(),
                    contentDescription = title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(34.dp)
                        .clip(RoundedCornerShape(6.dp)),
                )
                else -> Box(
                    Modifier
                        .size(34.dp)
                        .clip(RoundedCornerShape(7.dp))
                        .background(p.surfaceVariant),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = glyph,
                        contentDescription = null,
                        tint = p.accent,
                        modifier = Modifier.size(19.dp),
                    )
                }
            }
            // Name on top, size (or item count and date) underneath, both left
            // aligned in one column, chevron at the right edge. The earlier version
            // put the size on the same line as the name, which is not what the
            // reference does and it truncated long Indonesian file names.
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onBackground,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (subtitle != null) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = p.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            if (showChevron) {
                Icon(
                    imageVector = PureIcons.Chevron,
                    contentDescription = null,
                    tint = p.onSurfaceVariant.copy(alpha = 0.55f),
                    modifier = Modifier.size(16.dp),
                )
            }
        }
        if (!flush) {
            // Hairline inset past the icon, the way iOS separates rows in a card.
            Box(
                Modifier
                    .fillMaxWidth()
                    .padding(start = 60.dp, end = 14.dp)
                    .height(0.5.dp)
                    .background(p.separator),
            )
        }
    }
}

/**
 * Rounded card that iOS groups rows into, on top of the page background.
 *
 * In Files only lists live in cards. The icon grid sits straight on the page,
 * which is why [GridCell] is never wrapped in one -- the version that wrapped it
 * looked like a settings screen with pictures in it.
 */
@Composable
fun GroupCard(spec: PureThemeSpec, content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp + 2).dp))
            .background(spec.palette.surface),
    ) { content() }
}

/**
 * The grey search field, with the magnifier, a speaker for the microphone and a
 * cancel affordance, in the order Files shows them.
 *
 * It is also the one place the browser's filter is typed, so `value` is a real
 * parameter rather than placeholder text.
 */
@Composable
fun SearchField(
    spec: PureThemeSpec,
    value: String,
    onValueChange: (String) -> Unit,
    onSearchDevice: () -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp * 0.7f).dp))
            .background(p.surfaceVariant)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Icon(
            imageVector = PureIcons.Search,
            contentDescription = null,
            tint = p.onSurfaceVariant,
            modifier = Modifier.size(18.dp),
        )
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
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (value.isNotEmpty()) {
            Box(
                Modifier
                    .size(18.dp)
                    .clip(CircleShape)
                    .background(p.onSurfaceVariant.copy(alpha = 0.35f))
                    .clickable { onValueChange("") },
                contentAlignment = Alignment.Center,
            ) {
                Text("\u00D7", style = MaterialTheme.typography.labelSmall, color = p.surface)
            }
        }
        // Files keeps a microphone here. There is no speech recogniser in this
        // build, so the glyph is a shortcut for "search the whole device" instead
        // of a control that does nothing: an empty search field with a magnifier
        // already means "find", and the owner asked for a file manager that finds
        // things, not for dictation.
        Icon(
            imageVector = PureIcons.Device,
            contentDescription = "Cari di seluruh perangkat",
            tint = p.onSurfaceVariant,
            modifier = Modifier
                .clip(CircleShape)
                .clickable(onClick = onSearchDevice)
                .padding(4.dp)
                .size(20.dp),
        )
    }
}

/** A round toolbar button, the shape Files uses for its ellipsis and view toggles. */
@Composable
fun ToolButton(
    glyph: ImageVector,
    active: Boolean,
    onClick: () -> Unit,
    tint: Color? = null,
) {
    val spec = LocalPureSpec.current
    val p = spec.palette
    val fg = tint ?: p.accent
    Box(
        Modifier
            .size(36.dp)
            .clip(CircleShape)
            .background(if (active) fg.copy(alpha = 0.16f) else Color.Transparent)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = glyph,
            contentDescription = null,
            tint = if (active) fg else p.onBackground,
            modifier = Modifier.size(21.dp),
        )
    }
}


