package net.pure.manager.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.pure.manager.fs.FileEntry
import net.pure.manager.media.AudioPlayer
import net.pure.manager.media.MediaKind
import net.pure.manager.media.ZoomState
import net.pure.manager.media.clampZoom
import net.pure.manager.media.doubleTapZoomState
import net.pure.manager.media.formatClock
import net.pure.manager.media.nextIndex
import net.pure.manager.media.previousIndex
import net.pure.manager.media.previousRestartsInsteadOfGoingBack
import net.pure.manager.media.progressFraction
import net.pure.manager.media.shownPosition
import net.pure.manager.media.titleOf
import net.pure.manager.theme.PureThemeSpec

/**
 * A photo, as large as the screen allows.
 *
 * Android can already open an image in any gallery app, and the browser keeps that
 * route. This exists for the same reason the document viewer does: a file manager
 * that hands every file away is a folder tree, and the owner asked for the app to be
 * able to look at its own files.
 *
 * Zoom is clamped so a pinch cannot throw the picture off screen, and double-tap
 * toggles between fit and 2.5x. Both rules are arithmetic in `media/Timeline.kt`
 * where a test can reach them.
 */
@Composable
fun ImageViewer(
    spec: PureThemeSpec,
    entry: FileEntry,
    onClose: () -> Unit,
) {
    val p = spec.palette
    val config = LocalConfiguration.current
    var bitmap by remember(entry.path) { mutableStateOf<Bitmap?>(null) }
    var error by remember(entry.path) { mutableStateOf<String?>(null) }
    var zoom by remember(entry.path) { mutableStateOf(ZoomState()) }

    LaunchedEffect(entry.path) {
        val result = withContext(Dispatchers.IO) {
            runCatching {
                // Decoded at screen size, not at file size: a 48 MP photo decoded
                // whole is 190 MB of heap and an OutOfMemoryError on a 3 GB phone.
                decodeSampled(File(entry.path), config.screenWidthDp * 2)
            }
        }
        result.onSuccess { bitmap = it }
            .onFailure { error = it.message ?: "Gambar tidak bisa dibuka" }
    }

    Column(Modifier.fillMaxSize()) {
        Header(spec, entry.name, onClose)
        Text(
            "Cubit untuk memperbesar, ketuk dua kali untuk pas layar. " +
                "Gambar tidak bisa diedit atau diputar sebagai animasi.",
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
            modifier = Modifier.padding(vertical = 4.dp),
        )
        val bmp = bitmap
        when {
            error != null -> MessageCard(spec, "Tidak bisa dibuka", error!!)
            bmp == null -> Box(Modifier.fillMaxWidth().weight(1f), Alignment.Center) {
                Text("Membuka\u2026", style = MaterialTheme.typography.bodyMedium, color = p.onSurfaceVariant)
            }
            else -> Box(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .background(Color.Black)
                    .pointerInput(bmp) {
                        detectTransformGestures { _, pan, gestureZoom, _ ->
                            val vw = size.width.toFloat()
                            val vh = size.height.toFloat()
                            zoom = clampZoom(
                                zoom.copy(
                                    scale = zoom.scale * gestureZoom,
                                    offsetX = zoom.offsetX + pan.x,
                                    offsetY = zoom.offsetY + pan.y,
                                ),
                                vw, vh,
                            )
                        }
                    }
                    .clickable {
                        zoom = clampZoom(
                            zoom.copy(scale = doubleTapZoomState(zoom.scale)),
                            config.screenWidthDp * 2f,
                            config.screenHeightDp * 2f,
                        )
                    },
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    bitmap = bmp.asImageBitmap(),
                    contentDescription = entry.name,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .fillMaxSize()
                        .graphicsLayer(
                            scaleX = zoom.scale,
                            scaleY = zoom.scale,
                            translationX = zoom.offsetX,
                            translationY = zoom.offsetY,
                        ),
                )
            }
        }
        Text(
            "${bmp?.width ?: 0} \u00d7 ${bmp?.height ?: 0} piksel \u00b7 ${formatSizeForViewer(entry.sizeBytes)}",
            style = MaterialTheme.typography.labelSmall,
            color = p.onSurfaceVariant,
            modifier = Modifier.padding(vertical = 6.dp),
        )
    }
}

