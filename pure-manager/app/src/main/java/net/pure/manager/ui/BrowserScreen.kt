package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
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
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.pure.manager.fs.AccessMode
import net.pure.manager.fs.Alphabet
import net.pure.manager.fs.Archive
import net.pure.manager.fs.CopyEngine
import net.pure.manager.fs.FileEntry
import net.pure.manager.fs.FileOps
import net.pure.manager.fs.SortKey
import net.pure.manager.fs.SortOrder
import net.pure.manager.fs.Storage
import net.pure.manager.fs.Support
import net.pure.manager.fs.Search
import net.pure.manager.fs.Usage
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
 * Deliberately absent for now: drag and drop, thumbnails, archive extraction. They
 * arrive with progress reporting in stage 3, where a long copy can be cancelled
 * instead of blocking the screen.
 */
@Composable
fun BrowserScreen(
    spec: PureThemeSpec,
    selectionMode: Boolean = false,
    onSelectionModeChange: (Boolean) -> Unit = { _ -> },
    onSelectedCount: (Int) -> Unit = { _ -> },
) {
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
    // What "Salin"/"Pindahkan" put on the clipboard. Shared between the long-press
    // menu and multi-select because they are the same operation.
    var clipboard by remember { mutableStateOf<Clipboard?>(null) }
    var selected by remember { mutableStateOf<Set<String>>(emptySet()) }
    var picker by remember { mutableStateOf<DestinationPicker?>(null) }
    var bulkDelete by remember { mutableStateOf(false) }
    // The "Lokasi" sheet: internal storage, the SD card, and the folders the
    // user granted. Without it, a folder added through SAF was openable once and
    // then lost after the first navigation away from it.
    var showPlaces by remember { mutableStateOf(false) }
    // Root-only places are opt-in. Listing /system to someone who cannot read it
    // is a row that fails when tapped; the toggle says why before it is used.
    var showSystemPlaces by rememberSaveable { mutableStateOf(false) }
    // The copy job that is currently running, and its latest numbers. Two things:
    // a progress value for the dialog, and a cancellation flag the engine polls
    // between chunks. Without the second, "Batal" would be decoration.
    var job by remember { mutableStateOf<CopyEngine.Progress?>(null) }
    // Storage analysis. Computed on demand from the folder that is open, because
    // scanning on every navigation would make browsing slow to answer a question
    // nobody has asked yet.
    var usage by remember { mutableStateOf<List<Usage.Tally>?>(null) }
    var usageBusy by remember { mutableStateOf(false) }
    // The archive being looked into, and whether an extract is running. Extract uses
    // the same cancellation flag as copy: one job at a time is easier to explain
    // than a queue the user cannot see.
    var archiveView by remember { mutableStateOf<Pair<FileEntry, List<Archive.Entry>>?>(null) }
    // Device-wide search. Opened from the magnifier in the search field, not from
    // the field itself: typing stays a filter of the folder you are looking at,
    // which is what the field does in Files too.
    var searchDevice by remember { mutableStateOf(false) }
    // A document this app can render itself. Everything else still goes to the
    // system, which is the right default; these three formats have no viewer on a
    // clean Android phone.
    var previewing by remember { mutableStateOf<FileEntry?>(null) }
    // A text file being edited. Separate from `previewing` because the two screens
    // have different consequences: leaving a preview loses nothing, while leaving an
    // edit can lose work, so the editor refuses a silent close.
    var editing by remember { mutableStateOf<FileEntry?>(null) }
    // The letter the A-Z strip is filtered to, or null for everything. The strip
    // filters rather than scroll-jumps: this list scrolls inside the shell's own
    // scroll state, which this screen does not own, and a strip that cannot move
    // the list would be decoration.
    var letterFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var deviceQuery by remember { mutableStateOf("") }
    var deviceResults by remember { mutableStateOf<List<FileEntry>>(emptyList()) }
    var deviceBusy by remember { mutableStateOf(false) }
    // Separate flag from the copy job: closing the search sheet must stop the
    // walk, and sharing one token with a running copy would cancel that instead.
    val searchCancel = remember { java.util.concurrent.atomic.AtomicBoolean(false) }
    var extractProgress by remember { mutableStateOf<Pair<Long, Long>?>(null) }
    val cancelToken = remember { java.util.concurrent.atomic.AtomicBoolean(false) }
    // Bumped after every write so the LaunchedEffect re-reads the folder. Keying
    // on the path alone meant a rename or delete left a stale list until the user
    // navigated away and back -- which reads as data loss.
    var refreshKey by remember { mutableStateOf(0) }
    // Folders the user granted through SAF. Persisted, because a tree that is not
    // persisted becomes an entry that fails to open on the next launch, which reads
    // as data loss.
    var trees by remember {
        mutableStateOf(
            context.getSharedPreferences("pure-trees", android.content.Context.MODE_PRIVATE)
                .getStringSet("uris", emptySet()).orEmpty()
                    .map { uri ->
                        val label = runCatching {
                            android.provider.DocumentsContract
                                .getTreeDocumentId(android.net.Uri.parse(uri))
                                ?.substringAfterLast(':')
                                ?.ifEmpty { "Folder" }
                        }.getOrNull() ?: "Folder"
                        label to android.net.Uri.parse(uri)
                    }
        )
    }

    val folderPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocumentTree(),
    ) { uri ->
        if (uri != null && Storage.takePersistable(context, uri)) {
            val prefs = context.getSharedPreferences("pure-trees", android.content.Context.MODE_PRIVATE)
            prefs.edit().putStringSet("uris", prefs.getStringSet("uris", emptySet()).orEmpty() + uri.toString()).apply()
            trees = trees + (Storage.displayName(uri.toString()) to uri)
            // Open it immediately: choosing a folder and then staying put would
            // look like nothing happened.
            path = uri.toString()
            locationLabel = Storage.displayName(uri.toString())
            mode = AccessMode.STORAGE_TREE
            query = ""
            toast = "Folder ditambahkan"
        } else if (uri != null) {
            toast = "Folder itu tidak memberi izin permanen"
        }
    }

    // Re-read whenever the folder, the ordering or the hidden-file setting change.
    LaunchedEffect(path, sortKeyName, sortDescending, showHidden, mode, refreshKey) {
        if (mode == AccessMode.NONE) {
            entries = emptyList()
            return@LaunchedEffect
        }
        val folder = path.ifEmpty {
            Storage.locations(context).firstOrNull()?.path.orEmpty()
        }
        // A SAF tree is listed through the content resolver, not java.io.File.
        if (Storage.isTreePath(folder)) {
            loading = true
            error = null
            val result = withContext(Dispatchers.IO) {
                Storage.listTree(context, android.net.Uri.parse(folder), showHidden)
            }
            entries = result
                .map { it.sortedWith(comparatorFor(SortOrder(SortKey.valueOf(sortKeyName), sortDescending))) }
                .getOrElse {
                    error = it.message ?: "Folder tidak bisa dibaca"
                    emptyList()
                }
            loading = false
            return@LaunchedEffect
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

    // Selection is keyed by path, and cleared whenever the folder changes: keeping
    // paths from another directory selected is how a delete hits the wrong file.
    LaunchedEffect(path) {
        selected = emptySet()
        onSelectedCount(0)
        letterFilter = null
    }
    LaunchedEffect(selectionMode) {
        if (!selectionMode) {
            selected = emptySet()
            onSelectedCount(0)
        }
    }

    // Back means "up" while inside a folder, and "cancel" while items are ticked.
    // Without this, the system back button closed the app from any depth, which is
    // the single most common way a file manager feels wrong.
    BackHandler(enabled = selectionMode || Storage.parentOf(path) != null) {
        when {
            selectionMode -> {
                onSelectionModeChange(false)
                selected = emptySet()
                onSelectedCount(0)
            }
            else -> {
                val parent = Storage.parentOf(path)
                if (parent != null) {
                    path = parent
                    locationLabel = Storage.displayName(parent)
                    query = ""
                }
            }
        }
    }

    fun goTo(target: String, label: String) {
        path = target
        locationLabel = label
        query = ""
    }

    // Column count for the grid. Read once here instead of wrapping the list in a
    // BoxWithConstraints, which would add a nested scroll container.
    val widthDp = LocalConfiguration.current.screenWidthDp

    val visible = remember(entries, query) {
        if (query.isBlank()) entries
        else entries.filter { Storage.searchKey(it.name).contains(Storage.searchKey(query)) }
    }

    // A tap either opens (normal) or ticks (selection mode). A long press opens the
    // action sheet -- the gesture every file manager uses, and the one the owner
    // pointed out was missing. In selection mode a long press also ticks.
    //
    // Tapping a file hands it to whatever app registered for its type. Leaving a
    // placeholder toast here instead was the owner's complaint, and it was fair: a
    // file manager whose files cannot be opened is a folder tree with a settings
    // screen.
    val onTap: (FileEntry) -> Unit = { e ->
        when {
            selectionMode -> {
                val next = if (e.path in selected) selected - e.path else selected + e.path
                selected = next
                onSelectedCount(next.size)
            }
            e.isDirectory -> {
                path = e.path
                locationLabel = Storage.displayName(e.path)
                query = ""
            }
            e.extension in setOf("docx", "xlsx", "pdf") -> {
                editing = null
                previewing = e
            }
            else -> {
                val opened = Storage.open(context, e)
                if (opened.isFailure) {
                    toast = opened.exceptionOrNull()?.message ?: "Berkas tidak bisa dibuka"
                }
            }
        }
    }

    /**
     * Text files the editor can open.
     *
     * An explicit list rather than "anything that is not a binary": offering Edit on
     * a video produces only an error message, and a menu that offers what it cannot
     * do is worse than a shorter menu.
     */
    val canEdit: (FileEntry) -> Boolean = { e ->
        !e.isDirectory && (
            e.extension in setOf(
                "txt", "text", "log", "md", "markdown", "csv", "tsv", "json", "jsonl",
                "xml", "html", "htm", "css", "js", "mjs", "ts", "kt", "kts", "java",
                "py", "sh", "bash", "properties", "cfg", "conf", "ini", "toml", "yml",
                "yaml", "gradle", "sql", "c", "h", "cpp", "hpp", "rs", "go", "svg",
            ) || e.name in setOf("gradlew", "Makefile", "Dockerfile")
            )
    }

    val onLongPress: (FileEntry) -> Unit = { e ->
        if (selectionMode) {
            val next = if (e.path in selected) selected - e.path else selected + e.path
            selected = next
            onSelectedCount(next.size)
        } else {
            actionTarget = e
        }
    }

    Column {
        when (mode) {
            AccessMode.NONE -> PermissionCard(
                spec = spec,
                onAllFiles = { context.startActivity(Storage.allFilesIntent(context)) },
                onPickFolder = { folderPicker.launch(null) },
            )
            else -> {
                SearchField(
                    spec = spec,
                    value = query,
                    onValueChange = { query = it },
                    onSearchDevice = {
                        // The device search takes the text already typed, so the
                        // button continues what the user was doing instead of
                        // opening an empty box.
                        searchDevice = true
                        if (query.isNotBlank()) {
                            // Captured before the coroutine starts: reading a
                            // Compose state from a background thread is the kind of
                            // thing that works until it does not.
                            val needle = query
                            val includeHidden = showHidden
                            deviceQuery = needle
                            deviceBusy = true
                            deviceResults = emptyList()
                            searchCancel.set(false)
                            scope.launch {
                                val roots = Storage.locations(context).map { it.path }
                                val hits = withContext(Dispatchers.IO) {
                                    Search.find(
                                        roots = roots,
                                        query = needle,
                                        showHidden = includeHidden,
                                        cancelled = { searchCancel.get() },
                                    )
                                }
                                if (!searchCancel.get()) deviceResults = hits
                                deviceBusy = false
                            }
                        }
                    },
                )
                Spacer(Modifier.height(10.dp))
                Toolbar(
                    spec = spec,
                    label = locationLabel,
                    sortKey = SortKey.valueOf(sortKeyName),
                    descending = sortDescending,
                    grid = grid,
                    showHidden = showHidden,
                    onUp = {
                        Storage.parentOf(path)?.let { parent ->
                            goTo(parent, Storage.displayName(parent))
                        }
                    },
                    canGoUp = Storage.parentOf(path) != null,
                    onPlaces = { showPlaces = true },
                    onUsage = {
                        usageBusy = true
                        scope.launch {
                            val here = path
                            usage = withContext(Dispatchers.IO) {
                                Usage.scan(here, true).getOrDefault(emptyList())
                            }
                            usageBusy = false
                        }
                    },
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
                    onAddFolder = { folderPicker.launch(null) },
                    onHome = {
                        val first = Storage.locations(context).firstOrNull()
                        if (first != null) goTo(first.path, first.label)
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
                            // iPhone in portrait gets three columns; a tablet or a
                            // folded phone in landscape has room for four. Compute
                            // it from the width rather than hardcoding three and
                            // leaving a thumb-wide margin on a large screen.
                            val columns = if (widthDp >= 600) 4 else 3
                            // No card here. In Files the icons sit straight on the
                            // page, and the earlier version wrapped them in a white
                            // rounded card, which is what made it read as Android
                            // settings rather than a file manager.
                            Column(Modifier.padding(vertical = 6.dp)) {
                                visible.chunked(columns).forEach { row ->
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
                                                    onClick = { onTap(e) },
                                                    onLongClick = { onLongPress(e) },
                                                    selected = e.path in selected,
                                                    // Only images and videos ask for a
                                                    // thumbnail; a text file would
                                                    // spend a decode to draw its glyph.
                                                    thumbnailOf = e.path.takeIf { wantsThumbnail(e) },
                                                )
                                            }
                                        }
                                        repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
                                    }
                                }
                            }
                        } else {
                            // Sections, not one long card: the letter is the whole
                            // point of the index, and a single card gave no place
                            // to put it.
                            val grouped = Alphabet.group(
                                if (letterFilter == null) visible
                                else visible.filter { Alphabet.sectionOf(it.name) == letterFilter },
                            )
                            Row(Modifier.fillMaxWidth()) {
                                Column(Modifier.weight(1f)) {
                                    if (grouped.isEmpty()) {
                                        MessageCard(
                                            spec = spec,
                                            title = "Tidak ada di \u201c$letterFilter\u201d",
                                            body = "Tidak ada nama yang mulai dengan huruf itu.",
                                        )
                                    }
                                    grouped.forEach { (letter, items) ->
                                        SectionHeader(spec, letter)
                                        GroupCard(spec) {
                                            items.forEachIndexed { i, e ->
                                                // Files shows the size or the item
                                                // count under the name and a chevron
                                                // only for folders. The ellipsis
                                                // button that used to sit on every
                                                // row pushed the size out and made a
                                                // long list look like settings; the
                                                // menu is still on long-press.
                                                ListRow(
                                                    spec = spec,
                                                    title = e.name,
                                                    subtitle = subtitleFor(e),
                                                    isFolder = e.isDirectory,
                                                    glyph = glyphFor(e),
                                                    showChevron = !selectionMode && e.isDirectory,
                                                    onClick = { onTap(e) },
                                                    onLongClick = { onLongPress(e) },
                                                    selected = e.path in selected,
                                                    flush = i == items.lastIndex,
                                                    thumbnailOf = e.path.takeIf { wantsThumbnail(e) },
                                                )
                                            }
                                        }
                                    }
                                }
                                if (visible.size >= 8) {
                                    AlphabetStrip(
                                        spec = spec,
                                        letters = Alphabet.group(visible).map { it.first },
                                        active = letterFilter,
                                        onPick = { letter ->
                                            letterFilter = if (letterFilter == letter) null else letter
                                        },
                                    )
                                }
                            }
                        }

                        Spacer(Modifier.height(12.dp))
                        Text(
                            Support.countLabel(visible) +
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
                        onOpen = {
                            actionTarget = null
                            if (target.isDirectory) {
                                goTo(target.path, Storage.displayName(target.path))
                            } else {
                                val opened = Storage.open(context, target)
                                if (opened.isFailure) {
                                    toast = opened.exceptionOrNull()?.message
                                        ?: "Berkas tidak bisa dibuka"
                                }
                            }
                        },
                        onShare = {
                            actionTarget = null
                            val launched = runCatching {
                                context.startActivity(
                                    android.content.Intent.createChooser(
                                        Storage.shareIntent(context, target), "Bagikan lewat",
                                    ).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK),
                                )
                            }
                            if (launched.isFailure) {
                                toast = "Tidak ada aplikasi untuk membagikan berkas ini"
                            }
                        },
                        onArchive = if (!target.isDirectory && Archive.isZip(target.name)) {
                            {
                                actionTarget = null
                                val listing = Archive.list(target.path)
                                val entries = listing.getOrNull()
                                if (entries == null) {
                                    toast = listing.exceptionOrNull()?.message ?: "Arsip tidak bisa dibaca"
                                } else {
                                    archiveView = target to entries
                                }
                            }
                        } else null,
                        onExtract = if (!target.isDirectory && Archive.isZip(target.name)) {
                            {
                                actionTarget = null
                                val archive = target
                                val destination = Archive.destinationFor(archive.path, path)
                                cancelToken.set(false)
                                extractProgress = 0L to 0L
                                scope.launch {
                                    val result = withContext(Dispatchers.IO) {
                                        Archive.extract(
                                            archive.path,
                                            destination,
                                            cancelled = { cancelToken.get() },
                                        ) { done, total, _ -> extractProgress = done to total }
                                    }
                                    extractProgress = null
                                    toast = result.fold(
                                        { "$it berkas diekstrak" },
                                        { it.message ?: "Gagal mengekstrak" },
                                    )
                                    goTo(destination, Storage.displayName(destination))
                                    reload()
                                }
                            }
                        } else null,
                        onRename = { actionTarget = null; prompt = Prompt.Rename(target) },
                        onCopy = {
                            actionTarget = null
                            clipboard = Clipboard(listOf(target.path), move = false)
                            picker = DestinationPicker.Choosing(path, pickMode = false, startLabel = locationLabel)
                        },
                        onMove = {
                            actionTarget = null
                            clipboard = Clipboard(listOf(target.path), move = true)
                            picker = DestinationPicker.Choosing(path, pickMode = false, startLabel = locationLabel)
                        },
                        onDelete = { actionTarget = null; deleteTarget = target },
                        onInfo = { actionTarget = null; prompt = Prompt.Info(target) },
                        onEdit = if (canEdit(target)) {
                            {
                                actionTarget = null
                                previewing = null
                                editing = target
                            }
                        } else null,
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

                if (bulkDelete && selected.isNotEmpty()) {
                    ConfirmDialog(
                        spec = spec,
                        title = "Hapus ${selected.size} item?",
                        body = "Semua yang dipilih akan dihapus beserta isinya. " +
                            "Tidak ada tong sampah: ini langsung terhapus.",
                        confirm = "Hapus",
                        onDismiss = { bulkDelete = false },
                        onConfirm = {
                            val doomed = selected.toList()
                            bulkDelete = false
                            scope.launch {
                                val outcome = withContext(Dispatchers.IO) {
                                    doomed.map { path ->
                                        FileOps.delete(
                                            FileEntry(path, Storage.displayName(path), File(path).isDirectory, 0, 0, false, true),
                                        )
                                    }
                                }
                                val failed = outcome.count { it.isFailure }
                                toast = if (failed == 0) "${outcome.size} terhapus"
                                else "$failed gagal dihapus"
                                selected = emptySet()
                                onSelectedCount(0)
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

                editing?.let { file ->
                    EditorScreen(
                        spec = spec,
                        entry = file,
                        onClose = { editing = null },
                        onSaved = { toast = "Tersimpan" },
                    )
                }

                previewing?.let { doc ->
                    DocumentScreen(
                        spec = spec,
                        entry = doc,
                        onClose = { previewing = null },
                    )
                    Spacer(Modifier.height(16.dp))
                }

                if (searchDevice) {
                    DeviceSearchDialog(
                        spec = spec,
                        query = deviceQuery.ifBlank { "ketik sesuatu dulu" },
                        results = deviceResults,
                        busy = deviceBusy,
                        onDismiss = {
                            // Closing stops the walk rather than letting it read
                            // the card in the background for a list nobody sees.
                            searchCancel.set(true)
                            searchDevice = false
                        },
                        onOpen = { e ->
                            val opened = Storage.open(context, e)
                            if (opened.isFailure) {
                                toast = opened.exceptionOrNull()?.message
                                    ?: "Berkas tidak bisa dibuka"
                            }
                        },
                        onReveal = { e ->
                            searchDevice = false
                            searchCancel.set(true)
                            val folder = Support.parentOf(e.path)
                            if (folder != null) {
                                goTo(folder, Storage.displayName(folder))
                            }
                        },
                    )
                }

                if (selectionMode) {
                    Spacer(Modifier.height(10.dp))
                    SelectionBar(
                        spec = spec,
                        count = selected.size,
                        onSelectAll = {
                            val all = visible.map { it.path }.toSet()
                            selected = all
                            onSelectedCount(all.size)
                        },
                        onCopy = {
                            clipboard = Clipboard(selected.toList(), move = false)
                            picker = DestinationPicker.Choosing(
                                path, pickMode = false, startLabel = locationLabel,
                            )
                        },
                        onMove = {
                            clipboard = Clipboard(selected.toList(), move = true)
                            picker = DestinationPicker.Choosing(
                                path, pickMode = false, startLabel = locationLabel,
                            )
                        },
                        onDelete = {
                            // Bulk delete goes through the same confirmation as a
                            // single file, naming the count instead of one name.
                            bulkDelete = true
                        },
                        onCancel = {
                            onSelectionModeChange(false)
                            selected = emptySet()
                            onSelectedCount(0)
                        },
                    )
                }

                (picker as? DestinationPicker.Choosing)?.let { choosing ->
                    DestinationDialog(
                        spec = spec,
                        initialPath = choosing.startPath,
                        move = clipboard?.move == true,
                        count = clipboard?.paths?.size ?: 0,
                        onDismiss = { picker = null; clipboard = null },
                        onConfirm = { destination ->
                            val clip = clipboard
                            picker = null
                            clipboard = null
                            if (clip != null) {
                                // One job at a time. A second copy started while the
                                // first is running would fight over the same token.
                                cancelToken.set(false)
                                scope.launch {
                                    val outcome = withContext(Dispatchers.IO) {
                                        val report: (CopyEngine.Progress) -> Unit = { p ->
                                            // Called on the worker thread; writing a
                                            // Compose state from there is allowed and is
                                            // cheaper than bouncing every chunk back.
                                            job = p
                                        }
                                        val token = { cancelToken.get() }
                                        if (clip.move) {
                                            CopyEngine.move(clip.paths, destination, token, report)
                                        } else {
                                            CopyEngine.copy(clip.paths, destination, token, report)
                                        }
                                    }
                                    job = null
                                    val cancelledCount =
                                        outcome.count { it.exceptionOrNull() is CopyEngine.Cancelled }
                                    val failed = outcome.count { it.isFailure }
                                    toast = when {
                                        cancelledCount > 0 -> "Dibatalkan"
                                        failed == 0 -> "${outcome.size} selesai"
                                        failed == outcome.size ->
                                            outcome.first().exceptionOrNull()?.message ?: "Gagal"
                                        else -> "$failed dari ${outcome.size} gagal"
                                    }
                                    // A cancelled move must not clear the selection: the
                                    // files are still where they were.
                                    if (failed == 0 && clip.move) selected = emptySet()
                                    onSelectedCount(0)
                                    reload()
                                }
                            }
                        },
                    )
                }

                archiveView?.let { (archive, entries) ->
                    ArchiveDialog(
                        spec = spec,
                        title = archive.name,
                        entries = entries,
                        onDismiss = { archiveView = null },
                    )
                }

                extractProgress?.let { (done, total) ->
                    ExtractProgressDialog(
                        spec = spec,
                        done = done,
                        total = total,
                        onCancel = { cancelToken.set(true) },
                    )
                }

                if (usage != null || usageBusy) {
                    UsageDialog(
                        spec = spec,
                        busy = usageBusy,
                        tallies = usage.orEmpty(),
                        onDismiss = { usage = null; usageBusy = false },
                        onOpen = { tally ->
                            usage = null
                            if (tally.isDirectory) goTo(tally.path, tally.name)
                        },
                    )
                }

                job?.let { progress ->
                    CopyProgressDialog(
                        spec = spec,
                        progress = progress,
                        onCancel = { cancelToken.set(true) },
                    )
                }

                if (showPlaces) {
                    PlacesDialog(
                        spec = spec,
                        places = Storage.places(context, trees, showSystemPlaces),
                        current = path,
                        onDismiss = { showPlaces = false },
                        onPick = { location ->
                            showPlaces = false
                            goTo(location.path, location.label)
                        },
                        onAddTree = {
                            showPlaces = false
                            folderPicker.launch(null)
                        },
                        showSystem = showSystemPlaces,
                        onToggleSystem = { showSystemPlaces = !showSystemPlaces },
                    )
                }

                toast?.let { message ->
                    Toast(spec, message) { toast = null }
                }
            }
        }
    }
}

/** True for the file types where a picture beats a glyph. */
private fun wantsThumbnail(e: FileEntry): Boolean {
    if (e.isDirectory) return false
    val mime = Support.mimeFor(e.name)
    return mime.startsWith("image/") || mime.startsWith("video/")
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

/**
 * The clipboard.
 *
 * One type with a mode instead of two flows: "Salin" and "Pindahkan" differ only in
 * what happens after the destination is chosen, and building them as separate
 * journeys is how one of them ends up half-implemented.
 */
private data class Clipboard(val paths: List<String>, val move: Boolean)

/** Which destination dialog is open. */
private sealed interface DestinationPicker {
    /** Browsing to choose where the clipboard lands. */
    data class Choosing(
        val startPath: String,
        val pickMode: Boolean,
        val startLabel: String = "Internal",
    ) : DestinationPicker

    /** Confirming the folder currently browsed. */
    data class Confirm(val destination: String) : DestinationPicker
}

/** What the prompt dialog is for. One dialog, five jobs. */
private sealed interface Prompt {
    data object NEW_FOLDER : Prompt
    data class Rename(val entry: FileEntry) : Prompt
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
    onPlaces: () -> Unit,
    onUsage: () -> Unit,
    onAddFolder: () -> Unit,
    onUp: () -> Unit,
    onSort: () -> Unit,
    onToggleGrid: () -> Unit,
    onToggleHidden: () -> Unit,
    onHome: () -> Unit,
) {
    val p = spec.palette
    // Two rows, the way Files does it: the location and the sort order sit under
    // the bar, and the controls are round buttons on one line. The earlier version
    // packed six buttons and two lines of text into a single row, which on a
    // 360 dp screen left about 90 dp for the folder name.
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            if (canGoUp) {
                ToolButton("\u2190", false, onUp)
                Spacer(Modifier.size(4.dp))
            }
            Column(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape((spec.cornerDp * 0.6f).dp))
                    .clickable(onClick = onPlaces)
                    .padding(vertical = 2.dp, horizontal = 2.dp),
            ) {
                Text(
                    label,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = p.onBackground,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .clip(RoundedCornerShape((spec.cornerDp * 0.5f).dp))
                        .clickable(onClick = onSort)
                        .padding(vertical = 2.dp, horizontal = 2.dp),
                ) {
                    Text(
                        when (sortKey) {
                            SortKey.NAME -> "Nama"
                            SortKey.SIZE -> "Ukuran"
                            SortKey.DATE -> "Tanggal"
                            SortKey.TYPE -> "Jenis"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = p.accent,
                    )
                    Text(
                        if (descending) " \u25BE" else " \u25B4",
                        style = MaterialTheme.typography.labelSmall,
                        color = p.accent,
                    )
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            ToolButton(if (showHidden) "\u25C9" else "\u25CB", showHidden, onToggleHidden)
            ToolButton(if (grid) "\u2637" else "\u2263", true, onToggleGrid)
            ToolButton("\u25E7", false, onUsage)
            ToolButton("\u2302", false, onHome)
            ToolButton("\u2295", false, onAddFolder)
            Spacer(Modifier.weight(1f))
        }
    }
}

/**
 * The letter above a group in the list.
 *
 * Left-aligned and small, the way Files and Contacts draw it. The `#` group keeps
 * its header: an unlabelled pile of files whose names start with a digit is the
 * one place a reader cannot guess what they are looking at.
 */
@Composable
private fun SectionHeader(spec: PureThemeSpec, letter: String) {
    val p = spec.palette
    Text(
        letter,
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.SemiBold,
        color = p.accent,
        modifier = Modifier.padding(start = 16.dp, top = 14.dp, bottom = 4.dp),
    )
}

/**
 * The A–Z strip down the right edge.
 *
 * Two things it deliberately does not do:
 *
 *  - It does not draw all 27 letters when the folder only has four of them. An
 *    index with 23 dead letters is a scrollbar pretending to be a menu.
 *  - It is not a scroll-jump. The list lives inside the shell's scroll state,
 *    which this screen does not own, so the strip filters instead: tapping "L"
 *    shows the names that start with L, tapping it again goes back. Filtering is
 *    what the owner asked for when they said "indeks A–Z", and it works on a list
 *    of any length without a scroll position to fight over.
 */
@Composable
private fun AlphabetStrip(
    spec: PureThemeSpec,
    letters: List<String>,
    active: String?,
    onPick: (String) -> Unit,
) {
    val p = spec.palette
    Column(
        Modifier
            .padding(start = 2.dp)
            .padding(top = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        letters.forEach { letter ->
            val on = letter == active
            Box(
                Modifier
                    .width(22.dp)
                    .height(20.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (on) p.accent else Color.Transparent)
                    .clickable { onPick(letter) },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    letter,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
                    color = if (on) p.onAccent else p.accent,
                )
            }
        }
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

// internal, not private: the document viewer shows the same card when a file
// cannot be read, and one empty-state style is better than two that drift.
@Composable
internal fun MessageCard(spec: PureThemeSpec, title: String, body: String) {
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

/**
 * Every place the app can browse, in one list.
 *
 * The reason this exists: after the first launch, a folder added through SAF could
 * only be reached by adding it again. The trees were stored and never shown
 * anywhere, so "add a folder" was a one-way door, and a file manager that cannot
 * switch volume is stuck inside whichever one it opened.
 */
/**
 * The copy, while it happens.
 *
 * Deliberately not dismissible by tapping outside: a dialog that can be dismissed
 * while work continues underneath is a dialog that lies about what a tap did. The
 * only ways out are finishing and Batal, and both are visible.
 */
/**
 * Which folders are using the space.
 *
 * Bars are relative to the largest child, not to the sum: the job is to find the
 * biggest thing, and a folder holding 99% of the bytes would otherwise draw every
 * other row as a sliver too small to see.
 */
/**
 * What is inside a zip.
 *
 * Read-only on purpose. Showing the contents answers the question people actually
 * have ("did this download work?"), and extraction stays an explicit choice rather
 * than something that starts because a row was tapped.
 */
@Composable
private fun ArchiveDialog(
    spec: PureThemeSpec,
    title: String,
    entries: List<Archive.Entry>,
    onDismiss: () -> Unit,
) {
    val p = spec.palette
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1) },
        text = {
            Column {
                Text(
                    "${entries.size} entri \u00b7 " +
                        formatSize(entries.sumOf { it.bytes }, false),
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                Column(
                    Modifier
                        .fillMaxWidth()
                        .height(320.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    entries.forEach { entry ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 5.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                if (entry.isDirectory) "\u25A0 " else "\u00b7 ",
                                style = MaterialTheme.typography.bodySmall,
                                color = p.accent,
                            )
                            Text(
                                entry.name,
                                style = MaterialTheme.typography.bodySmall,
                                color = p.onBackground,
                                maxLines = 1,
                                modifier = Modifier.weight(1f),
                            )
                            if (!entry.isDirectory) {
                                Text(
                                    formatSize(entry.bytes, false),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = p.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Tutup", color = p.accent) }
        },
    )
}

/**
 * Extraction progress, in the same shape as the copy dialog.
 *
 * An archive with a single 2 GB video reports a size that only moves at the end, so
 * the percentage and the cancel button are what makes the wait tolerable.
 */
@Composable
private fun ExtractProgressDialog(
    spec: PureThemeSpec,
    done: Long,
    total: Long,
    onCancel: () -> Unit,
) {
    val p = spec.palette
    val fraction = if (total <= 0L) 0f else (done.toDouble() / total).toFloat().coerceIn(0f, 1f)
    AlertDialog(
        onDismissRequest = { /* only Batal stops the job */ },
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text("Mengekstrak", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                Text(
                    "${(fraction * 100).toInt()}%",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                    color = p.onBackground,
                )
                Spacer(Modifier.height(10.dp))
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(p.surfaceVariant),
                ) {
                    Box(
                        Modifier
                            .fillMaxWidth(fraction)
                            .height(8.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(p.accent),
                    )
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    formatSize(done, false) + " dari " + formatSize(total, false),
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onCancel) {
                Text("Batal", color = Color(0xFFEF4444), fontWeight = FontWeight.Medium)
            }
        },
    )
}

@Composable
private fun UsageDialog(
    spec: PureThemeSpec,
    busy: Boolean,
    tallies: List<Usage.Tally>,
    onDismiss: () -> Unit,
    onOpen: (Usage.Tally) -> Unit,
) {
    val p = spec.palette
    val top = tallies.maxOfOrNull { it.bytes } ?: 0L
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text("Analisis penyimpanan", style = MaterialTheme.typography.titleMedium) },
        text = {
            if (busy) {
                CircularProgressIndicator(color = p.accent)
            } else {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .height(320.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    if (tallies.isEmpty()) {
                        Text(
                            "Folder ini kosong.",
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    }
                    tallies.forEach { tally ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(spec.cornerDp.dp))
                                .clickable { onOpen(tally) }
                                .padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            if (tally.isDirectory) IosFolder(size = 20f)
                            Column(Modifier.weight(1f)) {
                                Text(
                                    tally.name,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = p.onBackground,
                                    maxLines = 1,
                                )
                                Spacer(Modifier.height(3.dp))
                                Box(
                                    Modifier
                                        .fillMaxWidth()
                                        .height(4.dp)
                                        .clip(RoundedCornerShape(2.dp))
                                        .background(p.surfaceVariant),
                                ) {
                                    val share = if (top <= 0L) 0f
                                        else (tally.bytes.toDouble() / top).toFloat()
                                    Box(
                                        Modifier
                                            .fillMaxWidth(share.coerceIn(0f, 1f))
                                            .height(4.dp)
                                            .clip(RoundedCornerShape(2.dp))
                                            .background(p.accent),
                                    )
                                }
                            }
                            Text(
                                formatSize(tally.bytes, tally.isDirectory),
                                style = MaterialTheme.typography.labelSmall,
                                color = p.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Tutup", color = p.accent) }
        },
    )
}

@Composable
private fun CopyProgressDialog(
    spec: PureThemeSpec,
    progress: CopyEngine.Progress,
    onCancel: () -> Unit,
) {
    val p = spec.palette
    val percent = (progress.fraction * 100).toInt().coerceIn(0, 100)
    AlertDialog(
        onDismissRequest = { /* only Batal stops the job */ },
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text("Menyalin berkas", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                Text(
                    "$percent%",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                    color = p.onBackground,
                )
                Spacer(Modifier.height(10.dp))
                // A plain filled bar instead of LinearProgressIndicator: one less
                // component whose size changes between Compose versions.
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(p.surfaceVariant),
                ) {
                    Box(
                        Modifier
                            .fillMaxWidth(progress.fraction.coerceIn(0f, 1f))
                            .height(8.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(p.accent),
                    )
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    "${progress.filesDone} dari ${progress.filesTotal} berkas \u00b7 " +
                        formatSize(progress.bytesDone, false) + " dari " +
                        formatSize(progress.bytesTotal, false),
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    progress.currentName,
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onCancel) {
                Text("Batal", color = Color(0xFFEF4444), fontWeight = FontWeight.Medium)
            }
        },
    )
}

@Composable
private fun PlacesDialog(
    spec: PureThemeSpec,
    places: List<net.pure.manager.fs.Location>,
    current: String,
    onDismiss: () -> Unit,
    onPick: (net.pure.manager.fs.Location) -> Unit,
    onAddTree: () -> Unit,
    showSystem: Boolean,
    onToggleSystem: () -> Unit,
) {
    val p = spec.palette
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = { Text("Lokasi", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                places.forEach { location ->
                    val here = location.path == current
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(spec.cornerDp.dp))
                            .clickable { onPick(location) }
                            .padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        IosFolder(size = 24f)
                        Column(Modifier.weight(1f)) {
                            Text(
                                location.label,
                                style = MaterialTheme.typography.bodyLarge,
                                color = if (here) p.accent else p.onBackground,
                                maxLines = 1,
                            )
                            Text(
                                location.description,
                                style = MaterialTheme.typography.bodySmall,
                                color = p.onSurfaceVariant,
                                maxLines = 1,
                            )
                        }
                        if (here) Text("\u2713", color = p.accent)
                    }
                }
                Spacer(Modifier.height(4.dp))
                // Root-only shortcuts, behind a switch. Without root the rows
                // would open and fail; with it they are the only way to reach
                // /system and /data from this screen at all.
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(spec.cornerDp.dp))
                        .clickable(onClick = onToggleSystem)
                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            "Folder sistem",
                            style = MaterialTheme.typography.bodyLarge,
                            color = p.onBackground,
                        )
                        Text(
                            if (showSystem) "/system, /data, /data/adb \u00b7 butuh root"
                            else "Tampilkan /system dan /data (butuh root)",
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    }
                    Text(
                        if (showSystem) "\u25C9" else "\u25CB",
                        style = MaterialTheme.typography.titleMedium,
                        color = p.accent,
                    )
                }
                Text(
                    "Tambah folder lewat sistem",
                    style = MaterialTheme.typography.bodyLarge,
                    color = p.accent,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(spec.cornerDp.dp))
                        .clickable(onClick = onAddTree)
                        .padding(vertical = 10.dp),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Tutup", color = p.accent) }
        },
    )
}

@Composable
private fun DeviceSearchDialog(
    spec: PureThemeSpec,
    query: String,
    results: List<FileEntry>,
    busy: Boolean,
    onDismiss: () -> Unit,
    onOpen: (FileEntry) -> Unit,
    onReveal: (FileEntry) -> Unit,
) {
    val p = spec.palette
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = {
            Column {
                Text("Cari di perangkat", style = MaterialTheme.typography.titleMedium)
                Text(
                    if (busy) "Mencari \u201c$query\u201d\u2026"
                    else "${results.size} hasil untuk \u201c$query\u201d",
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        },
        text = {
            Column(Modifier.heightIn(max = 380.dp).verticalScroll(rememberScrollState())) {
                if (busy && results.isEmpty()) {
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = p.accent,
                            strokeWidth = 2.dp,
                        )
                        Text(
                            "Menelusuri penyimpanan\u2026",
                            style = MaterialTheme.typography.bodyMedium,
                            color = p.onSurfaceVariant,
                        )
                    }
                } else if (results.isEmpty()) {
                    Text(
                        "Tidak ada berkas yang namanya mengandung \u201c$query\u201d. " +
                            "Pencarian menyusuri penyimpanan sampai " +
                            "${Search.MAX_DEPTH} tingkat dan berhenti di " +
                            "folder milik aplikasi lain.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = p.onSurfaceVariant,
                    )
                } else {
                    results.forEachIndexed { i, e ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(spec.cornerDp.dp))
                                .clickable { onOpen(e) }
                                .padding(vertical = 8.dp, horizontal = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Box(
                                Modifier
                                    .size(32.dp)
                                    .clip(RoundedCornerShape(7.dp))
                                    .background(p.surfaceVariant),
                                contentAlignment = Alignment.Center,
                            ) { Text(glyphFor(e), style = MaterialTheme.typography.labelLarge, color = p.accent) }
                            Column(Modifier.weight(1f)) {
                                Text(
                                    e.name,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = p.onBackground,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    Support.trimPath(e.path, 44) + " \u00b7 " +
                                        formatSize(e.sizeBytes, false),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = p.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                            Text(
                                "Buka",
                                style = MaterialTheme.typography.bodySmall,
                                color = p.accent,
                                modifier = Modifier
                                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                                    .clickable { onReveal(e) }
                                    .padding(horizontal = 6.dp, vertical = 4.dp),
                            )
                        }
                        if (i != results.lastIndex) {
                            Box(
                                Modifier
                                    .fillMaxWidth()
                                    .padding(start = 44.dp)
                                    .height(0.5.dp)
                                    .background(p.separator),
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Tutup", color = p.accent) }
        },
    )
}

@Composable
private fun ActionSheet(
    spec: PureThemeSpec,
    target: FileEntry,
    onDismiss: () -> Unit,
    onOpen: () -> Unit,
    onShare: () -> Unit,
    onArchive: (() -> Unit)?,
    onExtract: (() -> Unit)?,
    onRename: () -> Unit,
    onCopy: () -> Unit,
    onMove: () -> Unit,
    onDelete: () -> Unit,
    onInfo: () -> Unit,
    /** Null when the selected file is not text the editor can open. */
    onEdit: (() -> Unit)? = null,
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
                // A folder is opened by tapping it; a file needs an explicit row
                // because the same tap has to stay free for "select" in selection
                // mode. Share is separate from open: "make this available to
                // another app" is the reason people long-press a file.
                if (target.isDirectory) {
                    ActionRow("Buka", onOpen)
                } else {
                    ActionRow("Buka dengan\u2026", onOpen)
                    ActionRow("Bagikan", onShare)
                }
                if (onEdit != null) ActionRow("Edit teks", onEdit)
                if (onArchive != null) ActionRow("Lihat isi arsip", onArchive)
                if (onExtract != null) ActionRow("Ekstrak ke sini", onExtract)
                ActionRow("Ganti nama", onRename)
                ActionRow("Salin ke\u2026", onCopy)
                ActionRow("Pindahkan ke\u2026", onMove)
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
        is Prompt.Info -> prompt.entry.name
    }
    var value by remember { mutableStateOf(initial) }
    val isInfo = prompt is Prompt.Info

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

// ---------------------------------------------------------- destination picker

/**
 * Choose where copied or moved files land.
 *
 * The earlier build could only copy into the folder that was already open, which
 * is not copying: it is duplicating in place. This is a real browser with an up
 * button, a folder list, and an explicit confirmation, because "paste here" while
 * the destination is ambiguous is how files end up somewhere unexpected.
 */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun DestinationDialog(
    spec: PureThemeSpec,
    initialPath: String,
    move: Boolean,
    count: Int,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit,
) {
    val context = LocalContext.current
    val p = spec.palette
    var here by remember { mutableStateOf(initialPath) }
    var label by rememberSaveable { mutableStateOf(Storage.displayName(initialPath)) }
    var children by remember { mutableStateOf<List<FileEntry>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }

    LaunchedEffect(here) {
        busy = true
        children = if (Storage.isTreePath(here)) {
            withContext(Dispatchers.IO) { Storage.listTree(context, android.net.Uri.parse(here), false) }
                .getOrDefault(emptyList())
        } else {
            withContext(Dispatchers.IO) { Storage.list(here, false) }
                .getOrDefault(emptyList())
        }
            .filter { it.isDirectory }
            .sortedWith(comparatorFor(SortOrder(SortKey.NAME, false)))
        busy = false
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        titleContentColor = p.onBackground,
        textContentColor = p.onSurfaceVariant,
        title = {
            Text(
                "${if (move) "Pindahkan" else "Salin"} $count item",
                style = MaterialTheme.typography.titleMedium,
            )
        },
        text = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Named arguments, not a trailing lambda: ToolButton takes
                    // tint = null after onClick, so `ToolButton(a, b) { ... }`
                    // binds the lambda to tint and fails to compile.
                    ToolButton(
                        glyph = "\u2190",
                        active = false,
                        onClick = {
                            Storage.parentOf(here)?.let { up ->
                                here = up
                                label = Storage.displayName(up)
                            }
                        },
                    )
                    Spacer(Modifier.size(8.dp))
                    Text(
                        label,
                        style = MaterialTheme.typography.bodyLarge,
                        color = p.onBackground,
                        maxLines = 1,
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(8.dp))
                Column(
                    Modifier
                        .fillMaxWidth()
                        .height(280.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    if (busy) {
                        CircularProgressIndicator(color = p.accent)
                    } else if (children.isEmpty()) {
                        Text(
                            "Tidak ada subfolder di sini.",
                            style = MaterialTheme.typography.bodySmall,
                            color = p.onSurfaceVariant,
                        )
                    } else {
                        children.forEach { child ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        here = child.path
                                        label = child.name
                                    }
                                    .padding(vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                IosFolder(size = 26f)
                                Text(
                                    child.name,
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = p.onBackground,
                                    maxLines = 1,
                                )
                            }
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Nama yang sudah ada tidak ditimpa: berkas baru mendapat akhiran (1).",
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(here) }) {
                Text(
                    if (move) "Pindahkan ke sini" else "Salin ke sini",
                    color = p.accent,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Batal", color = p.accent) }
        },
    )
}

/** Bar shown while items are ticked: every bulk action in one row. */
@Composable
private fun SelectionBar(
    spec: PureThemeSpec,
    count: Int,
    onCopy: () -> Unit,
    onMove: () -> Unit,
    onDelete: () -> Unit,
    onSelectAll: () -> Unit,
    onCancel: () -> Unit,
) {
    val p = spec.palette
    GroupCard(spec) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                "$count dipilih",
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                color = p.onBackground,
                modifier = Modifier.padding(start = 8.dp).weight(1f),
            )
            SelectionAction("Pilih semua", p.accent, onSelectAll)
            SelectionAction("Salin", p.accent, onCopy)
            SelectionAction("Pindah", p.accent, onMove)
            SelectionAction("Hapus", Color(0xFFEF4444), onDelete)
            SelectionAction("Batal", p.onSurfaceVariant, onCancel)
        }
    }
}

@Composable
private fun SelectionAction(label: String, color: Color, onClick: () -> Unit) {
    val spec = LocalPureSpec.current
    Text(
        label,
        style = MaterialTheme.typography.labelMedium,
        color = color,
        modifier = Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 6.dp),
    )
}
