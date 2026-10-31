package com.rifsxd.ksunext.ui.screen

import android.content.Context
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Contrast
import androidx.compose.material.icons.rounded.Dock
import androidx.compose.material.icons.rounded.RadioButtonChecked
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.Translate
import androidx.compose.material.icons.rounded.ViewCarousel
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.dropUnlessResumed
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.MainActivity
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosSwitchRow
import com.rifsxd.ksunext.ui.util.LocalSnackbarHost
import com.rifsxd.ksunext.ui.util.LocaleHelper
import com.rifsxd.ksunext.ui.util.refreshActivity

@OptIn(ExperimentalMaterial3Api::class)
@Destination<RootGraph>
@Composable
fun CustomizationScreen(navigator: DestinationsNavigator) {
    val snackBarHost = LocalSnackbarHost.current
    val isManager = Natives.isManager
    val ksuVersion = if (isManager) Natives.version else null
    val context = LocalContext.current
    val activity = context as? MainActivity
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    val navBottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    var currentAppLocale by remember { mutableStateOf(LocaleHelper.getCurrentAppLocale(context)) }
    var showLanguageSheet by remember { mutableStateOf(false) }

    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
        currentAppLocale = LocaleHelper.getCurrentAppLocale(context)
    }

    val languageOptions = remember(context) {
        listOf(
            LocaleHelper.SYSTEM_LANGUAGE_TAG to context.getString(R.string.system_default)
        ) + LocaleHelper.getSupportedLocales(context)
            .map { it.toLanguageTag() to it.getDisplayName(it) }
            .sortedBy { (_, displayName) -> displayName }
    }
    val currentLanguageTag = currentAppLocale?.toLanguageTag() ?: LocaleHelper.SYSTEM_LANGUAGE_TAG
    val currentLanguageDisplay = currentAppLocale?.let { it.getDisplayName(it) }
        ?: stringResource(R.string.system_default)

    var enableAmoled by rememberSaveable {
        mutableStateOf(prefs.getBoolean("enable_amoled", false))
    }
    var useBanner by rememberSaveable {
        mutableStateOf(prefs.getBoolean("use_banner", true))
    }
    var enableNavBar by rememberSaveable {
        mutableStateOf(prefs.getBoolean("enable_navbar", true))
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            GlassTopBar(
                title = stringResource(R.string.customization),
                subtitle = stringResource(R.string.ios_customization_sub),
                onBack = dropUnlessResumed { navigator.popBackStack() },
            )
        },
        snackbarHost = { SnackbarHost(snackBarHost, modifier = Modifier.padding(bottom = navBottom)) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp)
                .padding(bottom = navBottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            IosGroup(title = stringResource(R.string.synthetica_custom_glass_group)) {
                IosRow(
                    icon = Icons.Rounded.Translate,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.settings_language),
                    value = currentLanguageDisplay,
                    showChevron = true,
                    onClick = { showLanguageSheet = true },
                )
                if (isSystemInDarkTheme()) {
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.Contrast,
                        badgeColor = IosIndigoDark,
                        title = stringResource(R.string.synthetica_amoled_glass_title),
                        subtitle = stringResource(R.string.synthetica_amoled_glass_sub),
                        checked = enableAmoled,
                        onCheckedChange = { checked ->
                            activity?.setAmoledMode(checked)
                            enableAmoled = checked
                        },
                    )
                }
            }

            IosGroup(title = stringResource(R.string.synthetica_custom_layout_group)) {
                IosSwitchRow(
                    icon = Icons.Rounded.Dock,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.settings_navbar),
                    subtitle = stringResource(R.string.settings_navbar_summary),
                    checked = enableNavBar,
                    onCheckedChange = { checked ->
                        activity?.setNavBarEnabled(checked)
                        enableNavBar = checked
                    },
                )
                if (ksuVersion != null) {
                    IosGroupDivider()
                    IosSwitchRow(
                        icon = Icons.Rounded.ViewCarousel,
                        badgeColor = IosPurpleDark,
                        title = stringResource(R.string.settings_banner),
                        subtitle = stringResource(R.string.settings_banner_summary),
                        checked = useBanner,
                        onCheckedChange = { checked ->
                            prefs.edit { putBoolean("use_banner", checked) }
                            useBanner = checked
                        },
                    )
                }
            }
        }
    }

    if (showLanguageSheet) {
        LanguageBottomSheet(
            options = languageOptions,
            selectedLanguageTag = currentLanguageTag,
            onDismiss = { showLanguageSheet = false },
            onLanguageSelected = { languageTag ->
                showLanguageSheet = false
                if (languageTag != currentLanguageTag) {
                    LocaleHelper.setAppLocale(context, languageTag)
                    currentAppLocale = LocaleHelper.getCurrentAppLocale(context)
                    if (!LocaleHelper.usesFrameworkLocaleManager) {
                        refreshActivity(context)
                    }
                }
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LanguageBottomSheet(
    options: List<Pair<String, String>>,
    selectedLanguageTag: String,
    onDismiss: () -> Unit,
    onLanguageSelected: (String) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
    ) {
        Text(
            text = stringResource(R.string.settings_language),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 24.dp, vertical = 12.dp),
        )
        LazyColumn(modifier = Modifier.fillMaxWidth()) {
            items(options, key = { it.first }) { (tag, label) ->
                val selected = tag == selectedLanguageTag
                ListItem(
                    colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                    headlineContent = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = label,
                                fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                            )
                        }
                    },
                    leadingContent = {
                        Icon(
                            imageVector = if (selected) Icons.Rounded.RadioButtonChecked else Icons.Rounded.RadioButtonUnchecked,
                            contentDescription = null,
                            tint = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onLanguageSelected(tag) },
                )
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
