package com.rifsxd.ksunext.ui.theme

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEvent
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rifsxd.ksunext.R
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlin.math.PI
import kotlin.math.sin
import kotlin.math.cos
import kotlin.random.Random

// ---- Chiptune SFX via SoundPool -------------------------------------------------
object RetroSfx {
    private var pool: SoundPool? = null
    private val ids = mutableMapOf<String, Int>()
    private fun ensure(context: Context) {
        if (pool != null) return
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_GAME)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val p = SoundPool.Builder().setMaxStreams(6).setAudioAttributes(attrs).build()
        ids["select"] = p.load(context, R.raw.sfx_select, 1)
        ids["activate"] = p.load(context, R.raw.sfx_activate, 1)
        ids["denied"] = p.load(context, R.raw.sfx_denied, 1)
        ids["win"] = p.load(context, R.raw.sfx_win, 1)
        ids["back"] = p.load(context, R.raw.sfx_back, 1)
        pool = p
    }
    fun play(context: Context, name: String, volume: Float = 0.6f) {
        ensure(context)
        val id = ids[name] ?: return
        pool?.play(id, volume, volume, 1, 0, 1.0f)
    }
}

// ---- Particle bus (state moved into a composable-less singleton for tap events) --
data class RetroParticle(
    val x: Float,
    val y: Float,
    val vx: Float,
    val vy: Float,
    val birth: Long,
    val ttl: Long,
    val color: Color,
    val shape: Int,
    val size: Float,
    val spin: Float,
)

object RetroParticles {
    val particles = mutableStateListOf<RetroParticle>()
    private val random = Random(System.currentTimeMillis())
    private val palette = listOf(
        Color(0xFFFF8A3D), Color(0xFFFFD000), Color(0xFFFF2BD6),
        Color(0xFF5EF2E0), Color(0xFFF5F5ED), Color(0xFF9BF0B4),
    )
    fun burst(at: Offset, count: Int = 22) {
        val now = System.currentTimeMillis()
        repeat(count) {
            val angle = random.nextFloat() * (2f * PI.toFloat())
            val speed = 40f + random.nextFloat() * 150f
            particles += RetroParticle(
                x = at.x,
                y = at.y,
                vx = cos(angle) * speed,
                vy = sin(angle) * speed - 40f,
                birth = now,
                ttl = 600L + (random.nextFloat() * 650f).toLong(),
                color = palette[random.nextInt(palette.size)],
                shape = random.nextInt(3),
                size = 6f + random.nextFloat() * 15f,
                spin = (random.nextFloat() - 0.5f) * 240f,
            )
        }
        while (particles.size > 240) particles.removeAt(0)
    }
    fun tick() {
        val now = System.currentTimeMillis()
        particles.removeAll { now - it.birth > it.ttl }
    }
    fun clear() = particles.clear()
}

// ---- Konami code detection ------------------------------------------------------
object RetroKonami {
    private val buffer = mutableListOf<Key>()
    private val sequence = listOf(
        Key.DirectionUp, Key.DirectionUp,
        Key.DirectionDown, Key.DirectionDown,
        Key.DirectionLeft, Key.DirectionRight,
        Key.DirectionLeft, Key.DirectionRight,
        Key.B, Key.A,
    )
    var won by mutableStateOf(false)
        private set

    fun push(event: KeyEvent): Boolean {
        if (event.type != KeyEventType.KeyDown) return false
        buffer += event.key
        if (buffer.size > sequence.size) buffer.removeAt(0)
        if (buffer == sequence) {
            won = true
            buffer.clear()
            return true
        }
        return false
    }

    fun acknowledgeWin() { won = false }
}

