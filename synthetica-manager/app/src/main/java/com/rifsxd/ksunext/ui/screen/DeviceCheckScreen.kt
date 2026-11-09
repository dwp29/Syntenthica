package com.rifsxd.ksunext.ui.screen

import androidx.compose.runtime.Composable
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.ui.device.DeviceCheckPage

// This screen never invokes the KernelSU daemon or changes device settings.
@Destination<RootGraph>
@Composable
fun DeviceCheckScreen(navigator: DestinationsNavigator) {
    DeviceCheckPage(onBack = { navigator.popBackStack() })
}
