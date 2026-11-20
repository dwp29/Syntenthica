package app.breakfast.manager.ui

import app.breakfast.manager.data.StabilityLedger

/**
 * Screen states, mapped one-to-one onto the six documented states.
 *
 * `Loading` has no spinner field on purpose: the spec forbids a rotating
 * spinner, so the UI draws a skeleton of the shape the data will take.
 * `Empty` always carries an action because an empty screen with no button is a
 * dead end. `NeverAudited` is deliberately separate from `Empty`: "we have not
 * looked" is not the same claim as "there is nothing".
 */
sealed interface ScreenState<out T> {
    data object Loading : ScreenState<Nothing>
    data object LoadingSlow : ScreenState<Nothing>
    data class Content<T>(val value: T) : ScreenState<T>
    data class Empty(val message: String, val action: String) : ScreenState<Nothing>
    data class Failed(val reason: String) : ScreenState<Nothing>
    data object NeverAudited : ScreenState<Nothing>
}

/** Indonesian and English copy for the states that carry text. */
object Copy {
    fun failedReason(kind: FailureKind): String = when (kind) {
        // The ledger reads the kernel ring buffer, never sysfs. Naming sysfs
        // here sent a real user looking in the wrong place, so the cause names
        // the thing that actually failed.
        FailureKind.PERMISSION -> "dmesg tidak bisa dibaca (izin ditolak)"
        FailureKind.NOT_MOUNTED -> "dmesg tidak tersedia (bukan root atau sudah dirotasi)"
        FailureKind.AUDIT -> "audit tidak bisa membaca node (izin ditolak)"
        FailureKind.VANISHED -> "node hilang. Audit ulang diperlukan."
    }

    fun ledgerUnavailable(): String = "—"

    fun bandLabel(band: StabilityLedger.Band): String = when (band) {
        StabilityLedger.Band.STABLE -> "Stabil"
        StabilityLedger.Band.NORMAL -> "Normal"
        StabilityLedger.Band.ATTENTION -> "Perlu perhatian"
        StabilityLedger.Band.TROUBLE -> "Bermasalah"
    }
}

enum class FailureKind { PERMISSION, NOT_MOUNTED, VANISHED, AUDIT }
