package com.rifsxd.ksunext.ui.theme

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Glassmorphism backdrop in the iOS style: a pale vertical gradient with three large,
 * very soft colour fields (system blue, mint, violet) drifting slowly behind every
 * screen, so white translucent cards read as frosted glass. Drawn on a Canvas only.
 */
@Composable
fun GlassBackground(modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "glassBackground")
    val drift by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 14000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glassDrift"
    )

    Box(
        modifier = modifier.background(
            Brush.verticalGradient(listOf(GLASS_BG_TOP, GLASS_BG_MID, GLASS_BG_BOT))
        )
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            val r = w * 0.55f
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(ACCENT_BLUE.copy(alpha = 0.28f), Color.Transparent),
                    center = Offset(w * (0.15f + 0.10f * drift), h * 0.12f),
                    radius = r
                ),
                radius = r,
                center = Offset(w * (0.15f + 0.10f * drift), h * 0.12f)
            )
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(ACCENT_VIOLET.copy(alpha = 0.24f), Color.Transparent),
                    center = Offset(w * (0.90f - 0.08f * drift), h * 0.45f),
                    radius = r
                ),
                radius = r,
                center = Offset(w * (0.90f - 0.08f * drift), h * 0.45f)
            )
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(ACCENT_MINT.copy(alpha = 0.20f), Color.Transparent),
                    center = Offset(w * (0.30f + 0.10f * drift), h * 0.92f),
                    radius = r
                ),
                radius = r,
                center = Offset(w * (0.30f + 0.10f * drift), h * 0.92f)
            )
        }
    }
}

/**
 * Splash: a frosted glass orb with a slowly rotating highlight arc, then the
 * wordmark "Synthetica" and a quiet subtitle. [rotation] is driven by
 * MainActivity's existing splash animation timing.
 */
@Composable
fun GlassSplash(rotation: Float = 0f, modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "glassSplash")
    val breathe by transition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "orbBreathe"
    )

    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Canvas(modifier = Modifier.size(170.dp).padding(bottom = 28.dp)) {
                val r = 62.dp.toPx() * breathe
                val c = Offset(size.width / 2f, size.height / 2f)
                drawCircle(
                    brush = Brush.radialGradient(
                        listOf(Color.White.copy(alpha = 0.95f), ACCENT_BLUE.copy(alpha = 0.35f), Color.Transparent),
                        center = c,
                        radius = r * 1.5f
                    ),
                    radius = r * 1.5f,
                    center = c
                )
                drawCircle(color = Color.White.copy(alpha = 0.85f), radius = r, center = c)
                drawCircle(
                    color = ACCENT_BLUE.copy(alpha = 0.20f),
                    radius = r,
                    center = c,
                    style = Stroke(width = 1.5.dp.toPx())
                )
                drawArc(
                    color = ACCENT_BLUE,
                    startAngle = rotation,
                    sweepAngle = 110f,
                    useCenter = false,
                    topLeft = Offset(c.x - r, c.y - r),
                    size = androidx.compose.ui.geometry.Size(r * 2, r * 2),
                    style = Stroke(width = 3.dp.toPx())
                )
                drawArc(
                    color = ACCENT_VIOLET.copy(alpha = 0.8f),
                    startAngle = rotation * 0.7f + 180f,
                    sweepAngle = 70f,
                    useCenter = false,
                    topLeft = Offset(c.x - r, c.y - r),
                    size = androidx.compose.ui.geometry.Size(r * 2, r * 2),
                    style = Stroke(width = 3.dp.toPx())
                )
            }
            Text(
                text = "Synthetica",
                style = MaterialTheme.typography.displaySmall.copy(
                    fontWeight = FontWeight.Bold,
                    letterSpacing = (-0.4).sp,
                    color = INK
                )
            )
            Text(
                text = "Clean. Calm. Yours.",
                style = MaterialTheme.typography.bodyMedium.copy(color = TEXT_DIM),
                modifier = Modifier.padding(top = 6.dp)
            )
        }
    }
}

// Synthetica 2.0 build retry after billing check (no functional change).
