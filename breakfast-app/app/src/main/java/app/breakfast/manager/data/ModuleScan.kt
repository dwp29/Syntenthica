package app.breakfast.manager.data

/**
 * KernelSU modules, from /data/adb/modules.
 *
 * This page used to read /proc/modules, which is a different thing entirely:
 * *.ko kernel objects, almost all of which a phone kernel links in statically.
 * The modules a person installs (Zygisk, busybox, tweaks) live as directories
 * under /data/adb/modules, and that is what was asked for. Reading the wrong file
 * meant the page could never show them no matter how many were installed.
 *
 * Both are kept, because both are facts worth having. Each carries its own
 * confidence, and neither may be described with the other's sentence: a failed
 * listing never becomes "0 modul", and a kernel object is never called an
 * installed module.
 */
object ModuleScan {

    data class Module(val name: String, val sizeBytes: Long, val usedBy: String)

    /** How the scan ended. Only [Loaded] may be described as a module list. */
    sealed interface Result {
        /** The file was read. An empty list here means genuinely no modules. */
        data class Loaded(val modules: List<Module>, val rawLines: Int) : Result

        /** The file exists but could not be opened; usually a permission problem. */
        data class Unreadable(val read: FileRead) : Result

        /** The file does not exist on this kernel at all. */
        data object NoProcModules : Result
    }

    /** One installed KernelSU module, as its directory says it is. */
    data class InstalledModule(
        val id: String,
        val version: String?,
        val description: String?,
        val enabled: Boolean,
        val updatePending: Boolean,
        val removePending: Boolean,
    )

    /** The installed-module listing, with the same honesty as [Result]. */
    sealed interface Installed {
        /** The directory was listed. An empty list here is genuinely zero modules. */
        data class Listed(val modules: List<InstalledModule>, val entries: Int) : Installed
        data class Unreadable(val read: FileRead) : Installed
        data object NoDirectory : Installed
    }

    const val INSTALLED_DIR = "/data/adb/modules"

    /**
     * Reads the modules directory through [read], which defaults to an ordinary
     * file read. Directory listing is done separately because FileRead models
     * files; the two failure modes are merged here with one rule: anything that
     * is not a successful listing is not a count.
     */
    fun scanInstalled(
        list: (String) -> List<String>? = { path -> java.io.File(path).list()?.toList() },
        read: (String) -> FileRead = { FileRead.read(it) },
    ): Installed {
        val entries = try {
            list(INSTALLED_DIR)
        } catch (e: SecurityException) {
            null
        } ?: run {
            val probe = read(INSTALLED_DIR)
            return if (probe is FileRead.Missing) Installed.NoDirectory
            else Installed.Unreadable(probe)
        }

        // A regular file such as .keep is not a module; only directories are.
        val modules = entries
            .filter { !it.startsWith(".") }
            .sorted()
            .map { id ->
                val dir = "$INSTALLED_DIR/$id"
                InstalledModule(
                    id = id,
                    version = read("$dir/module.prop").textOrNull()
                        ?.let { prop(it, "version") },
                    description = read("$dir/module.prop").textOrNull()
                        ?.let { prop(it, "description") },
                    // KernelSU's convention: a disable/remove file marks intent.
                    enabled = !exists("$dir/disable", read),
                    updatePending = exists("$dir/update", read),
                    removePending = exists("$dir/remove", read),
                )
            }
        return Installed.Listed(modules, entries.size)
    }

    private fun exists(path: String, read: (String) -> FileRead): Boolean =
        read(path) !is FileRead.Missing

    /** module.prop is a flat key=value file; a missing key is null, not empty. */
    fun prop(text: String, key: String): String? =
        text.lineSequence()
            .map { it.trim() }
            .firstOrNull { it.startsWith("$key=") }
            ?.substringAfter('=')
            ?.trim()
            ?.takeIf { it.isNotEmpty() }

    /** The sentence for installed modules, kept pure so a test can hold it still. */
    fun describeInstalled(result: Installed): Pair<String, String?> = when (result) {
        is Installed.Listed ->
            if (result.modules.isEmpty()) {
                "0 modul terpasang." to
                    "$INSTALLED_DIR terbaca ${result.entries} entri dan tidak ada satu pun " +
                    "direktori modul. Ini hasil pembacaan, bukan tebakan."
            } else {
                "${result.modules.size} modul terpasang" to null
            }
        is Installed.Unreadable ->
            "Daftar modul terpasang tidak bisa dibaca." to
                result.read.explain(INSTALLED_DIR) +
                ". Ini bukan pernyataan bahwa tidak ada modul terpasang."
        Installed.NoDirectory ->
            "Belum ada modul terpasang." to
                "$INSTALLED_DIR tidak ada. Pengelola root membuat direktori ini saat root " +
                "pertama kali berjalan, jadi ini juga berarti root belum pernah aktif."
    }

    /** Parses /proc/modules: name size refcount deps state address. */
    fun parse(text: String?): List<Module> {
        if (text == null) return emptyList()
        return text.lineSequence()
            .mapNotNull { line ->
                val parts = line.trim().split(Regex("\\s+"))
                if (parts.size < 3) return@mapNotNull null
                val name = parts[0].takeIf { it.isNotEmpty() } ?: return@mapNotNull null
                val size = parts[1].toLongOrNull() ?: return@mapNotNull null
                val deps = parts[3].takeIf { it != "-" && it.isNotEmpty() } ?: ""
                Module(name, size, deps)
            }
            .sortedBy { it.name }
            .toList()
    }

    fun scan(read: (String) -> FileRead = { FileRead.read(it) }): Result {
        val path = "/proc/modules"
        return when (val result = read(path)) {
            is FileRead.Ok -> {
                val lines = result.text.lineSequence().count { it.isNotBlank() }
                Result.Loaded(parse(result.text), lines)
            }
            FileRead.Missing -> Result.NoProcModules
            else -> Result.Unreadable(result)
        }
    }

    /**
     * Modules as the app should describe them, including the wording that must
     * match the evidence. Kept pure so a unit test can hold it still.
     */
    fun describe(result: Result): Pair<String, String?> {
        return when (result) {
            is Result.Loaded ->
                if (result.modules.isEmpty()) {
                    "Kernel ini memuat 0 modul." to
                        "/proc/modules terbaca ${result.rawLines} baris dan kosong. " +
                        "Banyak kernel OpenELA menautkan driver secara statis, jadi daftar " +
                        "kosong adalah fakta kernel, bukan kesalahan."
                } else {
                    "${result.modules.size} modul termuat" to null
                }
            is Result.Unreadable ->
                "Daftar modul tidak bisa dibaca." to
                    result.read.explain("/proc/modules") +
                    ". Ini bukan pernyataan bahwa tidak ada modul."
            Result.NoProcModules ->
                "Kernel ini tidak menyediakan /proc/modules." to
                    "Berkasnya tidak ada dan direktorinya sudah diperiksa. Kernel tanpa " +
                    "CONFIG_MODULES memang tidak membuat berkas ini."
        }
    }
}
