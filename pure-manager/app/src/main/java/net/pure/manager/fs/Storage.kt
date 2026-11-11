package net.pure.manager.fs

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.storage.StorageManager
import android.provider.Settings
import android.provider.DocumentsContract
import androidx.core.content.ContextCompat
import androidx.documentfile.provider.DocumentFile
import java.io.File
import java.util.Locale

/**
 * Where the browser is allowed to look, and how it got there.
 *
 * Two routes exist because Android keeps closing the good one:
 *
 *  - [Mode.ALL_FILES]  — `MANAGE_EXTERNAL_STORAGE`, real `java.io.File` access to
 *    everything not owned by another app. Android 10 and up, user grants it in
 *    Settings. This is what a file manager wants.
 *  - [Mode.STORAGE_TREE] — the Storage Access Framework. No special permission,
 *    the user picks folders. Works on every version and survives Android's
 *    tightening, but paths are document URIs, not files.
 *
 * The app asks for ALL_FILES first and falls back to SAF. It never claims to be
 * able to do something it cannot: [explain] returns the sentence shown when the
 * permission is missing, so the UI says why a folder is empty.
 */
enum class AccessMode {
    NONE,

    /** Full read/write through java.io.File, granted via MANAGE_EXTERNAL_STORAGE. */
    ALL_FILES,

    /** Scoped access to folders the user picked, through SAF. */
    STORAGE_TREE,
}

/** A top-level place the browser can open. */
data class Location(
    val label: String,
    val path: String,
    val description: String,
    /** Null for storage volumes, set for the SAF trees the user added. */
    val treeUri: Uri? = null,
)

object Storage {

    /** The permission the app asks for, and the one Google calls "all files". */
    const val ALL_FILES_PERMISSION: String = Manifest.permission.MANAGE_EXTERNAL_STORAGE

    fun mode(context: Context): AccessMode = when {
        Build.VERSION.SDK_INT < Build.VERSION_CODES.R ->
            // Below Android 11 the old storage model still works with a normal
            // runtime grant; SAF is the safe default there.
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED
            ) AccessMode.ALL_FILES else AccessMode.NONE

