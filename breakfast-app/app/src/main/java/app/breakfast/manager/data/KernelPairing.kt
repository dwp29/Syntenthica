package app.breakfast.manager.data

/**
 * Kernel <-> manager pairing.
 *
 * The manager only enables tuning when the running kernel release is one this
 * build was published against. This is a safety gate, not a security boundary:
 * it exists so that a user who flashed a different kernel is told plainly that
 * this app does not know that kernel's sysfs layout, instead of being handed
 * sliders that write nowhere or write the wrong node.
 *
 * The table is generated at build time from tools/pairing.json into
 * pairing_generated.kt, so the app can never disagree with the shipped table.
 */
object KernelPairing {

    data class Kernel(
        val release: String,
        val variant: String,
        val profile: String,
        val kernelUapi: Int,
        val tuning: Boolean,
        val status: String,
    )

    /** Cannot write a Data class literal from JSON at build time without a serializer. */
    data class Decision(
        val known: Boolean,
        val tuningAllowed: Boolean,
        val variant: String?,
        val reason: String,
    )

    fun decide(release: String, kernels: List<Kernel>): Decision {
        val match = kernels.firstOrNull { it.release == release }
            ?: return Decision(
                known = false,
                tuningAllowed = false,
                variant = null,
                reason = "unknown_kernel",
            )
        return Decision(
            known = true,
            tuningAllowed = match.tuning,
            variant = match.variant,
            reason = if (match.tuning) "paired" else "tuning_disabled_for_kernel",
        )
    }

    /**
     * Tuning additionally requires root. Without it every write would fail with
     * permission denied, which reads like a bug rather than a prerequisite.
     */
    fun canTune(release: String, kernels: List<Kernel>, hasRoot: Boolean): Boolean =
        hasRoot && decide(release, kernels).tuningAllowed

    /** UAPI of the manager itself, for the compatibility display. */
    const val MANAGER_UAPI = 4
}
