package com.rifsxd.ksunext.ui.device

import android.app.ActivityManager
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Sensor
import android.hardware.SensorManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.display.DisplayManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.PersistableBundle
import android.os.StatFs
import android.os.SystemClock
import android.system.Os
import android.text.format.DateUtils
import android.text.format.Formatter
import android.view.Display
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Android
import androidx.compose.material.icons.rounded.BatteryChargingFull
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.MonitorHeart
import androidx.compose.material.icons.rounded.Sensors
import androidx.compose.material.icons.rounded.Storage
import androidx.compose.material.icons.rounded.Thermostat
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import java.io.File
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext

private data class CameraInfo(val id: String, val facing: Int?, val focalLengths: List<Float>)
private data class HardwareInfo(
    val model: String?, val device: String?, val android: String?, val securityPatch: String?,
    val kernel: String?, val abi: String?, val hardware: String?, val display: String?,
    val cores: Int, val sensors: List<String>?, val cameras: List<CameraInfo>?,
    val gpuNodes: List<GpuNode>,
)
private data class BatteryInfo(
    val percent: Int?, val temperatureC: Double?, val voltageMv: Int?,
    val currentMa: Double?, val status: Int?,
)
private data class GpuNode(val frequency: File, val governor: File)
private data class PerformanceInfo(
    val load: List<Double>?, val gpuHz: Long?, val gpuGovernor: String?,
    val zramSize: Long?, val zramData: Pair<Long, Long>?,
    val cpuPressure: Double?, val memoryPressure: Double?, val ioPressure: Double?,
)
private data class LiveInfo(
    val battery: BatteryInfo?, val memory: Pair<Long, Long>?, val storage: Pair<Long, Long>?,
    val uptimeSeconds: Long, val frequencies: List<Pair<Int, Long>>, val thermals: List<Pair<String, Double>>?,
    val performance: PerformanceInfo,
)

private fun String?.known(): String? = this?.trim()?.takeIf { it.isNotEmpty() && it.lowercase(Locale.ROOT) != "unknown" }

// These paths are read only, under Android's normal app permissions. Dynamic
// devfreq candidates are discovered once per resumed page, not on each frame.
private fun discoverGpuNodes(): List<GpuNode> {
    val nodes = mutableListOf(
        GpuNode(File("/sys/class/kgsl/kgsl-3d0/gpuclk"), File("/sys/class/kgsl/kgsl-3d0/devfreq/governor")),
        GpuNode(File("/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq"), File("/sys/class/kgsl/kgsl-3d0/devfreq/governor")),
    )
    val candidates = runCatching {
        File("/sys/class/devfreq").listFiles()?.sortedBy { it.name }?.take(64).orEmpty()
    }.getOrDefault(emptyList())
    candidates.filter { it.name.contains("mali", true) || it.name.contains("gpu", true) || it.name.contains("kgsl", true) }
        .forEach { nodes.add(GpuNode(File(it, "cur_freq"), File(it, "governor"))) }
    return nodes.distinctBy { it.frequency.absolutePath }
}

private fun readKernelLine(file: File): String? = runCatching {
    file.bufferedReader().use { it.readLine()?.take(4096) }
}.getOrNull()

private fun readPerformance(nodes: List<GpuNode>): PerformanceInfo {
    var gpuHz: Long? = null
    var governor: String? = null
    for (node in nodes) {
        val hz = parseGpuFrequencyHz(readKernelLine(node.frequency))
        val gov = parseGovernor(readKernelLine(node.governor))
        if (hz != null || gov != null) {
            gpuHz = hz
            governor = gov
            break
        }
    }
    fun pressure(kind: String): Double? = parsePressureAvg10(readKernelLine(File("/proc/pressure/$kind")))
    return PerformanceInfo(
        load = parseLoadAverages(readKernelLine(File("/proc/loadavg"))),
        gpuHz = gpuHz, gpuGovernor = governor,
        zramSize = parseNonNegativeBytes(readKernelLine(File("/sys/block/zram0/disksize"))),
        zramData = parseZramData(readKernelLine(File("/sys/block/zram0/mm_stat"))),
        cpuPressure = pressure("cpu"), memoryPressure = pressure("memory"), ioPressure = pressure("io"),
    )
}

