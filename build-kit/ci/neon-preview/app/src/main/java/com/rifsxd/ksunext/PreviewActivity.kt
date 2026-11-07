package com.rifsxd.ksunext

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Contrast
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.SystemUpdateAlt
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.ui.theme.GlassBackground
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBadgeIcon
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosHeroCard
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPinkDark
import com.rifsxd.ksunext.ui.theme.IosPill
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosSwitchRow
import com.rifsxd.ksunext.ui.theme.IosTile
import com.rifsxd.ksunext.ui.theme.KernelSUTheme
import com.rifsxd.ksunext.ui.theme.NeonAccentOptions
import com.rifsxd.ksunext.ui.theme.NeonAccentState
import com.rifsxd.ksunext.ui.theme.NeonMotionState
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.theme.setNeonAccent
import com.rifsxd.ksunext.ui.theme.setNeonMotion

/** Isolated visual demo: no root access, native library, network or device tuning. */
class PreviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PreviewApp() }
    }
}

private data class PreviewTab(val label: String, val icon: ImageVector)
private val previewTabs = listOf(
    PreviewTab("Beranda", Icons.Rounded.Home),
    PreviewTab("Root apps", Icons.Rounded.AdminPanelSettings),
    PreviewTab("Modul", Icons.Rounded.GridView),
    PreviewTab("Setelan", Icons.Rounded.Tune),
)

