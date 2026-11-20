package app.breakfast.manager

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.AuditStore
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.DeviceFiles
import app.breakfast.manager.data.KernelPairing
import app.breakfast.manager.data.LedgerReader
import app.breakfast.manager.data.PairingGenerated
import app.breakfast.manager.data.RootBridge
import app.breakfast.manager.data.ModuleScan
import app.breakfast.manager.data.NativeGuard
import app.breakfast.manager.data.RootRequest
import app.breakfast.manager.data.RootStatus
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.data.ThemeStore
import app.breakfast.manager.data.TuningSession
import app.breakfast.manager.ui.BreakfastApp
import app.breakfast.manager.ui.BreakfastUiState
import app.breakfast.manager.ui.PulseReader
import app.breakfast.manager.ui.PulseReadings
import app.breakfast.manager.ui.ThemeCatalog
import app.breakfast.manager.ui.screens.SettingsSheet
import app.breakfast.manager.ui.theme.BreakfastTheme
import app.breakfast.manager.ui.theme.LocalBreakfastColors
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

/**
 * Hosts the Compose tree and owns the clocks.
 *
 * Two cadences:
 *  - 2 s: PULSE readings, because a dashboard that updates every 30 s is a
 *    screenshot, not a dashboard.
 *  - on demand: the audit and the ledger, which are expensive and rate-limited.
 *
 * Everything runs on one worker so readings cannot interleave, and each result
 * is applied on the main thread through the immutable state above.
 */
class MainActivity : ComponentActivity() {

    private val worker = Executors.newSingleThreadExecutor()
    private var ticker: ScheduledExecutorService? = null

    private lateinit var auditStore: AuditStore
    private lateinit var themeStore: ThemeStore
    private lateinit var nativeGuard: NativeGuard

    private var release: String = "—"
    private var decision: KernelPairing.Decision =
        KernelPairing.Decision(known = false, tuningAllowed = false, variant = null, reason = "unknown_kernel")
    private var report: DeviceAudit.Report = DeviceAudit.Report("—", 0L, emptyList())
    private var ledger: StabilityLedger.Score? = null
    private var ledgerReason: String? = null
    private var readings: PulseReadings = PulseReadings.empty()
    private var hasRoot = false
    private var auditing = false
    private var auditDirty = false
    private var lastPlan: TuningSession.Plan? = null
    private var lastAuditMs = 0L
    private var rootMessage: String? = null

    /** A start-up failure shown on screen instead of a force close. */
    private var startupError: String? = null
    private var rootSnapshot: RootStatus.Snapshot? = null
    private var modules: ModuleScan.Result? = null

    /** /data/adb/modules: what is installed, as opposed to what the kernel loaded. */
    private var installedModules: ModuleScan.Installed? = null

    /** Sampling interval, chosen in settings; 2 s was the only option before. */
    private var intervalSeconds = 2

    private var palette: ThemeCatalog.Palette = ThemeCatalog.ALL.first()
    private var settingsOpen by mutableStateOf(false)
    private var frame by mutableStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        auditStore = AuditStore(this)
        themeStore = ThemeStore(this)
        nativeGuard = NativeGuard(this)
        palette = ThemeCatalog.byId(themeStore.current()) ?: ThemeCatalog.offered().first()

        setContent {
            BreakfastTheme(palette) {
                val c = LocalBreakfastColors.current
                Box(Modifier.fillMaxSize().background(c.background)) {
                    // frame is read here so a worker-thread result recomposes the
                    // tree; without it, updating state would not redraw.
                    if (frame >= 0) {
                        BreakfastApp(
                            state = uiState(),
                            onOpenSettings = { settingsOpen = true },
                        )
                    }
                    SettingsSheet(
                        visible = settingsOpen,
                        current = palette,
                        onPick = { picked ->
                            palette = picked
                            themeStore.save(picked.id)
                            settingsOpen = false
                            frame++
                        },
                        onDismiss = { settingsOpen = false },
                        intervalSeconds = intervalSeconds,
                        onIntervalPick = { seconds ->
                            intervalSeconds = seconds
                            themeStore.saveInterval(seconds)
                            // The ticker must actually change rate, not just relabel.
                            restartTicker()
                            frame++
                        },
                        kernelRelease = release,
                        variantName = decision.variant?.let { "FRESH-MILK-14.03" } ?: release.takeLast(16),
                        onRunAudit = {
                            settingsOpen = false
                            audit(manual = true)
                        },
                        onResetSettings = {
                            palette = ThemeCatalog.ALL.first()
                            themeStore.save(palette.id)
                            intervalSeconds = 2
                            themeStore.saveInterval(2)
                            restartTicker()
                            settingsOpen = false
                            frame++
                        },
                    )
                }
            }
        }