private fun readHardware(context: Context): HardwareInfo {
    val display = runCatching {
        val manager = context.getSystemService(DisplayManager::class.java)
        val active = manager?.getDisplay(Display.DEFAULT_DISPLAY) ?: return@runCatching null
        val mode = active.mode
        "${mode.physicalWidth} × ${mode.physicalHeight} • ${String.format(Locale.getDefault(), "%.1f", active.refreshRate)} Hz"
    }.getOrNull()
    val sensors = runCatching {
        context.getSystemService(SensorManager::class.java)?.getSensorList(Sensor.TYPE_ALL)
            ?.map { listOfNotNull(it.name.known(), it.vendor.known()).joinToString(" • ") }
            ?.filter { it.isNotBlank() }?.distinct()?.sorted()
    }.getOrNull()
    // Only read Camera2 metadata. No camera is opened and no CAMERA permission is requested.
    val cameras = runCatching {
        val manager = context.getSystemService(CameraManager::class.java) ?: return@runCatching null
        manager.cameraIdList.sorted().map { id ->
            val chars = manager.getCameraCharacteristics(id)
            CameraInfo(
                id = id,
                facing = chars.get(CameraCharacteristics.LENS_FACING),
                focalLengths = chars.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)
                    ?.filter { it.isFinite() && it > 0f }?.distinct() ?: emptyList(),
            )
        }
    }.getOrNull()
    return HardwareInfo(
        model = listOfNotNull(Build.MANUFACTURER.known(), Build.MODEL.known()).distinct().joinToString(" ").known(),
        device = Build.DEVICE.known(),
        android = Build.VERSION.RELEASE.known()?.let { "$it • SDK ${Build.VERSION.SDK_INT}" },
        securityPatch = Build.VERSION.SECURITY_PATCH.known(),
        kernel = runCatching { Os.uname().release.known() }.getOrNull(),
        abi = Build.SUPPORTED_ABIS.firstOrNull().known(),
        hardware = Build.HARDWARE.known(), display = display,
        cores = Runtime.getRuntime().availableProcessors(),
        sensors = sensors, cameras = cameras, gpuNodes = discoverGpuNodes(),
    )
}

@Suppress("DEPRECATION")
private fun readBattery(context: Context): BatteryInfo? = runCatching {
    val data = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return@runCatching null
    fun extra(name: String): Int? = data.getIntExtra(name, Int.MIN_VALUE).takeUnless { it == Int.MIN_VALUE }
    val current = context.getSystemService(BatteryManager::class.java)
        ?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        ?.takeUnless { it == Int.MIN_VALUE }
    BatteryInfo(
        percent = checkedPercent(extra(BatteryManager.EXTRA_LEVEL), extra(BatteryManager.EXTRA_SCALE)),
        temperatureC = validBatteryTemperatureTenths(extra(BatteryManager.EXTRA_TEMPERATURE)),
        voltageMv = extra(BatteryManager.EXTRA_VOLTAGE)?.takeIf { it > 0 },
        currentMa = current?.div(1000.0),
        status = extra(BatteryManager.EXTRA_STATUS),
    )
}.getOrNull()

private fun readThermals(): List<Pair<String, Double>>? = runCatching {
    val entries = File("/sys/class/thermal").listFiles { file ->
        file.name.matches(Regex("thermal_zone[0-9]+"))
    } ?: return@runCatching null
    entries.sortedBy { it.name }.take(16).mapNotNull { zone ->
        runCatching zoneRead@ {
            val label = File(zone, "type").bufferedReader().use { it.readLine() }.known() ?: zone.name
            val milli = File(zone, "temp").bufferedReader().use { it.readLine() }?.trim()?.toLongOrNull()
                ?: return@zoneRead null
            if (milli !in -40_000L..200_000L) return@zoneRead null
            label to milli / 1000.0
        }.getOrNull()
    }.takeIf { it.isNotEmpty() }
}.getOrNull()

