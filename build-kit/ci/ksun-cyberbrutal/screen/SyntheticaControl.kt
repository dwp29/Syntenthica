package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.system.Os
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.destinations.BoostLegacyScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.rememberScrollConnection
import com.rifsxd.ksunext.ui.theme.BRUTAL_CYAN
import com.rifsxd.ksunext.ui.theme.BRUTAL_INK
import com.rifsxd.ksunext.ui.theme.BRUTAL_SIGNAL
import com.rifsxd.ksunext.ui.theme.BRUTAL_VOLT
import com.rifsxd.ksunext.ui.theme.BrutalStaggerItem
import com.rifsxd.ksunext.ui.theme.DepartureBoardText
import com.rifsxd.ksunext.ui.theme.FadeInText
import com.rifsxd.ksunext.ui.theme.SyntheticaDepartureAnimState
import com.rifsxd.ksunext.ui.theme.SyntheticaThemeModeState
import com.rifsxd.ksunext.ui.theme.brutalPlate
import com.rifsxd.ksunext.ui.theme.setSyntheticaDepartureAnim
import com.rifsxd.ksunext.ui.theme.setSyntheticaThemeMode
import com.rifsxd.ksunext.ui.util.createRootShell
import com.rifsxd.ksunext.ui.util.getSuSFS
import com.rifsxd.ksunext.ui.util.getSuSFSVersion
import com.rifsxd.ksunext.ui.util.rootAvailable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

private data class TelemetryState(
    val hasRoot: Boolean = false,
    val uname: String = "--",
    val cpuGov: String = "--",
    val cpuFreqSummary: String = "--",
    val gpuLevel: String = "--",
    val gpuNumLevels: Int = 0,
    val gpuMinIdx: Int = -1,
    val tempC: String = "--",
    val swappiness: String = "--",
    val pageCluster: String = "--",
    val zramInfo: String = "--",
    val ioSched: String = "--",
    val ioAvailable: List<String> = emptyList(),
    val selinux: String = "--",
    val susfsStatus: String = "--",
    val installLogTitle: String = "NO INSTALL LOG FOUND",
    val installLogBody: String = "Flash Synthetica 2.0+ in recovery to generate /sdcard/Synthetica/install-log-*.txt",
)

private fun runShellLines(script: String): List<String> {
    return runCatching {
        createRootShell(true).use { sh ->
            val out = ArrayList<String>()
            sh.newJob().add(script).to(out, null).exec()
            out
        }
    }.getOrDefault(emptyList())
}

