package com.rifsxd.ksunext.ui.screen

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.GraphicEq
import androidx.compose.material.icons.rounded.NetworkCheck
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import androidx.lifecycle.compose.dropUnlessResumed
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosSwitchRow
import com.rifsxd.ksunext.ui.theme.IosTeal
import com.rifsxd.ksunext.ui.util.LocalSnackbarHost
import com.rifsxd.ksunext.ui.util.rootAvailable
import com.topjohnwu.superuser.Shell
import kotlin.math.roundToInt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val BOOST_SCRIPT = "/data/adb/service.d/synthetica-boost.sh"
private const val LEGACY_BOOST_SCRIPT = "/data/adb/service.d/rc-boost.sh"
private const val SOUND_SCRIPT = "/data/adb/service.d/synthetica-sound.sh"
private const val LEGACY_SOUND_SCRIPT = "/data/adb/service.d/rc-sound.sh"

@Destination<RootGraph>
@Composable
fun BoostScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("synthetica_boost", Context.MODE_PRIVATE) }
    val snackBarHost = LocalSnackbarHost.current
    val scope = rememberCoroutineScope()

    var hasRoot by remember { mutableStateOf(rootAvailable()) }
    var wifiBoost by rememberSaveable { mutableStateOf(prefs.getBoolean("wifi_boost", false)) }
    var soundBoost by rememberSaveable { mutableStateOf(prefs.getBoolean("sound_boost", false)) }
    var soundGain by rememberSaveable { mutableFloatStateOf(prefs.getInt("sound_gain", 88).toFloat()) }

    var tcpCongestion by remember { mutableStateOf("—") }
    var wifiPowerSave by remember { mutableStateOf("—") }

    suspend fun refreshStatus() = withContext(Dispatchers.IO) {
        val rooted = rootAvailable()
        hasRoot = rooted
        if (!rooted) return@withContext
        val tcpOut = Shell.cmd("cat /proc/sys/net/ipv4/tcp_congestion_control 2>/dev/null").exec().out
        val psOut = Shell.cmd("iw dev wlan0 get power_save 2>/dev/null | awk '{print \$NF}'").exec().out
        val scriptExists = Shell.cmd("[ -f $BOOST_SCRIPT ] || [ -f $LEGACY_BOOST_SCRIPT ] && echo 1 || echo 0")
            .exec().out.firstOrNull()?.trim() == "1"
        val soundExists = Shell.cmd("[ -f $SOUND_SCRIPT ] || [ -f $LEGACY_SOUND_SCRIPT ] && echo 1 || echo 0")
            .exec().out.firstOrNull()?.trim() == "1"

        withContext(Dispatchers.Main) {
            tcpCongestion = tcpOut.firstOrNull()?.trim()?.takeIf { it.isNotEmpty() } ?: "cubic"
            wifiPowerSave = psOut.firstOrNull()?.trim()?.takeIf { it.isNotEmpty() } ?: "default"
            if (scriptExists && !wifiBoost) {
                wifiBoost = true
                prefs.edit { putBoolean("wifi_boost", true) }
            }
            if (soundExists && !soundBoost) {
                soundBoost = true
                prefs.edit { putBoolean("sound_boost", true) }
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshStatus()
    }

    fun applyWifiBoost(enable: Boolean) {
        scope.launch(Dispatchers.IO) {
            if (!rootAvailable()) {
                snackBarHost.showSnackbar(context.getString(R.string.synthetica_boost_root_required))
                return@launch
            }
            if (enable) {
                val script = """
                    #!/system/bin/sh
                    # Synthetica 2.0 Userspace Network & Wi-Fi Low-Latency Tuning
                    (
                      sleep 12
                      sysctl -w net.core.rmem_max=8388608 2>/dev/null
                      sysctl -w net.core.wmem_max=8388608 2>/dev/null
                      sysctl -w net.ipv4.tcp_fastopen=3 2>/dev/null
                      sysctl -w net.core.default_qdisc=fq_codel 2>/dev/null
                      if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
                        sysctl -w net.ipv4.tcp_congestion_control=bbr 2>/dev/null
                      fi
                      iw dev wlan0 set power_save off 2>/dev/null
                    ) &
                """.trimIndent()
                Shell.cmd(
                    "mkdir -p /data/adb/service.d",
                    "rm -f $LEGACY_BOOST_SCRIPT",
                    "cat <<'EOF' > $BOOST_SCRIPT\n$script\nEOF",
                    "chmod 0755 $BOOST_SCRIPT",
                    "sysctl -w net.core.rmem_max=8388608 2>/dev/null",
                    "sysctl -w net.core.wmem_max=8388608 2>/dev/null",
                    "sysctl -w net.ipv4.tcp_fastopen=3 2>/dev/null",
                    "iw dev wlan0 set power_save off 2>/dev/null",
                ).exec()
            } else {
                Shell.cmd(
                    "rm -f $BOOST_SCRIPT $LEGACY_BOOST_SCRIPT",
                    "iw dev wlan0 set power_save on 2>/dev/null",
                ).exec()
            }
            prefs.edit { putBoolean("wifi_boost", enable) }
            withContext(Dispatchers.Main) { wifiBoost = enable }
            refreshStatus()
        }
    }

    fun applySoundBoost(enable: Boolean, gain: Int) {
        scope.launch(Dispatchers.IO) {
            if (!rootAvailable()) {
                snackBarHost.showSnackbar(context.getString(R.string.synthetica_boost_root_required))
                return@launch
            }
            val clamped = gain.coerceIn(84, 96)
            if (enable) {
                val script = """
                    #!/system/bin/sh
                    # Synthetica 2.0 Userspace Qualcomm ALSA RX Digital Gain
                    (
                      sleep 15
                      for ctl in 'RX0 Digital Volume' 'RX1 Digital Volume' 'RX2 Digital Volume'; do
                        tinymix "${'$'}ctl" $clamped 2>/dev/null
                      done
                    ) &
                """.trimIndent()
                Shell.cmd(
                    "mkdir -p /data/adb/service.d",
                    "rm -f $LEGACY_SOUND_SCRIPT",
                    "cat <<'EOF' > $SOUND_SCRIPT\n$script\nEOF",
                    "chmod 0755 $SOUND_SCRIPT",
                    "tinymix 'RX0 Digital Volume' $clamped 2>/dev/null",
                    "tinymix 'RX1 Digital Volume' $clamped 2>/dev/null",
                    "tinymix 'RX2 Digital Volume' $clamped 2>/dev/null",
                ).exec()
            } else {
                Shell.cmd(
                    "rm -f $SOUND_SCRIPT $LEGACY_SOUND_SCRIPT",
                    "tinymix 'RX0 Digital Volume' 84 2>/dev/null",
                    "tinymix 'RX1 Digital Volume' 84 2>/dev/null",
                    "tinymix 'RX2 Digital Volume' 84 2>/dev/null",
                ).exec()
            }
            prefs.edit {
                putBoolean("sound_boost", enable)
                putInt("sound_gain", clamped)
            }
            withContext(Dispatchers.Main) {
                soundBoost = enable
                soundGain = clamped.toFloat()
            }
        }
    }

    val navBottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            GlassTopBar(
                title = stringResource(R.string.ios_boost_title),
                subtitle = stringResource(R.string.ios_boost_sub),
                onBack = dropUnlessResumed { navigator.popBackStack() },
            )
        },
        snackbarHost = { SnackbarHost(snackBarHost, modifier = Modifier.padding(bottom = navBottom)) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp)
                .padding(bottom = navBottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            IosGroup(
                title = stringResource(R.string.synthetica_boost_network_group),
                footer = stringResource(R.string.synthetica_boost_network_footer),
            ) {
                IosSwitchRow(
                    icon = Icons.Rounded.Wifi,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.synthetica_boost_wifi_title),
                    subtitle = stringResource(R.string.synthetica_boost_wifi_sub),
                    checked = wifiBoost,
                    enabled = hasRoot,
                    onCheckedChange = { applyWifiBoost(it) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Speed,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.synthetica_boost_tcp_cong),
                    pillText = tcpCongestion,
                    pillColor = IosCyanDark,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.NetworkCheck,
                    badgeColor = IosTeal,
                    title = stringResource(R.string.synthetica_boost_wifi_ps),
                    value = wifiPowerSave,
                )
            }

            IosGroup(
                title = stringResource(R.string.synthetica_boost_audio_group),
                footer = stringResource(R.string.synthetica_boost_audio_footer),
            ) {
                IosSwitchRow(
                    icon = Icons.Rounded.VolumeUp,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.synthetica_boost_sound_title),
                    subtitle = stringResource(R.string.synthetica_boost_sound_sub),
                    checked = soundBoost,
                    enabled = hasRoot,
                    onCheckedChange = { applySoundBoost(it, soundGain.roundToInt()) },
                )
                IosGroupDivider()
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = stringResource(R.string.synthetica_boost_sound_level),
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Medium,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                        }
                        IosPill(
                            text = "${soundGain.roundToInt()} / 96",
                            color = IosIndigoDark,
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    Slider(
                        value = soundGain,
                        onValueChange = { soundGain = it },
                        onValueChangeFinished = {
                            if (soundBoost) {
                                applySoundBoost(true, soundGain.roundToInt())
                            } else {
                                prefs.edit { putInt("sound_gain", soundGain.roundToInt()) }
                            }
                        },
                        valueRange = 84f..96f,
                        steps = 11,
                        enabled = hasRoot,
                        colors = SliderDefaults.colors(
                            thumbColor = Color.White,
                            activeTrackColor = MaterialTheme.colorScheme.primary,
                        ),
                    )
                }
            }
        }
    }
}
