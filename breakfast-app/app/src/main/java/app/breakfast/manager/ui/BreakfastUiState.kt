package app.breakfast.manager.ui

import app.breakfast.manager.data.DeviceAudit
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
    val onApply: (List<TuningSession.Proposal>) -> Unit = {},
    val onReset: () -> Unit = {},
)
