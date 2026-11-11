package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.pure.manager.fs.AccessMode
import net.pure.manager.fs.FileEntry
import net.pure.manager.fs.FileOps
import net.pure.manager.fs.SortKey
import net.pure.manager.fs.SortOrder
import net.pure.manager.fs.Storage
import net.pure.manager.fs.comparatorFor
import net.pure.manager.fs.formatDate
import net.pure.manager.fs.formatSize
import net.pure.manager.theme.LocalPureSpec
import net.pure.manager.theme.PureThemeSpec
import java.io.File

/**
 * The file browser.
 *
 * Reads the real file system now, or says plainly why it cannot. Every list is
 * loaded off the main thread and every failure is a message rather than a crash:
 * this screen touches storage the app does not own, which is where a file manager
 * usually dies.
 *
 * Deliberately absent for now: multi-select, drag and drop, thumbnails, archive
 * extraction. They arrive with progress reporting in stage 3, where a long copy
 * can be cancelled instead of blocking the screen.
 */
@Composable
fun BrowserScreen(spec: PureThemeSpec) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val p = spec.palette

    var mode by remember { mutableStateOf(Storage.mode(context)) }
    var entries by remember { mutableStateOf<List<FileEntry>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var locationLabel by rememberSaveable { mutableStateOf("Internal") }
    var path by rememberSaveable { mutableStateOf("") }
    var sortKeyName by rememberSaveable { mutableStateOf(SortKey.NAME.name) }
    var sortDescending by rememberSaveable { mutableStateOf(false) }
    var grid by rememberSaveable { mutableStateOf(spec.defaultGrid) }
    var showHidden by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    var actionTarget by remember { mutableStateOf<FileEntry?>(null) }
    var deleteTarget by remember { mutableStateOf<FileEntry?>(null) }
    var prompt by remember { mutableStateOf<Prompt?>(null) }
    var toast by remember { mutableStateOf<String?>(null) }
    // Bumped after every write so the LaunchedEffect re-reads the folder. Keying
    // on the path alone meant a rename or delete left a stale list until the user
    // navigated away and back -- which reads as data loss.
    var refreshKey by remember { mutableStateOf(0) }

    // Re-read whenever the folder, the ordering or the hidden-file setting change.
    LaunchedEffect(path, sortKeyName, sortDescending, showHidden, mode, refreshKey) {
        if (mode == AccessMode.NONE) {
            entries = emptyList()
            return@LaunchedEffect
        }
        val folder = path.ifEmpty {
            Storage.locations(context).firstOrNull()?.path.orEmpty()
        }
        if (folder.isEmpty()) return@LaunchedEffect
        loading = true
        error = null
        val result = withContext(Dispatchers.IO) { Storage.list(folder, showHidden) }
        entries = result
            .map { it.sortedWith(comparatorFor(SortOrder(SortKey.valueOf(sortKeyName), sortDescending))) }
            .getOrElse {
                error = it.message ?: "Folder tidak bisa dibaca"
                emptyList()
            }
        loading = false
        if (path.isEmpty()) path = folder
    }

    fun reload() {
        refreshKey++
    }

    val visible = remember(entries, query) {
        if (query.isBlank()) entries
        else entries.filter { Storage.searchKey(it.name).contains(Storage.searchKey(query)) }
    }

    // Defined before the tree so the tap handler closes over the same state.
    val openEntry: (FileEntry) -> Unit = { e ->
        if (e.isDirectory) {
            path = e.path
            locationLabel = Storage.displayName(e.path)
            query = ""
        } else {
            toast = "Pembuka berkas menyusul (tahap 5)"
        }
    }

    Column {
        when (mode) {
            AccessMode.NONE -> PermissionCard(
                spec = spec,
                onAllFiles = { context.startActivity(Storage.allFilesIntent(context)) },
                onPickFolder = {
                    // Handled by the caller's activity result launcher in a later
                    // slice; the button is here so the screen is honest about the
                    // two routes rather than showing one.
                    toast = "Pemilih folder SAF menyusul di irisan berikutnya."
                },
            )
            else -> {
                SearchField(spec, query, onValueChange = { query = it })
                Spacer(Modifier.height(10.dp))
                Toolbar(
                    spec = spec,
                    label = locationLabel,
                    sortKey = SortKey.valueOf(sortKeyName),
                    descending = sortDescending,
                    grid = grid,
                    showHidden = showHidden,
                    onUp = {
                        val parent = Storage.parentOf(path)
                        if (parent != null) {
                            path = parent
                            locationLabel = Storage.displayName(parent)
                            query = ""
                        }
                    },
                    canGoUp = Storage.parentOf(path) != null,
                    onSort = {
                        // One button cycles Name -> Size -> Date -> Type and then
                        // flips direction. A dropdown for four options costs more
                        // taps than a cycle.
                        when (SortKey.valueOf(sortKeyName)) {
                            SortKey.NAME -> sortKeyName = SortKey.SIZE.name
                            SortKey.SIZE -> sortKeyName = SortKey.DATE.name
                            SortKey.DATE -> sortKeyName = SortKey.TYPE.name
                            SortKey.TYPE -> {
                                sortKeyName = SortKey.NAME.name
                                sortDescending = !sortDescending
                            }
                        }
                    },
                    onToggleGrid = { grid = !grid },
                    onToggleHidden = { showHidden = !showHidden },
                    onHome = {
                        val first = Storage.locations(context).firstOrNull()
                        if (first != null) {
                            path = first.path
                            locationLabel = first.label
                            query = ""
                        }
                    },
                )

                Spacer(Modifier.height(10.dp))

                when {
                    loading -> Box(
                        Modifier.fillMaxWidth().padding(vertical = 40.dp),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator(color = p.accent) }

                    error != null -> MessageCard(spec, "Tidak bisa dibaca", error!!)

                    visible.isEmpty() -> MessageCard(
                        spec = spec,
                        title = if (query.isBlank()) "Folder kosong" else "Tidak ada yang cocok",
                        body = if (query.isBlank())
                            "Tidak ada berkas di ${Storage.displayName(path)}."
                        else
                            "Tidak ada nama yang mengandung \u201c$query\u201d.",
                    )

                    else -> {
                        if (grid) {
                            GroupCard(spec) {
                                Column(Modifier.padding(horizontal = 6.dp, vertical = 8.dp)) {
                                    visible.chunked(3).forEach { row ->
                                        Row(Modifier.fillMaxWidth()) {
                                            row.forEach { e ->
                                                Box(Modifier.weight(1f)) {
                                                    GridCell(
                                                        spec = spec,
                                                        title = e.name,
                                                        subtitle = if (e.isDirectory)
                                                            "${e.childCount} item"
                                                        else formatSize(e.sizeBytes, false),
                                                        isFolder = e.isDirectory,
                                                        glyph = glyphFor(e),
                                                        onClick = { openEntry(e) },
                                                    )
                                                }
                                            }
                                            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                                        }
                                    }
                                }
                            }
                        } else {
                            GroupCard(spec) {
                                visible.forEach { e ->
                                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                        Box(Modifier.weight(1f)) {
                                            ListRow(
                                                spec = spec,
                                                title = e.name,
                                                subtitle = subtitleFor(e),
                                                isFolder = e.isDirectory,
                                                glyph = glyphFor(e),
                                                showChevron = true,
                                                onClick = { openEntry(e) },
                                            )
                                        }
                                        Box(
                                            Modifier
                                                .size(36.dp)
                                                .clip(CircleShape)
                                                .clickable { actionTarget = e }
                                                .padding(8.dp),
                                            contentAlignment = Alignment.Center,
                                        ) {
                                            Text(
                                                "\u22EF",
                                                style = MaterialTheme.typography.titleMedium,
                                                color = p.onSurfaceVariant,
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(Modifier.height(12.dp))
                        Text(
                            "${visible.count { it.isDirectory }} folder \u00b7 " +
                                "${visible.count { !it.isDirectory }} berkas" +
                                if (showHidden) " \u00b7 termasuk tersembunyi" else "",
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    }
                }

                Spacer(Modifier.height(80.dp))

                if (spec.floatingAction) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        Box(
                            Modifier
                                .size(56.dp)
                                .clip(CircleShape)
                                .background(p.accent)
                                .clickable { prompt = Prompt.NEW_FOLDER },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                "+",
                                style = MaterialTheme.typography.headlineMedium,
                                color = p.onAccent,
                            )
                        }
                    }
                }

                // Long menus first, then confirmations: deleting something is the
                // only action here that cannot be undone from inside the app.
                actionTarget?.let { target ->
                    ActionSheet(
                        spec = spec,
                        target = target,
                        onDismiss = { actionTarget = null },
                        onRename = { actionTarget = null; prompt = Prompt.Rename(target) },
                        onCopy = { actionTarget = null; prompt = Prompt.CopyHere(target) },
                        onMove = { actionTarget = null; prompt = Prompt.MoveHere(target) },
                        onDelete = { actionTarget = null; deleteTarget = target },
                        onInfo = { actionTarget = null; prompt = Prompt.Info(target) },
                    )
                }

                deleteTarget?.let { target ->
                    val (bytes, files) = remember(target) { FileOps.measure(target) }
                    ConfirmDialog(
                        spec = spec,
                        title = "Hapus ${target.name}?",
                        body = if (target.isDirectory)
                            "Folder beserta $files berkas di dalamnya (${formatSize(bytes, false)}). " +
                                "Tidak ada tong sampah: ini langsung terhapus."
                        else
                            "${formatSize(target.sizeBytes, false)}. Tidak ada tong sampah: " +
                                "ini langsung terhapus.",
                        confirm = "Hapus",
                        onDismiss = { deleteTarget = null },
                        onConfirm = {
                            val t = target
                            deleteTarget = null
                            scope.launch {
                                val r = withContext(Dispatchers.IO) { FileOps.delete(t) }
                                toast = r.fold({ "Terhapus" }, { it.message ?: "Gagal menghapus" })
                                reload()
                            }
                        },
                    )
                }

                prompt?.let { pr ->
                    NamePrompt(
                        spec = spec,
                        prompt = pr,
                        onDismiss = { prompt = null },
                        onSubmit = { value ->
                            prompt = null
                            scope.launch {
                                val parent = path
                                val result = withContext(Dispatchers.IO) {
                                    when (pr) {
                                        Prompt.NEW_FOLDER -> FileOps.createFolder(parent, value)
                                        is Prompt.Rename -> FileOps.rename(pr.entry, value)
                                        is Prompt.CopyHere -> FileOps.copy(pr.entry.path, parent)
                                        is Prompt.MoveHere -> FileOps.move(pr.entry.path, parent)
                                        is Prompt.Info -> Result.success(File(parent))
                                    }
                                }
                                toast = result.fold(
                                    { "Selesai" },
                                    { it.message ?: "Gagal" },
                                )
                                reload()
                            }
                        },
                    )
                }

                toast?.let { message ->
                    Toast(spec, message) { toast = null }
                }
            }
        }
    }
}

private fun glyphFor(e: FileEntry): String = when {
    e.isDirectory -> ""
    e.extension in setOf("png", "jpg", "jpeg", "webp", "gif") -> "\u25A3"
    e.extension in setOf("mp3", "m4a", "wav", "ogg", "flac") -> "\u266A"
    e.extension in setOf("mp4", "mkv", "avi", "webm") -> "\u25B6"
    e.extension in setOf("zip", "rar", "7z", "tar", "gz") -> "\u25A4"
    e.extension == "apk" -> "\u25C8"
    e.extension in setOf("pdf") -> "\u25A4"
    else -> "\u25A7"
}

private fun subtitleFor(e: FileEntry): String =
    if (e.isDirectory) "${e.childCount} item \u00b7 ${formatDate(e.lastModified)}"
    else "${formatSize(e.sizeBytes, false)} \u00b7 ${formatDate(e.lastModified)}"

/** What the prompt dialog is for. One dialog, five jobs. */
private sealed interface Prompt {
    data object NEW_FOLDER : Prompt
    data class Rename(val entry: FileEntry) : Prompt
    data class CopyHere(val entry: FileEntry) : Prompt
    data class MoveHere(val entry: FileEntry) : Prompt
    data class Info(val entry: FileEntry) : Prompt
}

@Composable
private fun Toolbar(
    spec: PureThemeSpec,
    label: String,
    sortKey: SortKey,
    descending: Boolean,
    grid: Boolean,
    showHidden: Boolean,
    canGoUp: Boolean,
    onUp: () -> Unit,
    onSort: () -> Unit,
    onToggleGrid: () -> Unit,
    onToggleHidden: () -> Unit,
    onHome: () -> Unit,
) {
    val p = spec.palette
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (canGoUp) {
            ToolButton("\u2190", false, onUp)
            Spacer(Modifier.size(6.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(
                label,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                color = p.onBackground,
                maxLines = 1,
            )
            Text(
                when (sortKey) {
                    SortKey.NAME -> "Nama"
                    SortKey.SIZE -> "Ukuran"
                    SortKey.DATE -> "Tanggal"
                    SortKey.TYPE -> "Jenis"
                } + if (descending) " \u25BE" else " \u25B4",
                style = MaterialTheme.typography.bodySmall,
                color = p.accent,
                modifier = Modifier
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable(onClick = onSort)
                    .padding(vertical = 2.dp),
            )
        }
        ToolButton(if (showHidden) "\u25C9" else "\u25CB", showHidden, onToggleHidden)
        Spacer(Modifier.size(6.dp))
        ToolButton(if (grid) "\u2637" else "\u2263", true, onToggleGrid)
        Spacer(Modifier.size(6.dp))
        ToolButton("\u2302", false, onHome)
    }
}

@Composable
private fun PermissionCard(
    spec: PureThemeSpec,
    onAllFiles: () -> Unit,
    onPickFolder: () -> Unit,
) {
    val p = spec.palette
    GroupCard(spec) {
        Column(Modifier.padding(16.dp)) {
            Text(
                "Butuh izin berkas",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = p.onBackground,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                "Aplikasi ini pengelola berkas, jadi ia perlu membaca isi penyimpanan. " +
                    "Ada dua cara, dan keduanya bekerja:",
                style = MaterialTheme.typography.bodySmall,
                color = p.onSurfaceVariant,
            )
            Spacer(Modifier.height(14.dp))
            PrimaryButton(spec, "Beri izin \u201cSemua berkas\u201d", onAllFiles)
            Spacer(Modifier.height(8.dp))
            Text(
                "Membuka Setelan Android. Cari Pure Manager di daftar, lalu nyalakan " +
                    "\u201cIzinkan akses ke semua berkas\u201d. Ini yang membuat aplikasi bisa " +
                    "mengubah berkas, bukan sekadar melihat.",
                style = MaterialTheme.typography.bodySmall,
                color = p.onSurfaceVariant,
            )
            Spacer(Modifier.height(14.dp))
            SecondaryButton(spec, "Pilih satu folder saja", onPickFolder)
            Spacer(Modifier.height(8.dp))
            Text(
                "Tanpa izin khusus. Anda memilih folder mana yang boleh dibuka, dan " +
                    "aplikasi tidak bisa menyentuh yang lain.",
                style = MaterialTheme.typography.bodySmall,
                color = p.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PrimaryButton(spec: PureThemeSpec, label: String, onClick: () -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp * 0.8f).dp))
            .background(spec.palette.accent)
            .clickable(onClick = onClick)
            .padding(vertical = 13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            color = spec.palette.onAccent,
        )
    }
}

@Composable
private fun SecondaryButton(spec: PureThemeSpec, label: String, onClick: () -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp * 0.8f).dp))
            .border(1.dp, spec.palette.accent, RoundedCornerShape((spec.cornerDp * 0.8f).dp))
            .clickable(onClick = onClick)
            .padding(vertical = 13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyLarge,
            color = spec.palette.accent,
        )
    }
}