// ---- Retro CRT overlay + tap-burst particle canvas -----------------------------
@Composable
fun RetroCrtLayer(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var flash by remember { mutableStateOf(0f) }
    LaunchedEffect(Unit) {
        while (isActive) {
            RetroParticles.tick()
            flash *= 0.86f
            delay(16)
        }
    }
    Canvas(
        modifier
            .pointerInput(Unit) {
                detectTapGestures { offset ->
                    RetroParticles.burst(offset)
                    flash = 0.9f
                    RetroSfx.play(context, "select", 0.35f)
                }
            }
    ) {
        // Scanlines
        val scanH = 2.dp.toPx()
        var y = 0f
        while (y < size.height) {
            drawRect(
                color = Color(0x14FF8A3D),
                topLeft = Offset(0f, y),
                size = Size(size.width, scanH * 0.5f),
            )
            y += scanH
        }
        // Vignette
        drawRect(
            brush = Brush.radialGradient(
                colors = listOf(Color.Transparent, Color(0x52000000), Color(0xA0000000)),
                center = Offset(size.width / 2f, size.height * 0.40f),
                radius = size.height * 0.72f,
            ),
        )
        // Amber pulse bloom near the top (cabinet marquee)
        val now = System.currentTimeMillis()
        val pulse = 0.5f + 0.5f * sin(now / 900.0).toFloat()
        drawCircle(
            brush = Brush.radialGradient(
                listOf(Color(0xFFFFC08A).copy(alpha = 0.05f + 0.06f * pulse), Color.Transparent),
                center = Offset(size.width / 2f, size.height * 0.06f),
                radius = size.width * 0.75f,
            ),
            radius = size.width * 0.75f,
            center = Offset(size.width / 2f, size.height * 0.06f),
        )
        // White flash on tap
        if (flash > 0.01f) {
            drawRect(Color.White.copy(alpha = (flash * 0.35f).coerceAtMost(0.35f)))
        }
        // Particles: circles, squares, triangles
        val pNow = System.currentTimeMillis()
        RetroParticles.particles.forEach { p ->
            val age = (pNow - p.birth).coerceAtLeast(0L).toFloat()
            val lifeT = (age / p.ttl).coerceIn(0f, 1f)
            val secs = age / 1000f
            val px = p.x + p.vx * secs
            val py = p.y + p.vy * secs + 340f * secs * secs
            val alpha = (1f - lifeT).coerceIn(0f, 1f)
            val sz = p.size * (1f - lifeT * 0.35f)
            val angle = (p.spin * secs) % 360f
            rotate(angle, pivot = Offset(px, py)) {
                when (p.shape) {
                    0 -> drawCircle(color = p.color.copy(alpha = alpha), radius = sz / 2f, center = Offset(px, py))
                    1 -> drawRect(color = p.color.copy(alpha = alpha), topLeft = Offset(px - sz / 2f, py - sz / 2f), size = Size(sz, sz))
                    else -> {
                        val path = Path().apply {
                            moveTo(px, py - sz / 2f)
                            lineTo(px - sz * 0.5f, py + sz * 0.35f)
                            lineTo(px + sz * 0.5f, py + sz * 0.35f)
                            close()
                        }
                        drawPath(path = path, color = p.color.copy(alpha = alpha))
                    }
                }
            }
        }
    }
}

// ---- Konami win overlay ----------------------------------------------------------
@Composable
fun RetroKonamiOverlay() {
    val context = LocalContext.current
    LaunchedEffect(RetroKonami.won) {
        if (RetroKonami.won) {
            RetroSfx.play(context, "win", 0.8f)
            RetroParticles.burst(Offset(160f, 330f), 44)
            delay(2600)
            RetroKonami.acknowledgeWin()
        }
    }
    AnimatedVisibility(visible = RetroKonami.won, enter = fadeIn(), exit = fadeOut()) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFFFD000)),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "UFO LANDLORD",
                    color = Color(0xFF2A0A00),
                    style = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.Black),
                )
                Text(
                    text = "YOU WIN!",
                    color = Color(0xFF2A0A00),
                    style = TextStyle(fontSize = 64.sp, fontWeight = FontWeight.Black),
                )
                Text(
                    text = "HI-SCORE 999990",
                    color = Color(0xFF5A2A00),
                    style = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.Bold),
                )
            }
        }
    }
}
