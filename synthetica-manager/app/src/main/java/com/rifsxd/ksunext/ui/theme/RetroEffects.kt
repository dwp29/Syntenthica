package com.rifsxd.ksunext.ui.theme

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.ui.Alignment
import androidx.compose.material3.Text
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEvent
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.rememberTextMeasurer
import com.rifsxd.ksunext.R
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlin.math.exp
import kotlin.math.sin
import kotlin.random.Random

// ---- Unified chiptune SFX via SoundPool --------------------------------------
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

// ---- Particle bus -------------------------------------------------------------
data class RetroParticle(
    val x: Float, val y: Float,
    val vx: Float, val vy: Float,
    val birth: Long, val ttl: Long,
    val color: Color, val glyph: String, val size: Float,
)

object RetroParticles {
    val particles = mutableStateListOf<RetroParticle>()
    private val random = Random(System.currentTimeMillis())
    private val palette = listOf(Color(0xFFFF8A3D), Color(0xFFFFD000), Color(0xFFFF2BD6), Color(0xFF5EF2E0), Color(0xFFF5F5ED))
    private val glyphs = listOf("✦", "✱", "■", "▲", "▶", "+")
    fun burst(at: Offset, count: Int = 22) {
        val now = System.currentTimeMillis()
        repeat(count) {
            val angle = random.nextFloat() * 6.2832f
            val speed = 40f + random.nextFloat() * 150f
            particles += RetroParticle(
                x = at.x, y = at.y,
                vx = kotlin.math.cos(angle) * speed,
                vy = kotlin.math.sin(angle) * speed - 40f,
                birth = now,
                ttl = 600L + (random.nextFloat() * 650f).toLong(),
                color = palette[random.nextInt(palette.size)],
                glyph = glyphs[random.nextInt(glyphs.size)],
                size = 6f + random.nextFloat() * 16f,
            )
        }
        if (particles.size > 240) {
            particles.subList(0, particles.size - 240).clear()
        }
    }
    fun tick() {
        val now = System.currentTimeMillis()
        particles.removeAll { now - it.birth > it.ttl }
    }
    fun clear() = particles.clear()
}

// ---- Konami code detection ----------------------------------------------------
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
    fun push(event: KeyEvent): Boolean {
        if (event.type != androidx.compose.ui.input.key.KeyEventType.KeyDown) return false
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

// ---- Retro CRT overlay + particle canvas --------------------------------------
@Composable
fun RetroCrtLayer(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    var flash by remember { mutableStateOf(0f) }
    val rng = remember { Random(42) }
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
            drawRect(Color(0x14FF8A3D), topLeft = Offset(0f, y), size = Size(size.width, scanH * 0.5f))
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
        // Amber pulse top bloom (pulses like a cabinet marquee)
        val pulse = 0.5f + 0.5f * sin(System.currentTimeMillis() / 900.0)
        drawCircle(
            brush = Brush.radialGradient(
                listOf(Color(0xFFFFC08A).copy(alpha = 0.05f + 0.06f * pulse.toFloat()), Color.Transparent),
                center = Offset(size.width / 2f, size.height * 0.06f),
                radius = size.width * 0.75f,
            ),
            radius = size.width * 0.75f,
            center = Offset(size.width / 2f, size.height * 0.06f),
        )
        // White flash on tap/burst
        if (flash > 0.01f) {
            drawRect(Color.White.copy(alpha = (flash * 0.35f).coerceAtMost(0.35f)))
        }
        // Particles
        val now = System.currentTimeMillis()
        RetroParticles.particles.forEach { p ->
            val age = (now - p.birth).coerceAtLeast(0L)
            val lifeT = (age.toFloat() / p.ttl).coerceIn(0f, 1f)
            val secs = age / 1000f
            val px = p.x + p.vx * secs
            val py = p.y + p.vy * secs + 340f * secs * secs
            val alpha = (1f - lifeT).coerceIn(0f, 1f)
            val layout = measurer.measure(
                androidx.compose.ui.text.AnnotatedString(p.glyph),
                style = androidx.compose.ui.text.TextStyle(fontSize = androidx.compose.ui.unit.TextUnit(p.size, androidx.compose.ui.unit.TextUnitType.Sp), color = p.color.copy(alpha = alpha)),
            )
            drawText(layout, topLeft = Offset(px - layout.size.width / 2f, py - layout.size.height / 2f))
        }
    }
}

// ---- Konami win overlay --------------------------------------------------------
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
                    "★ UFO LANDLORD ★",
                    color = Color(0xFF2A0A00),
                    style = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.Black),
                )
                Text(
                    "YOU WIN!",
                    color = Color(0xFF2A0A00),
                    style = TextStyle(fontSize = 64.sp, fontWeight = FontWeight.Black),
                )
                Text(
                    "HI-SCORE 999990",
                    color = Color(0xFF5A2A00),
                    style = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.Bold),
                )
            }
        }
    }
}
