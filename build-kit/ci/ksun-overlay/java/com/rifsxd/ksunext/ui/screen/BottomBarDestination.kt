package com.rifsxd.ksunext.ui.screen

import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AdminPanelSettings
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.ui.graphics.vector.ImageVector
import com.ramcosta.composedestinations.generated.destinations.HomeScreenDestination
import com.ramcosta.composedestinations.generated.destinations.ModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SettingScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SuperUserScreenDestination
import com.ramcosta.composedestinations.spec.DirectionDestinationSpec
import com.rifsxd.ksunext.R

enum class BottomBarDestination(
    val direction: DirectionDestinationSpec,
    @StringRes val label: Int,
    val iconSelected: ImageVector,
    val iconNotSelected: ImageVector,
    val rootRequired: Boolean,
) {
    Home(
        HomeScreenDestination,
        R.string.ios_nav_home,
        Icons.Rounded.Home,
        Icons.Outlined.Home,
        false,
    ),
    SuperUser(
        SuperUserScreenDestination,
        R.string.ios_nav_apps,
        Icons.Rounded.AdminPanelSettings,
        Icons.Outlined.AdminPanelSettings,
        true,
    ),
    Module(
        ModuleScreenDestination,
        R.string.ios_nav_modules,
        Icons.Rounded.GridView,
        Icons.Outlined.GridView,
        true,
    ),
    Settings(
        SettingScreenDestination,
        R.string.ios_nav_settings,
        Icons.Rounded.Tune,
        Icons.Outlined.Tune,
        false,
    ),
}
