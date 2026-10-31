package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.os.Build
import android.os.Os
import android.os.PowerManager
import androidx.annotation.StringRes
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.Android
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.ExpandLess
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.PowerSettingsNew
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.SystemUpdateAlt
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.VisibilityOff
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.pm.PackageInfoCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.NavGraphs
import com.ramcosta.composedestinations.generated.destinations.BoostScreenDestination
import com.ramcosta.composedestinations.generated.destinations.InstallScreenDestination
import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.ModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SettingScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SuperUserScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.getKernelVersion
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.rememberScrollConnection
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosHeroCard
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRedDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosTeal
import com.rifsxd.ksunext.ui.theme.IosTile
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.util.getMetaModule
import com.rifsxd.ksunext.ui.util.getModuleCount
import com.rifsxd.ksunext.ui.util.getSELinuxStatus
import com.rifsxd.ksunext.ui.util.getSuSFS
import com.rifsxd.ksunext.ui.util.getSuSFSVariant
import com.rifsxd.ksunext.ui.util.getSuSFSVersion
import com.rifsxd.ksunext.ui.util.getSuperuserCount
import com.rifsxd.ksunext.ui.util.reboot
import com.rifsxd.ksunext.ui.util.rootAvailable
import com.rifsxd.ksunext.ui.viewmodel.ModuleViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private data class HomeEnvInfo(
    val unameRelease: String = "",
    val unameMachine: String = "",
    val managerVerName: String = "2.0",
    val managerVerCode: Long = 10000L,
    val hookMode: String = "Manual",
    val suSFSStatus: String = "",
    val suSFSVersion: String = "",
    val suSFSVariant: String = "",
    val metaModuleLabel: String = "None",
    val zygiskLabel: String = "Disabled",
    val selinuxLabel: String = "Enforcing",
    val moduleCount: Int = 0,
    val superuserCount: Int = 0,
)