        worker.execute {
            // Nothing that happens while collecting facts may close the app. The
            // worker is the only place that touches files, su and JNI; a failure
            // there used to propagate out of the executor and kill the process.
            try {
                release = RootBridge.kernelRelease() ?: "—"
                decision = KernelPairing.decide(release, PairingGenerated.KERNELS)
                val stored = auditStore.load()
                report = stored ?: DeviceAudit.Report(release, 0L, emptyList())
                hasRoot = RootBridge.hasRoot()
                intervalSeconds = themeStore.interval()
                lastAuditMs = stored?.timestampMs ?: 0L
                // At start-up the native library is NOT loaded. Run 30 proved it can
                // abort the process while loading, and nothing in Java can catch that.
                rootSnapshot = RootStatus.snapshot(allowLibrary = false)
                modules = ModuleScan.scan()
                installedModules = ModuleScan.scanInstalled()

                publish {
                    readLedger()
                    readAudit(force = true)
                    sampleOnce()
                    startTicker()
                }
            } catch (e: Throwable) {
                startupError = "${e.javaClass.simpleName}: ${e.message ?: "tanpa pesan"}"
                publish { frame++ }
            }
        }
    }

    override fun onDestroy() {
        ticker?.shutdownNow()
        worker.shutdownNow()
        super.onDestroy()
    }

    // ------------------------------------------------------------------ clocks

    private fun startTicker() {
        if (ticker != null) return
        ticker = Executors.newSingleThreadScheduledExecutor()
        ticker?.scheduleWithFixedDelay(
            {
                worker.execute {
                    sampleOnce()
                    publish { frame++ }
                }
            },
            intervalSeconds.toLong(),
            intervalSeconds.toLong(),
            TimeUnit.SECONDS,
        )
    }

    /** Applies a new sampling interval by replacing the scheduled task. */
    private fun restartTicker() {
        ticker?.shutdownNow()
        ticker = null
        startTicker()
    }

    private fun sampleOnce() {
        readings = PulseReader.sample(ledger, hasRoot)
    }

    private fun readLedger() {
        when (val result = LedgerReader.read()) {
            is LedgerReader.Result.Read -> {
                ledger = result.score
                ledgerReason = null
            }
            LedgerReader.Result.PermissionDenied -> {
                ledger = null
                ledgerReason = "dmesg tidak bisa dibaca (izin ditolak). Skor tidak dikarang."
            }
            LedgerReader.Result.Unavailable -> {
                ledger = null
                ledgerReason = "dmesg tidak tersedia (bukan root atau sudah dirotasi)."
            }
        }
    }

    private fun readAudit(force: Boolean = false) {
        if (auditing) return
        val now = System.currentTimeMillis()
        val automatic = report.kernelRelease != release || report.timestampMs == 0L || auditDirty
        if (!force && !automatic) return
        auditing = true
        publish { frame++ }
        val fresh = try {
            AuditRunner.run(AuditRunner.SystemFs, release, now, hasRoot = hasRoot)
        } catch (e: Exception) {
            null
        }
        when (val resolved = DeviceAudit.resolve(report, fresh, release, now)) {
            is DeviceAudit.Resolution.Fresh -> {
                report = resolved.report
                lastAuditMs = resolved.report.timestampMs
                auditStore.save(report)
            }
            is DeviceAudit.Resolution.KeptStale -> {
                report = resolved.report
                lastAuditMs = resolved.report.timestampMs
            }
            is DeviceAudit.Resolution.None -> {
                report = DeviceAudit.Report(release, 0L, emptyList())
                auditStore.clear()
                ledgerReason = resolved.reason
            }
        }
        auditing = false
        auditDirty = false
        publish { frame++ }
    }

    // ------------------------------------------------------------------ actions

    /**
     * Re-probes root. The ROOT page button is also the only place that consents
     * to loading libkernelsu.so, because that load is what closed the app in run
     * 30. The attempt is marked on disk first, so a process that dies during the
     * load is remembered on the next start instead of repeating forever.
     */
    private fun refreshRoot() {
        worker.execute {
            val mayLoad = nativeGuard.mayLoad()
            if (mayLoad) nativeGuard.markAttempt()
            rootSnapshot = RootStatus.snapshot(allowLibrary = mayLoad)
            if (mayLoad && rootSnapshot?.libraryLoaded == true) {
                // The library answered, so this process survived it.
                nativeGuard.clearAttempt()
                nativeGuard.setUserAllowedRetry(false)
            }
            hasRoot = rootSnapshot?.granted == true
            publish { frame++ }
        }
    }

    private fun refreshModules() {
        worker.execute {
            modules = ModuleScan.scan()
            installedModules = ModuleScan.scanInstalled()
            publish { frame++ }
        }
    }

    private fun audit(manual: Boolean) {
        worker.execute {
            if (manual) {
                val remaining = DeviceAudit.cooldownRemainingMs(lastAuditMs.takeIf { it > 0L }, System.currentTimeMillis())
                if (remaining > 0) {
                    publish { frame++ }
                    return@execute
                }
            }
            readLedger()
            readAudit(force = true)
            sampleOnce()
            publish { frame++ }
        }
    }

    private fun apply(proposals: List<TuningSession.Proposal>) {
        worker.execute {
            val offered = buildMap {
                report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == "zram_comp_algorithm" }
                    ?.value?.let { put("zram_comp_algorithm", app.breakfast.manager.data.TuningWhitelist.parseOffered(it)) }
            }
            val plan = TuningSession.plan(DeviceFiles, proposals, offered)
            if (plan.count == 0) {
                auditDirty = true
                publish { frame++ }
                return@execute
            }
            val result = TuningSession.apply(DeviceFiles, plan, offered)
            if (result.applied.isNotEmpty()) lastPlan = plan
            auditDirty = result.applied.isNotEmpty()
            readAudit(force = true)
            sampleOnce()
            publish { frame++ }
        }
    }

    private fun reset() {
        val plan = lastPlan ?: return
        worker.execute {
            TuningSession.reset(DeviceFiles, plan)
            lastPlan = null
            auditDirty = true
            readAudit(force = true)
            publish { frame++ }
        }
    }

    /** "3 menit lalu" from the real last audit time, not from uptime. */
    private fun auditAge(): String {
        val last = lastAuditMs.takeIf { it > 0L } ?: return "belum pernah"
        val age = (System.currentTimeMillis() - last).coerceAtLeast(0)
        return "${DeviceAudit.ageLabel(age)} lalu"
    }

    /**
     * Asks for root at the user's request, then redoes everything that depended
     * on it: ledger, audit, and readings. This is the flow that was missing when
     * the dashboard showed dashes everywhere.
     */
    private fun requestRoot() {
        worker.execute {
            val outcome = RootRequest.request()
            hasRoot = outcome == RootRequest.Outcome.Granted
            rootMessage = RootRequest.message(outcome)
            rootSnapshot = RootStatus.snapshot()
            if (hasRoot) {
                readLedger()
                readAudit(force = true)
            }
            sampleOnce()
            publish { frame++ }
        }
    }

    private fun publish(block: () -> Unit) {
        runOnUiThread {
            block()
            frame++
        }
    }

    // -------------------------------------------------------------------- state

    private fun uiState() = BreakfastUiState(
        kernelRelease = release,
        variantLabel = decision.variant?.let { "FRESH-MILK-14.03" } ?: release.takeLast(16),
        variantPaired = decision.known,
        tuningEnabled = decision.tuningAllowed && report.nodes.isNotEmpty(),
        tuningReason = if (decision.known) decision.reason else "unknown_kernel",
        hasRoot = hasRoot,
        auditing = auditing,
        canReset = lastPlan != null,
        report = report,
        ledger = ledger,
        ledgerReason = ledgerReason,
        readings = readings,
        uptimeText = PulseReader.formatUptime(readings.uptimeHours),
        palette = palette,
        auditAgeText = auditAge(),
        rootMessage = startupError?.let { "Gagal menyiapkan data: $it" } ?: rootMessage,
        onAudit = { audit(manual = true) },
        onRequestRoot = { requestRoot() },
        onRefreshRoot = { refreshRoot() },
        onRefreshModules = { refreshModules() },
        rootSnapshot = rootSnapshot,
        modules = modules,
        installedModules = installedModules,
        intervalSeconds = intervalSeconds,
        onIntervalPick = { seconds ->
            intervalSeconds = seconds
            themeStore.saveInterval(seconds)
            restartTicker()
            frame++
        },
        variantName = decision.variant?.let { "FRESH-MILK-14.03" } ?: release.takeLast(16),
        onApply = { proposals -> apply(proposals) },
        onReset = { reset() },
    )
}
