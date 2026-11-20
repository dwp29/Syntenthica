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

    data class Output(
        val ok: Boolean,
        val stdout: String,
        val exitCode: Int,
        /** True when su never answered; a different problem from being refused. */
        val timedOut: Boolean = false,
    )

    /**
     * Runs a fixed command with root. Returns ok=false when root was refused.
     *
     * The previous version read stdout to EOF before waitFor(), so the timeout
     * could never fire: if su started and then blocked waiting for a prompt the
     * user never saw, this call blocked forever and the app looked frozen. The
     * wait now comes first, and the stream is drained afterwards.
     */
    fun run(command: String): Output = try {
        val process = ProcessBuilder("su", "-c", command)
            .redirectErrorStream(true)
            .start()
        // Feed su's stdin nothing and close it: if a manager is waiting for a
        // keystroke on stdin it gets EOF instead of hanging.
        process.outputStream.close()
        val finished = process.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        val stdout = process.inputStream.bufferedReader().use { it.readText() }.trim()
        if (!finished) {
            process.destroyForcibly()
            Output(false, stdout, -1, timedOut = true)
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

    /**
     * Whether a su binary exists at all.
     *
     * Distinguishes "not rooted" from "root refused": without this, a device
     * with no KernelSU looks identical to one where the user tapped Deny, and
     * the advice for the two is completely different.
     */
    fun suExists(): Boolean = listOf(
        "/system/bin/su",
        "/system/xbin/su",
        "/sbin/su",
        "/data/adb/ksu/bin/su",
        "/debug_ramdisk/su",
    ).any { path ->
        try {
            java.io.File(path).exists()
        } catch (e: SecurityException) {
            false
        }
    }
}
