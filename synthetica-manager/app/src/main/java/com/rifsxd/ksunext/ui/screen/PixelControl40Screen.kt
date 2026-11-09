package com.rifsxd.ksunext.ui.screen

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.ui.pixel.PixelActionResult40
import com.rifsxd.ksunext.ui.pixel.PixelControl40Page
import com.rifsxd.ksunext.ui.util.canActImmediate60
import com.rifsxd.ksunext.ui.util.probeUniversalRoot60
import com.rifsxd.ksunext.ui.util.runPixelAction40
import kotlinx.coroutines.launch

@Destination<RootGraph>
@Composable
fun PixelControl40Screen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var canAct by remember { mutableStateOf(canActImmediate60()) }
    LaunchedEffect(Unit) {
        if (!canAct) canAct = probeUniversalRoot60()
    }
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<PixelActionResult40?>(null) }
    PixelControl40Page(canAct, busy, result, onBack = { navigator.popBackStack() }, onAction = { action ->
        if (!busy && canAct) {
            busy = true
            result = null
            val kind = if (action == "telemetry" || action.startsWith("kmod_") || action.startsWith("diag_")) "universal" else "control"
            scope.launch {
                try { result = runPixelAction40(context, kind, action) } finally { busy = false }
            }
        }
    })
}
