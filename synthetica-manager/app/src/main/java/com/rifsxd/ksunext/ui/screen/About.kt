package com.rifsxd.ksunext.ui.screen

import android.system.Os
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
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.Gavel
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.Person
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
import com.rifsxd.ksunext.ui.component.BrandIconRow
import com.rifsxd.ksunext.ui.component.rememberSafeLinkOpener
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.LocalManagerStyle
import com.rifsxd.ksunext.ui.theme.ManagerStyle
import com.rifsxd.ksunext.ui.theme.emblemResForStyle
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosIndigoDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.util.AppCredit60

@Destination<RootGraph>
@Composable
fun AboutScreen(navigator: DestinationsNavigator) {
    val openLink = rememberSafeLinkOpener()
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
                val activeStyle = LocalManagerStyle.current
                val iconShape = if (activeStyle == ManagerStyle.PIXEL) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.extraLarge
                Image(
                    painter = painterResource(emblemResForStyle(activeStyle)),
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

            // Who built this APK. The Telegram row is the only contact channel and
            // opens the profile directly in the Telegram app.
            IosGroup(title = stringResource(R.string.about_author_group)) {
                IosRow(
                    icon = Icons.Rounded.Person,
                    badgeColor = IosBlueDark,
                    title = stringResource(R.string.about_author_name),
                    subtitle = stringResource(R.string.about_author_role),
                )
                IosGroupDivider()
                BrandIconRow(
                    drawableRes = R.drawable.ic_telegram,
                    badgeColor = IosCyanDark,
                    title = AppCredit60.TELEGRAM_HANDLE,
                    subtitle = stringResource(R.string.about_author_tg_sub),
                    showChevron = true,
                    onClick = {
                        openLink(AppCredit60.TELEGRAM_URL, R.string.about_link_failed)
                    },
                )
            }

            // GitHub/source links are deliberately not shown here. The GPL-3.0
            // obligation is answered by the written source offer shipped with
            // the tree (synthetica-manager/SOURCE-OFFER.md), so the licence
            // group below stays exactly as it is: removing the licence or its
            // notice would breach the terms this APK is distributed under.
            // Licence. GPL-3.0 is not decoration: this APK is a derivative of
            // KernelSU-Next, so the licence and its notice must stay visible.
            IosGroup(title = stringResource(R.string.about_license)) {
                IosRow(
                    icon = Icons.Rounded.Gavel,
                    badgeColor = IosGreenDark,
                    title = AppCredit60.LICENSE_NAME,
                    subtitle = stringResource(R.string.about_license_sub),
                    pill = AppCredit60.LICENSE_SPDX,
                    pillColor = IosGreenDark,
                )
                IosGroupDivider()
                IosRow(
                    icon = Icons.Rounded.Description,
                    badgeColor = IosGreenDark,
                    title = stringResource(R.string.about_license_open),
                    subtitle = "gnu.org/licenses/gpl-3.0.txt",
                    showChevron = true,
                    onClick = {
                        openLink(AppCredit60.LICENSE_URL, R.string.about_link_failed)
                    },
                )
            }

            // Donation slot: reserved on purpose, disabled on purpose. No wallet
            // and no provider is invented while the author has not chosen one.
            IosGroup(
                title = stringResource(R.string.about_donate_group),
                footer = stringResource(R.string.about_donate_sub_empty),
            ) {
                BrandIconRow(
                    drawableRes = R.drawable.ic_donate_placeholder,
                    badgeColor = IosPinkDark,
                    title = stringResource(R.string.about_donate),
                    subtitle = stringResource(R.string.about_donate_sub_empty),
                    pill = stringResource(R.string.about_donate_soon),
                    pillColor = IosPinkDark,
                    enabled = false,
                )
            }

            IosGroup(
                title = stringResource(R.string.synthetica_about_credits_group),
                footer = stringResource(R.string.synthetica_about_credits_sub),
            ) {
                // Attribution without a repository link: GPL-3.0 asks for the
                // notice, not for a clickable URL in the UI.
                IosRow(
                    icon = Icons.Rounded.Code,
                    badgeColor = IosPurpleDark,
                    title = "KernelSU-Next & SuSFS",
                    subtitle = stringResource(R.string.about_credits_upstream_sub),
                    showChevron = false,
                )
            }
        }
    }
}