@Destination<RootGraph>(start = true)
@Composable
fun HomeScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val kernelVersion = getKernelVersion()

    val isManager = Natives.isManager
    val fullFeatured = Natives.isFullFeatured()
    val ksuVersion = if (isManager) Natives.version else null
    val kernelUAPIVersion = if (isManager) Natives.kernelUAPIVersion else null
    val managerUAPIVersion = Natives.managerUAPIVersion
    val isSafeMode = if (isManager) Natives.isSafeMode else false
    val isLkm = if (isManager) Natives.isLkmMode else false

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

    val moduleViewModel: ModuleViewModel = viewModel()
    var envInfo by remember {
        val uname = runCatching { Os.uname() }.getOrNull()
        val mgr = runCatching { getManagerVersion(context) }.getOrDefault("2.0" to 10000L)
        mutableStateOf(
            HomeEnvInfo(
                unameRelease = uname?.release.orEmpty(),
                unameMachine = uname?.machine.orEmpty(),
                managerVerName = mgr.first,
                managerVerCode = mgr.second,
            )
        )
    }
    var detailsExpanded by rememberSaveable { mutableStateOf(false) }

    val selinuxEnforcingStr = stringResource(R.string.selinux_status_enforcing)
    LaunchedEffect(ksuVersion, fullFeatured, moduleViewModel.moduleList.size) {
        envInfo = withContext(Dispatchers.IO) {
            val uname = runCatching { Os.uname() }.getOrNull()
            val mgr = runCatching { getManagerVersion(context) }.getOrDefault("2.0" to 10000L)
            val hook = if (ksuVersion != null) {
                Natives.getHookMode()?.takeIf { it.isNotBlank() } ?: "Manual"
            } else "—"
            val susfs = if (ksuVersion != null) runCatching { getSuSFS() }.getOrDefault("") else ""
            val susfsVer = if (susfs == "Supported") runCatching { getSuSFSVersion() }.getOrDefault("") else ""
            val susfsVar = if (susfs == "Supported") runCatching { getSuSFSVariant() }.getOrDefault("") else ""

            val metaRaw = if (ksuVersion != null) runCatching { getMetaModule() }.getOrDefault("") else ""
            val metaMod = moduleViewModel.moduleList.firstOrNull { it.isMetaModule }
            val metaLabel = when {
                metaMod != null -> "${metaMod.name} ${metaMod.version}".trim()
                metaRaw.isNotBlank() && metaRaw != "None" -> metaRaw
                else -> "OverlayFS / Built-in"
            }

            val zygiskOn = ksuVersion != null && runCatching { Natives.isZygiskEnabled() }.getOrDefault(false)
            val zygiskMod = if (zygiskOn) moduleViewModel.moduleList.firstOrNull { it.isZygisk && it.enabled } else null
            val zygiskLabel = when {
                zygiskMod != null -> "${zygiskMod.name} ${zygiskMod.version}".trim()
                zygiskOn -> "Enabled"
                else -> "Disabled"
            }

            val modCnt = if (fullFeatured) runCatching { getModuleCount() }.getOrDefault(moduleViewModel.moduleList.size) else 0
            val suCnt = if (fullFeatured) runCatching { getSuperuserCount() }.getOrDefault(0) else 0

            HomeEnvInfo(
                unameRelease = uname?.release.orEmpty(),
                unameMachine = uname?.machine.orEmpty(),
                managerVerName = mgr.first,
                managerVerCode = mgr.second,
                hookMode = hook,
                suSFSStatus = susfs,
                suSFSVersion = susfsVer,
                suSFSVariant = susfsVar,
                metaModuleLabel = metaLabel,
                zygiskLabel = zygiskLabel,
                selinuxLabel = selinuxEnforcingStr,
                moduleCount = modCnt,
                superuserCount = suCnt,
            )
        }
    }

    val selinuxText = getSELinuxStatus()

    fun navigateTab(routeSpec: com.ramcosta.composedestinations.spec.DirectionDestinationSpec) {
        navigator.navigate(routeSpec) {
            popUpTo(NavGraphs.root.startRoute) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            var showRebootMenu by remember { mutableStateOf(false) }
            GlassTopBar(
                title = stringResource(R.string.app_name),
                subtitle = "2.0  •  UAPI v$managerUAPIVersion",
                leading = {
                    val badgeShape = RoundedCornerShape(10.dp)
                    Image(
                        painter = painterResource(R.drawable.ic_synthetica_emblem),
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .size(34.dp)
                            .clip(badgeShape)
                            .border(0.75.dp, Color.White.copy(alpha = 0.45f), badgeShape),
                    )
                },
                actions = {
                    if (navBarEnabled?.value == false) {
                        IconButton(onClick = { navigateTab(SettingScreenDestination) }) {
                            Icon(
                                imageVector = Icons.Rounded.Tune,
                                contentDescription = stringResource(R.string.settings),
                            )
                        }
                    }
                    IconButton(onClick = { navigator.navigate(InstallScreenDestination) }) {
                        Icon(
                            imageVector = Icons.Rounded.SystemUpdateAlt,
                            contentDescription = stringResource(R.string.install),
                        )
                    }
                    if (fullFeatured) {
                        Box {
                            IconButton(onClick = { showRebootMenu = true }) {
                                Icon(
                                    imageVector = Icons.Rounded.PowerSettingsNew,
                                    contentDescription = stringResource(R.string.reboot),
                                )
                            }
                            DropdownMenu(
                                expanded = showRebootMenu,
                                onDismissRequest = { showRebootMenu = false },
                            ) {
                                RebootDropdownItem(id = R.string.reboot)
                                RebootDropdownItem(id = R.string.reboot_userspace, reason = "soft-reboot")
                                val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
                                @Suppress("DEPRECATION")
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && pm?.isRebootingUserspaceSupported == true) {
                                    RebootDropdownItem(id = R.string.reboot_userspace, reason = "userspace")
                                }
                                RebootDropdownItem(id = R.string.reboot_recovery, reason = "recovery")
                                RebootDropdownItem(id = R.string.reboot_bootloader, reason = "bootloader")
                                RebootDropdownItem(id = R.string.reboot_download, reason = "download")
                                RebootDropdownItem(id = R.string.reboot_edl, reason = "edl")
                            }
                        }
                    }
                },
            )
        },
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
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            // 1. Flagship Frosted Hero Status Card
            val heroStatusPill = when {
                isSafeMode -> stringResource(R.string.safe_mode)
                fullFeatured -> stringResource(R.string.ios_home_rooted)
                else -> stringResource(R.string.ios_home_tap_install)
            }
            val heroStatusColor = when {
                isSafeMode -> IosOrangeDark
                fullFeatured -> IosGreenDark
                else -> IosRedDark
            }
            val modeLabel = when {
                !isManager -> null
                isLkm -> "LKM"
                else -> "BUILT-IN"
            }
            val metaLine = if (isManager && ksuVersion != null) {
                "KernelSU $ksuVersion  •  UAPI v${kernelUAPIVersion ?: managerUAPIVersion}  •  ${envInfo.hookMode} Hook"
            } else {
                stringResource(R.string.home_click_to_install)
            }

            IosHeroCard(
                eyebrow = stringResource(R.string.ios_home_active_kernel),
                title = if (isManager) "Synthetica 2.0" else stringResource(R.string.home_not_installed),
                statusPill = heroStatusPill,
                statusColor = heroStatusColor,
                modePill = modeLabel,
                kernelLine = envInfo.unameRelease.ifBlank { kernelVersion.toString() },
                metaLine = metaLine,
                onClick = if (!isManager) ({ navigator.navigate(InstallScreenDestination) }) else null,
            )

            // 2. Conditional Safety Warnings Only (no upstream GitHub update nag!)
            val requiresNewKernel = isManager && kernelUAPIVersion != null && managerUAPIVersion > kernelUAPIVersion
            val requiresNewManager = isManager && kernelUAPIVersion != null && managerUAPIVersion < kernelUAPIVersion
            if (requiresNewKernel) {
                WarningCard(
                    message = stringResource(
                        id = if (isLkm) R.string.require_kernel_version else R.string.require_kernel_version_gki,
                        kernelUAPIVersion!!,
                        managerUAPIVersion,
                    )
                )
            }
            if (requiresNewManager) {
                WarningCard(
                    message = stringResource(
                        id = R.string.require_manager_version,
                        managerUAPIVersion,
                        kernelUAPIVersion!!,
                    )
                )
            }
            if (ksuVersion != null && !rootAvailable()) {
                WarningCard(message = stringResource(R.string.grant_root_failed))
            }

            // 3. APK 1.16 2x2 Control-Center Menu Grid
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    IosTile(
                        icon = Icons.Rounded.GridView,
                        badgeColor = IosBlueDark,
                        title = stringResource(R.string.ios_tile_modules),
                        subtitle = stringResource(R.string.ios_tile_modules_sub),
                        badgeText = if (fullFeatured) {
                            stringResource(R.string.ios_items_fmt, envInfo.moduleCount)
                        } else null,
                        modifier = Modifier.weight(1f),
                        onClick = {
                            if (fullFeatured) navigateTab(ModuleScreenDestination)
                            else navigator.navigate(InstallScreenDestination)
                        },
                    )
                    IosTile(
                        icon = Icons.Rounded.AdminPanelSettings,
                        badgeColor = IosGreenDark,
                        title = stringResource(R.string.ios_tile_apps),
                        subtitle = stringResource(R.string.ios_tile_apps_sub),
                        badgeText = if (fullFeatured) {
                            stringResource(R.string.ios_items_fmt, envInfo.superuserCount)
                        } else null,
                        modifier = Modifier.weight(1f),
                        onClick = {
                            if (fullFeatured) navigateTab(SuperUserScreenDestination)
                            else navigator.navigate(InstallScreenDestination)
                        },
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    IosTile(
                        icon = Icons.Rounded.SystemUpdateAlt,
                        badgeColor = IosOrangeDark,
                        title = stringResource(R.string.ios_tile_install),
                        subtitle = stringResource(R.string.ios_tile_install_sub),
                        modifier = Modifier.weight(1f),
                        onClick = { navigator.navigate(InstallScreenDestination) },
                    )
                    IosTile(
                        icon = Icons.Rounded.Tune,
                        badgeColor = IosIndigoDark,
                        title = stringResource(R.string.ios_tile_settings),
                        subtitle = stringResource(R.string.ios_tile_settings_sub),
                        modifier = Modifier.weight(1f),
                        onClick = { navigateTab(SettingScreenDestination) },
                    )
                }
            }

            // 4. APK 1.16 Status Group + Expandable System Details
            val susfsSupported = envInfo.suSFSStatus == "Supported"
            val susfsPill = if (susfsSupported) {
                envInfo.suSFSVersion.ifBlank { stringResource(R.string.ios_home_on) }
            } else {
                stringResource(R.string.ios_home_off)
            }

            IosGroup(title = stringResource(R.string.ios_home_status)) {
                IosRow(
                    icon = Icons.Rounded.Memory,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.ios_home_kernel),
                    subtitle = envInfo.unameRelease,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Verified,
                    badgeColor = IosIndigoDark,
                    title = stringResource(R.string.ios_home_manager),
                    value = "${envInfo.managerVerName} (${envInfo.managerVerCode})",
                    pillText = "UAPI v$managerUAPIVersion",
                    pillColor = IosBlueDark,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Security,
                    badgeColor = if (fullFeatured) IosGreenDark else IosRedDark,
                    title = stringResource(R.string.ios_home_root_access),
                    value = if (fullFeatured) envInfo.hookMode else null,
                    pillText = stringResource(if (fullFeatured) R.string.ios_home_yes else R.string.ios_home_no),
                    pillColor = if (fullFeatured) IosGreenDark else IosRedDark,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.VisibilityOff,
                    badgeColor = IosTeal,
                    title = stringResource(R.string.ios_home_hiding),
                    subtitle = if (susfsSupported && envInfo.suSFSVariant.isNotBlank()) {
                        "${stringResource(R.string.ios_home_hiding_sub)} • ${envInfo.suSFSVariant}"
                    } else {
                        stringResource(R.string.ios_home_hiding_sub)
                    },
                    pillText = susfsPill,
                    pillColor = if (susfsSupported) IosTeal else IosCyanDark,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Info,
                    badgeColor = IosPurpleDark,
                    title = stringResource(R.string.ios_home_system_details),
                    onClick = { detailsExpanded = !detailsExpanded },
                    trailing = {
                        Icon(
                            imageVector = if (detailsExpanded) Icons.Rounded.ExpandLess else Icons.Rounded.ExpandMore,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    },
                )

                AnimatedVisibility(
                    visible = detailsExpanded,
                    enter = expandVertically() + fadeIn(),
                    exit = shrinkVertically() + fadeOut(),
                ) {
                    Column {
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.Layers,
                            badgeColor = IosCyanDark,
                            title = stringResource(R.string.ios_home_metamodule),
                            value = envInfo.metaModuleLabel,
                        )
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.Hub,
                            badgeColor = IosIndigoDark,
                            title = stringResource(R.string.ios_home_zygisk),
                            value = envInfo.zygiskLabel,
                        )
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.Security,
                            badgeColor = IosGreenDark,
                            title = stringResource(R.string.ios_home_selinux),
                            value = selinuxText,
                        )
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.Android,
                            badgeColor = IosTeal,
                            title = stringResource(R.string.ios_home_android_sdk),
                            value = "${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})",
                        )
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.DeveloperBoard,
                            badgeColor = IosOrangeDark,
                            title = stringResource(R.string.ios_home_abi),
                            value = Build.SUPPORTED_ABIS.firstOrNull() ?: envInfo.unameMachine,
                        )
                    }
                }
            }

            // 5. APK 1.16 Quick Tools Group (Synthetica Boost & Metamodule)
            IosGroup(title = stringResource(R.string.ios_quick_utilities)) {
                IosRow(
                    icon = Icons.Rounded.Bolt,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.ios_boost_title),
                    subtitle = stringResource(R.string.ios_boost_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(BoostScreenDestination) },
                )
                if (fullFeatured) {
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Layers,
                        badgeColor = IosCyanDark,
                        title = stringResource(R.string.ios_home_metamodule),
                        subtitle = stringResource(R.string.ios_metamodule_sub),
                        value = envInfo.metaModuleLabel,
                        showChevron = true,
                        onClick = { navigator.navigate(MetaModuleScreenDestination) },
                    )
                }
            }
        }
    }
}

@Composable
fun WarningCard(
    message: String,
    color: Color = IosRedDark,
    onClick: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(
                shape = RoundedCornerShape(20.dp),
                tintTop = color.copy(alpha = 0.22f),
                tintBottom = color.copy(alpha = 0.14f),
            )
            .let { mod -> if (onClick != null) mod.clickable(onClick = onClick) else mod }
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Rounded.WarningAmber,
            contentDescription = null,
            tint = color,
            modifier = Modifier.size(24.dp),
        )
        Spacer(Modifier.width(12.dp))
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
fun RebootDropdownItem(@StringRes id: Int, reason: String = "") {
    DropdownMenuItem(
        text = { Text(stringResource(id)) },
        onClick = { reboot(reason) },
    )
}

fun getManagerVersion(context: Context): Pair<String, Long> {
    val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)!!
    val versionCode = PackageInfoCompat.getLongVersionCode(packageInfo)
    return Pair(packageInfo.versionName ?: "2.0", versionCode)
}
