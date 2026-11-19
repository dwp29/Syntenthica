package app.breakfast.manager.data

/**
 * Reads the ring buffer and turns it into a ledger.
 *
 * `dmesg -r` gives raw lines with `<level>` prefixes; the level is stripped so
 * classification sees the message text only. If the read fails - no root, or the
 * buffer was rotated away - this returns null and the UI shows "—". It never
 * substitutes zero events for "I could not look", because a fabricated 100 is a
 * lie a user would reasonably act on.
 */
object LedgerReader {

    sealed interface Result {
        data class Read(val score: StabilityLedger.Score, val occurrences: List<StabilityLedger.Occurrence>) : Result
        data object PermissionDenied : Result
        data object Unavailable : Result
    }

    fun read(root: RootBridge = RootBridge): Result {
        if (!root.hasRoot()) return Result.PermissionDenied
        val output = root.run("dmesg -r")
        if (!output.ok) return Result.PermissionDenied
        val lines = output.stdout.lineSequence().map(::stripLevel).filter { it.isNotBlank() }
        val occurrences = StabilityLedger.scan(lines)
        val hours = root.uptimeHours() ?: return Result.Unavailable
        return Result.Read(StabilityLedger.compute(occurrences, hours), occurrences)
    }

    /** Turns `<4>[  123.45] msg` into `[  123.45] msg`. */
    fun stripLevel(line: String): String =
        if (line.startsWith("<") && line.length > 3 && line[2] == '>') line.substring(3) else line
}
