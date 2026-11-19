package app.breakfast.manager.data

import java.io.File
import java.util.concurrent.TimeUnit

/**
 * The only place this app talks to the kernel.
 *
 * Everything goes through `su -c`, which means the app holds no root itself and
 * KernelSU decides per call whether to grant it. No shell string in this file is
 * ever built from user input: commands are constants, and the single dynamic
 * argument (a whitelisted path) is validated before it gets here.
 */
object RootBridge {

    private const val TIMEOUT_SECONDS = 8L

    data class Output(val ok: Boolean, val stdout: String, val exitCode: Int)

    /** Runs a fixed command with root. Returns ok=false when root was refused. */
    fun run(command: String): Output = try {
        val process = ProcessBuilder("su", "-c", command)
            .redirectErrorStream(false)
            .start()
        val stdout = process.inputStream.bufferedReader().use { it.readText() }
        val finished = process.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        if (!finished) {
            process.destroyForcibly()
            Output(false, stdout, -1)
        } else {
            Output(process.exitValue() == 0, stdout, process.exitValue())
        }
    } catch (e: Exception) {
        // No su binary at all: not a rooted device, or the manager is not
        // installed. Either way it is "unavailable", not "empty".
        Output(false, "", -1)
    }

    /**
     * `uname -r` capped to its first 64 characters.
     *
     * The cap is not cosmetic: the pairing table is matched exactly, and a
     * release string that has been silently truncated would be the wrong key.
     * Truncation is therefore done once, here, and the table is checked against
     * the same length at build time.
     */
    fun kernelRelease(): String? {
        val cached = System.getProperty("os.version")?.trim()
        if (!cached.isNullOrEmpty()) return cached.take(64)
        val output = run("uname -r")
        return output.stdout.trim().takeIf { it.isNotEmpty() }?.take(64)
    }

    /** Non-root read; used for uptime, which /proc exposes to everyone. */
    fun uptimeHours(): Double? = try {
        File("/proc/uptime").readText().trim().split(' ').firstOrNull()?.toDoubleOrNull()
            ?.let { it / 3600.0 }
    } catch (e: Exception) {
        null
    }

    fun hasRoot(): Boolean = run("id -u").stdout.trim() == "0"
}
