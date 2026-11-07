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
import com.rifsxd.ksunext.ui.pixel.PixelControl40Page
import com.rifsxd.ksunext.ui.util.runPixelAction40
import kotlinx.coroutines.launch

@Destination<RootGraph>
@Composable
fun PixelControl40Screen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val canAct = Natives.isManager && Natives.isFullFeatured()
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<PixelActionResult40?>(null) }
    PixelControl40Page(canAct, busy, result, onBack = { navigator.popBackStack() }, onAction = { action ->
        if (!busy && canAct) {
            busy = true
            result = null
            scope.launch {
                try { result = runPixelAction40(context, "control", action) } finally { busy = false }
            }
        }
    })
}
