package com.rifsxd.ksunext.ui.theme

import androidx.annotation.StringRes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Contrast
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R

private data class StyleOption(@StringRes val name: Int, @StringRes val detail: Int, val style: ManagerStyle)
private val styles = listOf(
    StyleOption(R.string.theme50_pixel, R.string.theme50_pixel_detail, ManagerStyle.PIXEL),
    StyleOption(R.string.theme50_cyber, R.string.theme50_cyber_detail, ManagerStyle.CYBERPUNK),
    StyleOption(R.string.theme50_ios, R.string.theme50_ios_detail, ManagerStyle.IOS_GLASS),
    StyleOption(R.string.theme50_neon, R.string.theme50_neon_detail, ManagerStyle.NEON),
)

/** Shared by the real Manager and the isolated, non-root preview. */
@Composable
fun NeonAppearanceControls(onThemeChanged: (String) -> Unit = {}) {
    val context = LocalContext.current
    val selectedStyle = ManagerStyleState.value
    IosGroup(title = stringResource(R.string.theme50_design_title), footer = stringResource(R.string.theme50_design_footer)) {
        styles.forEachIndexed { index, option ->
            if (index > 0) IosGroupDivider()
            StyleChoice(option, selectedStyle == option.style) { setManagerStyle(context, option.style.id) }
        }
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
    }
    Row(
        modifier = Modifier.fillMaxWidth().selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 15.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StyleThumbnail(option.style, previewSurface, previewAccent)
        Spacer(Modifier.width(13.dp))
        Column(Modifier.weight(1f)) {
            Text(stringResource(option.name), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
            Text(stringResource(option.detail), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        RadioButton(selected = selected, onClick = null)
    }
}

/** Illustrates each layout rather than showing four identical color swatches. */
@Composable
private fun StyleThumbnail(style: ManagerStyle, surface: Color, accent: Color) {
    val shape = if (style == ManagerStyle.PIXEL) RectangleShape else shapesForStyle(style).large
    Canvas(Modifier.size(width = 52.dp, height = 48.dp).clip(shape).background(surface)
        .border(1.dp, accent.copy(alpha = .7f), shape)) {
        val w = size.width
        val h = size.height
        val faint = accent.copy(alpha = .25f)
        when (style) {
            ManagerStyle.PIXEL -> {
                drawRect(faint, Offset(w * .1f, h * .12f), Size(w * .8f, h * .16f))
                drawRect(accent, Offset(w * .12f, h * .35f), Size(w * .22f, h * .24f))
                drawRect(accent.copy(alpha = .7f), Offset(w * .4f, h * .36f), Size(w * .44f, h * .06f))
                drawRect(faint, Offset(w * .4f, h * .48f), Size(w * .36f, h * .05f))
                drawRect(accent.copy(alpha = .6f), Offset(w * .1f, h * .74f), Size(w * .8f, h * .10f))
            }
            ManagerStyle.CYBERPUNK -> {
                val cut = Path().apply {
                    moveTo(w * .11f, h * .19f); lineTo(w * .70f, h * .19f)
                    lineTo(w * .88f, h * .37f); lineTo(w * .88f, h * .66f)
                    lineTo(w * .27f, h * .66f); lineTo(w * .11f, h * .50f); close()
                }
                drawPath(cut, faint)
                drawPath(cut, accent.copy(alpha = .85f), style = Stroke(width = 1.dp.toPx()))
                drawLine(accent, Offset(w * .18f, h * .32f), Offset(w * .55f, h * .32f), 2.dp.toPx())
                drawRect(accent, Offset(w * .67f, h * .35f), Size(w * .13f, h * .18f))
                drawRect(faint, Offset(w * .12f, h * .76f), Size(w * .76f, h * .08f))
            }
            ManagerStyle.IOS_GLASS -> {
                drawRoundRect(faint, Offset(w * .12f, h * .12f), Size(w * .76f, h * .58f), CornerRadius(w * .12f))
                drawCircle(accent, radius = w * .085f, center = Offset(w * .5f, h * .30f))
                drawRoundRect(Color.White.copy(alpha = .85f), Offset(w * .30f, h * .45f),
                    Size(w * .40f, h * .05f), CornerRadius(2.dp.toPx()))
                drawRoundRect(accent.copy(alpha = .75f), Offset(w * .22f, h * .77f),
                    Size(w * .56f, h * .11f), CornerRadius(5.dp.toPx()))
            }
            ManagerStyle.NEON -> {
                drawRoundRect(accent.copy(alpha = .9f), Offset(w * .10f, h * .15f), Size(w * .80f, h * .55f),
                    CornerRadius(5.dp.toPx()), style = Stroke(width = 1.5.dp.toPx()))
                drawRoundRect(accent, Offset(w * .18f, h * .25f), Size(w * .20f, h * .22f), CornerRadius(3.dp.toPx()))
                drawLine(accent, Offset(w * .47f, h * .30f), Offset(w * .78f, h * .30f), 2.dp.toPx())
                drawLine(Color(0xFFFF63DB), Offset(w * .18f, h * .57f), Offset(w * .79f, h * .57f), 2.dp.toPx())
                drawRoundRect(faint, Offset(w * .15f, h * .77f), Size(w * .70f, h * .10f), CornerRadius(3.dp.toPx()))
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
