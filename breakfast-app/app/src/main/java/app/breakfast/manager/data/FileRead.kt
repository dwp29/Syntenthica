package app.breakfast.manager.data

/**
 * A file read that refuses to hide why it failed.
 *
 * Every read in this app used to be `try { readText() } catch { null }`, which
 * collapsed "no such file", "permission denied" and "this is a directory" into
 * one silent null. That is how MODULES came to say "kernel ini tidak memuat
 * modul apa pun" when /proc/modules simply could not be opened, and how the ROOT
 * page came to say su was not found on a device running KernelSU.
 *
 * The three cases below are different facts and are never merged.
 */
sealed interface FileRead {
    data class Ok(val text: String) : FileRead

    /** The file exists but this process may not open it. Wants root, not a retry. */
    data object Denied : FileRead

    /** No such file, and the parent directory was listed to prove it. */
    data object Missing : FileRead

    /** Exists, but is a directory or otherwise not a file. */
    data object NotAFile : FileRead

    /** Something else went wrong; the message is kept so it can be shown. */
    data class Failed(val reason: String) : FileRead

    val isOk: Boolean get() = this is Ok
    fun textOrNull(): String? = (this as? Ok)?.text

    /** One short Indonesian sentence, safe to show in the UI. */
    fun explain(path: String): String = when (this) {
        is Ok -> "terbaca"
        Denied -> "$path tidak bisa dibuka: izin ditolak. Ini masalah izin, bukan bukti file tidak ada"
        Missing -> "$path tidak ada (direktori induknya sudah diperiksa)"
        NotAFile -> "$path ada, tetapi bukan berkas biasa"
        is Failed -> "$path gagal dibaca: $reason"
    }

    companion object {
        /** Reads through java.io, separating the failure modes instead of flattening them. */
        fun read(path: String): FileRead = try {
            val file = java.io.File(path)
            when {
                !file.exists() -> {
                    // exists() is not proof of absence when a parent cannot be read.
                    val parent = file.parentFile
                    val listed = try {
                        parent?.list()
                    } catch (e: SecurityException) {
                        null
                    }
                    if (listed != null && file.name !in listed) Missing else Denied
                }
                file.isDirectory -> NotAFile
                !file.canRead() -> Denied
                else -> Ok(file.readText())
            }
        } catch (e: SecurityException) {
            Denied
        } catch (e: java.io.FileNotFoundException) {
            Denied
        } catch (e: Exception) {
            Failed(e.javaClass.simpleName)
        }
    }
}