private fun readLive(context: Context, hardware: HardwareInfo): LiveInfo {
    val memory = runCatching {
        val manager = context.getSystemService(ActivityManager::class.java) ?: return@runCatching null
        val info = ActivityManager.MemoryInfo()
        manager.getMemoryInfo(info)
        val used = checkedUsedBytes(info.totalMem, info.availMem) ?: return@runCatching null
        used to info.totalMem
    }.getOrNull()
    val storage = runCatching {
        val stat = StatFs(Environment.getDataDirectory().absolutePath)
        checkedUsedBytes(stat.totalBytes, stat.availableBytes) ?: return@runCatching null
        stat.availableBytes to stat.totalBytes
    }.getOrNull()
    val frequencies = (0 until hardware.cores.coerceIn(1, 64)).mapNotNull { index ->
        val value = runCatching {
            File("/sys/devices/system/cpu/cpu$index/cpufreq/scaling_cur_freq")
                .bufferedReader().use { it.readLine() }
        }.getOrNull()
        parseCpuFrequencyKHz(value)?.let { index to it }
    }
    return LiveInfo(
        battery = readBattery(context), memory = memory, storage = storage,
        uptimeSeconds = SystemClock.elapsedRealtime() / 1000L,
        frequencies = frequencies, thermals = readThermals(), performance = readPerformance(hardware.gpuNodes),
    )
}

private fun displayBytes(context: Context, pair: Pair<Long, Long>?): String? = pair?.let {
    "${Formatter.formatShortFileSize(context, it.first)} / ${Formatter.formatShortFileSize(context, it.second)}"
}
private fun decimal(value: Double, unit: String): String = "${String.format(Locale.getDefault(), "%.1f", value)} $unit"

