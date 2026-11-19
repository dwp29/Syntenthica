package app.breakfast.manager

import app.breakfast.manager.data.KernelPairing
import app.breakfast.manager.data.PairingGenerated
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class KernelPairingTest {

    private val freshMilk = "4.14.357-openela-Fresh-Milk-14.03"
    private val cheeseBurger = "4.14.357-openela-CHEESE-BURGER-11.08"

    @Test
    fun `both published kernels are paired`() {
        val decision = KernelPairing.decide(freshMilk, PairingGenerated.KERNELS)
        assertTrue(decision.known)
        assertTrue(decision.tuningAllowed)
        assertEquals("fresh-milk", decision.variant)
    }

    @Test
    fun `cheese burger maps to its own variant`() {
        assertEquals("cheese-burger", KernelPairing.decide(cheeseBurger, PairingGenerated.KERNELS).variant)
    }

    @Test
    fun `unknown kernel is refused rather than guessed`() {
        val decision = KernelPairing.decide("4.14.357-openela-unknown", PairingGenerated.KERNELS)
        assertFalse(decision.known)
        assertFalse(decision.tuningAllowed)
        assertEquals("unknown_kernel", decision.reason)
    }

    @Test
    fun `a prefix of a real release is not a match`() {
        assertFalse(KernelPairing.decide("4.14.357-openela-Fresh-Milk-14.0", PairingGenerated.KERNELS).known)
    }

    @Test
    fun `tuning needs root as well as a paired kernel`() {
        assertFalse(KernelPairing.canTune(freshMilk, PairingGenerated.KERNELS, hasRoot = false))
        assertTrue(KernelPairing.canTune(freshMilk, PairingGenerated.KERNELS, hasRoot = true))
    }

    @Test
    fun `no kernel claims a boot test`() {
        for (kernel in PairingGenerated.KERNELS) {
            assertEquals("compiled_not_boot_tested", kernel.status)
        }
    }
}
