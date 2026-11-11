package net.pure.manager.root

import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Root access, without a library.
 *
 * `libsu` would be the usual choice, but it is a dependency that has to be fetched
 * on every build in a sandbox whose only working network path is git. The work it
 * actually does here is small and stable: run the `su` binary, feed it a command
 * line, read the exit code. That is `ProcessBuilder` and about forty lines, and it
 * can be tested on the JVM by pointing it at `sh` instead of `su`.
 *
 * Three rules, each of which is a bug when violated:
 *
 *  - **Nothing blocks forever.** A root prompt that the user walked away from must
 *    not freeze the app; every command gets a timeout and is killed.
 *  - **No shell interpolation.** Arguments are quoted, because a file name with a
 *    space or an apostrophe is normal, and an unquoted name is how a rename turns
 *    into running a command.
 *  - **Absence is not an error.** A phone without root is the common case; the
 *    browser then keeps using the SAF path it already has.
 */
object Shell {

    /** Where Android keeps the su binary families. */
    private val candidates = listOf(
        "/system/bin/su",
        "/system/xbin/su",
        "/sbin/su",
        "/su/bin/su",
        "/system/sd/xbin/su",
        "/data/adb/ksu/bin/su",
        "/data/adb/ksu/bin/ksud",
        "/debug_ramdisk/su",
    )

    /** What one command produced. [code] is -1 when it never ran. */
    data class Output(val code: Int, val output: String, val error: String) {
        val ok: Boolean get() = code == 0
        /** The one line worth showing when something fails. */
        val message: String
            get() = error.lines().firstOrNull { it.isNotBlank() }
                ?: output.lines().firstOrNull { it.isNotBlank() }
                ?: "Perintah gagal (kode $code)"
    }

    /**
     * The su binary on this device, or null.
     *
     * Probing does not prompt: a file that exists is a file that exists. Asking
     * for the grant is a separate step, because on KernelSU and Magisk the prompt
     * is a dialog the user must see with a reason on screen, not something that
     * appears the moment the app launches.
     */
    fun suBinary(fileExists: (String) -> Boolean = { File(it).exists() }): String? =
        candidates.firstOrNull { fileExists(it) }

    /**
     * Runs [command] through [binary] and returns its result.
     *
     * [binary] is a parameter rather than always `/system/bin/su` so the JVM tests
     * can drive this with `sh` and a temp directory. Without that, the only way to
     * test a root shell is to own a rooted phone, and untested code that runs as
     * root is the worst place to be untested.
     */
    fun run(
        binary: String,
        command: String,
        timeoutSeconds: Long = 15L,
        env: Map<String, String> = emptyMap(),
    ): Output {
        val process = runCatching {
            ProcessBuilder(binary, "-c", command)
                .redirectErrorStream(false)
                .apply { environment().putAll(env) }
                .start()
        }.getOrElse {
            return Output(-1, "", it.message ?: "Tidak bisa menjalankan $binary")
        }

        val out = StringBuilder()
        val err = StringBuilder()
        // Reading on this thread with a timeout: a `su` that is waiting for the
        // grant dialog writes nothing and would hang any reader thread forever.
        val reader = Thread {
            runCatching { process.inputStream.bufferedReader().forEachLine { out.appendLine(it) } }
            runCatching { process.errorStream.bufferedReader().forEachLine { err.appendLine(it) } }
        }
        reader.isDaemon = true
        reader.start()

        val finished = process.waitFor(timeoutSeconds, TimeUnit.SECONDS)
        if (!finished) {
            runCatching { process.destroyForcibly() }
            reader.join(500)
            return Output(
                code = -1,
                output = out.toString(),
                error = "Perintah tidak menjawab dalam $timeoutSeconds detik " +
                    "(dialog izin root tidak dijawab?)",
            )
        }
        reader.join(1_000)
        return Output(process.exitValue(), out.toString(), err.toString())
    }

    /**
     * Quotes one argument for a POSIX shell.
     *
     * Single quotes around everything, with embedded single quotes closed and
     * reopened. `it's here` becomes `'it'\''s here'`. Any other scheme breaks on a
     * file name the user is allowed to have.
     */
    fun quote(arg: String): String = "'" + arg.replace("'", "'\\''") + "'"

    /** Joins a command and its arguments with quoting. */
    fun command(vararg parts: String): String = parts.joinToString(" ") { quote(it) }
}
