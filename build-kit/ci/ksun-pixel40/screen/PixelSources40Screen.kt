package com.rifsxd.ksunext.ui.screen

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.pixel.PixelSources40Page

/** Explicit confirmation in the page opens a browser; no downloads or installs here. */
@Destination<RootGraph>
@Composable
fun PixelSources40Screen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    PixelSources40Page(onBack = { navigator.popBackStack() }, onOpen = { url ->
        val uri = Uri.parse(url)
        val permitted = uri.scheme == "https" && uri.host in setOf("github.com", "modules.kernelsu.org", "modules.lsposed.org", "t.me")
        if (!permitted || runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }.isFailure) {
            Toast.makeText(context, R.string.pixel40_sources_no_browser, Toast.LENGTH_LONG).show()
        }
    })
}