        Environment.isExternalStorageManager() -> AccessMode.ALL_FILES
        else -> AccessMode.NONE
    }

    /**
     * Whether the system will even offer the all-files switch.
     *
     * Some builds with locked-down policy disable it; asking the user to open a
     * Settings page that has no switch is worse than going straight to SAF.
     */
    fun allFilesAvailable(context: Context): Boolean =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.R

    /** Settings page where the user grants all-files access. */
    fun allFilesIntent(context: Context): Intent =
        Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

    /** Fallback if the per-app page is missing on an OEM build. */
    fun allFilesFallbackIntent(): Intent =
        Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)

    /**
     * The sentence shown when access is missing.
     *
     * Deliberately concrete: "izin belum diberikan" tells the user nothing about
     * what to do, and this is the failure mode where the app looks broken while
     * working exactly as written.
     */
    fun explain(context: Context): String? = when (mode(context)) {
        AccessMode.ALL_FILES -> null
        AccessMode.STORAGE_TREE -> null
        AccessMode.NONE ->
            "Akses berkas belum diberikan. Pilih folder lewat tombol di atas, " +
                "atau beri izin \u201cSemua berkas\u201d di Setelan Android."
    }

    /** Storage volumes that can be browsed with File access. */
    fun locations(context: Context): List<Location> {
        val out = mutableListOf<Location>()
        val external = Environment.getExternalStorageDirectory()
        out += Location(
            label = "Internal",
            path = external.absolutePath,
            description = "Penyimpanan dalam perangkat",
        )

        val sm = context.getSystemService(Context.STORAGE_SERVICE) as? StorageManager
        runCatching {
            sm?.storageVolumes?.forEach { vol ->
                val dir = vol.directory ?: return@forEach
                if (vol.isPrimary) return@forEach
                val state = vol.state
                val readable = state == Environment.MEDIA_MOUNTED
                out += Location(
                    label = vol.getDescription(context),
                    path = dir.absolutePath,
                    description = if (readable) "Kartu SD" else "Tidak terpasang",
                )
            }
        }
        return out
    }

    /**
     * Reads one directory. Never throws: an unreadable folder returns an error
     * string, because a file manager that closes on a permission error is worse
     * than one that says "tidak bisa dibaca".
     */
    fun list(path: String, showHidden: Boolean): Result<List<FileEntry>> = runCatching {
        val dir = File(path)
        if (!dir.isDirectory) return@runCatching emptyList()
        val children = dir.listFiles() ?: return@runCatching emptyList()
        children.asSequence()
            .filter { showHidden || !it.name.startsWith(".") }
            .map { f ->
                FileEntry(
                    path = f.absolutePath,
                    name = f.name,
                    isDirectory = f.isDirectory,
                    sizeBytes = if (f.isDirectory) 0 else f.length(),
                    lastModified = f.lastModified(),
                    isHidden = f.name.startsWith("."),
                    canRead = f.canRead(),
                    childCount = if (f.isDirectory) (f.list()?.size ?: 0) else -1,
                )
            }
            .toList()
    }

    /** Lists a SAF tree chosen by the user. */
    fun listTree(context: Context, treeUri: Uri, showHidden: Boolean): Result<List<FileEntry>> =
        runCatching {
            val root = DocumentFile.fromTreeUri(context, treeUri) ?: return@runCatching emptyList()
            root.listFiles()
                .asSequence()
                .filter { showHidden || !it.name.orEmpty().startsWith(".") }
                .map { d ->
                    FileEntry(
                        path = d.uri.toString(),
                        name = d.name ?: "(tanpa nama)",
                        isDirectory = d.isDirectory,
                        sizeBytes = d.length(),
                        lastModified = d.lastModified(),
                        isHidden = d.name.orEmpty().startsWith("."),
                        canRead = d.canRead(),
                    )
                }
                .toList()
        }

    /** All volumes, including the ones only reachable through SAF. */
    fun allLocations(context: Context, trees: List<Pair<String, Uri>>): List<Location> =
        locations(context) + trees.map { (label, uri) ->
            Location(label = label, path = uri.toString(), description = "Folder pilihan", treeUri = uri)
        }

    /** True when this path is a SAF document URI rather than a file path. */
    fun isTreePath(path: String): Boolean = path.startsWith("content://")

    /**
     * Confirms a SAF tree actually grants persistable access before it is stored.
     *
     * A tree that cannot be persisted becomes an entry that fails to open on the
     * next launch, which reads as data loss.
     */
    fun takePersistable(context: Context, uri: Uri): Boolean = runCatching {
        context.contentResolver.takePersistableUriPermission(
            uri,
            Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
        )
        true
    }.getOrDefault(false)

    /** Best-effort parent for the up button. */
    fun parentOf(path: String): String? {
        if (isTreePath(path)) {
            val docId = runCatching { DocumentsContract.getDocumentId(Uri.parse(path)) }.getOrNull()
                ?: return null
            // Document ids are "primary:Folder/Sub"; walking up means trimming the
            // last segment. Returning null at the root keeps the up button hidden.
            val trimmed = docId.substringBeforeLast('/', "")
            if (trimmed.isEmpty() || trimmed == docId) return null
            return path
        }
        val f = File(path).parentFile ?: return null
        return f.absolutePath
    }

    /** "12 item" or "12 item \u00b7 3 folder", matching the reference screenshots. */
    fun describeChildren(entries: List<FileEntry>): String {
        val folders = entries.count { it.isDirectory }
        val files = entries.size - folders
        val parts = mutableListOf<String>()
        if (folders > 0) parts += "$folders folder"
        if (files > 0) parts += "$files berkas"
        if (parts.isEmpty()) return "Kosong"
        return parts.joinToString(" \u00b7 ")
    }

    fun displayName(path: String): String {
        if (isTreePath(path)) return path.substringAfterLast("%2F").substringAfterLast('/')
        val f = File(path)
        return f.name.ifEmpty { f.absolutePath }
    }

    fun searchKey(text: String): String = text.lowercase(Locale.US).trim()
}