private suspend fun readTelemetrySnapshot(): TelemetryState = withContext(Dispatchers.IO) {
    val unameRel = runCatching { Os.uname().release }.getOrDefault("unknown")
    val rooted = runCatching { rootAvailable() }.getOrDefault(false)

    // Non-root fallback for install logs if readable on sdcard
    var logTitle = "NO INSTALL LOG FOUND"
    var logBody = "No /sdcard/Synthetica/install-log-*.txt detected yet."
    runCatching {
        val dir = File("/sdcard/Synthetica")
        val latest = dir.listFiles { f -> f.name.startsWith("install-log-") && f.name.endsWith(".txt") }
            ?.maxByOrNull { it.lastModified() }
        if (latest != null && latest.canRead()) {
            logTitle = latest.name
            logBody = latest.readText().trim().take(1500)
        }
    }

    if (!rooted) {
        return@withContext TelemetryState(
            hasRoot = false,
            uname = unameRel,
            cpuGov = "LOCKED",
            cpuFreqSummary = "ROOT REQUIRED",
            gpuLevel = "LOCKED",
            tempC = "--",
            swappiness = "--",
            pageCluster = "--",
            zramInfo = "--",
            ioSched = "--",
            selinux = "UNKNOWN",
            susfsStatus = "UNVERIFIED",
            installLogTitle = logTitle,
            installLogBody = logBody,
        )
    }

    val probe = """
        GOV=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null || cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "--")
        F0=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq 2>/dev/null || echo 0)
        F6=$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq 2>/dev/null || echo 0)
        GMIN=$(cat /sys/class/kgsl/kgsl-3d0/min_pwrlevel 2>/dev/null || echo -1)
        GNUM=$(cat /sys/class/kgsl/kgsl-3d0/num_pwrlevels 2>/dev/null || echo 0)
        GCUR=$(cat /sys/class/kgsl/kgsl-3d0/default_pwrlevel 2>/dev/null || echo "${'$'}GMIN")
        TRAW=$(cat /sys/class/power_supply/battery/temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
        SWAP=$(cat /proc/sys/vm/swappiness 2>/dev/null || echo "--")
        PCLS=$(cat /proc/sys/vm/page-cluster 2>/dev/null || echo "--")
        ZDISK=$(cat /sys/block/zram0/disksize 2>/dev/null || echo 0)
        ZMM=$(cat /sys/block/zram0/mm_stat 2>/dev/null | awk '{print $1" "$2}' || echo "0 0")
        IOS=$(cat /sys/block/sda/queue/scheduler 2>/dev/null || cat /sys/block/mmcblk0/queue/scheduler 2>/dev/null || echo "--")
        SEL=$(getenforce 2>/dev/null || echo "Unknown")
        LFILE=$(ls -1t /sdcard/Synthetica/install-log-*.txt /data/media/0/Synthetica/install-log-*.txt 2>/dev/null | head -n 1)
        echo "GOV=${'$'}GOV"
        echo "FREQ=${'$'}((F0/1000))/${'$'}((F6/1000))MHz"
        echo "GPU=${'$'}GMIN/${'$'}GNUM"
        echo "TEMP=${'$'}TRAW"
        echo "SWAP=${'$'}SWAP"
        echo "PCLS=${'$'}PCLS"
        echo "ZDISK=${'$'}ZDISK"
        echo "ZMM=${'$'}ZMM"
        echo "IOS=${'$'}IOS"
        echo "SEL=${'$'}SEL"
        echo "LFILE=${'$'}LFILE"
        if [ -n "${'$'}LFILE" ] && [ -f "${'$'}LFILE" ]; then
            echo "---LOG_BEGIN---"
            head -n 30 "${'$'}LFILE"
            echo "---LOG_END---"
        fi
    """.trimIndent()

    val lines = runShellLines(probe)
    val kv = HashMap<String, String>()
    val logLines = ArrayList<String>()
    var inLog = false
    for (line in lines) {
        if (line == "---LOG_BEGIN---") {
            inLog = true
            continue
        }
        if (line == "---LOG_END---") {
            inLog = false
            continue
        }
        if (inLog) {
            logLines.add(line)
        } else {
            val idx = line.indexOf('=')
            if (idx > 0) {
                kv[line.substring(0, idx)] = line.substring(idx + 1).trim()
            }
        }
    }

    val gpuParts = (kv["GPU"] ?: "-1/0").split("/")
    val gMin = gpuParts.getOrNull(0)?.toIntOrNull() ?: -1
    val gNum = (gpuParts.getOrNull(1)?.toIntOrNull() ?: 0).coerceIn(0, 32)

    val tempRaw = kv["TEMP"]?.toLongOrNull() ?: 0L
    val tempFmt = when {
        tempRaw > 1000L -> String.format("%.1f C", tempRaw / 1000.0)
        tempRaw > 100L -> String.format("%.1f C", tempRaw / 10.0)
        tempRaw > 0L -> "$tempRaw C"
        else -> "--"
    }

    val zDiskBytes = kv["ZDISK"]?.toLongOrNull() ?: 0L
    val zMmParts = (kv["ZMM"] ?: "0 0").split(" ")
    val zOrigBytes = zMmParts.getOrNull(0)?.toLongOrNull() ?: 0L
    val zramFmt = if (zDiskBytes > 0L) {
        val usedMb = zOrigBytes / (1024L * 1024L)
        val totalMb = zDiskBytes / (1024L * 1024L)
        "${usedMb}M / ${totalMb}M"
    } else {
        "UNAVAILABLE"
    }

    val schedRaw = kv["IOS"] ?: "--"
    val activeSched = Regex("\\[([^]]+)]").find(schedRaw)?.groupValues?.getOrNull(1) ?: schedRaw
    val availScheds = schedRaw.replace("[", "").replace("]", "")
        .split(Regex("\\s+")).filter { it.isNotBlank() && it != "--" }

    val susfs = runCatching {
        val s = getSuSFS().trim()
        if (s.equals("Supported", ignoreCase = true)) {
            val v = getSuSFSVersion().trim()
            if (v.isNotEmpty()) "SUPPORTED // $v" else "SUPPORTED"
        } else {
            "UNVERIFIED"
        }
    }.getOrDefault("UNVERIFIED")

    val lfile = kv["LFILE"].orEmpty()
    if (lfile.isNotEmpty() && logLines.isNotEmpty()) {
        logTitle = lfile.substringAfterLast('/')
        logBody = logLines.joinToString("\n")
    }

    TelemetryState(
        hasRoot = true,
        uname = unameRel,
        cpuGov = (kv["GOV"] ?: "--").uppercase(),
        cpuFreqSummary = kv["FREQ"] ?: "--",
        gpuLevel = if (gNum > 0 && gMin >= 0) "PWR L$gMin (0..${gNum - 1})" else "UNAVAILABLE",
        gpuNumLevels = gNum,
        gpuMinIdx = if (gNum > 0) gMin.coerceIn(0, gNum - 1) else -1,
        tempC = tempFmt,
        swappiness = kv["SWAP"] ?: "--",
        pageCluster = kv["PCLS"] ?: "--",
        zramInfo = zramFmt,
        ioSched = activeSched.uppercase(),
        ioAvailable = availScheds,
        selinux = (kv["SEL"] ?: "UNKNOWN").uppercase(),
        susfsStatus = susfs.uppercase(),
        installLogTitle = logTitle,
        installLogBody = logBody,
    )
}

