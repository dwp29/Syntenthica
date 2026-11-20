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
    /** True when `uname -r` matched a release this build was published against.
     *  A name match only: it is never evidence that a node exists or is writable. */
    val variantKnown: Boolean,
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
    /** /data/adb/modules: the modules a person installs. */
    val installedModules: ModuleScan.Installed? = null,

    /** /proc/modules: *.ko objects linked in or loaded by the kernel. */
    val modules: ModuleScan.Result? = null,
    val onRefreshRoot: () -> Unit = {},
    val onRefreshModules: () -> Unit = {},
    val intervalSeconds: Int = 2,
    val onIntervalPick: (Int) -> Unit = { _ -> },
    val variantName: String = "—",
    val onApply: (List<TuningSession.Proposal>) -> Unit = {},
    val onReset: () -> Unit = {},
)
