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
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.ui.theme.brutalPlate
import com.rifsxd.ksunext.ui.util.createRootShell
import com.rifsxd.ksunext.ui.util.rootAvailable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

private val boostMutex = Mutex()
private data class BoostResult(val success: Boolean, val output: String)

private suspend fun runBoost(context: Context, action: String, gain: Int = 88): BoostResult =
    boostMutex.withLock {
        withContext(Dispatchers.IO) {
            val allowed = setOf("status", "network_once", "network_boot_on", "network_boot_off", "audio_once", "audio_boot_on", "audio_boot_off")
            if (action !in allowed || gain !in 84..96) return@withContext BoostResult(false, "Invalid action")
            runCatching {
                val script = context.assets.open("synthetica-boost-compat.sh").bufferedReader().use { it.readText() }
                require(!script.lineSequence().any { it == "SYNTHETICA_BOOST_SCRIPT" })
                val command = "sh -s -- '$action' '$gain' <<'SYNTHETICA_BOOST_SCRIPT'\n$script\nSYNTHETICA_BOOST_SCRIPT"
                createRootShell(true).use { sh ->
                    val out = ArrayList<String>()
                    val err = ArrayList<String>()
                    val result = sh.newJob().add(command).to(out, err).exec()
                    BoostResult(result.isSuccess, (out + err).takeLast(12).joinToString("\n").ifBlank { "No output" })
                }
            }.getOrElse { BoostResult(false, "Root shell or boost helper unavailable") }
        }
    }

@OptIn(ExperimentalMaterial3Api::class)
@Destination<RootGraph>
@Composable
fun BoostLegacyScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var rooted by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var gain by remember { mutableFloatStateOf(88f) }
    var status by remember { mutableStateOf("Status not checked") }
    var resultText by remember { mutableStateOf("No changes applied") }

    suspend fun refreshStatus() {
        rooted = withContext(Dispatchers.IO) { runCatching { rootAvailable() }.getOrDefault(false) }
        status = if (rooted) runBoost(context, "status").output else "Root unavailable; existing startup scripts were not checked."
    }
    LaunchedEffect(Unit) { refreshStatus() }

    fun execute(action: String) {
        if (busy || !rooted) return
        busy = true
        scope.launch {
            val result = runBoost(context, action, gain.roundToInt())
            resultText = (if (result.success) "FINISHED" else "PARTIAL / FAILED") + "\n" + result.output
            refreshStatus()
            busy = false
        }
    }

    val bottomPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text("NETWORK / AUDIO BOOST") },
                navigationIcon = {
                    IconButton(onClick = { navigator.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { inner ->
        Column(
            modifier = Modifier.fillMaxSize().padding(inner).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp).padding(bottom = bottomPadding + 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Card(modifier = Modifier.fillMaxWidth().brutalPlate(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("SYNTHETICA 2.0 BOOST COMPATIBILITY", style = MaterialTheme.typography.titleSmall)
                    Text("Startup script presence is not proof that a tweak is active. Changes are made only when a button is pressed.", style = MaterialTheme.typography.bodySmall)
                    Text(status, style = MaterialTheme.typography.bodySmall)
                    OutlinedButton(enabled = !busy, onClick = { scope.launch { refreshStatus() } }) { Text("REFRESH") }
                }
            }
            Card(modifier = Modifier.fillMaxWidth().brutalPlate(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("NETWORK / WI-FI", style = MaterialTheme.typography.titleSmall)
                    Text("Uses the existing Synthetica TCP/Wi-Fi targets. Support varies by ROM; disabling startup does not restore live values.", style = MaterialTheme.typography.bodySmall)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(modifier = Modifier.weight(1f), enabled = rooted && !busy, onClick = { execute("network_once") }) { Text("APPLY ONCE") }
                        OutlinedButton(modifier = Modifier.weight(1f), enabled = rooted && !busy, onClick = { execute("network_boot_on") }) { Text("ON BOOT") }
                    }
                    OutlinedButton(enabled = rooted && !busy, onClick = { execute("network_boot_off") }) { Text("REMOVE STARTUP SCRIPT") }
                }
            }
            Card(modifier = Modifier.fillMaxWidth().brutalPlate(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("AUDIO / TINYMIX :: ${gain.roundToInt()}", style = MaterialTheme.typography.titleSmall)
                    Text("Codec controls and gain limits differ by ROM. Higher gain can distort audio or harm speakers; use cautiously. Removing startup does not reset the current mixer.", style = MaterialTheme.typography.bodySmall)
                    Slider(value = gain, onValueChange = { gain = it }, valueRange = 84f..96f, steps = 11, enabled = rooted && !busy)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(modifier = Modifier.weight(1f), enabled = rooted && !busy, onClick = { execute("audio_once") }) { Text("APPLY ONCE") }
                        OutlinedButton(modifier = Modifier.weight(1f), enabled = rooted && !busy, onClick = { execute("audio_boot_on") }) { Text("ON BOOT") }
                    }
                    OutlinedButton(enabled = rooted && !busy, onClick = { execute("audio_boot_off") }) { Text("REMOVE STARTUP SCRIPT") }
                }
            }
            Card(modifier = Modifier.fillMaxWidth().brutalPlate(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(16.dp)) {
                    Text("RESULT", style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    Text(resultText, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
