package com.rifsxd.ksunext.ui.theme

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.annotation.StringRes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Contrast
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.PlayCircleOutline
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R
import kotlin.math.cos
import kotlin.math.sin

private data class StyleOption(@StringRes val name: Int, @StringRes val detail: Int, val style: ManagerStyle)
private val styles = listOf(
    StyleOption(R.string.theme50_pixel, R.string.theme50_pixel_detail, ManagerStyle.PIXEL),
    StyleOption(R.string.theme50_cyber, R.string.theme50_cyber_detail, ManagerStyle.CYBERPUNK),
    StyleOption(R.string.theme50_ios, R.string.theme50_ios_detail, ManagerStyle.IOS_GLASS),
    StyleOption(R.string.theme50_neon, R.string.theme50_neon_detail, ManagerStyle.NEON),
    StyleOption(R.string.theme50_retro, R.string.theme50_retro_detail, ManagerStyle.RETRO_ARCADE),
    StyleOption(R.string.theme50_anime, R.string.theme50_anime_detail, ManagerStyle.ANIME_WIBU),
    StyleOption(R.string.theme50_gothic, R.string.theme50_gothic_detail, ManagerStyle.GOTHIC_CRIMSON),
)

/** Shared by the real Manager and the isolated, non-root preview. */
@Composable
fun NeonAppearanceControls(onThemeChanged: (String) -> Unit = {}) {
    val context = LocalContext.current
    val selectedStyle = ManagerStyleState.value
    val motionEnabled = LocalPixelMotionEnabled.current
    var backupStatus by remember { mutableStateOf<String?>(null) }

    IosGroup(title = stringResource(R.string.theme50_design_title), footer = stringResource(R.string.theme50_design_footer)) {
        styles.forEachIndexed { index, option ->
            if (index > 0) IosGroupDivider()
            StyleChoice(option, selectedStyle == option.style) {
                val changed = selectedStyle != option.style
                setManagerStyle(context, option.style.id)
                if (changed && motionEnabled) {
                    triggerThemeSplashPreview()
                }
            }
        }
        IosGroupDivider()
        IosRow(
            icon = Icons.Rounded.PlayCircleOutline,
            badgeColor = MaterialTheme.colorScheme.primary,
            title = stringResource(R.string.theme50_preview_splash),
            subtitle = stringResource(R.string.theme50_preview_splash_sub),
            pill = selectedStyle.id.uppercase(),
            pillColor = MaterialTheme.colorScheme.primary,
            showChevron = true,
            onClick = { triggerThemeSplashPreview() },
        )
    }
    val modes = listOf(
        "system" to R.string.neon31_theme_system,
        "light" to R.string.neon31_theme_light,
        "dark" to R.string.neon31_theme_dark,
        "amoled" to R.string.neon31_theme_amoled,
    )
    IosGroup(title = stringResource(R.string.neon31_theme_title)) {
        modes.forEachIndexed { index, (id, label) ->
            if (index > 0) IosGroupDivider()
            NeonChoice(label, Icons.Rounded.Contrast, MaterialTheme.colorScheme.primary, NeonThemeState.value == id) {
                setNeonTheme(context, id)
                onThemeChanged(id)
            }
        }
    }
    val dark = LocalGlassStyle.current.isDark
    IosGroup(title = stringResource(R.string.neon_accent_group)) {
        NeonAccentOptions.forEachIndexed { index, option ->
            if (index > 0) IosGroupDivider()
            NeonChoice(option.label, Icons.Rounded.Palette, accentForStyle(selectedStyle, option.id, dark),
                NeonAccentState.value == option.id) { setNeonAccent(context, option.id) }
        }
    }
    val glowLevels = listOf(
        "subtle" to R.string.neon31_glow_subtle,
        "normal" to R.string.neon31_glow_normal,
        "bright" to R.string.neon31_glow_bright,
    )
    val speedLevels = listOf(
        "normal" to R.string.manager60_anim_speed_normal,
        "turbo" to R.string.manager60_anim_speed_turbo,
        "reduced" to R.string.manager60_anim_speed_reduced,
    )
    IosGroup(title = stringResource(R.string.neon31_glow_title)) {
        glowLevels.forEachIndexed { index, (id, label) ->
            if (index > 0) IosGroupDivider()
            NeonChoice(label, Icons.Rounded.AutoAwesome, MaterialTheme.colorScheme.primary, NeonGlowState.value == id) {
                setNeonGlow(context, id)
            }
        }
        IosGroupDivider()
        IosSwitchRow(
            icon = Icons.Rounded.AutoAwesome,
            badgeColor = MaterialTheme.colorScheme.primary,
            title = stringResource(R.string.neon_motion_title),
            subtitle = stringResource(R.string.neon_motion_subtitle),
            checked = NeonMotionState.value,
            onCheckedChange = { setNeonMotion(context, it) },
        )
        speedLevels.forEach { (id, label) ->
            IosGroupDivider()
            NeonChoice(label, Icons.Rounded.Speed, IosCyanDark, ManagerAnimSpeedState.value == id) {
                setManagerAnimSpeed(context, id)
            }
        }
    }
    IosGroup(
        title = stringResource(R.string.manager60_backup_group),
        footer = backupStatus ?: stringResource(R.string.manager60_backup_footer),
    ) {
        IosRow(
            icon = Icons.Rounded.ContentCopy,
            badgeColor = IosCyanDark,
            title = stringResource(R.string.manager60_export_json),
            subtitle = stringResource(R.string.manager60_export_json_sub),
            showChevron = true,
            onClick = {
                runCatching {
                    val json = exportManagerConfigJson(context)
                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                    cm?.setPrimaryClip(ClipData.newPlainText("Synthetica Config JSON", json))
                    backupStatus = context.getString(R.string.manager60_export_ok)
                }
            },
        )
        IosGroupDivider()
        IosRow(
            icon = Icons.Rounded.ContentPaste,
            badgeColor = IosGreenDark,
            title = stringResource(R.string.manager60_import_json),
            subtitle = stringResource(R.string.manager60_import_json_sub),
            showChevron = true,
            onClick = {
                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                val text = cm?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString().orEmpty()
                val ok = importManagerConfigJson(context, text)
                if (ok) onThemeChanged(NeonThemeState.value)
                backupStatus = context.getString(if (ok) R.string.manager60_import_ok else R.string.manager60_import_fail)
            },
        )
    }
}

