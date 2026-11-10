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

    // Source/repository URLs are deliberately absent: the About page must not
    // carry a GitHub link. GPL-3.0 still requires a written source offer for a
    // binary distribution, and that obligation is met by
    // synthetica-manager/SOURCE-OFFER.md shipped inside this tree. Removing the
    // offer as well would put the distribution outside the licence.

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
