package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.system.Os
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.ui.pixel.Diagnostics40
import com.rifsxd.ksunext.ui.pixel.PixelActionResult40
import com.rifsxd.ksunext.ui.pixel.PixelDiagnostics40Page
import com.rifsxd.ksunext.ui.pixel.ProviderCandidate40
import com.rifsxd.ksunext.ui.pixel.knownProvider40
import com.rifsxd.ksunext.ui.util.createRootShell
import com.rifsxd.ksunext.ui.util.runPixelAction40
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File

/** Supports both Native Synthetica KernelSU and Universal Root Bridge on other kernels. */
private suspend fun readDiagnostics40(context: Context): Diagnostics40 = withContext(Dispatchers.IO) {
    val unameRel = runCatching { Os.uname().release }.getOrDefault("unknown")
    val isNativeKsu = Natives.isManager && Natives.isFullFeatured()
    runCatching {
        val daemon = File(context.applicationInfo.nativeLibraryDir, "libksud.so").absolutePath
        require('\'' !in daemon && '\n' !in daemon)
        createRootShell(true).use { shell ->
            fun query(command: String): String? {
                val stdout = ArrayList<String>()
                val stderr = ArrayList<String>()
                val result = shell.newJob().add(command).to(stdout, stderr).exec()
                if (!result.isSuccess) return null
                return stdout.joinToString("\n").take(512_001).trim()
            }
            if (query("id -u") != "0") {
                return@use Diagnostics40(
                    loading = false,
                    rootAccessible = false,
                    kernelModeLabel = "Read-Only Mode (No Root) · $unameRel",
                )
            }
            val quoted = "'$daemon'"
            val supported = query("$quoted susfs support") == "Supported"
            val version = if (supported) query("$quoted susfs version")?.take(128)?.takeIf { it.isNotBlank() } else null
            val variant = if (supported) query("$quoted susfs variant")?.take(128)?.takeIf { it.isNotBlank() } else null
            val features = if (supported) query("$quoted susfs features")?.take(8192)?.takeIf { it.isNotBlank() } else null
            val modules = query("$quoted module list")?.takeIf { it.length <= 512_000 }?.let { json ->
                runCatching {
                    val array = JSONArray(json)
                    require(array.length() <= 4096)
                    (0 until array.length()).mapNotNull { index ->
                        val entry = array.optJSONObject(index) ?: return@mapNotNull null
                        val id = entry.optString("id", "").filterNot { it.isISOControl() }.take(100)
                        val name = entry.optString("name", "").filterNot { it.isISOControl() }.take(100).ifBlank { id }
                        if (!knownProvider40(id, name)) return@mapNotNull null
                        ProviderCandidate40(id, name, entry.optBoolean("enabled", false) && !entry.optBoolean("remove", false))
                    }.distinctBy { it.id }
                }.getOrNull()
            }
            val modeLabel = if (isNativeKsu) {
                "Native Synthetica KernelSU (UAPI v4) · $unameRel"
            } else {
                "Universal Root Bridge (UID 0) · $unameRel"
            }
            Diagnostics40(
                loading = false,
                rootAccessible = true,
                susfsReported = supported,
                susfsVersion = version,
                susfsVariant = variant,
                susfsFeatures = features,
                zygiskProcessFlag = if (isNativeKsu) runCatching { Natives.isZygiskEnabled() }.getOrNull() else null,
                providers = modules,
                kernelModeLabel = modeLabel,
            )
        }
    }.getOrElse {
        Diagnostics40(
            loading = false,
            rootAccessible = false,
            kernelModeLabel = "Read-Only Mode · $unameRel",
        )
    }
}

@Destination<RootGraph>
@Composable
fun PixelDiagnostics40Screen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var snapshot by remember { mutableStateOf(Diagnostics40()) }
    var logBusy by remember { mutableStateOf(false) }
    var logResult by remember { mutableStateOf<PixelActionResult40?>(null) }
    LaunchedEffect(context) { snapshot = readDiagnostics40(context) }
    PixelDiagnostics40Page(
        snapshot = snapshot,
        onBack = { navigator.popBackStack() },
        onRefresh = {
            snapshot = Diagnostics40()
            scope.launch { snapshot = readDiagnostics40(context) }
        },
        logBusy = logBusy,
        logResult = logResult,
        onRunDiagAction = { action ->
            if (!logBusy && snapshot.rootAccessible) {
                logBusy = true
                logResult = null
                scope.launch {
                    try { logResult = runPixelAction40(context, "universal", action) } finally { logBusy = false }
                }
            }
        },
    )
}