/**
 * An audio file, with the folder's other audio files as its playlist.
 *
 * `MediaPlayer` decodes what the phone can decode; there is no tag reader, so the
 * title is the file name without its extension and the screen does not pretend to
 * know the artist. The playlist is the folder, which is what a file manager means
 * by "next song".
 */
@Composable
fun AudioScreen(
    spec: PureThemeSpec,
    entry: FileEntry,
    playlist: List<FileEntry>,
    onClose: () -> Unit,
) {
    val p = spec.palette
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val player = remember { AudioPlayer(context) }
    val audio = remember(playlist) {
        playlist.filter { !it.isDirectory && MediaKind.of(it.extension) == MediaKind.AUDIO }
    }
    var index by remember { mutableStateOf(audio.indexOfFirst { it.path == entry.path }.coerceAtLeast(0)) }
    var drag by remember { mutableStateOf<Float?>(null) }
    var repeat by remember { mutableStateOf(false) }
    var shuffle by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        player.attach(scope)
        player.onCompleted = {
            index = nextIndex(index, audio.size, repeat, shuffle, seed = index + 7)
        }
        onDispose { player.release() }
    }

    // Opening a new index replaces the player's source. `LaunchedEffect(index)`
    // rather than a click handler so that finishing a track advances the same way a
    // tap does.
    LaunchedEffect(index, audio.size) {
        val item = audio.getOrNull(index) ?: return@LaunchedEffect
        player.open(item.path, autoPlay = true)
    }

    val state by player.state.collectAsState()

    Column(Modifier.fillMaxSize()) {
        Header(spec, titleOf(entry.name), onClose)
        Spacer(Modifier.height(6.dp))

        Box(
            Modifier
                .fillMaxWidth()
                .weight(1f)
                .clip(RoundedCornerShape(spec.cornerDp.dp))
                .background(p.surface),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    titleOf(audio.getOrNull(index)?.name ?: entry.name),
                    style = MaterialTheme.typography.titleLarge,
                    color = p.onBackground,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "Audio \u00b7 ${formatSizeForViewer(audio.getOrNull(index)?.sizeBytes ?: entry.sizeBytes)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
                Spacer(Modifier.height(16.dp))
                Text(
                    "${index + 1} / ${audio.size.coerceAtLeast(1)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = p.onSurfaceVariant,
                )
                state.error?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall, color = p.accent, textAlign = TextAlign.Center)
                }
            }
        }

        Spacer(Modifier.height(10.dp))

        val position = shownPosition(state.positionMs, drag?.toLong(), state.durationMs)
        Slider(
            value = progressFraction(position, state.durationMs),
            onValueChange = { drag = (it * state.durationMs).toLong().toFloat() },
            onValueChangeFinished = {
                drag?.let { player.seekTo(it.toLong()) }
                drag = null
            },
            colors = SliderDefaults.colors(
                thumbColor = p.accent,
                activeTrackColor = p.accent,
                inactiveTrackColor = p.surfaceVariant,
            ),
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(formatClock(position), style = MaterialTheme.typography.labelSmall, color = p.onSurfaceVariant)
            Text(formatClock(state.durationMs), style = MaterialTheme.typography.labelSmall, color = p.onSurfaceVariant)
        }

        Row(
            Modifier.fillMaxWidth().padding(vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MediaButton(PureIcons.Previous, enabled = audio.size > 1) {
                index = if (previousRestartsInsteadOfGoingBack(state.positionMs) && index in audio.indices) {
                    index
                } else {
                    previousIndex(index, audio.size, repeat, shuffle, seed = index + 3)
                }
            }
            MediaButton(PureIcons.Rewind, enabled = state.prepared) { player.seekBy(-10_000) }
            MediaButton(
                if (state.playing) PureIcons.Pause else PureIcons.Play,
                enabled = state.prepared,
            ) { player.toggle() }
            MediaButton(PureIcons.Forward, enabled = state.prepared) { player.seekBy(10_000) }
            MediaButton(PureIcons.Next, enabled = audio.size > 1) {
                index = nextIndex(index, audio.size, repeat, shuffle, seed = index + 7)
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(bottom = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            SmallToggle("Ulangi", repeat) { repeat = !repeat }
            SmallToggle("Acak", shuffle) { shuffle = !shuffle }
        }
        Text(
            "Diputar dengan pemutar bawaan Android. Tidak membaca tag ID3, jadi judul " +
                "adalah nama berkas. Format yang tidak didukung Android tidak bisa diputar.",
            style = MaterialTheme.typography.labelSmall,
            color = p.onSurfaceVariant,
        )
    }
}

/**
 * A video file, played through `VideoView`.
 *
 * `VideoView` is the platform's own surface plus a `MediaPlayer`; it costs no
 * dependency and plays everything the phone can decode. What it does not give is a
 * clean seek bar or a fullscreen toggle, so both are drawn here.
 */
@Composable
fun VideoScreen(
    spec: PureThemeSpec,
    entry: FileEntry,
    onClose: () -> Unit,
) {
    val p = spec.palette
    val context = LocalContext.current
    var error by remember(entry.path) { mutableStateOf<String?>(null) }
    var position by remember { mutableLongStateOf(0L) }
    var duration by remember { mutableLongStateOf(-1L) }
    var playing by remember { mutableStateOf(true) }
    var drag by remember { mutableStateOf<Float?>(null) }

    Column(Modifier.fillMaxSize()) {
        Header(spec, entry.name, onClose)
        Spacer(Modifier.height(6.dp))

        // The view is created once and kept; recreating it on every recomposition is
        // how a video restarts from zero when the user drags the seek bar.
        val video = remember(entry.path) { android.widget.VideoView(context) }
        DisposableEffect(entry.path) {
            video.setVideoURI(android.net.Uri.fromFile(File(entry.path)))
            video.setOnPreparedListener { mp ->
                duration = mp.duration.toLong()
                mp.isLooping = false
                video.start()
            }
            video.setOnErrorListener { _, what, extra ->
                error = "Tidak bisa memutar video ini (kode $what/$extra)"
                true
            }
            video.setOnCompletionListener { playing = false }
            onDispose {
                runCatching { video.stopPlayback() }
                runCatching { video.suspend() }
            }
        }

        androidx.compose.ui.viewinterop.AndroidView(
            factory = { video },
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .clip(RoundedCornerShape(spec.cornerDp.dp))
                .background(Color.Black),
        )

        LaunchedEffect(playing) {
            while (playing) {
                position = runCatching { video.currentPosition.toLong() }.getOrDefault(0L)
                kotlinx.coroutines.delay(250)
            }
        }

        error?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = p.accent, modifier = Modifier.padding(6.dp))
        }

        val shown = shownPosition(position, drag?.toLong(), duration)
        Slider(
            value = progressFraction(shown, duration),
            onValueChange = { drag = (it * duration).toLong().toFloat() },
            onValueChangeFinished = {
                drag?.let { video.seekTo(it.toInt()) }
                drag = null
            },
            colors = SliderDefaults.colors(
                thumbColor = p.accent,
                activeTrackColor = p.accent,
                inactiveTrackColor = p.surfaceVariant,
            ),
        )
        Row(
            Modifier.fillMaxWidth().padding(bottom = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(formatClock(shown), style = MaterialTheme.typography.labelSmall, color = p.onSurfaceVariant)
            MediaButton(if (playing) PureIcons.Pause else PureIcons.Play, enabled = true) {
                if (playing) {
                    video.pause()
                    playing = false
                } else {
                    video.start()
                    playing = true
                }
            }
            MediaButton(PureIcons.Rewind, enabled = true) {
                video.seekTo((shown - 10_000).toInt().coerceAtLeast(0))
            }
            MediaButton("+10", enabled = true) { video.seekTo((shown + 10_000).coerceAtMost(duration).toInt()) }
            Text(formatClock(duration), style = MaterialTheme.typography.labelSmall, color = p.onSurfaceVariant)
        }
        Text(
            "Diputar dengan VideoView bawaan Android. Subtitle tidak didukung.",
            style = MaterialTheme.typography.labelSmall,
            color = p.onSurfaceVariant,
        )
    }
}

