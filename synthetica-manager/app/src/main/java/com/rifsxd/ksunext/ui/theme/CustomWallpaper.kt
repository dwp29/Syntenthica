package com.rifsxd.ksunext.ui.theme

import android.content.Context
import android.content.SharedPreferences
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import java.io.File

/**
 * User-chosen background image for the Manager.
 *
 * The Manager previously painted the same procedural canvas for every theme and gave no
 * way to use a picture of your own. This stores one imported image plus its two display
 * settings and exposes them to the rest of the UI.
 *
 * Robustness rules worth knowing before changing this file:
 *  - a wallpaper is optional; when absent, the original procedural theme canvas is used;
 *  - a corrupt or deleted file must fall back to the procedural canvas rather than crash,
 *    which is why decoding is guarded and the bitmap is re-validated on every load;
 *  - the image is copied into app-private storage, so revoking the source permission later
 *    does not break the background.
 */
object CustomWallpaper {
    private const val PREFS = "settings"
    private const val KEY_PATH = "wallpaper_path"
    private const val KEY_OPACITY = "wallpaper_opacity"
    private const val KEY_BLUR = "wallpaper_blur"

    /** Above this the cached bitmap is downsampled; a 4K phone wallpaper is wasteful to hold. */
    private const val MAX_DECODE_WIDTH = 1600

    private var prefs: SharedPreferences? = null

    /** Bumped whenever the wallpaper changes so composables recompute. */
    var revision by mutableIntStateOf(0)
        private set

    /** Decoded once and shared; null means "no usable wallpaper, paint the theme canvas". */
    var bitmap by mutableStateOf<Bitmap?>(null)
        private set

    /** 0.15..1.0. Kept low-biased because heavy backgrounds make text unreadable. */
    var opacity by mutableStateOf(0.55f)
        private set

    /** 0..24 dp of blur, so a photo cannot fight the interface text. */
    var blurDp by mutableStateOf(0f)
        private set

    val enabled: Boolean get() = bitmap != null

    fun init(context: Context) {
        if (prefs != null) return
        val p = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs = p
        opacity = p.getFloat(KEY_OPACITY, 0.55f).coerceIn(0.15f, 1f)
        blurDp = p.getFloat(KEY_BLUR, 0f).coerceIn(0f, 24f)
        bitmap = loadBitmap(context, p.getString(KEY_PATH, null))
        revision += 1
    }

    /** Copies [uri] into private storage and applies it. Returns false if it is not an image. */
    fun import(context: Context, uri: Uri): Boolean {
        val app = context.applicationContext
        val decoded = decode(app, uri) ?: return false
        val file = File(app.filesDir, "wallpaper_custom.img")
        val ok = runCatching {
            file.outputStream().use { out ->
                decoded.compress(Bitmap.CompressFormat.JPEG, 92, out)
            }
        }.isSuccess
        if (!ok) return false
        prefs?.edit()?.putString(KEY_PATH, file.absolutePath)?.apply()
        bitmap = decoded
        revision += 1
        return true
    }

    fun clear(context: Context) {
        File(context.applicationContext.filesDir, "wallpaper_custom.img").delete()
        prefs?.edit()?.remove(KEY_PATH)?.apply()
        bitmap = null
        revision += 1
    }

    fun setOpacity(context: Context, value: Float) {
        opacity = value.coerceIn(0.15f, 1f)
        prefs?.edit()?.putFloat(KEY_OPACITY, opacity)?.apply()
        revision += 1
    }

    fun setBlur(context: Context, value: Float) {
        blurDp = value.coerceIn(0f, 24f)
        prefs?.edit()?.putFloat(KEY_BLUR, blurDp)?.apply()
        revision += 1
    }

    private fun loadBitmap(context: Context, path: String?): Bitmap? {
        if (path.isNullOrBlank()) return null
        val file = File(path)
        if (!file.isFile || file.length() == 0L) return null
        return runCatching { BitmapFactory.decodeFile(path) }.getOrNull()
    }

    private fun decode(context: Context, uri: Uri): Bitmap? = runCatching {
        // First pass: bounds only, so a huge image is never fully allocated.
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        val w = bounds.outWidth
        if (w <= 0) return@runCatching null
        var sample = 1
        while (w / sample > MAX_DECODE_WIDTH) sample *= 2
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) }
    }.getOrNull()
}

/**
 * Paints the imported wallpaper behind the interface.
 *
 * A scrim sits between the picture and the content in both directions: without it a bright
 * photograph turns body text into an unreadable smear, which is the usual failure mode of
 * "custom background" features. The scrim is biased to the theme's own canvas colour so the
 * wallpaper still looks like it belongs to the active theme instead of fighting it.
 */
@Composable
fun CustomWallpaperLayer(modifier: Modifier = Modifier) {
    // Snapshot the object properties into locals: inside a draw lambda "CustomWallpaper.blurDp"
    // resolves against the Modifier receiver, not the object, and fails to compile.
    val image = CustomWallpaper.bitmap ?: return
    val alpha = CustomWallpaper.opacity
    val blur = CustomWallpaper.blurDp
    val glass = LocalGlassStyle.current
    val scrim = if (glass.isDark) Color.Black else Color.White
    Image(
        bitmap = image.asImageBitmap(),
        contentDescription = null,
        contentScale = ContentScale.Crop,
        alpha = alpha,
        modifier = modifier.fillMaxSize().blur(blur.dp),
    )
    Canvas(Modifier.fillMaxSize()) {
        drawRect(
            brush = Brush.verticalGradient(
                listOf(
                    glass.canvasBase.copy(alpha = 0.30f),
                    scrim.copy(alpha = if (glass.isDark) 0.28f else 0.22f),
                    glass.canvasBase.copy(alpha = 0.55f),
                ),
            ),
        )
    }
}
