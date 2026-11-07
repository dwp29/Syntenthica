package com.rifsxd.ksunext.ui.theme

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R

/** Shared by the real Manager and the separate, non-root preview. */
@Composable
fun NeonAppearanceControls(onThemeChanged: (String) -> Unit = {}) {
    val context = LocalContext.current
    val themes = listOf(
        "system" to R.string.neon31_theme_system,
        "light" to R.string.neon31_theme_light,
        "dark" to R.string.neon31_theme_dark,
        "amoled" to R.string.neon31_theme_amoled,
    )
    IosGroup(title = stringResource(R.string.neon31_theme_title)) {
        themes.forEachIndexed { index, (id, label) ->
            if (index > 0) IosGroupDivider()
            NeonChoice(label, Icons.Rounded.Contrast, IosIndigoDark, NeonThemeState.value == id) {
                setNeonTheme(context, id)
                onThemeChanged(id)
            }
        }
    }
    IosGroup(title = stringResource(R.string.neon_accent_group)) {
        NeonAccentOptions.forEachIndexed { index, option ->
            if (index > 0) IosGroupDivider()
            NeonChoice(option.label, Icons.Rounded.Palette, option.color, NeonAccentState.value == option.id) {
                setNeonAccent(context, option.id)
            }
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
            NeonChoice(label, Icons.Rounded.AutoAwesome, IosPinkDark, NeonGlowState.value == id) {
                setNeonGlow(context, id)
            }
        }
        IosGroupDivider()
        IosSwitchRow(
            icon = Icons.Rounded.AutoAwesome,
            badgeColor = IosPurpleDark,
            title = stringResource(R.string.neon_motion_title),
            subtitle = stringResource(R.string.neon_motion_subtitle),
            checked = NeonMotionState.value,
            onCheckedChange = { setNeonMotion(context, it) },
        )
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
        modifier = Modifier.fillMaxWidth().selectable(
            selected = selected, role = Role.RadioButton, onClick = onClick,
        ).padding(horizontal = 15.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IosBadgeIcon(icon = icon, color = color)
        Spacer(Modifier.width(13.dp))
        Text(
            text = stringResource(label), modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface,
        )
        RadioButton(selected = selected, onClick = null)
    }
}
