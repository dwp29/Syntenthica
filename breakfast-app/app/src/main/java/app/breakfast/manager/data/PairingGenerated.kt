package app.breakfast.manager.data

// GENERATED FILE - do not edit. Source: breakfast-app/tools/pairing.json
// Regenerate with: python3 breakfast-app/tools/gen_pairing.py

internal object PairingGenerated {
    val KERNELS: List<KernelPairing.Kernel> = listOf(
        KernelPairing.Kernel(
            release = "4.14.357-openela-Fresh-Milk-14.03",
            variant = "fresh-milk",
            profile = "synthetica",
            kernelUapi = 4,
            capabilitiesVerified = false,
            status = "compiled_not_boot_tested",
        ),
        KernelPairing.Kernel(
            release = "4.14.357-openela-CHEESE-BURGER-11.08",
            variant = "cheese-burger",
            profile = "critical",
            kernelUapi = 4,
            capabilitiesVerified = false,
            status = "compiled_not_boot_tested",
        ),
    )
}
