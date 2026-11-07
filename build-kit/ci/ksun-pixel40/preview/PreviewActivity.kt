package com.rifsxd.ksunext

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
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
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Public
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Speed
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.ui.device.DeviceCheckPage
import com.rifsxd.ksunext.ui.pixel.Diagnostics40
import com.rifsxd.ksunext.ui.pixel.PixelActionResult40
import com.rifsxd.ksunext.ui.pixel.PixelBoost40Page
import com.rifsxd.ksunext.ui.pixel.PixelControl40Page
import com.rifsxd.ksunext.ui.pixel.PixelDiagnostics40Page
import com.rifsxd.ksunext.ui.pixel.PixelSources40Page
import com.rifsxd.ksunext.ui.pixel.ProviderCandidate40
import com.rifsxd.ksunext.ui.theme.GlassBackground
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosHeroCard
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.KernelSUTheme
import com.rifsxd.ksunext.ui.theme.LocalPixelMotionEnabled
import com.rifsxd.ksunext.ui.theme.NeonAppearanceControls
import com.rifsxd.ksunext.ui.theme.iosGlass

/** Separate preview: NO native root backend, shell, network or installation. */
class PreviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PreviewApp() }
    }
}

private data class Tab(val label: String, val icon: ImageVector)
private val tabs = listOf(
    Tab("Home", Icons.Rounded.Home), Tab("Root apps", Icons.Rounded.AdminPanelSettings),
    Tab("Modules", Icons.Rounded.GridView), Tab("Settings", Icons.Rounded.Settings),
)

@Composable
private fun PreviewApp() {
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var page by rememberSaveable { mutableStateOf("") }
    var result by rememberSaveable { mutableStateOf("") }
    val context = LocalContext.current
    BackHandler(enabled = page.isNotEmpty()) { page = ""; result = "" }
    KernelSUTheme {
        val motion = LocalPixelMotionEnabled.current
        Box(modifier = Modifier.fillMaxSize()) {
            GlassBackground(wallpaperLayer = null)
            when (page) {
                "device" -> DeviceCheckPage(onBack = { page = "" })
                "zip" -> PreviewPreflightDemo(onBack = { page = "" })
                "sources" -> PixelSources40Page(onBack = { page = "" }, onOpen = {
                    Toast.makeText(context, "PREVIEW ONLY: link not opened", Toast.LENGTH_LONG).show()
                })
                "diagnostics" -> PixelDiagnostics40Page(
                    snapshot = Diagnostics40(loading = false, rootAccessible = true, susfsReported = true,
                        susfsVersion = "Example", susfsVariant = "DEMO", susfsFeatures = "EXAMPLE_FEATURE\nSIMULATED_ONLY",
                        zygiskProcessFlag = false, providers = listOf(
                            ProviderCandidate40("demo_rezygisk", "Example provider", true),
                            ProviderCandidate40("demo_neozygisk", "Second example", true))),
                    onRefresh = {}, onBack = { page = "" })
                "control" -> PixelControl40Page(true, false, result.takeIf { it.isNotEmpty() }?.let { PixelActionResult40(false, it) },
                    onAction = { result = "PREVIEW ONLY: simulated $it. No shell or settings changed." }, onBack = { page = ""; result = "" })
                "boost" -> PixelBoost40Page(true, false, result.takeIf { it.isNotEmpty() }?.let { PixelActionResult40(false, it) },
                    onAction = { result = "PREVIEW ONLY: simulated $it. No shell or settings changed." }, onBack = { page = ""; result = "" })
                else -> Scaffold(
                    containerColor = Color.Transparent,
                    topBar = { GlassTopBar(title = "Synthetica Preview", subtitle = "4.0.0 • PREVIEW ONLY",
                        actions = { IosPill(text = "DEMO", color = IosPinkDark) }) },
                    bottomBar = { PreviewDock(selected = selected, onSelected = { selected = it }) },
                ) { padding ->
                    AnimatedContent(
                        targetState = selected, modifier = Modifier.fillMaxSize().padding(padding),
                        transitionSpec = {
                            if (motion) fadeIn(tween(220)) togetherWith fadeOut(tween(180))
                            else EnterTransition.None togetherWith ExitTransition.None
                        }, label = "pixel-preview-tab",
                    ) { tab ->
                        Column(
                            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                                .padding(horizontal = 16.dp, vertical = 16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            Text("PREVIEW ONLY — not a root Manager. Root/module data and actions are simulated; Device Check reads this device.",
                                modifier = Modifier.fillMaxWidth().iosGlass(shape = MaterialTheme.shapes.medium).padding(14.dp),
                                color = MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.bodySmall)
                            when (tab) {
                                0 -> {
                                    IosHeroCard(eyebrow = "STATUS · EXAMPLE", title = "Synthetica Manager", statusPill = "DEMO",
                                        statusColor = IosPinkDark, modePill = "SIMULATED", kernelLine = "Example kernel",
                                        metaLine = "Preview does not manage root access")
                                    IosGroup(title = "TOOLS") {
                                        IosRow(Icons.Rounded.DeveloperBoard, IosCyanDark, stringResource(R.string.device31_title),
                                            subtitle = stringResource(R.string.device31_subtitle), showChevron = true, onClick = { page = "device" })
                                        IosGroupDivider()
                                        IosRow(Icons.Rounded.Hub, IosCyanDark, stringResource(R.string.pixel40_diagnostics_title),
                                            subtitle = "Simulated indicators", showChevron = true, onClick = { page = "diagnostics" })
                                        IosGroupDivider()
                                        IosRow(Icons.Rounded.Speed, IosOrangeDark, stringResource(R.string.pixel40_control_title),
                                            subtitle = "Simulation only", showChevron = true, onClick = { page = "control" })
                                        IosGroupDivider()
                                        IosRow(Icons.Rounded.Bolt, IosOrangeDark, stringResource(R.string.pixel40_boost_title),
                                            subtitle = "Simulation only", showChevron = true, onClick = { page = "boost" })
                                        IosGroupDivider()
                                        IosRow(Icons.Rounded.DeveloperBoard, IosBlueDark, "ZIP preflight preview",
                                            subtitle = "Demo samples only · no installation", showChevron = true, onClick = { page = "zip" })
                                    }
                                }
                                2 -> IosGroup(title = "EXPLORE") {
                                    IosRow(Icons.Rounded.Public, IosCyanDark, stringResource(R.string.pixel40_sources_action),
                                        subtitle = "Links are disabled in this preview", showChevron = true, onClick = { page = "sources" })
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
            .iosGlass(shape = MaterialTheme.shapes.extraLarge).padding(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        tabs.forEachIndexed { index, tab ->
            val active = selected == index
            Column(
                modifier = Modifier.weight(1f).height(56.dp).clip(MaterialTheme.shapes.medium)
                    .background(if (active) MaterialTheme.colorScheme.primary.copy(alpha = 0.16f) else Color.Transparent)
                    .selectable(selected = active, role = Role.Tab, onClick = { onSelected(index) }),
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
            ) {
                val color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                Icon(tab.icon, contentDescription = null, tint = color)
                Text(tab.label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium,
                    color = color, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}