@Composable
private fun MessageCard(spec: PureThemeSpec, title: String, body: String) {
    val p = spec.palette
    GroupCard(spec) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.bodyLarge, color = p.onBackground)
            Spacer(Modifier.height(4.dp))
            Text(body, style = MaterialTheme.typography.bodySmall, color = p.onSurfaceVariant)
        }
    }
}

@Composable
private fun Toast(spec: PureThemeSpec, message: String, onDismiss: () -> Unit) {
    val p = spec.palette
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((spec.cornerDp * 0.8f).dp))
            .background(p.surfaceVariant)
            .border(0.75.dp, p.separator, RoundedCornerShape((spec.cornerDp * 0.8f).dp))
            .clickable(onClick = onDismiss)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            message,
            style = MaterialTheme.typography.bodySmall,
            color = p.onBackground,
            modifier = Modifier.weight(1f),
        )
        Text("\u00D7", style = MaterialTheme.typography.titleMedium, color = p.onSurfaceVariant)
    }
}

@Composable
private fun ActionSheet(
    spec: PureThemeSpec,
    target: FileEntry,
    onDismiss: () -> Unit,
    onRename: () -> Unit,
    onCopy: () -> Unit,
    onMove: () -> Unit,
    onDelete: () -> Unit,
    onInfo: () -> Unit,
) {
    val p = spec.palette
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text(target.name, style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                ActionRow("Ganti nama", onRename)
                ActionRow("Salin ke folder ini", onCopy)
                ActionRow("Pindahkan ke folder ini", onMove)
                ActionRow("Info", onInfo)
                ActionRow("Hapus", onDelete, danger = true)
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Tutup", color = p.accent) }
        },
    )
}

