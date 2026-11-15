package com.rifsxd.ksunext.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Backup
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.CloudDownload
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Fence
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.MonitorHeart
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.SystemUpdateAlt
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.destinations.AboutScreenDestination
import com.ramcosta.composedestinations.generated.destinations.AppProfileTemplateScreenDestination
import com.ramcosta.composedestinations.generated.destinations.BackupRestoreScreenDestination
import com.ramcosta.composedestinations.generated.destinations.BoostScreenDestination
import com.ramcosta.composedestinations.generated.destinations.CustomizationScreenDestination
import com.ramcosta.composedestinations.generated.destinations.DeviceCheckScreenDestination
import com.ramcosta.composedestinations.generated.destinations.DownloadScreenDestination
import com.ramcosta.composedestinations.generated.destinations.InstallScreenDestination
import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.PixelControl40ScreenDestination
import com.ramcosta.composedestinations.generated.destinations.PixelDiagnostics40ScreenDestination
import com.ramcosta.composedestinations.generated.destinations.PixelSources40ScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SulogScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.rememberScrollConnection
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosTeal

/**
 * One door for every screen that is not a bottom-bar tab.
 *
 * Before this existed the app had 22 destinations and no inventory of them: seven
 * rows lived in Settings, three lived on Home, two were only reachable from a
 * module list, and About was three taps deep. Rows here are grouped by what the
 * user is trying to do, not by which file they live in.
 *
 * Rows that need root are hidden rather than shown and rejected, except where the
 * screen itself explains what is missing. That is the same rule the bottom bar uses.
 */
@Destination<RootGraph>
@Composable
fun ToolsScreen(navigator: DestinationsNavigator) {
    val scrollState = LocalScrollState.current
    val navBarEnabled = LocalNavBarEnabled.current
    val isNavBarHidden = (scrollState?.isScrollingDown?.value ?: false) || (navBarEnabled?.value == false)
    val navBarPadding =
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + if (isNavBarHidden) 0.dp else 112.dp

    val bottomBarScrollConnection = if (scrollState != null) {
        rememberScrollConnection(
            isScrollingDown = scrollState.isScrollingDown,
            scrollOffset = scrollState.scrollOffset,
            previousScrollOffset = scrollState.previousScrollOffset,
            threshold = 30f,
        )
    } else null

    val fullFeatured = Natives.isFullFeatured()

    Scaffold(
        containerColor = androidx.compose.ui.graphics.Color.Transparent,
        topBar = { GlassTopBar(title = stringResource(R.string.tools_title)) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .let { mod ->
                    if (bottomBarScrollConnection != null) mod.nestedScroll(bottomBarScrollConnection) else mod
                }
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp)
                .padding(bottom = navBarPadding),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Text(
                text = stringResource(R.string.tools_sub),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            // ---- Kernel and root -------------------------------------------
            IosGroup(title = stringResource(R.string.tools_group_kernel)) {
                IosRow(
                    icon = Icons.Rounded.SystemUpdateAlt,
                    badgeColor = IosOrangeDark,
                    title = stringResource(R.string.ios_tile_install),
                    subtitle = stringResource(R.string.ios_tile_install_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(InstallScreenDestination) },
                )
                if (fullFeatured) {
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Layers,
                        badgeColor = IosCyanDark,
                        title = stringResource(R.string.ios_home_metamodule),
                        subtitle = stringResource(R.string.ios_metamodule_sub),
                        showChevron = true,
                        onClick = { navigator.navigate(MetaModuleScreenDestination) },
                    )
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Fence,
                        badgeColor = IosTeal,
                        title = stringResource(R.string.settings_profile_template),
                        subtitle = stringResource(R.string.settings_profile_template_summary),
                        showChevron = true,
                        onClick = { navigator.navigate(AppProfileTemplateScreenDestination) },
                    )
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Backup,
                        badgeColor = IosIndigoDark,
                        title = stringResource(R.string.backup_restore),
                        showChevron = true,
                        onClick = { navigator.navigate(BackupRestoreScreenDestination) },
                    )
                }
            }

            // ---- Phone tools -------------------------------------------------
            IosGroup(title = stringResource(R.string.neon_quick_actions)) {
                IosRow(
                    icon = Icons.Rounded.MonitorHeart,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.pixel40_diagnostics_title),
                    subtitle = stringResource(R.string.pixel40_diagnostics_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(PixelDiagnostics40ScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Speed,
                    badgeColor = IosOrangeDark,
                    title = stringResource(R.string.pixel40_control_title),
                    subtitle = stringResource(R.string.pixel40_control_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(PixelControl40ScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Bolt,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.ios_boost_title),
                    subtitle = stringResource(R.string.ios_boost_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(BoostScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,
                    badgeColor = IosTeal,
                    title = stringResource(R.string.device31_title),
                    subtitle = stringResource(R.string.device31_subtitle),
                    showChevron = true,
                    onClick = { navigator.navigate(DeviceCheckScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Memory,
                    badgeColor = IosPurpleDark,
                    title = stringResource(R.string.pixel40_sources_action),
                    showChevron = true,
                    onClick = { navigator.navigate(PixelSources40ScreenDestination) },
                )
            }

            // ---- Logs, appearance, about -------------------------------------
            IosGroup(title = stringResource(R.string.tools_group_app)) {
                if (fullFeatured) {
                    IosRow(
                        icon = Icons.Rounded.Hub,
                        badgeColor = IosBlueDark,
                        title = stringResource(R.string.ios_sulog_viewer),
                        subtitle = stringResource(R.string.ios_sulog_viewer_sub),
                        showChevron = true,
                        onClick = { navigator.navigate(SulogScreenDestination) },
                    )
                    IosGroupDivider()
                }
                IosRow(
                    icon = Icons.Rounded.Palette,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.customization),
                    showChevron = true,
                    onClick = { navigator.navigate(CustomizationScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.CloudDownload,
                    badgeColor = IosGreenDark,
                    title = stringResource(R.string.module_repo_screen),
                    subtitle = stringResource(R.string.download_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(DownloadScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Info,
                    badgeColor = IosIndigoDark,
                    title = stringResource(R.string.about),
                    showChevron = true,
                    onClick = { navigator.navigate(AboutScreenDestination) },
                )
            }
        }
    }
}
