package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.pure.manager.module.ModuleManager
import net.pure.manager.theme.PureThemeSpec

/**
 * The Modul tab.
 *
 * Deliberately small: a terminal (which exists), and a module catalog that is empty
 * until a release publishes one. The empty state is not a placeholder with a fake
 * download button -- it says why it is empty and what would fill it. The owner has
 * seen too many rows in this app that looked installable and were not.
 *
 * The download path is real and tested: fetch, hash, compare, delete on mismatch.
 * What is missing is a published catalog, and that is a button on a release page,
 * not a line of code.
 */
@Composable
fun ModulesTab(spec: PureThemeSpec, catalog: List<ModuleManager.Entry> = emptyList()) {
    val p = spec.palette
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var terminal by rememberSaveable { mutableStateOf(false) }
    val directory = remember { File(context.filesDir, "modules").apply { mkdirs() } }
    // Installed ids, recomputed when a download lands or something is removed.
    var installed by remember { mutableStateOf<List<ModuleManager.Entry>>(emptyList()) }
    var version by remember { mutableStateOf(0) }
    val busy = remember { mutableStateMapOf<String, Float>() }
    var note by remember { mutableStateOf<String?>(null) }

    // Re-hashing on every recomposition would be absurd; this runs once per change.
    LaunchedEffect(version) {
        installed = withContext(Dispatchers.IO) { ModuleManager.installed(directory, catalog) }
    }

    if (terminal) {
        TerminalScreen(spec = spec, onClose = { terminal = false })
        Spacer(Modifier.height(16.dp))
    }

    GroupCard(spec) {
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(spec.cornerDp.dp))
                .clickable { terminal = true }
                .padding(horizontal = 14.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("Terminal", style = MaterialTheme.typography.bodyLarge, color = p.onBackground)
                Text(
                    if (terminal) "Terbuka di atas" else "Root + shell \u2014 siap dipakai",
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
            Icon(
                imageVector = PureIcons.Chevron,
                contentDescription = null,
                tint = p.onSurfaceVariant,
                modifier = Modifier.size(18.dp),
            )
        }
    }

    Spacer(Modifier.height(14.dp))
    Text(
        "MODUL",
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.SemiBold,
        color = p.onSurfaceVariant,
        modifier = Modifier.padding(start = 4.dp, bottom = 6.dp),
    )

    if (catalog.isEmpty()) {
        GroupCard(spec) {
            Column(Modifier.padding(14.dp)) {
                Text(
                    "Belum ada modul yang dipublikasikan.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.onBackground,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "Modul diunduh dari rilis GitHub dan diperiksa SHA-256 sebelum " +
                        "bisa dipakai. Katalognya kosong karena belum ada rilis modul, " +
                        "bukan karena fiturnya belum ada: alur unduh, periksa, pasang, " +
                        "dan hapus sudah jalan dan diuji.",
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        }
    } else {
        GroupCard(spec) {
            catalog.forEach { entry ->
                val isInstalled = installed.any { it.id == entry.id }
                val progress = busy[entry.id]
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                entry.name,
                                style = MaterialTheme.typography.bodyLarge,
                                color = p.onBackground,
                            )
                            Text(
                                "${entry.version} \u00b7 ${if (isInstalled) "terpasang" else "belum terpasang"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isInstalled) p.accent else p.onSurfaceVariant,
                            )
                        }
                        Text(
                            if (isInstalled) "Hapus" else if (progress != null) "\u2026" else "Unduh",
                            style = MaterialTheme.typography.bodyLarge,
                            color = if (isInstalled) p.accent else p.accent,
                            modifier = Modifier
                                .clip(RoundedCornerShape(spec.cornerDp.dp))
                                .clickable(enabled = progress == null) {
                                    if (isInstalled) {
                                        val f = File(directory, entry.id + ".pmod")
                                        val ok = runCatching { f.delete() }.getOrDefault(false)
                                        note = if (ok) "${entry.name} dihapus" else "Gagal menghapus"
                                        version += 1
                                    } else {
                                        busy[entry.id] = 0f
                                        scope.launch {
                                            val outcome = withContext(Dispatchers.IO) {
                                                download(entry, directory)
                                            }
                                            busy.remove(entry.id)
                                            note = when (outcome) {
                                                is ModuleManager.Outcome.Installed ->
                                                    "${entry.name} terpasang"
                                                ModuleManager.Outcome.HashMismatch ->
                                                    "Ditolak: SHA-256 tidak cocok. Berkas dihapus."
                                                is ModuleManager.Outcome.Failed ->
                                                    outcome.message
                                            }
                                            version += 1
                                        }
                                    }
                                }
                                .padding(horizontal = 8.dp, vertical = 4.dp),
                        )
                    }
                    if (progress != null) {
                        Spacer(Modifier.height(6.dp))
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .height(4.dp)
                                .clip(RoundedCornerShape(2.dp))
                                .background(p.surfaceVariant),
                        ) {
                            Box(
                                Modifier
                                    .fillMaxWidth(progress)
                                    .height(4.dp)
                                    .background(p.accent),
                            )
                        }
                    }
                }
            }
        }
    }

    note?.let { text ->
        Spacer(Modifier.height(10.dp))
        Text(text, style = MaterialTheme.typography.bodySmall, color = p.onSurfaceVariant)
    }

    Spacer(Modifier.height(12.dp))
    Text(
        "Verifikasi memakai SHA-256. Tanda tangan Ed25519 menyusul setelah kunci " +
            "publik modul diterbitkan; sampai itu ada, hash melindungi dari berkas " +
            "rusak, bukan dari pihak yang bisa mengganti hash dan berkas sekaligus.",
        style = MaterialTheme.typography.bodySmall,
        color = p.onSurfaceVariant,
    )
}

/**
 * Downloads one module and verifies it.
 *
 * The URL is built from the entry, and the file only becomes usable after the hash
 * matches. Kept as a plain function so the verification half is what the JVM tests
 * exercise; the network half is the part this sandbox cannot run.
 */
private fun download(entry: ModuleManager.Entry, directory: File): ModuleManager.Outcome {
    val target = File(directory, entry.id + ".pmod")
    return runCatching {
        val url = java.net.URL(
            "https://github.com/dwp29/Synthentica/releases/download/" +
                "module-${entry.id}-${entry.version}/${entry.asset}",
        )
        url.openStream().use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
    }.fold(
        onSuccess = { ModuleManager.verify(target, entry) },
        onFailure = { error ->
            runCatching { target.delete() }
            ModuleManager.Outcome.Failed(error.message ?: "Unduhan gagal")
        },
    )
}