@Composable
private fun ActionRow(label: String, onClick: () -> Unit, danger: Boolean = false) {
    val p = LocalPureSpec.current.palette
    Text(
        label,
        style = MaterialTheme.typography.bodyLarge,
        color = if (danger) Color(0xFFEF4444) else p.onBackground,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 11.dp),
    )
}

@Composable
private fun ConfirmDialog(
    spec: PureThemeSpec,
    title: String,
    body: String,
    confirm: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    val p = spec.palette
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text(title, style = MaterialTheme.typography.titleMedium) },
        text = { Text(body, style = MaterialTheme.typography.bodySmall) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(confirm, color = Color(0xFFEF4444), fontWeight = FontWeight.Medium)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Batal", color = p.accent) }
        },
    )
}

@Composable
private fun NamePrompt(
    spec: PureThemeSpec,
    prompt: Prompt,
    onDismiss: () -> Unit,
    onSubmit: (String) -> Unit,
) {
    val p = spec.palette
    val initial = when (prompt) {
        Prompt.NEW_FOLDER -> ""
        is Prompt.Rename -> prompt.entry.name
        is Prompt.CopyHere -> prompt.entry.name
        is Prompt.MoveHere -> prompt.entry.name
        is Prompt.Info -> prompt.entry.name
    }
    var value by remember { mutableStateOf(initial) }
    val isInfo = prompt is Prompt.Info
    val isDestructive = prompt is Prompt.MoveHere

    val infoText = if (prompt is Prompt.Info) {
        val e = prompt.entry
        buildString {
            appendLine("Lokasi: ${e.path}")
            appendLine("Jenis: ${if (e.isDirectory) "Folder" else e.extension.uppercase().ifEmpty { "Berkas" }}")
            appendLine("Ukuran: ${if (e.isDirectory) "${e.childCount} item" else formatSize(e.sizeBytes, false)}")
            appendLine("Diubah: ${formatDate(e.lastModified)}")
            append("Terbaca: ${if (e.canRead) "ya" else "tidak"}")
        }
    } else null

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = {
            Text(
                when (prompt) {
                    Prompt.NEW_FOLDER -> "Folder baru"
                    is Prompt.Rename -> "Ganti nama"
                    is Prompt.CopyHere -> "Salin berkas"
                    is Prompt.MoveHere -> "Pindahkan berkas"
                    is Prompt.Info -> "Info"
                },
                style = MaterialTheme.typography.titleMedium,
            )
        },
        text = {
            Column {
                if (isInfo) {
                    Text(infoText.orEmpty(), style = MaterialTheme.typography.bodySmall)
                } else {
                    OutlinedTextField(
                        value = value,
                        onValueChange = { value = it },
                        singleLine = true,
                        label = { Text("Nama") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (prompt is Prompt.CopyHere || prompt is Prompt.MoveHere) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Akan ${if (isDestructive) "dipindahkan" else "disalin"} ke " +
                                "folder yang sedang dibuka. Nama yang sudah ada tidak " +
                                "ditimpa: berkas baru mendapat akhiran (1).",
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    }
                }
            }
        },
        confirmButton = {
            if (!isInfo) {
                TextButton(onClick = { onSubmit(value) }, enabled = value.isNotBlank()) {
                    Text(
                        if (prompt is Prompt.Rename) "Ganti" else "Buat",
                        color = p.accent,
                    )
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(if (isInfo) "Tutup" else "Batal", color = p.accent)
            }
        },
    )
}
