package app.breakfast.manager.data

/**
 * Kernel <-> manager pairing.
 *
 * This is a *name* match and nothing more. `uname -r` says which string a kernel
 * was built with; it says nothing about whether a sysfs node exists, what its
 * range is, or whether the kernel honours a write. Anyone can flash a kernel and
 * call it anything.
 *
 * So it must not be described as proof of a kernel's capabilities. What it is
 * good for is the opposite direction: a release this build was never published
 * against is a reason to say "I do not know this kernel" and stop, rather than
 * hand out sliders that write nowhere.
 *
 * The evidence for tuning is the audit: each node is read on the device, and the
 * control only appears when that read succeeded. [Capability] below names which
 * of the two is deciding, so the UI can say it plainly instead of implying that
 * the release string proved something.
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
        /** Always false today: no node has been read on a device running this
         *  kernel. Kept as a field so the table cannot quietly grow a claim. */
        val capabilitiesVerified: Boolean,
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
            // Not a permission. A name match cannot approve a write; the node
            // read in the audit does that. This stays false until an on-device
            // audit has actually read nodes on this kernel and been recorded.
            tuningAllowed = match.capabilitiesVerified,
            variant = match.variant,
            reason = if (match.capabilitiesVerified) "paired" else "name_only",
        )
    }

    // canTune() used to live here: hasRoot && the release string matched. It was
    // removed because that rule is exactly the mistake - a name match plus root
    // was being treated as permission to hand out controls. Root is still needed
    // for a write to succeed, but it is checked when writing, and the control is
    // only drawn when its node was actually read.

    /** UAPI of the manager itself, for the compatibility display. */
    const val MANAGER_UAPI = 4

    /**
     * What actually decides whether a control may be drawn, and why.
     *
     * A release string is not evidence. This type exists so the app can never
     * again present a name match as if it were a capability check.
     */
    data class Capability(
        val key: String,
        val nodeRead: Boolean,
        val releaseKnown: Boolean,
    ) {
        val tunable: Boolean get() = nodeRead

        /** One short sentence, for the TUNING page. */
        fun explain(): String = when {
            tunable -> "Terbukti bisa: node dibaca di perangkat ini. Nama kernel " +
                "(${if (releaseKnown) "cocok" else "tidak dikenal"}) tidak dipakai sebagai bukti."
            !releaseKnown ->
                "Tidak ditampilkan: node tidak terbaca, dan kernel ini bukan salah satu " +
                    "yang pernah diuji build ini."
            else ->
                "Tidak ditampilkan: node tidak terbaca di perangkat ini."
        }
    }

    /**
     * The only gate for a control: the node was read, with a value, by the audit.
     *
     * The release is passed for the explanation only. It is deliberately not
     * required, because matching a name proves nothing about the node.
     */
    fun capability(
        key: String,
        nodeRead: Boolean,
        release: String,
        kernels: List<Kernel>,
    ): Capability = Capability(
        key = key,
        nodeRead = nodeRead,
        releaseKnown = kernels.any { it.release == release },
    )
}
