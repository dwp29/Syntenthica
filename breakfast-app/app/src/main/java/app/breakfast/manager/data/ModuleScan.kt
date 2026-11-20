package app.breakfast.manager.data

/**
 * Kernel modules actually loaded, from /proc/modules.
 *
 * The previous version returned an empty list both when the file could not be
 * read AND when it had no modules, so the screen said "Kernel ini tidak memuat
 * modul apa pun" on a device where the file simply was not readable. That is the
 * same mistake as reporting 0 C as a healthy temperature: an absence the app
 * never established, stated as fact.
 *
 * [scan] now returns a [Result] carrying the reason, and the screen can only
 * claim "no modules" when the file was actually read.
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
