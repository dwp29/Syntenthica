package app.breakfast.manager.ui

import app.breakfast.manager.data.LedgerReader
import app.breakfast.manager.data.StabilityLedger

/**
 * Maps a ledger read onto a screen state and its copy.
 *
 * Kept out of the Activity so that the "unreadable means dash, not zero" rule is
 * one testable function rather than a decision buried in a view.
 */
object LedgerView {

    data class Row(val label: String, val value: String, val color: Long)

    fun rows(result: LedgerReader.Result): List<Row> = when (result) {
        is LedgerReader.Result.Read -> {
            val score = result.score
            buildList {
                add(Row("Skor", score.value.toString(), statusColor(score)))
                add(Row("Beban", score.burden.toString(), ThemeCatalog.TEXT_PRIMARY))
                add(Row("Uptime", "%.1f jam".format(score.uptimeHours), ThemeCatalog.TEXT_PRIMARY))
                for (event in StabilityLedger.Event.entries) {
                    add(
                        Row(
                            event.label,
                            (score.counts[event] ?: 0).toString(),
                            ThemeCatalog.TEXT_PRIMARY,
                        )
                    )
                }
            }
        }

        LedgerReader.Result.PermissionDenied -> listOf(
            Row("Skor", Copy.ledgerUnavailable(), ThemeCatalog.STATUS_ATTENTION),
            Row("Sebab", Copy.failedReason(FailureKind.PERMISSION), ThemeCatalog.TEXT_SECONDARY),
        )

        LedgerReader.Result.Unavailable -> listOf(
            Row("Skor", Copy.ledgerUnavailable(), ThemeCatalog.STATUS_ATTENTION),
            Row("Sebab", Copy.failedReason(FailureKind.NOT_MOUNTED), ThemeCatalog.TEXT_SECONDARY),
        )
    }

    /** Status bands map to the fixed semantic colours, never to theme accents. */
    fun statusColor(score: StabilityLedger.Score): Long = when (score.band) {
        StabilityLedger.Band.STABLE -> ThemeCatalog.STATUS_STABLE
        StabilityLedger.Band.NORMAL -> ThemeCatalog.STATUS_NORMAL
        StabilityLedger.Band.ATTENTION -> ThemeCatalog.STATUS_ATTENTION
        StabilityLedger.Band.TROUBLE -> ThemeCatalog.STATUS_TROUBLE
    }

    fun bandLabel(score: StabilityLedger.Score): String = Copy.bandLabel(score.band)

    /** True when the score must be shown as a dash rather than a number. */
    fun isPlaceholder(score: StabilityLedger.Score): Boolean = !score.readable
}