/** Back row shared by the three screens; the editor has its own because it guards unsaved work. */
@Composable
private fun Header(spec: PureThemeSpec, title: String, onClose: () -> Unit) {
    val p = spec.palette
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            "\u2039 Kembali",
            style = MaterialTheme.typography.bodyLarge,
            color = p.accent,
            modifier = Modifier
                .clip(RoundedCornerShape(spec.cornerDp.dp))
                .clickable(onClick = onClose)
                .padding(horizontal = 8.dp, vertical = 6.dp),
        )
        Spacer(Modifier.width(6.dp))
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            color = p.onBackground,
            modifier = Modifier.weight(1f),
            maxLines = 1,
        )
    }
}

@Composable
private fun MediaButton(icon: ImageVector, enabled: Boolean, onClick: () -> Unit) {
    val spec = net.pure.manager.theme.LocalPureSpec.current
    val p = spec.palette
    Box(
        Modifier
            .size(52.dp)
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(if (enabled) p.surfaceVariant else Color.Transparent)
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = if (enabled) p.onBackground else p.onSurfaceVariant.copy(alpha = 0.4f),
            modifier = Modifier.size(24.dp),
        )
    }
}

@Composable
private fun SmallToggle(label: String, on: Boolean, onClick: () -> Unit) {
    val spec = net.pure.manager.theme.LocalPureSpec.current
    val p = spec.palette
    Text(
        if (on) "$label: ya" else "$label: tidak",
        style = MaterialTheme.typography.labelSmall,
        color = if (on) p.accent else p.onSurfaceVariant,
        modifier = Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(if (on) p.surfaceVariant else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 5.dp),
    )
}