@Composable
private fun StyleChoice(option: StyleOption, selected: Boolean, onClick: () -> Unit) {
    val previewAccent = accentForStyle(option.style, "cyan", true)
    val previewSurface = when (option.style) {
        ManagerStyle.PIXEL -> Color(0xFF1C1C1A)
        ManagerStyle.CYBERPUNK -> Color(0xFF12151D)
        ManagerStyle.IOS_GLASS -> Color(0xFF1B2A40)
        ManagerStyle.NEON -> Color(0xFF111A30)
        ManagerStyle.RETRO_ARCADE -> Color(0xFF13233F)
        ManagerStyle.ANIME_WIBU -> Color(0xFF1E1430)
        ManagerStyle.GOTHIC_CRIMSON -> Color(0xFF0A0708)
    }
    Row(
        modifier = Modifier.fillMaxWidth().selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 15.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StyleThumbnail(option.style, previewSurface, previewAccent)
        Spacer(Modifier.width(13.dp))
        Column(Modifier.weight(1f)) {
            Text(
                text = stringResource(option.name),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(option.detail),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        RadioButton(selected = selected, onClick = null)
    }
}

/** Displays each theme's authentic PNG emblem together with its geometric layout signature. */
@Composable
private fun StyleThumbnail(style: ManagerStyle, surface: Color, accent: Color) {
    val shape = if (style == ManagerStyle.PIXEL) RectangleShape else shapesForStyle(style).medium
    val emblemShape = when (style) {
        ManagerStyle.PIXEL -> RectangleShape
        ManagerStyle.CYBERPUNK -> shapesForStyle(style).small
        ManagerStyle.IOS_GLASS -> RoundedCornerShape(10.dp)
        ManagerStyle.NEON -> RoundedCornerShape(8.dp)
        ManagerStyle.RETRO_ARCADE -> RoundedCornerShape(4.dp)
        ManagerStyle.ANIME_WIBU -> RoundedCornerShape(14.dp)
        ManagerStyle.GOTHIC_CRIMSON -> CutCornerShape(topStart = 2.dp, topEnd = 9.dp, bottomEnd = 2.dp, bottomStart = 9.dp)
    }
    Row(
        modifier = Modifier
            .width(68.dp)
            .height(48.dp)
            .clip(shape)
            .background(surface)
            .border(1.2.dp, accent.copy(alpha = 0.78f), shape)
            .padding(horizontal = 5.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Image(
            painter = painterResource(emblemResForStyle(style)),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(34.dp)
                .clip(emblemShape)
                .border(0.8.dp, accent.copy(alpha = 0.65f), emblemShape),
        )
        Canvas(modifier = Modifier.weight(1f).fillMaxSize()) {
            val w = size.width
            val h = size.height
            val faint = accent.copy(alpha = 0.30f)
            when (style) {
                ManagerStyle.PIXEL -> {
                    val dot = 3.dp.toPx()
                    for (r in 0..3) {
                        drawRect(if (r % 2 == 0) accent else faint, Offset(w * 0.15f, r * (dot + 3.dp.toPx())), Size(w * 0.70f, dot))
                    }
                }
                ManagerStyle.CYBERPUNK -> {
                    val cut = Path().apply {
                        moveTo(0f, h * 0.10f); lineTo(w * 0.72f, h * 0.10f)
                        lineTo(w, h * 0.32f); lineTo(w, h * 0.90f)
                        lineTo(0f, h * 0.90f); close()
                    }
                    drawPath(cut, faint)
                    drawPath(cut, accent, style = Stroke(width = 1.dp.toPx()))
                }
                ManagerStyle.IOS_GLASS -> {
                    drawCircle(accent, radius = w * 0.32f, center = Offset(w * 0.5f, h * 0.35f))
                    drawRoundRect(Color.White.copy(alpha = 0.75f), Offset(w * 0.1f, h * 0.72f), Size(w * 0.8f, h * 0.16f), CornerRadius(3.dp.toPx()))
                }
                ManagerStyle.RETRO_ARCADE -> {
                    // Scanline stack with one lit bar, like a cabinet score rail.
                    val line = 2.dp.toPx()
                    for (r in 0..4) {
                        val colour = if (r == 1) accent else faint
                        drawRect(colour, Offset(w * 0.12f, r * (line + 2.dp.toPx())), Size(w * 0.78f, line))
                    }
                    drawCircle(Color(0xFFFF8A3D), radius = 2.5.dp.toPx(), center = Offset(w * 0.5f, h * 0.86f))
                }
                ManagerStyle.GOTHIC_CRIMSON -> {
                    // Moon disc with a thorn ring and a thin crimson rule.
                    drawCircle(accent.copy(alpha = 0.85f), radius = w * 0.20f, center = Offset(w * 0.62f, h * 0.32f))
                    for (i in 0..7) {
                        val a = (i / 8f) * 2f * Math.PI.toFloat()
                        val r = w * 0.20f
                        drawLine(Color(0xFF5A0A10), Offset(w * 0.62f + cos(a) * r, h * 0.32f + sin(a) * r),
                            Offset(w * 0.62f + cos(a) * r * 1.3f, h * 0.32f + sin(a) * r * 1.3f), 1.dp.toPx())
                    }
                    drawRect(accent.copy(alpha = 0.55f), Offset(w * 0.1f, h * 0.82f), Size(w * 0.8f, 1.2.dp.toPx()))
                }
                ManagerStyle.ANIME_WIBU -> {
                    // Sakura scatter plus a rounded caption bar.
                    repeat(4) { i ->
                        drawCircle(accent.copy(alpha = 0.55f), radius = 1.8.dp.toPx(),
                            center = Offset(w * (0.2f + 0.2f * i), h * (0.18f + 0.1f * (i % 2))))
                    }
                    drawRoundRect(Color.White.copy(alpha = 0.85f), Offset(0f, h * 0.68f), Size(w, h * 0.32f), CornerRadius(6.dp.toPx()))
                }
                ManagerStyle.NEON -> {
                    drawLine(accent, Offset(w * 0.15f, h * 0.25f), Offset(w * 0.85f, h * 0.25f), 2.dp.toPx())
                    drawLine(Color(0xFFFF63DB), Offset(w * 0.15f, h * 0.52f), Offset(w * 0.85f, h * 0.52f), 2.dp.toPx())
                    drawRoundRect(accent.copy(alpha = 0.85f), Offset(w * 0.1f, h * 0.72f), Size(w * 0.8f, h * 0.18f), CornerRadius(2.dp.toPx()), style = Stroke(width = 1.dp.toPx()))
                }
            }
        }
    }
}

@Composable
private fun NeonChoice(
    @StringRes label: Int,
    icon: ImageVector,
    color: Color,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 15.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IosBadgeIcon(icon = icon, color = color)
        Spacer(Modifier.width(13.dp))
        Text(text = stringResource(label), modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
        RadioButton(selected = selected, onClick = null)
    }
}
