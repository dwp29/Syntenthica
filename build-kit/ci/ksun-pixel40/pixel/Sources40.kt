package com.rifsxd.ksunext.ui.pixel

import androidx.annotation.StringRes
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
import androidx.compose.material.icons.rounded.OpenInNew
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.iosGlass

/** A hand-reviewed set of external links, not another JSON feed or installer. */
data class PixelSource40(val name: String, val url: String, @StringRes val description: Int)
data class PixelSourceGroup40(@StringRes val title: Int, val links: List<PixelSource40>)

// Release pages and channels are linked by the respective project's own repo.
// Entries are untrusted third-party sources; this list does not assert compatibility.
val PixelSources40 = listOf(
    PixelSourceGroup40(R.string.pixel40_sources_directories, listOf(
        PixelSource40("KernelSU Modules", "https://modules.kernelsu.org/en/", R.string.pixel40_src_ksu_dir),
        PixelSource40("KernelSU Next catalogue", "https://github.com/KernelSU-Next/KernelSU-Next-Modules-Repo", R.string.pixel40_src_ksun_dir),
        PixelSource40("Magisk Modules Alt Repo", "https://github.com/Magisk-Modules-Alt-Repo", R.string.pixel40_src_alt_dir),
        PixelSource40("LSPosed Module Repository", "https://modules.lsposed.org/", R.string.pixel40_src_xposed_dir),
        PixelSource40("Awesome Android Root", "https://github.com/awesome-android-root/awesome-android-root", R.string.pixel40_src_awesome),
    )),
    PixelSourceGroup40(R.string.pixel40_sources_providers, listOf(
        PixelSource40("Zygisk Next", "https://github.com/Dr-TSNG/ZygiskNext/releases", R.string.pixel40_src_provider),
        PixelSource40("ReZygisk", "https://github.com/PerformanC/ReZygisk/releases", R.string.pixel40_src_provider),
        PixelSource40("NeoZygisk", "https://github.com/JingMatrix/NeoZygisk/releases", R.string.pixel40_src_provider),
    )),
    PixelSourceGroup40(R.string.pixel40_sources_frameworks, listOf(
        PixelSource40("LSPosed", "https://github.com/LSPosed/LSPosed/releases", R.string.pixel40_src_lsposed),
        PixelSource40("Vector (JingMatrix fork)", "https://github.com/JingMatrix/Vector/releases", R.string.pixel40_src_vector),
    )),
    PixelSourceGroup40(R.string.pixel40_sources_modules, listOf(
        PixelSource40("bindhosts", "https://github.com/bindhosts/bindhosts/releases", R.string.pixel40_src_hosts),
        PixelSource40("Systemless Hosts", "https://github.com/symbuzzer/systemless-hosts-KernelSU-module/releases", R.string.pixel40_src_hosts),
        PixelSource40("AdGuard Home for Root", "https://github.com/twoone-3/AdGuardHomeForRoot/releases", R.string.pixel40_src_dns),
        PixelSource40("PlayIntegrityFork", "https://github.com/osm0sis/PlayIntegrityFork/releases", R.string.pixel40_src_integrity),
        PixelSource40("PlayIntegrityFix (KOWX712)", "https://github.com/KOWX712/PlayIntegrityFix/releases", R.string.pixel40_src_integrity),
        PixelSource40("SuSFS module (sidex15)", "https://github.com/sidex15/susfs4ksu-module/releases", R.string.pixel40_src_susfs),
        PixelSource40("Mountify", "https://github.com/backslashxx/mountify/releases", R.string.pixel40_src_mountify),
        PixelSource40("Advanced Charging Controller", "https://github.com/VR-25/acc/releases", R.string.pixel40_src_acc),
        PixelSource40("Universal GMS Doze", "https://github.com/gloeyisk/universal-gms-doze/releases", R.string.pixel40_src_doze),
    )),
    PixelSourceGroup40(R.string.pixel40_sources_xposed, listOf(
        PixelSource40("Hide My Applist", "https://github.com/Dr-TSNG/Hide-My-Applist/releases", R.string.pixel40_src_xposed_apk),
        PixelSource40("HyperCeiler", "https://github.com/ReChronoRain/HyperCeiler/releases", R.string.pixel40_src_hyper),
        PixelSource40("DisableFlagSecure", "https://github.com/LSPosed/DisableFlagSecure/releases", R.string.pixel40_src_flag),
    )),
    PixelSourceGroup40(R.string.pixel40_sources_channels, listOf(
        PixelSource40("LSPosed · Telegram", "https://t.me/LSPosed", R.string.pixel40_src_channel),
        PixelSource40("ReZygisk · Telegram", "https://t.me/rezygisk", R.string.pixel40_src_channel),
    )),
)

/** UI is shared with an isolated preview; onOpen is the only external action. */
@Composable
fun PixelSources40Page(onBack: () -> Unit, onOpen: (String) -> Unit) {
    var selected by remember { mutableStateOf<PixelSource40?>(null) }
    selected?.let { source ->
        AlertDialog(
            onDismissRequest = { selected = null },
            title = { Text(stringResource(R.string.pixel40_sources_open_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(source.name, style = MaterialTheme.typography.titleMedium)
                    Text(source.url, style = MaterialTheme.typography.bodySmall)
                    Text(stringResource(source.description), style = MaterialTheme.typography.bodyMedium)
                    Text(stringResource(R.string.pixel40_sources_open_warning), style = MaterialTheme.typography.bodyMedium)
                }
            },
            confirmButton = {
                TextButton(onClick = { selected = null; onOpen(source.url) }) {
                    Text(stringResource(R.string.pixel40_sources_open))
                }
            },
            dismissButton = {
                TextButton(onClick = { selected = null }) { Text(stringResource(R.string.pixel40_action_cancel)) }
            },
        )
    }
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Scaffold(
        containerColor = Color.Transparent,
        topBar = { GlassTopBar(stringResource(R.string.pixel40_sources_title), stringResource(R.string.pixel40_sources_subtitle), onBack = onBack) },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp).padding(bottom = bottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Text(
                stringResource(R.string.pixel40_sources_warning),
                modifier = Modifier.iosGlass(shape = MaterialTheme.shapes.medium).padding(16.dp),
                color = MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.bodyMedium,
            )
            PixelSources40.forEach { group ->
                IosGroup(title = stringResource(group.title)) {
                    group.links.forEachIndexed { index, source ->
                        if (index > 0) IosGroupDivider()
                        IosRow(
                            icon = Icons.Rounded.OpenInNew, badgeColor = IosCyanDark,
                            title = source.name, subtitle = stringResource(source.description),
                            showChevron = true, onClick = { selected = source },
                        )
                    }
                }
            }
        }
    }
}