/**
 * `BitmapFactory` with `inSampleSize`, so a large photo is decoded at display size.
 *
 * Setting `inJustDecodeBounds` first is what makes this a thumbnail rather than a
 * gamble: decoding at full size and then scaling is the version that dies with
 * `OutOfMemoryError` on the owner's phone but not on a test device.
 */
internal fun decodeSampled(file: File, targetWidthPx: Int): Bitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.absolutePath, bounds)
    if (bounds.outWidth <= 0) return null
    var sample = 1
    while (bounds.outWidth / (sample * 2) >= targetWidthPx) sample *= 2
    val opts = BitmapFactory.Options().apply { inSampleSize = sample }
    val decoded = BitmapFactory.decodeFile(file.absolutePath, opts) ?: return null
    // Rotation: a portrait photo from most Android cameras is stored landscape with
    // an orientation tag, and ignoring it shows every photo sideways.
    //
    // `android.media.ExifInterface` was removed from the public SDK, and
    // `androidx.exifinterface` is a dependency this project does not carry. Android's
    // own `MediaMetadataRetriever` reports the same tag for images on our minimum
    // (Android 10) and is part of the platform, so it costs nothing.
    val degrees = runCatching {
        val retriever = android.media.MediaMetadataRetriever()
        try {
            retriever.setDataSource(file.absolutePath)
            when (retriever.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull() ?: 0) {
                90 -> 90f
                180 -> 180f
                270 -> 270f
                else -> 0f
            }
        } finally {
            runCatching { retriever.release() }
        }
    }.getOrDefault(0f)
    if (degrees == 0f) return decoded
    val matrix = Matrix().apply { postRotate(degrees) }
    return Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true)
}

/** `formatSize`, without importing the browser's copy into three screens. */
internal fun formatSizeForViewer(bytes: Long): String = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1024L * 1024 -> "${bytes / 1024} KB"
    bytes < 1024L * 1024 * 1024 -> String.format(java.util.Locale.US, "%.1f MB", bytes / (1024.0 * 1024))
    else -> String.format(java.util.Locale.US, "%.2f GB", bytes / (1024.0 * 1024 * 1024))
}
