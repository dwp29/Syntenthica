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
    fun `a published kernel is recognised by name and by nothing else`() {
        val decision = KernelPairing.decide(freshMilk, PairingGenerated.KERNELS)
        assertTrue(decision.known)
        assertEquals("fresh-milk", decision.variant)
        // Publishing a kernel is not evidence about its nodes. This used to be
        // true, which is how a name match came to stand in for a capability.
        assertFalse("a name must not authorise anything", decision.tuningAllowed)
        assertEquals("name_only", decision.reason)
    }

    @Test
    fun `no row in the table claims verified capabilities`() {
        for (kernel in PairingGenerated.KERNELS) {
            assertFalse(
                "${kernel.release} claims capabilities nobody read on a device",
                kernel.capabilitiesVerified,
            )
        }
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
    fun `a matching name is not permission`() {
        // The old canTune() returned true here: correct release string plus root.
        // It was removed because a name match is not evidence of anything. The
        // node read is what decides now, and it is the only thing that does.
        val known = KernelPairing.capability(
            key = "zram_mem_limit",
            nodeRead = false,
            release = freshMilk,
            kernels = PairingGenerated.KERNELS,
        )
        assertFalse("a known kernel must not unlock an unread node", known.tunable)
        assertTrue(known.releaseKnown)
        assertTrue(known.explain().contains("node tidak terbaca"))

        val read = known.copy(nodeRead = true)
        assertTrue("a read node is the evidence", read.tunable)
    }

    @Test
    fun `a read node works even when the kernel name is unknown`() {
        // The reverse of the old bug: the previous gate refused a kernel whose
        // nodes were right there, simply because its release string was absent.
        val unknown = KernelPairing.capability(
            key = "zram_mem_limit",
            nodeRead = true,
            release = "4.14.357-openela-not-in-the-table",
            kernels = PairingGenerated.KERNELS,
        )
        assertTrue(unknown.tunable)
        assertFalse(unknown.releaseKnown)
        assertTrue(
            "must say the name was not used as proof: ${unknown.explain()}",
            unknown.explain().contains("tidak dipakai sebagai bukti"),
        )
    }

    @Test
    fun `neither a name nor a root shell is called proof`() {
        // Both were, at different times. Nothing in this file may claim that a
        // release string establishes what the kernel can do.
        val decision = KernelPairing.decide(freshMilk, PairingGenerated.KERNELS)
        assertTrue(decision.known)
        // known=true is all it means; there is no field asserting capability.
        assertEquals("paired", decision.reason)
    }

    @Test
    fun `no kernel claims a boot test`() {
        for (kernel in PairingGenerated.KERNELS) {
            assertEquals("compiled_not_boot_tested", kernel.status)
        }
    }
}
