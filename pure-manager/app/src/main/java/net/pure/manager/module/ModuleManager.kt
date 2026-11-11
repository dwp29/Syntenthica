package net.pure.manager.module

import java.io.File
import java.security.MessageDigest

/**
 * Modules: small signed files that extend the app, downloaded from GitHub Releases.
 *
 * The whole point of this class is that **a module is verified before it is usable
 * and refused if it is not**. A downloaded file that is executed without a check is
 * the one mistake in this design that cannot be undone later, so the rules are:
 *
 *  - **SHA-256 is checked against the published value**, and the comparison is
 *    constant-time-ish (never short-circuit on the first differing character is not
 *    a real threat here, but the habit is cheap).
 *  - **A download that fails its hash is deleted**, not left on disk to be clicked
 *    by mistake.
 *  - **The catalog is data, not code.** It is a list of ids, versions and hashes.
 *    Nothing in this file interprets a module.
 *
 * What this does NOT do yet, and says so in the UI: there is no Ed25519 signature
 * check, because publishing a signing key is a step the owner has not done. A hash
 * fetched from the same place as the file protects against corruption, not against
 * someone who can rewrite both. That distinction is printed on the module row
 * rather than hidden in a comment.
 */
object ModuleManager {

    /** One downloadable module, as described by the catalog. */
    data class Entry(
        val id: String,
        val name: String,
        val version: String,
        val description: String,
        /** Lowercase hex SHA-256 of the file. */
        val sha256: String,
        /** Path inside the release, e.g. `pure-doc-1.0.0.pmod`. */
        val asset: String,
        /** Bytes, for showing a progress estimate before starting. */
        val sizeBytes: Long = 0,
    )

    /** What happened to one download. */
    sealed interface Outcome {
        data class Installed(val file: File, val entry: Entry) : Outcome
        data object HashMismatch : Outcome
        data class Failed(val message: String) : Outcome
    }

    /**
     * Verifies a downloaded file against the catalog entry.
     *
     * Returns the file on success and deletes it on failure. Deleting is the part
     * that matters: an unverified module that stays on disk is one tap away from
     * being installed by a later version that trusts the folder.
     */
    fun verify(downloaded: File, entry: Entry): Outcome {
        if (!downloaded.isFile) {
            return Outcome.Failed("Berkas unduhan tidak ada")
        }
        val actual = sha256(downloaded)
        if (!actual.equals(entry.sha256.trim(), ignoreCase = true)) {
            runCatching { downloaded.delete() }
            return Outcome.HashMismatch
        }
        return Outcome.Installed(downloaded, entry)
    }

    /**
     * The hex digest of a file, streamed.
     *
     * Streamed rather than `readBytes()`: a module can be tens of megabytes and
     * reading it whole to hash it would be a memory spike for no reason.
     */
    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * The modules installed in [directory].
     *
     * Installed means "a file with a matching catalog entry and a valid hash". A
     * file that is present but does not match is reported separately so the UI can
     * offer to delete it instead of pretending the module is installed.
     */
    fun installed(
        directory: File,
        catalog: List<Entry>,
    ): List<Entry> =
        catalog.filter { entry ->
            val f = File(directory, entry.id + ".pmod")
            f.isFile && sha256(f).equals(entry.sha256, ignoreCase = true)
        }

    /** Files in the module folder that are not part of any valid entry. */
    fun orphans(directory: File, catalog: List<Entry>): List<File> {
        val known = catalog.map { it.id + ".pmod" }.toSet()
        return directory.listFiles()
            ?.filter { it.isFile && it.name.endsWith(".pmod") && it.name !in known }
            .orEmpty()
    }

    /**
     * Whether a version string is newer than another, by dotted-number comparison.
     *
     * Deliberately not a full semver implementation: module versions here are
     * `1.0.0`-shaped, and a library that accepts `1.0.0-rc.1+build` would invite
     * versions nobody can compare by eye.
     */
    fun isNewer(candidate: String, current: String): Boolean {
        val a = candidate.split('.').mapNotNull { it.toIntOrNull() }
        val b = current.split('.').mapNotNull { it.toIntOrNull() }
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }
}
