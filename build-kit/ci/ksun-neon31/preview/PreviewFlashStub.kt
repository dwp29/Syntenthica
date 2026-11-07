package com.rifsxd.ksunext.ui.screen

import android.net.Uri

/** Preview-only value objects. This app has no installer or root backend. */
internal sealed class FlashIt {
    data class FlashModules(
        val uris: List<Uri>, val allowAnyKernel: Boolean = false, val approvedHashes: List<String> = emptyList()
    ) : FlashIt()
    data class FlashAnyKernel(val uri: Uri, val approvedHash: String = "") : FlashIt()
}
