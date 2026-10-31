package com.rifsxd.ksunext.ui.screen

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.system.OsConstants
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Article
import androidx.compose.material.icons.automirrored.rounded.Undo
import androidx.compose.material.icons.rounded.Backup
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.DeleteForever
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Fence
import androidx.compose.material.icons.rounded.FolderDelete
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.Policy
import androidx.compose.material.icons.rounded.RadioButtonChecked
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.RemoveCircle
import androidx.compose.material.icons.rounded.RemoveModerator
import androidx.compose.material.icons.rounded.Save
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material.icons.rounded.Usb
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.core.content.edit
import com.maxkeppeker.sheets.core.models.base.Header
import com.maxkeppeker.sheets.core.models.base.IconSource
import com.maxkeppeker.sheets.core.models.base.rememberUseCaseState
import com.maxkeppeler.sheets.list.ListDialog
import com.maxkeppeler.sheets.list.models.ListOption
import com.maxkeppeler.sheets.list.models.ListSelection
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.destinations.AboutScreenDestination
import com.ramcosta.composedestinations.generated.destinations.AppProfileTemplateScreenDestination
import com.ramcosta.composedestinations.generated.destinations.BackupRestoreScreenDestination
import com.ramcosta.composedestinations.generated.destinations.BoostScreenDestination
import com.ramcosta.composedestinations.generated.destinations.CustomizationScreenDestination
import com.ramcosta.composedestinations.generated.destinations.DeveloperScreenDestination
import com.ramcosta.composedestinations.generated.destinations.FlashScreenDestination
import com.ramcosta.composedestinations.generated.destinations.MetaModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SulogScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.BuildConfig
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.component.ConfirmResult
import com.rifsxd.ksunext.ui.component.DialogHandle
import com.rifsxd.ksunext.ui.component.rememberConfirmDialog
import com.rifsxd.ksunext.ui.component.rememberCustomDialog
import com.rifsxd.ksunext.ui.component.rememberLoadingDialog
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
import com.rifsxd.ksunext.ui.theme.IosRedDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosSwitchRow
import com.rifsxd.ksunext.ui.theme.IosTeal
import com.rifsxd.ksunext.ui.util.LocalSnackbarHost
import com.rifsxd.ksunext.ui.util.execKsud
import com.rifsxd.ksunext.ui.util.getBugreportFile
import com.rifsxd.ksunext.ui.util.getBugreportFileUnrooted
import com.rifsxd.ksunext.ui.util.getFeaturePersistValue
import com.rifsxd.ksunext.ui.util.getFeatureStatus
import com.rifsxd.ksunext.ui.util.rootAvailable
import com.topjohnwu.superuser.ShellUtils
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Destination<RootGraph>
@Composable
fun SettingScreen(navigator: DestinationsNavigator) {
    val snackBarHost = LocalSnackbarHost.current
    val isManager = Natives.isManager
    val fullFeatured = Natives.isFullFeatured()
    val ksuVersion = if (isManager) Natives.version else null

    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

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

    val loadingDialog = rememberLoadingDialog()
    var isUnrooted by remember { mutableStateOf(!rootAvailable()) }
    LaunchedEffect(Unit) { isUnrooted = !rootAvailable() }

    val exportBugreportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/gzip")
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch(Dispatchers.IO) {
            loadingDialog.show()
            context.contentResolver.openOutputStream(uri)?.use { output ->
                val bugReport = if (isUnrooted) getBugreportFileUnrooted(context) else getBugreportFile(context)
                bugReport.inputStream().use { it.copyTo(output) }
            }
            loadingDialog.hide()
            snackBarHost.showSnackbar(context.getString(R.string.log_saved))
        }
    }

    var suCompatStatus by rememberSaveable { mutableStateOf("") }
    var kernelUmountStatus by rememberSaveable { mutableStateOf("") }
    var adbRootStatus by rememberSaveable { mutableStateOf("") }
    var selinuxHideStatus by rememberSaveable { mutableStateOf("") }
    var sulogStatus by rememberSaveable { mutableStateOf("") }
    var isSulogEnabled by rememberSaveable { mutableStateOf(false) }
    var avcSpoofStatus by rememberSaveable { mutableStateOf("") }

    LaunchedEffect(ksuVersion) {
        if (ksuVersion != null && rootAvailable()) {
            suCompatStatus = getFeatureStatus("su_compat")
            kernelUmountStatus = getFeatureStatus("kernel_umount")
            sulogStatus = getFeatureStatus("sulog")
            isSulogEnabled = getFeaturePersistValue("sulog") == 1L
            adbRootStatus = getFeatureStatus("adb_root")
            selinuxHideStatus = getFeatureStatus("selinux_hide")
            avcSpoofStatus = getFeatureStatus("avc_spoof")
        }
    }

    var showExportSheet by remember { mutableStateOf(false) }

    val uninstallConfirmDialog = rememberConfirmDialog()
    val uninstallDialog = rememberUninstallDialog { uninstallType ->
        scope.launch {
            val result = uninstallConfirmDialog.awaitConfirm(
                title = context.getString(uninstallType.title),
                content = context.getString(uninstallType.message),
            )
            if (result == ConfirmResult.Confirmed) {
                loadingDialog.withLoading {
                    when (uninstallType) {
                        UninstallType.PERMANENT -> navigator.navigate(FlashScreenDestination(FlashIt.FlashUninstall))
                        UninstallType.RESTORE_STOCK_IMAGE -> navigator.navigate(FlashScreenDestination(FlashIt.FlashRestore))
                        else -> Unit
                    }
                }
            }
        }
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            GlassTopBar(title = stringResource(R.string.ios_nav_settings))
        },
        snackbarHost = { SnackbarHost(snackBarHost, modifier = Modifier.padding(bottom = navBarPadding)) },
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
            // Group 1: Kernel & Root Features (when fullFeatured)
            if (ksuVersion != null && fullFeatured) {
                val suCompatSupported = suCompatStatus == "supported"
                val kernelUmountSupported = kernelUmountStatus == "supported"
                val sulogSupported = sulogStatus == "supported"
                val adbRootSupported = adbRootStatus == "supported"
                val selinuxHideSupported = selinuxHideStatus == "supported"
                val avcSpoofSupported = avcSpoofStatus == "supported"

                var umountChecked by rememberSaveable { mutableStateOf(Natives.isDefaultUmountModules()) }
                var isSuEnabled by rememberSaveable { mutableStateOf(Natives.isSuEnabled()) }
                var isKernelUmountEnabled by rememberSaveable { mutableStateOf(Natives.isKernelUmountEnabled()) }
                var isAdbRootEnabled by rememberSaveable { mutableStateOf(Natives.isAdbRootEnabled()) }
                var isSelinuxHideEnabled by rememberSaveable { mutableStateOf(Natives.isSelinuxHideEnabled()) }
                var isAvcSpoofEnabled by rememberSaveable { mutableStateOf(Natives.isAvcSpoofEnabled()) }

                IosGroup(title = stringResource(R.string.ios_group_kernel_root)) {
                    IosSwitchRow(
                        icon = Icons.Rounded.FolderDelete,
                        badgeColor = IosOrangeDark,
                        title = stringResource(R.string.settings_umount_modules_default),
                        subtitle = stringResource(R.string.settings_umount_modules_default_summary),
                        checked = umountChecked,
                        onCheckedChange = {
                            if (Natives.setDefaultUmountModules(it)) umountChecked = it
                        },
                    )
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.RemoveModerator,
                        badgeColor = IosGreenDark,
                        title = stringResource(R.string.settings_enable_su),
                        subtitle = if (suCompatSupported) stringResource(R.string.settings_enable_su_summary)
                        else stringResource(R.string.feature_status_unsupported_summary),
                        checked = isSuEnabled,
                        enabled = suCompatSupported,
                        onCheckedChange = { checked ->
                            if (Natives.setSuEnabled(checked)) {
                                execKsud("feature save", true)
                                prefs.edit { putInt("su_compat_mode", if (checked) 0 else 2) }
                                isSuEnabled = checked
                            }
                        },
                    )
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.RemoveCircle,
                        badgeColor = IosTeal,
                        title = stringResource(R.string.settings_enable_kernel_umount),
                        subtitle = if (kernelUmountSupported) stringResource(R.string.settings_enable_kernel_umount_summary)
                        else stringResource(R.string.feature_status_unsupported_summary),
                        checked = isKernelUmountEnabled,
                        enabled = kernelUmountSupported,
                        onCheckedChange = { checked ->
                            if (Natives.setKernelUmountEnabled(checked)) {
                                execKsud("feature save", true)
                                prefs.edit { putInt("kernel_umount_mode", if (checked) 0 else 2) }
                                isKernelUmountEnabled = checked
                            }
                        },
                    )
                    IosGroupDivider()
                    val sulogSub = when (sulogStatus) {
                        "unsupported" -> stringResource(R.string.feature_status_unsupported_summary)
                        "managed" -> stringResource(R.string.feature_status_managed_summary)
                        else -> stringResource(R.string.settings_sulog_summary)
                    }
                    IosSwitchRow(
                        icon = Icons.AutoMirrored.Rounded.Article,
                        badgeColor = IosBlueDark,
                        title = stringResource(R.string.settings_sulog),
                        subtitle = sulogSub,
                        checked = isSulogEnabled,
                        enabled = sulogSupported,
                        onCheckedChange = { checked ->
                            if (execKsud("feature set sulog ${if (checked) 1 else 0}", true)) {
                                execKsud("feature save", true)
                                isSulogEnabled = checked
                            }
                        },
                    )
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.Usb,
                        badgeColor = IosIndigoDark,
                        title = stringResource(R.string.settings_adb_root),
                        subtitle = if (adbRootSupported) stringResource(R.string.settings_adb_root_summary)
                        else stringResource(R.string.feature_status_unsupported_summary),
                        checked = isAdbRootEnabled,
                        enabled = adbRootSupported,
                        onCheckedChange = { checked ->
                            if (Natives.setAdbRootEnabled(checked)) {
                                execKsud("feature save", true)
                                prefs.edit { putInt("adb_root_mode", if (checked) 0 else 2) }
                                ShellUtils.fastCmd("setprop ctl.restart adbd")
                                isAdbRootEnabled = checked
                            }
                        },
                    )
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.Policy,
                        badgeColor = IosPurpleDark,
                        title = stringResource(R.string.settings_selinux_hide),
                        subtitle = if (selinuxHideSupported) stringResource(R.string.settings_selinux_hide_summary)
                        else stringResource(R.string.feature_status_unsupported_summary),
                        checked = isSelinuxHideEnabled,
                        enabled = selinuxHideSupported,
                        onCheckedChange = { checked ->
                            scope.launch(Dispatchers.IO) {
                                val status = Natives.setSelinuxHideEnabled(checked)
                                execKsud("feature save", true)
                                prefs.edit { putInt("selinux_hide_mode", if (checked) 0 else 2) }
                                withContext(Dispatchers.Main) {
                                    isSelinuxHideEnabled = checked
                                    if (status == -OsConstants.EAGAIN) {
                                        Toast.makeText(
                                            context,
                                            R.string.settings_selinux_hide_reboot_required,
                                            Toast.LENGTH_LONG,
                                        ).show()
                                    } else if (status != 0) {
                                        Toast.makeText(
                                            context,
                                            context.getString(R.string.settings_selinux_hide_failed, status),
                                            Toast.LENGTH_LONG,
                                        ).show()
                                    }
                                }
                            }
                        },
                    )
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.Shield,
                        badgeColor = IosCyanDark,
                        title = stringResource(R.string.settings_enable_avc_spoof),
                        subtitle = if (avcSpoofSupported) stringResource(R.string.settings_enable_avc_spoof_summary)
                        else stringResource(R.string.feature_status_unsupported_summary),
                        checked = isAvcSpoofEnabled,
                        enabled = avcSpoofSupported,
                        onCheckedChange = { checked ->
                            if (Natives.setAvcSpoofEnabled(checked)) {
                                execKsud("feature save", true)
                                prefs.edit { putInt("avc_spoof_mode", if (checked) 0 else 2) }
                                isAvcSpoofEnabled = checked
                            }
                        },
                    )
                }
            }

            // Group 2: Tools & Modules (APK 1.16 Menu Layout)
            IosGroup(title = stringResource(R.string.ios_group_tools)) {
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
                        showChevron = true,
                        onClick = { navigator.navigate(MetaModuleScreenDestination) },
                    )
                    IosGroupDivider()
                    IosRow(
                        icon = Icons.AutoMirrored.Rounded.Article,
                        badgeColor = IosBlueDark,
                        title = stringResource(R.string.ios_sulog_viewer),
                        subtitle = stringResource(R.string.ios_sulog_viewer_sub),
                        showChevron = true,
                        onClick = { navigator.navigate(SulogScreenDestination) },
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
                    if (Natives.isLkmMode) {
                        IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.Delete,
                            badgeColor = IosRedDark,
                            title = stringResource(R.string.settings_uninstall),
                            showChevron = true,
                            onClick = { uninstallDialog.show() },
                        )
                    }
                }
            }

            // Group 3: Appearance & App
            var requireBiometric by rememberSaveable {
                mutableStateOf(prefs.getBoolean("enable_biometric_lock", false))
            }
            var appLockTimeout by rememberSaveable {
                mutableLongStateOf(prefs.getLong("app_lock_timeout", 60000L))
            }
            var showTimeoutMenu by remember { mutableStateOf(false) }
            val timeoutOptions = remember {
                listOf(
                    0L to R.string.settings_app_lock_timeout_immediate,
                    60000L to R.string.settings_app_lock_timeout_1m,
                    300000L to R.string.settings_app_lock_timeout_5m,
                )
            }
            val timeoutLabel = stringResource(
                timeoutOptions.find { it.first == appLockTimeout }?.second
                    ?: R.string.settings_app_lock_timeout_1m
            )

            IosGroup(title = stringResource(R.string.ios_group_app)) {
                IosRow(
                    icon = Icons.Rounded.Palette,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.customization),
                    subtitle = stringResource(R.string.ios_customization_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(CustomizationScreenDestination) },
                )
                IosGroupDivider()
                IosSwitchRow(
                    icon = Icons.Rounded.Lock,
                    badgeColor = IosGreenDark,
                    title = stringResource(R.string.settings_app_lock),
                    subtitle = stringResource(R.string.settings_app_lock_summary),
                    checked = requireBiometric,
                    onCheckedChange = { newValue ->
                        val km = context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
                        if (newValue && !km.isDeviceSecure) {
                            Toast.makeText(
                                context,
                                context.getString(R.string.settings_app_lock_no_credential),
                                Toast.LENGTH_SHORT,
                            ).show()
                            return@IosSwitchRow
                        }
                        requireBiometric = newValue
                        prefs.edit { putBoolean("enable_biometric_lock", newValue) }
                    },
                )
                if (requireBiometric) {
                    IosGroupDivider()
                    Box {
                        IosRow(
                            icon = Icons.Rounded.Timer,
                            badgeColor = IosTeal,
                            title = stringResource(R.string.settings_app_lock_timeout),
                            value = timeoutLabel,
                            showChevron = true,
                            onClick = { showTimeoutMenu = true },
                        )
                        DropdownMenu(
                            expanded = showTimeoutMenu,
                            onDismissRequest = { showTimeoutMenu = false },
                        ) {
                            timeoutOptions.forEach { (time, labelRes) ->
                                DropdownMenuItem(
                                    text = { Text(stringResource(labelRes)) },
                                    trailingIcon = {
                                        Icon(
                                            imageVector = if (appLockTimeout == time) {
                                                Icons.Rounded.RadioButtonChecked
                                            } else {
                                                Icons.Rounded.RadioButtonUnchecked
                                            },
                                            contentDescription = null,
                                            tint = if (appLockTimeout == time) {
                                                MaterialTheme.colorScheme.primary
                                            } else {
                                                MaterialTheme.colorScheme.onSurfaceVariant
                                            },
                                        )
                                    },
                                    onClick = {
                                        appLockTimeout = time
                                        prefs.edit { putLong("app_lock_timeout", time) }
                                        showTimeoutMenu = false
                                    },
                                )
                            }
                        }
                    }
                }
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,
                    badgeColor = IosPurpleDark,
                    title = stringResource(R.string.developer),
                    subtitle = stringResource(R.string.ios_developer_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(DeveloperScreenDestination) },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.BugReport,
                    badgeColor = IosOrangeDark,
                    title = stringResource(if (isUnrooted) R.string.export_log_unrooted else R.string.export_log),
                    subtitle = stringResource(R.string.ios_export_sub),
                    showChevron = true,
                    onClick = { showExportSheet = true },
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Info,
                    badgeColor = IosIndigoDark,
                    title = stringResource(R.string.ios_about_title),
                    subtitle = stringResource(R.string.ios_about_sub),
                    showChevron = true,
                    onClick = { navigator.navigate(AboutScreenDestination) },
                )
            }
        }
    }

    if (showExportSheet) {
        ExportLogBottomSheet(
            onDismiss = { showExportSheet = false },
            onSave = {
                val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd_HH_mm")
                val current = LocalDateTime.now().format(formatter)
                exportBugreportLauncher.launch("Synthetica_bugreport_${current}.tar.gz")
                showExportSheet = false
            },
            onShare = {
                scope.launch {
                    val bugreport = loadingDialog.withLoading {
                        withContext(Dispatchers.IO) {
                            if (isUnrooted) getBugreportFileUnrooted(context) else getBugreportFile(context)
                        }
                    }
                    val uri: Uri = FileProvider.getUriForFile(
                        context,
                        "${BuildConfig.APPLICATION_ID}.fileprovider",
                        bugreport,
                    )
                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                        putExtra(Intent.EXTRA_STREAM, uri)
                        setDataAndType(uri, "application/gzip")
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    context.startActivity(
                        Intent.createChooser(shareIntent, context.getString(R.string.send_log))
                    )
                }
                showExportSheet = false
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExportLogBottomSheet(
    onDismiss: () -> Unit,
    onSave: () -> Unit,
    onShare: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 18.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Column(
                modifier = Modifier
                    .clip(MaterialTheme.shapes.medium)
                    .clickable(onClick = onSave)
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                IconButton(
                    onClick = onSave,
                    modifier = Modifier.size(56.dp).clip(CircleShape),
                ) {
                    Icon(Icons.Rounded.Save, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    text = stringResource(R.string.save_log),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.titleSmall,
                )
            }
            Column(
                modifier = Modifier
                    .clip(MaterialTheme.shapes.medium)
                    .clickable(onClick = onShare)
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                IconButton(
                    onClick = onShare,
                    modifier = Modifier.size(56.dp).clip(CircleShape),
                ) {
                    Icon(Icons.Rounded.Share, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    text = stringResource(R.string.send_log),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.titleSmall,
                )
            }
        }
        Spacer(Modifier.height(16.dp))
    }
}

enum class UninstallType(val title: Int, val message: Int, val icon: ImageVector) {
    TEMPORARY(
        R.string.settings_uninstall_temporary,
        R.string.settings_uninstall_temporary_message,
        Icons.Rounded.Delete,
    ),
    PERMANENT(
        R.string.settings_uninstall_permanent,
        R.string.settings_uninstall_permanent_message,
        Icons.Rounded.DeleteForever,
    ),
    RESTORE_STOCK_IMAGE(
        R.string.settings_restore_stock_image,
        R.string.settings_restore_stock_image_message,
        Icons.AutoMirrored.Rounded.Undo,
    ),
    NONE(0, 0, Icons.Rounded.Delete),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun rememberUninstallDialog(onSelected: (UninstallType) -> Unit): DialogHandle {
    return rememberCustomDialog { dismiss ->
        val options = listOf(
            UninstallType.PERMANENT,
            UninstallType.RESTORE_STOCK_IMAGE,
        )
        val listOptions = options.map {
            ListOption(
                titleText = stringResource(it.title),
                subtitleText = if (it.message != 0) stringResource(it.message) else null,
                icon = IconSource(it.icon),
            )
        }
        var selection = UninstallType.NONE
        ListDialog(
            state = rememberUseCaseState(
                visible = true,
                onFinishedRequest = {
                    if (selection != UninstallType.NONE) onSelected(selection)
                },
                onCloseRequest = { dismiss() },
            ),
            header = Header.Default(title = stringResource(R.string.settings_uninstall)),
            selection = ListSelection.Single(
                showRadioButtons = false,
                options = listOptions,
            ) { index, _ ->
                selection = options[index]
            },
        )
    }
}
