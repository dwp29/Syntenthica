package app.breakfast.manager.ui

import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.ModuleScan
import app.breakfast.manager.data.RootStatus
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.data.TuningSession

/**
 * Everything the UI renders, in one immutable value.
 *
 * Keeping the screen a pure function of this state is what lets the same code
 * render a placeholder instead of a number: there is no path from "read failed"
 * to a zero.
 */
data class BreakfastUiState(
    val kernelRelease: String,
    val variantLabel: String,
    val variantPaired: Boolean,
    val tuningEnabled: Boolean,
    val tuningReason: String,
    val hasRoot: Boolean,
    val auditing: Boolean,
    val canReset: Boolean,
    val report: DeviceAudit.Report,
    val ledger: StabilityLedger.Score?,
    val ledgerReason: String?,
    val readings: PulseReadings,
    val uptimeText: String,
    val palette: ThemeCatalog.Palette,
    val onAudit: () -> Unit = {},
    val onRequestRoot: () -> Unit = {},
    val auditAgeText: String = "—",
    val rootMessage: String? = null,
    /** Checked facts for the ROOT page; null until the first probe finishes. */
    val rootSnapshot: RootStatus.Snapshot? = null,
    /** /proc/modules, or null when the file could not be read at all. */
    val modules: List<ModuleScan.Module>? = null,
    val onRefreshRoot: () -> Unit = {},
    val onRefreshModules: () -> Unit = {},
    val intervalSeconds: Int = 2,
    val onIntervalPick: (Int) -> Unit = { _ -> },
    val variantName: String = "—",
    val onApply: (List<TuningSession.Proposal>) -> Unit = {},
    val onReset: () -> Unit = {},
)