/** Runtime-only, opt-in controls. The bundled helper verifies each write and records originals. */
private data class ControlResult(val success: Boolean, val message: String)
private val controlActionMutex = Mutex()

private suspend fun applyControlAction(context: Context, action: String): ControlResult =
    controlActionMutex.withLock {
        withContext(Dispatchers.IO) {
            val permitted = Regex("(?:profile_(?:daily|gaming|revert)|swap:(?:40|60|80|100)|pcls:[03]|gpu:[0-7]|ios:[A-Za-z0-9_-]{1,32})")
            if (!permitted.matches(action)) {
                return@withContext ControlResult(false, "REJECTED // unsupported control action")
            }
            runCatching {
                val script = context.assets.open("synthetica-control.sh").bufferedReader().use { it.readText() }
                require(!script.lineSequence().any { it == "SYNTHETICA_CONTROL_SCRIPT" })
                val command = "sh -s -- '$action' <<'SYNTHETICA_CONTROL_SCRIPT'\n$script\nSYNTHETICA_CONTROL_SCRIPT"
                createRootShell(true).use { sh ->
                    val out = ArrayList<String>()
                    val err = ArrayList<String>()
                    val result = sh.newJob().add(command).to(out, err).exec()
                    val summary = (out + err).takeLast(10).joinToString("\n").ifBlank { "No output from root shell" }
                    ControlResult(result.isSuccess, summary)
                }
            }.getOrElse {
                ControlResult(false, "ERROR // root shell or bundled control script unavailable")
            }
        }
    }

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Destination<RootGraph>
@Composable
fun SyntheticaControlScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior(rememberTopAppBarState())

    val bottomBarScrollState = LocalScrollState.current
    val navBarEnabled = LocalNavBarEnabled.current
    val isNavBarHidden = (bottomBarScrollState?.isScrollingDown?.value ?: false) || (navBarEnabled?.value == false)
    val navBarPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() +
            if (isNavBarHidden) 0.dp else 112.dp

    val bottomBarScrollConnection = if (bottomBarScrollState != null) {
        rememberScrollConnection(
            isScrollingDown = bottomBarScrollState.isScrollingDown,
            scrollOffset = bottomBarScrollState.scrollOffset,
            previousScrollOffset = bottomBarScrollState.previousScrollOffset,
            threshold = 30f
        )
    } else null

    var telemetry by remember { mutableStateOf(TelemetryState()) }
    var boardTrigger by remember { mutableIntStateOf(0) }
    var consoleMsg by remember { mutableStateOf("SYS.READY // NO CHANGES APPLIED") }
    var activeProfile by remember { mutableStateOf("UNVERIFIED") }

    LaunchedEffect(boardTrigger) {
        telemetry = readTelemetrySnapshot()
    }

    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.4f
    val accent = if (isDark) BRUTAL_VOLT else BRUTAL_SIGNAL
    val subAccent = if (isDark) BRUTAL_CYAN else BRUTAL_INK

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    scrolledContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)
                ),
                title = {
                    Column {
                        DepartureBoardText(
                            text = "SYNTHETICA // CTRL",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Black,
                            triggerKey = boardTrigger
                        )
                        FadeInText(
                            text = "CYBERBRUTAL TELEMETRY & RUNTIME ENGINE",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            triggerKey = boardTrigger
                        )
                    }
                },
                actions = {
                    IconButton(onClick = {
                        consoleMsg = "RESCANNING KERNEL NODES..."
                        boardTrigger++
                    }) {
                        Icon(
                            imageVector = Icons.Filled.Refresh,
                            contentDescription = "Scan",
                            tint = accent
                        )
                    }
                },
                windowInsets = WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal),
                scrollBehavior = scrollBehavior
            )
        },
        contentWindowInsets = WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .let { mod ->
                    if (bottomBarScrollConnection != null) {
                        mod.nestedScroll(bottomBarScrollConnection)
                            .nestedScroll(scrollBehavior.nestedScrollConnection)
                    } else {
                        mod.nestedScroll(scrollBehavior.nestedScrollConnection)
                    }
                }
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp)
                .padding(bottom = navBarPadding),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // 01: LIVE TELEMETRY DEPARTURE BOARD
            BrutalStaggerItem(index = 0, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(active = true),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Filled.Speed, null, tint = accent, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = "[01] DEPARTURE TELEMETRY",
                                    style = MaterialTheme.typography.labelLarge,
                                    color = accent
                                )
                            }
                            Box(
                                modifier = Modifier
                                    .border(1.dp, MaterialTheme.colorScheme.outline)
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                DepartureBoardText(
                                    text = if (telemetry.hasRoot) "ROOT:ONLINE" else "READ-ONLY",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = subAccent,
                                    triggerKey = boardTrigger
                                )
                            }
                        }

                        TelemetryRow("KERNEL", telemetry.uname, 20, boardTrigger)
                        TelemetryRow("CPU GOV", telemetry.cpuGov, 55, boardTrigger)
                        TelemetryRow("CLUSTER", telemetry.cpuFreqSummary, 90, boardTrigger)
                        TelemetryRow("ADRENO", telemetry.gpuLevel, 125, boardTrigger)
                        TelemetryRow("THERMAL", telemetry.tempC, 160, boardTrigger)
                        TelemetryRow("ZRAM", telemetry.zramInfo, 195, boardTrigger)
                        TelemetryRow("I/O BUS", telemetry.ioSched, 230, boardTrigger)
                    }
                }
            }

            // 02: RUNTIME PERFORMANCE PROFILE
            BrutalStaggerItem(index = 1, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(active = activeProfile == "GAMING"),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Bolt, null, tint = accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "[02] RUNTIME PROFILE // OPT-IN",
                                style = MaterialTheme.typography.labelLarge,
                                color = accent
                            )
                        }
                        FadeInText(
                            text = "Gaming raises CPU/GPU floors and may increase heat and battery use. REVERT restores saved values where possible.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            BrutalActionButton(
                                label = "DAILY",
                                selected = activeProfile == "DAILY",
                                enabled = telemetry.hasRoot,
                                modifier = Modifier.weight(1f)
                            ) {
                                scope.launch {
                                    val result = applyControlAction(context, "profile_daily")
                                    consoleMsg = result.message
                                    activeProfile = if (result.success) "DAILY" else "UNVERIFIED"
                                    boardTrigger++
                                }
                            }
                            BrutalActionButton(
                                label = "GAMING",
                                selected = activeProfile == "GAMING",
                                enabled = telemetry.hasRoot,
                                modifier = Modifier.weight(1f)
                            ) {
                                scope.launch {
                                    val result = applyControlAction(context, "profile_gaming")
                                    consoleMsg = result.message
                                    activeProfile = if (result.success) "GAMING" else "UNVERIFIED"
                                    boardTrigger++
                                }
                            }
                            BrutalActionButton(
                                label = "REVERT",
                                selected = false,
                                enabled = telemetry.hasRoot,
                                modifier = Modifier.weight(1f)
                            ) {
                                scope.launch {
                                    val result = applyControlAction(context, "profile_revert")
                                    consoleMsg = result.message
                                    activeProfile = if (result.success) "UNVERIFIED" else "UNVERIFIED"
                                    boardTrigger++
                                }
                            }
                        }
                    }
                }
            }

            // 03: MEMORY, ZRAM, GPU & I/O TUNABLES
            BrutalStaggerItem(index = 2, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Memory, null, tint = accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "[03] MEMORY / GPU / I/O MATRIX",
                                style = MaterialTheme.typography.labelLarge,
                                color = accent
                            )
                        }

                        // Swappiness presets
                        Text(
                            text = "VM.SWAPPINESS :: CURRENT [${telemetry.swappiness}]",
                            style = MaterialTheme.typography.labelMedium
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            for (sw in listOf("40", "60", "80", "100")) {
                                BrutalActionButton(
                                    label = sw,
                                    selected = telemetry.swappiness == sw,
                                    enabled = telemetry.hasRoot,
                                    modifier = Modifier.weight(1f)
                                ) {
                                    scope.launch {
                                        val result = applyControlAction(context, "swap:$sw")
                                        consoleMsg = result.message
                                        activeProfile = if (result.success) "CUSTOM" else "UNVERIFIED"
                                        boardTrigger++
                                    }
                                }
                            }
                        }

                        // ZRAM page-cluster low-latency toggle
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "ZRAM ZERO-READAHEAD (PAGE-CLUSTER 0)",
                                    style = MaterialTheme.typography.labelMedium
                                )
                                Text(
                                    text = "Cuts random swap latency for 6GB multitasking & camera",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Switch(
                                checked = telemetry.pageCluster == "0",
                                enabled = telemetry.hasRoot,
                                onCheckedChange = { on ->
                                    scope.launch {
                                        val result = applyControlAction(context, "pcls:${if (on) 0 else 3}")
                                        consoleMsg = result.message
                                        activeProfile = if (result.success) "CUSTOM" else "UNVERIFIED"
                                        boardTrigger++
                                    }
                                }
                            )
                        }

                        // Adreno GPU Min Powerlevel
                        Text(
                            text = if (telemetry.gpuNumLevels > 0) "ADRENO MIN_PWRLEVEL (0..${telemetry.gpuNumLevels - 1})" else "ADRENO POWER LEVELS UNAVAILABLE",
                            style = MaterialTheme.typography.labelMedium
                        )
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            for (lvl in 0 until telemetry.gpuNumLevels.coerceIn(0, 8)) {
                                BrutalChip(
                                    text = "L$lvl",
                                    selected = telemetry.gpuMinIdx == lvl,
                                    enabled = telemetry.hasRoot
                                ) {
                                    scope.launch {
                                        val result = applyControlAction(context, "gpu:$lvl")
                                        consoleMsg = result.message
                                        activeProfile = if (result.success) "CUSTOM" else "UNVERIFIED"
                                        boardTrigger++
                                    }
                                }
                            }
                        }

                        // I/O Scheduler
                        if (telemetry.ioAvailable.isNotEmpty()) {
                            Text(
                                text = "UFS I/O SCHEDULER",
                                style = MaterialTheme.typography.labelMedium
                            )
                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                for (sched in telemetry.ioAvailable) {
                                    BrutalChip(
                                        text = sched.uppercase(),
                                        selected = telemetry.ioSched.equals(sched, ignoreCase = true),
                                        enabled = telemetry.hasRoot
                                    ) {
                                        scope.launch {
                                            val result = applyControlAction(context, "ios:$sched")
                                        consoleMsg = result.message
                                        activeProfile = if (result.success) "CUSTOM" else "UNVERIFIED"
                                            boardTrigger++
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            OutlinedButton(
                onClick = { navigator.navigate(BoostLegacyScreenDestination) },
                modifier = Modifier.fillMaxWidth(),
                border = BorderStroke(1.dp, accent),
                shape = MaterialTheme.shapes.small
            ) {
                Text("NETWORK / AUDIO BOOST (2.0)", color = accent)
            }

            // 04: observed kernel security status (no bootloader or integrity spoofing)
            BrutalStaggerItem(index = 3, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Security, null, tint = accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "[04] KERNEL SECURITY STATUS",
                                style = MaterialTheme.typography.labelLarge,
                                color = accent
                            )
                        }
                        TelemetryRow("SELINUX", telemetry.selinux, 40, boardTrigger)
                        TelemetryRow("SUSFS", telemetry.susfsStatus, 80, boardTrigger)
                        TelemetryRow("NOMOUNT", "UNVERIFIED", 120, boardTrigger)
                    }
                }
            }

            // 05: CYBERBRUTAL DISPLAY & MOTION ENGINE
            BrutalStaggerItem(index = 4, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(active = true),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Tune, null, tint = accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "[05] CYBERBRUTAL DISPLAY & MOTION",
                                style = MaterialTheme.typography.labelLarge,
                                color = accent
                            )
                        }

                        val curMode = SyntheticaThemeModeState.value
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            listOf(
                                "dark" to "OBSIDIAN DARK",
                                "light" to "INDUSTRIAL LIGHT",
                                "amoled" to "AMOLED PITCH",
                                "auto" to "SYSTEM AUTO"
                            ).forEach { (key, title) ->
                                BrutalChip(
                                    text = title,
                                    selected = curMode == key,
                                    enabled = true
                                ) {
                                    setSyntheticaThemeMode(context, key)
                                    boardTrigger++
                                }
                            }
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "AIRPORT SPLIT-FLAP DEPARTURE TEXT",
                                    style = MaterialTheme.typography.labelMedium
                                )
                                Text(
                                    text = "Mechanical Solari character flip across Modules, Apps & Telemetry",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Switch(
                                checked = SyntheticaDepartureAnimState.value,
                                onCheckedChange = {
                                    setSyntheticaDepartureAnim(context, it)
                                    boardTrigger++
                                }
                            )
                        }

                        OutlinedButton(
                            onClick = {
                                consoleMsg = "SOLARI DEPARTURE BOARD TEST TRIGGERED"
                                boardTrigger++
                            },
                            modifier = Modifier.fillMaxWidth(),
                            border = BorderStroke(1.dp, accent),
                            shape = MaterialTheme.shapes.small
                        ) {
                            Text(
                                text = "[ TEST DEPARTURE BOARD ANIMATION ]",
                                style = MaterialTheme.typography.labelMedium,
                                color = accent
                            )
                        }
                    }
                }
            }

            // 06: CONSOLE + KERNEL INSTALL LOG VIEWER
            BrutalStaggerItem(index = 5, triggerKey = boardTrigger) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .brutalPlate(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Terminal, null, tint = accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "[06] CONSOLE & INSTALL LOG // ${telemetry.installLogTitle}",
                                style = MaterialTheme.typography.labelLarge,
                                color = accent
                            )
                        }
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(MaterialTheme.colorScheme.surfaceContainerLowest)
                                .border(1.dp, MaterialTheme.colorScheme.outline)
                                .padding(12.dp)
                        ) {
                            Text(
                                text = "> $consoleMsg\n\n${telemetry.installLogBody}",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp,
                                lineHeight = 16.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TelemetryRow(
    label: String,
    value: String,
    delayMs: Int,
    triggerKey: Int,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant)
            .padding(horizontal = 10.dp, vertical = 7.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.width(12.dp))
        DepartureBoardText(
            text = value,
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            delayMillis = delayMs,
            charStaggerMs = 18,
            triggerKey = triggerKey
        )
    }
}

@Composable
private fun BrutalActionButton(
    label: String,
    selected: Boolean,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    FilledTonalButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        shape = MaterialTheme.shapes.small,
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp),
        colors = ButtonDefaults.filledTonalButtonColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondaryContainer,
            contentColor = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSecondaryContainer
        )
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Black,
            maxLines = 1
        )
    }
}

@Composable
private fun BrutalChip(
    text: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val bg = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant
    val fg = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface
    Box(
        modifier = Modifier
            .border(1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline)
            .background(bg)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = fg,
            fontWeight = FontWeight.Bold
        )
    }
}
