package com.rifsxd.ksunext.ui.screen

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.ui.pixel.PixelActionResult40
import com.rifsxd.ksunext.ui.pixel.PixelBoost40Page
import com.rifsxd.ksunext.ui.util.runPixelAction40
import kotlinx.coroutines.launch

/** Runtime-only redesign: old persistent scripts remain until explicitly removed. */
@Destination<RootGraph>
@Composable
fun BoostScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val canAct = Natives.isManager && Natives.isFullFeatured()
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<PixelActionResult40?>(null) }
    PixelBoost40Page(canAct, busy, result, onBack = { navigator.popBackStack() }, onAction = { action ->
        if (!busy && canAct) {
            busy = true
            result = null
            scope.launch {
                try { result = runPixelAction40(context, "boost", action) } finally { busy = false }
            }
        }
    })
}
