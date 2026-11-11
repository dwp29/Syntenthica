package net.pure.manager.media

import android.content.Context
import android.media.MediaPlayer
import android.net.Uri
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * One audio file, played through the platform's `MediaPlayer`.
 *
 * No ExoPlayer: 1.5 MB of dependency for what a file manager needs is not a trade
 * worth making when `MediaPlayer` already decodes everything the phone can play. What
 * `MediaPlayer` lacks is a state machine that does not deadlock, so that is what this
 * class adds -- plus the discipline of releasing it, because a leaked `MediaPlayer`
 * keeps the audio focus and the phone stays silent for every other app.
 *
 * The position is polled while playing rather than pushed by a callback. A seek bar
 * needs a position every ~200 ms, `MediaPlayer` has no such callback on all versions,
 * and a poll that stops when playback does costs nothing.
 */
class AudioPlayer(private val context: Context) {

    data class State(
        val path: String? = null,
        val positionMs: Long = 0,
        val durationMs: Long = -1,
        val playing: Boolean = false,
        val error: String? = null,
        val prepared: Boolean = false,
    )

    private val _state = MutableStateFlow(State())
    val state: StateFlow<State> = _state

    private var player: MediaPlayer? = null
    private var ticker: Job? = null
    private var scope: CoroutineScope? = null

    /** The scope that owns the polling job; cancelled when the screen goes away. */
    fun attach(scope: CoroutineScope) {
        this.scope = scope
    }

    fun open(path: String, autoPlay: Boolean = true) {
        release()
        _state.value = State(path = path)
        val mp = MediaPlayer()
        player = mp
        try {
            mp.setDataSource(sourceFor(context, path))
            mp.setOnPreparedListener {
                _state.value = _state.value.copy(
                    prepared = true,
                    durationMs = it.duration.toLong(),
                    error = null,
                )
                if (autoPlay) play()
            }
            mp.setOnCompletionListener {
                _state.value = _state.value.copy(playing = false, positionMs = 0)
                stopTicker()
                onCompleted?.invoke()
            }
            mp.setOnErrorListener { _, what, extra ->
                _state.value = _state.value.copy(
                    playing = false,
                    error = "Tidak bisa memutar berkas ini (kode $what/$extra)",
                )
                false
            }
            mp.prepareAsync()
        } catch (e: Exception) {
            _state.value = _state.value.copy(error = describe(e))
            release()
        }
    }

    /** Called when playback reaches the end, so the screen can advance the playlist. */
    var onCompleted: (() -> Unit)? = null

    fun play() {
        val mp = player ?: return
        if (!_state.value.prepared) return
        runCatching { mp.start() }
            .onSuccess {
                _state.value = _state.value.copy(playing = true)
                startTicker()
            }
            .onFailure { _state.value = _state.value.copy(error = describe(it)) }
    }

    fun pause() {
        val mp = player ?: return
        if (!_state.value.playing) return
        runCatching { mp.pause() }
        _state.value = _state.value.copy(playing = false, positionMs = mp.currentPosition.toLong())
        stopTicker()
    }

    fun toggle() {
        if (_state.value.playing) pause() else play()
    }

    fun seekTo(ms: Long) {
        val mp = player ?: return
        val duration = _state.value.durationMs
        val target = if (duration > 0) ms.coerceIn(0, duration) else ms.coerceAtLeast(0)
        runCatching { mp.seekTo(target.toInt()) }
        // The reported position lags a seek by a frame or two on some devices, so the
        // state is updated here rather than waiting for the poll to catch up.
        _state.value = _state.value.copy(positionMs = target)
    }

    fun seekBy(deltaMs: Long) = seekTo(_state.value.positionMs + deltaMs)

    /** Releases the player and the polling job. Safe to call twice. */
    fun release() {
        stopTicker()
        player?.let { mp ->
            runCatching { if (mp.isPlaying) mp.stop() }
            runCatching { mp.reset() }
            runCatching { mp.release() }
        }
        player = null
        _state.value = _state.value.copy(playing = false, prepared = false)
    }

    private fun startTicker() {
        stopTicker()
        val s = scope ?: return
        ticker = s.launch {
            while (true) {
                delay(200)
                val mp = player ?: break
                if (!_state.value.playing) break
                val position = runCatching { mp.currentPosition.toLong() }.getOrDefault(0)
                val duration = runCatching { mp.duration.toLong() }.getOrDefault(-1)
                _state.value = _state.value.copy(
                    positionMs = position,
                    durationMs = if (duration > 0) duration else _state.value.durationMs,
                )
            }
        }
    }

    private fun stopTicker() {
        ticker?.cancel()
        ticker = null
    }

    private fun describe(e: Throwable): String = when (e) {
        is java.io.IOException -> "Berkas tidak bisa dibaca: ${e.message ?: "format tidak dikenal"}"
        is SecurityException -> "Aplikasi tidak diizinkan membuka berkas ini"
        else -> e.message ?: "Berkas ini tidak bisa diputar"
    }

    companion object {
        /**
         * A SAF document URI or a real path, as the `MediaPlayer` wants it.
         *
         * This is the one place the two path kinds differ, and getting it wrong is
         * silent: `setDataSource("/content://...")` is a valid path that simply does
         * not exist, and the error surfaces later as "cannot play".
         */
        fun sourceFor(context: Context, path: String): String =
            if (path.startsWith("content://")) path else File(path).absolutePath
    }
}

/**
 * The file name without its extension, for the "now playing" line.
 *
 * A player that shows `lagu.mp3` where the song has a title is a file list; showing
 * the name without the extension is the most a file manager can honestly claim,
 * because there is no tag library here to read ID3 from.
 */
fun titleOf(name: String): String {
    val dot = name.lastIndexOf('.')
    return if (dot > 0) name.substring(0, dot) else name
}

/** Where the playlist sits relative to the file that was tapped. */
fun playlistPosition(paths: List<String>, tapped: String): Int =
    paths.indexOf(tapped).coerceAtLeast(0)
