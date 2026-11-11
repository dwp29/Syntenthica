package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * What the app shows if the theme system throws during composition.
 *
 * Deliberately does not import a single token: this screen must render even when
 * the thing that failed is the token system itself. Fixed colours, fixed sizes,
 * no blur, no spec.
 *
 * Exists because "force close on launch" gave no information at all. Now a broken
 * theme produces a readable screen with the exception and a reset button, which
 * is a bug report the owner can send instead of a silent disappearance.
 */
@Composable
fun FallbackScreen(reason: String, dark: Boolean, onReset: () -> Unit) {
    val bg = if (dark) Color(0xFF101014) else Color(0xFFF2F2F7)
    val fg = if (dark) Color(0xFFE6E0E9) else Color(0xFF1C1C1E)
    val dim = if (dark) Color(0xFF938F99) else Color(0xFF6B6B70)
    val card = if (dark) Color(0xFF1C1C1E) else Color(0xFFFFFFFF)
    val line = if (dark) Color(0xFF3D3D3D) else Color(0xFFD8D8DC)
    val accent = Color(0xFF007AFF)

    Box(Modifier.fillMaxSize().background(bg)) {
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
        ) {
            Spacer(Modifier.height(48.dp))
            Text(
                "Tampilan gagal dimuat",
                color = fg,
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Aplikasi masih berjalan. Tema yang dipilih tidak bisa digambar, " +
                    "jadi tampilan dikembalikan ke pengaturan awal.",
                color = dim,
                fontSize = 14.sp,
            )
            Spacer(Modifier.height(18.dp))
            Text(
                reason,
                color = fg,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(card)
                    .border(0.5.dp, line, RoundedCornerShape(10.dp))
                    .padding(12.dp),
            )
            Spacer(Modifier.height(24.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(accent, RoundedCornerShape(12.dp))
                    .clickable(onClick = onReset)
                    .padding(vertical = 14.dp),
                contentAlignment = androidx.compose.ui.Alignment.Center,
            ) {
                Text(
                    "Kembali ke tampilan awal",
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Detail lengkap ada di tab Setelan \u2192 Laporan crash, " +
                    "setelah tampilan pulih.",
                color = dim,
                fontSize = 12.sp,
            )
            Spacer(Modifier.height(40.dp))
        }
    }
}

