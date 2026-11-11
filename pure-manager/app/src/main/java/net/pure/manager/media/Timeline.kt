package net.pure.manager.media

/**
 * The arithmetic of playback, as plain Kotlin.
 *
 * A media player is mostly clock management, and clock management is where the bugs
 * live: a seek bar that snaps backwards while the user drags it, a "next track" that
 * chooses the track already playing, a timer that shows `-1:59` for a file that has
 * not reported its duration yet. None of that needs a device to be wrong, so none of
 * it lives in a composable.
 *
 * Everything here takes and returns milliseconds unless the name says otherwise.
 */

/** `m:ss`, or `h:mm:ss` past an hour. Negative and unknown durations show as `--:--`. */
fun formatClock(ms: Long): String {
    if (ms < 0 || ms == Long.MAX_VALUE) return "--:--"
    val total = ms / 1000
    val seconds = total % 60
    val minutes = (total / 60) % 60
    val hours = total / 3600
    return if (hours > 0) {
        "%d:%02d:%02d".format(hours, minutes, seconds)
    } else {
        "%d:%02d".format(minutes, seconds)
    }
}

/**
 * What a seek bar should show while the user is dragging it.
 *
 * Releasing the thumb has to survive the player's own position updates: the player
 * reports its old position for a frame or two after a seek, and a bar that believes
 * every update jumps backwards under the finger. [dragPositionMs] wins until the drag
 * ends, then [positionMs] takes over again.
 */
fun shownPosition(positionMs: Long, dragPositionMs: Long?, durationMs: Long): Long {
    val candidate = dragPositionMs ?: positionMs
    return candidate.coerceIn(0L, if (durationMs > 0) durationMs else 0L)
}

/** 0f..1f for the bar; 0 when the duration is unknown rather than NaN. */
fun progressFraction(positionMs: Long, durationMs: Long): Float {
    if (durationMs <= 0L) return 0f
    return (positionMs.toFloat() / durationMs.toFloat()).coerceIn(0f, 1f)
}

/**
 * The index "next" goes to.
 *
 * `repeat` wraps, otherwise the last track stays last instead of stopping on
 * silence. Shuffle picks a different track when there is more than one; with a
 * single track it picks that one, because refusing to play the only song is worse
 * than repeating it.
 */
fun nextIndex(current: Int, count: Int, repeat: Boolean, shuffle: Boolean, seed: Int = 0): Int {
    if (count <= 1) return 0
    if (shuffle) {
        // Deterministic so it can be tested: the caller passes a fresh seed per
        // press. The step is in 1..count-1, so the result differs from `current` by
        // construction rather than by luck -- a real `random` picks the playing track
        // a third of the time with three files, which reads as a dead button.
        //
        // `floorMod` rather than `%`: a negative seed or index would otherwise give
        // a negative result, and a negative index into a playlist is a crash.
        val step = Math.floorMod(seed, count - 1) + 1
        return Math.floorMod(current + step, count)
    }
    val candidate = current + 1
    return if (candidate < count) candidate else if (repeat) 0 else count - 1
}

/** The index "previous" goes to. Mirrors [nextIndex], including the shuffle rule. */
fun previousIndex(current: Int, count: Int, repeat: Boolean, shuffle: Boolean, seed: Int = 0): Int {
    if (count <= 1) return 0
    if (shuffle) {
        val step = Math.floorMod(seed, count - 1) + 1
        return Math.floorMod(current - step, count)
    }
    val candidate = current - 1
    return if (candidate >= 0) candidate else if (repeat) count - 1 else 0
}

/**
 * "Back to the start, or the previous track?" -- the rule every player uses.
 *
 * After three seconds, Previous restarts the current track; before that it goes to
 * the one before. Returning the position instead of the index keeps the decision
 * free of player state.
 */
fun previousRestartsInsteadOfGoingBack(positionMs: Long, thresholdMs: Long = 3_000L): Boolean =
    positionMs > thresholdMs

/**
 * The playlist a media screen shows: the files in the folder that this player can
 * play, in the order the browser already shows them.
 *
 * Deciding here rather than in the screen means "audio files" has one definition.
 * The extension list is the set Android's own decoders handle on the owner's phone;
 * a format outside it would open and fail, so it is not offered.
 */
enum class MediaKind(val extensions: Set<String>) {
    IMAGE(setOf("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif", "dng")),
    AUDIO(setOf("mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac", "mid", "midi", "amr", "weba")),
    VIDEO(setOf("mp4", "m4v", "mkv", "webm", "3gp", "avi", "mov", "ts")),
    ;

    companion object {
        fun of(extension: String): MediaKind? {
            val ext = extension.lowercase()
            return entries.firstOrNull { ext in it.extensions }
        }

        /** True for the file types the in-app players are offered for. */
        fun playable(extension: String): Boolean {
            val kind = of(extension) ?: return false
            return kind == AUDIO || kind == VIDEO
        }
    }
}

/**
 * A zoom/pan state for an image, kept as numbers so the gesture maths is testable.
 *
 * [offsetX]/[offsetY] are the translation in screen pixels; [scale] is 1 for "fit".
 * Clamping exists so a pinch-out cannot throw the image off screen and leave an empty
 * white rectangle with no way back -- which is the second-most-common bug in a photo
 * viewer after the zoom that flickers.
 */
data class ZoomState(val scale: Float = 1f, val offsetX: Float = 0f, val offsetY: Float = 0f)

fun clampZoom(
    state: ZoomState,
    viewportWidth: Float,
    viewportHeight: Float,
    minScale: Float = 1f,
    maxScale: Float = 8f,
): ZoomState {
    val scale = state.scale.coerceIn(minScale, maxScale)
    // The image fills the viewport at scale 1, so the overflow on each side is half
    // of what the zoom added. The first version wrote `maxX = 0f` here, which is
    // correct at fit scale and makes panning dead at every other scale: the picture
    // can be zoomed and then never moved.
    val maxX = (viewportWidth * (scale - 1f) / 2f).coerceAtLeast(0f)
    val maxY = (viewportHeight * (scale - 1f) / 2f).coerceAtLeast(0f)
    return state.copy(
        scale = scale,
        offsetX = state.offsetX.coerceIn(-maxX, maxX),
        offsetY = state.offsetY.coerceIn(-maxY, maxY),
    )
}

/**
 * Where a double-tap zooms to: 1 -> 2.5 -> 1.
 *
 * Toggling rather than accumulating means the gesture always returns to a known
 * state, so a user who taps twice is never stranded at 1.7x with no reset.
 */
fun doubleTapZoomState(current: Float, target: Float = 2.5f, fit: Float = 1f): Float =
    if (current > fit + 0.01f) fit else target
