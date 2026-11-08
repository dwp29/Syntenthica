package com.rifsxd.ksunext.ui.theme

import androidx.annotation.StringRes
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
import androidx.compose.ui.graphics.Color
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
    val shape = shapesForStyle(option.style).medium
    Row(
        modifier = Modifier.fillMaxWidth().selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 15.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(modifier = Modifier.size(42.dp).clip(shape).background(previewSurface)
            .border(1.dp, previewAccent.copy(alpha = .7f), shape), contentAlignment = Alignment.Center) {
            Box(Modifier.width(22.dp).height(4.dp).clip(shape).background(previewAccent))
        }
        Spacer(Modifier.width(13.dp))
        Column(Modifier.weight(1f)) {
            Text(stringResource(option.name), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
            Text(stringResource(option.detail), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        RadioButton(selected = selected, onClick = null)
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