@Composable
private fun PreviewApp() {
    val context = LocalContext.current
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var amoled by rememberSaveable { mutableStateOf(false) }
    KernelSUTheme(amoledMode = amoled) {
        Box(modifier = Modifier.fillMaxSize()) {
            GlassBackground(wallpaperLayer = null)
            Scaffold(
                containerColor = Color.Transparent,
                topBar = {
                    GlassTopBar(
                        title = "Synthetica Preview",
                        subtitle = "3.0.0  •  PRATINJAU SAJA",
                        actions = { IosPill(text = "DEMO", color = IosPinkDark) },
                    )
                },
                bottomBar = {
                    PreviewDock(selected = tab, onSelected = { tab = it })
                },
            ) { innerPadding ->
                AnimatedContent(
                    targetState = tab,
                    modifier = Modifier.fillMaxSize().padding(innerPadding),
                    transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(180)) },
                    label = "preview-tab",
                ) { page ->
                    Column(
                        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                            .padding(horizontal = 16.dp, vertical = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        PreviewNotice()
                        when (page) {
                            0 -> PreviewHome(onTab = { tab = it }, onInstall = {
                                Toast.makeText(context, "Pratinjau saja — tidak memasang kernel", Toast.LENGTH_SHORT).show()
                            })
                            1 -> PreviewItems("Root apps", Icons.Rounded.AdminPanelSettings)
                            2 -> PreviewItems("Modul", Icons.Rounded.Layers)
                            else -> PreviewSettings(amoled = amoled, onAmoledChange = { amoled = it })
                        }
                        Spacer(Modifier.height(12.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun PreviewNotice() {
    Text(
        text = "PRATINJAU SAJA — bukan Manager root; data di bawah adalah contoh.",
        modifier = Modifier.fillMaxWidth().iosGlass(shape = MaterialTheme.shapes.medium, elevation = 2.dp)
            .padding(horizontal = 14.dp, vertical = 11.dp),
        color = MaterialTheme.colorScheme.onSurface,
        style = MaterialTheme.typography.bodySmall,
        fontWeight = FontWeight.Medium,
    )
}

@Composable
private fun PreviewHome(onTab: (Int) -> Unit, onInstall: () -> Unit) {
    IosHeroCard(
        eyebrow = "STATUS • CONTOH",
        title = "Synthetica Manager",
        statusPill = "DEMO",
        statusColor = IosPinkDark,
        modePill = "SIMULASI",
        kernelLine = "Bukan data kernel perangkat",
        metaLine = "Pratinjau tampilan • tidak mengelola akses root",
    )
    Text("AKSES CEPAT", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            IosTile(icon = Icons.Rounded.GridView, badgeColor = IosBlueDark, title = "Modul", subtitle = "Daftar contoh", modifier = Modifier.weight(1f), onClick = { onTab(2) })
            IosTile(icon = Icons.Rounded.AdminPanelSettings, badgeColor = IosGreenDark, title = "Root apps", subtitle = "Profil contoh", modifier = Modifier.weight(1f), onClick = { onTab(1) })
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            IosTile(icon = Icons.Rounded.SystemUpdateAlt, badgeColor = IosOrangeDark, title = "Pasang kernel", subtitle = "Tidak aktif di demo", modifier = Modifier.weight(1f), onClick = onInstall)
            IosTile(icon = Icons.Rounded.Tune, badgeColor = IosPurpleDark, title = "Setelan", subtitle = "Aksen & animasi", modifier = Modifier.weight(1f), onClick = { onTab(3) })
        }
    }
    IosGroup(title = "STATUS • CONTOH") {
        IosRow(icon = Icons.Rounded.Layers, badgeColor = IosCyanDark, title = "Kernel", value = "Simulasi")
        IosGroupDivider()
        IosRow(icon = Icons.Rounded.AdminPanelSettings, badgeColor = IosPinkDark, title = "Akses root", value = "Tidak tersedia")
    }
}

@Composable
private fun PreviewItems(title: String, icon: ImageVector) {
    IosGroup(title = "$title • CONTOH") {
        IosRow(icon = icon, badgeColor = IosCyanDark, title = "Contoh tampilan", subtitle = "Pratinjau ini tidak membaca atau mengubah $title pada perangkat.")
        IosGroupDivider()
        IosRow(icon = Icons.Rounded.AutoAwesome, badgeColor = IosPinkDark, title = "Panel neon", subtitle = "Warna, glow dan animasi adalah contoh UI.")
    }
}

@Composable
private fun PreviewSettings(amoled: Boolean, onAmoledChange: (Boolean) -> Unit) {
    val context = LocalContext.current
    IosGroup(title = "TAMPILAN NEON • PREVIEW") {
        IosSwitchRow(
            icon = Icons.Rounded.AutoAwesome,
            badgeColor = IosPinkDark,
            title = "Animasi neon",
            subtitle = "Glow dan garis bergerak mengikuti pengaturan animasi sistem",
            checked = NeonMotionState.value,
            onCheckedChange = { setNeonMotion(context, it) },
        )
        IosGroupDivider()
        IosSwitchRow(
            icon = Icons.Rounded.Contrast,
            badgeColor = IosPurpleDark,
            title = "Hitam AMOLED",
            subtitle = "Latar OLED hitam dalam pratinjau ini",
            checked = amoled,
            onCheckedChange = onAmoledChange,
        )
    }
    IosGroup(title = "AKSEN NEON • PREVIEW") {
        NeonAccentOptions.forEachIndexed { index, option ->
            if (index > 0) IosGroupDivider()
            val selected = NeonAccentState.value == option.id
            Row(
                modifier = Modifier.fillMaxWidth().selectable(
                    selected = selected, role = Role.RadioButton,
                    onClick = { setNeonAccent(context, option.id) },
                ).padding(horizontal = 15.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IosBadgeIcon(icon = Icons.Rounded.Palette, color = option.color)
                Spacer(Modifier.width(13.dp))
                Text(stringResource(option.label), modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
                RadioButton(selected = selected, onClick = null)
            }
        }
    }
}

@Composable
private fun PreviewDock(selected: Int, onSelected: (Int) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 18.dp, vertical = 12.dp)
            .iosGlass(shape = MaterialTheme.shapes.extraLarge, elevation = 12.dp)
            .padding(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        previewTabs.forEachIndexed { index, item ->
            val isSelected = selected == index
            Column(
                modifier = Modifier.weight(1f).height(56.dp).clip(MaterialTheme.shapes.medium)
                    .background(if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.16f) else Color.Transparent)
                    .selectable(selected = isSelected, role = Role.Tab, onClick = { onSelected(index) }),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                val color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                Icon(item.icon, contentDescription = null, tint = color, modifier = Modifier.size(22.dp))
                Spacer(Modifier.height(2.dp))
                Text(item.label, style = MaterialTheme.typography.labelSmall, color = color, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}
