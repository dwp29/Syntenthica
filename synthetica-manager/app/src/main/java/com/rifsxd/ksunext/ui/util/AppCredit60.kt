package com.rifsxd.ksunext.ui.util

/**
 * Single source of truth for who made this APK: the author identity, where the
 * full source lives, the licence, and the (currently empty) donation target.
 *
 * Kept out of the composables so About, the licences page and any future
 * diagnostics all render exactly the same strings, and so the donation slot can
 * be filled by changing one constant instead of touching UI code.
 */
object AppCredit60 {
    /** Public author identity of this build. */
    const val AUTHOR = "Pure_Saturday"

    /** Telegram handle, with the @ that the user wrote it as. */
    const val TELEGRAM_HANDLE = "@Pure_Saturday"

    /** Explicit scheme so Android resolves it to the Telegram app, not a browser. */
    const val TELEGRAM_URL = "https://t.me/Pure_Saturday"

    /** Repository that contains the kernel, the modules and this Manager. */
    const val SOURCE_URL = "https://github.com/dwp29/Syntenthica"

    /** Where the Manager's own sources live inside that repository. */
    const val SOURCE_MANAGER_URL = "https://github.com/dwp29/Syntenthica/tree/main/synthetica-manager"

    /** Upstream this Manager is derived from. */
    const val UPSTREAM_URL = "https://github.com/KernelSU-Next/KernelSU-Next"

    /** SPDX identifier of the licence this APK is distributed under. */
    const val LICENSE_SPDX = "GPL-3.0-only"

    const val LICENSE_NAME = "GNU General Public License v3.0"

    const val LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.txt"

    /**
     * Donation target. Intentionally blank for now: the row renders as a
     * disabled placeholder instead of guessing a wallet, link or account.
     * Fill this with a URL the author confirms and the row becomes live.
     */
    const val DONATE_URL = ""

    /** True when a real donation target has been configured. */
    val donateConfigured: Boolean get() = DONATE_URL.isNotBlank()
}
