package com.rifsxd.ksunext.ui.pixel

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.DeveloperBoard
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Terminal
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosBlueDark
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosGroup
import com.rifsxd.ksunext.ui.theme.IosGroupDivider
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.IosPurpleDark
import com.rifsxd.ksunext.ui.theme.IosRow
import com.rifsxd.ksunext.ui.theme.IosTeal
import com.rifsxd.ksunext.ui.theme.iosGlass
import java.util.Locale

/** These are observations, not attestation that a provider/hiding is active. */
data class ProviderCandidate40(val id: String, val name: String, val markedEnabled: Boolean)
data class Diagnostics40(
    val loading: Boolean = true,
    val rootAccessible: Boolean = false,
    val susfsReported: Boolean = false,
    val susfsVersion: String? = null,
    val susfsVariant: String? = null,
    val susfsFeatures: String? = null,
    val zygiskProcessFlag: Boolean? = null,
    // null means that module enumeration failed; an empty list means no known names.
    val providers: List<ProviderCandidate40>? = null,
    val kernelModeLabel: String? = null,
)

fun knownProvider40(id: String, name: String): Boolean {
    fun norm(s: String) = s.lowercase(Locale.ROOT).filter { it in 'a'..'z' || it in '0'..'9' }
    val idKey = norm(id)
    val nameKey = norm(name)
    return listOf("zygisknext", "rezygisk", "neozygisk").any { it in idKey || it in nameKey }
}

fun possibleProviderConflict40(providers: List<ProviderCandidate40>?): Boolean =
    providers != null && providers.count { it.markedEnabled } > 1

@Composable
fun PixelDiagnostics40Page(
    snapshot: Diagnostics40,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
    logBusy: Boolean = false,
    logResult: PixelActionResult40? = null,
    onRunDiagAction: (String) -> Unit = {},
) {
    val context = LocalContext.current
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val unavailable = stringResource(R.string.pixel40_unavailable)
    Scaffold(
        containerColor = Color.Transparent,
        topBar = { GlassTopBar(stringResource(R.string.pixel40_diagnostics_title), stringResource(R.string.pixel40_diagnostics_subtitle), onBack = onBack) },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 16.dp).padding(bottom = bottom + 16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            IosGroup(title = stringResource(R.string.manager60_universal_bridge_title)) {
                IosRow(
                    Icons.Rounded.DeveloperBoard,
                    IosGreenDark,
                    stringResource(R.string.manager60_universal_mode),
                    subtitle = snapshot.kernelModeLabel ?: stringResource(R.string.manager60_universal_mode_sub),
                )
                IosGroupDivider()
                IosRow(Icons.Rounded.Refresh, IosCyanDark, stringResource(R.string.pixel40_diagnostics_refresh),
                    enabled = !snapshot.loading, showChevron = true, onClick = onRefresh)
            }
            if (snapshot.loading) {
                Text(stringResource(R.string.pixel40_diagnostics_loading), style = MaterialTheme.typography.bodyMedium)
            } else if (!snapshot.rootAccessible) {
                Text(stringResource(R.string.pixel40_diagnostics_no_root), style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.iosGlass().padding(16.dp))
            } else {
                IosGroup(title = stringResource(R.string.manager60_log_viewer_group)) {
                    IosRow(Icons.Rounded.Terminal, IosCyanDark, stringResource(R.string.manager60_diag_dmesg),
                        subtitle = stringResource(R.string.manager60_diag_dmesg_sub),
                        enabled = !logBusy, showChevron = true,
                        onClick = { onRunDiagAction("diag_dmesg") })
                    IosGroupDivider()
                    IosRow(Icons.Rounded.BugReport, IosOrangeDark, stringResource(R.string.manager60_diag_pstore),
                        subtitle = stringResource(R.string.manager60_diag_pstore_sub),
                        enabled = !logBusy, showChevron = true,
                        onClick = { onRunDiagAction("diag_pstore") })
                    IosGroupDivider()
                    IosRow(Icons.Rounded.DeveloperBoard, IosPurpleDark, stringResource(R.string.manager60_diag_boot),
                        subtitle = stringResource(R.string.manager60_diag_boot_sub),
                        enabled = !logBusy, showChevron = true,
                        onClick = { onRunDiagAction("diag_boot") })
                    if (logResult != null && !logBusy) {
                        IosGroupDivider()
                        IosRow(
                            Icons.Rounded.ContentCopy,
                            IosBlueDark,
                            stringResource(R.string.manager60_diag_copy),
                            subtitle = stringResource(R.string.manager60_diag_copy_sub),
                            showChevron = true,
                            onClick = {
                                runCatching {
                                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                                    cm?.setPrimaryClip(ClipData.newPlainText("Synthetica Diagnostics", logResult.output))
                                }
                            },
                        )
                        Column(Modifier.fillMaxWidth().padding(16.dp)) {
                            SelectionContainer {
                                Text(
                                    logResult.output,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontFamily = FontFamily.Monospace,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
                IosGroup(title = stringResource(R.string.pixel40_susfs_title), footer = stringResource(R.string.pixel40_susfs_warning)) {
                    IosRow(Icons.Rounded.Security, IosTeal, stringResource(R.string.pixel40_susfs_support),
                        subtitle = if (snapshot.susfsReported) stringResource(R.string.pixel40_supported) else unavailable)
                    IosGroupDivider()
                    IosRow(Icons.Rounded.Info, IosCyanDark, stringResource(R.string.pixel40_susfs_version),
                        subtitle = listOfNotNull(snapshot.susfsVersion, snapshot.susfsVariant).joinToString(" / ").ifBlank { unavailable })
                    IosGroupDivider()
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.pixel40_susfs_features), style = MaterialTheme.typography.titleMedium)
                        SelectionContainer {
                            Text(snapshot.susfsFeatures ?: unavailable, style = MaterialTheme.typography.bodySmall,
                                fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                IosGroup(title = stringResource(R.string.pixel40_zygisk_title), footer = stringResource(R.string.pixel40_zygisk_warning)) {
                    IosRow(Icons.Rounded.Hub, IosCyanDark, stringResource(R.string.pixel40_zygisk_env),
                        subtitle = when (snapshot.zygiskProcessFlag) {
                            true -> stringResource(R.string.pixel40_zygisk_observed)
                            false -> stringResource(R.string.pixel40_zygisk_not_observed)
                            null -> unavailable
                        })
                    IosGroupDivider()
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.pixel40_zygisk_candidates), style = MaterialTheme.typography.titleMedium)
                        when {
                            snapshot.providers == null -> Text(unavailable, style = MaterialTheme.typography.bodyMedium)
                            snapshot.providers.isEmpty() -> Text(stringResource(R.string.pixel40_zygisk_none), style = MaterialTheme.typography.bodyMedium)
                            else -> snapshot.providers.forEach { item ->
                                val status = stringResource(if (item.markedEnabled) R.string.pixel40_zygisk_marked_enabled else R.string.pixel40_zygisk_marked_disabled)
                                Text("${item.name} (${item.id}) · $status", style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                        if (possibleProviderConflict40(snapshot.providers)) {
                            Text(stringResource(R.string.pixel40_zygisk_conflict), color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
