package com.rifsxd.ksunext.ui.pixel

import androidx.activity.compose.BackHandler
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.NetworkCheck
import androidx.compose.material.icons.rounded.Restore
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.VolumeUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.iosGlass
import kotlin.math.roundToInt

/** This result reports command completion, never an assumed global enabled state. */
data class PixelActionResult40(val success: Boolean, val output: String)
private data class PendingAction40(val action: String, @StringRes val label: Int, @StringRes val warning: Int)

@Composable
private fun ActionConfirmation40(pending: PendingAction40?, onCancel: () -> Unit, onConfirm: (String) -> Unit) {
    if (pending == null) return
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text(stringResource(R.string.pixel40_action_confirm)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(stringResource(pending.label), style = MaterialTheme.typography.titleMedium)
                Text(stringResource(pending.warning), style = MaterialTheme.typography.bodyMedium)
            }
        },
        confirmButton = { TextButton(onClick = { onConfirm(pending.action) }) { Text(stringResource(R.string.pixel40_action_confirm_button)) } },
        dismissButton = { TextButton(onClick = onCancel) { Text(stringResource(R.string.pixel40_action_cancel)) } },
    )
}

@Composable
private fun ActionResult40(result: PixelActionResult40?, busy: Boolean, canAct: Boolean) {
    IosGroup(title = stringResource(R.string.pixel40_result_title)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            val status = when {
                busy -> stringResource(R.string.pixel40_action_working)
                !canAct -> stringResource(R.string.pixel40_root_required)
                result == null -> stringResource(R.string.pixel40_result_empty)
                result.success -> stringResource(R.string.pixel40_action_success)
                else -> stringResource(R.string.pixel40_action_partial)
            }
            Text(status, style = MaterialTheme.typography.bodyMedium,
                color = if (result?.success == false && !busy) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            if (result != null && !busy) SelectionContainer {
                Text(result.output, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun ActionResultDialog40(result: PixelActionResult40?, busy: Boolean) {
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(result) { visible = result != null }
    if (visible && result != null && !busy) {
        AlertDialog(
            onDismissRequest = { visible = false },
            title = { Text(stringResource(if (result.success) R.string.pixel40_action_success else R.string.pixel40_action_partial)) },
            text = {
                SelectionContainer {
                    Text(result.output, modifier = Modifier.heightIn(max = 300.dp).verticalScroll(rememberScrollState()),
                        style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                }
            },
            confirmButton = { TextButton(onClick = { visible = false }) { Text(stringResource(R.string.pixel40_action_close)) } },
        )
    }
}

@Composable
private fun ActionWarning40(@StringRes text: Int) {
    Text(stringResource(text), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.fillMaxWidth().iosGlass(shape = MaterialTheme.shapes.medium).padding(16.dp))
}

/** Preview supplies inert callbacks; the real screen supplies explicit root actions. */
@Composable
fun PixelControl40Page(canAct: Boolean, busy: Boolean, result: PixelActionResult40?, onAction: (String) -> Unit, onBack: () -> Unit) {
    var pending by remember { mutableStateOf<PendingAction40?>(null) }
    BackHandler(enabled = busy) { /* let the in-flight root action finish */ }
    ActionConfirmation40(pending, onCancel = { pending = null }, onConfirm = { action -> pending = null; onAction(action) })
    ActionResultDialog40(result, busy)
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Scaffold(
        containerColor = Color.Transparent,
        topBar = { GlassTopBar(stringResource(R.string.pixel40_control_title), stringResource(R.string.pixel40_control_subtitle), onBack = { if (!busy) onBack() }) },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp).padding(bottom = bottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            ActionWarning40(R.string.pixel40_control_warning)
            IosGroup {
                IosRow(Icons.Rounded.Speed, IosCyanDark, stringResource(R.string.pixel40_control_daily),
                    subtitle = stringResource(R.string.pixel40_control_daily_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("profile_daily", R.string.pixel40_control_daily, R.string.pixel40_control_warning) })
                IosGroupDivider()
                IosRow(Icons.Rounded.Bolt, IosOrangeDark, stringResource(R.string.pixel40_control_gaming),
                    subtitle = stringResource(R.string.pixel40_control_gaming_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("profile_gaming", R.string.pixel40_control_gaming, R.string.pixel40_control_warning) })
                IosGroupDivider()
                IosRow(Icons.Rounded.Restore, IosCyanDark, stringResource(R.string.pixel40_control_restore),
                    subtitle = stringResource(R.string.pixel40_control_restore_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("profile_revert", R.string.pixel40_control_restore, R.string.pixel40_control_restore_warning) })
            }
            ActionResult40(result, busy, canAct)
        }
    }
}

@Composable
fun PixelBoost40Page(canAct: Boolean, busy: Boolean, result: PixelActionResult40?, onAction: (String) -> Unit, onBack: () -> Unit) {
    var pending by remember { mutableStateOf<PendingAction40?>(null) }
    var gain by rememberSaveable { mutableFloatStateOf(88f) }
    BackHandler(enabled = busy) { }
    ActionConfirmation40(pending, onCancel = { pending = null }, onConfirm = { action -> pending = null; onAction(action) })
    ActionResultDialog40(result, busy)
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Scaffold(
        containerColor = Color.Transparent,
        topBar = { GlassTopBar(stringResource(R.string.pixel40_boost_title), stringResource(R.string.pixel40_boost_subtitle), onBack = { if (!busy) onBack() }) },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp).padding(bottom = bottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            ActionWarning40(R.string.pixel40_boost_warning)
            IosGroup(footer = stringResource(R.string.pixel40_boost_conflicts)) {
                IosRow(Icons.Rounded.NetworkCheck, IosCyanDark, stringResource(R.string.pixel40_boost_network),
                    subtitle = stringResource(R.string.pixel40_boost_network_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("network_apply", R.string.pixel40_boost_network, R.string.pixel40_boost_warning) })
                IosGroupDivider()
                IosRow(Icons.Rounded.Restore, IosCyanDark, stringResource(R.string.pixel40_boost_restore_network),
                    enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("network_restore", R.string.pixel40_boost_restore_network, R.string.pixel40_boost_conflicts) })
                IosGroupDivider()
                IosRow(Icons.Rounded.VolumeUp, IosPinkDark, stringResource(R.string.pixel40_boost_audio),
                    subtitle = stringResource(R.string.pixel40_boost_audio_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("audio_apply:${gain.roundToInt()}", R.string.pixel40_boost_audio, R.string.pixel40_boost_warning) })
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(stringResource(R.string.pixel40_boost_gain), style = MaterialTheme.typography.bodyMedium)
                        Text(gain.roundToInt().toString(), style = MaterialTheme.typography.labelLarge)
                    }
                    Slider(value = gain, onValueChange = { gain = it }, valueRange = 84f..96f, steps = 11, enabled = canAct && !busy)
                }
                IosGroupDivider()
                IosRow(Icons.Rounded.Restore, IosCyanDark, stringResource(R.string.pixel40_boost_restore_audio),
                    enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("audio_restore", R.string.pixel40_boost_restore_audio, R.string.pixel40_boost_conflicts) })
            }
            IosGroup(title = stringResource(R.string.pixel40_boost_legacy), footer = stringResource(R.string.pixel40_boost_legacy_warning)) {
                IosRow(Icons.Rounded.History, IosOrangeDark, stringResource(R.string.pixel40_boost_legacy),
                    subtitle = stringResource(R.string.pixel40_boost_legacy_sub), enabled = canAct && !busy, showChevron = true,
                    onClick = { onAction("status") })
                IosGroupDivider()
                IosRow(Icons.Rounded.Restore, IosOrangeDark, stringResource(R.string.pixel40_boost_remove_legacy),
                    enabled = canAct && !busy, showChevron = true,
                    onClick = { pending = PendingAction40("remove_legacy", R.string.pixel40_boost_remove_legacy, R.string.pixel40_boost_legacy_warning) })
            }
            ActionResult40(result, busy, canAct)
        }
    }
}