/** Read-only diagnostics shared by the actual Manager and the isolated preview. */
@Composable
fun DeviceCheckPage(onBack: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hardware by remember { mutableStateOf<HardwareInfo?>(null) }
    var live by remember { mutableStateOf<LiveInfo?>(null) }
    var showCopyDialog by remember { mutableStateOf(false) }
    LaunchedEffect(context, lifecycleOwner) {
        lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            val staticData = withContext(Dispatchers.IO) { readHardware(context.applicationContext) }
            hardware = staticData
            while (isActive) {
                live = withContext(Dispatchers.IO) { readLive(context.applicationContext, staticData) }
                delay(3_000L)
            }
        }
    }
    val unavailable = stringResource(R.string.device31_unavailable)
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Scaffold(
        containerColor = Color.Transparent,
        topBar = { GlassTopBar(title = stringResource(R.string.device31_title), subtitle = stringResource(R.string.device31_subtitle), onBack = onBack) },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp).padding(bottom = bottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(stringResource(R.string.device31_privacy), color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall)
            if (hardware == null || live == null) {
                IosGroup { IosRow(Icons.Rounded.MonitorHeart, IosCyanDark, stringResource(R.string.device31_loading)) }
            } else {
                val h = hardware!!
                val l = live!!
                val performance = l.performance
                val load = performance.load?.joinToString(" / ") { String.format(Locale.getDefault(), "%.2f", it) } ?: unavailable
                fun pressure(value: Double?): String = value?.let { decimal(it, "%") } ?: unavailable
                fun size(value: Long?): String = value?.let { Formatter.formatShortFileSize(context, it) } ?: unavailable
                val gpu = performance.gpuHz?.let { decimal(it / 1_000_000.0, "MHz") } ?: unavailable
                val zramData = displayBytes(context, performance.zramData) ?: unavailable
                val summarySections = listOf(
                    SummarySection("device", stringResource(R.string.device31_copy_device), listOf(
                        stringResource(R.string.device31_model) to (h.model ?: unavailable),
                        stringResource(R.string.device31_codename) to (h.device ?: unavailable))),
                    SummarySection("system", stringResource(R.string.device31_copy_system), listOf(
                        stringResource(R.string.device31_android) to (h.android ?: unavailable),
                        stringResource(R.string.device31_patch) to (h.securityPatch ?: unavailable),
                        stringResource(R.string.device31_kernel) to (h.kernel ?: unavailable),
                        stringResource(R.string.device31_abi) to (h.abi ?: unavailable))),
                    SummarySection("display", stringResource(R.string.device31_copy_display), listOf(
                        stringResource(R.string.device31_display) to (h.display ?: unavailable))),
                    SummarySection("cpu", stringResource(R.string.device31_copy_cpu), listOf(
                        stringResource(R.string.device31_hardware) to (h.hardware ?: unavailable),
                        stringResource(R.string.device31_core_count) to h.cores.toString())),
                    SummarySection("live", stringResource(R.string.device31_copy_live), listOf(
                        stringResource(R.string.device31_battery) to (l.battery?.percent?.let { "$it%" } ?: unavailable),
                        stringResource(R.string.device31_memory_used) to (displayBytes(context, l.memory) ?: unavailable),
                        stringResource(R.string.device31_storage_used) to (displayBytes(context, l.storage) ?: unavailable),
                        stringResource(R.string.device31_uptime) to DateUtils.formatElapsedTime(l.uptimeSeconds))),
                    SummarySection("performance", stringResource(R.string.device31_copy_performance), listOf(
                        stringResource(R.string.device31_load) to load,
                        stringResource(R.string.device31_gpu_clock) to gpu,
                        stringResource(R.string.device31_gpu_governor) to (performance.gpuGovernor ?: unavailable),
                        stringResource(R.string.device31_zram_size) to size(performance.zramSize),
                        stringResource(R.string.device31_zram_data) to zramData,
                        stringResource(R.string.device31_psi_cpu) to pressure(performance.cpuPressure),
                        stringResource(R.string.device31_psi_memory) to pressure(performance.memoryPressure),
                        stringResource(R.string.device31_psi_io) to pressure(performance.ioPressure))),
                )
                IosGroup {
                    IosRow(Icons.Rounded.ContentCopy, IosBlueDark, stringResource(R.string.device31_copy_title),
                        subtitle = stringResource(R.string.device31_copy_subtitle), showChevron = true,
                        onClick = { showCopyDialog = true })
                }
                if (showCopyDialog) {
                    CopyDeviceInfoDialog(summarySections, onDismiss = { showCopyDialog = false })
                }
                IosGroup(title = stringResource(R.string.device31_summary)) {
                    IosRow(Icons.Rounded.BatteryChargingFull, IosGreenDark, stringResource(R.string.device31_battery),
                        value = l.battery?.percent?.let { "$it%" } ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Memory, IosCyanDark, stringResource(R.string.device31_memory_used), value = displayBytes(context, l.memory) ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Storage, IosPurpleDark, stringResource(R.string.device31_storage_used), value = displayBytes(context, l.storage) ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Timer, IosOrangeDark, stringResource(R.string.device31_uptime), value = DateUtils.formatElapsedTime(l.uptimeSeconds))
                }
                IosGroup(title = stringResource(R.string.device31_system)) {
                    IosRow(Icons.Rounded.Android, IosGreenDark, stringResource(R.string.device31_model), value = h.model ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.DeveloperBoard, IosBlueDark, stringResource(R.string.device31_codename), value = h.device ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Android, IosCyanDark, stringResource(R.string.device31_android), value = h.android ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.MonitorHeart, IosPinkDark, stringResource(R.string.device31_patch), value = h.securityPatch ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.DeveloperBoard, IosIndigoDark, stringResource(R.string.device31_kernel), subtitle = h.kernel ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Memory, IosOrangeDark, stringResource(R.string.device31_abi), value = h.abi ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.MonitorHeart, IosPurpleDark, stringResource(R.string.device31_display), value = h.display ?: unavailable)
                }
                IosGroup(title = stringResource(R.string.device31_cpu)) {
                    IosRow(Icons.Rounded.DeveloperBoard, IosCyanDark, stringResource(R.string.device31_hardware), value = h.hardware ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Memory, IosBlueDark, stringResource(R.string.device31_core_count), value = h.cores.toString())
                    if (l.frequencies.isEmpty()) {
                        IosGroupDivider()
                        IosRow(Icons.Rounded.Memory, IosIndigoDark, stringResource(R.string.device31_frequency), value = unavailable)
                    } else l.frequencies.forEach { (index, khz) ->
                        IosGroupDivider()
                        IosRow(Icons.Rounded.Memory, IosIndigoDark, "CPU $index", value = decimal(khz / 1000.0, "MHz"))
                    }
                }
                IosGroup(title = stringResource(R.string.device31_performance), footer = stringResource(R.string.device31_performance_note)) {
                    IosRow(Icons.Rounded.MonitorHeart, IosCyanDark, stringResource(R.string.device31_load), value = load)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.DeveloperBoard, IosPinkDark, stringResource(R.string.device31_gpu_clock), value = gpu)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.DeveloperBoard, IosPurpleDark, stringResource(R.string.device31_gpu_governor), value = performance.gpuGovernor ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Memory, IosBlueDark, stringResource(R.string.device31_zram_size), value = size(performance.zramSize))
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Memory, IosIndigoDark, stringResource(R.string.device31_zram_data), value = zramData)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.MonitorHeart, IosOrangeDark, stringResource(R.string.device31_psi_cpu), value = pressure(performance.cpuPressure))
                    IosGroupDivider()
                    IosRow(Icons.Rounded.MonitorHeart, IosOrangeDark, stringResource(R.string.device31_psi_memory), value = pressure(performance.memoryPressure))
                    IosGroupDivider()
                    IosRow(Icons.Rounded.MonitorHeart, IosOrangeDark, stringResource(R.string.device31_psi_io), value = pressure(performance.ioPressure))
                }
                IosGroup(title = stringResource(R.string.device31_battery)) {
                    val b = l.battery
                    IosRow(Icons.Rounded.BatteryChargingFull, IosGreenDark, stringResource(R.string.device31_status), value = batteryStatus(b?.status, unavailable))
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Thermostat, IosOrangeDark, stringResource(R.string.device31_temperature), value = b?.temperatureC?.let { decimal(it, "°C") } ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.BatteryChargingFull, IosPinkDark, stringResource(R.string.device31_voltage), value = b?.voltageMv?.let { "$it mV" } ?: unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.BatteryChargingFull, IosPurpleDark, stringResource(R.string.device31_current), value = b?.currentMa?.let { decimal(it, "mA") } ?: unavailable)
                }
                IosGroup(title = stringResource(R.string.device31_thermal), footer = stringResource(R.string.device31_thermal_note)) {
                    if (l.thermals.isNullOrEmpty()) {
                        IosRow(Icons.Rounded.Thermostat, IosOrangeDark, stringResource(R.string.device31_temperature), value = unavailable)
                    } else l.thermals.forEachIndexed { index, (name, temp) ->
                        if (index > 0) IosGroupDivider()
                        IosRow(Icons.Rounded.Thermostat, IosOrangeDark, name, value = decimal(temp, "°C"))
                    }
                }
                IosGroup(title = stringResource(R.string.device31_sensors)) {
                    if (h.sensors.isNullOrEmpty()) {
                        IosRow(Icons.Rounded.Sensors, IosCyanDark, stringResource(R.string.device31_sensors), value = unavailable)
                    } else h.sensors.forEachIndexed { index, sensor ->
                        if (index > 0) IosGroupDivider()
                        IosRow(Icons.Rounded.Sensors, IosCyanDark, sensor)
                    }
                }
                IosGroup(title = stringResource(R.string.device31_cameras), footer = stringResource(R.string.device31_camera_note)) {
                    if (h.cameras.isNullOrEmpty()) {
                        IosRow(Icons.Rounded.CameraAlt, IosPinkDark, stringResource(R.string.device31_cameras), value = unavailable)
                    } else h.cameras.forEachIndexed { index, camera ->
                        if (index > 0) IosGroupDivider()
                        val lens = camera.focalLengths.takeIf { it.isNotEmpty() }?.joinToString(" / ") { decimal(it.toDouble(), "mm") }
                        IosRow(Icons.Rounded.CameraAlt, IosPinkDark, "Camera ${camera.id}", subtitle = lens,
                            value = cameraFacing(camera.facing, unavailable))
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun CopyDeviceInfoDialog(sections: List<SummarySection>, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var selected by remember { mutableStateOf(emptySet<String>()) }
    val title = stringResource(R.string.device31_copy_report_title)
    val preview = renderSelectedSummary(title, sections, selected)
    val copied = stringResource(R.string.device31_copy_done)
    val failed = stringResource(R.string.device31_copy_failed)
    val chooseHint = stringResource(R.string.device31_copy_choose)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.device31_copy_title)) },
        text = {
            Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                Text(stringResource(R.string.device31_copy_privacy), style = MaterialTheme.typography.bodySmall)
                sections.forEach { section ->
                    val checked = section.id in selected
                    Row(
                        modifier = Modifier.fillMaxWidth().toggleable(value = checked, role = Role.Checkbox) { enabled ->
                            selected = if (enabled) selected + section.id else selected - section.id
                        }.padding(vertical = 3.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(checked = checked, onCheckedChange = null)
                        Text(section.title, modifier = Modifier.padding(start = 8.dp))
                    }
                }
                Text(stringResource(R.string.device31_copy_preview), style = MaterialTheme.typography.titleSmall)
                Text(preview.ifEmpty { chooseHint },
                    style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            TextButton(enabled = preview.isNotEmpty(), onClick = {
                val ok = runCatching {
                    val clipboard = context.getSystemService(ClipboardManager::class.java) ?: error("clipboard unavailable")
                    val clip = ClipData.newPlainText(title, preview)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        clip.description.extras = PersistableBundle().apply { putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true) }
                    }
                    clipboard.setPrimaryClip(clip)
                }.isSuccess
                Toast.makeText(context, if (ok) copied else failed, Toast.LENGTH_SHORT).show()
                onDismiss()
            }) { Text(stringResource(R.string.device31_copy_button)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

@Composable
private fun batteryStatus(status: Int?, unavailable: String): String = when (status) {
    BatteryManager.BATTERY_STATUS_CHARGING -> stringResource(R.string.device31_charging)
    BatteryManager.BATTERY_STATUS_DISCHARGING -> stringResource(R.string.device31_discharging)
    BatteryManager.BATTERY_STATUS_NOT_CHARGING -> stringResource(R.string.device31_not_charging)
    BatteryManager.BATTERY_STATUS_FULL -> stringResource(R.string.device31_full)
    else -> unavailable
}

@Composable
private fun cameraFacing(facing: Int?, unavailable: String): String = when (facing) {
    CameraCharacteristics.LENS_FACING_BACK -> stringResource(R.string.device31_camera_back)
    CameraCharacteristics.LENS_FACING_FRONT -> stringResource(R.string.device31_camera_front)
    CameraCharacteristics.LENS_FACING_EXTERNAL -> stringResource(R.string.device31_camera_external)
    else -> unavailable
}
