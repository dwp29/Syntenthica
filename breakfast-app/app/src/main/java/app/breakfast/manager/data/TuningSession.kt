package app.breakfast.manager.data

/**
 * One tuning session: propose changes, confirm, apply, and undo.
 *
 * The rules that make writing defensible:
 *
 *  - Nothing is written until every proposed value has been validated against
 *    the allow-list and against the value the kernel actually offers.
 *  - Every original value is captured before writing, so "reset to default" has
 *    something true to restore. If a node cannot be read, it is not offered.
 *  - Apply is all-or-reported: each parameter's outcome is kept separately, and
 *    a partial result is described as partial rather than rolled up into
 *    "failed" or "done".
 *  - A parameter flagged needs-reboot is reported as pending, not as applied,
 *    because the current value will not change until the next boot.
 */
object TuningSession {

    data class Proposal(val key: String, val value: String)

    data class Plan(
        val applicable: List<Proposal>,
        val rejected: List<Pair<Proposal, TuningWhitelist.Reason>>,
        val originals: Map<String, String>,
        val needsReboot: List<String>,
    ) {
        val count: Int get() = applicable.size
        val isEmpty: Boolean get() = applicable.isEmpty()
    }

    data class Applied(
        val key: String,
        val value: String,
        val source: String,
        val pendingReboot: Boolean,
    )

    data class Result(
        val applied: List<Applied>,
        val failed: List<TuningEngine.Result>,
        val rejected: List<Pair<Proposal, TuningWhitelist.Reason>>,
    ) {
        /** What the confirmation dialog promised, versus what happened. */
        fun summary(): String {
            if (applied.isEmpty() && failed.isEmpty()) return "Tidak ada perubahan."
            val pending = applied.count { it.pendingReboot }
            return buildString {
                append("${applied.size} parameter diubah")
                if (pending > 0) append(", $pending berlaku setelah reboot")
                if (failed.isNotEmpty()) append(", ${failed.size} gagal")
                append('.')
            }
        }

        val fullyApplied: Boolean get() = failed.isEmpty() && rejected.isEmpty()
    }

    /**
     * Builds a plan from proposed values and the values currently offered by the
     * kernel. Anything that cannot be validated is rejected here, before the
     * confirmation dialog, so the dialog never promises a change that is known
     * to be impossible.
     */
    fun plan(
        files: TuningEngine.Files,
        proposals: List<Proposal>,
        offered: Map<String, List<String>> = emptyMap(),
    ): Plan {
        val applicable = mutableListOf<Proposal>()
        val rejected = mutableListOf<Pair<Proposal, TuningWhitelist.Reason>>()
        val originals = mutableMapOf<String, String>()

        for (proposal in proposals) {
            val parameter = TuningWhitelist.byKey(proposal.key)
            if (parameter == null) {
                rejected += proposal to TuningWhitelist.Reason.NOT_WHITELISTED
                continue
            }
            when (val v = TuningWhitelist.validate(proposal.key, proposal.value, offered[proposal.key])) {
                is TuningWhitelist.Validation.Rejected -> rejected += proposal to v.reason
                TuningWhitelist.Validation.Ok -> {
                    // No original value means the node is gone; do not invent one.
                    val original = files.read(parameter.path)?.trim()
                    if (original == null) {
                        rejected += proposal to TuningWhitelist.Reason.EMPTY
                        continue
                    }
                    originals[proposal.key] = original
                    applicable += proposal
                }
            }
        }

        val pending = applicable.filter { TuningEngine.needsReboot(it.key) }.map { it.key }
        return Plan(applicable, rejected, originals, pending)
    }

    fun apply(
        files: TuningEngine.Files,
        plan: Plan,
        offered: Map<String, List<String>> = emptyMap(),
    ): Result {
        val applied = mutableListOf<Applied>()
        val failed = mutableListOf<TuningEngine.Result>()

        for (proposal in plan.applicable) {
            val outcome = TuningEngine.apply(files, proposal.key, proposal.value, offered[proposal.key])
            if (outcome.ok) {
                applied += Applied(
                    key = proposal.key,
                    value = proposal.value,
                    source = plan.originals[proposal.key] ?: "",
                    pendingReboot = TuningEngine.needsReboot(proposal.key),
                )
            } else {
                failed += outcome
            }
        }
        return Result(applied, failed, plan.rejected)
    }

    /**
     * Restores the captured originals. Used by "reset to default"; a value that
     * cannot be restored is reported rather than silently dropped.
     */
    fun reset(files: TuningEngine.Files, plan: Plan): Result {
        val restore = plan.originals.map { (key, value) -> Proposal(key, value) }
        return apply(files, Plan(restore, emptyList(), emptyMap(), emptyList()))
    }
}
