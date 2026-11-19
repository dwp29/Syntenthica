package app.breakfast.manager.data

/**
 * Applies whitelisted parameters and reports *why* a write failed.
 *
 * Four distinct failures, four distinct messages - never one generic error:
 *   permission denied / out of range / node vanished / read-back mismatch.
 *
 * Every write is read back. A change that cannot be confirmed is reported as a
 * failure, because on a rooted device "probably applied" is indistinguishable
 * from "silently ignored" until something breaks.
 */
object TuningEngine {

    /** Result of a single parameter write. */
    sealed interface Outcome {
        data class Applied(val value: String) : Outcome
        data object PermissionDenied : Outcome
        data class OutOfRange(val min: Long, val max: Long) : Outcome
        data class Vanished(val key: String) : Outcome
        data class ReadBackMismatch(val written: String, val read: String?) : Outcome
        data class Rejected(val reason: TuningWhitelist.Reason) : Outcome
        data class Failed(val detail: String) : Outcome
    }

    data class Result(val key: String, val outcome: Outcome) {
        val ok: Boolean get() = outcome is Outcome.Applied
    }

    /** Minimal seam over the filesystem so this can be tested without a device. */
    interface Files {
        fun exists(path: String): Boolean
        fun read(path: String): String?
        fun write(path: String, value: String): Boolean
    }

    /**
     * Normalises for comparison. The kernel echoes some values with a trailing
     * newline, and comp_algorithm echoes the active choice in brackets, so a raw
     * string compare would report a false mismatch on a successful write.
     */
    fun normalise(key: String, raw: String): String {
        val trimmed = raw.trim()
        return if (key == "zram_comp_algorithm") {
            TuningWhitelist.parseActive(trimmed) ?: trimmed
        } else {
            trimmed
        }
    }

    fun apply(
        files: Files,
        key: String,
        value: String,
        offered: List<String>? = null,
    ): Result {
        val parameter = TuningWhitelist.byKey(key)
            ?: return Result(key, Outcome.Rejected(TuningWhitelist.Reason.NOT_WHITELISTED))

        // Refuse locally before touching the filesystem.
        when (val v = TuningWhitelist.validate(key, value, offered)) {
            is TuningWhitelist.Validation.Rejected -> return Result(key, Outcome.Rejected(v.reason))
            TuningWhitelist.Validation.Ok -> Unit
        }

        if (!files.exists(parameter.path)) return Result(key, Outcome.Vanished(key))

        val wrote = files.write(parameter.path, value.trim())
        if (!wrote) return Result(key, Outcome.PermissionDenied)

        val readBack = files.read(parameter.path)
        val expected = normalise(key, value)
        val actual = readBack?.let { normalise(key, it) }
        return if (actual == expected) {
            Result(key, Outcome.Applied(value.trim()))
        } else {
            Result(key, Outcome.ReadBackMismatch(expected, actual))
        }
    }

    fun applyAll(
        files: Files,
        changes: Map<String, String>,
        offered: Map<String, List<String>> = emptyMap(),
    ): List<Result> = changes.map { (key, value) ->
        apply(files, key, value, offered[key])
    }.sortedBy { it.key }

    /** True when a parameter can never take effect until the device reboots. */
    fun needsReboot(key: String): Boolean =
        TuningWhitelist.byKey(key)?.mode == TuningWhitelist.WriteMode.NEEDS_REBOOT
}
