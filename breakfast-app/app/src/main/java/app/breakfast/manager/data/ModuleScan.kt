package app.breakfast.manager.data

/**
 * Kernel modules actually loaded, from /proc/modules.
 *
 * MODULES used to be a placeholder that said the list "belum ada di build ini",
 * which was untrue: the device has modules and the app can read /proc/modules
 * without root. This reports what is there and nothing about what is not.
 */
object ModuleScan {

    data class Module(val name: String, val sizeBytes: Long, val usedBy: String)

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

    fun scan(read: (String) -> String? = { DeviceFiles.read(it) }): List<Module> =
        parse(read("/proc/modules"))
}
