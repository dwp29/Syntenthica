package com.rifsxd.ksunext.ui.pixel

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.URI

class PixelLogic40Test {
    @Test fun providerNamesAreNormalizedButGenericZygiskModulesAreNotProviders() {
        assertTrue(knownProvider40("zygisk_next", "Something"))
        assertTrue(knownProvider40("rezygisk", "ReZygisk"))
        assertTrue(knownProvider40("neo-zygisk", "NeoZygisk"))
        assertFalse(knownProvider40("lsposed", "LSPosed Zygisk"))
        assertFalse(knownProvider40("some_mod", "Other"))
    }

    @Test fun onlyTwoMarkedEnabledCandidatesTriggerPossibleConflict() {
        val a = ProviderCandidate40("rezygisk", "ReZygisk", true)
        val b = ProviderCandidate40("neozygisk", "NeoZygisk", false)
        assertFalse(possibleProviderConflict40(null))
        assertFalse(possibleProviderConflict40(emptyList()))
        assertFalse(possibleProviderConflict40(listOf(a, b)))
        assertTrue(possibleProviderConflict40(listOf(a, b.copy(markedEnabled = true))))
    }

    @Test fun curatedLinksAreHttpsAllowlistedAndUnique() {
        val links = PixelSources40.flatMap { it.links }
        assertTrue(links.size >= 20)
        assertEquals(links.size, links.map { it.url }.distinct().size)
        links.forEach {
            val uri = URI(it.url)
            assertEquals("https", uri.scheme)
            assertTrue(uri.host in setOf("github.com", "modules.kernelsu.org", "modules.lsposed.org", "t.me"))
            assertFalse(uri.userInfo != null)
        }
    }

    @Test fun frameworksProvidersAndXposedApksAreSeparateGroups() {
        assertTrue(PixelSources40[2].links.any { it.name == "LSPosed" })
        assertTrue(PixelSources40[1].links.any { it.name == "ReZygisk" })
        assertTrue(PixelSources40[4].links.any { it.name == "Hide My Applist" })
    }
}
