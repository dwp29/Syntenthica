package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.os.Build
import android.os.PowerManager
import android.system.Os
import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.PowerSettingsNew
import androidx.compose.material.icons.rounded.SystemUpdateAlt
import androidx.compose.material.icons.rounded.Tune
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.content.pm.PackageInfoCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.NavGraphs
import com.ramcosta.composedestinations.generated.destinations.InstallScreenDestination
import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SettingScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.BuildConfig
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.getKernelVersion
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.rememberScrollConnection
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosHeroCard
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosRedDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosTeal
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.util.RootChannel
import com.rifsxd.ksunext.ui.util.detectRootChannel
import com.rifsxd.ksunext.ui.util.diagnoseRoot60
import com.rifsxd.ksunext.ui.util.getMetaModule
import com.rifsxd.ksunext.ui.util.getModuleCount
import com.rifsxd.ksunext.ui.util.getSELinuxStatus
import com.rifsxd.ksunext.ui.util.getSuSFS
import com.rifsxd.ksunext.ui.util.getSuSFSVariant
import com.rifsxd.ksunext.ui.util.getSuSFSVersion
import com.rifsxd.ksunext.ui.util.getSuperuserCount
import com.rifsxd.ksunext.ui.util.probeUniversalRoot60
import com.rifsxd.ksunext.ui.util.reboot
import com.rifsxd.ksunext.ui.util.rootAvailable
import com.rifsxd.ksunext.ui.viewmodel.ModuleViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private data class HomeEnvInfo(
    val unameRelease: String = "",
    val unameMachine: String = "",
    val managerVerName: String = BuildConfig.VERSION_NAME,
    val managerVerCode: Long = BuildConfig.VERSION_CODE.toLong(),
    val hookMode: String = "Manual",
    val suSFSStatus: String = "",
    val suSFSVersion: String = "",
    val suSFSVariant: String = "",
    val metaModuleLabel: String = "None",
    val zygiskLabel: String = "Not reported in Manager",
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
        val mgr = runCatching { getManagerVersion(context) }.getOrDefault(BuildConfig.VERSION_NAME to BuildConfig.VERSION_CODE.toLong())
        mutableStateOf(
            HomeEnvInfo(
                unameRelease = uname?.release.orEmpty(),
                unameMachine = uname?.machine.orEmpty(),
                managerVerName = mgr.first,
                managerVerCode = mgr.second,
            )
        )
    }
    var universalRoot by remember { mutableStateOf(false) }
    // Only shown when the kernel is foreign, so the user can see *why* a feature
    // is unavailable instead of a status that silently lies.
    var rootChannel by remember { mutableStateOf(RootChannel.NONE) }
    var rootDiag by remember { mutableStateOf("") }
    LaunchedEffect(isManager) {
        if (!isManager) {
            universalRoot = probeUniversalRoot60()
            rootChannel = detectRootChannel()
            // When root exists but was not reached, the device itself has to
            // say why. Without this the only report was "no root", which the
            // user could not tell apart from a real permission problem.
            if (!universalRoot) rootDiag = diagnoseRoot60()
        }
    }

    val selinuxEnforcingStr = stringResource(R.string.selinux_status_enforcing)
    LaunchedEffect(ksuVersion, fullFeatured, moduleViewModel.moduleList.size) {
        envInfo = withContext(Dispatchers.IO) {
            val uname = runCatching { Os.uname() }.getOrNull()
            val mgr = runCatching { getManagerVersion(context) }.getOrDefault(BuildConfig.VERSION_NAME to BuildConfig.VERSION_CODE.toLong())
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
                else -> "Not reported"
            }

            val zygiskOn = ksuVersion != null && runCatching { Natives.isZygiskEnabled() }.getOrDefault(false)
            val zygiskMod = if (zygiskOn) moduleViewModel.moduleList.firstOrNull { it.isZygisk && it.enabled } else null
            val zygiskLabel = when {
                zygiskMod != null -> "${zygiskMod.name} ${zygiskMod.version}".trim()
                zygiskOn -> "Reported in Manager"
                else -> "Not reported in Manager"
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
    val managerSeccompMode = remember {
        // PR_GET_SECCOMP is per-thread; this measures the Manager's UI thread only.
        runCatching { Os.prctl(21, 0, 0, 0, 0) }.getOrDefault(-1)
    }
    val managerSeccompLabel = stringResource(when (managerSeccompMode) {
        0 -> R.string.neon_seccomp_disabled
        1 -> R.string.neon_seccomp_strict
        2 -> R.string.neon_seccomp_filter
        -1 -> R.string.neon_seccomp_unavailable
        else -> R.string.neon_seccomp_unknown
    })

    fun navigateTab(routeSpec: com.ramcosta.composedestinations.spec.DirectionDestinationSpec) {
        navigator.navigate(routeSpec) {
            popUpTo(NavGraphs.root.startRoute) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    val heroStatusPill = when {
        isSafeMode -> stringResource(R.string.safe_mode)
        fullFeatured -> stringResource(R.string.ios_home_rooted)
        universalRoot -> "UNIVERSAL ROOT"
        else -> stringResource(R.string.ios_home_tap_install)
    }
    val heroStatusColor = when {
        isSafeMode -> IosOrangeDark
        fullFeatured -> IosGreenDark
        universalRoot -> IosCyanDark
        else -> IosRedDark
    }
    val modeLabel = when {
        !isManager && universalRoot -> "BRIDGE"
        !isManager -> null
        isLkm -> "LKM"
        else -> "BUILT-IN"
    }
    val metaLine = when {
        isManager && ksuVersion != null ->
            "KernelSU $ksuVersion  •  UAPI v${kernelUAPIVersion ?: managerUAPIVersion}  •  ${envInfo.hookMode} Hook"
        universalRoot ->
            "Universal Root Bridge (UID 0)  •  UAPI v$managerUAPIVersion"
        else ->
            stringResource(R.string.home_click_to_install)
    }
    val susfsSupported = envInfo.suSFSStatus == "Supported"
    val susfsPill = if (susfsSupported) {
        envInfo.suSFSVersion.ifBlank { stringResource(R.string.pixel40_supported_short) }
    } else {
        stringResource(R.string.pixel40_unavailable_short)
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            var showRebootMenu by remember { mutableStateOf(false) }
            GlassTopBar(
                // The Hub writes the name once, as the wordmark; repeating the app
                // name in a bar title above it was the second-largest source of the
                // "everything is full" feeling the owner reported.
                title = heroStatusPill,
                subtitle = "${BuildConfig.VERSION_NAME}  •  UAPI v$managerUAPIVersion",
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
                .padding(bottom = navBarPadding),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            // ---- 1. Pager: one subject per card -------------------------------
            // The old Hub printed kernel, manager, root, SuSFS, seccomp and system
            // details stacked in five separate groups. Each is now a card the user
            // swipes to, so only one subject is on screen at a time.
            val pagerState = rememberPagerState { 3 }
            HorizontalPager(
                state = pagerState,
                contentPadding = PaddingValues(horizontal = 20.dp),
                pageSpacing = 12.dp,
                modifier = Modifier.fillMaxWidth(),
            ) { page ->
                when (page) {
                    // Page 1 keeps the themed, animated hero: it is the per-theme
                    // banner, and the pager is what finally gives it the screen to
                    // itself instead of stacking four more blocks under it.
                    0 -> IosHeroCard(
                        eyebrow = stringResource(R.string.ios_home_active_kernel),
                        title = if (isManager || universalRoot) stringResource(R.string.neon_manager_title) else stringResource(R.string.home_not_installed),
                        statusPill = heroStatusPill,
                        statusColor = heroStatusColor,
                        modePill = modeLabel,
                        kernelLine = envInfo.unameRelease.ifBlank { kernelVersion.toString() },
                        metaLine = metaLine,
                        onClick = if (!isManager && !universalRoot) ({ navigator.navigate(InstallScreenDestination) }) else null,
                    )
                    1 -> HubPanel(eyebrow = stringResource(R.string.ios_home_manager)) {
                        HubLine(
                            label = stringResource(R.string.ios_home_root_access),
                            value = if (fullFeatured) stringResource(R.string.ios_home_yes) else stringResource(R.string.ios_home_no),
                            tint = if (fullFeatured) IosGreenDark else IosRedDark,
                        )
                        HubLine(label = stringResource(R.string.ios_home_manager), value = "${envInfo.managerVerName} (${envInfo.managerVerCode})")
                        HubLine(label = stringResource(R.string.ios_home_hook), value = envInfo.hookMode)
                        HubLine(label = stringResource(R.string.ios_home_uapi), value = "v$managerUAPIVersion")
                    }
                    else -> HubPanel(eyebrow = stringResource(R.string.ios_home_hiding)) {
                        HubLine(
                            label = stringResource(R.string.ios_home_hiding),
                            value = susfsPill,
                            tint = if (susfsSupported) IosTeal else IosCyanDark,
                        )
                        HubLine(label = stringResource(R.string.neon_seccomp_title), value = managerSeccompLabel)
                        HubLine(label = stringResource(R.string.ios_home_selinux), value = selinuxText)
                        HubLine(label = stringResource(R.string.ios_home_android_sdk), value = "${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})")
                    }
                }
            }

            val scope = rememberCoroutineScope()
            PagerDots(
                count = 3,
                selectedIndex = pagerState.currentPage,
                activeColor = MaterialTheme.colorScheme.primary,
                inactiveColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.35f),
                // A dot that only reports position is decoration. Tapping one is how
                // you reach page 3 without three swipes.
                onSelect = { page -> scope.launch { pagerState.animateScrollToPage(page) } },
                dotLabels = List(3) { page -> stringResource(R.string.ios_home_pager_dot, page + 1) },
            )

            // ---- 2. Warnings: only when measured ------------------------------
            val requiresNewKernel = isManager && kernelUAPIVersion != null && managerUAPIVersion > kernelUAPIVersion
            val requiresNewManager = isManager && kernelUAPIVersion != null && managerUAPIVersion < kernelUAPIVersion
            Column(
                modifier = Modifier.padding(horizontal = 20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
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
            }

            // ---- 3. Root bridge: one row, not a whole group -------------------
            Column(modifier = Modifier.padding(horizontal = 20.dp)) {
                if (!isManager) {
                    IosGroup(
                        title = stringResource(R.string.manager60_universal_bridge_title),
                        footer = stringResource(
                            if (universalRoot) R.string.manager60_bridge_row_sub
                            else R.string.manager60_universal_mode_sub,
                        ),
                    ) {
                        IosRow(
                            icon = Icons.Rounded.Hub,
                            badgeColor = if (universalRoot) IosCyanDark else IosOrangeDark,
                            title = stringResource(R.string.manager60_universal_mode),
                            subtitle = when {
                                universalRoot && rootChannel == RootChannel.SU ->
                                    stringResource(R.string.manager60_bridge_row_sub_su)
                                universalRoot -> stringResource(R.string.manager60_bridge_row_sub)
                                // No root: name the exact layer that failed instead of
                                // telling the user to install a kernel that may already
                                // be installed but signed for another manager.
                                rootChannel == RootChannel.SU_DENIED ->
                                    stringResource(R.string.manager60_no_root_reason)
                                rootChannel == RootChannel.SU_ABSENT ->
                                    stringResource(R.string.manager60_no_su_reason)
                                else -> stringResource(R.string.manager60_no_su_reason)
                            } + if (rootDiag.isNotBlank()) " · $rootDiag" else "",
                            // The diagnostic tail must stay readable; two lines cut
                            // it off mid-word, which is how the cause stayed hidden.
                            subtitleMaxLines = if (rootDiag.isNotBlank()) 6 else 2,
                            pill = stringResource(
                                if (universalRoot) R.string.manager60_bridge_active
                                else R.string.manager60_bridge_inactive
                            ),
                            pillColor = if (universalRoot) IosGreenDark else IosOrangeDark,
                        )
                    }
                } else {
                    IosGroup(title = stringResource(R.string.manager60_universal_bridge_title)) {
                        IosRow(
                            icon = Icons.Rounded.Hub,
                            badgeColor = IosCyanDark,
                            title = stringResource(R.string.manager60_universal_mode),
                            subtitle = stringResource(R.string.manager60_bridge_row_sub_native),
                            pill = stringResource(R.string.manager60_bridge_native),
                            pillColor = IosGreenDark,
                        )
                    }
                }
            }

            // ---- 4. Three rows to the rest of the app -------------------------
            // The four quick-access tiles that lived here duplicated the bottom
            // bar. Modules and Root apps are one tap away there already; this is
            // the third door, for Download and the tool screens.
            Column(modifier = Modifier.padding(horizontal = 20.dp)) {
                IosGroup(title = stringResource(R.string.ios_group_tools)) {
                    IosRow(
                        icon = Icons.Rounded.SystemUpdateAlt,
                        badgeColor = IosOrangeDark,
                        title = stringResource(R.string.ios_tile_install),
                        subtitle = stringResource(R.string.ios_tile_install_sub),
                        showChevron = true,
                        onClick = { navigator.navigate(InstallScreenDestination) },
                    )
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Layers,
                        badgeColor = IosCyanDark,
                        title = stringResource(R.string.ios_home_metamodule),
                        subtitle = stringResource(R.string.ios_metamodule_sub),
                        value = envInfo.metaModuleLabel,
                        showChevron = true,
                        onClick = {
                            if (fullFeatured) navigator.navigate(MetaModuleScreenDestination)
                            else navigator.navigate(InstallScreenDestination)
                        },
                    )
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.Rounded.Tune,
                        badgeColor = IosIndigoDark,
                        title = stringResource(R.string.ios_tile_settings),
                        subtitle = stringResource(R.string.ios_tile_settings_sub),
                        showChevron = true,
                        onClick = { navigateTab(SettingScreenDestination) },
                    )
                }
            }
        }
    }
}

/** One card of the Hub pager: an eyebrow, then label/value lines. */
@Composable
private fun HubPanel(eyebrow: String, content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(22.dp)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(shape = shape, tintTop = MaterialTheme.colorScheme.surface.copy(alpha = 0.55f))
            .padding(horizontal = 18.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = eyebrow.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        content()
    }
}

@Composable
private fun HubLine(label: String, value: String, tint: Color? = null) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = tint ?: MaterialTheme.colorScheme.onSurface,
        )
    }
}

/** The dots under the pager: they report position and jump to a page when tapped. */
@Composable
private fun PagerDots(
    count: Int,
    selectedIndex: Int,
    activeColor: Color,
    inactiveColor: Color,
    onSelect: (Int) -> Unit,
    dotLabels: List<String>,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(count) { index ->
            // 32dp of touch target around a 6dp dot; the dot itself stays small.
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .semantics {
                        contentDescription = dotLabels[index]
                        role = Role.Tab
                        selected = index == selectedIndex
                    }
                    .clickable { onSelect(index) },
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(if (index == selectedIndex) 8.dp else 6.dp)
                        .background(
                            color = if (index == selectedIndex) activeColor else inactiveColor,
                            shape = CircleShape,
                        ),
                )
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
    return Pair(packageInfo.versionName ?: BuildConfig.VERSION_NAME, versionCode)
}
