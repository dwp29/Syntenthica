package com.rifsxd.ksunext.ui.screen

import android.os.Os
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Code
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.dropUnlessResumed
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.BuildConfig
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.iosGlass

@Destination<RootGraph>
@Composable
fun AboutScreen(navigator: DestinationsNavigator) {
    val uriHandler = LocalUriHandler.current
    val navBottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val uname = Os.uname()
    val isManager = Natives.isManager
    val ksuVer = if (isManager) Natives.version.toString() else "—"
    val kernelUapi = if (isManager) "v${Natives.kernelUAPIVersion}" else "—"
    val managerUapi = "v${Natives.managerUAPIVersion}"

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            GlassTopBar(
                title = stringResource(R.string.ios_about_title),
                onBack = dropUnlessResumed { navigator.popBackStack() },
            )
        },
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
            // Centered Liquid Glass Emblem Pedestal Card
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .iosGlass(shape = RoundedCornerShape(26.dp))
                    .padding(horizontal = 24.dp, vertical = 26.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                val iconShape = RoundedCornerShape(24.dp)
                Image(
                    painter = painterResource(R.drawable.ic_synthetica_emblem),
                    contentDescription = "Synthetica",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(88.dp)
                        .shadow(14.dp, iconShape)
                        .clip(iconShape)
                        .border(1.dp, Color.White.copy(alpha = 0.55f), iconShape),
                )
                Spacer(Modifier.height(14.dp))
                Text(
                    text = "Synthetica",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = stringResource(R.string.synthetica_about_tagline),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(12.dp))
                IosPill(
                    text = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) • UAPI $managerUapi",
                    color = IosBlueDark,
                )
            }

            IosGroup(title = stringResource(R.string.synthetica_about_build_group)) {
                IosRow(
                    icon = Icons.Rounded.Verified,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.ios_home_manager),
                    value = "${BuildConfig.APPLICATION_ID} • ${BuildConfig.VERSION_NAME}",
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Memory,
                    badgeColor = IosCyanDark,
                    title = stringResource(R.string.ios_home_kernel),
                    subtitle = uname.release,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Security,
                    badgeColor = IosGreenDark,
                    title = stringResource(R.string.synthetica_about_protocol),
                    value = "KSU $ksuVer • Kernel $kernelUapi / App $managerUapi",
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.DeveloperBoard,
                    badgeColor = IosIndigoDark,
                    title = stringResource(R.string.synthetica_about_platform),
                    subtitle = stringResource(R.string.synthetica_about_platform_val),
                )
            }

            IosGroup(
                title = stringResource(R.string.synthetica_about_credits_group),
                footer = stringResource(R.string.synthetica_about_credits_sub),
            ) {
                IosRow(
                    icon = Icons.Rounded.Code,
                    badgeColor = IosPurpleDark,
                    title = "KernelSU-Next & SuSFS",
                    subtitle = "github.com/KernelSU-Next/KernelSU-Next • GPL-3.0",
                    showChevron = true,
                    onClick = { uriHandler.openUri("https://github.com/KernelSU-Next/KernelSU-Next") },
                )
            }
        }
    }
}
