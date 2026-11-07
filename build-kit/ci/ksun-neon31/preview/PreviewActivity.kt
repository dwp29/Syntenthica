package com.rifsxd.ksunext

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.ui.device.DeviceCheckPage
import com.rifsxd.ksunext.ui.theme.GlassBackground
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosHeroCard
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.KernelSUTheme
import com.rifsxd.ksunext.ui.theme.NeonAppearanceControls
import com.rifsxd.ksunext.ui.theme.iosGlass

/** Separate preview: no native root backend, no shell, no network and no installs. */
class PreviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PreviewApp() }
    }
}

private data class Tab(val label: String, val icon: ImageVector)
private val tabs = listOf(
    Tab("Home", Icons.Rounded.Home),
    Tab("Root apps", Icons.Rounded.AdminPanelSettings),
    Tab("Modules", Icons.Rounded.GridView),
    Tab("Settings", Icons.Rounded.Settings),
)

@Composable
private fun PreviewApp() {
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var deviceOpen by rememberSaveable { mutableStateOf(false) }
    BackHandler(enabled = deviceOpen) { deviceOpen = false }
    KernelSUTheme {
        Box(modifier = Modifier.fillMaxSize()) {
            GlassBackground(wallpaperLayer = null)
            if (deviceOpen) {
                DeviceCheckPage(onBack = { deviceOpen = false })
            } else {
                Scaffold(
                    containerColor = Color.Transparent,
                    topBar = {
                        GlassTopBar(title = "Synthetica Preview", subtitle = "3.1.0 • PREVIEW ONLY",
                            actions = { IosPill(text = "DEMO", color = IosPinkDark) })
                    },
                    bottomBar = { PreviewDock(selected = selected, onSelected = { selected = it }) },
                ) { padding ->
                    AnimatedContent(
                        targetState = selected,
                        modifier = Modifier.fillMaxSize().padding(padding),
                        transitionSpec = { fadeIn(tween(260)) togetherWith fadeOut(tween(200)) },
                        label = "preview-tab",
                    ) { page ->
                        Column(
                            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                                .padding(horizontal = 16.dp, vertical = 16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            Text(
                                "PREVIEW ONLY — not a root Manager. Root and module data are examples; Device Check reads this device.",
                                modifier = Modifier.fillMaxWidth().iosGlass(shape = MaterialTheme.shapes.medium, elevation = 2.dp)
                                    .padding(horizontal = 14.dp, vertical = 11.dp),
                                color = MaterialTheme.colorScheme.onSurface,
                                style = MaterialTheme.typography.bodySmall,
                            )
                            when (page) {
                                0 -> {
                                    IosHeroCard(
                                        eyebrow = "STATUS • EXAMPLE", title = "Synthetica Manager", statusPill = "DEMO",
                                        statusColor = IosPinkDark, modePill = "SIMULATED",
                                        kernelLine = "Example kernel", metaLine = "Preview does not manage root access",
                                    )
                                    IosGroup(title = "TOOLS") {
                                        IosRow(Icons.Rounded.DeveloperBoard, IosCyanDark, stringResource(R.string.device31_title),
                                            subtitle = stringResource(R.string.device31_subtitle), showChevron = true,
                                            onClick = { deviceOpen = true })
                                    }
                                }
                                3 -> NeonAppearanceControls()
                                else -> IosGroup(title = "EXAMPLE") {
                                    IosRow(Icons.Rounded.GridView, IosBlueDark, "Preview only", subtitle = "No root or module changes are made.")
                                }
                            }
                            Spacer(Modifier.height(12.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PreviewDock(selected: Int, onSelected: (Int) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 18.dp, vertical = 12.dp)
            .iosGlass(shape = MaterialTheme.shapes.extraLarge, elevation = 12.dp).padding(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        tabs.forEachIndexed { index, tab ->
            val active = selected == index
            Column(
                modifier = Modifier.weight(1f).height(56.dp).clip(MaterialTheme.shapes.medium)
                    .background(if (active) MaterialTheme.colorScheme.primary.copy(alpha = 0.16f) else Color.Transparent)
                    .selectable(selected = active, role = Role.Tab, onClick = { onSelected(index) }),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                val color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                Icon(tab.icon, contentDescription = null, tint = color)
                Text(tab.label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium,
                    color = color, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}
